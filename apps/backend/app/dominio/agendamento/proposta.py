"""Proposta de vaga (UC-003, ADR-021)."""

from typing import Any
from uuid import UUID

from app.dominio.relogio import Relogio


def propor_vaga(solicitacao: Any, vaga: Any, proposto_por: UUID | None, relogio: Relogio) -> Any:
    """Propõe `vaga` à `solicitacao`. Toda proposta do sistema passa por aqui (ADR-021).

    A implementação deverá garantir, numa única transação (SDD 5.1):
    - RN-001 e RN-002: no máximo um agendamento ativo por vaga; a corrida é decidida pelo
      índice único parcial em `agendamento(vaga_id)`, e a violação vira 409 ou descarte;
    - RN-003: as regras de estado da solicitação e do agendamento;
    - RN-008: não propor se o prazo de resposta passar do horário da vaga menos
      `PROPOSTA_ANTECEDENCIA_MINIMA_HORAS`; a vaga fica livre ("vaga sem proposta");
    - auditoria e evento na outbox gravados na mesma transação da proposta;
    - `proposto_por=None` significa proposta automática (Worker); senão, o ID do atendente.

    Os tipos de `solicitacao` e `vaga` serão as entidades de domínio criadas no UC-003.
    """
    raise NotImplementedError("UC-003")
