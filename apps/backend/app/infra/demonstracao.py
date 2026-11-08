"""Fila de demonstração para a apresentação ao vivo (dados SINTÉTICOS, sem migração).

`python -m app.infra.demonstracao preparar|desativar --confirmo-banco-de-demonstracao`

Cria (ou reativa) a fila "Consulta de demonstração" no CISAM, vazia e com uma agenda que gera
vagas, para o pedido feito ao vivo receber proposta na próxima rodada do Worker. Não toca nas
outras filas. Travas, sempre, também em development: `DEMO_SEED_PERMITIDO=true` e a flag
`--confirmo-banco-de-demonstracao`. Idempotente.
"""

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dominio.agendamento.prazos import calcular_expira_em
from app.dominio.relogio import Relogio
from app.infra.acesso import carregar_escopo
from app.infra.agendamentos import gerar_vagas_da_agenda, vaga_ocupada
from app.infra.db import SessionLocal
from app.infra.modelos import Agenda, Especialidade, Fila, Unidade, Usuario, Vaga, usuario_fila
from app.infra.relogio import RelogioReal
from app.logging import configurar_logging

logger = logging.getLogger(__name__)

UNIDADE = "CISAM"
ESPECIALIDADE = "Demonstração"
FILA = "Consulta de demonstração"
DESCRICAO = "Fila de demonstração do protótipo. Dados sintéticos."
PROFISSIONAL = "Profissional Demonstração (fictício)"
DIAS_UTEIS = [1, 2, 3, 4, 5]
HORA_INICIO, HORA_FIM, DURACAO_MIN = time(8), time(16), 60
ATENDENTE = "atendente.cisam@exemplo.com"
GESTOR = "gestor.cisam@exemplo.com"
LOCK = 7_300_184_002  # advisory lock; o do seed é 7_300_184_001


class DemonstracaoRecusada(Exception):
    """Trava do comando. A mensagem explica o que falta."""


@dataclass
class Resumo:
    fila_id: UUID
    vagas_livres: int
    primeira_proponivel: datetime | None


def _recusa(settings: Settings, confirmo: bool) -> str | None:
    if settings.app_env not in ("development", "production"):
        return (
            "demonstração recusada: só roda com APP_ENV=development ou production "
            f"(atual: {settings.app_env})"
        )
    if not settings.demo_seed_permitido:
        return (
            "demonstração recusada: defina DEMO_SEED_PERMITIDO=true no .env (e desligue depois) "
            "e passe --confirmo-banco-de-demonstracao. Só em banco de demonstração."
        )
    if not confirmo:
        return "demonstração recusada: falta a flag --confirmo-banco-de-demonstracao."
    return None


def _travar(session: Session, settings: Settings, confirmo: bool) -> None:
    if recusa := _recusa(settings, confirmo):
        raise DemonstracaoRecusada(recusa)
    session.execute(select(func.pg_advisory_xact_lock(LOCK)))


def _fila_e_agenda(session: Session, unidade_id: UUID) -> tuple[Fila | None, Agenda | None]:
    fila = session.scalar(select(Fila).where(Fila.unidade_id == unidade_id, Fila.nome == FILA))
    if fila is None:
        return None, None
    agenda = session.scalar(
        select(Agenda).where(Agenda.fila_id == fila.id, Agenda.profissional == PROFISSIONAL)
    )
    return fila, agenda


def _unidade(session: Session) -> Unidade:
    unidade = session.scalar(select(Unidade).where(Unidade.sigla == UNIDADE))
    if unidade is None:
        raise DemonstracaoRecusada(f"unidade {UNIDADE} não existe: rode o seed antes.")
    return unidade


def preparar(
    session: Session,
    settings: Settings,
    relogio: Relogio,
    escrever: Callable[[str], None],
    *,
    confirmo: bool,
) -> Resumo:
    """Cria ou reativa fila, agenda e acesso, e gera as vagas já. Não faz commit."""
    _travar(session, settings, confirmo)
    agora = relogio.agora()
    fuso = ZoneInfo(settings.timezone_exibicao)
    amanha = agora.astimezone(fuso).date() + timedelta(days=1)
    unidade = _unidade(session)

    especialidade = session.scalar(select(Especialidade).where(Especialidade.nome == ESPECIALIDADE))
    if especialidade is None:
        especialidade = Especialidade(nome=ESPECIALIDADE)
        session.add(especialidade)
        session.flush()

    fila, agenda = _fila_e_agenda(session, unidade.id)
    if fila is None:
        fila = Fila(
            unidade_id=unidade.id,
            especialidade_id=especialidade.id,
            nome=FILA,
            descricao_paciente=DESCRICAO,
        )
        session.add(fila)
        session.flush()
    fila.ativa = True
    if agenda is None:
        agenda = Agenda(
            fila_id=fila.id,
            profissional=PROFISSIONAL,
            dias_semana=DIAS_UTEIS,
            hora_inicio=HORA_INICIO,
            hora_fim=HORA_FIM,
            duracao_min=DURACAO_MIN,
            vigencia_inicio=amanha,
        )
        session.add(agenda)
    agenda.ativa = True
    agenda.vigencia_inicio = max(agenda.vigencia_inicio, amanha)
    session.flush()

    atendente = session.scalar(select(Usuario).where(Usuario.email == ATENDENTE))
    if atendente is not None:
        session.execute(
            insert(usuario_fila)
            .values(usuario_id=atendente.id, fila_id=fila.id)
            .on_conflict_do_nothing()
        )
    gestor = session.scalar(select(Usuario).where(Usuario.email == GESTOR))
    gestor_ve = gestor is not None and fila.id in carregar_escopo(session, gestor.id)

    gerar_vagas_da_agenda(session, agenda.id, agora, settings)
    inicios = list(
        session.scalars(
            select(Vaga.inicio)
            .where(
                Vaga.agenda_id == agenda.id,
                Vaga.status_admin == "ATIVA",
                Vaga.inicio > agora,
                ~vaga_ocupada(Vaga.id),
            )
            .order_by(Vaga.inicio)
        )
    )
    primeira = next(
        (
            i
            for i in inicios
            if calcular_expira_em(
                agora,
                i,
                fila.prazo_confirmacao_horas,
                settings.proposta_antecedencia_minima_horas,
                janela_minima_horas=settings.proposta_janela_minima_horas,
            )
        ),
        None,
    )
    horas = settings.proposta_antecedencia_minima_horas + settings.proposta_janela_minima_horas
    escrever(f"fila: {FILA} (unidade {UNIDADE}), id {fila.id}")
    if atendente is not None and gestor_ve:
        escrever("acesso: atendente.cisam e gestor.cisam enxergam a fila")
    else:
        escrever("ATENÇÃO: atendente.cisam ou gestor.cisam não existe (rode o seed --historico)")
    escrever(f"vagas livres: {len(inicios)}")
    if primeira is None:
        escrever("Nenhuma vaga pode receber proposta agora.")
    else:
        quando = primeira.astimezone(fuso).strftime("%d/%m/%Y %H:%M")
        escrever(
            f"Uma proposta feita agora oferece vaga a partir de {quando} "
            f"({horas} h de antecedência pelas regras atuais)"
        )
    return Resumo(fila.id, len(inicios), primeira)


def desativar(
    session: Session, settings: Settings, escrever: Callable[[str], None], *, confirmo: bool
) -> bool:
    """Desativa fila e agenda, sem apagar nada. Devolve False se a fila não existe."""
    _travar(session, settings, confirmo)
    fila, agenda = _fila_e_agenda(session, _unidade(session).id)
    if fila is None:
        escrever("fila de demonstração não existe; nada feito")
        return False
    fila.ativa = False
    if agenda is not None:
        agenda.ativa = False
    escrever("fila e agenda de demonstração desativadas; histórico mantido")
    return True


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    configurar_logging(settings.log_level)
    parser = argparse.ArgumentParser(prog="python -m app.infra.demonstracao", description=__doc__)
    parser.add_argument("acao", choices=["preparar", "desativar"])
    parser.add_argument("--confirmo-banco-de-demonstracao", dest="confirmo", action="store_true")
    args = parser.parse_args(argv)
    try:
        with SessionLocal() as session:
            if args.acao == "preparar":
                preparar(session, settings, RelogioReal(), print, confirmo=args.confirmo)
            else:
                desativar(session, settings, print, confirmo=args.confirmo)
            session.commit()
    except DemonstracaoRecusada as erro:
        sys.exit(str(erro))


if __name__ == "__main__":
    main()
