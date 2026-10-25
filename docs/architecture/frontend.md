# Frontend

Implementada em `apps/web`, conforme a autorização de 2026-10-21 para a base do [ADR-001](../decisions/ADR-001-stack.md). Inclui Entrar/Criar conta e, na entrega de 2026-10-24, o layout do paciente e Meus atendimentos com resposta à proposta de vaga. As telas completas de novo pedido, detalhe e avisos continuam pendentes.

## Organização e dependências

React e TypeScript com Vite; React Router no modo declarativo; TanStack Query para consultas em memória; React Hook Form e Zod para os formulários de login/cadastro. O transporte usa `fetch` nativo. ESLint, TypeScript e Vitest verificam o frontend; Testing Library, user-event, MSW e vitest-axe cobrem as telas com dados sintéticos. `openapi-typescript` gera os tipos do contrato real do FastAPI.

- `src/app`: rotas e criação do QueryClient.
- `src/layouts`: cabeçalho, navegação responsiva, contador de avisos e saída da área do paciente; layout da equipe ainda vazio. Ambos usam `Outlet` para rotas filhas.
- `src/shared/api`: HTTP, CSRF, Problem Details e tipos gerados.
- `src/shared/auth`: consulta da sessão e guarda por papel.
- `src/pages/auth`: Entrar, CriarConta, etapas, termo, layout público e validação.
- `src/pages/paciente`: consultas tipadas, MeusAtendimentos, CartaoPedido e PropostaVaga.
- `src/shared/ui`: campos, botão, alerta, indicador de etapas, cartão, selo de status, diálogo, abas, paginação e estado vazio.
- `src/shared/mascaras.ts`: funções pequenas de formatação, sem biblioteca de máscaras.
- `src/shared/datas.ts`: datas civis do pedido e horários em `America/Recife`, incluindo prazo e aviso de menos de 24 horas.
- `src/styles`: tokens das referências e CSS responsivo; contraste documentado no README web.
- `src/test`: preparação dos testes; testes ficam junto dos módulos.
- `scripts`: geração e conferência dos tipos OpenAPI.

## Transporte e autenticação

O navegador sempre consulta `/api/v1` na mesma origem. Em desenvolvimento, o Vite encaminha `/api` para `WEB_API_PROXY_TARGET`, definido no `.env` da raiz (exemplo no `.env.example`); não remove nem reescreve o prefixo. Em produção, o Nginx precisa servir `dist` com fallback de rotas para `index.html` e encaminhar `/api` ao backend. `vite preview` apenas inspeciona o build, sem proxy de API.

O cliente envia cookies com `credentials: same-origin`, desabilita cache HTTP e recusa redirects e destinos fora de `/api/v1`. Access e refresh tokens continuam em cookies `httpOnly`, sem leitura ou persistência no JavaScript. Escritas leem o cookie `csrf_token` no momento do envio e preenchem `X-CSRF-Token`, inclusive após a rotação. Login e registro continuam dispensados de CSRF no servidor, como no [ADR-003](../decisions/ADR-003-autenticacao-web.md); o cliente pode enviar o header quando o cookie já existir.

Um `401` fora de `/auth/*` dispara `POST /auth/refresh`. Requisições simultâneas compartilham uma única promessa por instância da aplicação. Um contador identifica `401` atrasado para evitar outra rotação. Depois do refresh, cada pedido é repetido no máximo uma vez; falha de rede, `403`, conflitos e validação não são repetidos. Cancelar um pedido não cancela a renovação compartilhada. Outras abas têm instâncias próprias, sujeitas à tolerância do backend descrita no ADR-003.

Falhas do refresh (HTTP ou rede), exceto o bloqueio específico de troca de senha descrito abaixo, notificam `GerenciarSessao`: cancela as consultas em andamento, limpa o cache da aplicação e marca a sessão como ausente. Respostas tardias das consultas canceladas não repõem dados no cache. Um novo `401` após a única repetição também encerra a sessão. O redirecionamento para `/entrar` guarda apenas o pathname em `location.state.origem`, sem persistência em storage. `rotaAposLogin(location.state)` fornece o destino de retorno para a tela de login e recusa destinos externos ou que repitam `/entrar`.

Cada login/registro bem-sucedido estabelece uma nova época de autenticação no HTTP. Respostas e renovações de épocas antigas são descartadas antes de notificar expiração, bloquear por troca de senha ou devolver dados. Escritas em `/auth/*`, incluindo refresh, são serializadas por instância: login/registro aguardam logout/refresh anteriores, pois o navegador aplica `Set-Cookie` antes de o JavaScript poder rejeitar uma resposta antiga. Essa fila continua existindo ao mudar de época. O CSRF é lido quando o envio efetivamente começa.

Cada operação coordenada tem limite de **15 segundos**, centralizado em `limiteOperacaoAuthMs`, contado a partir do início da operação e abrangendo a leitura do corpo usado pelo cliente. No limite, um `AbortController` cancela o transporte antes de liberar o próximo envio. A continuação também verifica o sinal, além da época, antes de aplicar efeitos; respostas e rejeições tardias continuam tratadas. Cancelar uma autenticação ainda enfileirada rejeita sua espera imediatamente e impede seu envio posterior. Falhas e timeouts não deixam a fila rejeitada; timers e listeners são removidos ao concluir ou abortar. Cancelar uma consulta continua sem cancelar o refresh compartilhado, que possui seu próprio sinal e prazo.

`ApiError` preserva os campos e extensões de Problem Details e a resposta original, inclusive headers como `Retry-After`. Sua `message` vem de `mensagensPorTipo`, que cobre os types anunciados no OpenAPI; tipos desconhecidos, HTML ou corpo inválido geram mensagem genérica, sem expor `title`, `detail` ou o corpo do proxy. Tratamentos específicos devem usar `problem.type`, nunca comparar `detail`. Não há logs de payloads nem de dados da sessão.

`aplicarErrosDeValidacao(error, setError, campos)` integra o `errors` do 422 ao React Hook Form. Recebe a lista explícita de caminhos dos campos do formulário (inclusive índices como `respostas.0.valor`), remove somente o prefixo `body` de `loc`, aplica o primeiro erro de cada campo e foca o primeiro. Erros globais, de parâmetros, de campos extras ou malformados vão para `root.server` com mensagem genérica; erros de outros status retornam `false` para o chamador tratar.

## Sessão e rotas

`GET /me` fornece a sessão; o papel é validado contra `PACIENTE`, `ATENDENTE`, `GESTOR` e `ADMIN`. Papel desconhecido ou erro de consulta concluída fecha o acesso. A consulta não persiste em storage, não usa retries automáticos e é revalidada nas montagens e eventos de foco/reconexão tratados pelo TanStack Query. A guarda mostra espera na consulta inicial; `isFetching` com sessão conhecida mantém a árvore protegida montada, preservando diálogo, foco e escrita em andamento. O resultado concluído de `/me` pode revogar o acesso, mudar o papel ou encaminhar deliberadamente para troca de senha.

`trocar_senha === true` no login ou em `/me` encaminha para `/trocar-senha`, uma rota provisória com título e explicação, sem formulário. O campo gerado é opcional (`true | null`): ausência ou `null` preservam o fluxo habitual; `false` não pertence ao contrato. O payload de `/me` mantém o campo tipado ao validar o papel. O HTTP também mantém em memória o bloqueio informado no login ou pelo Problem Details `403 /problemas/troca-de-senha-obrigatoria`. Esse `403`, inclusive se vier do refresh, encaminha ao fluxo de troca sem expirar a sessão, limpar o cache ou iniciar outra renovação. A sessão consultada permanece em memória ao desmontar a área protegida; sua limpeza ocorre explicitamente na saída, expiração ou nova entrada. `422` de `/auth/trocar-senha` não renova a sessão, e o adaptador de validação associa `errors[].loc = ['body', 'senha_atual']` ao campo `senha_atual`.

**Contrato atualizado (24/10/2026):** o OpenAPI da Parte 1 (`be32204`) foi incorporado e os DTOs foram regenerados com `npm run api:generate`, sem edição manual. O login usa `LoginSaida`; cadastro e refresh continuam com `SessaoSaida`. `/me` usa `EuSaida`, e a decisão de troca recebe os DTOs gerados em vez do adaptador provisório baseado em `unknown`. `TrocaSenhaEntrada` tipa os dois campos da futura tela nos testes do HTTP e do adaptador de formulário. O tratamento de bloqueio compara `ApiError`, status 403 e o URI exato do Problem Details. Os tipos também incluem as rotas `/admin/*` e removem as antigas rotas de suspensão e reativação; não há UI administrativa nem rota de indicadores nesta etapa. A rota de troca de senha permanece provisória e o E2E real continua pendente.

| Rota | Acesso | Conteúdo atual |
| --- | --- | --- |
| `/` | Público | Identificação mínima da base |
| `/entrar` | Público | CPF ou e-mail e senha |
| `/criar-conta` | Público | Cadastro do paciente em três etapas |
| `/trocar-senha` | Mensagem pública, sem dados de conta | Provisória: informa troca obrigatória, sem formulário |
| `/paciente` | PACIENTE | Meus atendimentos, propostas em destaque, abas e paginação |
| `/paciente/novo` | PACIENTE | Provisória: apenas o título Novo pedido |
| `/paciente/solicitacoes/:id` | PACIENTE | Provisória: apenas o título Detalhes do pedido |
| `/paciente/avisos` | PACIENTE | Provisória: apenas o título Avisos |
| `/equipe` | ATENDENTE, GESTOR, ADMIN | Layout vazio |
| Outros caminhos | Público | Mensagem de página inexistente |

Sem sessão, a guarda redireciona para `/entrar` e guarda a origem no mesmo formato usado por `GerenciarSessao`. Login usa a origem interna validada ou o destino do papel informado na resposta, validado também em runtime; registro vai para `/paciente`. Após sucesso, o cache anterior é limpo e a guarda consulta `/me`. Falha de `/me` não oferece reenvio do registro já concluído. Papel diferente exibe acesso negado. A guarda apenas controla a navegação: dono, papel, escopo e suspensão continuam sendo conferidos pelo servidor conforme a [matriz de permissões](../security/access-control.md). Não há regras de negócio ou cálculo de fila no frontend.

O botão Sair chama `POST /auth/logout` pelo cliente HTTP com CSRF e captura a época de origem. Tanto no sucesso quanto na falha, cancela consultas pendentes, limpa o cache e navega para `/entrar`, desde que a época ainda seja a mesma; a limpeza confere novamente a época após aguardar cancelamentos, e o chamador confere a época de encerramento antes de navegar. Uma saída atrasada nunca limpa nem redireciona a sessão nova, inclusive quando ela exige troca de senha. Um bloqueio associado ao QueryClient, somente em memória, impede que voltar à rota reabra a sessão nesta instância após a saída; login ou cadastro bem-sucedido libera uma nova sessão. O cliente não lê nem apaga cookies `httpOnly` diretamente.

A mensagem “Conta criada.” é consumida de `location.state` com navegação `replace`, aparece uma vez e desaparece após seis segundos ou ao usar a navegação do cabeçalho.

Os [comandos de instalação, geração e validação](../../apps/web/README.md) ficam junto do pacote.

## Cadastro em memória (UC-001)

As etapas são Seus dados (nome, CPF, CNS, nascimento e sexo opcional), Contato (município, telefone e e-mail opcional) e Senha e termo (senha, confirmação, aceite obrigatório e lembrete opcional). Zod espelha validações do servidor, inclusive CPF/CNS e data no fuso de Recife. O backend continua sendo a autoridade.

A consulta pública do termo retorna `{ versao, texto }`; seu texto completo é escapado e expansível, sem execução de HTML. A versão enviada é a recebida da API; uma versão recusada exige novo carregamento e aceite. Sem e-mail, o lembrete fica desmarcado e desabilitado, com explicação.

O formulário mantém dados somente em memória, sem storage nem logs. O adaptador 422 é reutilizado; quando necessário, a tela monta a etapa anterior antes de focar o campo. 401/409 não identificam qual dado falhou ou já existia. As mensagens e estados de carregamento/falha/sucesso estão cobertos por testes.

## Meus atendimentos e proposta de vaga

A implementação usa os contratos existentes de [UC-004](../requirements/use-cases/UC-004-confirmar-proposta.md) e [UC-005](../requirements/use-cases/UC-005-pedir-outra-data-ou-cancelar.md), sem alterar endpoints ou regras do backend. A tela consulta `GET /solicitacoes` com `situacao=abertas` ou `encerradas`; o cache inclui filtro e página. A lista visível usa `limit=5` e `offset`, com a resposta `{ total, itens }`. Trocar de aba reinicia a página. O total é de pedidos do próprio paciente, sem informação sobre o tamanho de filas.

Se uma resposta reduzir o total e invalidar a página atual, a tela ajusta o estado para a última página válida antes de exibir o resultado. A nova chave do React Query busca essa página; durante a busca aparece carregamento. Com total zero, o estado retorna à página inicial e exibe o vazio normal, sem repetição de consultas.

Uma consulta complementar busca `situacao=abertas&limit=100&offset=0`. Se não houver proposta e existirem mais itens, avança até a primeira página que contenha proposta ou até esgotar os resultados. As propostas encontradas ficam antes das abas, inclusive no Histórico e fora da página visível; propostas da página visível também entram no destaque, sem duplicar o cartão. Não há varredura das páginas seguintes depois de encontrar uma proposta.

`agendamento_ativo` e `expira_em` vêm da API. A tela mostra a unidade como local, pois o resumo não fornece endereço. Não calcula o prazo de dois dias nem decide a regra de reentrada. Os horários são formatados em Recife; `data_pedido` é uma data civil e não passa por conversão de fuso. Um relógio da interface atualiza o aviso de prazo a cada 30 segundos e ao voltar à aba.

Confirmação e recusa abrem um diálogo antes do POST. As escritas usam o cliente HTTP com CSRF, sem corpo. O `SolicitacaoDetalhe` devolvido atualiza os caches; leituras antigas são canceladas antes dessa atualização, e a lista é revalidada em seguida. A recusa usa mensagem neutra, pois a resposta de sucesso não contém uma mensagem própria. Em `409` `/problemas/proposta-expirada`, a tela mostra imediatamente “O prazo para confirmar terminou. Seu pedido voltou para a fila.” e invalida a lista, sem condicionar o texto ao estado devolvido pela leitura seguinte. Outro conflito informa que o atendimento mudou. Fechar o diálogo durante o envio não esconde uma falha posterior: o erro aparece na tela com caminho para tentar de novo.

O contador usa `GET /avisos/contagem` e é revalidado ao retornar à aba. Lista, busca complementar e contador têm espera e erro com nova tentativa. O menu do celular usa um botão de expansão e navegação comum, com `aria-expanded`, controle por teclado e Esc. O diálogo usa `HTMLDialogElement.showModal()`, título acessível, foco inicial em Voltar, contenção do foco, Esc e restauração ao acionador. Abas têm semântica própria e navegação por setas, Home e End. Os selos apresentam ícone e texto. Nenhum componente do paciente exibe posição, nota, tamanho de fila ou risco, conforme ADR-007.

Fechar o menu sem navegar devolve o foco ao botão Menu, inclusive Esc com o foco ainda no acionador. Ao seguir um link do cabeçalho na mesma aba, o layout fecha o menu e foca seu `main[tabIndex=-1]` depois da mudança de rota, sem temporizadores. Abrir um link em outra aba mantém o comportamento nativo.
