"""Senhas, tokens e sessões de refresh (ADR-003)."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.infra.modelos import Paciente, SessaoRefresh, TentativaLogin, Usuario

_hasher = PasswordHasher()  # Argon2id com os parâmetros padrão da biblioteca


def hash_senha(senha: str) -> str:
    return _hasher.hash(senha)


@lru_cache
def _hash_ficticio() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def conferir_senha(senha_hash: str | None, senha: str) -> bool:
    """Sem usuário, confere contra um hash fictício: o tempo de resposta fica parecido (AM-005).

    Hash inválido (ex.: `!sem-senha` de um seed antigo) conta como senha errada.
    """
    try:
        return _hasher.verify(senha_hash or _hash_ficticio(), senha) and senha_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def precisa_rehash(senha_hash: str) -> bool:
    return _hasher.check_needs_rehash(senha_hash)


def sha256(valor: str) -> str:
    """Hash do refresh token. Basta SHA-256 puro: o token tem 256 bits de entropia."""
    return hashlib.sha256(valor.encode()).hexdigest()


def hash_identificador(identificador: str) -> str:
    """HMAC-SHA256 do CPF ou e-mail normalizado. Sem a chave, não se reverte testando os
    ~10^9 CPFs possíveis, como aconteceria com um SHA-256 puro."""
    chave = get_settings().login_hash_key.get_secret_value().encode()
    return hmac.new(chave, identificador.encode(), hashlib.sha256).hexdigest()


def emitir_access_token(
    usuario_id: UUID, papel: str, familia_id: UUID, agora: datetime, ttl: timedelta, chave: str
) -> tuple[str, datetime]:
    """JWT HS256 sem dado pessoal. Devolve o token e quando expira.

    `sid` é a família do refresh token: revogada a família (logout, reuso, suspensão), o access
    token cai na hora. `papel` é só informativo: a autorização usa o papel lido do banco.
    """
    expira_em = agora + ttl
    claims = {
        "sub": str(usuario_id),
        "sid": str(familia_id),
        "papel": papel,
        "iat": int(agora.timestamp()),
        "exp": int(expira_em.timestamp()),
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, chave, algorithm="HS256"), expira_em


def ler_access_token(token: str, agora: datetime, chave: str) -> tuple[UUID, UUID] | None:
    """(ID do usuário, família da sessão), ou None se o token é inválido ou venceu.

    Não depende do transporte: a web manda o token em cookie; o Bearer não será
    ativado (ADR-003). O vencimento é conferido com o `Relogio`, não com o
    relógio do PyJWT, para os testes poderem fixar o tempo.
    """
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            chave,
            algorithms=["HS256"],
            options={
                "require": ["sub", "sid", "papel", "exp", "iat", "jti"],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
        if claims["exp"] <= agora.timestamp():
            return None
        return UUID(claims["sub"]), UUID(claims["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None


def abrir_sessao(
    session: Session,
    usuario_id: UUID,
    agora: datetime,
    ttl: timedelta,
    ip: str | None,
    familia_id: UUID | None = None,
) -> tuple[str, SessaoRefresh]:
    """Cria um refresh token opaco. O banco guarda só o hash; o token vai para o cookie."""
    token = secrets.token_urlsafe(32)
    sessao = SessaoRefresh(
        usuario_id=usuario_id,
        familia_id=familia_id or uuid4(),
        token_hash=sha256(token),
        expira_em=agora + ttl,
        ip=ip,
    )
    session.add(sessao)
    session.flush()
    return token, sessao


def familia_ativa(session: Session, familia_id: UUID) -> bool:
    """A família tem ao menos um refresh não revogado (logout e reuso revogam todos).

    Um refresh vencido e não revogado ainda conta: o access token dura minutos e o job de
    retenção apaga os vencidos.
    """
    return session.scalar(
        select(
            exists().where(
                SessaoRefresh.familia_id == familia_id, SessaoRefresh.revogado_em.is_(None)
            )
        )
    )


def revogar_sessoes(session: Session, agora: datetime, *criterios: Any) -> None:
    """Revoga as sessões ainda abertas que atendem aos critérios (família ou usuário).

    Trava antes de atualizar: se um refresh concorrente estiver rotacionando, a trava espera o
    commit dele, e o UPDATE (outro comando, outro snapshot em READ COMMITTED) já vê a sessão
    nova. Sem isso, o logout deixaria viva a sessão que o refresh acabou de criar.
    """
    session.execute(select(SessaoRefresh.id).where(*criterios).with_for_update())
    session.execute(
        update(SessaoRefresh)
        .where(SessaoRefresh.revogado_em.is_(None), *criterios)
        .values(revogado_em=agora)
    )


def buscar_para_login(session: Session, tipo: str, identificador: str) -> Usuario | None:
    """Paciente entra com CPF; a equipe, com e-mail. Paciente com e-mail não entra por ele."""
    if tipo == "CPF":
        consulta = select(Usuario).join(Paciente, Paciente.usuario_id == Usuario.id)
        return session.scalar(consulta.where(Paciente.cpf == identificador))
    return session.scalar(
        select(Usuario).where(Usuario.email == identificador, Usuario.papel != "PACIENTE")
    )


def registrar_tentativa(
    session: Session,
    tipo: str,
    agora: datetime,
    ip: str | None,
    sucesso: bool,
    identificador_hash: str | None = None,
) -> None:
    session.add(
        TentativaLogin(
            tipo=tipo,
            identificador_hash=identificador_hash,
            ip=ip,
            sucesso=sucesso,
            ocorrido_em=agora,
        )
    )


def falhas_de_login(
    session: Session, desde: datetime, ip: str | None, identificador_hash: str
) -> int:
    """Maior número de falhas na janela: pelo IP ou pelo identificador (AM-004)."""
    base = select(func.count()).where(
        TentativaLogin.tipo == "LOGIN",
        TentativaLogin.sucesso.is_(False),
        TentativaLogin.ocorrido_em > desde,
    )
    pelo_identificador = session.scalar(
        base.where(TentativaLogin.identificador_hash == identificador_hash)
    )
    pelo_ip = session.scalar(base.where(TentativaLogin.ip == ip)) if ip else 0
    return max(pelo_identificador or 0, pelo_ip or 0)


def registros_do_ip(session: Session, desde: datetime, ip: str) -> int:
    """Registros tentados pelo IP na janela, com ou sem sucesso (criação de contas em massa)."""
    return (
        session.scalar(
            select(func.count()).where(
                TentativaLogin.tipo == "REGISTRO",
                TentativaLogin.ip == ip,
                TentativaLogin.ocorrido_em > desde,
            )
        )
        or 0
    )


RETENCAO_TENTATIVAS = timedelta(hours=24)  # data-protection.md (proposta)


def apagar_dados_vencidos(session: Session, agora: datetime) -> int:
    """Apaga tentativas com mais de 24 h e refresh tokens vencidos. Idempotente; não faz commit.

    As tentativas só servem à janela do limite (minutos). Um refresh vencido não renova nada
    e já não segura access token (que dura minutos).
    """
    # Subconsulta, não lista no Python: um backlog grande não estoura o limite de parâmetros.
    # SKIP LOCKED: a sessão travada por um refresh em andamento fica para a próxima rodada.
    vencidas = (
        select(SessaoRefresh.id)
        .where(SessaoRefresh.expira_em < agora)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    # Quem aponta para uma sessão que vai ser apagada perde o ponteiro (FK RESTRICT).
    session.execute(
        update(SessaoRefresh)
        .where(SessaoRefresh.substituido_por_id.in_(vencidas))
        .values(substituido_por_id=None)
    )
    sessoes = session.execute(delete(SessaoRefresh).where(SessaoRefresh.id.in_(vencidas)))
    tentativas = session.execute(
        delete(TentativaLogin).where(TentativaLogin.ocorrido_em < agora - RETENCAO_TENTATIVAS)
    )
    return sessoes.rowcount + tentativas.rowcount
