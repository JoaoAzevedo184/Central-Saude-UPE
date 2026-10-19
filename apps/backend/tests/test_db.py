import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infra.db import engine


@pytest.mark.integracao
def test_erro_de_sql_nao_expoe_valor_do_parametro():
    valor = "cpf-sintetico-52998224725"

    with engine.connect() as conexao, pytest.raises(DBAPIError) as erro:
        # Tabela inexistente: o erro vem do SQLAlchemy com o SQL, sem o Postgres ecoar o valor.
        conexao.execute(text("SELECT * FROM tabela_inexistente WHERE x = :valor"), {"valor": valor})

    assert engine.hide_parameters
    assert valor not in str(erro.value)
