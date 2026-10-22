"""Enums do contrato: nascem das constantes do domínio (`dominio.vocabulario`), sem copiar a lista.

Cada um vira um schema nomeado no OpenAPI (`#/components/schemas/Papel` etc.), que o gerador de
tipos do frontend reaproveita. Os valores de entrada e de saída são as mesmas strings do banco.
"""

from enum import StrEnum

from app.dominio.notificacoes.avisos import TIPOS_AVISO
from app.dominio.vocabulario import (
    MOTIVOS_CANCELAMENTO,
    ORIGENS_CRITERIO,
    PAPEIS,
    RISCOS,
    SITUACOES_VAGA,
    STATUS_AGENDAMENTO,
    STATUS_SOLICITACAO,
    TIPOS_CRITERIO,
    TIPOS_HISTORICO,
    TURNOS,
)


def _enum(nome: str, valores) -> type[StrEnum]:
    return StrEnum(nome, {v: v for v in valores})


Papel = _enum("Papel", PAPEIS)
StatusSolicitacao = _enum("StatusSolicitacao", STATUS_SOLICITACAO)
StatusAgendamento = _enum("StatusAgendamento", STATUS_AGENDAMENTO)
ClassificacaoRisco = _enum("ClassificacaoRisco", RISCOS)
Turno = _enum("Turno", TURNOS)
MotivoCancelamento = _enum("MotivoCancelamento", MOTIVOS_CANCELAMENTO)
TipoEventoLinhaDoTempo = _enum("TipoEventoLinhaDoTempo", TIPOS_HISTORICO)
TipoAviso = _enum("TipoAviso", TIPOS_AVISO)
SituacaoVaga = _enum("SituacaoVaga", SITUACOES_VAGA)
TipoCriterio = _enum("TipoCriterio", TIPOS_CRITERIO)
OrigemCriterio = _enum("OrigemCriterio", ORIGENS_CRITERIO)
