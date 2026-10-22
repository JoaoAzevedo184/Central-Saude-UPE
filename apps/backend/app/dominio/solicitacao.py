"""Solicitação e sua linha do tempo (ADR-026, ADR-007)."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.dominio.erros import EntradaInvalida, TransicaoInvalida
from app.dominio.vocabulario import MOTIVOS_CANCELAMENTO, RISCOS


@dataclass(frozen=True)
class Solicitacao:
    id: UUID
    status: str
    classificacao_risco: str | None
    nota: int
    data_entrada_fila: datetime | None


@dataclass(frozen=True)
class EventoHistorico:
    """Linha de `historico_solicitacao`. Nunca carrega posição nem tamanho da fila."""

    tipo: str
    status_anterior: str | None
    status_novo: str | None
    motivo: str | None
    visivel_paciente: bool
    ocorrido_em: datetime


# Motivo da volta para a fila → (status de origem exigido, texto para o paciente).
# Texto fixo: o paciente recebe o motivo, nunca a posição (ADR-007, ADR-026).
MOTIVOS_REENTRADA = {
    "PROPOSTA_EXPIRADA": (
        "EM_PROPOSTA",
        "Você não confirmou a vaga no prazo. Sua solicitação voltou para a fila.",
    ),
    "FALTOU": (
        "AGENDADA",
        "Você não compareceu à consulta. Sua solicitação voltou para a fila.",
    ),
    "RECUSOU_MAIS_DE_UMA_DATA": (
        "EM_PROPOSTA",
        "Você recusou outras datas. Sua solicitação voltou para a fila.",
    ),
}


def reentrar_no_fim_da_fila(
    solicitacao: Solicitacao, agora: datetime, motivo: str
) -> tuple[Solicitacao, EventoHistorico]:
    """Devolve a solicitação ao fim da fila (ADR-026): `data_entrada_fila = agora`.

    `motivo` é uma chave de `MOTIVOS_REENTRADA`. Estado de origem diferente do exigido
    pelo motivo levanta `TransicaoInvalida`.
    """
    if motivo not in MOTIVOS_REENTRADA:
        raise ValueError(f"motivo de reentrada desconhecido: {motivo!r}")
    origem, texto = MOTIVOS_REENTRADA[motivo]
    if solicitacao.status != origem:
        raise TransicaoInvalida("A solicitação não está em um estado que permita voltar à fila.")

    nova = replace(solicitacao, status="NA_FILA", data_entrada_fila=agora)
    evento = EventoHistorico(
        tipo="REENTROU_NA_FILA",
        status_anterior=solicitacao.status,
        status_novo="NA_FILA",
        motivo=texto,
        visivel_paciente=True,
        ocorrido_em=agora,
    )
    return nova, evento


TEXTO_CRIADA = "Recebemos seu pedido. Ele está em análise."
TEXTO_ENTROU_NA_FILA = "Seu pedido entrou na fila."
TEXTO_NOTA_RECALCULADA = "nota recalculada"
TEXTO_PROPOSTA_ENVIADA = "Uma vaga foi reservada para você. Confirme dentro do prazo."
TEXTO_CONFIRMADA = "Você confirmou a consulta."
TEXTO_RECUSADA = "Você pediu outra data. A vaga foi liberada."
TEXTO_PROPOSTA_EXPIRADA = "O prazo para confirmar a vaga acabou."
TEXTO_ATENDIDA = "Consulta realizada."
TEXTO_FALTOU = "A equipe registrou sua falta à consulta."
# Estados em que a equipe ainda responde critérios (a nota só pesa antes da proposta).
STATUS_COM_RESPOSTAS_DA_EQUIPE = frozenset({"EM_ANALISE", "NA_FILA"})
# Em EM_PROPOSTA e AGENDADA, quem chama cancela o agendamento ativo na mesma transação
# (`estados.cancelar_pelo_paciente`, que confere o início da vaga).
STATUS_CANCELAVEIS = frozenset({"EM_ANALISE", "NA_FILA", "EM_PROPOSTA", "AGENDADA"})


def evento_criada(agora: datetime) -> EventoHistorico:
    """Primeiro evento da linha do tempo (UC-002)."""
    return EventoHistorico("CRIADA", None, "EM_ANALISE", TEXTO_CRIADA, True, agora)


def classificar(
    solicitacao: Solicitacao, risco: str, motivo: str | None, agora: datetime
) -> tuple[Solicitacao, list[EventoHistorico]]:
    """Classificação de risco pela equipe, simulando a regulação.

    - EM_ANALISE: entra na fila (`data_entrada_fila = agora`), com os eventos CLASSIFICADA
      (só equipe) e ENTROU_NA_FILA (texto neutro para o paciente).
    - NA_FILA: só reclassifica, com motivo obrigatório; evento RECLASSIFICADA (só equipe).
    - Outros estados: `TransicaoInvalida`.
    """
    if risco not in RISCOS:
        raise ValueError(f"classificação de risco desconhecida: {risco!r}")
    if solicitacao.status == "EM_ANALISE":
        nova = replace(
            solicitacao, status="NA_FILA", classificacao_risco=risco, data_entrada_fila=agora
        )
        return nova, [
            EventoHistorico("CLASSIFICADA", "EM_ANALISE", "NA_FILA", motivo, False, agora),
            EventoHistorico("ENTROU_NA_FILA", None, None, TEXTO_ENTROU_NA_FILA, True, agora),
        ]
    if solicitacao.status == "NA_FILA":
        if not motivo:
            raise EntradaInvalida("Informe o motivo da reclassificação.")
        nova = replace(solicitacao, classificacao_risco=risco)
        return nova, [EventoHistorico("RECLASSIFICADA", "NA_FILA", "NA_FILA", motivo, False, agora)]
    raise TransicaoInvalida("A solicitação não está em um estado que permita classificar.")


def exigir_aceita_respostas(solicitacao: Solicitacao) -> None:
    """A equipe só responde critérios antes da proposta; depois, `TransicaoInvalida`."""
    if solicitacao.status not in STATUS_COM_RESPOSTAS_DA_EQUIPE:
        raise TransicaoInvalida("A solicitação não aceita mais respostas aos critérios.")


def recalcular_nota(
    solicitacao: Solicitacao, nota: int, agora: datetime
) -> tuple[Solicitacao, EventoHistorico | None]:
    """Nova nota depois de a equipe responder critérios (ADR-024).

    Na fila, nota diferente muda a posição: evento RECLASSIFICADA (só equipe).
    """
    exigir_aceita_respostas(solicitacao)
    nova = replace(solicitacao, nota=nota)
    if solicitacao.status != "NA_FILA" or nota == solicitacao.nota:
        return nova, None
    return nova, EventoHistorico(
        "RECLASSIFICADA", "NA_FILA", "NA_FILA", TEXTO_NOTA_RECALCULADA, False, agora
    )


def cancelar(
    solicitacao: Solicitacao,
    motivo_codigo: str,
    agora: datetime,
    *,
    tem_agendamento_ativo: bool = False,
) -> tuple[Solicitacao, EventoHistorico]:
    """Cancelamento pelo paciente ("não vou precisar"), em `STATUS_CANCELAVEIS`.

    Em EM_PROPOSTA e AGENDADA exige o agendamento ativo, que quem chama cancela junto;
    sem ele o estado está inconsistente e a transição é recusada.

    `motivo_codigo` é uma chave de `MOTIVOS_CANCELAMENTO`; o evento leva o rótulo.
    """
    if solicitacao.status not in STATUS_CANCELAVEIS:
        raise TransicaoInvalida("A solicitação não pode ser cancelada neste estado.")
    if solicitacao.status in ("EM_PROPOSTA", "AGENDADA") and not tem_agendamento_ativo:
        raise TransicaoInvalida("A solicitação não pode ser cancelada neste estado.")
    if motivo_codigo not in MOTIVOS_CANCELAMENTO:
        raise EntradaInvalida("Motivo de cancelamento desconhecido.")
    nova = replace(solicitacao, status="CANCELADA")
    rotulo = MOTIVOS_CANCELAMENTO[motivo_codigo]
    evento = EventoHistorico("CANCELADA", solicitacao.status, "CANCELADA", rotulo, True, agora)
    return nova, evento


# --- ciclo da proposta (UC-003, UC-004, UC-005, UC-006) -----------------------------------


def _exigir(solicitacao: Solicitacao, status: str) -> None:
    if solicitacao.status != status:
        raise TransicaoInvalida("A solicitação não está em um estado que permita esta ação.")


def receber_proposta(
    solicitacao: Solicitacao, agora: datetime
) -> tuple[Solicitacao, EventoHistorico]:
    """NA_FILA → EM_PROPOSTA (UC-003). Quem escolhe a solicitação é `propor_vaga()`."""
    _exigir(solicitacao, "NA_FILA")
    evento = EventoHistorico(
        "PROPOSTA_ENVIADA", "NA_FILA", "EM_PROPOSTA", TEXTO_PROPOSTA_ENVIADA, True, agora
    )
    return replace(solicitacao, status="EM_PROPOSTA"), evento


def confirmar_proposta(
    solicitacao: Solicitacao, agora: datetime
) -> tuple[Solicitacao, EventoHistorico]:
    """EM_PROPOSTA → AGENDADA (UC-004)."""
    _exigir(solicitacao, "EM_PROPOSTA")
    evento = EventoHistorico("CONFIRMADA", "EM_PROPOSTA", "AGENDADA", TEXTO_CONFIRMADA, True, agora)
    return replace(solicitacao, status="AGENDADA"), evento


def recusar_proposta(
    solicitacao: Solicitacao,
    recusas_anteriores: int,
    recusas_mantendo_posicao: int,
    agora: datetime,
) -> tuple[Solicitacao, list[EventoHistorico]]:
    """ "Esta data não serve" (UC-005, regra proposta): EM_PROPOSTA → NA_FILA.

    `recusas_anteriores` conta só as recusas desde a última entrada na fila. As primeiras
    `recusas_mantendo_posicao` mantêm `data_entrada_fila`; a seguinte manda a solicitação
    para o fim da fila (`reentrar_no_fim_da_fila`), e a contagem recomeça.
    """
    _exigir(solicitacao, "EM_PROPOSTA")
    recusada = EventoHistorico("RECUSADA", "EM_PROPOSTA", "NA_FILA", TEXTO_RECUSADA, True, agora)
    if recusas_anteriores < recusas_mantendo_posicao:
        return replace(solicitacao, status="NA_FILA"), [recusada]
    nova, reentrada = reentrar_no_fim_da_fila(solicitacao, agora, "RECUSOU_MAIS_DE_UMA_DATA")
    return nova, [recusada, reentrada]


def expirar_proposta(
    solicitacao: Solicitacao, agora: datetime
) -> tuple[Solicitacao, list[EventoHistorico]]:
    """Proposta não confirmada no prazo: volta para o fim da fila (UC-006, ADR-026)."""
    _exigir(solicitacao, "EM_PROPOSTA")
    expirada = EventoHistorico(
        "PROPOSTA_EXPIRADA", "EM_PROPOSTA", "NA_FILA", TEXTO_PROPOSTA_EXPIRADA, True, agora
    )
    nova, reentrada = reentrar_no_fim_da_fila(solicitacao, agora, "PROPOSTA_EXPIRADA")
    return nova, [expirada, reentrada]


# --- presença (UC-008) --------------------------------------------------------------------


def registrar_atendimento(
    solicitacao: Solicitacao, agora: datetime
) -> tuple[Solicitacao, EventoHistorico]:
    """Compareceu: AGENDADA → ATENDIDA."""
    _exigir(solicitacao, "AGENDADA")
    evento = EventoHistorico("ATENDIDA", "AGENDADA", "ATENDIDA", TEXTO_ATENDIDA, True, agora)
    return replace(solicitacao, status="ATENDIDA"), evento


def registrar_falta(
    solicitacao: Solicitacao, agora: datetime
) -> tuple[Solicitacao, list[EventoHistorico]]:
    """Faltou: volta para o fim da fila (RN-014, ADR-026)."""
    _exigir(solicitacao, "AGENDADA")
    faltou = EventoHistorico("FALTOU", "AGENDADA", "NA_FILA", TEXTO_FALTOU, True, agora)
    nova, reentrada = reentrar_no_fim_da_fila(solicitacao, agora, "FALTOU")
    return nova, [faltou, reentrada]
