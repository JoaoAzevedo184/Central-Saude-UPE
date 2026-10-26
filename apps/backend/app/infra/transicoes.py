"""Transições de estado do paciente e da equipe, passos 3 a 6 da regra de arquitetura 2.

A rota (ou o seed) já travou o agregado (`FOR UPDATE`) e conferiu dono ou escopo; estas funções
conferem estado e prazo no domínio com `agora`, aplicam, auditam e gravam a outbox. O commit é de
quem chama. `ip=None` serve ao Worker e ao seed. As rotas só traduzem HTTP: a regra e a gravação
ficam aqui, para a API e o seed usarem a mesma implementação.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.agendamento.estados import cancelar_pelo_paciente as cancelar_agendamento
from app.dominio.agendamento.estados import confirmar as confirmar_agendamento
from app.dominio.agendamento.estados import recusar as recusar_agendamento
from app.dominio.agendamento.estados import registrar_presenca
from app.dominio.erros import EntradaInvalida, NaoElegivel, SemConsentimento, SolicitacaoDuplicada
from app.dominio.fila.criterios import (
    ORIGENS_DA_EQUIPE,
    ORIGENS_DO_PACIENTE,
    calcular_nota,
    pontuar_respostas,
)
from app.dominio.fila.elegibilidade import DadosPaciente, RestricoesFila, motivo_inelegivel
from app.dominio.solicitacao import cancelar as cancelar_solicitacao
from app.dominio.solicitacao import (
    classificar as classificar_solicitacao,
)
from app.dominio.solicitacao import (
    confirmar_proposta,
    evento_criada,
    exigir_aceita_respostas,
    recalcular_nota,
    recusar_proposta,
    registrar_atendimento,
    registrar_falta,
)
from app.infra.agendamentos import (
    aplicar_agendamento,
    contar_recusas,
    para_dominio_agendamento,
)
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Consentimento,
    Fila,
    Paciente,
    RespostaCriterio,
    Solicitacao,
    Vaga,
)
from app.infra.solicitacoes import criterios_da_fila, gravar_transicao, para_dominio

ENCERRADAS = ("ATENDIDA", "CANCELADA")
INDICE_SOLICITACAO_ATIVA = "ux_solicitacao_ativa_por_fila"


def motivo_de_inelegibilidade(paciente: Paciente, fila: Fila, hoje: date) -> str | None:
    return motivo_inelegivel(
        DadosPaciente(paciente.sexo, paciente.data_nascimento),
        RestricoesFila(fila.sexo_elegivel, fila.idade_minima, fila.idade_maxima),
        hoje,
    )


# --- paciente -----------------------------------------------------------------------------


def criar_solicitacao(
    session: Session,
    paciente: Paciente,
    fila_id: UUID,
    respostas: list[tuple[UUID, Any]],
    *,
    turno_preferido: str,
    origem_encaminhamento: str | None,
    agora: datetime,
    hoje: date,
    ip: str | None,
) -> Solicitacao:
    """UC-002: cria a solicitação em EM_ANALISE, com a nota das respostas (RN-006)."""
    consentimento = session.scalar(
        select(
            exists().where(
                Consentimento.paciente_id == paciente.id,
                Consentimento.finalidade == "AGENDAMENTO",
                Consentimento.revogado_em.is_(None),
            )
        )
    )
    if not consentimento:
        raise SemConsentimento("É preciso consentir com o uso dos dados para agendamento.")
    fila = session.scalar(select(Fila).where(Fila.id == fila_id, Fila.ativa))
    if fila is None:
        raise EntradaInvalida("Fila inexistente ou inativa.")
    if motivo := motivo_de_inelegibilidade(paciente, fila, hoje):
        raise NaoElegivel(motivo)

    criterios = criterios_da_fila(session, fila.id)
    pontos = pontuar_respostas(criterios, respostas, ORIGENS_DO_PACIENTE)
    nota = calcular_nota((criterios[c], v) for c, v in respostas)

    try:
        with session.begin_nested():
            s = Solicitacao(
                paciente_id=paciente.id,
                fila_id=fila.id,
                status="EM_ANALISE",
                nota=nota,
                turno_preferido=turno_preferido,
                origem_encaminhamento=origem_encaminhamento,
                data_pedido=hoje,
                criada_em=agora,
            )
            session.add(s)
            session.flush()
    except IntegrityError as exc:
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != (
            INDICE_SOLICITACAO_ATIVA
        ):
            raise
        existente = session.scalar(
            select(Solicitacao.id).where(
                Solicitacao.paciente_id == paciente.id,
                Solicitacao.fila_id == fila.id,
                Solicitacao.status.not_in(ENCERRADAS),
            )
        )
        raise SolicitacaoDuplicada(existente) from None
    gravar_transicao(
        session,
        s,
        para_dominio(s),
        [evento_criada(agora)],
        ator_id=paciente.usuario_id,
        acao="CRIAR_SOLICITACAO",
        ip=ip,
        evento_outbox="SOLICITACAO_CRIADA",
        criacao=True,
    )
    session.add_all(
        RespostaCriterio(
            solicitacao_id=s.id,
            criterio_id=c,
            fila_id=fila.id,
            valor=v,
            pontos=pontos[c],
            respondido_por_usuario_id=paciente.usuario_id,
            respondido_em=agora,
        )
        for c, v in respostas
    )
    return s


def cancelar_do_paciente(
    session: Session,
    s: Solicitacao,
    ativo: tuple[Agendamento, datetime] | None,
    motivo_codigo: str,
    *,
    agora: datetime,
    usuario_id: UUID,
    ip: str | None,
) -> None:
    """Cancelamento ("não vou precisar"). `ativo` é o agendamento PROPOSTO ou CONFIRMADO, já
    travado, com o início da vaga; ele é cancelado junto, só antes do início (RN-005)."""
    nova, evento = cancelar_solicitacao(
        para_dominio(s), motivo_codigo, agora, tem_agendamento_ativo=ativo is not None
    )
    if ativo:
        a, inicio = ativo
        aplicar_agendamento(
            session,
            a,
            cancelar_agendamento(para_dominio_agendamento(a), inicio, agora),
            ator_id=usuario_id,
            acao="CANCELAR_AGENDAMENTO",
            ip=ip,
        )
    s.motivo_cancelamento = motivo_codigo
    gravar_transicao(
        session,
        s,
        nova,
        [evento],
        ator_id=usuario_id,
        acao="CANCELAR_SOLICITACAO",
        ip=ip,
        evento_outbox="AGENDAMENTO_CANCELADO" if ativo else "SOLICITACAO_CANCELADA",
        auditoria_depois={"motivo_cancelamento": motivo_codigo},
        agendamento_id=ativo[0].id if ativo else None,
    )


def confirmar_do_paciente(
    session: Session,
    s: Solicitacao,
    a: Agendamento,
    *,
    agora: datetime,
    usuario_id: UUID,
    ip: str | None,
) -> None:
    """UC-004: PROPOSTO → CONFIRMADO e solicitação AGENDADA, só antes de `expira_em`."""
    novo = confirmar_agendamento(para_dominio_agendamento(a), agora)
    nova, evento = confirmar_proposta(para_dominio(s), agora)
    aplicar_agendamento(session, a, novo, ator_id=usuario_id, acao="CONFIRMAR_AGENDAMENTO", ip=ip)
    gravar_transicao(
        session,
        s,
        nova,
        [evento],
        ator_id=usuario_id,
        acao="CONFIRMAR_AGENDAMENTO",
        ip=ip,
        evento_outbox="AGENDAMENTO_CONFIRMADO",
        agendamento_id=a.id,
    )


def recusar_do_paciente(
    session: Session,
    s: Solicitacao,
    a: Agendamento,
    *,
    agora: datetime,
    usuario_id: UUID,
    ip: str | None,
) -> None:
    """UC-005 ("esta data não serve"): só PROPOSTO. A vaga fica livre para o próximo."""
    novo = recusar_agendamento(para_dominio_agendamento(a), agora)
    nova, eventos = recusar_proposta(
        para_dominio(s),
        contar_recusas(session, s),
        get_settings().recusas_mantendo_posicao,
        agora,
    )
    aplicar_agendamento(session, a, novo, ator_id=usuario_id, acao="RECUSAR_PROPOSTA", ip=ip)
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=usuario_id,
        acao="RECUSAR_PROPOSTA",
        ip=ip,
        evento_outbox="PROPOSTA_RECUSADA",
        agendamento_id=a.id,
    )


# --- equipe -------------------------------------------------------------------------------


def classificar_na_fila(
    session: Session,
    s: Solicitacao,
    classificacao_risco: str,
    motivo: str | None,
    *,
    agora: datetime,
    atendente_id: UUID,
    ip: str | None,
) -> None:
    """EM_ANALISE → NA_FILA; em NA_FILA só reclassifica, com motivo obrigatório."""
    primeira = s.status == "EM_ANALISE"
    nova, eventos = classificar_solicitacao(para_dominio(s), classificacao_risco, motivo, agora)
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=atendente_id,
        acao="CLASSIFICAR" if primeira else "RECLASSIFICAR",
        ip=ip,
        evento_outbox="SOLICITACAO_NA_FILA" if primeira else None,
    )


def responder_criterios_da_equipe(
    session: Session,
    s: Solicitacao,
    novas: list[tuple[UUID, Any]],
    *,
    agora: datetime,
    atendente_id: UUID,
    ip: str | None,
) -> None:
    """Critérios de origem REGULACAO ou EQUIPE; a nota é recalculada por `calcular_nota()`.
    Na fila, nota diferente grava RECLASSIFICADA (só equipe)."""
    exigir_aceita_respostas(para_dominio(s))  # estado de origem antes de validar a entrada
    criterios = criterios_da_fila(session, s.fila_id)
    pontos = pontuar_respostas(criterios, novas, ORIGENS_DA_EQUIPE)

    gravadas = {
        r.criterio_id: r
        for r in session.scalars(
            select(RespostaCriterio).where(RespostaCriterio.solicitacao_id == s.id)
        )
    }
    valores = {c: r.valor for c, r in gravadas.items() if c in criterios} | dict(novas)
    nota = calcular_nota((criterios[c], v) for c, v in valores.items())
    nova, evento = recalcular_nota(para_dominio(s), nota, agora)
    # RN-010: quais respostas mudaram, sem nome nem CPF.
    respostas_antes = {str(c): gravadas[c].valor if c in gravadas else None for c, _ in novas}

    for criterio_id, valor in novas:
        resposta = gravadas.get(criterio_id) or RespostaCriterio(
            solicitacao_id=s.id, criterio_id=criterio_id, fila_id=s.fila_id
        )
        resposta.valor = valor
        resposta.pontos = pontos[criterio_id]
        resposta.respondido_por_usuario_id = atendente_id
        resposta.respondido_em = agora
        session.add(resposta)
    gravar_transicao(
        session,
        s,
        nova,
        [evento] if evento else [],
        ator_id=atendente_id,
        acao="RESPONDER_CRITERIOS",
        ip=ip,
        auditoria_antes={"respostas": respostas_antes},
        auditoria_depois={"respostas": {str(c): v for c, v in novas}},
    )


def registrar_presenca_do_agendamento(
    session: Session,
    s: Solicitacao,
    a: Agendamento,
    compareceu: bool,
    *,
    agora: datetime,
    atendente_id: UUID,
    ip: str | None,
) -> None:
    """UC-008. Compareceu: a partir do início da vaga, REALIZADO e solicitação ATENDIDA.
    Faltou: só depois da tolerância (RN-013), FALTOU e solicitação no fim da fila (RN-014)."""
    inicio, tolerancia = session.execute(
        select(Vaga.inicio, Fila.tolerancia_atraso_min)
        .join(Agenda, Agenda.id == Vaga.agenda_id)
        .join(Fila, Fila.id == Agenda.fila_id)
        .where(Vaga.id == a.vaga_id)
    ).one()
    novo = registrar_presenca(para_dominio_agendamento(a), compareceu, inicio, tolerancia, agora)
    if compareceu:
        nova, evento = registrar_atendimento(para_dominio(s), agora)
        eventos, acao, outbox = [evento], "REGISTRAR_COMPARECIMENTO", "ATENDIMENTO_REGISTRADO"
    else:
        nova, eventos = registrar_falta(para_dominio(s), agora)
        acao, outbox = "REGISTRAR_FALTA", "FALTA_REGISTRADA"
    aplicar_agendamento(session, a, novo, ator_id=atendente_id, acao=acao, ip=ip)
    gravar_transicao(
        session,
        s,
        nova,
        eventos,
        ator_id=atendente_id,
        acao=acao,
        ip=ip,
        evento_outbox=outbox,
        agendamento_id=a.id,
    )
