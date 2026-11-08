"""Comandos de administração pelo terminal do servidor.

    python -m app.infra.admin redefinir-senha --email <email>   # equipe
    python -m app.infra.admin redefinir-senha --cpf <cpf>       # paciente

Caminho de recuperação, por isso roda em qualquer APP_ENV (inclusive produção): quem tem
acesso ao servidor já tem acesso ao banco. Serve para ADMIN, cuja senha o admin da API não
redefine, e para paciente, que não tem tela de recuperação. A senha temporária é impressa uma
vez e nunca vai para log nem auditoria.
"""

import argparse
import logging
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.acesso import PAPEIS_EQUIPE, normalizar_identificador
from app.dominio.cadastro import cpf_valido
from app.dominio.relogio import Relogio
from app.infra.autenticacao import aplicar_senha_temporaria
from app.infra.db import SessionLocal
from app.infra.modelos import Auditoria, Paciente, Usuario
from app.infra.relogio import RelogioReal
from app.logging import configurar_logging

logger = logging.getLogger(__name__)


class ContaNaoEncontrada(Exception):
    pass


def _redefinir(session: Session, usuario: Usuario | None, relogio: Relogio) -> str:
    if usuario is None:
        raise ContaNaoEncontrada
    senha = aplicar_senha_temporaria(session, usuario, relogio.agora())
    session.add(
        Auditoria(
            ator_usuario_id=None,
            acao="REDEFINIR_SENHA",
            entidade="usuario",
            entidade_id=usuario.id,
            dados_depois={"origem": "terminal"},
        )
    )
    session.commit()
    logger.info("senha redefinida pelo terminal: id=%s", usuario.id)
    return senha


def redefinir_senha(session: Session, email: str, relogio: Relogio) -> str:
    """Nova senha temporária da conta da equipe com este e-mail. Faz commit.

    A auditoria não tem ator (nulo = sistema) e marca a origem no `dados_depois`.
    """
    usuario = session.scalar(
        select(Usuario)
        .where(Usuario.email == email.strip().lower(), Usuario.papel.in_(PAPEIS_EQUIPE))
        .with_for_update()
    )
    return _redefinir(session, usuario, relogio)


def redefinir_senha_paciente(session: Session, cpf: str, relogio: Relogio) -> str:
    """Nova senha temporária do paciente com este CPF (com ou sem pontuação). Faz commit.

    CPF inválido, inexistente ou de conta da equipe dão o mesmo erro: não revela se a conta existe.
    """
    tipo, digitos = normalizar_identificador(cpf)
    usuario = None
    if tipo == "CPF" and cpf_valido(digitos):
        usuario = session.scalar(
            select(Usuario)
            .join(Paciente, Paciente.usuario_id == Usuario.id)
            .where(Paciente.cpf == digitos, Usuario.papel == "PACIENTE")
            .with_for_update(of=Usuario)
        )
    return _redefinir(session, usuario, relogio)


def main(argv: list[str] | None = None) -> int:
    configurar_logging(get_settings().log_level)
    parser = argparse.ArgumentParser(prog="python -m app.infra.admin")
    comandos = parser.add_subparsers(dest="comando", required=True)
    redefinir = comandos.add_parser("redefinir-senha", help="gera uma senha temporária")
    alvo = redefinir.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--email", help="conta da equipe")
    alvo.add_argument("--cpf", help="conta de paciente")
    args = parser.parse_args(argv)

    with SessionLocal() as session:
        try:
            if args.cpf is not None:
                senha = redefinir_senha_paciente(session, args.cpf, RelogioReal())
            else:
                senha = redefinir_senha(session, args.email, RelogioReal())
        except ContaNaoEncontrada:
            if args.cpf is not None:
                print("conta de paciente não encontrada para esse CPF", file=sys.stderr)
            else:
                print("conta da equipe não encontrada para esse e-mail", file=sys.stderr)
            return 1
    # print, não logger: a senha não vai para logs coletados.
    print(f"senha temporária (mostrada uma vez; a troca é obrigatória no primeiro acesso): {senha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
