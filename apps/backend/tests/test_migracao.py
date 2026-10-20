import pytest
from alembic import command

from tests.conftest import alembic_config

pytestmark = pytest.mark.integracao


def test_downgrade_e_upgrade_das_migracoes(banco):
    config = alembic_config()
    banco.dispose()

    command.downgrade(config, "0003")
    command.upgrade(config, "head")
    command.downgrade(config, "0002")
    command.upgrade(config, "head")
    command.downgrade(config, "0001")
    command.upgrade(config, "head")


def test_modelos_batem_com_a_migracao(banco):
    # Falha se um modelo mudar sem a migração correspondente (ou vice-versa).
    command.check(alembic_config())
