# 012 — Implantação numa VM Oracle com Docker Compose

- **Status:** Aceito
- **Data:** 2026-10-12

## Contexto

O projeto não tem orçamento. O grupo tem acesso a uma VM do nível gratuito da Oracle Cloud (2 OCPU, 12 GB de RAM, 200 GB de disco e 20 GB de Object Storage), suficiente para o volume de uma demonstração.

## Decisão

- Um único ambiente de produção nessa VM, com **Docker Compose** orquestrando Nginx, API, Worker e PostgreSQL.
- O **Nginx** é o único serviço exposto: termina TLS, entrega o frontend e faz proxy de `/api/v1`. Os demais ficam na rede interna do Compose.
- **GitHub Actions** roda lint e testes em todo pull request.
- O mesmo arquivo Compose serve ao desenvolvimento local, com sobreposições para o que muda entre os ambientes.

## Consequências

- Ambiente igual para os seis integrantes e para a produção.
- A VM é um ponto único de falha, mitigado pelo backup fora dela ([ADR-009](ADR-009-backup.md)). Alta disponibilidade e Kubernetes ficam adiados (ADR-019).
- Segredos (senha do banco, chaves de token, SMTP) ficam em variáveis de ambiente fora do repositório; o repositório só tem um `.env.example`.
