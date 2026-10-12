# 001 — Stack do projeto

- **Status:** Aceito para backend, banco e infraestrutura. Frontend: Proposto (em revisão pelo grupo)
- **Data:** 2026-10-12

## Contexto

Seis integrantes, todos atuando como fullstack, com cerca de cinco semanas de desenvolvimento até o MVP de novembro. A stack precisa ser algo que a maioria já domina, para todos produzirem desde a primeira semana.

## Decisão

- **Backend:** Python com FastAPI **síncrono**, SQLAlchemy 2, Alembic para migrações, Pydantic para validação e Pytest para testes. Python é a linguagem predominante do grupo.
- **Banco:** PostgreSQL.
- **Infraestrutura:** Docker Compose, Nginx e GitHub Actions ([ADR-012](ADR-012-implantacao.md)).
- **Frontend (proposta em revisão):** React + TypeScript + Vite, com React Router, TanStack Query, React Hook Form e Zod. A escolha final depende da conversa do grupo; quando fechar, este ADR é atualizado ou substituído.

## Alternativas consideradas

- **FastAPI assíncrono:** mais desempenho em I/O concorrente, mas exige cuidado com sessões assíncronas do SQLAlchemy e bibliotecas compatíveis. O volume do MVP não justifica a complexidade para um grupo que ainda está aprendendo.
- **Spring Boot:** robusto, mas a maioria do grupo tem mais familiaridade com Python. Fica como possibilidade para uma evolução futura.

## Consequências

- O frontend não bloqueia o backend: a API é definida pelo contrato OpenAPI, e qualquer frontend o consome.
- Com FastAPI síncrono, tarefas lentas (envio de e-mail, expiração de propostas) não podem rodar dentro da requisição; vão para o Worker ([ADR-005](ADR-005-worker-separado.md)).
