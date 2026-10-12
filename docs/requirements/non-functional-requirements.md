# Requisitos não funcionais

Metas marcadas com *(proposta)* ainda não foram validadas pelo grupo; servem de ponto de partida para os testes.

## Segurança e privacidade

| ID | Requisito | Detalhe |
| --- | --- | --- |
| RNF-001 | Autenticação segura na web | Refresh token em cookie `httpOnly` + `Secure` + `SameSite`; header contra CSRF ([ADR-003](../decisions/ADR-003-autenticacao-web.md)) |
| RNF-002 | Controle de acesso por papel e por dono do recurso | Matriz em [controle de acesso](../security/access-control.md) |
| RNF-003 | Senhas armazenadas só como hash com algoritmo próprio para senhas | — |
| RNF-004 | Trilha de auditoria append-only das mudanças de estado | RN-010 |
| RNF-005 | Minimização e mascaramento de dados pessoais; somente dados sintéticos no projeto | [proteção de dados](../security/data-protection.md) |
| RNF-006 | Consentimento registrado por finalidade, com versão do termo, e revogável | RN-009 |
| RNF-007 | Segredos fora do repositório | Variáveis de ambiente; o repositório só tem `.env.example` |

## Acessibilidade e usabilidade

| ID | Requisito | Detalhe |
| --- | --- | --- |
| RNF-010 | Interface responsiva, pensada primeiro para o celular | [ADR-002](../decisions/ADR-002-web-primeiro.md) |
| RNF-011 | Conformidade com WCAG 2.1 nível AA nas telas do paciente | Contraste, foco visível, navegação por teclado, labels, erro em texto, área de toque ≥ 44 px |
| RNF-012 | Linguagem simples | Textos curtos; botões dizem exatamente o que fazem; consequências explícitas ("depois disso, a vaga vai para outra pessoa") |
| RNF-013 | Fonte de alta legibilidade | Atkinson Hyperlegible, corpo ≥ 17 px |

## Confiabilidade e dados

| ID | Requisito | Detalhe |
| --- | --- | --- |
| RNF-020 | Nenhuma vaga entregue a dois pacientes, mesmo sob concorrência | Índice único parcial ([ADR-004](../decisions/ADR-004-ocupacao-da-vaga.md)) e teste de concorrência |
| RNF-021 | Nenhum aviso perdido nem enviado sobre algo não gravado | Outbox transacional ([ADR-006](../decisions/ADR-006-outbox.md)) |
| RNF-022 | Jobs idempotentes e sem execução duplicada | [ADR-005](../decisions/ADR-005-worker-separado.md) |
| RNF-023 | Backup fora da VM com restauração testada; RPO igual à frequência do dump | [ADR-009](../decisions/ADR-009-backup.md) |
| RNF-024 | Datas com fuso; exibição em `America/Recife` | [ADR-008](../decisions/ADR-008-datas-e-fuso.md) |

## Desempenho *(proposta)*

| ID | Requisito | Meta |
| --- | --- | --- |
| RNF-030 | Tempo de resposta das leituras do paciente | p95 abaixo de 300 ms no teste de carga |
| RNF-031 | Atraso entre a ação e o aviso no site | Menor que o intervalo de leitura do Worker (ex.: 30 s) |

## Manutenibilidade e operação

| ID | Requisito | Detalhe |
| --- | --- | --- |
| RNF-040 | Ambiente reproduzível | Docker Compose igual para os seis integrantes e para produção ([ADR-012](../decisions/ADR-012-implantacao.md)) |
| RNF-041 | CI em todo pull request | Lint e testes no GitHub Actions |
| RNF-042 | Regras de negócio testáveis sem banco nem framework | Camada `dominio` isolada ([SDD](../architecture/SDD.md)) |
| RNF-043 | Integrações substituíveis | Interfaces com implementação simulada ([ADR-010](../decisions/ADR-010-integracoes-por-interface.md)) |
| RNF-044 | Contrato da API publicado | OpenAPI gerado pelo FastAPI |
