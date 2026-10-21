"""Avisos ao paciente: consumo da outbox, envio de e-mail, lembrete e rotas /avisos.

ADR-006, ADR-007, ADR-010, AM-008, RF-019, RF-024, RN-009, UC-003, UC-004.
Os jobs rodam com sessões na transação do teste; o de concorrência usa conexões próprias,
numa fila só dele, e apaga tudo no fim. E-mails vão para o `CanalFalso`.
"""

import ast
import json
import logging
import os
import smtplib
import threading
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.notificacoes.avisos import (
    TIPO_LEMBRETE,
    TIPOS_EVENTO_OUTBOX,
    Contexto,
    montar_avisos,
)
from app.dominio.notificacoes.canal import Mensagem
from app.dominio.notificacoes.textos import TEXTOS
from app.infra.db import SessionLocal
from app.infra.email import CanalEmailSmtp
from app.infra.modelos import (
    Agendamento,
    Consentimento,
    Especialidade,
    Fila,
    Notificacao,
    Outbox,
    Paciente,
    Solicitacao,
    Unidade,
    Usuario,
)
from app.infra.relogio import RelogioFixo
from app.worker import __main__ as worker
from app.worker import jobs
from tests.fila_sintetica import criar_paciente, csrf, entrar, montar_mundo
from tests.test_agendamentos import (
    LIMPEZA,
    T0,
    as_9h,
    criar_agenda,
    criar_vaga,
    na_fila,
    solicitacao_na_fila,
)

RECIFE = ZoneInfo("America/Recife")
APP = Path(__file__).resolve().parent.parent / "app"
COM_EMAIL = {t for t, (_, _, email) in TEXTOS.items() if email}


@dataclass
class CanalFalso:
    """Guarda as mensagens em memória; com `falhar`, levanta como um SMTP fora do ar."""

    falhar: bool = False
    enviadas: list[Mensagem] = field(default_factory=list)

    def enviar(self, mensagem: Mensagem) -> None:
        if self.falhar:
            raise smtplib.SMTPServerDisconnected("conexão perdida")
        self.enviadas.append(mensagem)


# --- mapeamento (sem banco) ---------------------------------------------------------------


def _tipos_gravados_no_codigo() -> set[str]:
    """Literais que chegam a `evento_outbox=` ou `tipo_evento=` em `app/`, inclusive por
    ternário ou por variável atribuída na mesma função (ex.: equipe.py)."""
    achados: set[str] = set()
    for arquivo in APP.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(), filename=str(arquivo))
        for funcao in ast.walk(arvore):
            if not isinstance(funcao, ast.FunctionDef):
                continue
            nomes: dict[str, set[str]] = {}
            for no in ast.walk(funcao):
                if isinstance(no, ast.Assign):
                    for alvo in no.targets:
                        pares = (
                            zip(alvo.elts, no.value.elts, strict=False)
                            if isinstance(alvo, ast.Tuple) and isinstance(no.value, ast.Tuple)
                            else [(alvo, no.value)]
                        )
                        for a, v in pares:
                            if isinstance(a, ast.Name):
                                nomes.setdefault(a.id, set()).update(_literais(v))
            for no in ast.walk(funcao):
                if isinstance(no, ast.keyword) and no.arg in ("evento_outbox", "tipo_evento"):
                    achados |= _valores(no.value, nomes, arquivo)
    return achados


def _valores(no: ast.expr, nomes: dict[str, set[str]], arquivo: Path) -> set[str]:
    """Valores possíveis da expressão: literal, ternário (sem a condição) ou variável local."""
    if isinstance(no, ast.Constant):
        return {no.value} if isinstance(no.value, str) else set()
    if isinstance(no, ast.IfExp):
        return _valores(no.body, nomes, arquivo) | _valores(no.orelse, nomes, arquivo)
    if isinstance(no, ast.Name):
        if no.id == "evento_outbox":  # o parâmetro de gravar_transicao
            return set()
        assert no.id in nomes, f"{arquivo}: tipo de evento em {no.id}"
        return nomes[no.id]
    raise AssertionError(f"{arquivo}:{no.lineno}: tipo de evento em expressão não prevista")


def _literais(no: ast.AST) -> set[str]:
    return {
        s.value for s in ast.walk(no) if isinstance(s, ast.Constant) and isinstance(s.value, str)
    }


def test_adr006_todo_tipo_gravado_no_codigo_esta_na_lista():
    assert _tipos_gravados_no_codigo() == TIPOS_EVENTO_OUTBOX


def test_adr006_todo_tipo_da_lista_tem_aviso_definido():
    assert set(TEXTOS) == TIPOS_EVENTO_OUTBOX | {TIPO_LEMBRETE}


PROIBIDAS_EMAIL = (
    "posição",
    "posicao",
    "fila",
    "nota",
    "risco",
    "compareceu",
    "falta",
    "cancel",
)


@pytest.mark.parametrize("tipo", sorted(TEXTOS))
def test_am008_email_minimo_sem_dado_pessoal_nem_local(tipo):
    contexto = Contexto(
        inicio=datetime(2026, 10, 29, 12, tzinfo=UTC),
        expira_em=datetime(2026, 10, 21, 12, tzinfo=UTC),
        unidade="Unidade Sintética 1",
        profissional="Dra. Sintética Exemplo",
        fim_da_fila=True,
    )
    avisos = montar_avisos(tipo, contexto, com_email=True, link="https://central", fuso=RECIFE)
    site = avisos[0]
    assert site.canal == "IN_APP"
    assert "{" not in site.titulo + site.corpo  # todo campo preenchido
    assert "posição" not in (site.titulo + site.corpo).lower()
    emails = [a for a in avisos if a.canal == "EMAIL"]
    assert len(emails) == (tipo in COM_EMAIL)
    for e in emails:
        texto = (e.titulo + e.corpo).lower()
        assert "unidade sintética" not in texto and "dra. sintética" not in texto
        assert all(p not in texto for p in PROIBIDAS_EMAIL)
        assert "https://central" in e.corpo
        assert e.titulo == "Central de Agendamento: você tem uma atualização"


def test_adr008_datas_do_aviso_no_fuso_de_recife():
    contexto = Contexto(expira_em=datetime(2026, 10, 21, 12, tzinfo=UTC))
    site, email = montar_avisos("PROPOSTA_ENVIADA", contexto, com_email=True, link="x", fuso=RECIFE)
    assert "21/10 às 09:00" in site.titulo
    assert "21/10 às 09:00" in email.corpo


def test_worker_agenda_inclui_os_jobs_de_aviso():
    agenda = [job for job, _ in worker.montar_agenda(get_settings())]
    assert {jobs.processar_outbox, jobs.enviar_emails, jobs.enviar_lembretes} <= set(agenda)


# --- cenário com banco --------------------------------------------------------------------


@dataclass
class Cenario:
    usuario: Usuario
    paciente: Paciente
    solicitacao: UUID
    agendamento: UUID
    inicio: datetime


def montar_cenario(sessao, relogio, mundo, *, com_email=True, lembrete=False, inicio=None):
    usuario, paciente = criar_paciente(sessao, login=False)
    if not com_email:
        usuario.email = None
    if lembrete:
        sessao.add(
            Consentimento(paciente_id=paciente.id, finalidade="LEMBRETE_EMAIL", versao_termo="v1")
        )
    inicio = inicio or as_9h()
    vaga = criar_vaga(sessao, criar_agenda(sessao, mundo.fila), inicio)
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    sessao.get(Solicitacao, sid).status = "AGENDADA"
    agora = relogio.agora()
    a = Agendamento(
        solicitacao_id=sid,
        vaga_id=vaga,
        status="CONFIRMADO",
        proposto_em=agora - timedelta(hours=1),
        expira_em=agora + timedelta(days=1),
    )
    sessao.add(a)
    sessao.flush()
    return Cenario(usuario, paciente, sid, a.id, inicio)


def gravar_evento(sessao, cenario, tipo, **payload) -> UUID:
    evento = Outbox(
        tipo_evento=tipo,
        agregado_tipo="solicitacao",
        agregado_id=cenario.solicitacao,
        payload={
            "solicitacao_id": str(cenario.solicitacao),
            "agendamento_id": str(cenario.agendamento),
        }
        | payload,
    )
    sessao.add(evento)
    sessao.flush()
    return evento.id


def avisos_de(sessao, usuario_id, canal=None) -> list[Notificacao]:
    consulta = select(Notificacao).where(Notificacao.usuario_id == usuario_id)
    if canal:
        consulta = consulta.where(Notificacao.canal == canal)
    return list(sessao.scalars(consulta.order_by(Notificacao.criada_em, Notificacao.canal)))


@pytest.fixture
def mundo(sessao):
    return montar_mundo(sessao)


@pytest.fixture
def cenario(sessao, relogio, mundo):
    return montar_cenario(sessao, relogio, mundo)


@pytest.fixture
def rodar(conexao, sessao, relogio):
    def _rodar(job, **kw):
        resultado = job(
            fabrica=lambda: Session(bind=conexao, join_transaction_mode="create_savepoint"),
            relogio=relogio,
            **kw,
        )
        sessao.expire_all()
        return resultado

    return _rodar


@pytest.fixture
def canal():
    return CanalFalso()


# --- processar_outbox ---------------------------------------------------------------------


@pytest.mark.integracao
@pytest.mark.parametrize("tipo", sorted(TIPOS_EVENTO_OUTBOX))
def test_adr006_processar_outbox_cria_os_avisos_de_cada_tipo(sessao, cenario, rodar, tipo):
    evento = gravar_evento(sessao, cenario, tipo, fim_da_fila=True)

    assert rodar(jobs.processar_outbox) == 1

    site = avisos_de(sessao, cenario.usuario.id, "IN_APP")
    email = avisos_de(sessao, cenario.usuario.id, "EMAIL")
    assert len(site) == 1 and site[0].tipo == tipo and site[0].status_envio == "ENVIADA"
    assert site[0].outbox_id == evento
    assert len(email) == (tipo in COM_EMAIL)
    for e in email:
        assert e.status_envio == "PENDENTE"
        # AM-008: nada que identifique o paciente, o local ou a fila.
        texto = (e.titulo + e.corpo).lower()
        proibidas = [
            cenario.paciente.nome,
            cenario.paciente.cpf,
            "Geral",  # nome da fila
            "Especialidade Sintética",
            "Unidade Sintética",
            "Dra. Sintética",
            *PROIBIDAS_EMAIL,
        ]
        assert all(p.lower() not in texto for p in proibidas)
    assert sessao.get(Outbox, evento).status == "PROCESSADO"


@pytest.mark.integracao
def test_adr007_aviso_do_site_traz_local_e_horario_sem_posicao(sessao, cenario, rodar):
    gravar_evento(sessao, cenario, "AGENDAMENTO_CONFIRMADO")
    rodar(jobs.processar_outbox)

    (site,) = avisos_de(sessao, cenario.usuario.id, "IN_APP")
    assert site.titulo == "Consulta confirmada para 29/10 às 09:00"
    assert "Unidade Sintética 1" in site.corpo and "Dra. Sintética Exemplo" in site.corpo
    assert "posição" not in site.corpo.lower()


@pytest.mark.integracao
@pytest.mark.parametrize(("fim", "efeito"), [(True, "fim da fila"), (False, "continua na fila")])
def test_uc005_aviso_da_recusa_diz_o_efeito_sem_posicao(sessao, cenario, rodar, fim, efeito):
    gravar_evento(sessao, cenario, "PROPOSTA_RECUSADA", fim_da_fila=fim)
    rodar(jobs.processar_outbox)

    (site,) = avisos_de(sessao, cenario.usuario.id, "IN_APP")
    assert efeito in site.corpo


@pytest.mark.integracao
def test_worker_lote_maximo_limita_cada_rodada(sessao, cenario, rodar, monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_lote_maximo", 2)
    for _ in range(3):
        gravar_evento(sessao, cenario, "SOLICITACAO_CRIADA")

    assert rodar(jobs.processar_outbox) == 2
    assert rodar(jobs.processar_outbox) == 1


@pytest.mark.integracao
def test_adr006_rodar_duas_vezes_nao_duplica(sessao, cenario, rodar):
    evento = gravar_evento(sessao, cenario, "PROPOSTA_ENVIADA")
    rodar(jobs.processar_outbox)
    assert rodar(jobs.processar_outbox) == 0

    # Mesmo que o evento volte a PENDENTE (Worker caiu antes do commit), o índice segura.
    sessao.get(Outbox, evento).status = "PENDENTE"
    sessao.flush()
    assert rodar(jobs.processar_outbox) == 1
    assert len(avisos_de(sessao, cenario.usuario.id)) == 2


@pytest.mark.integracao
def test_data_protection_paciente_sem_email_so_recebe_no_site(sessao, relogio, mundo, rodar):
    c = montar_cenario(sessao, relogio, mundo, com_email=False)
    gravar_evento(sessao, c, "PROPOSTA_ENVIADA")
    rodar(jobs.processar_outbox)

    assert [n.canal for n in avisos_de(sessao, c.usuario.id)] == ["IN_APP"]


@pytest.mark.integracao
def test_adr006_tipo_desconhecido_vai_para_falhou(sessao, cenario, rodar, caplog):
    evento = gravar_evento(sessao, cenario, "TIPO_QUE_NAO_EXISTE")
    with caplog.at_level(logging.WARNING):
        rodar(jobs.processar_outbox)

    assert sessao.get(Outbox, evento).status == "FALHOU"
    assert avisos_de(sessao, cenario.usuario.id) == []
    assert str(evento) in caplog.text and "desconhecido" in caplog.text


@pytest.mark.integracao
def test_adr006_falha_ao_montar_preserva_a_tentativa(sessao, cenario, rodar, relogio):
    evento = gravar_evento(sessao, cenario, "PROPOSTA_ENVIADA", solicitacao_id=str(uuid4()))
    rodar(jobs.processar_outbox)

    e = sessao.get(Outbox, evento)
    assert (e.status, e.tentativas) == ("PENDENTE", 1)
    assert e.proximo_retry_em == relogio.agora() + timedelta(minutes=1)
    assert rodar(jobs.processar_outbox) == 0  # ainda na espera
    assert sessao.get(Outbox, evento).tentativas == 1


@pytest.mark.integracao
def test_adr006_evento_que_sempre_falha_chega_a_falhou(sessao, cenario, rodar, relogio):
    evento = gravar_evento(sessao, cenario, "PROPOSTA_ENVIADA", solicitacao_id=str(uuid4()))
    maximo = get_settings().outbox_max_tentativas

    for _ in range(maximo + 2):
        rodar(jobs.processar_outbox)
        relogio.avancar(timedelta(hours=1))

    e = sessao.get(Outbox, evento)
    assert (e.status, e.tentativas) == ("FALHOU", maximo)


# --- enviar_emails ------------------------------------------------------------------------


def email_pendente(sessao, cenario, rodar) -> Notificacao:
    gravar_evento(sessao, cenario, "PROPOSTA_ENVIADA")
    rodar(jobs.processar_outbox)
    (email,) = avisos_de(sessao, cenario.usuario.id, "EMAIL")
    return email


@pytest.mark.integracao
def test_adr010_enviar_emails_sucesso_marca_enviada(sessao, cenario, rodar, canal, relogio):
    email = email_pendente(sessao, cenario, rodar)

    assert rodar(jobs.enviar_emails, canal=canal) == 1

    sessao.refresh(email)
    assert (email.status_envio, email.enviada_em) == ("ENVIADA", relogio.agora())
    (mensagem,) = canal.enviadas
    assert mensagem.destino == cenario.usuario.email
    assert mensagem.corpo == email.corpo
    assert rodar(jobs.enviar_emails, canal=canal) == 0
    assert len(canal.enviadas) == 1


@pytest.mark.integracao
def test_adr006_falha_no_envio_tenta_de_novo_com_espera_crescente(
    sessao, cenario, rodar, canal, relogio
):
    email = email_pendente(sessao, cenario, rodar)
    canal.falhar = True
    inicio = relogio.agora()

    rodar(jobs.enviar_emails, canal=canal)
    sessao.refresh(email)
    assert (email.status_envio, email.tentativas) == ("PENDENTE", 1)
    assert email.proximo_retry_em == inicio + timedelta(minutes=1)

    relogio.avancar(timedelta(seconds=59))
    assert rodar(jobs.enviar_emails, canal=canal) == 0
    sessao.refresh(email)
    assert email.tentativas == 1  # ainda na espera, nem tentou

    relogio.avancar(timedelta(seconds=1))
    rodar(jobs.enviar_emails, canal=canal)
    sessao.refresh(email)
    assert email.tentativas == 2
    assert email.proximo_retry_em == relogio.agora() + timedelta(minutes=5)

    canal.falhar = False
    relogio.avancar(timedelta(minutes=5))
    assert rodar(jobs.enviar_emails, canal=canal) == 1


@pytest.mark.integracao
def test_adr006_no_maximo_de_tentativas_vai_para_falhou(sessao, cenario, rodar, canal, relogio):
    email = email_pendente(sessao, cenario, rodar)
    canal.falhar = True
    maximo = get_settings().outbox_max_tentativas

    for _ in range(maximo + 2):
        rodar(jobs.enviar_emails, canal=canal)
        relogio.avancar(timedelta(hours=1))

    sessao.refresh(email)
    assert (email.status_envio, email.tentativas) == ("FALHOU", maximo)


@pytest.mark.integracao
def test_am008_log_do_envio_sem_email_nem_corpo(sessao, cenario, rodar, canal, caplog):
    email = email_pendente(sessao, cenario, rodar)
    canal.falhar = True
    with caplog.at_level(logging.DEBUG):
        rodar(jobs.enviar_emails, canal=canal)
        canal.falhar = False

    assert str(email.id) in caplog.text and "SMTPServerDisconnected" in caplog.text
    assert cenario.usuario.email not in caplog.text
    assert "conexão perdida" not in caplog.text  # a mensagem da exceção não vai para o log
    assert email.corpo.splitlines()[2] not in caplog.text


# --- lembrete -----------------------------------------------------------------------------


@pytest.mark.integracao
def test_rf024_lembrete_sai_uma_vez_so(sessao, relogio, mundo, rodar, canal):
    c = montar_cenario(
        sessao, relogio, mundo, lembrete=True, inicio=relogio.agora() + timedelta(hours=20)
    )

    assert rodar(jobs.enviar_lembretes) == 1
    assert rodar(jobs.enviar_lembretes) == 0

    lembretes = [n for n in avisos_de(sessao, c.usuario.id) if n.tipo == TIPO_LEMBRETE]
    assert sorted(n.canal for n in lembretes) == ["EMAIL", "IN_APP"]
    assert rodar(jobs.enviar_emails, canal=canal) == 1
    assert "Lembrete" in canal.enviadas[0].corpo


@pytest.mark.integracao
def test_rn009_sem_lembrete_email_o_lembrete_fica_so_no_site(sessao, relogio, mundo, rodar):
    c = montar_cenario(sessao, relogio, mundo, inicio=relogio.agora() + timedelta(hours=20))

    rodar(jobs.enviar_lembretes)

    assert [n.canal for n in avisos_de(sessao, c.usuario.id)] == ["IN_APP"]


@pytest.mark.integracao
def test_rf024_sem_lembrete_para_agendamento_cancelado(sessao, relogio, mundo, rodar):
    c = montar_cenario(
        sessao, relogio, mundo, lembrete=True, inicio=relogio.agora() + timedelta(hours=20)
    )
    sessao.get(Agendamento, c.agendamento).status = "CANCELADO"
    sessao.flush()

    assert rodar(jobs.enviar_lembretes) == 0
    assert avisos_de(sessao, c.usuario.id) == []


@pytest.mark.integracao
def test_rf024_cancelado_depois_do_lembrete_cancela_o_email(sessao, relogio, mundo, rodar, canal):
    c = montar_cenario(
        sessao, relogio, mundo, lembrete=True, inicio=relogio.agora() + timedelta(hours=20)
    )
    rodar(jobs.enviar_lembretes)
    sessao.get(Agendamento, c.agendamento).status = "CANCELADO"
    sessao.flush()

    assert rodar(jobs.enviar_emails, canal=canal) == 0

    (email,) = avisos_de(sessao, c.usuario.id, "EMAIL")
    assert email.status_envio == "CANCELADA"
    assert canal.enviadas == []


@pytest.mark.integracao
def test_rn009_consentimento_revogado_antes_do_envio_cancela_o_lembrete(
    sessao, relogio, mundo, rodar, canal
):
    c = montar_cenario(
        sessao, relogio, mundo, lembrete=True, inicio=relogio.agora() + timedelta(hours=20)
    )
    rodar(jobs.enviar_lembretes)
    consentimento = sessao.scalar(
        select(Consentimento).where(
            Consentimento.paciente_id == c.paciente.id,
            Consentimento.finalidade == "LEMBRETE_EMAIL",
        )
    )
    consentimento.revogado_em = relogio.agora()
    sessao.flush()

    rodar(jobs.enviar_emails, canal=canal)

    assert avisos_de(sessao, c.usuario.id, "EMAIL")[0].status_envio == "CANCELADA"
    assert canal.enviadas == []


@pytest.mark.integracao
@pytest.mark.parametrize(("horas", "sai"), [(23, True), (24, True), (25, False), (-1, False)])
def test_rf024_lembrete_respeita_a_antecedencia(sessao, relogio, mundo, rodar, horas, sai):
    c = montar_cenario(
        sessao, relogio, mundo, lembrete=True, inicio=relogio.agora() + timedelta(hours=horas)
    )

    rodar(jobs.enviar_lembretes)

    assert bool(avisos_de(sessao, c.usuario.id)) is sai


# --- rotas /avisos ------------------------------------------------------------------------


@pytest.fixture
def logado(api, sessao, relogio, mundo, rodar):
    """Paciente logado com dois avisos no site (e um e-mail que a rota não mostra)."""
    usuario, paciente = criar_paciente(sessao)
    sessao.flush()
    c = Cenario(usuario, paciente, *_solicitacao_com_agendamento(sessao, relogio, mundo, paciente))
    gravar_evento(sessao, c, "SOLICITACAO_CRIADA")
    gravar_evento(sessao, c, "PROPOSTA_ENVIADA")
    rodar(jobs.processar_outbox)
    entrar(api, paciente.cpf)
    return c


def _solicitacao_com_agendamento(sessao, relogio, mundo, paciente):
    vaga = criar_vaga(sessao, criar_agenda(sessao, mundo.fila), as_9h())
    sid = solicitacao_na_fila(sessao, paciente, mundo.fila)
    agora = relogio.agora()
    a = Agendamento(
        solicitacao_id=sid, vaga_id=vaga, proposto_em=agora, expira_em=agora + timedelta(days=1)
    )
    sessao.add(a)
    sessao.flush()
    return sid, a.id, as_9h()


@pytest.mark.integracao
def test_rf019_lista_so_os_proprios_avisos_do_site(api, sessao, relogio, mundo, rodar, logado):
    outro = montar_cenario(sessao, relogio, mundo)
    gravar_evento(sessao, outro, "PROPOSTA_ENVIADA")
    rodar(jobs.processar_outbox)

    resposta = api.get("/api/v1/avisos")

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-store"
    itens = resposta.json()
    assert len(itens) == 2  # só IN_APP do próprio usuário
    assert {"canal", "status_envio", "tentativas", "usuario_id"}.isdisjoint(itens[0])
    assert {i["tipo"] for i in itens} == {"SOLICITACAO_CRIADA", "PROPOSTA_ENVIADA"}


@pytest.mark.integracao
def test_am001_aviso_de_outro_usuario_retorna_404(api, sessao, relogio, mundo, rodar, logado):
    outro = montar_cenario(sessao, relogio, mundo)
    gravar_evento(sessao, outro, "SOLICITACAO_CRIADA")
    rodar(jobs.processar_outbox)
    (alheio,) = avisos_de(sessao, outro.usuario.id, "IN_APP")

    resposta = api.post(f"/api/v1/avisos/{alheio.id}/lido", headers=csrf(api))

    assert resposta.status_code == 404
    sessao.refresh(alheio)
    assert alheio.lida_em is None


@pytest.mark.integracao
def test_rf019_e_mail_nao_e_aviso_do_site(api, sessao, logado):
    (email,) = avisos_de(sessao, logado.usuario.id, "EMAIL")

    assert api.post(f"/api/v1/avisos/{email.id}/lido", headers=csrf(api)).status_code == 404


@pytest.mark.integracao
def test_rf019_marcar_como_lido_duas_vezes_nao_da_erro(api, sessao, relogio, logado):
    aviso = avisos_de(sessao, logado.usuario.id, "IN_APP")[0]

    assert api.post(f"/api/v1/avisos/{aviso.id}/lido", headers=csrf(api)).status_code == 204
    primeira = relogio.agora()
    relogio.avancar(timedelta(minutes=5))
    assert api.post(f"/api/v1/avisos/{aviso.id}/lido", headers=csrf(api)).status_code == 204

    sessao.refresh(aviso)
    assert aviso.lida_em == primeira


@pytest.mark.integracao
def test_rf019_contagem_e_marcar_todos(api, sessao, logado):
    assert api.get("/api/v1/avisos/contagem").json() == {"nao_lidos": 2}
    aviso = avisos_de(sessao, logado.usuario.id, "IN_APP")[0]
    api.post(f"/api/v1/avisos/{aviso.id}/lido", headers=csrf(api))
    assert api.get("/api/v1/avisos/contagem").json() == {"nao_lidos": 1}
    assert len(api.get("/api/v1/avisos", params={"somente_nao_lidos": True}).json()) == 1

    assert api.post("/api/v1/avisos/lidos", headers=csrf(api)).status_code == 204

    assert api.get("/api/v1/avisos/contagem").json() == {"nao_lidos": 0}


@pytest.mark.integracao
@pytest.mark.parametrize("caminho", ["/api/v1/avisos/lidos", f"/api/v1/avisos/{uuid4()}/lido"])
def test_am002_escrita_em_avisos_sem_csrf_retorna_403(api, logado, caminho):
    assert api.post(caminho).status_code == 403


@pytest.mark.integracao
@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("GET", "/api/v1/avisos"),
        ("GET", "/api/v1/avisos/contagem"),
        ("POST", "/api/v1/avisos/lidos"),
        ("POST", f"/api/v1/avisos/{uuid4()}/lido"),
    ],
)
def test_am001_avisos_sem_sessao_retornam_401(api, metodo, caminho):
    api.cookies.set("csrf_token", "x")
    assert api.request(metodo, caminho, headers={"X-CSRF-Token": "x"}).status_code == 401


# --- ponta a ponta ------------------------------------------------------------------------


@pytest.mark.integracao
def test_uc003_uc004_proposta_vira_aviso_e_email_e_paciente_le(
    api, sessao, mundo, relogio, rodar, canal
):
    _, paciente = criar_paciente(sessao)
    entrar(api, paciente.cpf)
    criar_vaga(sessao, criar_agenda(sessao, mundo.fila), as_9h())
    solicitacao_na_fila(sessao, paciente, mundo.fila)

    assert rodar(jobs.propor_vagas) == 1  # 1. proposta enviada
    assert rodar(jobs.processar_outbox) == 1  # 2. aviso criado
    assert rodar(jobs.enviar_emails, canal=canal) == 1  # 3. e-mail entregue
    (mensagem,) = canal.enviadas
    assert "confirme até" in mensagem.corpo

    assert api.get("/api/v1/avisos/contagem").json() == {"nao_lidos": 1}  # 4. paciente vê
    (aviso,) = api.get("/api/v1/avisos").json()
    assert aviso["tipo"] == "PROPOSTA_ENVIADA" and aviso["lido_em"] is None
    assert api.post(f"/api/v1/avisos/{aviso['id']}/lido", headers=csrf(api)).status_code == 204
    assert api.get("/api/v1/avisos/contagem").json() == {"nao_lidos": 0}


# --- concorrência (conexões próprias, commit de verdade) ----------------------------------


@pytest.fixture
def fila_real(banco):
    with SessionLocal() as s:
        sufixo = uuid4().hex[:8]
        unidade = Unidade(sigla=f"A{sufixo}", nome="Unidade Sintética Avisos")
        especialidade = Especialidade(nome=f"Especialidade Avisos {sufixo}")
        s.add_all([unidade, especialidade])
        s.flush()
        fila = Fila(
            unidade_id=unidade.id,
            especialidade_id=especialidade.id,
            nome="Avisos",
            descricao_paciente="Fila sintética dos avisos.",
        )
        s.add(fila)
        s.commit()
        ids = {"fila": fila.id, "unidade": unidade.id, "especialidade": especialidade.id}
    yield fila.id
    with banco.begin() as c:
        c.execute(
            text(
                "DELETE FROM notificacao WHERE solicitacao_id IN "
                "(SELECT id FROM solicitacao WHERE fila_id = :fila)"
            ),
            ids,
        )
        for comando in filter(str.strip, LIMPEZA.split(";")):
            c.execute(text(comando), ids)


@pytest.mark.integracao
def test_adr006_dois_workers_em_paralelo_nao_duplicam_avisos(fila_real):
    relogio = RelogioFixo(datetime(2030, 1, 7, 12, tzinfo=UTC))
    n = 10
    with SessionLocal() as s:
        solicitacoes = [na_fila(s, fila_real, entrada=T0) for _ in range(n)]
        for sid in solicitacoes:
            s.add(
                Outbox(
                    tipo_evento="SOLICITACAO_NA_FILA",
                    agregado_tipo="solicitacao",
                    agregado_id=sid,
                    payload={"solicitacao_id": str(sid)},
                )
            )
        s.commit()

    largada = threading.Barrier(2)
    erros: list[BaseException] = []
    feitos: list[int] = []

    def rodar_worker():
        try:
            largada.wait()
            feitos.append(jobs.processar_outbox(relogio=relogio))
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    threads = [threading.Thread(target=rodar_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not erros
    assert sum(feitos) == n  # cada evento contado por um único Worker
    with SessionLocal() as s:
        avisos = s.scalars(
            select(Notificacao.solicitacao_id).where(Notificacao.solicitacao_id.in_(solicitacoes))
        ).all()
    assert sorted(avisos) == sorted(solicitacoes)  # um aviso no site por evento, sem e-mail


# --- mailpit (só com o mailpit no ar; fora da CI) -----------------------------------------


def _mailpit_no_ar() -> bool:
    cfg = get_settings()
    try:
        smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=2).quit()
    except OSError:
        return False
    return True


@pytest.mark.skipif(
    not _mailpit_no_ar(), reason="mailpit fora do ar (docker compose --profile dev)"
)
def test_adr010_email_de_proposta_chega_no_mailpit():
    cfg = get_settings()
    destino = f"teste-{uuid4().hex[:8]}@exemplo.com"
    _, email = montar_avisos(
        "PROPOSTA_ENVIADA",
        Contexto(expira_em=datetime(2026, 10, 21, 12, tzinfo=UTC)),
        com_email=True,
        link=cfg.app_url_publica,
        fuso=RECIFE,
    )

    CanalEmailSmtp(cfg).enviar(Mensagem(destino=destino, assunto=email.titulo, corpo=email.corpo))

    api = os.environ.get("MAILPIT_API", f"http://{cfg.smtp_host}:8025")
    with urllib.request.urlopen(f"{api}/api/v1/search?query=to:{destino}", timeout=5) as r:
        mensagens = json.load(r)["messages"]
    assert len(mensagens) == 1
    assert mensagens[0]["Subject"] == "Central de Agendamento: você tem uma atualização"


@pytest.mark.integracao
def test_adr005_dois_workers_enviando_emails_nao_duplicam(fila_real):
    relogio = RelogioFixo(datetime(2030, 1, 7, 12, tzinfo=UTC))
    n = 10
    with SessionLocal() as s:
        for _ in range(n):
            sid = na_fila(s, fila_real, entrada=T0)
            usuario_id = s.scalar(
                select(Paciente.usuario_id)
                .join(Solicitacao, Solicitacao.paciente_id == Paciente.id)
                .where(Solicitacao.id == sid)
            )
            s.add(
                Notificacao(
                    usuario_id=usuario_id,
                    solicitacao_id=sid,
                    canal="EMAIL",
                    tipo="PROPOSTA_ENVIADA",
                    titulo="t",
                    corpo="c",
                    proximo_retry_em=relogio.agora(),
                )
            )
        s.commit()
    canal = CanalFalso()
    largada = threading.Barrier(2)
    erros: list[BaseException] = []
    feitos: list[int] = []

    def rodar_worker():
        try:
            largada.wait()
            feitos.append(jobs.enviar_emails(relogio=relogio, canal=canal))
        except BaseException as exc:  # noqa: BLE001
            erros.append(exc)

    threads = [threading.Thread(target=rodar_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not erros
    assert sum(feitos) == n
    assert len(canal.enviadas) == n  # nenhum e-mail saiu duas vezes


@pytest.mark.integracao
def test_rf024_lembrete_durante_cancelamento_pula_sem_deadlock(fila_real):
    """O cancelamento trava a solicitação; o lembrete pula o item em vez de esperar."""
    relogio = RelogioFixo(datetime(2030, 1, 7, 12, tzinfo=UTC))
    with SessionLocal() as s:
        agenda = criar_agenda(s, fila_real, vigencia_inicio=datetime(2030, 1, 1).date())
        vaga = criar_vaga(s, agenda, relogio.agora() + timedelta(hours=10))
        sid = na_fila(s, fila_real, entrada=T0)
        s.get(Solicitacao, sid).status = "AGENDADA"
        a = Agendamento(
            solicitacao_id=sid,
            vaga_id=vaga,
            status="CONFIRMADO",
            proposto_em=relogio.agora() - timedelta(days=2),
            expira_em=relogio.agora() - timedelta(days=1),
        )
        s.add(a)
        s.commit()
        agendamento_id = a.id

    with SessionLocal() as cancelamento:
        cancelamento.scalar(select(Solicitacao).where(Solicitacao.id == sid).with_for_update())
        assert jobs.enviar_lembretes(relogio=relogio) == 0
        cancelamento.rollback()

    assert jobs.enviar_lembretes(relogio=relogio) == 1
    with SessionLocal() as s:
        assert s.scalar(select(Notificacao.id).where(Notificacao.agendamento_id == agendamento_id))
