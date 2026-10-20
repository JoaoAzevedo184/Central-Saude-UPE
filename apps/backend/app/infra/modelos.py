"""Modelos SQLAlchemy (docs/architecture/data-model.md).

Convenções: enum como `text` + CHECK; UUID gerado pelo banco (`gen_random_uuid()`);
FK com `ON DELETE RESTRICT`; datas e horas em `timestamptz` (ADR-008).
A fonte de verdade das restrições é a migração; estes modelos a espelham.
"""

from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base

PAPEIS = ("PACIENTE", "ATENDENTE", "GESTOR", "ADMIN")
SITUACOES_USUARIO = ("ATIVO", "SUSPENSO")
SEXOS = ("FEMININO", "MASCULINO")
FINALIDADES_CONSENTIMENTO = ("AGENDAMENTO", "LEMBRETE_EMAIL")
TIPOS_CRITERIO = ("SIM_NAO", "NUMERO", "OPCAO")
ORIGENS_CRITERIO = ("PACIENTE", "REGULACAO", "EQUIPE")
STATUS_VAGA = ("ATIVA", "BLOQUEADA")
RISCOS = ("VERMELHO", "AMARELO", "VERDE")
TURNOS = ("MANHA", "TARDE", "QUALQUER")
STATUS_SOLICITACAO = ("EM_ANALISE", "NA_FILA", "EM_PROPOSTA", "AGENDADA", "ATENDIDA", "CANCELADA")
STATUS_AGENDAMENTO = ("PROPOSTO", "CONFIRMADO", "CANCELADO", "EXPIRADO", "REALIZADO", "FALTOU")
TIPOS_HISTORICO = (
    "CRIADA",
    "CLASSIFICADA",
    "ENTROU_NA_FILA",
    "PROPOSTA_ENVIADA",
    "CONFIRMADA",
    "RECUSADA",
    "PROPOSTA_EXPIRADA",
    "FALTOU",
    "ATENDIDA",
    "CANCELADA",
    "REENTROU_NA_FILA",
    "RECLASSIFICADA",
)
CANAIS = ("IN_APP", "EMAIL")
STATUS_ENVIO = ("PENDENTE", "ENVIADA", "FALHOU")
STATUS_OUTBOX = ("PENDENTE", "PROCESSADO", "FALHOU")
TIPOS_TENTATIVA = ("LOGIN", "REGISTRO")


def em(coluna: str, valores: tuple[str, ...]) -> CheckConstraint:
    """CHECK de enum em coluna text. O nome final segue a convenção: ck_<tabela>_<coluna>."""
    lista = ", ".join(f"'{v}'" for v in valores)
    return CheckConstraint(f"{coluna} IN ({lista})", name=coluna)


def pk_uuid() -> Mapped[UUID]:
    return mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))


def fk(alvo: str, **kwargs: Any) -> Mapped[Any]:
    return mapped_column(ForeignKey(alvo, ondelete="RESTRICT"), **kwargs)


def agora() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        em("papel", PAPEIS),
        em("situacao", SITUACOES_USUARIO),
        # ADR-028: suspenso, nunca apagado; a suspensão guarda quando aconteceu.
        CheckConstraint("situacao = 'ATIVO' OR suspenso_em IS NOT NULL", name="suspensao_datada"),
    )

    id: Mapped[UUID] = pk_uuid()
    # Anulável: o e-mail do paciente é opcional (UC-001); a equipe entra por e-mail.
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    senha_hash: Mapped[str] = mapped_column(Text)
    papel: Mapped[str] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(Text, server_default="ATIVO")
    suspenso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_suspensao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = agora()


class Paciente(Base):
    __tablename__ = "paciente"
    __table_args__ = (
        em("sexo", SEXOS),
        CheckConstraint("cpf ~ '^[0-9]{11}$'", name="cpf_formato"),
    )

    id: Mapped[UUID] = pk_uuid()
    usuario_id: Mapped[UUID] = fk("usuario.id", unique=True)
    nome: Mapped[str] = mapped_column(Text)
    cpf: Mapped[str] = mapped_column(Text, unique=True)
    cns: Mapped[str | None] = mapped_column(Text, unique=True)
    data_nascimento: Mapped[date]
    telefone: Mapped[str | None] = mapped_column(Text)
    # Só para elegibilidade da fila e direcionamento (docs/security/data-protection.md).
    sexo: Mapped[str | None] = mapped_column(Text)
    municipio: Mapped[str | None] = mapped_column(Text)


class Consentimento(Base):
    __tablename__ = "consentimento"
    __table_args__ = (
        em("finalidade", FINALIDADES_CONSENTIMENTO),
        Index(
            "ux_consentimento_vigente",
            "paciente_id",
            "finalidade",
            unique=True,
            postgresql_where=text("revogado_em IS NULL"),
        ),
    )

    id: Mapped[UUID] = pk_uuid()
    paciente_id: Mapped[UUID] = fk("paciente.id")
    finalidade: Mapped[str] = mapped_column(Text)
    versao_termo: Mapped[str] = mapped_column(Text)
    concedido_em: Mapped[datetime] = agora()
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessaoRefresh(Base):
    """Refresh token (ADR-003). Só o hash SHA-256; cada refresh gera um novo na mesma família."""

    __tablename__ = "sessao_refresh"

    id: Mapped[UUID] = pk_uuid()
    usuario_id: Mapped[UUID] = fk("usuario.id", index=True)
    familia_id: Mapped[UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    criado_em: Mapped[datetime] = agora()
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    substituido_por_id: Mapped[UUID | None] = fk("sessao_refresh.id")
    reapresentado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)


class TentativaLogin(Base):
    """Tentativas de login e de registro, para o limite do AM-004. Sem identificador em claro."""

    __tablename__ = "tentativa_login"
    __table_args__ = (
        em("tipo", TIPOS_TENTATIVA),
        CheckConstraint(
            "tipo = 'REGISTRO' OR identificador_hash IS NOT NULL", name="login_identificado"
        ),
        Index(
            "ix_tentativa_login_identificador_hash_ocorrido_em", "identificador_hash", "ocorrido_em"
        ),
        Index("ix_tentativa_login_ip_ocorrido_em", "ip", "ocorrido_em"),
    )

    id: Mapped[UUID] = pk_uuid()
    tipo: Mapped[str] = mapped_column(Text)
    identificador_hash: Mapped[str | None] = mapped_column(Text)  # HMAC-SHA256 do CPF/e-mail
    ip: Mapped[str | None] = mapped_column(INET)
    sucesso: Mapped[bool] = mapped_column(Boolean)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Unidade(Base):
    __tablename__ = "unidade"

    id: Mapped[UUID] = pk_uuid()
    sigla: Mapped[str] = mapped_column(Text, unique=True)
    nome: Mapped[str] = mapped_column(Text)
    endereco: Mapped[str | None] = mapped_column(Text)


class Especialidade(Base):
    __tablename__ = "especialidade"

    id: Mapped[UUID] = pk_uuid()
    nome: Mapped[str] = mapped_column(Text, unique=True)


class Fila(Base):
    """ADR-027: uma especialidade tem várias filas, cada uma com seu protocolo (ADR-024)."""

    __tablename__ = "fila"
    __table_args__ = (
        UniqueConstraint("unidade_id", "nome", name="uq_fila_unidade_nome"),
        em("sexo_elegivel", SEXOS),
        CheckConstraint(
            "idade_minima IS NULL OR idade_maxima IS NULL OR idade_minima <= idade_maxima",
            name="faixa_etaria",
        ),
        CheckConstraint("prazo_confirmacao_horas > 0", name="prazo_confirmacao_positivo"),
        CheckConstraint("tolerancia_atraso_min >= 0", name="tolerancia_nao_negativa"),
    )

    id: Mapped[UUID] = pk_uuid()
    unidade_id: Mapped[UUID] = fk("unidade.id")
    especialidade_id: Mapped[UUID] = fk("especialidade.id")
    nome: Mapped[str] = mapped_column(Text)
    descricao_paciente: Mapped[str] = mapped_column(Text)
    sexo_elegivel: Mapped[str | None] = mapped_column(Text)  # nulo = qualquer
    idade_minima: Mapped[int | None] = mapped_column(SmallInteger)
    idade_maxima: Mapped[int | None] = mapped_column(SmallInteger)
    prazo_confirmacao_horas: Mapped[int] = mapped_column(server_default="48")  # ADR-026
    tolerancia_atraso_min: Mapped[int] = mapped_column(server_default="60")  # ADR-026
    ativa: Mapped[bool] = mapped_column(server_default=text("true"))


class CriterioFila(Base):
    """ADR-024: critério com peso; a nota da solicitação é a soma dos pontos."""

    __tablename__ = "criterio_fila"
    __table_args__ = (
        UniqueConstraint("fila_id", "codigo", name="uq_criterio_fila_codigo"),
        # Alvo da FK composta de resposta_criterio: o critério é da mesma fila da solicitação.
        UniqueConstraint("id", "fila_id", name="uq_criterio_fila_id_fila"),
        em("tipo", TIPOS_CRITERIO),
        em("origem", ORIGENS_CRITERIO),
        CheckConstraint("peso >= 0", name="peso_nao_negativo"),
    )

    id: Mapped[UUID] = pk_uuid()
    fila_id: Mapped[UUID] = fk("fila.id")
    codigo: Mapped[str] = mapped_column(Text)
    descricao: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    peso: Mapped[int]
    parametros: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    origem: Mapped[str] = mapped_column(Text)
    simulado: Mapped[bool] = mapped_column(server_default=text("true"))  # ADR-011
    ativo: Mapped[bool] = mapped_column(server_default=text("true"))


class Agenda(Base):
    __tablename__ = "agenda"
    __table_args__ = (
        CheckConstraint("hora_inicio < hora_fim", name="horario"),
        CheckConstraint("duracao_min > 0", name="duracao_positiva"),
        CheckConstraint("vigencia_fim IS NULL OR vigencia_inicio <= vigencia_fim", name="vigencia"),
    )

    id: Mapped[UUID] = pk_uuid()
    fila_id: Mapped[UUID] = fk("fila.id")
    profissional: Mapped[str] = mapped_column(Text)
    dias_semana: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    hora_inicio: Mapped[time]
    hora_fim: Mapped[time]
    duracao_min: Mapped[int]
    vigencia_inicio: Mapped[date]
    vigencia_fim: Mapped[date | None]
    ativa: Mapped[bool] = mapped_column(server_default=text("true"))


class Vaga(Base):
    """Não tem coluna "ocupada": a ocupação vem do agendamento ativo (ADR-004)."""

    __tablename__ = "vaga"
    __table_args__ = (
        UniqueConstraint("agenda_id", "inicio", name="uq_vaga_agenda_inicio"),
        em("status_admin", STATUS_VAGA),
        CheckConstraint("inicio < fim", name="intervalo"),
    )

    id: Mapped[UUID] = pk_uuid()
    agenda_id: Mapped[UUID] = fk("agenda.id")
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status_admin: Mapped[str] = mapped_column(Text, server_default="ATIVA")


class Solicitacao(Base):
    """A posição na fila não é gravada: é calculada na consulta por `ordenar_fila()`."""

    __tablename__ = "solicitacao"
    __table_args__ = (
        UniqueConstraint("id", "fila_id", name="uq_solicitacao_id_fila"),
        em("classificacao_risco", RISCOS),
        em("turno_preferido", TURNOS),
        em("status", STATUS_SOLICITACAO),
        CheckConstraint(
            "status IN ('EM_ANALISE', 'CANCELADA') OR classificacao_risco IS NOT NULL",
            name="classificada",
        ),
        CheckConstraint(
            "status <> 'NA_FILA' OR data_entrada_fila IS NOT NULL", name="na_fila_com_entrada"
        ),
        Index(
            "ix_solicitacao_fila_ordem",
            "fila_id",
            "data_entrada_fila",
            postgresql_where=text("status = 'NA_FILA'"),
        ),
    )

    id: Mapped[UUID] = pk_uuid()
    paciente_id: Mapped[UUID] = fk("paciente.id")
    fila_id: Mapped[UUID] = fk("fila.id")
    classificacao_risco: Mapped[str | None] = mapped_column(Text)
    turno_preferido: Mapped[str] = mapped_column(Text, server_default="QUALQUER")
    origem_encaminhamento: Mapped[str | None] = mapped_column(Text)
    data_pedido: Mapped[date]
    status: Mapped[str] = mapped_column(Text, server_default="EM_ANALISE")
    nota: Mapped[int] = mapped_column(server_default="0")  # ADR-024
    # Hora de chegada na fila (desempate). Ao reentrar, recebe o horário atual (ADR-026).
    data_entrada_fila: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criada_em: Mapped[datetime] = agora()


class RespostaCriterio(Base):
    __tablename__ = "resposta_criterio"
    __table_args__ = (
        PrimaryKeyConstraint("solicitacao_id", "criterio_id"),
        # Solicitação e critério da mesma fila. Trocar a fila de uma solicitação que já tem
        # respostas é bloqueado (ON UPDATE RESTRICT).
        ForeignKeyConstraint(
            ["solicitacao_id", "fila_id"],
            ["solicitacao.id", "solicitacao.fila_id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["criterio_id", "fila_id"],
            ["criterio_fila.id", "criterio_fila.fila_id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
    )

    solicitacao_id: Mapped[UUID]
    criterio_id: Mapped[UUID]
    fila_id: Mapped[UUID]
    valor: Mapped[Any] = mapped_column(JSONB)
    pontos: Mapped[int]  # calculado por calcular_pontos() ao gravar
    respondido_por_usuario_id: Mapped[UUID | None] = fk("usuario.id")
    respondido_em: Mapped[datetime] = agora()


class HistoricoSolicitacao(Base):
    """Linha do tempo da solicitação. Append-only (gatilho na migração).

    Nunca guarda posição na fila.
    """

    __tablename__ = "historico_solicitacao"
    __table_args__ = (em("tipo", TIPOS_HISTORICO),)

    id: Mapped[UUID] = pk_uuid()
    solicitacao_id: Mapped[UUID] = fk("solicitacao.id", index=True)
    tipo: Mapped[str] = mapped_column(Text)
    status_anterior: Mapped[str | None] = mapped_column(Text)
    status_novo: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str | None] = mapped_column(Text)
    visivel_paciente: Mapped[bool]
    ator_usuario_id: Mapped[UUID | None] = fk("usuario.id")  # nulo = Worker
    ocorrido_em: Mapped[datetime] = agora()


class Agendamento(Base):
    __tablename__ = "agendamento"
    __table_args__ = (
        em("status", STATUS_AGENDAMENTO),
        # RN-001 / ADR-004: a ocupação da vaga é derivada do agendamento ativo.
        Index(
            "ux_agendamento_vaga_ativa",
            "vaga_id",
            unique=True,
            postgresql_where=text("status IN ('PROPOSTO', 'CONFIRMADO')"),
        ),
        # RN-002: no máximo uma proposta ou confirmação ativa por solicitação.
        Index(
            "ux_agendamento_solicitacao_ativa",
            "solicitacao_id",
            unique=True,
            postgresql_where=text("status IN ('PROPOSTO', 'CONFIRMADO')"),
        ),
        Index(
            "ix_agendamento_expiracao",
            "expira_em",
            postgresql_where=text("status = 'PROPOSTO'"),
        ),
        CheckConstraint("expira_em > proposto_em", name="expira_depois_de_propor"),
    )

    id: Mapped[UUID] = pk_uuid()
    solicitacao_id: Mapped[UUID] = fk("solicitacao.id")
    vaga_id: Mapped[UUID] = fk("vaga.id")
    status: Mapped[str] = mapped_column(Text, server_default="PROPOSTO")
    proposto_por_usuario_id: Mapped[UUID | None] = fk("usuario.id")  # nulo = automático
    proposto_em: Mapped[datetime] = agora()
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    respondido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text)


class Notificacao(Base):
    __tablename__ = "notificacao"
    __table_args__ = (em("canal", CANAIS), em("status_envio", STATUS_ENVIO))

    id: Mapped[UUID] = pk_uuid()
    usuario_id: Mapped[UUID] = fk("usuario.id")
    solicitacao_id: Mapped[UUID | None] = fk("solicitacao.id")
    agendamento_id: Mapped[UUID | None] = fk("agendamento.id")
    canal: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text)
    titulo: Mapped[str] = mapped_column(Text)
    corpo: Mapped[str] = mapped_column(Text)
    status_envio: Mapped[str] = mapped_column(Text, server_default="PENDENTE")
    tentativas: Mapped[int] = mapped_column(server_default="0")
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criada_em: Mapped[datetime] = agora()


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        em("status", STATUS_OUTBOX),
        Index(
            "ix_outbox_pendente",
            "proximo_retry_em",
            postgresql_where=text("status = 'PENDENTE'"),
        ),
    )

    id: Mapped[UUID] = pk_uuid()
    tipo_evento: Mapped[str] = mapped_column(Text)
    agregado_tipo: Mapped[str] = mapped_column(Text)
    agregado_id: Mapped[UUID]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default="PENDENTE")
    tentativas: Mapped[int] = mapped_column(server_default="0")
    proximo_retry_em: Mapped[datetime] = agora()
    criado_em: Mapped[datetime] = agora()
    processado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Auditoria(Base):
    """Append-only (gatilho na migração). ADR-028: o ator nunca é apagado, só suspenso."""

    __tablename__ = "auditoria"

    id: Mapped[UUID] = pk_uuid()
    ator_usuario_id: Mapped[UUID | None] = fk("usuario.id")  # nulo = sistema ou Worker
    acao: Mapped[str] = mapped_column(Text)
    entidade: Mapped[str] = mapped_column(Text)
    entidade_id: Mapped[UUID]
    dados_antes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dados_depois: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    ocorrido_em: Mapped[datetime] = agora()


# ADR-025: ATENDENTE vê só as filas atribuídas; GESTOR vê as unidades atribuídas
# (sem linha = central inteira). O papel de quem aparece aqui é conferido pelo domínio.
usuario_fila = Table(
    "usuario_fila",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="RESTRICT"), primary_key=True),
    Column("fila_id", ForeignKey("fila.id", ondelete="RESTRICT"), primary_key=True),
)

usuario_unidade = Table(
    "usuario_unidade",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="RESTRICT"), primary_key=True),
    Column("unidade_id", ForeignKey("unidade.id", ondelete="RESTRICT"), primary_key=True),
)
