# Documentação

Cada documento responde a uma pergunta. Para a mesma informação não ficar repetida em vários lugares, cada assunto tem um único documento "dono", e os demais apenas apontam para ele.

| Pasta | Pergunta que responde | Documentos |
| --- | --- | --- |
| [product/](product/) | **O que** construir e **por quê** | [PRD](product/PRD.md), [escopo e roadmap](product/scope-and-roadmap.md) |
| [requirements/](requirements/) | **Como o sistema deve se comportar** | [requisitos funcionais](requirements/functional-requirements.md), [não funcionais](requirements/non-functional-requirements.md), [regras de negócio](requirements/business-rules.md), [casos de uso](requirements/use-cases/README.md), [questões em aberto](requirements/open-questions.md) |
| [architecture/](architecture/) | **Como** o software é organizado | [SDD](architecture/SDD.md), [modelo de dados](architecture/data-model.md), [API](architecture/api-design.md), [diagramas](architecture/diagrams/) |
| [security/](security/) | Como os riscos são **prevenidos, detectados e tratados** | [visão geral](security/security-overview.md), [modelo de ameaças](security/threat-model.md), [controle de acesso](security/access-control.md), [proteção de dados](security/data-protection.md), [resposta a incidentes](security/incident-response.md) |
| [decisions/](decisions/) | **Por que** decidimos assim | [ADRs](decisions/README.md) |
| [operations/](operations/) | Como **implantar e operar** | [implantação](operations/deployment.md), [backup e restauração](operations/backup-restore.md) |

## Identificadores

Os IDs são estáveis: um item removido não tem o número reaproveitado.

| Prefixo | Significado | Onde vive |
| --- | --- | --- |
| `RF-NNN` | Requisito funcional | [functional-requirements.md](requirements/functional-requirements.md) |
| `RNF-NNN` | Requisito não funcional | [non-functional-requirements.md](requirements/non-functional-requirements.md) |
| `RN-NNN` | Regra de negócio | [business-rules.md](requirements/business-rules.md) |
| `UC-NNN` | Caso de uso | [use-cases/](requirements/use-cases/) |
| `AM-NNN` | Ameaça | [threat-model.md](security/threat-model.md) |
| `ADR-NNN` | Decisão de arquitetura | [decisions/](decisions/) |
| `ABERTO-N` | Questão sem resposta | [open-questions.md](requirements/open-questions.md) |

## Rastreabilidade

Um requisito deve poder ser seguido do produto até o teste:

```
RF-012 Paciente confirma proposta
  → UC-004 Confirmar proposta (fluxos e critérios de aceite)
  → RN-003 prazo de resposta · RN-001 ocupação da vaga
  → diagrams/sequence-confirmation.md
  → access-control.md (só o dono da proposta confirma)
  → teste automatizado que cita UC-004 no nome
```

Nos testes, use o ID no nome ou na docstring (`test_uc004_proposta_expirada_retorna_409`), para a busca pelo ID achar o teste.

## Onde fica cada coisa: GitHub ou Notion

- **GitHub (esta pasta) é a fonte oficial** da documentação técnica: requisitos, design, segurança e decisões. Muda por pull request, junto com o código.
- **Notion** é o espaço de planejamento: Kanban, atas de reunião, contato com a UPE e rascunhos. Quando uma decisão discutida no Notion é fechada, ela vira um ADR ou uma alteração aqui, e o Notion passa a apontar para o arquivo.

## Diagramas

Os diagramas são escritos em [Mermaid](https://mermaid.js.org/), que o GitHub renderiza direto no navegador e que fica versionado como texto. Para o relatório acadêmico, exporte as imagens com o [Mermaid Live Editor](https://mermaid.live/) ou com o `mmdc`.
