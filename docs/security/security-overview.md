# Segurança — visão geral

Controles de segurança do sistema e onde cada um é detalhado. Documentar esses controles não significa, por si só, estar em conformidade com a LGPD; este é um protótipo acadêmico que usa apenas dados sintéticos.

## O que protegemos

| Ativo | Por que importa |
| --- | --- |
| Dados pessoais do paciente (nome, CPF, cartão do SUS, nascimento, contato) | Identificam a pessoa |
| Dados de saúde implícitos (especialidade pedida, classificação de risco, prioridade legal) | Revelam condição de saúde; são dados sensíveis na LGPD |
| Integridade da fila e das vagas | Uma vaga entregue errado ou duas vezes prejudica o paciente |
| Trilha de auditoria | É a prova de quem fez o quê |
| Credenciais e segredos | Dão acesso a todo o resto |

## Controles

| Área | Controle | Situação | Detalhe |
| --- | --- | --- | --- |
| Autenticação | Refresh token em cookie `httpOnly` + `Secure` + `SameSite`; access token de vida curta | Decidido | [ADR-003](../decisions/ADR-003-autenticacao-web.md) |
| Autenticação | Senhas só como hash com algoritmo próprio para senhas | Decidido | RNF-003 |
| Autenticação | Limite de tentativas de login e de cadastro | Proposto | AM-004 |
| Sessão | Header contra CSRF em toda requisição que altera estado | Decidido | [ADR-003](../decisions/ADR-003-autenticacao-web.md) |
| Autorização | Papéis + verificação de dono do recurso em toda rota com ID | Decidido | [controle de acesso](access-control.md) |
| Autorização | Escopo por unidade para a equipe | Provisório: todas as unidades, via `escopo_da_equipe()`, mitigado pela auditoria ([ADR-023](../decisions/ADR-023-escopo-todas-as-unidades.md)) | [controle de acesso](access-control.md) |
| Integridade | Índice único parcial na ocupação da vaga; transições com `FOR UPDATE` | Decidido | [ADR-004](../decisions/ADR-004-ocupacao-da-vaga.md) |
| Auditoria | Registro append-only de toda mudança de estado, com ator | Decidido | RN-010 |
| Dados | Minimização, mascaramento de CPF, consentimento por finalidade, só dados sintéticos | Decidido | [proteção de dados](data-protection.md) |
| Entrada | Validação com Pydantic; SQL só pelo ORM ou com parâmetros | Decidido | AM-010 |
| Saída | Schemas de resposta explícitos por papel; nada de devolver o modelo do banco inteiro | Proposto | AM-013, AM-014 |
| Transporte | HTTPS em tudo; HSTS no Nginx | Proposto | [implantação](../operations/deployment.md) |
| Cabeçalhos | `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy` no Nginx | Proposto | AM-003 |
| Rede | Só o Nginx exposto; API, Worker e banco na rede interna | Decidido | [ADR-012](../decisions/ADR-012-implantacao.md) |
| Segredos | Variáveis de ambiente fora do repositório; só `.env.example` versionado | Decidido | AM-009 |
| Dependências | Alertas do Dependabot e varredura de dependências na CI | Proposto | — |
| Disponibilidade | Backup fora da VM com restauração testada | Decidido | [backup e restauração](../operations/backup-restore.md) |

## Responsabilidades

| Quem | Responde por |
| --- | --- |
| Dono da frente 1 (Autenticação, papéis e LGPD) | Autenticação, autorização, consentimento, auditoria |
| Todos os integrantes | Verificação de dono do recurso e testes de acesso negado nas rotas da própria frente |
| Quem revisa o PR | Itens de segurança do modelo de pull request |
| Responsável pela infraestrutura | Nginx, segredos da VM, backup |

## Documentos

- [Modelo de ameaças](threat-model.md)
- [Controle de acesso](access-control.md)
- [Proteção de dados](data-protection.md)
- [Resposta a incidentes](incident-response.md)
- Como reportar uma vulnerabilidade: [SECURITY.md](../../SECURITY.md)
