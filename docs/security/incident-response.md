# Resposta a incidentes

Procedimento proporcional a um protótipo acadêmico com dados sintéticos. Se o sistema um dia tratar dados reais, este documento precisa ser revisto com a instituição, inclusive quanto à comunicação à ANPD e aos titulares exigida pela LGPD.

## O que conta como incidente

- Acesso indevido a dados ou a contas, mesmo que só com dados sintéticos.
- Segredo exposto (senha do banco, chave de token, credencial SMTP, chave SSH).
- Vulnerabilidade reportada por alguém de fora ([SECURITY.md](../../SECURITY.md)).
- Perda ou corrupção de dados.
- Indisponibilidade prolongada durante uma apresentação ou teste com usuários.

## Etapas

| Etapa | O que fazer | Quem |
| --- | --- | --- |
| 1. Registrar | Abrir uma issue privada (ou uma mensagem no canal da equipe, se envolver detalhes sensíveis) com data, quem percebeu e o que foi observado | Quem percebeu |
| 2. Conter | Tirar do ar a parte afetada, revogar ou rotacionar o segredo exposto, encerrar sessões | Responsável pela infraestrutura |
| 3. Investigar | Consultar a auditoria e os logs; identificar o que foi acessado ou alterado e desde quando | Dono da frente afetada + infraestrutura |
| 4. Corrigir | Corrigir a causa, com teste que reproduz o problema; restaurar backup se necessário ([backup e restauração](../operations/backup-restore.md)) | Dono da frente afetada |
| 5. Comunicar | Informar a equipe e o professor orientador; se houver usuários de teste afetados, avisá-los | Líder da equipe |
| 6. Aprender | Registrar causa, impacto e correção; atualizar o [modelo de ameaças](threat-model.md) | Todos |

## Segredo exposto

1. Rotacionar imediatamente o segredo (gerar um novo e atualizar o `.env` da VM).
2. Remover o segredo do repositório e do histórico, se foi publicado.
3. Para chave de token: trocar a chave invalida todas as sessões; avisar a equipe.
4. Verificar na auditoria e nos logs se houve uso no período da exposição.
