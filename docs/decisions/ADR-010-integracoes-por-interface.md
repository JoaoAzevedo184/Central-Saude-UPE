# 010 — Integrações atrás de interfaces

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O desafio pede integração com sistemas de regulação e comunicação multicanal (WhatsApp, SMS, e-mail, app). Para alunos, a integração real com a regulação não está disponível, e WhatsApp e SMS têm custo e burocracia.

## Decisão

Toda integração externa fica atrás de uma interface do domínio, com uma implementação simples ou simulada no MVP:

| Interface | Implementações no MVP | Depois |
| --- | --- | --- |
| `CanalNotificacao` | Site (in-app) e e-mail (SMTP) | Telegram via n8n (ADR-013), push (ADR-015) |
| `ReguladorGateway` | Simulada, com dados sintéticos | Conector real, se a UPE disponibilizar |

## Consequências

- Adicionar um canal novo é escrever uma classe nova, sem mexer nas regras de negócio.
- As regras de negócio podem ser testadas com implementações falsas das interfaces.
- A apresentação mostra a arquitetura pronta para crescer sem depender de APIs pagas.
