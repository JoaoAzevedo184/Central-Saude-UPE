"""Elegibilidade do paciente para a fila: sexo e faixa etária (ADR-027)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DadosPaciente:
    sexo: str | None
    data_nascimento: date | None


@dataclass(frozen=True)
class RestricoesFila:
    sexo_elegivel: str | None = None
    idade_minima: int | None = None
    idade_maxima: int | None = None


def idade_em_anos(data_nascimento: date, hoje: date) -> int:
    """Anos completos. Quem nasceu em 29/02 completa o ano em 01/03 nos anos não bissextos."""
    ainda_nao_fez = (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day)
    return hoje.year - data_nascimento.year - ainda_nao_fez


# Motivos para o paciente: textos fixos, sem dados de outros pacientes.
MOTIVO_SEXO = "Esta fila não atende o sexo informado no seu cadastro."
MOTIVO_DADO_AUSENTE = "Seu cadastro não tem os dados que esta fila exige."
MOTIVO_IDADE = "Esta fila atende outra faixa de idade."


def motivo_inelegivel(paciente: DadosPaciente, fila: RestricoesFila, hoje: date) -> str | None:
    """Por que o paciente não pode entrar na fila; `None` se pode. Limites de idade inclusivos.

    `hoje` é a data em America/Recife, vinda do `Relogio` (ADR-008). Dado ausente que a fila
    restringe torna o paciente inelegível (falha fechada).
    """
    if fila.sexo_elegivel is not None:
        if paciente.sexo is None:
            return MOTIVO_DADO_AUSENTE
        if paciente.sexo != fila.sexo_elegivel:
            return MOTIVO_SEXO
    if fila.idade_minima is None and fila.idade_maxima is None:
        return None
    if paciente.data_nascimento is None:
        return MOTIVO_DADO_AUSENTE
    idade = idade_em_anos(paciente.data_nascimento, hoje)
    if idade < 0:  # nascimento no futuro: dado inválido, falha fechada
        return MOTIVO_DADO_AUSENTE
    if fila.idade_minima is not None and idade < fila.idade_minima:
        return MOTIVO_IDADE
    if fila.idade_maxima is not None and idade > fila.idade_maxima:
        return MOTIVO_IDADE
    return None


def verificar_elegibilidade(paciente: DadosPaciente, fila: RestricoesFila, hoje: date) -> bool:
    """O paciente pode entrar na fila? A regra está em `motivo_inelegivel`."""
    return motivo_inelegivel(paciente, fila, hoje) is None
