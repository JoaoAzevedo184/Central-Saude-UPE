# 009 — Backup com pg_dump e RPO declarado

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O sistema roda numa única VM ([ADR-012](ADR-012-implantacao.md)). Se o disco ou a VM forem perdidos, o PostgreSQL vai junto. Um backup que nunca foi restaurado não é garantia de nada.

## Decisão

- `pg_dump` agendado, com os arquivos enviados para o Object Storage da Oracle, fora da VM.
- O **RPO** (quanto dado se pode perder) declarado é igual à frequência real do dump. Frequência escolhida: _a definir no setup_.
- A restauração é **testada**: restaurar o dump mais recente num banco limpo e conferir a contagem de registros das tabelas principais.

## Consequências

- O RPO só pode ser reduzido aumentando a frequência ou passando para backup contínuo (WAL), o que exigiria um novo ADR.
- O procedimento de restauração precisa estar escrito, para qualquer integrante conseguir executá-lo.
