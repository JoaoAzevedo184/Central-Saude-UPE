"""Indicadores do gestor: período, semanas e razões.

As contagens saem do banco (`infra/indicadores.py`); aqui ficam as regras que não dependem dele.
Divisão por zero não é 0 %: a taxa é `None` e a resposta traz numerador e denominador.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.dominio.erros import EntradaInvalida

MAX_DIAS_PERIODO = 366


def verificar_periodo(de: date, ate: date) -> None:
    """Dias inclusivos; de 1 a `MAX_DIAS_PERIODO`."""
    if ate < de or (ate - de).days >= MAX_DIAS_PERIODO:
        raise EntradaInvalida(f"Informe um período de 1 a {MAX_DIAS_PERIODO} dias.")


def limites_do_periodo(de: date, ate: date, fuso: ZoneInfo) -> tuple[datetime, datetime]:
    """Instantes [início, fim) que cobrem os dias `de` a `ate` no fuso local."""
    return (
        datetime.combine(de, time.min, tzinfo=fuso).astimezone(UTC),
        datetime.combine(ate + timedelta(days=1), time.min, tzinfo=fuso).astimezone(UTC),
    )


def semanas_do_periodo(de: date, ate: date) -> list[date]:
    """Segundas-feiras das semanas que tocam o período, em ordem; semana sem dado é preenchida."""
    segunda = de - timedelta(days=de.weekday())
    return [segunda + timedelta(weeks=n) for n in range((ate - segunda).days // 7 + 1)]


def razao(numerador: int, denominador: int) -> float | None:
    return round(numerador / denominador, 4) if denominador else None
