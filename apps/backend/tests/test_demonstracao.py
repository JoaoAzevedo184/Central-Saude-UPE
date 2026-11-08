"""Fila de demonstração da apresentação ao vivo (comando `app.infra.demonstracao`).

Cobre as travas, a criação idempotente, o isolamento das outras filas, o escopo da equipe,
a regra das 36 h (24 h de antecedência + 12 h de janela) e o `desativar`.
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.infra import demonstracao
from app.infra.acesso import carregar_escopo
from app.infra.demonstracao import DemonstracaoRecusada, desativar, preparar
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Especialidade,
    Fila,
    Solicitacao,
    Usuario,
    Vaga,
    usuario_fila,
)
from app.infra.seed import semear
from app.infra.transicoes import EntradaInvalida, classificar_na_fila, criar_solicitacao
from app.worker import jobs
from tests.fila_sintetica import criar_paciente
from tests.test_agendamentos import agendamentos_de, rodar  # noqa: F401  (fixture)

pytestmark = pytest.mark.integracao

RECIFE = ZoneInfo("America/Recife")


@pytest.fixture
def cfg():
    return get_settings().model_copy(update={"app_env": "development", "demo_seed_permitido": True})


@pytest.fixture
def seed(sessao, relogio):
    semear(sessao, relogio, "hash-de-teste")
    sessao.add(Usuario(email=demonstracao.ATENDENTE, senha_hash="!", papel="ATENDENTE"))
    sessao.flush()


def ids_fora_da_demo(sessao):
    demo = select(Fila.id).where(Fila.nome == demonstracao.FILA)
    return (
        set(sessao.scalars(select(Fila.id).where(Fila.nome != demonstracao.FILA))),
        set(sessao.scalars(select(Agenda.id).where(Agenda.fila_id.not_in(demo)))),
        set(sessao.scalars(select(Vaga.id).join(Agenda).where(Agenda.fila_id.not_in(demo)))),
    )


def fila_demo(sessao) -> Fila:
    return sessao.scalar(select(Fila).where(Fila.nome == demonstracao.FILA))


def usuario(sessao, email):
    return sessao.scalar(select(Usuario).where(Usuario.email == email))


@pytest.mark.parametrize(
    ("ambiente", "permitido", "confirmo"),
    [
        ("development", True, False),
        ("development", False, True),
        ("production", False, True),
        ("production", True, False),
        ("test", True, True),
    ],
)
def test_demo_sem_as_travas_recusa(sessao, seed, relogio, cfg, ambiente, permitido, confirmo):
    cfg = cfg.model_copy(update={"app_env": ambiente, "demo_seed_permitido": permitido})

    with pytest.raises(DemonstracaoRecusada):
        preparar(sessao, cfg, relogio, lambda _: None, confirmo=confirmo)
    with pytest.raises(DemonstracaoRecusada):
        desativar(sessao, cfg, lambda _: None, confirmo=confirmo)

    assert fila_demo(sessao) is None


def test_demo_preparar_cria_fila_agenda_e_vagas_sem_duplicar(sessao, seed, relogio, cfg):
    primeiro = preparar(sessao, cfg, relogio, lambda _: None, confirmo=True)
    vagas = sessao.scalar(select(func.count()).select_from(Vaga))
    segundo = preparar(sessao, cfg, relogio, lambda _: None, confirmo=True)

    fila = fila_demo(sessao)
    assert primeiro.fila_id == segundo.fila_id == fila.id
    assert fila.ativa and fila.sexo_elegivel is None and fila.idade_minima is None
    assert sessao.scalar(select(func.count()).select_from(Especialidade)) == 5  # 4 do seed + 1
    assert sessao.scalar(select(func.count()).where(Agenda.fila_id == fila.id)) == 1
    assert sessao.scalar(select(func.count()).select_from(Vaga)) == vagas
    assert primeiro.vagas_livres == segundo.vagas_livres > 0
    atendente = usuario(sessao, demonstracao.ATENDENTE)
    assert sessao.scalar(select(func.count()).where(usuario_fila.c.fila_id == fila.id)) == 1
    assert (
        sessao.scalar(select(usuario_fila.c.usuario_id).where(usuario_fila.c.fila_id == fila.id))
        == atendente.id
    )


def test_demo_preparar_nao_altera_as_outras_filas(sessao, seed, relogio, cfg):
    antes = ids_fora_da_demo(sessao)

    preparar(sessao, cfg, relogio, lambda _: None, confirmo=True)
    preparar(sessao, cfg, relogio, lambda _: None, confirmo=True)

    assert ids_fora_da_demo(sessao) == antes
    assert len(antes[0]) == 5 and len(antes[1]) == 5


def test_demo_escopo_da_equipe(sessao, seed, relogio, cfg):
    preparar(sessao, cfg, relogio, lambda _: None, confirmo=True)
    fila = fila_demo(sessao).id

    def escopo(email):
        return carregar_escopo(sessao, usuario(sessao, email).id)

    assert fila in escopo(demonstracao.ATENDENTE)
    assert fila in escopo(demonstracao.GESTOR)
    assert fila not in escopo("atendente.huoc@exemplo.com")  # outra unidade


def test_demo_pedido_so_recebe_vaga_a_36h_ou_mais(sessao, seed, relogio, cfg, rodar):  # noqa: F811
    saida: list[str] = []
    resumo = preparar(sessao, cfg, relogio, saida.append, confirmo=True)
    agora = relogio.agora()
    _, p = criar_paciente(sessao, login=False)
    s = criar_solicitacao(
        sessao,
        p,
        resumo.fila_id,
        [],
        turno_preferido="QUALQUER",
        origem_encaminhamento=None,
        agora=agora,
        hoje=agora.astimezone(RECIFE).date(),
        ip=None,
    )
    atendente = usuario(sessao, demonstracao.ATENDENTE)
    classificar_na_fila(sessao, s, "AMARELO", None, agora=agora, atendente_id=atendente.id, ip=None)
    sessao.flush()

    assert rodar(jobs.propor_vagas) == 1

    (proposta,) = agendamentos_de(sessao, s.id)
    inicio = sessao.get(Vaga, proposta.vaga_id).inicio
    assert inicio >= agora + timedelta(hours=36)
    assert inicio == resumo.primeira_proponivel  # o resumo não mente
    # só uma proposta, e nenhuma vaga de menos de 36 h ficou ocupada
    assert sessao.scalar(select(func.count()).select_from(Agendamento)) == 1
    assert any("a partir de" in linha and "36 h" in linha for linha in saida)


def test_demo_desativar_tira_de_uso_sem_apagar_historico(sessao, seed, relogio, cfg, rodar):  # noqa: F811
    resumo = preparar(sessao, cfg, relogio, lambda _: None, confirmo=True)
    _, p = criar_paciente(sessao, login=False)
    _, p2 = criar_paciente(sessao, login=False)
    agora = relogio.agora()
    s = criar_solicitacao(
        sessao,
        p,
        resumo.fila_id,
        [],
        turno_preferido="QUALQUER",
        origem_encaminhamento=None,
        agora=agora,
        hoje=agora.astimezone(RECIFE).date(),
        ip=None,
    )
    vagas = sessao.scalar(select(func.count()).select_from(Vaga))

    assert desativar(sessao, cfg, lambda _: None, confirmo=True) is True
    assert desativar(sessao, cfg, lambda _: None, confirmo=True) is True  # idempotente

    fila = fila_demo(sessao)
    assert not fila.ativa
    assert not sessao.scalar(select(Agenda.ativa).where(Agenda.fila_id == fila.id))
    assert sessao.scalar(select(func.count()).select_from(Vaga)) == vagas
    assert sessao.get(Solicitacao, s.id) is not None
    with pytest.raises(EntradaInvalida):
        criar_solicitacao(
            sessao,
            p2,
            fila.id,
            [],
            turno_preferido="QUALQUER",
            origem_encaminhamento=None,
            agora=agora,
            hoje=agora.astimezone(RECIFE).date(),
            ip=None,
        )


def test_demo_desativar_sem_fila_nao_faz_nada(sessao, seed, cfg):
    assert desativar(sessao, cfg, lambda _: None, confirmo=True) is False
