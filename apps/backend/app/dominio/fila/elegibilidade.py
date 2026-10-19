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


def verificar_elegibilidade(paciente: DadosPaciente, fila: RestricoesFila, hoje: date) -> bool:
    """O paciente pode entrar na fila? Limites de idade inclusivos.

    `hoje` é a data em America/Recife, vinda do `Relogio` (ADR-008). Dado ausente que a fila
    restringe torna o paciente inelegível (falha fechada).
    """
    if fila.sexo_elegivel is not None and paciente.sexo != fila.sexo_elegivel:
        return False
    if fila.idade_minima is None and fila.idade_maxima is None:
        return True
    if paciente.data_nascimento is None:
        return False
    idade = idade_em_anos(paciente.data_nascimento, hoje)
    if idade < 0:  # nascimento no futuro: dado inválido, falha fechada
        return False
    if fila.idade_minima is not None and idade < fila.idade_minima:
        return False
    return fila.idade_maxima is None or idade <= fila.idade_maxima
