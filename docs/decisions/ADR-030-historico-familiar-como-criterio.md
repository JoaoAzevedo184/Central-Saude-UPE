# 030 — Histórico familiar como critério respondido pelo paciente

- **Status:** Proposto
- **Data:** 2026-10-15

## Contexto

Alguns protocolos dependem de histórico familiar. Na mamografia, por exemplo, pesa saber se a mãe ou uma irmã teve câncer de mama. Ligar o cadastro do paciente ao de parentes exporia dados de terceiros que não consentiram e que podem nem usar o sistema.

## Decisão (proposta)

- O histórico familiar entra como um **critério da fila** ([ADR-024](ADR-024-protocolo-por-fila.md)), do tipo `SIM_NAO` e com origem `PACIENTE`. Exemplo: "Sua mãe ou irmã teve câncer de mama?".
- O sistema guarda **só a resposta** do paciente (`resposta_criterio`).
- Não há cadastro de parentes, ligação entre pacientes nem nenhum dado pessoal de terceiros.
- O seed já traz esse critério como exemplo, marcado como simulado. Não há código específico além do protocolo da fila.

## Alternativas consideradas

- **Ligar cadastros de parentes:** trata dados de terceiros sem consentimento e sem necessidade.
- **Campo livre de histórico familiar:** coleta mais do que o protocolo precisa e não pontua.

## Consequências

- A resposta é autodeclarada. Se a UPE exigir comprovação, a origem do critério passa a ser `EQUIPE` ou `REGULACAO`.
- A resposta é dado de saúde: aparece no inventário de [proteção de dados](../security/data-protection.md) e só é vista pela equipe da fila.
