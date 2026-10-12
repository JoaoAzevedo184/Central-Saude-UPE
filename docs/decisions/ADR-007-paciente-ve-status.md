# 007 — Paciente vê o status, não a posição na fila

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

A posição na fila muda por motivos que o paciente não enxerga: entra alguém com classificação de risco maior, uma prioridade legal é aplicada, uma regra muda. Mostrar "12ª posição" e depois "15ª posição" gera desconfiança e ligações para a central, além de expor indiretamente informações sobre outros pacientes.

## Decisão

- A API do paciente expõe apenas o **status da solicitação** (`EM_ANALISE`, `NA_FILA`, `EM_PROPOSTA`, `AGENDADA`, `ATENDIDA`, `CANCELADA`), com textos como "Em análise" e "Aguardando vaga".
- A ordenação da fila só é exposta para os papéis da equipe.
- O paciente recebe uma explicação geral de como a fila funciona: classificação de risco, prioridades legais e data do pedido.

## Consequências

- Nenhum schema de resposta destinado ao paciente pode conter posição, total da fila ou estimativa derivada deles.
- O protótipo no Figma foi ajustado (telas 02 e 10) para refletir esta decisão.
