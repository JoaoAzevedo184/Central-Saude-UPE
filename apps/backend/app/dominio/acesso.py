"""Acesso da equipe: escopo por fila (ADR-025) e usuário suspenso (ADR-028)."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from uuid import UUID

from app.dominio.erros import (
    EntradaInvalida,
    OperacaoNaoPermitida,
    TransicaoInvalida,
    VisaoCentralNaoConfirmada,
)

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


SENHA_MINIMA = 10


def verificar_atribuicao_de_filas(papel: str) -> None:
    """Só ATENDENTE recebe fila (RF-035)."""
    if papel != "ATENDENTE":
        raise OperacaoNaoPermitida("Só atendentes recebem filas.")


def verificar_atribuicao_de_unidades(
    papel: str, unidade_ids: frozenset[UUID], confirmar_visao_central: bool
) -> None:
    """Só GESTOR recebe unidade (RF-035). Sem nenhuma unidade o gestor passa a ver a central
    inteira (ADR-025): isso exige confirmação explícita, nunca acontece por omissão."""
    if papel != "GESTOR":
        raise OperacaoNaoPermitida("Só gestores recebem unidades.")
    if not unidade_ids and not confirmar_visao_central:
        raise VisaoCentralNaoConfirmada(
            "Sem unidades, o gestor vê a central inteira. "
            "Envie confirmar_visao_central=true para confirmar."
        )


def verificar_criacao_de_usuario(
    papel: str, unidade_ids: frozenset[UUID] | None, confirmar_visao_central: bool
) -> None:
    """Contas criadas pelo admin: ATENDENTE, GESTOR ou ADMIN. `unidade_ids` só vale para GESTOR
    (outro papel → 422); GESTOR segue a mesma regra de `verificar_atribuicao_de_unidades`."""
    if papel not in PAPEIS_EQUIPE:
        raise EntradaInvalida("Papel inválido para a equipe.")
    if papel != "GESTOR":
        if unidade_ids is not None:
            raise EntradaInvalida("Só gestores recebem unidades.")
        return
    verificar_atribuicao_de_unidades(papel, unidade_ids or frozenset(), confirmar_visao_central)


def verificar_troca_de_senha(senha_atual: str, senha_nova: str) -> None:
    """Nova senha com ao menos `SENHA_MINIMA` caracteres e diferente da atual (422)."""
    if len(senha_nova) < SENHA_MINIMA:
        raise EntradaInvalida(f"A nova senha precisa ter ao menos {SENHA_MINIMA} caracteres.")
    if senha_nova == senha_atual:
        raise EntradaInvalida("A nova senha precisa ser diferente da atual.")


def verificar_redefinicao_de_senha(alvo_papel: str) -> None:
    """O admin redefine só ATENDENTE e GESTOR. Recuperar um ADMIN é pelo terminal
    (`python -m app.infra.admin redefinir-senha`), que não depende de outro admin logado."""
    if alvo_papel not in ("ATENDENTE", "GESTOR"):
        raise OperacaoNaoPermitida(
            "A senha de administrador só é redefinida pelo terminal do servidor."
        )


def normalizar_identificador(valor: str) -> tuple[str, str]:
    """Login: 11 dígitos (com ou sem pontuação) é CPF; o resto é e-mail, em minúsculas.

    A mesma forma normalizada é usada na busca e no hash do limite de tentativas.
    """
    valor = valor.strip()
    digitos = valor.replace(".", "").replace("-", "")
    if len(digitos) == 11 and digitos.isdigit():
        return "CPF", digitos
    return "EMAIL", valor.lower()
