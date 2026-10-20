"""Acesso da equipe: escopo por fila (ADR-025) e usuário suspenso (ADR-028)."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from uuid import UUID

from app.dominio.erros import OperacaoNaoPermitida, TransicaoInvalida

PAPEIS_EQUIPE = frozenset({"ATENDENTE", "GESTOR", "ADMIN"})


def pode_autenticar(situacao: str) -> bool:
    """Usuário SUSPENSO não faz login nem renova o refresh token (ADR-028).

    O login deve responder com a mesma mensagem genérica de credenciais inválidas.
    """
    return situacao == "ATIVO"


def calcular_escopo(
    papel: str,
    situacao: str,
    filas_atribuidas: frozenset[UUID],
    unidades_atribuidas: frozenset[UUID],
    unidade_da_fila: Mapping[UUID, UUID],
) -> frozenset[UUID]:
    """Filas que o usuário da equipe pode ver e operar. Ponto único de troca do escopo.

    - ATENDENTE: só as filas em `usuario_fila`; sem atribuição, nenhuma.
    - GESTOR: as filas das unidades em `usuario_unidade`; sem unidade, a central inteira.
    - ADMIN: todas.
    Suspenso ou outro papel: nenhuma (falha fechada).

    `unidade_da_fila` mapeia cada fila existente para a sua unidade.
    """
    if not pode_autenticar(situacao):
        return frozenset()
    if papel == "ADMIN" or (papel == "GESTOR" and not unidades_atribuidas):
        return frozenset(unidade_da_fila)
    if papel == "GESTOR":
        return frozenset(f for f, u in unidade_da_fila.items() if u in unidades_atribuidas)
    if papel == "ATENDENTE":
        return filas_atribuidas & frozenset(unidade_da_fila)
    return frozenset()


def refresh_na_tolerancia(
    revogado_em: datetime,
    substituido: bool,
    ja_reapresentado: bool,
    agora: datetime,
    tolerancia: timedelta,
) -> bool:
    """Refresh já substituído, reapresentado uma única vez dentro da tolerância: duas abas
    renovando juntas, não roubo (ADR-003, AM-003). Fora dela, numa segunda reapresentação ou
    revogado sem substituto (logout), é reuso."""
    return substituido and not ja_reapresentado and agora - revogado_em < tolerancia


def tentativas_esgotadas(falhas_na_janela: int, maximo: int) -> bool:
    """Limite de tentativas (AM-004): bloqueia ao atingir `maximo` dentro da janela."""
    return falhas_na_janela >= maximo


def verificar_suspensao(
    ator_id: UUID, alvo_id: UUID, alvo_papel: str, alvo_situacao: str, admins_ativos: int
) -> None:
    """Pode suspender? Só contas da equipe, nunca a si mesmo nem o último ADMIN ativo.

    `admins_ativos` deve ser contado com as linhas dos ADMIN ativos travadas (FOR UPDATE):
    sem isso, dois admins podem suspender um ao outro ao mesmo tempo e não sobrar nenhum.
    """
    if alvo_situacao != "ATIVO":
        raise TransicaoInvalida("A conta já está suspensa.")
    if alvo_id == ator_id:
        raise OperacaoNaoPermitida("Não é possível suspender a própria conta.")
    if alvo_papel not in PAPEIS_EQUIPE:
        raise OperacaoNaoPermitida("Só contas da equipe podem ser suspensas.")
    if alvo_papel == "ADMIN" and admins_ativos <= 1:
        raise OperacaoNaoPermitida("Não é possível suspender o último administrador ativo.")


def verificar_reativacao(alvo_situacao: str) -> None:
    if alvo_situacao != "SUSPENSO":
        raise TransicaoInvalida("A conta já está ativa.")


def normalizar_identificador(valor: str) -> tuple[str, str]:
    """Login: 11 dígitos (com ou sem pontuação) é CPF; o resto é e-mail, em minúsculas.

    A mesma forma normalizada é usada na busca e no hash do limite de tentativas.
    """
    valor = valor.strip()
    digitos = valor.replace(".", "").replace("-", "")
    if len(digitos) == 11 and digitos.isdigit():
        return "CPF", digitos
    return "EMAIL", valor.lower()
