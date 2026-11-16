# MockTalk

Permitir desenvolver e testar automações de WhatsApp (n8n, Python, Java, Node.js e agentes de IA) num WhatsApp simulado, sem número real, com testes manuais e automáticos e visibilidade completa de onde a automação falhou.

> Status: em definição (passo 0). Nenhum código ainda.

## O que faz
- Simula um WhatsApp no navegador: você conversa com seu bot como um cliente real, sem chip, celular ou QR Code.
- Expõe uma API compatível com o WAHA: seu bot troca só a URL entre teste e produção.
- Mostra, num painel do desenvolvedor, todas as conversas em tempo real com mensagens, webhooks, latência e erros.
- Executa testes automáticos com vários clientes virtuais, por script ou com personas de IA.
- Gera relatórios com aprovações, falhas e evidências, e permite reproduzir cada teste.

**O MockTalk não é** um cliente de WhatsApp para uso real, não envia mensagens para números reais e não é ferramenta de disparo em massa.

> ⚠️ O MockTalk substitui só o canal WhatsApp. Se o seu bot envia e-mails, cria eventos de calendário ou grava em bancos, essas ações acontecem de verdade durante o teste. Use credenciais e contas de teste.

## Stack
- Backend: Rust (Axum + Tokio), agentes com Rig — a validar na TASK-001
- Frontend: React + TypeScript + Vite, servido pelo backend
- Banco: PostgreSQL (Redis em fase posterior)
- Execução: Docker Compose

## Como rodar
```bash
docker compose up   # a confirmar
```

## Estrutura
A confirmar após a TASK-001.

## Documentação
- [Visão](docs/VISION.md) · [Regras](docs/PRODUCT.md) · [Design](docs/DESIGN.md)
- [Arquitetura](docs/ARCHITECTURE.md) · [Decisões](docs/DECISIONS.md)

## Como trabalhamos
Desenvolvimento com agentes de IA no fluxo ASF-Loop: Análise → Desenho → Gate de Entrada → Loop → Aceite.
Veja [docs/MODELO.md](docs/MODELO.md) e [AGENTS.md](AGENTS.md).

## Licença
[MIT](LICENSE)
