# Pesquisa pública sobre o CHU/UPE (CISAM, HUOC e PROCAPE)

> **Estado: pesquisa preliminar, não verificada.** Organizada em 07/11/2026 a partir de uma conversa de pesquisa com IA. As fontes ainda **não foram reabertas** uma a uma. Nada aqui é regra oficial do hospital até que o item da seção 6 seja conferido e marcado com a data de acesso. Não use estes dados como fato no relatório sem essa conferência.

Este documento responde a uma pergunta: **o que se sabe publicamente sobre os serviços e as regras de acesso do Complexo Hospitalar Universitário da UPE, e o que disso afeta o MVP**. Os requisitos do sistema continuam em [`requirements/`](../../requirements/), e as decisões em [`decisions/`](../../decisions/).

## 1. Classes de evidência

Toda afirmação desta pasta tem uma classe:

| Classe | Significado | Pode ir para o relatório como |
|---|---|---|
| **A — Oficial** | Está num documento público de órgão oficial (SES-PE, Prefeitura do Recife, UPE, Ministério da Saúde) e foi conferido com URL, data de acesso e trecho | Fato, com a citação |
| **B — Histórico** | Aparece em documento oficial antigo (por exemplo, relatórios de 2010–2011) | Contexto histórico, nunca como oferta atual |
| **C — Proposta do MVP** | Escolha de projeto deste grupo, sem validação do hospital | Proposta, dita como proposta |
| **D — Pendente** | Encontrado na pesquisa, mas ainda não conferido | Nada, até ser conferido |

**Hoje, todos os itens desta pasta estão em B, C ou D.** Nenhum chegou a A, porque as fontes ainda não foram reabertas.

## 2. As três unidades (resumo)

| Unidade | Perfil | Observação |
|---|---|---|
| CISAM | Saúde da mulher, obstetrícia, maternidade, neonatologia e pediatria | A página do NUTES-CISAM descreveria uma **Central de Teleagendamento** própria, com abertura de prontuário, pedido de consulta e teleconsulta com consentimento (D) |
| HUOC | Várias especialidades clínicas e cirúrgicas, oncologia, infectologia, transplante hepático, radioterapia | A lista não prova que cada serviço esteja ativo em 2026 (D) |
| PROCAPE | Cardiologia, emergência cardiovascular, intervenções e cirurgia cardíaca | Os exames listados vêm só de relatórios de 2010–2011 (B) |

Os catálogos completos estão em dois arquivos CSV:

- [`catalogo-servicos.csv`](catalogo-servicos.csv): 64 especialidades e serviços (CISAM 29, HUOC 27, PROCAPE 8);
- [`catalogo-exames.csv`](catalogo-exames.csv): 23 exames e procedimentos (CISAM 11, PROCAPE 12).

Colunas dos dois: `unidade`, o serviço ou exame, `tipo`, `status_evidencia` (`catalogo_institucional_preliminar` ou `historico_2010_2011`), `disponibilidade_2026` (todos `nao_verificada`), `codigo_sigtap` (vazio: nenhum código foi conferido) e `fonte_referencia`.

**Não use os catálogos para afirmar que um serviço existe ou tem agenda hoje.** Eles servem para o relatório (contexto) e para uma futura revisão dos dados sintéticos do seed.

## 3. Regras encontradas e como o MVP se compara

| ID na pesquisa | Regra | Classe | O que o MVP faz | Situação |
|---|---|---|---|---|
| P-01 | Consultas e exames regulados seguem encaminhamento e autorização | D (fonte geral SES/Recife) | O pedido entra "em análise" e só vai para a fila depois da classificação pela equipe | Compatível |
| P-02 | A prioridade é definida por critérios clínicos da regulação, sem pesos improvisados | D | A atendente classifica o risco (3 níveis); uma nota calculada pelos critérios configurados por fila desempata | Explicar que os critérios são configuráveis e, num uso real, seriam definidos pela regulação |
| P-03 | Atendimento pelo SUS é gratuito | D | Não há cobrança | Compatível |
| P-04 | Identificação, Cartão SUS, encaminhamento e comprovantes, conforme o fluxo | D | O cadastro pede CPF e CNS; o pedido registra a origem do encaminhamento | Parcial: o MVP não recebe documentos (módulo de documentos ficou para depois) |
| P-05 | No CISAM, a abertura de prontuário vem antes do pedido de consulta | D (fluxo do NUTES-CISAM) | Não existe prontuário no MVP | Lacuna, fica para depois do MVP; não generalizar para HUOC e PROCAPE |
| P-06 | Teleconsulta exige análise de elegibilidade, consentimento e teste de conexão | D (NUTES-CISAM) | O MVP agenda consultas presenciais; não faz teleconsulta | Fora do escopo |
| P-12 | Recusa não redistribui vaga automaticamente sem regra validada | C (sugestão conservadora da pesquisa) | O Worker oferece a vaga livre ao próximo da fila ([ADR-021](../../decisions/ADR-021-matching-automatico.md)) | **Divergência consciente:** é a proposta central do MVP. Apresentar como proposta a validar com a regulação, junto com a RN-020 |
| P-14 | Dados de saúde exigem proteção e acesso restrito | D (LGPD, Lei 13.709/2018) | Papéis, escopo por unidade, auditoria, CPF mascarado, paciente sem posição nem risco | Compatível; o detalhamento está em [`security/data-protection.md`](../../security/data-protection.md) |

As demais regras da pesquisa (paciente só vê os próprios pedidos, auditoria das ações, concorrência sem estados contraditórios, vínculo do pedido com unidade e serviço) já estão no MVP e documentadas em [`requirements/business-rules.md`](../../requirements/business-rules.md) e em [`security/`](../../security/).

**Estados.** A pesquisa sugere `CRIADA → EM_ANALISE → AUTORIZADA → AGENDADA → NOTIFICADA → CONFIRMADA | RECUSADA → ENCERRADA`. O MVP usa `EM_ANALISE → NA_FILA → EM_PROPOSTA → AGENDADA → ATENDIDA | CANCELADA`, com a notificação como evento (avisos e e-mail), não como estado. A diferença é de nomenclatura e granularidade; nenhuma mudança está prevista antes da apresentação.

## 4. Dados sintéticos do seed comparados com a pesquisa

| Fila no seed | Pesquisa | Ação |
|---|---|---|
| Laqueadura tubária — CISAM | Laqueadura aparece no CISAM | Coerente |
| Mamografia — CISAM | Mamografia não aparece em nenhuma unidade; mastologia aparece no HUOC | Revisar numa futura atualização do seed (não antes da apresentação) |
| Dermatologia clínica e cirúrgica — HUOC | Dermatologia aparece no HUOC | Coerente |
| Cardiologia — anticoagulação — PROCAPE | Cardiologia é o perfil do PROCAPE | Coerente |
| Consulta de demonstração — CISAM | — | Fila só para a apresentação ao vivo; desativada depois |

Os dados do seed são **sintéticos e ilustrativos**. Na apresentação, dizer isso explicitamente.

## 5. Uso no relatório e na apresentação

- **Contexto:** se a Central de Teleagendamento do NUTES-CISAM for confirmada (seção 6), o projeto deve ser apresentado como **proposta de evolução** de um serviço que já existe numa das unidades, e não como algo inédito.
- **Slide "o que é regra e o que é proposta":** usar as classes da seção 1. Matching automático, nota por critérios e prazos de resposta são **C — proposta do MVP**.
- **Próximos passos:** as pendências da seção 6 viram a seção de validação institucional.

## 6. Fontes e pendências

<a id="fontes"></a>

Fontes citadas pela pesquisa. **Nenhuma foi reaberta ainda.** Quem conferir preenche a data de acesso e o trecho usado, e muda a classe do item na seção 3.

| # | Fonte | URL | Data de acesso | Conferida |
|---|---|---|---|---|
| 1 | Carta de Serviços do Complexo Hospitalar da UPE, 2ª edição | https://drive.google.com/file/d/1SFJcDtMZazzW-oKgifO0caK4R0A7nVdz/view | — | Não |
| 2 | Portal do Complexo Hospitalar — UPE | https://upe.br/complexo-hospitalar/ | — | Não |
| 3 | NUTES-CISAM — Central de Teleagendamento | https://www.upe.br/uh-cisam/nutes/nutes-2/ | — | Não |
| 4 | NUTES-CISAM — abertura de prontuário | https://www.upe.br/uh-cisam/nutes/teleagendamento-abertura-de-prontuario/ | — | Não |
| 5 | Carta de Serviços da SES-PE — consultas e exames | https://cartadeservicos.saude.pe.gov.br/consultas-e-exames/ | — | Não |
| 6 | Regulação em Saúde — Prefeitura do Recife | https://www2.recife.pe.gov.br/servico/regulacao-em-saude?op=ODA1NA%3D%3D | — | Não |
| 7 | Documentos institucionais da UPE | https://upe.br/documentos-institucionais-upe/ | — | Não |
| 8 | DATASUS — CNES | https://cnes.datasus.gov.br/ | — | Não |
| 9 | SIGTAP | http://sigtap.datasus.gov.br/ | — | Não |
| 10 | LGPD — Lei 13.709/2018 | https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm | — | Não |

Pendências, em ordem de prioridade para o relatório:

- [ ] Reabrir as fontes 1, 3, 4, 5 e 8; registrar data de acesso e trecho.
- [ ] Confirmar se a Central de Teleagendamento do NUTES-CISAM está ativa em 2026 e como funciona.
- [ ] Ler e indexar a Carta de Serviços do CHU/UPE (2ª edição).
- [ ] Consultar o CNES atual das três unidades.
- [ ] Confirmar quais serviços dependem de regulação e por quais canais.
- [ ] Confirmar prazos de confirmação, cancelamento e remarcação.
- [ ] Confirmar a regra de reaproveitamento de vaga recusada (impacta ADR-021 e RN-020).
- [ ] Códigos SIGTAP dos serviços e exames (para uma versão futura do catálogo).
- [ ] Orientações de preparo, documentos e consentimento por exame.
- [ ] Validação por profissionais ou pela coordenação das unidades antes de tratar qualquer item como oficial.

A coleta segue as políticas dos sites e não inclui dado pessoal de paciente.
