from app.config import Settings
from app.worker import __main__ as worker
from app.worker import jobs


def test_excecao_em_um_job_nao_derruba_o_laco():
    chamadas = []

    def quebra():
        chamadas.append("quebra")
        raise RuntimeError("falha sintética")

    def ok():
        chamadas.append("ok")
        return 0

    worker.rodar([(quebra, 0), (ok, 0)], parar=lambda: chamadas.count("ok") >= 2)

    assert chamadas.count("quebra") >= 2
    assert chamadas.count("ok") == 2


def test_adr021_matching_so_entra_na_agenda_com_a_flag():
    com = worker.montar_agenda(Settings(matching_automatico=True))
    sem = worker.montar_agenda(Settings(matching_automatico=False))

    assert jobs.propor_vagas in [job for job, _ in com]
    assert jobs.propor_vagas not in [job for job, _ in sem]


def test_retencao_entra_na_agenda():
    assert jobs.limpar_dados_de_autenticacao in [job for job, _ in worker.montar_agenda(Settings())]
