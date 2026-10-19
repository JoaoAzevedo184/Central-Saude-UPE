import pytest

from app.api.deps import EscopoEquipe, escopo_da_equipe
from app.config import Settings


def test_adr023_padrao_ve_todas_as_unidades():
    escopo = escopo_da_equipe(Settings(escopo_por_unidade=False))

    assert escopo == EscopoEquipe(unidade_ids=None)


def test_adr023_escopo_por_unidade_ainda_nao_implementado():
    with pytest.raises(NotImplementedError, match="ADR-023"):
        escopo_da_equipe(Settings(escopo_por_unidade=True))
