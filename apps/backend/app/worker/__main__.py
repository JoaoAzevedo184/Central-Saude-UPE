"""Ponto de entrada do Worker: `python -m app.worker` (ADR-005)."""

import logging
import signal
import time
from collections.abc import Callable

from app.config import Settings, get_settings
from app.logging import configurar_logging, resumo_do_erro
from app.worker import jobs

logger = logging.getLogger("app.worker")

Job = Callable[[], int]

# Passo máximo do sono do laço: limita o tempo de reação ao SIGTERM.
PASSO_S = 0.5


def montar_agenda(settings: Settings) -> list[tuple[Job, float]]:
    agenda: list[tuple[Job, float]] = [
        (jobs.expirar_propostas, settings.worker_intervalo_expiracao_s),
        (jobs.processar_outbox, settings.worker_intervalo_outbox_s),
        (jobs.limpar_dados_de_autenticacao, settings.worker_intervalo_retencao_s),
    ]
    if settings.matching_automatico:
        # ADR-021: o matching anda junto com a outbox (eventos de vaga livre).
        agenda.append((jobs.propor_vagas_livres, settings.worker_intervalo_outbox_s))
    return agenda


def rodar(agenda: list[tuple[Job, float]], parar: Callable[[], bool]) -> None:
    """Roda cada job no seu intervalo até `parar()` ser verdadeiro.

    A exceção de um job vai para o log e não derruba o laço.
    """
    proxima = [0.0] * len(agenda)
    while not parar():
        for i, (job, intervalo) in enumerate(agenda):
            if parar() or time.monotonic() < proxima[i]:
                continue
            try:
                job()
            except Exception as exc:
                logger.error("job %s falhou: %s", job.__name__, resumo_do_erro(exc))
            proxima[i] = time.monotonic() + intervalo
        espera = min(proxima) - time.monotonic()
        if espera > 0:
            time.sleep(min(espera, PASSO_S))


def main() -> None:
    settings = get_settings()
    configurar_logging(settings.log_level)

    # Só uma flag no handler: nada de locks dentro de tratador de sinal.
    sinal_recebido: list[int] = []
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda signum, _frame: sinal_recebido.append(signum))

    agenda = montar_agenda(settings)
    logger.info("worker iniciado com jobs: %s", ", ".join(j.__name__ for j, _ in agenda))
    rodar(agenda, parar=lambda: bool(sinal_recebido))
    logger.info("worker encerrado (sinal %s)", sinal_recebido[0])


if __name__ == "__main__":
    main()
