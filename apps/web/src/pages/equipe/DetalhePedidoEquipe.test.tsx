import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as msw, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import type { components } from '../../shared/api/generated/schema'
import { sessaoOptions } from '../../shared/auth/session'
import { detalheEquipeOptions, filasEquipeOptions, type DetalheEquipe } from './api'
import { textosStatusEquipe } from './estado-fila'

const mensagemPedidoAtualizado = 'Este pedido foi atualizado por outra pessoa. Os dados foram recarregados.'

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const urlDetalhe = '*/api/v1/equipe/solicitacoes/:id'
const urlClassificar = `${urlDetalhe}/classificar`
const fila = { id: uuid(1), nome: 'Dermatologia clínica', unidade_sigla: 'HUOC', especialidade: 'Dermatologia', ativa: true,
  contagem_por_status: { EM_ANALISE: 1, NA_FILA: 0, EM_PROPOSTA: 0, AGENDADA: 0, ATENDIDA: 0, CANCELADA: 0 } }
function resposta(n: number, valor: unknown, origem: components['schemas']['OrigemCriterio'] = 'PACIENTE') {
  return { criterio_id: uuid(n), codigo: `C${n}`, descricao: `Pergunta sintética ${n}`, origem, valor, pontos: 876543 }
}
function evento(tipo: DetalheEquipe['historico'][number]['tipo'], ocorrido_em: string, motivo: string | null = null): DetalheEquipe['historico'][number] {
  return { tipo, ocorrido_em, motivo, ator_usuario_id: uuid(555), status_anterior: null, status_novo: null, visivel_paciente: false }
}
function detalhe(extra: Partial<DetalheEquipe> = {}): DetalheEquipe {
  return { id: uuid(2), fila_id: uuid(1), paciente_nome: 'Paciente Sintética de Demonstração', paciente_cpf: '***.482.***-10',
    status: 'EM_ANALISE', classificacao_risco: null, nota: 987654, data_pedido: '2026-10-31', data_entrada_fila: null,
    turno_preferido: 'TARDE', origem_encaminhamento: 'Encaminhamento sintético da UBS',
    respostas: [resposta(11, false), resposta(12, 0), resposta(13, ''), resposta(14, null), resposta(15, true, 'REGULACAO'), resposta(16, 'OPCAO_A', 'EQUIPE')],
    historico: [evento('CRIADA', '2026-10-31T02:30:00Z', 'Motivo sintético inicial')], ...extra }
}
let pedido: DetalheEquipe
let papel: components['schemas']['Papel']
let leituras: number
let envios: { body: unknown; csrf: string | null }[]
const servidor = setupServer(
  msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(99), papel, nome: null, filas: [fila.id] })),
  msw.get('*/api/v1/equipe/filas', () => HttpResponse.json({ total: 1, itens: [fila] })),
  msw.get(urlDetalhe, () => { leituras++; return HttpResponse.json(pedido) }),
  msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => HttpResponse.json({ total: 0, itens: [] })),
  msw.post(urlClassificar, async ({ request }) => {
    const body = await request.json() as components['schemas']['ClassificacaoEntrada']
    envios.push({ body, csrf: request.headers.get('X-CSRF-Token') })
    pedido = { ...pedido, status: 'NA_FILA', classificacao_risco: body.classificacao_risco,
      historico: [...pedido.historico, evento('CLASSIFICADA', '2026-10-31T12:00:00Z', body.motivo)] }
    return HttpResponse.json(pedido)
  }),
  msw.post('*/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => { pedido = detalhe(); papel = 'ATENDENTE'; leituras = 0; envios = []; http.iniciarSessao(); document.cookie = 'csrf_token=csrf-sintetico; path=/' })
afterEach(() => { servidor.resetHandlers(); vi.restoreAllMocks(); http.iniciarSessao() })
function abrir() {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/equipe/solicitacoes/${uuid(2)}?fila=${uuid(1)}&ordem=chegada&status=EM_ANALISE&pagina=2`]}><Rotas /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, user: userEvent.setup() }
}
const pronto = () => screen.findByRole('heading', { name: 'Paciente Sintética de Demonstração' })
const motivo = () => screen.getByRole('textbox', { name: 'Motivo' }) as HTMLTextAreaElement
async function preencher(user: ReturnType<typeof userEvent.setup>, texto = 'Motivo sintético informado', risco = 'Alto') {
  await user.click(screen.getByRole('radio', { name: risco })); await user.click(motivo()); await user.paste(texto)
}
async function preparar(user: ReturnType<typeof userEvent.setup>, nome = 'Classificar') {
  await user.click(screen.getByRole('button', { name: nome }))
  return screen.findByRole('dialog')
}
function problema(status: number, tipo = 'about:blank', errors?: unknown[]) {
  return HttpResponse.json({ status, type: tipo, title: 'Texto técnico não exibível', detail: 'Informação não exibível', errors }, { status, headers: { 'Content-Type': 'application/problem+json' } })
}
function adiar<T>() { let resolver!: (valor: T) => void; const promise = new Promise<T>((resolve) => { resolver = resolve }); return { promise, resolver } }

describe('UC-007 — detalhe da equipe', () => {
  it('mostra topo e separa respostas sem perder false/zero/vazio, sem pontuação nem autor no HTML', async () => {
    const { container } = abrir(); await pronto()
    const paciente = screen.getByRole('region', { name: 'Respostas do paciente' })
    const equipe = screen.getByRole('region', { name: 'Critérios respondidos pela equipe' })
    for (const texto of ['Não', '0', 'Não respondida', 'Encaminhamento sintético da UBS', 'Tarde']) expect(paciente.textContent).toContain(texto)
    expect(within(paciente).getAllByText('Não respondida')).toHaveLength(2)
    expect(paciente.textContent).not.toContain('Pergunta sintética 15')
    expect(equipe.textContent).toContain('Sim'); expect(equipe.textContent).toContain('OPCAO_A')
    expect(screen.getByText('Dermatologia clínica · HUOC')).toBeTruthy()
    expect(screen.getByText('CPF: ***.482.***-10')).toBeTruthy(); expect(screen.getByText('31/10/2026')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Fila' }).getAttribute('aria-current')).toBe('page')
    expect(screen.getByRole('link', { name: '‹ Voltar para a fila' }).getAttribute('href')).toBe(`/equipe/fila?fila=${uuid(1)}&ordem=chegada&status=EM_ANALISE&pagina=2`)
    for (const proibido of ['987654', '876543', uuid(555), 'Autor', 'Posição', 'Agendamento ativo', 'nota=', 'pontos=']) expect(container.innerHTML).not.toContain(proibido)
    expect(screen.queryByRole('heading', { name: 'Critérios da regulação' })).toBeNull()
  })
  it('respostas da equipe também preservam zero/false/vazio e não mostram perguntas ausentes', async () => {
    pedido.respostas = [resposta(15, false, 'REGULACAO'), resposta(16, 0, 'EQUIPE'), resposta(17, '  ', 'EQUIPE')]
    abrir(); await pronto()
    const equipe = screen.getByRole('region', { name: 'Critérios respondidos pela equipe' })
    for (const texto of ['Não', '0', 'Não respondida']) expect(equipe.textContent).toContain(texto)
    expect(screen.getByText('Nenhuma resposta do paciente registrada.')).toBeTruthy()
    expect(screen.queryByText('Pergunta sintética 11')).toBeNull()
  })
  it('fila ausente do escopo carregado usa Fila sem erro e não mostra bloco vazio da equipe', async () => {
    pedido.fila_id = uuid(20); pedido.respostas = []; abrir(); await pronto()
    expect(screen.queryByRole('region', { name: 'Critérios respondidos pela equipe' })).toBeNull()
    expect(screen.getAllByText('Fila').some((el) => el.tagName === 'P')).toBe(true)
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('falha na consulta complementar de filas não impede ler nem classificar', async () => {
    servidor.use(msw.get('*/api/v1/equipe/filas', () => problema(403)))
    const { user } = abrir(); await pronto(); await preencher(user); await preparar(user)
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it.each(Object.entries(textosStatusEquipe))('status %s tem texto correto e ação só onde permitido', async (status, texto) => {
    pedido.status = status as DetalheEquipe['status']; pedido.classificacao_risco = status === 'EM_ANALISE' ? null : 'AMARELO'
    abrir(); await pronto(); expect(screen.getByText(texto)).toBeTruthy()
    expect(Boolean(screen.queryByRole('button', { name: /^(Reclassificar|Classificar)$/ }))).toBe(['EM_ANALISE', 'NA_FILA'].includes(status))
  })
  it.each(['GESTOR', 'ADMIN'] as const)('%s só lê, inclusive em NA_FILA', async (valor) => {
    papel = valor; pedido.status = 'NA_FILA'; pedido.classificacao_risco = 'AMARELO'; abrir(); await pronto()
    expect(screen.queryByRole('radio')).toBeNull(); expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByRole('region', { name: 'Histórico' })).toBeTruthy()
  })
  it('ordena todo histórico por instante, desempata invertendo sequência e mostra motivos em Recife, com tipo desconhecido neutro', async () => {
    const tipos = ['CRIADA', 'CLASSIFICADA', 'ENTROU_NA_FILA', 'PROPOSTA_ENVIADA', 'CONFIRMADA', 'RECUSADA', 'PROPOSTA_EXPIRADA', 'FALTOU', 'ATENDIDA', 'CANCELADA', 'REENTROU_NA_FILA', 'RECLASSIFICADA'] as const
    const textos = ['Pedido criado', 'Risco classificado', 'Pedido entrou na fila', 'Proposta de vaga enviada', 'Consulta confirmada', 'Paciente informou que esta data não serve', 'Prazo para confirmar encerrado', 'Falta registrada', 'Atendimento realizado', 'Pedido cancelado', 'Pedido voltou à fila', 'Prioridade atualizada']
    pedido.historico = tipos.map((tipo) => evento(tipo, '2026-10-31T02:30:00Z', `Motivo ${tipo}`))
    pedido.historico.splice(2, 0, evento('TIPO_FUTURO' as typeof tipos[number], '2026-11-01T12:00:00Z', 'Motivo mais recente'))
    abrir(); await pronto(); const lista = screen.getByRole('list', { name: 'Histórico do pedido' })
    const itens = within(lista).getAllByRole('listitem')
    expect(itens[0]?.textContent).toContain('Atualização do pedido'); expect(itens[0]?.textContent).toContain('01/11/2026, às 09:00')
    expect(itens[1]?.textContent).toContain('Prioridade atualizada'); expect(itens.at(-1)?.textContent).toContain('Pedido criado')
    for (const texto of textos) expect(lista.textContent).toContain(texto)
    expect(lista.textContent).toContain('30/10/2026, às 23:30'); expect(lista.textContent).toContain('Motivo mais recente')
    expect(lista.textContent).not.toContain('TIPO_FUTURO'); expect(lista.innerHTML).not.toContain(uuid(555))
  })
  it('carregamento e erro com nova tentativa; 404 e 403 escondem dados, inclusive no refetch', async () => {
    const pendente = adiar<Response>()
    servidor.use(msw.get(urlDetalhe, () => pendente.promise))
    const { user, client } = abrir(); await screen.findByText('Carregando pedido…')
    await act(async () => pendente.resolver(problema(503)))
    await screen.findByRole('alert'); servidor.resetHandlers()
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await pronto()
    servidor.use(msw.get(urlDetalhe, () => problema(403, '/problemas/sem-permissao')))
    await act(async () => { await client.invalidateQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey }) })
    await waitFor(() => expect(screen.queryByText(pedido.paciente_nome)).toBeNull())
    expect(screen.getByRole('alert').textContent).toContain('Confira seu acesso')
    servidor.use(msw.get(urlDetalhe, () => problema(404)))
    await act(async () => { await client.invalidateQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey }) })
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Pedido não encontrado ou fora das suas filas.'))
    expect(screen.getByRole('link', { name: '‹ Voltar para a fila' })).toBeTruthy()
  })
})

describe('UC-007 — classificar e reclassificar', () => {
  it('valida risco, motivo obrigatório e limites após trim, com contador', async () => {
    const { user } = abrir(); await pronto()
    await user.click(screen.getByRole('button', { name: 'Classificar' }))
    expect(screen.getByText('Escolha Alto, Médio ou Baixo.')).toBeTruthy()
    expect(document.activeElement).toBe(screen.getAllByRole('radio')[0])
    await preencher(user, '  ab  '); await user.click(screen.getByRole('button', { name: 'Classificar' }))
    expect(screen.getByText('Informe um motivo com 3 a 500 caracteres.')).toBeTruthy(); expect(document.activeElement).toBe(motivo())
    await user.clear(motivo()); await user.paste('x'.repeat(501)); await user.click(screen.getByRole('button', { name: 'Classificar' }))
    expect(screen.queryByRole('dialog')).toBeNull(); expect(screen.getByText(/501\/500/)).toBeTruthy(); expect(leituras).toBe(1)
    await user.clear(motivo()); await user.paste('  abc  '); await preparar(user)
    expect(screen.getByText(/3\/500/)).toBeTruthy()
  })
  it('checagem nova precede diálogo, confirmação mostra efeito, CSRF/corpo exatos, duplo clique envia uma vez e atualiza só detalhe/Fila', async () => {
    const { user, client } = abrir(); await pronto()
    const invalidar = vi.spyOn(client, 'invalidateQueries')
    client.setQueryDefaults(['fila-equipe'], { gcTime: Infinity })
    client.setQueryDefaults(['avisos'], { gcTime: Infinity })
    client.setQueryData(['fila-equipe', fila.id, 'prioridade', 'todos', 1], { total: 1, itens: [] })
    client.setQueryData(['avisos', 'contagem'], { nao_lidos: 3 })
    const pendente = adiar<Response>(); const enviou = vi.fn()
    servidor.use(msw.post(urlClassificar, async ({ request }) => {
      envios.push({ body: await request.json(), csrf: request.headers.get('X-CSRF-Token') }); enviou(); return pendente.promise
    }))
    await preencher(user, '  Motivo sintético  '); const dialogo = await preparar(user)
    expect(leituras).toBe(2)
    expect(dialogo.textContent).toContain('Classificar como Alto. O pedido entra na fila de Dermatologia clínica · HUOC e pode receber uma vaga automaticamente.')
    const confirmar = within(dialogo).getByRole('button', { name: 'Confirmar' })
    await user.dblClick(confirmar); await waitFor(() => expect(enviou).toHaveBeenCalledOnce())
    expect(confirmar.getAttribute('aria-busy')).toBe('true'); expect(confirmar.hasAttribute('disabled')).toBe(true)
    pedido = detalhe({ status: 'NA_FILA', classificacao_risco: 'VERMELHO' })
    await act(async () => pendente.resolver(HttpResponse.json(pedido)))
    await screen.findByText('Pedido classificado como Alto.'); await screen.findByText('Aguardando vaga')
    expect(screen.getByText('Pedido classificado como Alto.').getAttribute('role')).toBe('status')
    expect(envios).toEqual([{ body: { classificacao_risco: 'VERMELHO', motivo: 'Motivo sintético' }, csrf: 'csrf-sintetico' }])
    expect(client.getQueryData(detalheEquipeOptions(pedido.id).queryKey)).toMatchObject({ status: 'NA_FILA', classificacao_risco: 'VERMELHO' })
    expect(client.getQueryState(['fila-equipe', fila.id, 'prioridade', 'todos', 1])?.isInvalidated).toBe(true)
    const chaves = invalidar.mock.calls.map(([filtro]) => filtro?.queryKey?.[0])
    expect(chaves).toContain('filas-equipe'); expect(chaves).toContain('pedido-equipe'); expect(chaves).toContain('fila-equipe')
    expect(chaves.every((chave) => ['filas-equipe', 'pedido-equipe', 'fila-equipe'].includes(String(chave)))).toBe(true)
    expect(client.getQueryState(['avisos', 'contagem'])?.isInvalidated).toBe(false)
  })
  it('NA_FILA vem marcado e confirmação explica de Médio para Alto; limite 500 é aceito', async () => {
    pedido = detalhe({ status: 'NA_FILA', classificacao_risco: 'AMARELO' })
    const { user } = abrir(); await pronto(); expect((screen.getByRole('radio', { name: 'Médio' }) as HTMLInputElement).checked).toBe(true)
    await preencher(user, 'x'.repeat(500)); const dialogo = await preparar(user, 'Reclassificar')
    expect(dialogo.textContent).toContain('Reclassificar de Médio para Alto.')
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))
    await screen.findByText('Pedido classificado como Alto.'); expect(envios).toHaveLength(1)
  })
  it.each([
    { status: 'NA_FILA', classificacao_risco: 'AMARELO' },
    { status: 'EM_ANALISE', classificacao_risco: 'VERDE' },
    { status: 'EM_PROPOSTA', classificacao_risco: 'VERMELHO' },
  ] as const)('checagem detecta mudança para $status/$classificacao_risco sem abrir confirmação, preservando motivo', async (novo) => {
    const { user } = abrir(); await pronto(); await preencher(user)
    pedido = { ...pedido, ...novo }; await user.click(screen.getByRole('button', { name: 'Classificar' }))
    await screen.findByText(mensagemPedidoAtualizado)
    expect(screen.queryByRole('dialog')).toBeNull(); expect(envios).toHaveLength(0)
    if (novo.status !== 'EM_PROPOSTA') expect(motivo().value).toBe('Motivo sintético informado')
    if (novo.status === 'NA_FILA') expect((screen.getByRole('radio', { name: 'Médio' }) as HTMLInputElement).checked).toBe(true)
  })
  it('checagem pendente bloqueia cliques repetidos e não abre diálogo antes da leitura', async () => {
    const { user } = abrir(); await pronto(); await preencher(user)
    const pendente = adiar<Response>(); const leu = vi.fn()
    servidor.use(msw.get(urlDetalhe, () => { leu(); return pendente.promise }))
    const botao = screen.getByRole('button', { name: 'Classificar' }); await user.dblClick(botao)
    await waitFor(() => expect(leu).toHaveBeenCalledOnce()); expect(botao.getAttribute('aria-busy')).toBe('true'); expect(screen.queryByRole('dialog')).toBeNull()
    // O Chromium retira o foco de um botão desabilitado; reproduzimos isso no jsdom.
    ;(document.activeElement as HTMLElement).blur()
    await act(async () => pendente.resolver(HttpResponse.json(pedido))); await screen.findByRole('dialog')
    await user.keyboard('{Escape}'); expect(document.activeElement).toBe(botao)
  })
  it('409 no POST recarrega e mantém motivo; novo risco fica marcado', async () => {
    const { user } = abrir(); await pronto(); await preencher(user); const dialogo = await preparar(user)
    servidor.use(msw.post(urlClassificar, () => { pedido = detalhe({ status: 'NA_FILA', classificacao_risco: 'AMARELO' }); return problema(409, '/problemas/transicao-invalida') }))
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))
    await screen.findByText(mensagemPedidoAtualizado)
    expect(motivo().value).toBe('Motivo sintético informado'); expect((screen.getByRole('radio', { name: 'Médio' }) as HTMLInputElement).checked).toBe(true)
    expect(screen.queryByRole('dialog')).toBeNull(); expect(leituras).toBe(3)
  })
  it('409 seguido de falha na leitura não anuncia recarga como concluída', async () => {
    const { user } = abrir(); await pronto(); await preencher(user); const dialogo = await preparar(user)
    servidor.use(msw.post(urlClassificar, () => problema(409, '/problemas/transicao-invalida')), msw.get(urlDetalhe, () => problema(503)))
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))
    await screen.findByText(/O pedido mudou, mas não foi possível recarregar/)
    expect(screen.queryByText(mensagemPedidoAtualizado)).toBeNull(); expect(motivo().value).toBe('Motivo sintético informado')
  })
  it.each([['motivo', 'string_too_short'], ['classificacao_risco', 'enum']])('422 põe erro e foco em %s após fechar diálogo', async (campo, type) => {
    const { user } = abrir(); await pronto(); await preencher(user); const dialogo = await preparar(user)
    servidor.use(msw.post(urlClassificar, () => problema(422, 'about:blank', [{ loc: ['body', campo], type, msg: 'Texto técnico não exibível' }])))
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))
    await screen.findByRole('alert'); await waitFor(() => expect(document.activeElement).toBe(campo === 'motivo' ? motivo() : screen.getAllByRole('radio')[0]))
    expect(document.activeElement?.getAttribute('aria-describedby')).toContain(campo === 'motivo' ? 'motivo-erro' : 'risco-erro')
    expect(document.body.textContent).not.toContain('Texto técnico'); expect(screen.queryByRole('dialog')).toBeNull()
  })
  it.each([undefined, [{ loc: ['body', 'motivo'], type: 'codigo_futuro', msg: 'Texto técnico não exibível' }]])('422 sem localização reconhecida usa alerta global', async (errors) => {
    const { user } = abrir(); await pronto(); await preencher(user); const dialogo = await preparar(user)
    servidor.use(msw.post(urlClassificar, () => problema(422, 'about:blank', errors)))
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' })); await screen.findByRole('alert')
    expect(screen.queryByText('Texto técnico não exibível')).toBeNull(); expect(motivo().value).toBe('Motivo sintético informado')
  })
  it('403 de escrita é neutro, mantém sessão e não renova; rede não repete POST', async () => {
    const { user, client } = abrir(); await pronto(); await preencher(user); let dialogo = await preparar(user)
    const renovar = vi.fn(); const post = vi.fn(() => problema(403, '/problemas/sem-permissao'))
    servidor.use(msw.post(urlClassificar, post), msw.post('*/api/v1/auth/refresh', renovar))
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' })); await screen.findByRole('alert')
    expect(screen.getByRole('alert').textContent).toContain('Confira seu acesso'); expect(renovar).not.toHaveBeenCalled()
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ papel: 'ATENDENTE' }); expect(post).toHaveBeenCalledOnce()
    const rede = vi.fn(() => HttpResponse.error()); servidor.use(msw.post(urlClassificar, rede))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Classificar' }).hasAttribute('disabled')).toBe(false))
    dialogo = await preparar(user); await user.click(within(dialogo).getByRole('button', { name: 'Confirmar' }))
    await screen.findByText(/Confira o pedido antes de tentar novamente/); expect(rede).toHaveBeenCalledOnce()
  })
  it('refetch de /me preserva formulário e diálogo (B2); mudança do detalhe fecha confirmação antiga', async () => {
    const { user, client } = abrir(); await pronto(); await preencher(user); await preparar(user)
    await act(async () => { await client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    expect(screen.getByRole('dialog')).toBeTruthy(); expect(motivo().value).toBe('Motivo sintético informado')
    pedido = detalhe({ status: 'NA_FILA', classificacao_risco: 'VERDE' })
    await act(async () => { await client.invalidateQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey }) })
    await screen.findByText(mensagemPedidoAtualizado); expect(screen.queryByRole('dialog')).toBeNull()
  })
  it('axe, fieldset/legend, foco inicial, contenção nos dois sentidos, Esc e retorno ao acionador', async () => {
    const { user, container } = abrir(); await pronto()
    expect(screen.getByRole('group', { name: 'Nível de risco' }).tagName).toBe('FIELDSET')
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
    await preencher(user); const acionador = screen.getByRole('button', { name: 'Classificar' }); const dialogo = await preparar(user)
    const voltar = within(dialogo).getByRole('button', { name: 'Voltar' }); const confirmar = within(dialogo).getByRole('button', { name: 'Confirmar' })
    expect(document.activeElement).toBe(voltar); await user.tab({ shift: true }); expect(document.activeElement).toBe(confirmar)
    await user.tab(); expect(document.activeElement).toBe(voltar)
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
    await user.keyboard('{Escape}'); expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(acionador)
  })
  it.each(['POST', 'checagem'] as const)('B1: Sair com %s pendente, novo login e resposta antiga não alteram tela/cache/foco novos', async (etapa) => {
    const { user, client } = abrir(); await pronto(); await preencher(user)
    if (etapa === 'POST') await preparar(user)
    const pendente = adiar<Response>(); const iniciou = vi.fn()
    const responder = () => { iniciou(); return pendente.promise }
    servidor.use(etapa === 'POST' ? msw.post(urlClassificar, responder) : msw.get(urlDetalhe, responder))
    await user.click(screen.getByRole('button', { name: etapa === 'POST' ? 'Confirmar' : 'Classificar' }))
    await waitFor(() => expect(iniciou).toHaveBeenCalledOnce())
    // O diálogo pode fechar por Esc enquanto a operação continua pendente.
    if (etapa === 'POST') await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Sair' })); await screen.findByRole('heading', { name: 'Entrar' })
    servidor.use(msw.post('*/api/v1/auth/login', () => HttpResponse.json({ papel: 'GESTOR', expira_em: '2026-11-01T12:00:00Z' })),
      msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(98), papel: 'GESTOR', nome: null, filas: [fila.id] })))
    await user.type(screen.getByLabelText('CPF ou e-mail'), 'gestor.sintetico@exemplo.test')
    await user.type(screen.getByLabelText('Senha', { exact: true }), 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' })); await screen.findByRole('heading', { name: 'Fila' })
    const menu = screen.getByRole('button', { name: 'Menu' }); menu.focus()
    await act(async () => pendente.resolver(HttpResponse.json(detalhe({ paciente_nome: 'Resposta antiga sintética', status: 'NA_FILA', classificacao_risco: 'VERMELHO' }))))
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ id: uuid(98), papel: 'GESTOR' })
    expect(client.getQueryData(filasEquipeOptions.queryKey)).toBeTruthy()
    expect(JSON.stringify(client.getQueryCache().getAll().map((q) => q.state.data))).not.toContain('Resposta antiga sintética')
    expect(screen.queryByRole('dialog')).toBeNull(); expect(screen.queryByText(/Pedido classificado/)).toBeNull(); expect(document.activeElement).toBe(menu)
  })
  it('formulário e motivo não são persistidos em storage ou URL', async () => {
    const salvar = vi.spyOn(Storage.prototype, 'setItem'); const remover = vi.spyOn(Storage.prototype, 'removeItem'); const limpar = vi.spyOn(Storage.prototype, 'clear')
    const { user } = abrir(); await pronto(); await preencher(user); await preparar(user); await user.keyboard('{Escape}')
    expect(salvar).not.toHaveBeenCalled(); expect(remover).not.toHaveBeenCalled(); expect(limpar).not.toHaveBeenCalled()
    for (const link of screen.getAllByRole('link')) expect(link.getAttribute('href')).not.toContain('Motivo')
  })
})
