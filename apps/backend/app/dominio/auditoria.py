"""Consulta da auditoria (RF-023, RN-010): o que da trilha pode sair na resposta.

`dados_antes`/`dados_depois` nunca saem crus. Cada ação tem uma lista permitida de chaves e,
à parte, as chaves ocultas (`nota`, `respostas`): aparecem só como "mudou", sem valor.
Chave fora das duas listas, ação desconhecida ou valor fora do formato ligam `omitidos`.
O `ip` não está em nenhuma lista: nunca sai.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.dominio.erros import EntradaInvalida
from app.dominio.vocabulario import (
    FINALIDADES_CONSENTIMENTO,
    MOTIVOS_CANCELAMENTO,
    MOTIVOS_CANCELAMENTO_AGENDAMENTO,
    PAPEIS,
    RISCOS,
    SITUACOES_USUARIO,
    STATUS_AGENDAMENTO,
    STATUS_SOLICITACAO,
)

Valor = str | int | bool | list[str]

ENTIDADES: tuple[str, ...] = (
    "solicitacao",
    "agendamento",
    "usuario",
    "paciente",
    "fila",
    "unidade",
)
ORDENACOES = ("prioridade", "chegada")
ORIGENS = ("terminal",)
MAX_LISTA = 500
MAX_INTEIRO = 10_000
# Datas aceitas nos filtros (`de`/`ate`): fora disso o cálculo do instante estoura.
DATA_MINIMA, DATA_MAXIMA = date(2000, 1, 1), date(2100, 12, 31)

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?)?")
# `versao_termo` só chega aqui depois de conferida contra a versão vigente (config).
_VERSAO_TERMO = re.compile(r"[A-Za-z0-9._-]{1,20}")

Validador = Callable[[Any], bool]


def _em(vocabulario: Any) -> Validador:
    return lambda v: isinstance(v, str) and v in vocabulario


def _uuid(v: Any) -> bool:
    return isinstance(v, str) and _UUID.fullmatch(v) is not None


def _iso(v: Any) -> bool:
    if not isinstance(v, str) or _ISO.fullmatch(v) is None:
        return False
    try:
        datetime.fromisoformat(v)
    except ValueError:
        return False
    return True


def _inteiro(v: Any) -> bool:
    return type(v) is int and 0 <= v <= MAX_INTEIRO


def _booleano(v: Any) -> bool:
    return type(v) is bool


def _versao(v: Any) -> bool:
    return isinstance(v, str) and _VERSAO_TERMO.fullmatch(v) is not None


def _lista(item: Validador) -> Validador:
    return lambda v: isinstance(v, list) and len(v) <= MAX_LISTA and all(item(x) for x in v)


_STATUS = (*STATUS_SOLICITACAO, *STATUS_AGENDAMENTO)
_MOTIVOS = (*MOTIVOS_CANCELAMENTO, *MOTIVOS_CANCELAMENTO_AGENDAMENTO)

# Um validador por campo. Campo sem validador aqui é reprovado. `None` sempre passa
# (campo sem valor); tipo errado nunca passa (`True` não é inteiro, `1` não é booleano).
VALIDADORES: dict[str, Validador] = {
    "status": _em(_STATUS),
    "classificacao_risco": _em(RISCOS),
    "motivo_cancelamento": _em(_MOTIVOS),
    "papel": _em(PAPEIS),
    "situacao": _em(SITUACOES_USUARIO),
    "consentimentos": _lista(_em(FINALIDADES_CONSENTIMENTO)),
    "ordenacao": _em(ORDENACOES),
    "origem": _em(ORIGENS),
    "entidade": _em(ENTIDADES),
    "acao": lambda v: isinstance(v, str) and v in PERMITIDAS,
    "solicitacao_id": _uuid,
    "vaga_id": _uuid,
    "unidade_id": _uuid,
    "fila_id": _uuid,
    "entidade_id": _uuid,
    "ator_usuario_id": _uuid,
    "filas": _lista(_uuid),
    "unidades": _lista(_uuid),
    "data_entrada_fila": _iso,
    "respondido_em": _iso,
    "confirmado_em": _iso,
    "expira_em": _iso,
    "data": _iso,
    "de": _iso,
    "ate": _iso,
    "visao_central": _booleano,
    "limit": _inteiro,
    "offset": _inteiro,
    "versao_termo": _versao,
}


def verificar_data_da_consulta(dia: date) -> None:
    """Filtros `de`/`ate`: dentro de `DATA_MINIMA`..`DATA_MAXIMA`."""
    if not DATA_MINIMA <= dia <= DATA_MAXIMA:
        raise EntradaInvalida(f"Informe uma data entre {DATA_MINIMA} e {DATA_MAXIMA}.")


def inicio_do_dia(dia: date, fuso: ZoneInfo) -> datetime:
    """Instante UTC em que o dia começa no fuso local."""
    return datetime.combine(dia, time.min, tzinfo=fuso).astimezone(UTC)


def fim_do_dia(dia: date, fuso: ZoneInfo) -> datetime:
    """Instante UTC em que o dia seguinte começa (limite superior exclusivo)."""
    return inicio_do_dia(dia + timedelta(days=1), fuso)


@dataclass(frozen=True)
class CampoAuditoria:
    campo: str
    antes: Valor | None
    depois: Valor | None
    oculto: bool = False


_TRANSICAO = ("status", "classificacao_risco", "data_entrada_fila")
_AGENDAMENTO = ("respondido_em", "confirmado_em", "motivo_cancelamento")
_NOTA = ("nota",)
_TRANSICAO_COM_NOTA = _TRANSICAO + _AGENDAMENTO


# Uma ação pode gravar linha de solicitação e de agendamento: a lista é a união das duas.
PERMITIDAS: dict[str, tuple[str, ...]] = {
    "CRIAR_SOLICITACAO": _TRANSICAO,
    "CLASSIFICAR": _TRANSICAO,
    "RECLASSIFICAR": _TRANSICAO,
    "RESPONDER_CRITERIOS": _TRANSICAO,
    "CANCELAR_SOLICITACAO": _TRANSICAO_COM_NOTA,
    "CANCELAR_AGENDAMENTO": _TRANSICAO_COM_NOTA,
    "CONFIRMAR_AGENDAMENTO": _TRANSICAO_COM_NOTA,
    "RECUSAR_PROPOSTA": _TRANSICAO_COM_NOTA,
    "EXPIRAR_PROPOSTA": _TRANSICAO_COM_NOTA,
    "REGISTRAR_COMPARECIMENTO": _TRANSICAO_COM_NOTA,
    "REGISTRAR_FALTA": _TRANSICAO_COM_NOTA,
    "PROPOR_VAGA": (*_TRANSICAO_COM_NOTA, "solicitacao_id", "vaga_id", "expira_em"),
    "CRIAR_USUARIO": ("papel", "unidades"),
    "REDEFINIR_SENHA": ("origem",),
    "ATRIBUIR_FILAS": ("filas",),
    "ATRIBUIR_UNIDADES": ("unidades", "visao_central"),
    "SUSPENDER": ("situacao",),
    "REATIVAR": ("situacao",),
    "LOGIN": (),
    "TROCAR_SENHA": (),
    "REGISTRO": ("consentimentos", "versao_termo"),
    "CONSULTAR_PAINEL": ("status", "ordenacao", "limit", "offset"),
    "CONSULTAR_SOLICITACAO": (),
    "CONSULTAR_AGENDAMENTOS": ("data",),
    "CONSULTAR_VAGAS": ("de", "ate"),
    "CONSULTAR_INDICADORES": ("de", "ate", "unidade_id", "fila_id"),
    "CONSULTAR_AUDITORIA": ("entidade", "entidade_id", "acao", "ator_usuario_id", "de", "ate"),
}

# `nota` muda em quase toda transição da solicitação; `respostas` só em RESPONDER_CRITERIOS.
# Mostram que mudaram, nunca o valor.
OCULTOS: dict[str, tuple[str, ...]] = {
    acao: _NOTA if chaves[:3] == _TRANSICAO else () for acao, chaves in PERMITIDAS.items()
}
OCULTOS["RESPONDER_CRITERIOS"] = ("respostas", "nota")


def _reprovado(_: Any) -> bool:
    return False


def montar_campos(
    acao: str, antes: dict[str, Any] | None, depois: dict[str, Any] | None
) -> tuple[list[CampoAuditoria], bool]:
    """Campos da resposta, na ordem da lista permitida da ação, e se algo foi omitido.

    Pura: sem banco, sem relógio. Ação desconhecida devolve lista vazia e `True`.
    """
    antes, depois = antes or {}, depois or {}
    chaves = antes.keys() | depois.keys()
    if acao not in PERMITIDAS:
        return [], True
    permitidas, ocultos = PERMITIDAS[acao], OCULTOS[acao]
    omitidos = bool(chaves - set(permitidas) - set(ocultos))
    campos: list[CampoAuditoria] = []
    for campo in permitidas:
        if campo not in chaves:
            continue
        a, d = antes.get(campo), depois.get(campo)
        valido = VALIDADORES.get(campo, _reprovado)
        if not all(v is None or valido(v) for v in (a, d)):
            omitidos = True
            continue
        campos.append(CampoAuditoria(campo, a, d))
    campos.extend(CampoAuditoria(c, None, None, True) for c in ocultos if c in chaves)
    return campos, omitidos
