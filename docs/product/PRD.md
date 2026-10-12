# PRD — Central Inteligente de Teleagendamento

| | |
| --- | --- |
| **Produto** | Central Inteligente de Teleagendamento do Complexo Hospitalar da UPE |
| **Origem** | Desafio do programa [Desafios PE](https://desafios.pe.gov.br/), lançado pela Coordenação de Saúde Digital do CH/UPE |
| **Contexto acadêmico** | Projeto de Intervenção — Atividades Práticas Interdisciplinares de Extensão III, Sistemas de Informação, UNINASSAU Olinda |
| **Versão** | 0.1 — outubro/2026 |
| **Status** | Escopo do MVP definido; regras da fila dependem da UPE ([questões em aberto](../requirements/open-questions.md)) |

## 1. Problema

O Complexo Hospitalar da UPE (CISAM, HUOC e PROCAPE) é referência estadual em alta complexidade pelo SUS. Em 2024 registrou mais de 36 mil internamentos e 1,5 milhão de procedimentos ambulatoriais.

Parte da marcação e da remarcação ainda depende de ligações, atendimento presencial, planilhas e fluxos de regulação diferentes. As consequências:

- o paciente espera sem saber em que pé está o pedido;
- a confirmação depende de conseguir falar com alguém por telefone;
- vagas canceladas em cima da hora ficam ociosas;
- quem vem de outro município pode chegar sem saber o local exato ou o preparo necessário;
- os gestores não enxergam filas, faltas e desistências com rapidez.

## 2. Usuários

| Persona | Quem é | O que precisa |
| --- | --- | --- |
| **Paciente** | Usuário do SUS encaminhado ao Complexo, muitas vezes de outro município, com letramento digital variado, acessando principalmente pelo celular | Saber o status do pedido, receber a vaga com antecedência, confirmar ou remarcar sem ligar, saber onde ir e o que levar |
| **Atendente** | Profissional da central ou da regulação interna | Ver a fila de cada especialidade, validar pedidos e acompanhar propostas pendentes |
| **Gestor** | Coordenação da unidade ou do Complexo | Indicadores de fila, confirmação, faltas e vagas reaproveitadas para tomar decisões |
| **Administrador** | Responsável pela configuração do sistema | Cadastrar unidades, especialidades, agendas e regras da fila |

## 3. Objetivos

| Objetivo | Como medir no protótipo |
| --- | --- |
| Reduzir o tempo entre a solicitação e a confirmação | Tempo médio da proposta até a confirmação, no painel |
| Reaproveitar vagas liberadas por cancelamento | Quantidade de vagas canceladas que receberam nova proposta |
| Reduzir faltas | Taxa de faltas sobre os agendamentos confirmados |
| Dar previsibilidade ao paciente | 100% das solicitações com status visível; nenhuma ligação necessária no caminho feliz |
| Ser utilizável por quem tem pouca familiaridade digital | Testes de usabilidade com pelo menos 4 pessoas, incluindo uma de perfil mais velho; tarefas principais concluídas sem ajuda |

Os números do painel vêm de dados sintéticos e servem para demonstrar o mecanismo, não para afirmar ganhos reais.

## 4. Escopo

O recorte do MVP de novembro/2026 e o que vem depois estão em [escopo e roadmap](scope-and-roadmap.md). Os requisitos detalhados estão em [requisitos funcionais](../requirements/functional-requirements.md).

**Em uma frase:** no MVP, o paciente pede o atendimento, acompanha o status, recebe uma proposta de vaga e confirma, remarca ou cancela pelo site. A vaga cancelada volta para a fila, e os gestores acompanham tudo num painel.

## 5. Restrições

- **Sem dados reais.** Nenhum dado real de paciente é usado; nenhum teste é feito com usuários do SUS sem autorização da instituição.
- **Sem integração real com a regulação.** Fica atrás de uma interface com implementação simulada ([ADR-010](../decisions/ADR-010-integracoes-por-interface.md)).
- **As regras da fila são da instituição.** As do protótipo são exemplos marcados como simulados ([ADR-011](../decisions/ADR-011-regras-de-prioridade.md)).
- **Sem orçamento.** Uma VM do nível gratuito da Oracle Cloud; nenhum serviço pago (WhatsApp e SMS ficam fora).
- **Prazo.** MVP funcional em novembro/2026 e relatório final em dezembro/2026, com uma equipe de seis estudantes.

## 6. Premissas e dependências

- A UPE responde às [questões em aberto](../requirements/open-questions.md) a tempo de orientar a fila e o controle de acesso; caso contrário, o MVP usa a opção mais simples, documentada como simulada.
- A classificação de risco chega pronta da regulação; o sistema não faz triagem clínica.

## 7. Fora do escopo do produto

- Triagem ou priorização clínica feita pelo sistema.
- Prontuário, resultados de exames ou qualquer dado clínico além do necessário para agendar.
- Substituir os sistemas oficiais de regulação municipais e estaduais.

## 8. Glossário

| Termo | Significado |
| --- | --- |
| **Unidade** | CISAM, HUOC ou PROCAPE |
| **Especialidade** | Área de atendimento. A mesma especialidade pode existir em mais de uma unidade, cada uma com seu prazo de resposta |
| **Agenda** | Grade de horários de um profissional para uma especialidade numa unidade (`Schedule` no FHIR) |
| **Vaga** | Um horário concreto gerado a partir de uma agenda (`Slot` no FHIR) |
| **Solicitação** | O pedido de atendimento do paciente: a demanda que fica na fila |
| **Agendamento** | O vínculo entre uma solicitação e uma vaga (`Appointment` no FHIR). Ocupa a vaga enquanto estiver `PROPOSTO` ou `CONFIRMADO` |
| **Proposta** | Agendamento `PROPOSTO`, com prazo de resposta |
| **Classificação de risco** | Prioridade clínica definida pela regulação (vermelho, amarelo, verde, azul) |
| **Prioridade legal** | Prioridades previstas em lei: idosos, gestantes, pessoas com deficiência |
| **Regulação** | Processo e sistemas públicos que autorizam e encaminham o acesso a consultas e procedimentos especializados |

## Referências

- Desafios PE — *Central Inteligente de Teleagendamento para o Complexo Hospitalar Universitário da UPE*.
- SCH/UPE — *CH em números: anuário estatístico 2025, ano-base 2024*.
- Projeto de Intervenção (PEX-MDL-54) da equipe, versão de setembro/2026.
