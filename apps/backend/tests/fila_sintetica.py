"""Filas, critérios, pacientes e equipe fictícios para os testes de solicitação e painel."""

from dataclasses import dataclass
from datetime import date, datetime
from itertools import count
from uuid import UUID

from sqlalchemy import insert

from app.config import get_settings
from app.infra.autenticacao import hash_senha
from app.infra.modelos import (
    Consentimento,
    CriterioFila,
    Especialidade,
    Fila,
    Paciente,
    Solicitacao,
    Unidade,
    Usuario,
    usuario_fila,
    usuario_unidade,
)
from tests.sinteticos import cpf

SENHA = "senha-de-teste-123"
CSRF = get_settings().csrf_header_name
_seq = count(1)


@dataclass
class Mundo:
    unidade: UUID
    outra_unidade: UUID
    fila: UUID  # sem restrição; critérios P_FILHOS (PACIENTE) e R_GESTACOES (REGULACAO)
    laqueadura: UUID  # FEMININO, 18+
    mamografia: UUID  # 40 a 69 anos
    fila_outra_unidade: UUID
    p_filhos: UUID
    p_opcao: UUID
    r_gestacoes: UUID
    criterio_outra_fila: UUID


def _fila(sessao, unidade, especialidade, nome, **restricoes) -> UUID:
    fila = Fila(
        unidade_id=unidade,
        especialidade_id=especialidade,
        nome=nome,
        descricao_paciente=f"Fila sintética: {nome}.",
        **restricoes,
    )
    sessao.add(fila)
    sessao.flush()
    return fila.id


def _criterio(sessao, fila, codigo, tipo, peso, origem, parametros=None) -> UUID:
    c = CriterioFila(
        fila_id=fila,
        codigo=codigo,
        descricao=f"Pergunta sintética {codigo}",
        tipo=tipo,
        peso=peso,
        origem=origem,
        parametros=parametros or {},
    )
    sessao.add(c)
    sessao.flush()
    return c.id


def montar_mundo(sessao) -> Mundo:
    u1 = Unidade(sigla="TST1", nome="Unidade Sintética 1")
    u2 = Unidade(sigla="TST2", nome="Unidade Sintética 2")
    esp = Especialidade(nome="Especialidade Sintética")
    sessao.add_all([u1, u2, esp])
    sessao.flush()
    fila = _fila(sessao, u1.id, esp.id, "Geral")
    outra = _fila(sessao, u2.id, esp.id, "Outra unidade")
    return Mundo(
        unidade=u1.id,
        outra_unidade=u2.id,
        fila=fila,
        laqueadura=_fila(
            sessao, u1.id, esp.id, "Laqueadura", sexo_elegivel="FEMININO", idade_minima=18
        ),
        mamografia=_fila(sessao, u1.id, esp.id, "Mamografia", idade_minima=40, idade_maxima=69),
        fila_outra_unidade=outra,
        p_filhos=_criterio(sessao, fila, "P_FILHOS", "SIM_NAO", 10, "PACIENTE"),
        p_opcao=_criterio(
            sessao, fila, "P_OPCAO", "OPCAO", 2, "PACIENTE", {"opcoes": {"A": 1, "B": 3}}
        ),
        r_gestacoes=_criterio(
            sessao,
            fila,
            "R_GESTACOES",
            "NUMERO",
            5,
            "REGULACAO",
            {"faixas": [{"min": 0, "max": 1, "fator": 0}, {"min": 2, "fator": 2}]},
        ),
        criterio_outra_fila=_criterio(sessao, outra, "P_OUTRA", "SIM_NAO", 7, "PACIENTE"),
    )


def criar_paciente(
    sessao,
    nome="Maria Sintética da Silva",
    sexo="FEMININO",
    nascimento=date(1985, 3, 2),
    consentimento=True,
    login=True,
) -> tuple[Usuario, Paciente]:
    """Paciente fictício. `login=False` pula o hash Argon2 (mais rápido)."""
    n = next(_seq)
    usuario = Usuario(
        email=f"paciente{n}@exemplo.com",
        senha_hash=hash_senha(SENHA) if login else "!",
        papel="PACIENTE",
    )
    sessao.add(usuario)
    sessao.flush()
    paciente = Paciente(
        usuario_id=usuario.id,
        nome=nome,
        cpf=cpf(f"{300000000 + n * 7919:09d}"),
        data_nascimento=nascimento,
        sexo=sexo,
    )
    sessao.add(paciente)
    sessao.flush()
    if consentimento:
        sessao.add(
            Consentimento(paciente_id=paciente.id, finalidade="AGENDAMENTO", versao_termo="v1")
        )
        sessao.flush()
    return usuario, paciente


def criar_equipe(sessao, papel, filas=(), unidades=()) -> Usuario:
    usuario = Usuario(
        email=f"{papel.lower()}{next(_seq)}@exemplo.com", senha_hash=hash_senha(SENHA), papel=papel
    )
    sessao.add(usuario)
    sessao.flush()
    for f in filas:
        sessao.execute(insert(usuario_fila).values(usuario_id=usuario.id, fila_id=f))
    for u in unidades:
        sessao.execute(insert(usuario_unidade).values(usuario_id=usuario.id, unidade_id=u))
    return usuario


def na_fila(sessao, fila, risco, nota, entrada: datetime, nome="Paciente Sintético Fila") -> UUID:
    """Solicitação já NA_FILA, gravada direto (sem passar pela API), de um paciente novo."""
    _, paciente = criar_paciente(sessao, nome=nome, login=False)
    s = Solicitacao(
        paciente_id=paciente.id,
        fila_id=fila,
        status="NA_FILA",
        classificacao_risco=risco,
        nota=nota,
        data_entrada_fila=entrada,
        data_pedido=date(2026, 10, 1),
    )
    sessao.add(s)
    sessao.flush()
    return s.id


def entrar(cliente, identificador):
    resposta = cliente.post(
        "/api/v1/auth/login", json={"identificador": identificador, "senha": SENHA}
    )
    assert resposta.status_code == 200, resposta.text
    return cliente


def csrf(cliente):
    return {CSRF: cliente.cookies.get("csrf_token", "")}


def chaves(dado) -> set[str]:
    """Todas as chaves de um JSON, em qualquer nível."""
    if isinstance(dado, dict):
        return set(dado) | {k for v in dado.values() for k in chaves(v)}
    if isinstance(dado, list):
        return {k for v in dado for k in chaves(v)}
    return set()
