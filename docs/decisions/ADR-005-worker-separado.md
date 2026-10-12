# 005 — Worker separado da API

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

Há tarefas que não pertencem a uma requisição HTTP: expirar propostas vencidas, enviar e-mails e retentar envios com falha. Se rodassem dentro da API (por exemplo, com um agendador no processo), cada worker do Uvicorn executaria o mesmo job, em duplicidade.

## Decisão

- Os jobs rodam **somente no container `worker`**, que usa o mesmo pacote Python da API com outro ponto de entrada.
- Jobs no MVP: expiração de propostas, consumo da outbox ([ADR-006](ADR-006-outbox.md)) e retentativa de notificações.
- Todo job é **idempotente** e pega trabalho com `SELECT ... FOR UPDATE SKIP LOCKED`, de modo que dois Workers nunca processam a mesma linha.

## Consequências

- É possível subir mais de um Worker sem mudar o código.
- A API fica com respostas rápidas e previsíveis.
- Os testes dos jobs precisam rodar o mesmo job duas vezes e verificar que o resultado não muda.
