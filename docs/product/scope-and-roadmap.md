# Escopo e roadmap

## MVP — novembro/2026

| Área | Entra no MVP | Requisitos |
| --- | --- | --- |
| Conta e acesso | Cadastro de paciente com consentimento LGPD, sexo e município; login; papéis (Paciente, Atendente, Gestor, Admin); escopo por fila; suspensão de acesso | RF-001 a RF-004, RF-033 a RF-035 |
| Cadastros | Unidades, especialidades, filas (elegibilidade, prazo de confirmação, tolerância), agendas e geração de vagas, bloqueio de vaga | RF-005 a RF-007 |
| Fila | Filas com elegibilidade e protocolo próprios, solicitação, validação pela equipe, ordem por risco, nota e chegada, linha do tempo sem posição | RF-008 a RF-010, RF-022, RF-028 a RF-032 |
| Agendamento | Proposta com prazo, confirmação, pedido de outra data, cancelamento, expiração automática, reaproveitamento de vaga, registro de comparecimento e falta | RF-011 a RF-017 |
| Comunicação | Avisos no site e por e-mail | RF-018, RF-019 |
| Acompanhamento | Paciente vê o status, a linha do tempo e o histórico de atendimentos, sem posição na fila | RF-020, RF-029, RF-030 |
| Gestão | Painel de indicadores, trilha de auditoria | RF-021, RF-023 |
| Plataforma | Web responsivo, Docker Compose, CI, deploy numa VM Oracle, backup | RNF-* |

**Desejável no MVP, se houver tempo:** lembrete automático antes do atendimento (RF-024) e leitura em voz alta dos detalhes do agendamento.

## Fora do MVP

| Item | Por quê | Quando |
| --- | --- | --- |
| App mobile React Native e push | Dividiria a equipe; o web responsivo atende o celular | Fase 2 ([ADR-002](../decisions/ADR-002-web-primeiro.md)) |
| Telegram via n8n | Depende do fluxo de e-mail estável | Fase 2 (ADR-013) |
| WhatsApp e SMS | Custo e burocracia de API | Sem data |
| Integração real com a regulação | Não disponível para alunos | Se a UPE disponibilizar |
| Chatbot | Só faz sentido com o fluxo principal pronto | Se sobrar tempo |
| Previsão de faltas e de demanda | Exige histórico real | Sem data |
| Observabilidade completa (Prometheus, Grafana, Loki) | Entra depois do primeiro deploy | Fase 2 (ADR-014) |

## Cronograma

| Mês (2026) | Marco acadêmico | Marco do produto |
| --- | --- | --- |
| Agosto | Apresentação do projeto | — |
| Setembro | Assessoramentos | Protótipo navegável no Figma |
| Outubro | Entrega do projeto e correções | Documentação técnica; setup do repositório; modelo de dados; início do backend |
| Novembro | Execução do projeto e relatório | MVP funcional e implantado; testes de usabilidade |
| Dezembro | Entrega do relatório | Relatório final e apresentação |

## Riscos do escopo

| Risco | Mitigação |
| --- | --- |
| A UPE não responde às questões em aberto a tempo | Usar a opção mais simples de cada uma, marcada como simulada, e registrar a pendência no relatório |
| O escopo cresce com canais e integrações | Tudo fora do MVP fica atrás de interfaces; nada entra sem passar por esta página |
| Pouco tempo de código (cerca de cinco semanas) | Frentes verticais com dono; o backend começa antes da definição final do frontend |
