"""Vagas geradas a partir da agenda (ADR-008: horário local de Recife, gravado com fuso)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.dominio.agendamento.prazos import calcular_expira_em
from app.dominio.vocabulario import SITUACOES_VAGA

SituacaoVaga = Literal[*SITUACOES_VAGA]


@dataclass(frozen=True)
class GradeAgenda:
    dias_semana: list[int]  # ISO 8601: 1 = segunda ... 7 = domingo
    hora_inicio: time
    hora_fim: time
    duracao_min: int
    vigencia_inicio: date
    vigencia_fim: date | None


def horarios_da_agenda(
    grade: GradeAgenda, agora: datetime, horizonte_dias: int, fuso: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    """(início, fim) das vagas dos `horizonte_dias` dias a partir de hoje, dentro da vigência.

    Só vagas inteiras (que terminam até `hora_fim`) e que ainda não começaram.
    """
    hoje = agora.astimezone(fuso).date()
    primeiro = max(hoje, grade.vigencia_inicio)
    ultimo = hoje + timedelta(days=horizonte_dias - 1)
    if grade.vigencia_fim is not None:
        ultimo = min(ultimo, grade.vigencia_fim)
    duracao = timedelta(minutes=grade.duracao_min)
    horarios = []
    dia = primeiro
    while dia <= ultimo:
        if dia.isoweekday() in grade.dias_semana:
            inicio = datetime.combine(dia, grade.hora_inicio, fuso)
            limite = datetime.combine(dia, grade.hora_fim, fuso)
            while inicio + duracao <= limite:
                if inicio > agora:
                    horarios.append((inicio, inicio + duracao))
                inicio += duracao
        dia += timedelta(days=1)
    return horarios


def situacao_da_vaga(
    vaga_inicio: datetime,
    status_admin: str,
    status_agendamento_ativo: str | None,
    agora: datetime,
    prazo_confirmacao_horas: int,
    antecedencia_minima_horas: int,
    *,
    janela_minima_horas: int,
) -> SituacaoVaga:
    """Situação da vaga no painel da equipe, calculada na consulta e nunca gravada (ADR-004).

    Livre no futuro, mas sem janela para propor (`calcular_expira_em` é `None`, RN-016):
    `LIVRE_SEM_PROPOSTA`, candidata a encaixe manual (ADR-021). Vaga que já começou sem
    agendamento ativo: `ENCERRADA` (realizada, falta ou simplesmente não usada).
    """
    if status_agendamento_ativo == "PROPOSTO":
        return "PROPOSTA"
    if status_agendamento_ativo == "CONFIRMADO":
        return "CONFIRMADA"
    if status_admin == "BLOQUEADA":
        return "BLOQUEADA"
    if vaga_inicio <= agora:
        return "ENCERRADA"
    expira_em = calcular_expira_em(
        agora,
        vaga_inicio,
        prazo_confirmacao_horas,
        antecedencia_minima_horas,
        janela_minima_horas=janela_minima_horas,
    )
    return "LIVRE" if expira_em else "LIVRE_SEM_PROPOSTA"
