"""Erros de domínio. A API traduz para Problem Details (RFC 9457).

A mensagem vai para o cliente: nunca coloque dados pessoais nela.
"""


class ErroDeDominio(Exception):
    """Regra de negócio violada. Responde `status` (409, salvo nas subclasses)."""

    tipo = "/problemas/erro-de-dominio"
    status = 409
    extras: dict[str, str] = {}  # campos a mais no Problem Details


class TransicaoInvalida(ErroDeDominio):
    """Estado de origem não permite a transição pedida. Responde 409."""

    tipo = "/problemas/transicao-invalida"


class PropostaExpirada(TransicaoInvalida):
    """Confirmar ou recusar depois de `expira_em`, mesmo antes do Worker expirar (UC-004). 409."""

    tipo = "/problemas/proposta-expirada"


class ToleranciaNaoEncerrada(TransicaoInvalida):
    """Falta registrada antes de `início da vaga + tolerância` (RN-013). 409."""

    tipo = "/problemas/tolerancia-nao-encerrada"


class OperacaoNaoPermitida(ErroDeDominio):
    """A operação é válida em geral, mas não neste alvo (ex.: suspender a si mesmo). 409."""

    tipo = "/problemas/operacao-nao-permitida"


class VisaoCentralNaoConfirmada(ErroDeDominio):
    """Gestor sem unidade vê a central inteira (ADR-025): o admin precisa confirmar. 409."""

    tipo = "/problemas/visao-central-nao-confirmada"


class NaoElegivel(ErroDeDominio):
    """O paciente não cumpre a elegibilidade da fila (RN-017). 409."""

    tipo = "/problemas/nao-elegivel"


class SolicitacaoDuplicada(ErroDeDominio):
    """Já existe solicitação ativa do paciente na fila (RN-018). 409."""

    tipo = "/problemas/solicitacao-duplicada"

    def __init__(self, solicitacao_id: object) -> None:
        super().__init__("Você já tem uma solicitação ativa nesta fila.")
        # UC-002 E2: mostra a existente (se foi encerrada no meio-tempo, não há o que mostrar).
        self.extras = {"solicitacao_id": str(solicitacao_id)} if solicitacao_id else {}


class SemConsentimento(ErroDeDominio):
    """Sem consentimento AGENDAMENTO vigente, o paciente não solicita (RN-009). 403."""

    tipo = "/problemas/sem-consentimento"
    status = 403


class EntradaInvalida(ErroDeDominio):
    """Dado de entrada que só o domínio sabe recusar (ex.: critério de outra fila). 422."""

    tipo = "about:blank"
    status = 422
