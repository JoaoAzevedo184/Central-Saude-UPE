"""Histórico SINTÉTICO de N semanas para a demonstração (`seed --historico`).

Em vez de gravar estados prontos, o simulador avança um relógio de 2 em 2 horas e usa o mesmo
código da API e do Worker: os jobs `gerar_vagas`, `propor_vagas` e `expirar_propostas` e as
funções de `infra.transicoes`. Por isso toda linha respeita a ordem da fila, os prazos e os
índices do banco. Os sorteios usam semente fixa: o histórico é muito parecido a cada carga,
mas não idêntico, porque os desempates dos jobs usam UUIDs.

Nada aqui envia aviso: os pacientes sintéticos não têm e-mail e nenhum job de aviso roda. Quem
chama marca a outbox como processada antes do commit (ver `seed.py`). Não faz commit.

A auditoria das transições leva o horário da carga (`auditoria` é append-only e usa `now()`);
linha do tempo, agendamentos e solicitações levam o horário simulado.
"""

import hashlib
import heapq
import logging
import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Uuid, event, exists, insert, inspect, select, text, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.acesso import verificar_atribuicao_de_unidades
from app.dominio.cadastro import cpf_com_digitos
from app.dominio.erros import ErroDeDominio
from app.dominio.vocabulario import MOTIVOS_CANCELAMENTO
from app.infra.agendamentos import ATIVOS, travar_agendamento
from app.infra.modelos import (
    Agenda,
    Agendamento,
    Consentimento,
    CriterioFila,
    Fila,
    Paciente,
    Solicitacao,
    Unidade,
    Usuario,
    Vaga,
    usuario_fila,
)
from app.infra.relogio import RelogioFixo
from app.infra.transicoes import (
    cancelar_do_paciente,
    classificar_na_fila,
    confirmar_do_paciente,
    criar_solicitacao,
    motivo_de_inelegibilidade,
    recusar_do_paciente,
    registrar_presenca_do_agendamento,
    responder_criterios_da_equipe,
)
from app.worker import jobs

logger = logging.getLogger(__name__)

SEMENTE = 20261019
PASSO = timedelta(hours=2)  # o Worker real roda a cada minuto; 2 horas bastam para um histórico
MIN_SEMANAS, MAX_SEMANAS = 2, 26

# CPFs sintéticos do seed: 9 primeiros dígitos nestas faixas. É assim que se reconhece um
# paciente que NÃO é do seed (cadastro feito pelo site).
BASE_CPF_POOL = 900_000_000  # + índice, até 99 999
BASE_CPF_APRESENTACAO = 910_000_000  # + 1 e + 2
CPF_MARIA = "12345678909"  # paciente do seed de desenvolvimento (123456789)


def cpf_do_pool(indice: int) -> str:
    return cpf_com_digitos(str(BASE_CPF_POOL + indice))


def cpf_de_apresentacao(numero: int) -> str:
    return cpf_com_digitos(str(BASE_CPF_APRESENTACAO + numero))


def cpf_e_do_seed(cpf: str) -> bool:
    if cpf == CPF_MARIA:
        return True
    base = int(cpf[:9]) if cpf[:9].isdigit() else -1
    no_pool = BASE_CPF_POOL < base < BASE_CPF_POOL + 100_000
    na_apresentacao = base in (BASE_CPF_APRESENTACAO + 1, BASE_CPF_APRESENTACAO + 2)
    return (no_pool or na_apresentacao) and cpf == cpf_com_digitos(cpf[:9])


# Procura de cada fila em múltiplos da capacidade semanal de vagas. Acima de 1, sobra fila: com o
# horizonte de 30 dias de vagas já reservado, quem espera mais de ~4 semanas de capacidade fica
# na fila (é isso que dá espera de semanas). Fins de semana valem 30% da procura de um dia útil.
DEMANDA = {
    "Laqueadura tubária": 1.35,
    "Mamografia": 1.3,
    "Cardiologia — anticoagulação": 1.3,
    "Dermatologia clínica": 1.3,
    "Dermatologia cirúrgica": 1.35,
}
DIAS_UTEIS_EQUIVALENTES = 5 + 2 * 0.3  # uma semana de chegadas, em dias úteis
# A simulação começa com a fila já formada: 48 dias de chegadas, sem vagas, e mais 7 dias com os
# jobs rodando, para que as vagas da primeira semana do período já estejam reservadas.
PRE_PERIODO = timedelta(days=48)
RAMPA = timedelta(days=7)
P_CONFIRMA, P_RECUSA = 0.62, 0.15  # o resto ignora a proposta, que expira
P_COMPARECE = 0.85
P_DESISTE_NA_FILA = 0.22  # quem espera semanas desiste de parte dos pedidos
P_CANCELA_CONFIRMADA = 0.06
P_VERMELHO, P_AMARELO = 0.04, 0.10
VAGAS_ABERTAS_NO_FIM = 8  # desistências de cardiologia que liberam vaga para o roteiro final
ULTIMO_LOTE = {"VERMELHO": 3, "AMARELO": 2}  # por fila, 2 h antes do fim (`_ultimo_lote`)
PRIMEIROS_NOMES = (
    "Ana", "Bruno", "Carla", "Davi", "Elisa", "Fábio", "Gabriela", "Hugo", "Iara", "João",
    "Karina", "Lucas", "Marta", "Nelson", "Olívia", "Paulo", "Quitéria", "Rafael", "Sara",
    "Tiago", "Úrsula", "Vítor", "Wanda", "Xavier", "Yara", "Zeca",
)  # fmt: skip
MUNICIPIOS = ("Recife", "Olinda", "Jaboatão dos Guararapes", "Paulista", "Camaragibe")

EMAIL_ATENDENTES = {
    "CISAM": "atendente.cisam@exemplo.com",
    "HUOC": "atendente.huoc@exemplo.com",
    "PROCAPE": "atendente.procape@exemplo.com",
}


@dataclass
class Conta:
    """Conta criada nesta carga; `identificador` é o e-mail ou o CPF de login."""

    identificador: str
    papel: str
    usuario: Usuario
    apresentacao: bool = False


@dataclass
class Resultado:
    contas: list[Conta] = field(default_factory=list)
    solicitacoes: int = 0
    pacientes: int = 0
    ignoradas: int = 0


class IdsDaSemente:
    """UUIDs das linhas que o seed cria, tirados de um `random.Random` da semente.

    Os desempates do sistema (`ordem_da_fila`, `Vaga.inicio, Vaga.id`, `Agendamento.id`) acabam
    no id; com `gen_random_uuid()` cada carga desempataria de um jeito. Aqui só entram as sessões
    do seed (`anexar`); a geração de id do resto do sistema não muda. Só as linhas ORM recebem id
    pelo sorteio; as vagas, inseridas em lote pelo job, são renomeadas por `fixar_vagas`."""

    def __init__(self) -> None:
        self.rng = random.Random(SEMENTE ^ 0x1D5)
        self.vagas: set[UUID] = set()

    def anexar(self, session: Session) -> Callable[[], None]:
        """Liga o sorteio à sessão; devolve a função que desliga."""
        event.listen(session, "before_flush", self._atribuir)
        return lambda: event.remove(session, "before_flush", self._atribuir)

    def _atribuir(self, session: Session, _contexto: Any, _instancias: Any) -> None:
        # `session.new` é um conjunto: sem ordenar, a ordem dos ids seguiria o endereço dos objetos.
        for obj in sorted(session.new, key=lambda o: inspect(o).insert_order):
            chave = inspect(obj).mapper.primary_key
            uuid_simples = len(chave) == 1 and chave[0].name == "id"
            if uuid_simples and isinstance(chave[0].type, Uuid) and obj.id is None:
                obj.id = UUID(int=self.rng.getrandbits(128), version=4)

    def fixar_vagas(self, session: Session) -> None:
        """Dá às vagas novas um id que depende só de (agenda, início). Elas ainda não têm
        agendamento, então nenhuma chave estrangeira aponta para o id antigo."""
        todas = set(session.scalars(select(Vaga.id)))
        novas = todas - self.vagas
        if novas:
            linhas = session.execute(
                select(Vaga.id, Vaga.agenda_id, Vaga.inicio).where(
                    Vaga.id.in_(novas), ~exists().where(Agendamento.vaga_id == Vaga.id)
                )
            ).all()
            renomear = []
            for antigo, agenda_id, inicio in linhas:
                resumo = hashlib.sha256(f"{SEMENTE}|{agenda_id}|{inicio.isoformat()}".encode())
                renomear.append(
                    {"antigo": antigo, "novo": UUID(bytes=resumo.digest()[:16], version=4)}
                )
            session.execute(text("UPDATE vaga SET id = :novo WHERE id = :antigo"), renomear)
            todas = (todas - novas) | {r["novo"] for r in renomear}
        self.vagas = todas


def _poisson(rng: random.Random, media: float) -> int:
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


class Simulacao:
    def __init__(
        self,
        session: Session,
        fim: datetime,
        semanas: int,
        novo_hash: Callable[[], str],
        ids: IdsDaSemente,
    ) -> None:
        self.session = session
        self.ids = ids
        self.fim = fim
        self.inicio = fim - timedelta(weeks=semanas)
        self.semanas = semanas
        self.novo_hash = novo_hash
        self.rng = random.Random(SEMENTE)
        self.relogio = RelogioFixo(self.inicio)
        self.cfg = get_settings()
        self.fuso = ZoneInfo(self.cfg.timezone_exibicao)
        self.resultado = Resultado()
        self.agenda: list[tuple[datetime, int, str, tuple]] = []  # heap de ações futuras
        self.seq = 0
        self.passos = 0
        self.sujo = True  # houve mudança que pode abrir vaga ou fila: vale rodar o matching
        self.dia_das_vagas: date | None = None
        self.roteiro: dict[str, UUID] = {}  # a1, a2, b1, b2 -> paciente
        self.atendentes: dict[UUID, UUID] = {}  # fila -> atendente
        self.criterios: dict[UUID, list[CriterioFila]] = {}
        self.pool: list[Paciente] = []
        self.ritmo: dict[str, float] = {}

    # --- preparo --------------------------------------------------------------------------

    def preparar(self) -> None:
        s = self.session
        self.filas = list(
            s.scalars(
                select(Fila)
                .join(Unidade, Unidade.id == Fila.unidade_id)
                .where(Fila.nome.in_(DEMANDA))
                .order_by(Fila.nome)
            )
        )
        if len(self.filas) != len(DEMANDA):
            raise RuntimeError("as filas do seed não existem; rode o seed sem --historico antes")
        self.fila_por_nome = {f.nome: f for f in self.filas}
        for f in self.filas:
            self.criterios[f.id] = list(
                s.scalars(
                    select(CriterioFila).where(CriterioFila.fila_id == f.id, CriterioFila.ativo)
                )
            )
        # As agendas do seed de desenvolvimento começam hoje; o histórico precisa de vagas antes.
        s.execute(
            update(Agenda)
            .where(Agenda.fila_id.in_([f.id for f in self.filas]))
            .values(vigencia_inicio=(self.inicio - RAMPA).astimezone(self.fuso).date())
        )
        self.ritmo = self._ritmo()
        self._equipe()
        self._pacientes()

    def _ritmo(self) -> dict[str, float]:
        """Chegadas por dia útil de cada fila: `DEMANDA` vezes as vagas de uma semana."""
        ritmo = {}
        for f in self.filas:
            vagas = 0
            for a in self.session.scalars(select(Agenda).where(Agenda.fila_id == f.id)):
                minutos = (a.hora_fim.hour - a.hora_inicio.hour) * 60 + (
                    a.hora_fim.minute - a.hora_inicio.minute
                )
                vagas += len(a.dias_semana) * (minutos // a.duracao_min)
            ritmo[f.nome] = DEMANDA[f.nome] * vagas / DIAS_UTEIS_EQUIVALENTES
        return ritmo

    def _equipe(self) -> None:
        s = self.session
        for sigla, email in EMAIL_ATENDENTES.items():
            u = s.scalar(select(Usuario).where(Usuario.email == email))
            filas = [
                f
                for f in self.filas
                if s.scalar(select(Unidade.sigla).where(Unidade.id == f.unidade_id)) == sigla
            ]
            if u is None:
                u = Usuario(email=email, senha_hash=self.novo_hash(), papel="ATENDENTE")
                s.add(u)
                s.flush()
                s.execute(
                    insert(usuario_fila),
                    [{"usuario_id": u.id, "fila_id": f.id} for f in filas],
                )
                self.resultado.contas.append(Conta(email, "ATENDENTE", u))
            for f in filas:
                self.atendentes[f.id] = u.id

        self._gestor_da_central()

    def _gestor_da_central(self) -> None:
        """Gestor sem unidade: vê a central inteira (ADR-025). A regra do domínio exige a
        confirmação explícita; o seed a dá."""
        email = "gestor.central@exemplo.com"
        verificar_atribuicao_de_unidades("GESTOR", frozenset(), confirmar_visao_central=True)
        if self.session.scalar(select(Usuario).where(Usuario.email == email)) is None:
            u = Usuario(email=email, senha_hash=self.novo_hash(), papel="GESTOR")
            self.session.add(u)
            self.session.flush()
            self.resultado.contas.append(Conta(email, "GESTOR", u))

    def _novo_paciente(self, indice_cpf: str, nome: str, sexo: str, idade: int, **extra: Any):
        s = self.session
        u = Usuario(email=None, senha_hash=self.hash_pacientes, papel="PACIENTE")
        s.add(u)
        s.flush()
        hoje = self.inicio.astimezone(self.fuso).date()
        p = Paciente(
            usuario_id=u.id,
            nome=nome,
            cpf=indice_cpf,
            data_nascimento=date(
                hoje.year - idade, 1 + self.rng.randrange(12), 1 + self.rng.randrange(28)
            ),
            sexo=sexo,
            municipio=self.rng.choice(MUNICIPIOS),
            **extra,
        )
        s.add(p)
        s.flush()
        s.add(
            Consentimento(
                paciente_id=p.id,
                finalidade="AGENDAMENTO",
                versao_termo=self.cfg.termo_versao_atual,
                concedido_em=self.inicio - RAMPA - PRE_PERIODO,
            )
        )
        self.resultado.pacientes += 1
        return u, p

    def _pacientes(self) -> None:
        # Ninguém conhece a senha dos pacientes sintéticos; um hash só serve a todos (e é rápido).
        # Os de apresentação ganham senha temporária própria depois, em `executar_seed`.
        self.hash_pacientes = self.novo_hash()
        n = max(120, 80 * (self.semanas + PRE_PERIODO.days // 7 + 1))
        for i in range(1, n + 1):
            sexo = "FEMININO" if self.rng.random() < 0.65 else "MASCULINO"
            nome = f"{self.rng.choice(PRIMEIROS_NOMES)} Exemplo {i:03d}"
            _, p = self._novo_paciente(cpf_do_pool(i), nome, sexo, self.rng.randint(30, 70))
            self.pool.append(p)
        for numero, nome, idade in (
            (1, "Paciente Demonstração Um", 63),
            (2, "Paciente Demonstração Dois", 45),
        ):
            u, p = self._novo_paciente(cpf_de_apresentacao(numero), nome, "FEMININO", idade)
            self.roteiro[f"paciente{numero}"] = p.id
            self.resultado.contas.append(Conta(p.cpf, "PACIENTE", u, apresentacao=True))
        self.pessoa = {k: self.session.get(Paciente, v) for k, v in self.roteiro.items()}

    # --- agenda de ações ------------------------------------------------------------------

    def _agendar(self, quando: datetime, tipo: str, *args: Any) -> None:
        self.seq += 1
        heapq.heappush(self.agenda, (quando, self.seq, tipo, args))

    def _executar_vencidas(self, ate: datetime) -> None:
        while self.agenda and self.agenda[0][0] <= ate:
            quando, _, tipo, args = heapq.heappop(self.agenda)
            self.relogio.instante = max(self.relogio.instante, quando)
            try:
                with self.session.begin_nested():
                    getattr(self, f"_acao_{tipo}")(*args)
                self.sujo = True  # pode ter devolvido uma vaga ou uma pessoa à fila
            except ErroDeDominio:
                self.resultado.ignoradas += (
                    1  # o estado mudou no meio-tempo: o paciente perdeu o prazo
                )

    # --- chegada e classificação ----------------------------------------------------------

    def _respostas_do_paciente(self, fila: Fila) -> list[tuple[UUID, Any]]:
        saida: list[tuple[UUID, Any]] = []
        for c in self.criterios[fila.id]:
            if c.origem != "PACIENTE":
                continue
            if c.tipo == "SIM_NAO":
                # A maioria responde igual: a nota empata e o desempate é a chegada. Com uma nota
                # diferente por paciente, só os de nota alta seriam atendidos e a mediana de
                # espera ficaria em poucos dias, com a fila crescendo.
                saida.append(
                    (c.id, self.rng.random() < (0.9 if c.codigo == "USA_ANTICOAGULANTE" else 0.1))
                )
            elif c.tipo == "NUMERO":
                saida.append((c.id, self.rng.choice((1, 2, 2, 2, 3, 3, 3, 4))))
            else:
                saida.append((c.id, self.rng.choice(sorted(c.parametros["opcoes"]))))
        return saida

    def _nova_solicitacao(self, fila: Fila, paciente: Paciente | None = None, **roteiro: Any):
        t = self.relogio.agora()
        hoje = t.astimezone(self.fuso).date()
        candidatos = [paciente] if paciente else self.rng.sample(self.pool, k=len(self.pool))
        for p in candidatos:
            if motivo_de_inelegibilidade(p, fila, hoje):
                continue
            respostas = self._respostas_do_paciente(fila)
            if roteiro.get("anticoagulante"):
                respostas = [
                    (c, True if c in self._ids(fila, "USA_ANTICOAGULANTE") else v)
                    for c, v in respostas
                ]
            try:
                with self.session.begin_nested():
                    s = criar_solicitacao(
                        self.session,
                        p,
                        fila.id,
                        respostas,
                        turno_preferido="QUALQUER",
                        origem_encaminhamento="USF Sintética",
                        agora=t,
                        hoje=hoje,
                        ip=None,
                    )
            except ErroDeDominio:  # já tem solicitação ativa nesta fila: tenta outro paciente
                continue
            self.resultado.solicitacoes += 1
            r = self.rng.random()
            risco = roteiro.get("risco") or (
                "VERMELHO"
                if r < P_VERMELHO
                else "AMARELO"
                if r < P_VERMELHO + P_AMARELO
                else "VERDE"
            )
            # quem chega nas últimas horas é classificado antes do fim: sem pendência na fila final
            ate_o_fim = int((self.fim - t).total_seconds() // 3600) - 1
            espera = roteiro.get("classificar_em") or timedelta(
                hours=self.rng.randint(1, max(1, min(30, ate_o_fim)))
            )
            self._agendar(t + espera, "classificar", s.id, risco)
            if "cancelar_em" in roteiro:
                self._agendar(t + roteiro["cancelar_em"], "cancelar", s.id, "CONFLITO_DE_HORARIO")
            elif not paciente and self.rng.random() < P_DESISTE_NA_FILA:
                motivo = self.rng.choice(sorted(MOTIVOS_CANCELAMENTO))
                self._agendar(t + timedelta(days=self.rng.randint(1, 20)), "cancelar", s.id, motivo)
            return s
        return None

    def _ids(self, fila: Fila, codigo: str) -> set[UUID]:
        return {c.id for c in self.criterios[fila.id] if c.codigo == codigo}

    def _acao_classificar(self, solicitacao_id: UUID, risco: str) -> None:
        s = self._travar(solicitacao_id)
        if s.status != "EM_ANALISE":
            return
        p = self.session.get(Paciente, s.paciente_id)
        t = self.relogio.agora()
        idade = (t.astimezone(self.fuso).date() - p.data_nascimento).days // 365
        valores = {"IDADE": idade, "PRIORIDADE_LEGAL_60": idade >= 60}
        regulacao = [
            (c.id, valores[c.codigo])
            for c in self.criterios[s.fila_id]
            if c.origem == "REGULACAO" and c.codigo in valores
        ]
        atendente = self.atendentes[s.fila_id]
        if regulacao:
            responder_criterios_da_equipe(
                self.session, s, regulacao, agora=t, atendente_id=atendente, ip=None
            )
        classificar_na_fila(self.session, s, risco, None, agora=t, atendente_id=atendente, ip=None)

    def _travar(self, solicitacao_id: UUID) -> Solicitacao:
        return self.session.scalar(
            select(Solicitacao)
            .where(Solicitacao.id == solicitacao_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    # --- respostas do paciente e da equipe ------------------------------------------------

    def _acao_cancelar(self, solicitacao_id: UUID, motivo: str) -> None:
        s = self._travar(solicitacao_id)
        ativo = self.session.execute(
            select(Agendamento, Vaga.inicio)
            .join(Vaga, Vaga.id == Agendamento.vaga_id)
            .where(Agendamento.solicitacao_id == s.id, Agendamento.status.in_(ATIVOS))
            .with_for_update(of=Agendamento)
            .execution_options(populate_existing=True)
        ).one_or_none()
        usuario_id = self.session.scalar(
            select(Paciente.usuario_id).where(Paciente.id == s.paciente_id)
        )
        cancelar_do_paciente(
            self.session,
            s,
            tuple(ativo) if ativo else None,
            motivo,
            agora=self.relogio.agora(),
            usuario_id=usuario_id,
            ip=None,
        )

    def _acao_responder(self, agendamento_id: UUID, confirma: bool) -> None:
        par = travar_agendamento(self.session, agendamento_id)
        s, a = par
        usuario_id = self.session.scalar(
            select(Paciente.usuario_id).where(Paciente.id == s.paciente_id)
        )
        t = self.relogio.agora()
        if not confirma:
            recusar_do_paciente(self.session, s, a, agora=t, usuario_id=usuario_id, ip=None)
            return
        confirmar_do_paciente(self.session, s, a, agora=t, usuario_id=usuario_id, ip=None)
        inicio, tolerancia = self.session.execute(
            select(Vaga.inicio, Fila.tolerancia_atraso_min)
            .join(Agenda, Agenda.id == Vaga.agenda_id)
            .join(Fila, Fila.id == Agenda.fila_id)
            .where(Vaga.id == a.vaga_id)
        ).one()
        roteirizado = s.paciente_id in self.roteiro.values()
        compareceu = True if roteirizado else self.rng.random() < P_COMPARECE
        self._agendar(
            inicio + timedelta(minutes=tolerancia + self.rng.randint(5, 120)),
            "presenca",
            a.id,
            compareceu,
        )
        if not roteirizado and self.rng.random() < P_CANCELA_CONFIRMADA:
            horas = (inicio - t).total_seconds() / 3600
            if horas > 6:
                motivo = self.rng.choice(sorted(MOTIVOS_CANCELAMENTO))
                self._agendar(
                    t + timedelta(hours=self.rng.uniform(1, horas - 3)), "cancelar", s.id, motivo
                )

    def _acao_presenca(self, agendamento_id: UUID, compareceu: bool) -> None:
        s, a = travar_agendamento(self.session, agendamento_id)
        registrar_presenca_do_agendamento(
            self.session,
            s,
            a,
            compareceu,
            agora=self.relogio.agora(),
            atendente_id=self.atendentes[s.fila_id],
            ip=None,
        )

    def _decidir_propostas(self) -> None:
        novas = self.session.execute(
            select(Agendamento, Solicitacao.paciente_id)
            .join(Solicitacao, Solicitacao.id == Agendamento.solicitacao_id)
            .join(Vaga, Vaga.id == Agendamento.vaga_id)
            .join(Agenda, Agenda.id == Vaga.agenda_id)
            .join(Fila, Fila.id == Agenda.fila_id)
            .where(
                Agendamento.status == "PROPOSTO", Agendamento.proposto_em == self.relogio.agora()
            )
            .order_by(
                Vaga.inicio, Fila.nome
            )  # os UUIDs mudam a cada carga: não servem de desempate
        ).all()
        for a, paciente_id in novas:
            prazo = (a.expira_em - a.proposto_em).total_seconds() / 3600
            if paciente_id == self.roteiro["paciente1"] and self._demo_1_aberta:
                continue  # proposta aberta de apresentação: fica sem resposta
            if paciente_id in (self.roteiro["paciente1"], self.roteiro["paciente2"]):
                if paciente_id == self.roteiro["paciente2"] and self._demo_2_cancela:
                    continue  # o pedido será cancelado; a proposta não é respondida
                self._agendar(a.proposto_em + timedelta(hours=1), "responder", a.id, True)
                continue
            r = self.rng.random()
            if r >= P_CONFIRMA + P_RECUSA:
                continue  # ignora: expira sozinha
            atraso = timedelta(hours=prazo * self.rng.uniform(0.05, 0.8))
            self._agendar(a.proposto_em + atraso, "responder", a.id, r < P_CONFIRMA)

    # --- laço principal -------------------------------------------------------------------

    def _chegadas(self, t: datetime) -> None:
        local = t.astimezone(self.fuso)
        if not 7 <= local.hour < 19 or t > self.fim - timedelta(hours=4):
            return
        fator = 0.3 if local.weekday() >= 5 else 1.0
        for nome, por_dia in self.ritmo.items():
            for _ in range(_poisson(self.rng, por_dia * fator * PASSO.total_seconds() / 3600 / 12)):
                self._nova_solicitacao(self.fila_por_nome[nome])

    def _roteiro(self, t: datetime) -> None:
        """Os dois pacientes de apresentação (ver `rodar`): momentos fixos, contados de trás."""
        cardio = self.fila_por_nome["Cardiologia — anticoagulação"]
        mamo = self.fila_por_nome["Mamografia"]
        um, dois = self.pessoa["paciente1"], self.pessoa["paciente2"]
        marcos = {
            self.inicio + timedelta(days=1): lambda: self._nova_solicitacao(
                cardio, um, risco="VERMELHO", classificar_em=timedelta(hours=1), anticoagulante=True
            ),
            self.inicio + timedelta(days=2): lambda: self._nova_solicitacao(
                mamo, dois, risco="VERDE", cancelar_em=timedelta(days=5)
            ),
            self.fim - timedelta(hours=2): self._fechamento,
            self.fim - timedelta(hours=6): lambda: self._nova_solicitacao(
                cardio,
                dois,
                risco="VERMELHO",
                classificar_em=timedelta(hours=1),
                anticoagulante=True,
            ),
            self.fim - timedelta(hours=4): lambda: self._nova_solicitacao(
                cardio, um, risco="VERMELHO", classificar_em=timedelta(hours=1), anticoagulante=True
            ),
        }
        for marco, acao in marcos.items():
            if t == marco:
                acao()

    def _fechamento(self) -> None:
        self._abrir_vagas_de_cardiologia()
        self._ultimo_lote()

    def _ultimo_lote(self) -> None:
        """Chegadas de última hora. Os casos graves ganham vaga assim que aparece uma; sem este
        lote, a fila do instante da carga nunca teria vermelho nem amarelo. Entram na fila depois
        de o matching da hora passar, então ficam esperando."""
        for fila in self.filas:
            for risco, quantos in ULTIMO_LOTE.items():
                for _ in range(quantos):
                    self._nova_solicitacao(fila, risco=risco, classificar_em=timedelta(hours=1))

    def _abrir_vagas_de_cardiologia(self) -> None:
        """Com a fila funda, o vermelho que chega nas últimas horas só ganha vaga quando alguém
        desiste. Algumas desistências de consulta futura (pela rotina real do paciente) garantem
        as vagas que o roteiro final precisa. Vêm depois de os dois pacientes estarem na fila
        (classificados) e antes do matching da mesma hora, para a vaga ir para eles."""
        cardio = self.fila_por_nome["Cardiologia — anticoagulação"]
        alvos = self.session.execute(
            select(Solicitacao.id)
            .join(Agendamento, Agendamento.solicitacao_id == Solicitacao.id)
            .join(Vaga, Vaga.id == Agendamento.vaga_id)
            .where(
                Solicitacao.fila_id == cardio.id,
                Agendamento.status == "CONFIRMADO",
                Vaga.inicio > self.fim + timedelta(days=1),
                Solicitacao.paciente_id.not_in(self.roteiro.values()),
            )
            .order_by(Vaga.inicio)
            .limit(VAGAS_ABERTAS_NO_FIM)
        ).all()
        for (solicitacao_id,) in alvos:
            try:
                with self.session.begin_nested():
                    self._acao_cancelar(solicitacao_id, "CONFLITO_DE_HORARIO")
            except ErroDeDominio:
                self.resultado.ignoradas += 1
        self.sujo = True

    def _jobs(self, t: datetime) -> bool:
        """Os jobs do Worker, com o relógio simulado e sessões no mesmo SAVEPOINT desta carga.
        O matching só roda quando algo mudou: sem mudança, nenhuma vaga ganha candidato."""
        self.relogio.instante = t
        self.session.flush()

        def fabrica() -> Session:
            sessao = Session(
                bind=self.session.connection(), join_transaction_mode="create_savepoint"
            )
            self.ids.anexar(sessao)
            return sessao

        if jobs.expirar_propostas(fabrica, self.relogio):
            self.sujo = True
        dia = t.astimezone(self.fuso).date()
        if dia != self.dia_das_vagas:
            self.dia_das_vagas = dia
            # Numa transação só o autovacuum não atualiza as estatísticas, e os planos pioram.
            self.session.execute(
                text("ANALYZE vaga, agendamento, solicitacao, historico_solicitacao")
            )
            if jobs.gerar_vagas(fabrica, self.relogio):
                self.sujo = True
            self.ids.fixar_vagas(self.session)
        self.passos += 1
        # a cada 6 horas (a cada passo nas últimas 6, para a demonstração fechar no estado certo)
        propos = self.sujo and (self.passos % 3 == 0 or t >= self.fim - timedelta(hours=6))
        if propos:
            jobs.propor_vagas(fabrica, self.relogio)
            self.sujo = False
        self.session.expire_all()
        return propos

    def rodar(self) -> Resultado:
        """Do início ao fim, de hora em hora. Roteiro dos pacientes de apresentação:
        o 1 usa a cardiologia no 2º dia (confirma e comparece) e de novo nas últimas horas
        (proposta aberta); o 2 pede mamografia no 3º dia e cancela, e nas últimas horas pede
        cardiologia e confirma uma consulta futura."""
        self._demo_1_aberta = False
        self._demo_2_cancela = False
        antes = logging.getLogger("app.worker.jobs").level
        logging.getLogger("app.worker.jobs").setLevel(logging.WARNING)
        try:
            self._rodar()
        finally:
            logging.getLogger("app.worker.jobs").setLevel(antes)
        return self.resultado

    def _rodar(self) -> None:
        # antes do período só há chegadas e classificações: a fila já existe quando as vagas abrem
        t = self.inicio - RAMPA - PRE_PERIODO
        while t < self.inicio - RAMPA:
            self.relogio.instante = t
            self._executar_vencidas(t)
            self._chegadas(t)
            t += PASSO
        t = self.inicio - RAMPA
        while t <= self.fim:
            self._executar_vencidas(t)
            self.relogio.instante = max(self.relogio.instante, t)
            self._demo_1_aberta = t >= self.fim - timedelta(hours=4)
            self._demo_2_cancela = t < self.inicio + timedelta(days=9)
            self._roteiro(t)
            self._chegadas(t)
            if self._jobs(t):
                self._decidir_propostas()
            t += PASSO
        self._executar_vencidas(self.fim)
        self._conferir_roteiro()

    def _conferir_roteiro(self) -> None:
        """A demonstração depende destes quatro estados; sem eles a carga falha em vez de mentir."""
        s = self.session
        um, dois = self.roteiro["paciente1"], self.roteiro["paciente2"]

        def tem(paciente: UUID, *filtros: Any) -> bool:
            return (
                s.scalar(
                    select(Agendamento.id)
                    .join(Solicitacao, Solicitacao.id == Agendamento.solicitacao_id)
                    .where(Solicitacao.paciente_id == paciente, *filtros)
                    .limit(1)
                )
                is not None
            )

        agora = self.fim
        falhas = []
        if not tem(um, Agendamento.status == "REALIZADO"):
            falhas.append("paciente 1 sem consulta realizada")
        if not tem(um, Agendamento.status == "PROPOSTO", Agendamento.expira_em > agora):
            falhas.append("paciente 1 sem proposta aberta")
        if not tem(
            dois,
            Agendamento.status == "CONFIRMADO",
            Vaga.inicio > agora,
            Vaga.id == Agendamento.vaga_id,
        ):
            falhas.append("paciente 2 sem consulta futura")
        cancelado = s.scalar(
            select(Solicitacao.id)
            .where(Solicitacao.paciente_id == dois, Solicitacao.status == "CANCELADA")
            .limit(1)
        )
        if cancelado is None:
            falhas.append("paciente 2 sem pedido cancelado")
        if falhas:
            raise RuntimeError("roteiro de apresentação incompleto: " + "; ".join(falhas))


def gerar_historico(
    session: Session,
    fim: datetime,
    semanas: int,
    novo_hash: Callable[[], str],
    ids: IdsDaSemente,
) -> Resultado:
    """Cria pacientes, solicitações e agendamentos de `semanas` semanas até `fim`."""
    sim = Simulacao(session, fim, semanas, novo_hash, ids)
    sim.preparar()
    return sim.rodar()


__all__ = ["Conta", "IdsDaSemente", "Resultado", "cpf_e_do_seed", "gerar_historico"]
