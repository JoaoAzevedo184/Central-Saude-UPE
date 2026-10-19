import logging

import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import text

from app.api.main import app
from app.dominio.erros import TransicaoInvalida
from app.infra.db import engine

router = APIRouter(prefix="/_teste")


class Entrada(BaseModel):
    idade: int


@router.post("/validacao")
def _validacao(entrada: Entrada) -> dict[str, int]:
    return {"idade": entrada.idade}


@router.post("/transicao")
def _transicao() -> None:
    raise TransicaoInvalida("A proposta já foi respondida.")


@router.get("/nao-encontrado")
def _nao_encontrado() -> None:
    raise HTTPException(status_code=404, detail="Solicitação não encontrada.")


@router.get("/inesperado")
def _inesperado() -> None:
    raise RuntimeError("cpf=52998224725")


@router.get("/cpf-duplicado")
def _cpf_duplicado() -> None:
    # Sem commit: o rollback ao fechar a conexão não deixa nada no banco de teste.
    with engine.connect() as conexao:
        for email in ("dup-a@exemplo.com", "dup-b@exemplo.com"):
            usuario_id = conexao.execute(
                text(
                    "INSERT INTO usuario (email, senha_hash, papel) "
                    "VALUES (:e, '!', 'PACIENTE') RETURNING id"
                ),
                {"e": email},
            ).scalar_one()
            conexao.execute(
                text(
                    "INSERT INTO paciente (usuario_id, nome, cpf, data_nascimento) "
                    "VALUES (:u, 'Paciente Sintético', '52998224725', '1990-01-01')"
                ),
                {"u": usuario_id},
            )


app.include_router(router)
client = TestClient(app, raise_server_exceptions=False)


def test_validacao_responde_422_sem_ecoar_a_entrada():
    resposta = client.post("/_teste/validacao", json={"idade": "nome-sintetico-xyz"})

    assert resposta.status_code == 422
    assert resposta.headers["content-type"] == "application/problem+json"
    assert resposta.json()["errors"][0]["loc"] == ["body", "idade"]
    assert "nome-sintetico-xyz" not in resposta.text


def test_transicao_invalida_responde_409_com_type_estavel():
    resposta = client.post("/_teste/transicao")

    assert resposta.status_code == 409
    assert resposta.json()["type"] == "/problemas/transicao-invalida"
    assert resposta.json()["detail"] == "A proposta já foi respondida."


def test_erro_inesperado_responde_500_sem_detalhe(caplog):
    with caplog.at_level(logging.ERROR):
        resposta = client.get("/_teste/inesperado")

    assert resposta.status_code == 500
    assert resposta.headers["content-type"] == "application/problem+json"
    assert "52998224725" not in resposta.text
    assert "52998224725" not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.integracao
def test_erro_de_banco_loga_so_tipo_e_sqlstate(banco, caplog):
    # raise_server_exceptions=True: se a exceção escapasse do middleware, o servidor real
    # logaria o traceback com a mensagem do Postgres ("Key (cpf)=(...)").
    with TestClient(app) as c, caplog.at_level(logging.ERROR):
        resposta = c.get("/_teste/cpf-duplicado")

    assert resposta.status_code == 500
    assert "52998224725" not in resposta.text
    assert "52998224725" not in caplog.text
    assert "IntegrityError sqlstate=23505" in caplog.text


@pytest.mark.parametrize(
    ("rota", "metodo", "status"),
    [("/_teste/nao-encontrado", "get", 404), ("/_teste/transicao", "post", 409)],
)
def test_middleware_do_500_nao_captura_http_nem_dominio(caplog, rota, metodo, status):
    # raise_server_exceptions=True: se o erro escapasse até o middleware, viraria 500.
    with TestClient(app) as c, caplog.at_level(logging.ERROR):
        resposta = getattr(c, metodo)(rota)

    assert resposta.status_code == status
    assert resposta.headers["content-type"] == "application/problem+json"
    assert resposta.json()["status"] == status
    assert resposta.json()["detail"]
    assert "erro inesperado" not in caplog.text
