from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.main import app
from app.dominio.erros import TransicaoInvalida

router = APIRouter(prefix="/_teste")


class Entrada(BaseModel):
    idade: int


@router.post("/validacao")
def _validacao(entrada: Entrada) -> dict[str, int]:
    return {"idade": entrada.idade}


@router.post("/transicao")
def _transicao() -> None:
    raise TransicaoInvalida("A proposta já foi respondida.")


@router.get("/inesperado")
def _inesperado() -> None:
    raise RuntimeError("cpf=52998224725")


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


def test_erro_inesperado_responde_500_sem_detalhe():
    resposta = client.get("/_teste/inesperado")

    assert resposta.status_code == 500
    assert resposta.headers["content-type"] == "application/problem+json"
    assert "52998224725" not in resposta.text
