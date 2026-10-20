"""Dados SINTÉTICOS para desenvolvimento: `SEED_SENHA=... python -m app.infra.seed`.

Nomes, pesos e critérios são simulados (ADR-011). Idempotente: se as unidades já existem,
não faz nada. Só roda com APP_ENV=development (lista de permissão, não de bloqueio).
Todos os usuários do seed recebem a senha de SEED_SENHA, passada só na linha de comando;
sem ela, uma senha aleatória é gerada e impressa uma vez.
"""

import logging
import os
import secrets
import sys
from datetime import date, time
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dominio.cadastro import cpf_com_digitos as cpf_sintetico
from app.dominio.relogio import Relogio
from app.infra.autenticacao import hash_senha
from app.infra.db import SessionLocal
from app.infra.modelos import (
    Agenda,
    CriterioFila,
    Especialidade,
    Fila,
    Paciente,
    Unidade,
    Usuario,
    usuario_fila,
    usuario_unidade,
)
from app.infra.relogio import RelogioReal
from app.logging import configurar_logging

logger = logging.getLogger(__name__)

__all__ = ["cpf_sintetico", "semear"]


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


def main() -> None:
    settings = get_settings()
    configurar_logging(settings.log_level)
    if settings.app_env != "development":
        sys.exit(f"seed recusado: só roda com APP_ENV=development (atual: {settings.app_env})")
    senha = os.environ.get("SEED_SENHA") or secrets.token_urlsafe(12)
    with SessionLocal() as session:
        criou = semear(session, RelogioReal(), hash_senha(senha))
        session.commit()
    if criou and not os.environ.get("SEED_SENHA"):
        # print, não logger: a senha não vai para logs coletados.
        print(f"seed: SEED_SENHA ausente; senha gerada para todos os usuários: {senha}")
    logger.info("seed: %s", "dados criados" if criou else "já existia, nada feito")


if __name__ == "__main__":
    main()
