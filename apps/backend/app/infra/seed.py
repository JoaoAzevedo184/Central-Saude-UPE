"""Dados SINTÉTICOS: `SEED_SENHA=... python -m app.infra.seed [--historico --semanas 8]`.

Nomes, pesos e critérios são simulados (ADR-011). Idempotente: se as unidades já existem, a
estrutura não é refeita; se já há solicitações do seed, o histórico também não.

Ambientes (lista de permissão, não de bloqueio):
- development: todos os usuários recebem a senha de SEED_SENHA, passada só na linha de comando;
  sem ela, uma senha aleatória é gerada e impressa uma vez.
- production (banco de demonstração): exige `DEMO_SEED_PERMITIDO=true` e a flag
  `--confirmo-banco-de-demonstracao`, e recusa se houver paciente que não seja do seed. Ninguém
  fica com senha conhecida: pacientes sintéticos têm senha aleatória nunca impressa; equipe e os
  dois pacientes de apresentação recebem senha temporária, impressa uma vez, com troca obrigatória.
  Conta que já existia nunca tem a senha trocada.
- qualquer outro: recusa.
"""

import argparse
import logging
import os
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dominio.cadastro import cpf_com_digitos as cpf_sintetico
from app.dominio.relogio import Relogio
from app.infra.autenticacao import aplicar_senha_temporaria, hash_senha
from app.infra.db import SessionLocal
from app.infra.modelos import (
    Agenda,
    CriterioFila,
    Especialidade,
    Fila,
    Outbox,
    Paciente,
    Solicitacao,
    Unidade,
    Usuario,
    usuario_fila,
    usuario_unidade,
)
from app.infra.relogio import RelogioReal
from app.infra.seed_historico import (
    CPF_MARIA,
    MAX_SEMANAS,
    MIN_SEMANAS,
    IdsDaSemente,
    cpf_e_do_seed,
    gerar_historico,
)
from app.logging import configurar_logging

logger = logging.getLogger(__name__)

__all__ = ["Opcoes", "SeedRecusado", "cpf_sintetico", "executar_seed", "main", "semear"]


def _faixas(*faixas: tuple[int | None, int | None, int]) -> dict[str, Any]:
    return {
        "faixas": [
            {k: v for k, v in (("min", mn), ("max", mx), ("fator", f)) if v is not None}
            for mn, mx, f in faixas
        ]
    }


# (unidade, especialidade, nome, descrição, sexo, idade mín., critérios)
# critério: (código, descrição, tipo, peso, parâmetros, origem)
FILAS = [
    (
        "CISAM",
        "Ginecologia",
        "Laqueadura tubária",
        "Para mulheres a partir de 18 anos que desejam a laqueadura, com encaminhamento.",
        "FEMININO",
        18,
        [
            (
                "NUM_FILHOS",
                "Número de filhos",
                "NUMERO",
                10,
                _faixas((0, 1, 0), (2, 3, 1), (4, None, 2)),
                "PACIENTE",
            ),
            (
                "IDADE",
                "Idade da paciente",
                "NUMERO",
                5,
                _faixas((18, 29, 0), (30, 39, 1), (40, None, 2)),
                "REGULACAO",
            ),
            (
                "FILHO_NEURODEGENERATIVA",
                "Tem filho com doença neurodegenerativa?",
                "SIM_NAO",
                20,
                {},
                "PACIENTE",
            ),
        ],
    ),
    (
        "CISAM",
        "Mastologia",
        "Mamografia",
        "Exame de rastreamento do câncer de mama para mulheres a partir de 40 anos.",
        "FEMININO",
        40,
        [
            # ADR-030: só a resposta da paciente; nenhum dado dos parentes é guardado.
            (
                "HIST_FAMILIAR_CA_MAMA",
                "Sua mãe ou irmã teve câncer de mama?",
                "SIM_NAO",
                20,
                {},
                "PACIENTE",
            ),
            (
                "IDADE",
                "Idade da paciente",
                "NUMERO",
                5,
                _faixas((40, 49, 1), (50, 69, 2), (70, None, 1)),
                "REGULACAO",
            ),
        ],
    ),
    (
        "PROCAPE",
        "Cardiologia",
        "Cardiologia — anticoagulação",
        "Acompanhamento de pacientes que usam ou vão usar anticoagulante.",
        None,
        None,
        [
            ("USA_ANTICOAGULANTE", "Usa anticoagulante?", "SIM_NAO", 15, {}, "PACIENTE"),
            (
                "PRIORIDADE_LEGAL_60",
                "Prioridade legal: 60 anos ou mais",
                "SIM_NAO",
                10,
                {},
                "REGULACAO",
            ),
        ],
    ),
    (
        "HUOC",
        "Dermatologia",
        "Dermatologia clínica",
        "Consultas para doenças de pele tratadas sem cirurgia.",
        None,
        None,
        [],
    ),
    (
        "HUOC",
        "Dermatologia",
        "Dermatologia cirúrgica",
        "Avaliação para pequenas cirurgias de pele, com encaminhamento do dermatologista.",
        None,
        None,
        [],
    ),
]

# Endereços institucionais públicos das unidades (não são dados pessoais).
UNIDADES = [
    (
        "CISAM",
        "Centro Integrado de Saúde Amaury de Medeiros",
        "Rua Visconde de Mamanguape, s/n, Encruzilhada, Recife - PE",
    ),
    (
        "HUOC",
        "Hospital Universitário Oswaldo Cruz",
        "Rua Arnóbio Marques, 310, Santo Amaro, Recife - PE",
    ),
    (
        "PROCAPE",
        "Pronto-Socorro Cardiológico de Pernambuco",
        "Rua dos Palmares, s/n, Santo Amaro, Recife - PE",
    ),
]

# Uma agenda por fila: (fila, profissional fictício, dias ISO, início, fim, duração em min).
# As vagas saem do job `gerar_vagas` do Worker.
AGENDAS = [
    ("Laqueadura tubária", "Dra. Ana Exemplo", [2, 4], time(8), time(12), 60),
    ("Mamografia", "Dra. Beatriz Exemplo", [1, 3, 5], time(13), time(17), 30),
    ("Cardiologia — anticoagulação", "Dr. Carlos Exemplo", [1, 2, 3, 4, 5], time(8), time(11), 20),
    ("Dermatologia clínica", "Dra. Daniela Exemplo", [2, 3], time(8), time(12), 30),
    ("Dermatologia cirúrgica", "Dr. Eduardo Exemplo", [4], time(13), time(17), 60),
]


def semear(session: Session, relogio: Relogio, senha_hash: str) -> bool:
    """Grava os dados sintéticos. Devolve False se já existiam. Não faz commit."""
    if session.scalar(select(Unidade).where(Unidade.sigla == "CISAM")) is not None:
        return False

    unidades = {
        sigla: Unidade(sigla=sigla, nome=nome, endereco=endereco)
        for sigla, nome, endereco in UNIDADES
    }
    especialidades = {nome: Especialidade(nome=nome) for nome in {f[1] for f in FILAS}}
    session.add_all([*unidades.values(), *especialidades.values()])
    session.flush()

    filas: dict[str, Fila] = {}
    for sigla, especialidade, nome, descricao, sexo, idade_minima, criterios in FILAS:
        fila = Fila(
            unidade_id=unidades[sigla].id,
            especialidade_id=especialidades[especialidade].id,
            nome=nome,
            descricao_paciente=descricao,
            sexo_elegivel=sexo,
            idade_minima=idade_minima,
        )
        session.add(fila)
        session.flush()
        filas[nome] = fila
        session.add_all(
            CriterioFila(
                fila_id=fila.id,
                codigo=codigo,
                descricao=desc,
                tipo=tipo,
                peso=peso,
                parametros=parametros,
                origem=origem,
            )
            for codigo, desc, tipo, peso, parametros, origem in criterios
        )

    hoje = relogio.agora().astimezone(ZoneInfo(get_settings().timezone_exibicao)).date()
    session.add_all(
        Agenda(
            fila_id=filas[fila].id,
            profissional=profissional,
            dias_semana=dias,
            hora_inicio=inicio,
            hora_fim=fim,
            duracao_min=duracao,
            vigencia_inicio=hoje,
        )
        for fila, profissional, dias, inicio, fim, duracao in AGENDAS
    )

    def usuario(email: str, papel: str, **extra: Any) -> Usuario:
        u = Usuario(email=email, senha_hash=senha_hash, papel=papel, **extra)
        session.add(u)
        return u

    admin = usuario("admin@exemplo.com", "ADMIN")
    gestor = usuario("gestor.cisam@exemplo.com", "GESTOR")
    atendente = usuario("atendente.huoc@exemplo.com", "ATENDENTE")
    suspenso = usuario(
        "atendente.suspenso@exemplo.com",
        "ATENDENTE",
        situacao="SUSPENSO",
        suspenso_em=relogio.agora(),
        motivo_suspensao="Férias (dado sintético)",
    )
    paciente = usuario("paciente@exemplo.com", "PACIENTE")
    session.flush()

    session.add(
        Paciente(
            usuario_id=paciente.id,
            nome="Maria Exemplo da Silva",
            cpf=cpf_sintetico("123456789"),
            data_nascimento=date(1980, 5, 17),
            sexo="FEMININO",
            municipio="Olinda",
        )
    )
    session.execute(
        insert(usuario_unidade), [{"usuario_id": gestor.id, "unidade_id": unidades["CISAM"].id}]
    )
    session.execute(
        insert(usuario_fila),
        [
            {"usuario_id": atendente.id, "fila_id": filas["Dermatologia clínica"].id},
            {"usuario_id": atendente.id, "fila_id": filas["Dermatologia cirúrgica"].id},
            {"usuario_id": suspenso.id, "fila_id": filas["Laqueadura tubária"].id},
        ],
    )
    session.flush()
    logger.info("seed: %d filas, usuários admin=%s", len(filas), admin.id)
    return True


SEED_LOCK = 7_300_184_001  # chave do advisory lock que serializa as cargas
EQUIPE_DO_SEED = (
    "admin@exemplo.com",
    "gestor.cisam@exemplo.com",
    "atendente.huoc@exemplo.com",
)  # a conta suspensa não entra: ninguém precisa entrar com ela


class SeedRecusado(Exception):
    """Trava do seed. A mensagem explica o que falta e nunca traz CPF nem senha."""


@dataclass
class Opcoes:
    historico: bool = False
    semanas: int = 8
    confirmo: bool = False


def _recusa_de_ambiente(settings: Settings) -> str | None:
    """Recusas que só dependem do ambiente e da variável (valem antes de ler a linha de comando)."""
    if settings.app_env == "production":
        if not settings.demo_seed_permitido:
            return (
                "seed recusado em production: só roda num banco de demonstração. Defina "
                "DEMO_SEED_PERMITIDO=true no .env e passe --confirmo-banco-de-demonstracao. "
                "Fora da demonstração, o seed só roda com APP_ENV=development."
            )
        return None
    if settings.app_env != "development":
        return f"seed recusado: só roda com APP_ENV=development (atual: {settings.app_env})"
    return None


def _tem_paciente_fora_do_seed(session: Session) -> bool:
    return any(not cpf_e_do_seed(cpf) for cpf in session.scalars(select(Paciente.cpf)))


def _tem_historico(session: Session) -> bool:
    """Há solicitação de paciente do seed? (faixas de CPF do pool, da apresentação e a Maria)"""
    return (
        session.scalar(
            select(Solicitacao.id)
            .join(Paciente, Paciente.id == Solicitacao.paciente_id)
            .where(
                Paciente.cpf.like("9000%")
                | Paciente.cpf.like("9100000%")
                | (Paciente.cpf == CPF_MARIA)
            )
            .limit(1)
        )
        is not None
    )


def executar_seed(
    session: Session,
    settings: Settings,
    relogio: Relogio,
    opcoes: Opcoes,
    escrever: Callable[[str], None],
    senha_dev: str | None = None,
) -> bool:
    """Aplica o seed na sessão, sem commit. Levanta `SeedRecusado` se uma trava barrar.

    Devolve se criou contas com a senha comum de desenvolvimento. Tudo o que é secreto sai por
    `escrever` (stdout), nunca por log nem por auditoria, e só no fim: se a carga falhar, nada
    foi dito."""
    if recusa := _recusa_de_ambiente(settings):
        raise SeedRecusado(recusa)
    producao = settings.app_env == "production"
    # Uma carga por vez. Em production, também bloqueia cadastros novos até o commit: um paciente
    # real que aparecesse no meio da carga entraria no matching com o relógio simulado.
    session.execute(select(func.pg_advisory_xact_lock(SEED_LOCK)))
    if producao:
        session.execute(text("LOCK TABLE paciente IN SHARE ROW EXCLUSIVE MODE"))
        if not opcoes.confirmo:
            raise SeedRecusado(
                "seed recusado em production: falta a flag --confirmo-banco-de-demonstracao."
            )
        if _tem_paciente_fora_do_seed(session):
            raise SeedRecusado(
                "seed recusado em production: o banco tem paciente que não é do seed (cadastro "
                "feito pelo site). Dados de teste não se misturam com cadastros reais."
            )
    if opcoes.historico and not MIN_SEMANAS <= opcoes.semanas <= MAX_SEMANAS:
        raise SeedRecusado(f"--semanas precisa estar entre {MIN_SEMANAS} e {MAX_SEMANAS}.")

    agora = relogio.agora()
    if producao:
        # Ninguém conhece estas senhas: as contas que precisam de login ganham uma temporária.
        def novo_hash() -> str:
            return hash_senha(secrets.token_urlsafe(24))

        senha_hash = novo_hash()
    else:
        senha_hash = hash_senha(senha_dev or secrets.token_urlsafe(12))

        def novo_hash() -> str:
            return senha_hash

    mensagens: list[str] = []
    escrever_depois = mensagens.append
    temporarias: list[tuple[str, str, str]] = []  # (papel, identificador, senha)
    novas_contas = False

    ids = IdsDaSemente()
    soltar_ids = ids.anexar(session) if opcoes.historico else None
    try:
        criou = semear(session, relogio, senha_hash)
        if criou:
            if producao:
                for email in EQUIPE_DO_SEED:
                    u = session.scalar(select(Usuario).where(Usuario.email == email))
                    temporarias.append(
                        (u.papel, email, aplicar_senha_temporaria(session, u, agora))
                    )
                # a paciente do seed de desenvolvimento não recebe aviso por e-mail na demonstração
                session.execute(
                    update(Usuario)
                    .where(Usuario.email == "paciente@exemplo.com")
                    .values(email=None)
                )
            novas_contas = True
            escrever_depois(
                "estrutura criada: unidades, filas, critérios, agendas e contas da equipe"
            )
        else:
            escrever_depois(
                "estrutura e contas da equipe já existiam; nenhuma senha foi trocada "
                "(use redefinir-senha se precisar)"
            )
            if producao:
                escrever_depois(
                    "ATENÇÃO: se este banco veio de um seed de desenvolvimento, as senhas dessas "
                    "contas podem ser conhecidas. Rode redefinir-senha para cada uma antes "
                    "de expor."
                )

        if opcoes.historico:
            if _tem_historico(session):
                escrever_depois("histórico já existia; nada feito (nenhuma senha foi trocada)")
            else:
                resultado = gerar_historico(session, agora, opcoes.semanas, novo_hash, ids)
                for conta in resultado.contas:
                    if producao:
                        senha = aplicar_senha_temporaria(session, conta.usuario, agora)
                        temporarias.append((conta.papel, conta.identificador, senha))
                # O Worker da demonstração nunca vê estes eventos: viram processados na mesma
                # transação. Todo evento criado aqui tem `criado_em` igual ao `now()` da transação.
                session.execute(
                    update(Outbox)
                    .where(Outbox.criado_em == func.now(), Outbox.status == "PENDENTE")
                    .values(status="PROCESSADO", processado_em=func.now())
                )
                escrever_depois(
                    f"histórico de {opcoes.semanas} semanas: {resultado.pacientes} pacientes, "
                    f"{resultado.solicitacoes} solicitações"
                )
                apresentacao = [c.identificador for c in resultado.contas if c.apresentacao]
                escrever_depois(
                    "pacientes de apresentação (entram com o CPF): " + ", ".join(apresentacao)
                )
                if not producao:
                    novas_contas = True
                    escrever_depois("senha dos usuários novos: a mesma dos demais usuários do seed")

        if temporarias:
            escrever_depois(
                "SENHAS TEMPORÁRIAS (aparecem só agora; a troca é obrigatória no primeiro acesso):"
            )
            for papel, identificador, senha in temporarias:
                escrever_depois(f"  {papel:<9} {identificador}  {senha}")

        for linha in mensagens:
            escrever(linha)
        return novas_contas
    finally:
        if soltar_ids:
            soltar_ids()


def main(argv: list[str] | None = None) -> None:
    settings = get_settings()
    configurar_logging(settings.log_level)
    if recusa := _recusa_de_ambiente(settings):
        sys.exit(recusa)
    parser = argparse.ArgumentParser(prog="python -m app.infra.seed", description=__doc__)
    parser.add_argument("--historico", action="store_true", help="gera o histórico sintético")
    parser.add_argument("--semanas", type=int, default=8, help="semanas de histórico (padrão 8)")
    parser.add_argument(
        "--confirmo-banco-de-demonstracao",
        dest="confirmo",
        action="store_true",
        help="exigida em production, junto de DEMO_SEED_PERMITIDO=true",
    )
    args = parser.parse_args(argv)
    senha_dev = os.environ.get("SEED_SENHA") or None
    if settings.app_env == "production" and senha_dev:
        print("seed: SEED_SENHA é ignorada em production.")
    gerada = None
    if settings.app_env == "development" and not senha_dev:
        gerada = senha_dev = secrets.token_urlsafe(12)
    try:
        with SessionLocal() as session:
            novas = executar_seed(
                session,
                settings,
                RelogioReal(),
                Opcoes(args.historico, args.semanas, args.confirmo),
                print,  # print, não logger: senha não vai para logs coletados
                senha_dev,
            )
            session.commit()
    except SeedRecusado as erro:
        sys.exit(str(erro))
    except Exception as erro:
        if settings.app_env != "production":
            raise
        # O erro do banco repete os dados da linha (CPF, nome): em production, só a classe.
        logger.error("seed falhou: %s", type(erro).__name__)
        sys.exit("seed falhou e nada foi gravado; detalhes omitidos para não imprimir dados.")
    if gerada and novas:
        print(f"seed: senha gerada para os usuários novos do desenvolvimento: {gerada}")


if __name__ == "__main__":
    main()
