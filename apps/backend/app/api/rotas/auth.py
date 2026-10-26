"""Registro, login, refresh, logout e /me (ADR-003, ADR-028, UC-001)."""

import logging
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import (
    COOKIE_ACCESS,
    COOKIE_CSRF,
    COOKIE_REFRESH,
    Problema,
    esquema_refresh,
    get_relogio,
    get_session,
    ip_do_cliente,
    usuario_da_sessao_sem_troca,
)
from app.api.problemas import CSRF, NAO_AUTENTICADO, erros
from app.api.tipos import Papel
from app.config import get_settings
from app.dominio.acesso import (
    SENHA_MINIMA,
    normalizar_identificador,
    pode_autenticar,
    refresh_na_tolerancia,
    tentativas_esgotadas,
    verificar_troca_de_senha,
)
from app.dominio.cadastro import EMAIL, cns_valido, cpf_valido, erro_data_nascimento
from app.dominio.erros import EntradaInvalida
from app.dominio.relogio import Relogio
from app.infra.acesso import carregar_escopo
from app.infra.autenticacao import (
    abrir_sessao,
    buscar_para_login,
    conferir_senha,
    emitir_access_token,
    falhas_de_login,
    familia_ativa,
    hash_identificador,
    hash_senha,
    ler_access_token,
    precisa_rehash,
    registrar_tentativa,
    registros_do_ip,
    revogar_sessoes,
    sha256,
)
from app.infra.modelos import Auditoria, Consentimento, Paciente, SessaoRefresh, Usuario

logger = logging.getLogger(__name__)
router = APIRouter(tags=["autenticacao"])

SessionDep = Annotated[Session, Depends(get_session)]
RelogioDep = Annotated[Relogio, Depends(get_relogio)]

PATH_ACCESS = "/api/v1"
PATH_REFRESH = "/api/v1/auth"
MENSAGEM_DUPLICADO = (
    "Não foi possível concluir o cadastro. Se você já tem conta, entre com seu CPF."
)


def _nao_autenticado() -> Problema:
    return Problema(401, "/problemas/nao-autenticado", "Sessão inválida ou expirada.")


def _muitas_tentativas() -> Problema:
    minutos = get_settings().login_janela_min
    return Problema(
        429,
        "/problemas/muitas-tentativas",
        "Muitas tentativas. Aguarde alguns minutos e tente de novo.",
        headers={"Retry-After": str(minutos * 60)},
    )


def _so_digitos(valor: str) -> str:
    return re.sub(r"[.\-\s]", "", valor)


class RegistroEntrada(BaseModel):
    """AM-013: sem papel, situação, classificação de risco nem IDs; campo extra → 422."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=200)
    cpf: str = Field(max_length=14)
    cns: str = Field(max_length=18)
    data_nascimento: date
    sexo: Literal["FEMININO", "MASCULINO"] | None = None
    municipio: str = Field(min_length=2, max_length=100)
    telefone: str = Field(min_length=10, max_length=20)
    email: str | None = Field(default=None, max_length=254)
    senha: SecretStr = Field(min_length=SENHA_MINIMA, max_length=256)
    aceite_termo: Literal[True]
    versao_termo: str = Field(min_length=1, max_length=20)
    aceite_lembrete_email: bool = False

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, valor: str) -> str:
        valor = _so_digitos(valor)
        if not cpf_valido(valor):
            raise ValueError("CPF inválido.")
        return valor

    @field_validator("cns")
    @classmethod
    def _cns(cls, valor: str) -> str:
        valor = _so_digitos(valor)
        if not cns_valido(valor):
            raise ValueError("Cartão do SUS inválido.")
        return valor

    @field_validator("versao_termo")
    @classmethod
    def _versao_vigente(cls, valor: str) -> str:
        if valor != get_settings().termo_versao_atual:
            raise ValueError("Aceite de uma versão do termo que não é a vigente.")
        return valor

    @field_validator("telefone")
    @classmethod
    def _telefone(cls, valor: str) -> str:
        valor = re.sub(r"[\s()\-+]", "", valor)
        if not valor.isdigit() or not 10 <= len(valor) <= 13:
            raise ValueError("Telefone inválido.")
        return valor

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str | None) -> str | None:
        if not valor:
            return None
        if not EMAIL.match(valor):
            raise ValueError("E-mail inválido.")
        return valor.lower()

    @model_validator(mode="after")
    def _lembrete_exige_email(self) -> "RegistroEntrada":
        if self.aceite_lembrete_email and not self.email:
            raise ValueError("Lembretes por e-mail exigem um e-mail.")
        return self


class LoginEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identificador: str = Field(min_length=1, max_length=254, description="CPF ou e-mail")
    senha: SecretStr = Field(min_length=1, max_length=256)


class SessaoSaida(BaseModel):
    """Os tokens vão só em cookies httpOnly (ADR-003); o corpo não traz token."""

    papel: Papel
    expira_em: datetime


class LoginSaida(SessaoSaida):
    """`trocar_senha` só aparece (`true`) para conta com senha temporária: o frontend deve levar
    a pessoa à troca, porque o resto da API responde 403 até lá."""

    trocar_senha: Literal[True] | None = None


class TrocaSenhaEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A atual só não pode ser vazia: uma senha antiga curta ainda tem de chegar ao domínio.
    senha_atual: SecretStr = Field(min_length=1, max_length=256)
    senha_nova: SecretStr = Field(min_length=SENHA_MINIMA, max_length=256)


class EuSaida(BaseModel):
    """Para o paciente, nunca posição nem tamanho da fila (ADR-007).

    Todas as chaves vêm sempre. `nome` é `null` na equipe (`usuario` não tem nome) e `filas`
    é `null` no paciente; na equipe, `filas` traz o escopo (ADR-025), `[]` se não houver.
    """

    id: UUID
    papel: Papel
    nome: str | None
    filas: list[UUID] | None
    # Opcional: só aparece (`true`) com senha temporária; sem ele a resposta não muda.
    trocar_senha: Literal[True] | None = None


def _cookie(response: Response, nome: str, valor: str, path: str, max_age: int, httponly: bool):
    settings = get_settings()
    response.set_cookie(
        nome,
        valor,
        max_age=max_age,
        path=path,
        domain=settings.cookie_domain or None,
        secure=settings.cookie_secure,
        httponly=httponly,
        samesite=settings.cookie_samesite,
    )


def _iniciar_sessao(
    session: Session,
    response: Response,
    usuario: Usuario,
    agora: datetime,
    ip: str | None,
    familia_id: UUID | None = None,
) -> tuple[SessaoSaida, SessaoRefresh]:
    """Emite access token, refresh token e token CSRF, cada um no seu cookie."""
    settings = get_settings()
    ttl_access = timedelta(minutes=settings.access_token_ttl_minutos)
    ttl_refresh = timedelta(days=settings.refresh_token_ttl_dias)
    refresh, sessao = abrir_sessao(session, usuario.id, agora, ttl_refresh, ip, familia_id)
    access, expira_em = emitir_access_token(
        usuario.id,
        usuario.papel,
        sessao.familia_id,
        agora,
        ttl_access,
        settings.jwt_secret_key.get_secret_value(),
    )
    segundos_refresh = int(ttl_refresh.total_seconds())
    _cookie(response, COOKIE_ACCESS, access, PATH_ACCESS, int(ttl_access.total_seconds()), True)
    _cookie(response, COOKIE_REFRESH, refresh, PATH_REFRESH, segundos_refresh, True)
    # Não httpOnly: o frontend lê e devolve no header (double-submit).
    _cookie(response, COOKIE_CSRF, secrets.token_urlsafe(32), "/", segundos_refresh, False)
    return SessaoSaida(papel=usuario.papel, expira_em=expira_em), sessao


def _apagar_cookies(response: Response) -> None:
    domain = get_settings().cookie_domain or None
    for nome, path in (
        (COOKIE_ACCESS, PATH_ACCESS),
        (COOKIE_REFRESH, PATH_REFRESH),
        (COOKIE_CSRF, "/"),
    ):
        response.delete_cookie(nome, path=path, domain=domain)


@router.post(
    "/auth/registro",
    status_code=201,
    responses=erros((409, "cadastro-nao-concluido"), (429, "muitas-tentativas"), 422),
)
def registrar(
    dados: RegistroEntrada,
    request: Request,
    response: Response,
    session: SessionDep,
    relogio: RelogioDep,
) -> SessaoSaida:
    """UC-001. CPF, cartão do SUS ou e-mail já cadastrados dão o mesmo 409 genérico (AM-005)."""
    settings = get_settings()
    agora = relogio.agora()
    hoje = agora.astimezone(ZoneInfo(settings.timezone_exibicao)).date()
    if erro := erro_data_nascimento(dados.data_nascimento, hoje):
        raise RequestValidationError(
            [{"loc": ("body", "data_nascimento"), "msg": erro, "type": "value_error"}]
        )
    ip = ip_do_cliente(request)
    desde = agora - timedelta(minutes=settings.login_janela_min)
    if ip and tentativas_esgotadas(
        registros_do_ip(session, desde, ip), settings.registro_max_tentativas
    ):
        raise _muitas_tentativas()

    senha_hash = hash_senha(dados.senha.get_secret_value())
    try:
        # As UNIQUE do banco decidem a duplicidade: um só caminho para CPF, CNS e e-mail,
        # sem corrida entre consultar e inserir.
        with session.begin_nested():
            usuario = Usuario(email=dados.email, senha_hash=senha_hash, papel="PACIENTE")
            session.add(usuario)
            session.flush()
            paciente = Paciente(
                usuario_id=usuario.id,
                nome=dados.nome,
                cpf=dados.cpf,
                cns=dados.cns,
                data_nascimento=dados.data_nascimento,
                telefone=dados.telefone,
                sexo=dados.sexo,
                municipio=dados.municipio,
            )
            session.add(paciente)
            session.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) != "23505":
            raise
        registrar_tentativa(session, "REGISTRO", agora, ip, sucesso=False)
        session.commit()
        raise Problema(409, "/problemas/cadastro-nao-concluido", MENSAGEM_DUPLICADO) from None

    finalidades = ["AGENDAMENTO"] + (["LEMBRETE_EMAIL"] if dados.aceite_lembrete_email else [])
    session.add_all(
        Consentimento(paciente_id=paciente.id, finalidade=f, versao_termo=dados.versao_termo)
        for f in finalidades
    )
    session.add(
        Auditoria(
            ator_usuario_id=usuario.id,
            acao="REGISTRO",
            entidade="paciente",
            entidade_id=paciente.id,
            dados_depois={"consentimentos": finalidades, "versao_termo": dados.versao_termo},
            ip=ip,
        )
    )
    registrar_tentativa(session, "REGISTRO", agora, ip, sucesso=True)
    corpo, _ = _iniciar_sessao(session, response, usuario, agora, ip)
    session.commit()
    logger.info("registro: usuario=%s", usuario.id)
    return corpo


@router.post(
    "/auth/login",
    response_model_exclude_none=True,
    responses=erros((401, "credenciais-invalidas"), (429, "muitas-tentativas"), 422),
)
def login(
    dados: LoginEntrada,
    request: Request,
    response: Response,
    session: SessionDep,
    relogio: RelogioDep,
) -> LoginSaida:
    """CPF (paciente) ou e-mail (equipe). Inexistente, senha errada e suspenso respondem igual."""
    settings = get_settings()
    agora = relogio.agora()
    ip = ip_do_cliente(request)
    tipo, identificador = normalizar_identificador(dados.identificador)
    identificador_hash = hash_identificador(identificador)
    desde = agora - timedelta(minutes=settings.login_janela_min)
    falhas = falhas_de_login(session, desde, ip, identificador_hash)
    if tentativas_esgotadas(falhas, settings.login_max_tentativas):
        raise _muitas_tentativas()

    senha = dados.senha.get_secret_value()
    usuario = buscar_para_login(session, tipo, identificador)
    senha_ok = conferir_senha(usuario.senha_hash if usuario else None, senha)
    if usuario is None or not senha_ok or not pode_autenticar(usuario.situacao):
        registrar_tentativa(session, "LOGIN", agora, ip, False, identificador_hash)
        session.commit()
        raise Problema(401, "/problemas/credenciais-invalidas", "Identificador ou senha inválidos.")

    if precisa_rehash(usuario.senha_hash):
        usuario.senha_hash = hash_senha(senha)
    registrar_tentativa(session, "LOGIN", agora, ip, True, identificador_hash)
    session.add(
        Auditoria(
            ator_usuario_id=usuario.id,
            acao="LOGIN",
            entidade="usuario",
            entidade_id=usuario.id,
            ip=ip,
        )
    )
    corpo, _ = _iniciar_sessao(session, response, usuario, agora, ip)
    session.commit()
    logger.info("login: usuario=%s", usuario.id)
    return LoginSaida(**corpo.model_dump(), trocar_senha=True if usuario.senha_temporaria else None)


@router.post(
    "/auth/trocar-senha",
    status_code=204,
    responses=erros(NAO_AUTENTICADO, CSRF, 422, (429, "muitas-tentativas")),
)
def trocar_senha(
    dados: TrocaSenhaEntrada,
    request: Request,
    usuario: Annotated[Usuario, Depends(usuario_da_sessao_sem_troca)],
    session: SessionDep,
    relogio: RelogioDep,
) -> Response:
    """Qualquer usuário autenticado. Zera `senha_temporaria` e revoga as outras sessões; a
    atual continua. Senha atual errada conta no limite do login (AM-020), por usuário e por IP,
    e o excesso responde 429 sem revogar nada."""
    settings = get_settings()
    agora = relogio.agora()
    ip = ip_do_cliente(request)
    # Serializa por usuário e relê o estado: tentativas paralelas esperam a anterior gravar a
    # falha (o limite vale no total, não por lote) e uma redefinição, troca ou suspensão
    # concorrente já commitada é vista antes de conferir e gravar a senha.
    usuario = session.scalar(
        select(Usuario)
        .where(Usuario.id == usuario.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if usuario is None or not pode_autenticar(usuario.situacao):
        raise _nao_autenticado()
    identificador_hash = hash_identificador(str(usuario.id))
    desde = agora - timedelta(minutes=settings.login_janela_min)
    falhas = falhas_de_login(session, desde, ip, identificador_hash, "TROCA_SENHA")
    if tentativas_esgotadas(falhas, settings.login_max_tentativas):
        raise _muitas_tentativas()

    atual = dados.senha_atual.get_secret_value()
    nova = dados.senha_nova.get_secret_value()
    if not conferir_senha(usuario.senha_hash, atual):
        registrar_tentativa(session, "TROCA_SENHA", agora, ip, False, identificador_hash)
        session.commit()
        raise RequestValidationError(
            [
                {
                    "loc": ("body", "senha_atual"),
                    "msg": "Senha atual incorreta.",
                    "type": "value_error",
                }
            ]
        )
    try:
        verificar_troca_de_senha(atual, nova)
    except EntradaInvalida as erro:
        # Mesmo formato da senha atual errada: o frontend lê o campo em `errors[].loc`.
        raise RequestValidationError(
            [{"loc": ("body", "senha_nova"), "msg": str(erro), "type": "value_error"}]
        ) from erro

    token = request.cookies.get(COOKIE_ACCESS)
    lido = ler_access_token(token or "", agora, settings.jwt_secret_key.get_secret_value())
    if lido is None:
        raise _nao_autenticado()
    usuario.senha_hash = hash_senha(nova)
    usuario.senha_temporaria = False
    registrar_tentativa(session, "TROCA_SENHA", agora, ip, True, identificador_hash)
    revogar_sessoes(
        session,
        agora,
        SessaoRefresh.usuario_id == usuario.id,
        SessaoRefresh.familia_id != lido[1],
    )
    session.add(
        Auditoria(
            ator_usuario_id=usuario.id,
            acao="TROCAR_SENHA",
            entidade="usuario",
            entidade_id=usuario.id,
            ip=ip,
        )
    )
    session.commit()
    logger.info("troca de senha: usuario=%s", usuario.id)
    return Response(status_code=204)


@router.post("/auth/refresh", responses=erros(NAO_AUTENTICADO, CSRF))
def renovar(
    request: Request,
    response: Response,
    session: SessionDep,
    relogio: RelogioDep,
    _cookie: Annotated[str | None, Security(esquema_refresh)] = None,
) -> SessaoSaida:
    """Rotação: o token usado é revogado e outro da mesma família é emitido. Reuso de um token
    já revogado indica roubo e revoga a família inteira, exceto dentro da tolerância
    (REFRESH_TOLERANCIA_S): aí é outra aba renovando junto e ganha um token da mesma família.
    Só uma reapresentação por token cabe na tolerância; a segunda revoga a família."""
    token = request.cookies.get(COOKIE_REFRESH)
    if not token:
        raise _nao_autenticado()
    agora = relogio.agora()
    atual = session.scalar(
        select(SessaoRefresh).where(SessaoRefresh.token_hash == sha256(token)).with_for_update()
    )
    if atual is None:
        raise _nao_autenticado()
    tolerancia = timedelta(seconds=get_settings().refresh_tolerancia_s)
    na_tolerancia = (
        atual.revogado_em is not None
        and refresh_na_tolerancia(
            atual.revogado_em,
            atual.substituido_por_id is not None,
            atual.reapresentado_em is not None,
            agora,
            tolerancia,
        )
        and familia_ativa(session, atual.familia_id)
    )
    if atual.revogado_em is not None and not na_tolerancia:
        revogar_sessoes(session, agora, SessaoRefresh.familia_id == atual.familia_id)
        session.commit()
        logger.warning(
            "refresh reutilizado: familia=%s usuario=%s", atual.familia_id, atual.usuario_id
        )
        raise _nao_autenticado()
    usuario = session.get(Usuario, atual.usuario_id)
    if atual.expira_em <= agora or usuario is None or not pode_autenticar(usuario.situacao):
        raise _nao_autenticado()

    corpo, nova = _iniciar_sessao(
        session, response, usuario, agora, ip_do_cliente(request), atual.familia_id
    )
    if na_tolerancia:
        atual.reapresentado_em = agora
        # Visível no log para acompanhar abuso da tolerância (achado da revisão de segurança).
        logger.info("refresh na tolerância: familia=%s usuario=%s", atual.familia_id, usuario.id)
    else:
        atual.revogado_em = agora
        atual.substituido_por_id = nova.id
    session.commit()
    return corpo


@router.post("/auth/logout", status_code=204, responses=erros(CSRF))
def logout(
    request: Request,
    session: SessionDep,
    relogio: RelogioDep,
    _cookie: Annotated[str | None, Security(esquema_refresh)] = None,
) -> Response:
    """Revoga a família do refresh token e apaga os cookies. Idempotente: 204 mesmo sem sessão."""
    token = request.cookies.get(COOKIE_REFRESH)
    if token:
        familia_id = session.scalar(
            select(SessaoRefresh.familia_id).where(SessaoRefresh.token_hash == sha256(token))
        )
        if familia_id is not None:
            revogar_sessoes(session, relogio.agora(), SessaoRefresh.familia_id == familia_id)
            session.commit()
    response = Response(status_code=204)
    _apagar_cookies(response)
    return response


def _eu(usuario: Usuario, nome: str | None, filas: list[UUID] | None) -> EuSaida:
    extra = {"trocar_senha": True} if usuario.senha_temporaria else {}
    return EuSaida(id=usuario.id, papel=usuario.papel, nome=nome, filas=filas, **extra)


@router.get("/me", response_model_exclude_unset=True, responses=erros(NAO_AUTENTICADO))
def eu(
    usuario: Annotated[Usuario, Depends(usuario_da_sessao_sem_troca)], session: SessionDep
) -> EuSaida:
    """Dados do usuário logado. A equipe recebe também as filas do seu escopo (ADR-025)."""
    if usuario.papel == "PACIENTE":
        nome = session.scalar(select(Paciente.nome).where(Paciente.usuario_id == usuario.id))
        return _eu(usuario, nome, None)
    # A equipe não tem nome no modelo de dados (só e-mail): `nome` fica `null`.
    filas = sorted(carregar_escopo(session, usuario.id))
    return _eu(usuario, None, filas)
