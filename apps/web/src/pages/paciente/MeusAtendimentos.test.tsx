import { QueryClientProvider, focusManager } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, useLocation } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as mockHttp, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { pedidosKey, propostasOptions } from './api'
import type { DetalhePedido, Pedido } from './api'
import { http } from '../../shared/api/http'
import { encerrarSessaoLocal, sessaoOptions } from '../../shared/auth/session'

const unidade = { id: '00000000-0000-4000-8000-000000000002', nome: 'Hospital Sintético', sigla: 'HS' }
const base: Pedido = { id: '00000000-0000-4000-8000-000000000003', status: 'NA_FILA',
  fila: { id: '00000000-0000-4000-8000-000000000004', nome: 'Consulta sintética', unidade },
  data_pedido: '2026-10-20', criada_em: '2026-10-20T11:00:00Z', agendamento_ativo: null }
const proposta: Pedido = { ...base, status: 'EM_PROPOSTA', agendamento_ativo: {
  id: '00000000-0000-4000-8000-000000000005', status: 'PROPOSTO', inicio: '2026-10-28T11:00:00Z',
  expira_em: '2026-10-25T11:00:00Z', unidade, profissional: 'Profissional Sintético' } }
function detalhe(pedido: Pedido): DetalhePedido {
  return { ...pedido, turno_preferido: 'QUALQUER', origem_encaminhamento: null, respostas: [], linha_do_tempo: [],
    agendamento_ativo: pedido.agendamento_ativo ? { ...pedido.agendamento_ativo, fim: '2026-10-28T11:30:00Z', endereco: null } : null }
}
let itens: Pedido[] = []
const servidor = setupServer(
  mockHttp.get('*/api/v1/me', () => HttpResponse.json({ id: '00000000-0000-4000-8000-000000000001', papel: 'PACIENTE', nome: null, filas: null })),
  mockHttp.get('*/api/v1/avisos/contagem', () => HttpResponse.json({ nao_lidos: 3 })),
  mockHttp.get('*/api/v1/solicitacoes', ({ request }) => {
    const params = new URL(request.url).searchParams
    const filtrados = itens.filter((i) => params.get('situacao') === 'encerradas' ? ['ATENDIDA', 'CANCELADA'].includes(i.status) : !['ATENDIDA', 'CANCELADA'].includes(i.status))
    const offset = Number(params.get('offset')), limit = Number(params.get('limit'))
    return HttpResponse.json({ total: filtrados.length, itens: filtrados.slice(offset, offset + limit) })
  }),
  mockHttp.post('*/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => { itens = []; vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-24T13:00:00Z')); document.cookie = 'csrf_token=csrf-sintetico; path=/' })
afterEach(() => { servidor.resetHandlers(); vi.restoreAllMocks(); http.iniciarSessao(); focusManager.setFocused(undefined); document.cookie = 'csrf_token=; max-age=0; path=/' })

function Localizacao() { const l = useLocation(); return <><output data-testid="localizacao">{JSON.stringify(l)}</output><Link to="/paciente">Reabrir paciente</Link><Link to="/entrar">Abrir entrada</Link></> }
function abrir(state?: unknown) {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[{ pathname: '/paciente', state }]}><Rotas /><Localizacao /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, user: userEvent.setup() }
}
async function carregou() { await screen.findByRole('heading', { name: 'Meus atendimentos' }); await waitFor(() => expect(screen.queryByText('Buscando propostas de vaga…')).toBeNull()) }
async function abrirConfirmacao(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Confirmar consulta' }))
  return screen.getByRole('dialog')
}
function problema(status: number, type: string) { return HttpResponse.json({ type: `/problemas/${type}`, title: 'Falha sintética', status }, { status, headers: { 'Content-Type': 'application/problem+json' } }) }

describe('PacienteLayout — sessão, avisos e navegação', () => {
  it.each([false, true])('B1: novo login aguarda logout atrasado com sucesso (trocar_senha: %s)', async (trocarSenha) => {
    let liberar!: (response: Response) => void
    const sair = vi.fn(() => new Promise<Response>((resolve) => { liberar = resolve }))
    servidor.use(mockHttp.post('*/api/v1/auth/logout', sair))
    const entrar = vi.fn(() => HttpResponse.json({
      papel: 'PACIENTE', expira_em: '2026-10-24T14:00:00Z', ...(trocarSenha ? { trocar_senha: true } : {}),
    }))
    servidor.use(mockHttp.post('*/api/v1/auth/login', entrar))
    const pedidos = vi.spyOn(http, 'request')
    const { user, client } = abrir(); await carregou()
    const geracaoAntiga = http.geracaoSessao()
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await waitFor(() => expect(sair).toHaveBeenCalledTimes(1))
    const saida = pedidos.mock.results[pedidos.mock.calls.findIndex(([path]) => path === '/auth/logout')]!.value as Promise<unknown>
    await user.click(screen.getByRole('link', { name: 'Abrir entrada' }))
    await user.type(screen.getByLabelText('CPF ou e-mail'), 'paciente@exemplo.test')
    await user.type(screen.getByLabelText('Senha'), 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(entrar).not.toHaveBeenCalled()
    await act(async () => {
      liberar(new HttpResponse(null, { status: 204, headers: { 'Set-Cookie': 'access_token=; Max-Age=0; HttpOnly; Path=/' } }))
      await saida.catch(() => undefined)
    })
    const destino = trocarSenha ? '/trocar-senha' : '/paciente'
    await screen.findByRole('heading', { name: trocarSenha ? 'Troca de senha obrigatória' : 'Meus atendimentos' })
    client.setQueryDefaults(['nova-sessao'], { gcTime: Infinity })
    client.setQueryData(['nova-sessao'], { id: 'preservado' })
    const geracao = http.geracaoSessao()
    await act(async () => {
      // Mesmo uma limpeza local da geração antiga que termine depois não
      // pode apagar o cache ou a marca de troca obrigatória da sessão nova.
      expect(await encerrarSessaoLocal(client, geracaoAntiga)).toBe(false)
    })
    expect(JSON.parse(screen.getByTestId('localizacao').textContent!).pathname).toBe(destino)
    expect(client.getQueryData(['nova-sessao'])).toEqual({ id: 'preservado' })
    expect(http.geracaoSessao()).toBe(geracao)
    expect(http.trocaDeSenhaObrigatoria()).toBe(trocarSenha)
    expect(entrar).toHaveBeenCalledTimes(1)
    if (!trocarSenha) expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ papel: 'PACIENTE' })
  })

  it.each([false, true])('B2: foco/reconexão preserva diálogo e escrita em andamento (enviando: %s)', async (enviando) => {
    itens = [proposta]
    let concluirEscrita!: (response: Response) => void
    const confirmar = vi.fn(() => new Promise<Response>((resolve) => { concluirEscrita = resolve }))
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', confirmar))
    const { user, client } = abrir(); await carregou()
    const dialogo = await abrirConfirmacao(user)
    if (enviando) {
      await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
      await waitFor(() => expect(confirmar).toHaveBeenCalledTimes(1))
    }
    let concluirMe!: (response: Response) => void
    const revalidar = vi.fn(() => new Promise<Response>((resolve) => { concluirMe = resolve }))
    servidor.use(mockHttp.get('*/api/v1/me', revalidar))
    await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true) })
    await waitFor(() => expect(revalidar).toHaveBeenCalledTimes(1))
    expect(client.isFetching({ queryKey: sessaoOptions.queryKey })).toBe(1)
    expect(screen.getByRole('dialog')).toBe(dialogo)
    expect(screen.getByRole('heading', { name: 'Meus atendimentos' })).toBeTruthy()
    expect(screen.queryByText('Verificando sessão…')).toBeNull()
    if (enviando) expect((within(dialogo).getByRole('button', { name: 'Aguarde…' }) as HTMLButtonElement).disabled).toBe(true)
    else expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: 'Voltar' }))
    await act(async () => { concluirMe(HttpResponse.json({ id: 'sintetico', papel: 'PACIENTE', nome: null, filas: null })) })
    await waitFor(() => expect(client.isFetching({ queryKey: sessaoOptions.queryKey })).toBe(0))
    expect(screen.getByRole('dialog')).toBe(dialogo)
    if (enviando) {
      await act(async () => { itens = []; concluirEscrita(HttpResponse.json(detalhe({ ...proposta, status: 'AGENDADA', agendamento_ativo: { ...proposta.agendamento_ativo!, status: 'CONFIRMADO' } }))) })
      await screen.findByText('Consulta confirmada')
      expect(confirmar).toHaveBeenCalledTimes(1)
    }
  })

  it.each(['ok', 'rede', 'http'])('sai com CSRF, cancela consultas e limpa cache, mesmo com falha: %s', async (resultado) => {
    const sair = vi.fn(({ request }: { request: Request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
      if (resultado === 'rede') return HttpResponse.error()
      return new HttpResponse(null, { status: resultado === 'ok' ? 204 : 503 })
    })
    servidor.use(mockHttp.post('*/api/v1/auth/logout', sair))
    const { user, client } = abrir(); await carregou()
    client.setQueryData(['dados-sinteticos'], { id: 'teste' })
    let signal: AbortSignal | undefined
    const pendente = client.fetchQuery({ queryKey: ['pendente'], queryFn: ({ signal: s }) => {
      signal = s
      return new Promise((resolve) => s.addEventListener('abort', () => resolve('resposta tardia')))
    } }).catch(() => undefined)
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' }); await pendente
    expect(sair).toHaveBeenCalledTimes(1)
    expect(signal?.aborted).toBe(true)
    expect(client.getQueryCache().getAll()).toHaveLength(0)
    // Mesmo se os cookies do servidor sobreviverem à falha, voltar não abre a área nesta instância.
    await user.click(screen.getByRole('link', { name: 'Reabrir paciente' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    expect(screen.queryByRole('main', { name: 'Área do paciente' })).toBeNull()
  })
  it('mostra contador e atualiza ao voltar à aba', async () => {
    const contador = vi.fn(() => HttpResponse.json({ nao_lidos: 7 }))
    const { client } = abrir(); await screen.findByRole('link', { name: 'Avisos, 3 não lidos' })
    servidor.use(mockHttp.get('*/api/v1/avisos/contagem', contador))
    await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true) })
    await screen.findByRole('link', { name: 'Avisos, 7 não lidos' })
    await waitFor(() => expect(client.isFetching()).toBe(0))
    expect(contador).toHaveBeenCalled()
  })
  it('recupera falha do contador', async () => {
    servidor.use(mockHttp.get('*/api/v1/avisos/contagem', () => HttpResponse.error()))
    const { user } = abrir(); await screen.findByText('Não foi possível contar os avisos.')
    servidor.use(mockHttp.get('*/api/v1/avisos/contagem', () => HttpResponse.json({ nao_lidos: 0 })))
    await user.click(screen.getByRole('button', { name: 'Tentar contar de novo' }))
    await screen.findByRole('link', { name: 'Avisos, 0 não lidos' })
  })
  it('menu abre por teclado, Esc restaura foco e links navegam a rotas mínimas', async () => {
    const { user } = abrir(); await carregou()
    const menu = screen.getByRole('button', { name: 'Menu' }); menu.focus()
    await user.keyboard('{Enter}')
    expect(menu.getAttribute('aria-expanded')).toBe('true')
    await user.tab(); expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Meus atendimentos' }))
    await user.keyboard('{Escape}')
    expect(menu.getAttribute('aria-expanded')).toBe('false'); expect(document.activeElement).toBe(menu)
    await user.keyboard('{Enter}'); await user.click(screen.getByRole('link', { name: 'Novo pedido' }))
    await screen.findByRole('heading', { name: 'Novo pedido' })
    expect(menu.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('form')).toBeNull()
  })
  it('I2: Enter no menu leva o foco ao conteúdo da nova rota, inclusive ao voltar', async () => {
    const { user } = abrir(); await carregou()
    const menu = screen.getByRole('button', { name: 'Menu' })
    menu.focus(); await user.keyboard('{Enter}')
    await user.tab(); await user.tab()
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Novo pedido' }))
    await user.keyboard('{Enter}')
    await screen.findByRole('heading', { name: 'Novo pedido' })
    expect(menu.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).not.toBe(document.body)
    expect(document.activeElement).toBe(screen.getByRole('main', { name: 'Área do paciente' }))

    menu.focus(); await user.keyboard('{Enter}'); await user.tab(); await user.keyboard('{Enter}')
    await screen.findByRole('heading', { name: 'Meus atendimentos' })
    expect(document.activeElement).toBe(screen.getByRole('main', { name: 'Área do paciente' }))
  })
  it('I2: Esc no próprio acionador fecha o menu e preserva o foco', async () => {
    const { user } = abrir(); await carregou()
    const menu = screen.getByRole('button', { name: 'Menu' })
    menu.focus(); await user.keyboard('{Enter}'); await user.keyboard('{Escape}')
    expect(menu.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(menu)
  })
  it('consome Conta criada uma única vez e remove da navegação', async () => {
    const { user } = abrir({ mensagem: 'Conta criada.' }); await screen.findByText('Conta criada.')
    await waitFor(() => expect(JSON.parse(screen.getByTestId('localizacao').textContent!).state).toEqual({}))
    await user.click(screen.getByRole('link', { name: 'Novo pedido' })); await user.click(screen.getByRole('link', { name: 'Meus atendimentos' }))
    expect(screen.queryByText('Conta criada.')).toBeNull()
  })
})

describe('Meus atendimentos — lista e ADR-007', () => {
  it('I1: total de 6 para 5 corrige a página e busca os itens sem mostrar vazio enganoso', async () => {
    itens = Array.from({ length: 6 }, (_, i) => ({ ...base, id: `${i}`, fila: { ...base.fila, nome: `Pedido sintético ${i}` } }))
    const { user, client } = abrir(); await carregou()
    await user.click(screen.getByRole('button', { name: 'Próxima' }))
    await screen.findByRole('heading', { name: 'Pedido sintético 5' })
    itens = itens.slice(0, 5)
    const offsets: number[] = []
    let liberar!: (response: Response) => void
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => {
      const params = new URL(request.url).searchParams
      if (params.get('limit') !== '5') return HttpResponse.json({ total: 5, itens })
      const offset = Number(params.get('offset')); offsets.push(offset)
      return offset === 5 ? HttpResponse.json({ total: 5, itens: [] })
        : new Promise<Response>((resolve) => { liberar = resolve })
    }))
    await act(async () => { await client.invalidateQueries({ queryKey: pedidosKey }) })
    await waitFor(() => expect(offsets).toEqual([5, 0]))
    expect(screen.getByText('Carregando seus pedidos…')).toBeTruthy()
    expect(screen.queryByText('Você ainda não tem pedidos')).toBeNull()
    await act(async () => { liberar(HttpResponse.json({ total: 5, itens })) })
    await screen.findByRole('heading', { name: 'Pedido sintético 0' })
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(5)
    expect(screen.queryByRole('navigation', { name: 'Páginas dos seus pedidos' })).toBeNull()
    expect(offsets).toEqual([5, 0])
  })
  it('I1: total zero restaura a página inicial sem loop e permite novos itens no próximo refetch', async () => {
    itens = Array.from({ length: 6 }, (_, i) => ({ ...base, id: `${i}`, fila: { ...base.fila, nome: `Pedido sintético ${i}` } }))
    const { user, client } = abrir(); await carregou()
    await user.click(screen.getByRole('button', { name: 'Próxima' }))
    await screen.findByRole('heading', { name: 'Pedido sintético 5' })
    const anteriores = itens.slice(0, 5); itens = []
    const offsets: number[] = []
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => {
      const params = new URL(request.url).searchParams
      const offset = Number(params.get('offset')), limit = Number(params.get('limit'))
      if (limit === 5) offsets.push(offset)
      return HttpResponse.json({ total: itens.length, itens: itens.slice(offset, offset + limit) })
    }))
    await act(async () => { await client.invalidateQueries({ queryKey: pedidosKey }) })
    await screen.findByText('Você ainda não tem pedidos')
    await waitFor(() => expect(client.isFetching({ queryKey: pedidosKey })).toBe(0))
    expect(offsets).toEqual([5, 0])
    itens = anteriores
    await act(async () => { await client.invalidateQueries({ queryKey: pedidosKey }) })
    await screen.findByRole('heading', { name: 'Pedido sintético 0' })
    expect(offsets).toEqual([5, 0, 0])
  })
  it('I1: resposta tardia da página antiga não altera a aba atual nem sua paginação', async () => {
    itens = Array.from({ length: 6 }, (_, i) => ({ ...base, id: `${i}`, fila: { ...base.fila, nome: `Pedido sintético ${i}` } }))
    itens.push({ ...base, id: 'historico', status: 'ATENDIDA', fila: { ...base.fila, nome: 'Pedido realizado' } })
    const { user, client } = abrir(); await carregou()
    await user.click(screen.getByRole('button', { name: 'Próxima' }))
    await screen.findByRole('heading', { name: 'Pedido sintético 5' })
    let liberar!: (response: Response) => void
    let signal: AbortSignal | undefined
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => {
      const params = new URL(request.url).searchParams
      if (params.get('offset') !== '5') return
      signal = request.signal
      return new Promise<Response>((resolve) => { liberar = resolve })
    }))
    let revalidacao!: Promise<void>
    await act(async () => { revalidacao = client.invalidateQueries({ queryKey: [...pedidosKey, 'abertas', 1] }) })
    await waitFor(() => expect(liberar).toBeTypeOf('function'))
    await user.click(screen.getByRole('tab', { name: 'Histórico' }))
    await screen.findByRole('heading', { name: 'Pedido realizado' })
    expect(signal?.aborted).toBe(true)
    await act(async () => { liberar(HttpResponse.json({ total: 0, itens: [] })); await revalidacao })
    expect(screen.getByRole('tab', { name: 'Histórico' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('heading', { name: 'Pedido realizado' })).toBeTruthy()
    await user.click(screen.getByRole('tab', { name: 'Em andamento' }))
    await screen.findByRole('heading', { name: 'Pedido sintético 0' })
    expect(screen.getByText('Página 1 de 2')).toBeTruthy()
  })
  it('troca situacao nas abas, pagina e reinicia pagina ao trocar aba', async () => {
    itens = Array.from({ length: 6 }, (_, i) => ({ ...base, id: `${i}`, fila: { ...base.fila, nome: `Pedido sintético ${i}` } }))
    itens.push({ ...base, id: 'historico', status: 'ATENDIDA', fila: { ...base.fila, nome: 'Pedido realizado' } })
    const { user } = abrir(); await screen.findByRole('heading', { name: 'Pedido sintético 0' })
    expect(screen.queryByRole('heading', { name: 'Pedido sintético 5' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Próxima' })); await screen.findByRole('heading', { name: 'Pedido sintético 5' })
    expect(screen.getByText('Página 2 de 2')).toBeTruthy()
    await user.click(screen.getByRole('tab', { name: 'Histórico' })); await screen.findByRole('heading', { name: 'Pedido realizado' })
    await user.keyboard('{ArrowLeft}'); await screen.findByRole('heading', { name: 'Pedido sintético 0' })
    expect(screen.getByText('Página 1 de 2')).toBeTruthy()
  })
  it('mostra vazio e permite navegar para novo pedido', async () => {
    const { user } = abrir(); await screen.findByText('Você ainda não tem pedidos')
    await user.click(screen.getByRole('link', { name: 'Fazer um pedido' })); await screen.findByRole('heading', { name: 'Novo pedido' })
  })
  it('recupera falha de rede da lista com nova tentativa', async () => {
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => new URL(request.url).searchParams.get('limit') === '100' ? HttpResponse.json({ total: 0, itens: [] }) : HttpResponse.error()))
    const { user } = abrir(); await screen.findByText('Não foi possível carregar seus pedidos.')
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', () => HttpResponse.json({ total: 1, itens: [base] })))
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await screen.findByText('Aguardando vaga')
  })
  it('exibe todos os status em linguagem simples sem dados internos', async () => {
    const estados = ['EM_ANALISE', 'NA_FILA', 'AGENDADA', 'ATENDIDA', 'CANCELADA'] as const
    const textos = ['Pedido em análise', 'Aguardando vaga', 'Consulta marcada', 'Atendimento realizado', 'Pedido cancelado'] as const
    itens = estados.map((status, i) => ({ ...base, id: `${i}`, status }))
    const { user, container } = abrir(); await screen.findByText(textos[0])
    for (const texto of textos.slice(0, 3)) expect(screen.getByText(texto)).toBeTruthy()
    expect(container.textContent).not.toMatch(/posição|nota|risco|tamanho da fila/i)
    await user.click(screen.getByRole('tab', { name: 'Histórico' })); await screen.findByText(textos[3])
    expect(screen.getByText(textos[4])).toBeTruthy()
    expect(container.textContent).not.toMatch(/posição|nota|risco|tamanho da fila/i)
  })
  it('consulta marcada tem local, horário, profissional e tolerância', async () => {
    itens = [{ ...proposta, status: 'AGENDADA', agendamento_ativo: { ...proposta.agendamento_ativo!, status: 'CONFIRMADO', expira_em: null } }]
    abrir(); await screen.findByText('Consulta marcada')
    expect(screen.getByText('quarta-feira, 28/10, às 08:00')).toBeTruthy()
    expect(screen.getByText('Local: Hospital Sintético (HS)')).toBeTruthy()
    expect(screen.getByText('Profissional: Profissional Sintético')).toBeTruthy()
    expect(screen.getByText('Chegue com antecedência. Tolerância de atraso: 1 hora.')).toBeTruthy()
  })
})

describe('UC-004/UC-005 — proposta', () => {
  beforeEach(() => { itens = [proposta] })
  it('destaca proposta antes das abas, prazo de Recife e menos de 24 horas', async () => {
    const { container } = abrir(); await screen.findByRole('region', { name: 'Propostas de vaga' })
    expect(screen.getByText('quarta-feira, 28/10, às 08:00')).toBeTruthy()
    expect(screen.getByText('25/10 às 08:00')).toBeTruthy()
    expect(screen.getByText('Faltam 22 horas')).toBeTruthy()
    const destaque = screen.getByRole('region', { name: 'Propostas de vaga' })
    expect(destaque.compareDocumentPosition(screen.getByRole('tablist')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.textContent).not.toMatch(/posição|nota|risco|tamanho da fila/i)
  })
  it('não exibe urgência com 24 horas ou mais e impede ação depois do prazo', async () => {
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-10-24T11:00:00Z'))
    const { unmount } = abrir(); await screen.findByRole('button', { name: 'Confirmar consulta' })
    expect(screen.queryByText(/Faltam/)).toBeNull(); unmount()
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-10-25T11:00:00Z'))
    abrir(); await screen.findByText('O prazo para responder terminou.')
    expect(screen.queryByRole('button', { name: 'Confirmar consulta' })).toBeNull()
  })
  it('confirma com CSRF, mostra sucesso e atualiza para AGENDADA', async () => {
    const confirmar = vi.fn(({ request }: { request: Request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
      itens = [{ ...proposta, status: 'AGENDADA', agendamento_ativo: { ...proposta.agendamento_ativo!, status: 'CONFIRMADO' } }]
      return HttpResponse.json(detalhe(itens[0]!))
    })
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', confirmar))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    expect(within(dialogo).getByText('Confirmar a consulta de quarta-feira, 28/10, às 08:00?')).toBeTruthy()
    expect(confirmar).not.toHaveBeenCalled()
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await screen.findByText('Consulta confirmada'); await screen.findByText('Consulta marcada')
    expect(confirmar).toHaveBeenCalledTimes(1); expect(screen.queryByRole('dialog')).toBeNull()
  })
  it('409 proposta-expirada mostra texto literal imediatamente, mesmo com lista ainda EM_PROPOSTA', async () => {
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => problema(409, 'proposta-expirada')))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await screen.findByText('O prazo para confirmar terminou. Seu pedido voltou para a fila.')
    // O mock preserva EM_PROPOSTA, como pode acontecer antes do Worker.
    await screen.findByText('Você tem uma vaga para confirmar')
  })
  it('recusa só após explicação; envia CSRF e usa texto neutro', async () => {
    const recusar = vi.fn(({ request }: { request: Request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
      itens = [base]; return HttpResponse.json(detalhe(base))
    })
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/recusar', recusar))
    const { user } = abrir(); await user.click(await screen.findByRole('button', { name: 'Esta data não serve' }))
    const dialogo = screen.getByRole('dialog')
    expect(dialogo.textContent).toContain('Você continua na fila e vamos procurar outra data.')
    expect(dialogo.textContent).not.toMatch(/posição|fim da fila/i)
    expect(recusar).not.toHaveBeenCalled()
    await user.click(within(dialogo).getByRole('button', { name: 'Esta data não serve' }))
    await screen.findByText('Aguardando vaga'); expect(recusar).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Você continua na fila e vamos procurar outra data.').getAttribute('role')).toBe('status')
  })
  it('falha no envio permite tentar novamente no diálogo', async () => {
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => HttpResponse.error()))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await within(dialogo).findByText('Não foi possível conectar. Confira sua internet e tente de novo.')
    expect(within(dialogo).getByRole('button', { name: 'Tentar de novo' })).toBeTruthy()
  })
  it('mantém transição confirmada se o refetch das propostas falhar', async () => {
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => {
      const confirmado: Pedido = { ...proposta, status: 'AGENDADA', agendamento_ativo: { ...proposta.agendamento_ativo!, status: 'CONFIRMADO' } }
      itens = [confirmado]
      servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => new URL(request.url).searchParams.get('limit') === '100'
        ? HttpResponse.error() : HttpResponse.json({ total: 1, itens })))
      return HttpResponse.json(detalhe(confirmado))
    }))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await screen.findByText('Consulta marcada'); await screen.findByText('Não foi possível buscar propostas de vaga.')
    expect(screen.queryByRole('region', { name: 'Propostas de vaga' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Confirmar consulta' })).toBeNull()
  })
  it('409 por outra aba reconcilia lista nova mesmo se a busca complementar falhar', async () => {
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => {
      itens = [{ ...proposta, status: 'AGENDADA', agendamento_ativo: { ...proposta.agendamento_ativo!, status: 'CONFIRMADO' } }]
      servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => new URL(request.url).searchParams.get('limit') === '100'
        ? HttpResponse.error() : HttpResponse.json({ total: 1, itens })))
      return problema(409, 'transicao-invalida')
    }))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await screen.findByText('Consulta marcada'); await screen.findByText('Não foi possível buscar propostas de vaga.')
    expect(screen.queryByRole('region', { name: 'Propostas de vaga' })).toBeNull()
    expect(screen.getByText('Este atendimento mudou. Confira os dados atualizados do seu pedido.')).toBeTruthy()
  })
  it('409 não reoferece ação da lista antiga se só a busca complementar atualizar', async () => {
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => {
      servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => new URL(request.url).searchParams.get('limit') === '100'
        ? HttpResponse.json({ total: 0, itens: [] }) : HttpResponse.error()))
      return problema(409, 'transicao-invalida')
    }))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await screen.findByText('Não foi possível carregar seus pedidos.')
    expect(screen.queryByRole('region', { name: 'Propostas de vaga' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Confirmar consulta' })).toBeNull()
  })
  it('mostra erro e nova tentativa mesmo se Esc fechar o diálogo durante envio', async () => {
    let liberar!: () => void
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', async () => {
      await new Promise<void>((resolve) => { liberar = resolve })
      return HttpResponse.error()
    }))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await waitFor(() => expect(liberar).toBeDefined())
    within(dialogo).getByRole('button', { name: 'Voltar' }).focus()
    await user.keyboard('{Escape}'); expect(screen.queryByRole('dialog')).toBeNull()
    liberar()
    await screen.findByText('Não foi possível conectar. Confira sua internet e tente de novo.')
    await user.click(screen.getByRole('button', { name: 'Rever e tentar de novo' }))
    expect(screen.getByRole('dialog')).toBeTruthy()
  })
  it('recupera falha da busca complementar sem perder a lista', async () => {
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => new URL(request.url).searchParams.get('limit') === '100'
      ? HttpResponse.error() : HttpResponse.json({ total: 1, itens: [base] })))
    const { user } = abrir(); await screen.findByText('Aguardando vaga')
    await screen.findByText('Não foi possível buscar propostas de vaga.')
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', () => HttpResponse.json({ total: 1, itens: [proposta] })))
    await user.click(screen.getByRole('button', { name: 'Tentar buscar propostas de novo' }))
    await screen.findByRole('region', { name: 'Propostas de vaga' })
  })
  it('axe na tela e diálogo, foco inicial, contenção nos dois sentidos e Esc restaura', async () => {
    const { user, container } = abrir(); await carregou()
    const conferir = async () => expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
    await conferir()
    const abrirBotao = screen.getByRole('button', { name: 'Confirmar consulta' })
    await user.click(abrirBotao); const dialogo = screen.getByRole('dialog')
    expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: 'Voltar' }))
    await user.tab({ shift: true }); expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: 'Confirmar consulta' }))
    await user.tab(); expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: 'Voltar' }))
    await conferir(); await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(abrirBotao)
  })
  it('não usa armazenamento do navegador durante confirmação', async () => {
    const spies = ['setItem', 'removeItem', 'clear'].map((m) => vi.spyOn(Storage.prototype, m as 'setItem'))
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => HttpResponse.json(detalhe(proposta))))
    const { user } = abrir(); const dialogo = await abrirConfirmacao(user)
    await user.click(within(dialogo).getByRole('button', { name: 'Confirmar consulta' })); await screen.findByText('Consulta confirmada')
    for (const spy of spies) expect(spy).not.toHaveBeenCalled()
  })
})

describe('Busca complementar de propostas — paginação com parada antecipada', () => {
  it.each([0, 100, 200, -1])('para ao encontrar proposta ou esgotar: offset %s', async (onde) => {
    const offsets: number[] = []
    servidor.use(mockHttp.get('*/api/v1/solicitacoes', ({ request }) => {
      const params = new URL(request.url).searchParams
      expect(params.get('situacao')).toBe('abertas'); expect(params.get('limit')).toBe('100')
      const offset = Number(params.get('offset')); offsets.push(offset)
      const pagina = Array.from({ length: offset === 200 ? 1 : 100 }, (_, i) => ({ ...base, id: `${offset + i}` }))
      if (offset === onde) pagina[0] = proposta
      return HttpResponse.json({ total: 201, itens: pagina })
    }))
    const client = criarQueryClient(); const encontrados = await client.fetchQuery(propostasOptions)
    expect(offsets).toEqual(onde === 0 ? [0] : onde === 100 ? [0, 100] : [0, 100, 200])
    expect(encontrados).toEqual(onde === -1 ? [] : [proposta]); client.clear()
  })
  it('proposta fora da página visível aparece no topo', async () => {
    itens = Array.from({ length: 6 }, (_, i) => ({ ...base, id: `${i}`, fila: { ...base.fila, nome: `Pedido ${i}` } }))
    itens.push(proposta)
    abrir(); await screen.findByRole('region', { name: 'Propostas de vaga' })
    expect(screen.getByText('Você tem uma vaga para confirmar')).toBeTruthy()
    expect(screen.getByText('Página 1 de 2')).toBeTruthy()
  })
})
