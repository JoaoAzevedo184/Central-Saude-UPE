import { QueryClientProvider, focusManager } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as msw, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import { sessaoOptions } from '../../shared/auth/session'
import type { components } from '../../shared/api/generated/schema'

type Item = components['schemas']['ItemPainel']
type Fila = components['schemas']['FilaEquipeSaida']
const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const fila = (n = 1, extra: Partial<Fila> = {}): Fila => ({ id: uuid(n), nome: `Fila sintética ${n}`, especialidade: 'Cardiologia',
  unidade_sigla: 'PROCAPE', ativa: true, contagem_por_status: { EM_ANALISE: 3, NA_FILA: 12, EM_PROPOSTA: 1, AGENDADA: 2, ATENDIDA: 4, CANCELADA: 0 }, ...extra })
const item = (n = 1, extra: Partial<Item> = {}): Item => ({ id: uuid(n + 100), paciente_nome: `Sintético ${n} S.`, paciente_cpf: '***.482.***-10',
  status: 'NA_FILA', posicao: n, classificacao_risco: 'VERMELHO', nota: 987654, data_entrada_fila: '2026-10-29T02:30:00Z',
  ultima_mudanca: { tipo: 'ENTROU_NA_FILA', ocorrido_em: '2026-10-29T02:30:00Z' }, ...extra })
let filas: Fila[]
let itens: Item[]
let papel: components['schemas']['Papel']
let consultas: URL[]
let consultasFilas: URL[]
const servidor = setupServer(
  msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(99), papel, nome: null, filas: filas.map((f) => f.id) })),
  msw.get('*/api/v1/equipe/filas', ({ request }) => {
    const url = new URL(request.url); consultasFilas.push(url)
    const inicio = Number(url.searchParams.get('offset')); const limite = Number(url.searchParams.get('limit'))
    return HttpResponse.json({ total: filas.length, itens: filas.slice(inicio, inicio + limite) })
  }),
  msw.get('*/api/v1/equipe/filas/:id/solicitacoes', ({ request }) => {
    const url = new URL(request.url); consultas.push(url)
    const inicio = Number(url.searchParams.get('offset'))
    return HttpResponse.json({ total: itens.length, itens: itens.slice(inicio, inicio + 20) })
  }),
  msw.get('*/api/v1/solicitacoes', () => HttpResponse.json({ total: 0, itens: [] })),
  msw.get('*/api/v1/avisos/contagem', () => HttpResponse.json({ nao_lidos: 0 })),
  msw.post('*/api/v1/auth/logout', ({ request }) => {
    expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
    return new HttpResponse(null, { status: 204 })
  }),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => {
  filas = [fila()]; itens = [item()]; papel = 'ATENDENTE'; consultas = []; consultasFilas = []
  http.iniciarSessao(); document.cookie = 'csrf_token=csrf-sintetico; path=/'
})
afterEach(() => { servidor.resetHandlers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); http.iniciarSessao(); focusManager.setFocused(undefined) })
function Navegacao() {
  const location = useLocation(); const navigate = useNavigate()
  return <><output data-testid="url">{location.pathname}{location.search}</output>
    <button onClick={() => void navigate(-1)}>História anterior</button></>
}
function abrir(path = '/equipe/fila') {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Rotas /><Navegacao /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, user: userEvent.setup() }
}
const tabela = () => screen.findByRole('table', { name: /Pedidos da fila/ })
function problema(status: number, tipo = 'sem-permissao') { return HttpResponse.json({ type: `/problemas/${tipo}`, status, title: 'Falha sintética' }, { status }) }
function adiar<T>() { let resolver!: (valor: T) => void; const promise = new Promise<T>((resolve) => { resolver = resolve }); return { promise, resolver } }

describe('RF-031/032 — layout e painel da equipe', () => {
  it.each([['ATENDENTE', 'Atendente'], ['GESTOR', 'Gestor'], ['ADMIN', 'Administrador']] as const)('mostra papel %s, menu atual e sai com CSRF', async (valor, texto) => {
    papel = valor; const { user, client } = abrir()
    await tabela()
    expect(screen.getByText(texto)).toBeTruthy()
    expect(screen.queryByText(`${texto} · PROCAPE`)).toBeNull()
    expect(screen.getByRole('link', { name: 'Fila' }).getAttribute('aria-current')).toBe('page')
    expect(screen.queryByRole('link', { name: 'Indicadores' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Pular para o conteúdo' })).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    expect(client.getQueryData(['fila-equipe'])).toBeUndefined()
  })
  it('abre e fecha Menu com teclado e restaura foco por Escape', async () => {
    const { user } = abrir(); await tabela()
    const menu = screen.getByRole('button', { name: 'Menu' }); menu.focus()
    expect(menu.getAttribute('aria-expanded')).toBe('false')
    await user.keyboard('{Enter}'); expect(menu.getAttribute('aria-expanded')).toBe('true')
    await user.tab(); expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Fila' }))
    await user.keyboard('{Escape}'); expect(menu.getAttribute('aria-expanded')).toBe('false'); expect(document.activeElement).toBe(menu)
    await user.keyboard(' '); expect(menu.getAttribute('aria-expanded')).toBe('true')
    await user.click(menu); expect(menu.getAttribute('aria-expanded')).toBe('false')
  })
  it('fila única vira texto; mantém campos e a ordem literal da API, sem expor pontuação', async () => {
    itens = [item(4), item(2, { classificacao_risco: 'AMARELO' }), item(3, { classificacao_risco: 'VERDE' }),
      item(1, { status: 'EM_ANALISE', posicao: 9, classificacao_risco: null, data_entrada_fila: null, ultima_mudanca: null })]
    abrir(); const table = await tabela()
    expect(screen.queryByRole('combobox', { name: 'Fila' })).toBeNull()
    expect(consultasFilas[0]?.searchParams.get('limit')).toBe('100')
    expect(within(table).getAllByRole('columnheader').map((el) => el.textContent)).toEqual(['Posição', 'Risco', 'Nome', 'CPF', 'Entrada na fila', 'Status', 'Última mudança'])
    expect(within(table).getAllByRole('columnheader').every((el) => el.getAttribute('scope') === 'col')).toBe(true)
    expect(table.querySelector('caption')).toBeTruthy()
    expect(within(table).getAllByRole('link').map((el) => el.textContent)).toEqual(itens.map((i) => i.paciente_nome))
    for (const texto of ['Alto', 'Médio', 'Baixo', 'Sem classificação', 'Ainda não entrou na fila', 'sem posição', 'Entrou na fila · 28/10', '28/10/2026']) expect(table.textContent).toContain(texto)
    expect(within(table).getAllByText('***.482.***-10')).toHaveLength(4)
    expect(document.body.innerHTML).not.toContain('987654')
    expect(screen.getByRole('option', { name: 'Todos (22)' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Em análise (3)' })).toBeTruthy()
  })
  it('várias filas: ativas antes das inativas; seleção e filtros vão para URL e API, Voltar restaura', async () => {
    filas = [fila(2, { ativa: false }), fila()]; itens = Array.from({ length: 21 }, (_, n) => item(n + 1))
    const { user } = abrir(); await tabela()
    const seletor = screen.getByRole('combobox', { name: 'Fila' })
    expect(within(seletor).getAllByRole('option').map((o) => o.textContent)).toEqual(['Fila sintética 1 · PROCAPE', 'Fila sintética 2 · PROCAPE (inativa)'])
    await user.click(screen.getByRole('button', { name: 'Próxima' }))
    await waitFor(() => expect(consultas.at(-1)?.searchParams.get('offset')).toBe('20'))
    expect(screen.getByTestId('url').textContent).toContain('pagina=2')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ordenação' }), 'chegada')
    await waitFor(() => expect(consultas.at(-1)?.searchParams.get('ordenacao')).toBe('chegada'))
    expect(consultas.at(-1)?.searchParams.get('offset')).toBe('0')
    expect(screen.getByText('A posição segue a prioridade da fila.')).toBeTruthy()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'EM_ANALISE')
    await waitFor(() => expect(consultas.at(-1)?.searchParams.get('status')).toBe('EM_ANALISE'))
    await user.selectOptions(seletor, uuid(2))
    await waitFor(() => expect(consultas.at(-1)?.pathname).toContain(uuid(2)))
    await user.click(screen.getByRole('button', { name: 'História anterior' }))
    await waitFor(() => expect((screen.getByRole('combobox', { name: 'Fila' }) as HTMLSelectElement).value).toBe(uuid(1)))
    await user.click(screen.getByRole('button', { name: 'História anterior' }))
    await waitFor(() => expect((screen.getByRole('combobox', { name: 'Status' }) as HTMLSelectElement).value).toBe('todos'))
    await user.click(screen.getByRole('button', { name: 'História anterior' }))
    await waitFor(() => expect(screen.getByTestId('url').textContent).toContain('pagina=2'))
    expect((screen.getByRole('combobox', { name: 'Ordenação' }) as HTMLSelectElement).value).toBe('prioridade')
  })
  it('nenhuma fila informa como obter acesso', async () => {
    filas = []; abrir()
    expect(await screen.findByText('Você ainda não tem filas liberadas. Fale com o gestor da unidade.')).toBeTruthy()
    expect(consultas).toHaveLength(0)
  })
  it('detalhe provisório e Voltar preservam somente identificadores e filtros', async () => {
    const { user } = abrir(`/equipe/fila?fila=${uuid(1)}&ordem=chegada&status=NA_FILA&pagina=1`)
    const table = await tabela(); const link = within(table).getByRole('link', { name: itens[0]!.paciente_nome })
    expect(link.getAttribute('href')).toContain(`/equipe/solicitacoes/${itens[0]!.id}`)
    await user.click(link)
    await screen.findByRole('heading', { name: 'Detalhe do pedido' })
    await user.click(screen.getByRole('link', { name: '‹ Voltar para a fila' }))
    await tabela()
    expect(screen.getByTestId('url').textContent).toBe(`/equipe/fila?fila=${uuid(1)}&ordem=chegada&status=NA_FILA&pagina=1`)
    expect(screen.getByTestId('url').textContent).not.toContain('Sintético')
    expect(screen.getByTestId('url').textContent).not.toContain('482')
  })
  it('Atualizar e volta à aba atualizam pedidos e contadores', async () => {
    const { user } = abrir(); await tabela()
    const hora = await screen.findByText(/^Atualizado às/)
    const antes = hora.textContent
    const instante = vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 120000)
    filas[0]!.contagem_por_status.EM_ANALISE = 4
    const listas = consultasFilas.length; const pedidos = consultas.length
    await user.click(screen.getByRole('button', { name: 'Atualizar' }))
    await screen.findByRole('option', { name: 'Em análise (4)' })
    await waitFor(() => expect(hora.textContent).not.toBe(antes))
    expect(consultas.length).toBeGreaterThan(pedidos); expect(consultasFilas.length).toBeGreaterThan(listas)
    instante.mockRestore()
    const novamente = consultasFilas.length; const novamentePedidos = consultas.length
    await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true) })
    await waitFor(() => expect(consultasFilas.length).toBeGreaterThan(novamente))
    await waitFor(() => expect(consultas.length).toBeGreaterThan(novamentePedidos))
  })
  it.each([403, 404, 503])('erro %s permite tentar novamente sem expor corpo bruto', async (status) => {
    servidor.use(msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => problema(status)))
    const { user } = abrir(); await screen.findByRole('alert')
    expect(screen.queryByRole('table')).toBeNull()
    servidor.resetHandlers()
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    await tabela()
  })
  it('vazio do filtro tem mensagem e anúncio', async () => {
    itens = []; abrir()
    await screen.findByText('Nenhum pedido com este status nesta fila.')
    expect(within(screen.getByRole('region', { name: 'Fila' })).getByRole('status').textContent).toContain('Mostrando 0 de 0 pedidos')
  })
  it('axe verifica layout e tabela', async () => {
    const { container } = abrir(); await tabela()
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
  })
  it('a única fila inativa é exibida como texto com sufixo', async () => {
    filas = [fila(1, { ativa: false })]; abrir(); await tabela()
    expect(screen.getByText('Fila sintética 1 · PROCAPE (inativa)')).toBeTruthy()
    expect(screen.queryByRole('combobox', { name: 'Fila' })).toBeNull()
  })
  it('carrega todas as páginas de filas usando limit 100', async () => {
    filas = Array.from({ length: 101 }, (_, n) => fila(n + 1))
    abrir(); await tabela()
    expect(consultasFilas.map((url) => url.searchParams.get('offset'))).toEqual(['0', '100'])
    expect(consultasFilas.every((url) => url.searchParams.get('limit') === '100')).toBe(true)
    expect(within(screen.getByRole('combobox', { name: 'Fila' })).getAllByRole('option')).toHaveLength(101)
  })
  it('mostra os seis status e só mostra posição em NA_FILA; eventos nulos ou desconhecidos não exibem código', async () => {
    const status = ['EM_ANALISE', 'NA_FILA', 'EM_PROPOSTA', 'AGENDADA', 'ATENDIDA', 'CANCELADA'] as const
    itens = status.map((valor, n) => item(n + 1, { status: valor, posicao: 42,
      ultima_mudanca: n === 0 ? { tipo: 'EVENTO_FUTURO', ocorrido_em: '2026-10-29T02:30:00Z' } as unknown as Item['ultima_mudanca'] :
        n === 1 ? { tipo: 'REENTROU_NA_FILA', ocorrido_em: '2026-10-29T02:30:00Z' } :
          n === 2 ? { tipo: 'RECLASSIFICADA', ocorrido_em: '2026-10-29T02:30:00Z' } : null }))
    abrir(); const table = await tabela()
    for (const texto of ['Em análise', 'Aguardando vaga', 'Aguardando confirmação', 'Agendado', 'Atendimento realizado', 'Cancelado', 'Voltou à fila · 28/10', 'Reclassificado · 28/10']) expect(table.textContent).toContain(texto)
    expect(within(table).getAllByText('42')).toHaveLength(1)
    expect(within(table).getAllByText('sem posição')).toHaveLength(5)
    expect(document.body.innerHTML).not.toContain('EVENTO_FUTURO')
  })
  it('carregamento inicial de filas e de pedidos tem anúncio sem tabela antiga', async () => {
    const lista = adiar<Response>(); const painel = adiar<Response>()
    servidor.use(msw.get('*/api/v1/equipe/filas', () => lista.promise), msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => painel.promise))
    abrir(); await screen.findByText('Carregando filas…'); expect(screen.queryByRole('table')).toBeNull()
    await act(async () => lista.resolver(HttpResponse.json({ total: 1, itens: filas })))
    await screen.findByText('Carregando pedidos…'); expect(screen.queryByRole('table')).toBeNull()
    await act(async () => painel.resolver(HttpResponse.json({ total: 1, itens })))
    await tabela()
  })
  it.each([403, 503])('erro %s na lista de filas tem nova tentativa', async (codigo) => {
    servidor.use(msw.get('*/api/v1/equipe/filas', () => problema(codigo)))
    const { user } = abrir(); const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).not.toContain('Falha sintética')
    expect(screen.queryByRole('table')).toBeNull()
    servidor.resetHandlers(); await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await tabela()
  })
  it('refetch 403 oculta dados anteriores sem encerrar sessão nem renovar', async () => {
    const refresh = vi.fn(); const { user, client } = abrir(); await tabela()
    servidor.use(msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => problema(403)), msw.post('*/api/v1/auth/refresh', refresh))
    await user.click(screen.getByRole('button', { name: 'Atualizar' })); await screen.findByRole('alert')
    expect(screen.queryByRole('table')).toBeNull(); expect(refresh).not.toHaveBeenCalled()
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ papel: 'ATENDENTE' })
  })
  it('corrige página após redução do total e não mostra uma página fora do intervalo', async () => {
    itens = Array.from({ length: 21 }, (_, n) => item(n + 1))
    const { user } = abrir(`/equipe/fila?fila=${uuid(1)}&pagina=2`); await tabela()
    expect(within(await tabela()).getByRole('link').textContent).toBe('Sintético 21 S.')
    itens = itens.slice(0, 20)
    await user.click(screen.getByRole('button', { name: 'Atualizar' }))
    await waitFor(() => expect(screen.getByTestId('url').textContent).toContain('pagina=1'))
    await waitFor(() => expect(within(screen.getByRole('table')).getAllByRole('link')).toHaveLength(20))
    expect(consultas.at(-1)?.searchParams.get('offset')).toBe('0')
  })
  it('URL inválida é normalizada sem campos extras e sem persistência', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    const remover = vi.spyOn(Storage.prototype, 'removeItem'); const limpar = vi.spyOn(Storage.prototype, 'clear')
    const { user } = abrir('/equipe/fila?fila=invalida&ordem=invalida&status=toString&pagina=-1&nome=nao-copiar')
    await tabela()
    await waitFor(() => expect(screen.getByTestId('url').textContent).toBe(`/equipe/fila?fila=${uuid(1)}&ordem=prioridade&pagina=1`))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Status' }), 'EM_ANALISE')
    expect(storage).not.toHaveBeenCalled(); expect(remover).not.toHaveBeenCalled(); expect(limpar).not.toHaveBeenCalled()
    expect(consultas.at(-1)?.searchParams.get('limit')).toBe('20')
  })
  it.each(['ATENDENTE', 'GESTOR', 'ADMIN'] as const)('/ manda %s para Fila', async (valor) => {
    papel = valor; abrir('/'); await tabela()
    expect(screen.getByTestId('url').textContent).toMatch(/^\/equipe\/fila\?/)
  })
  it('paciente em rota da equipe vai para Meus atendimentos', async () => {
    papel = 'PACIENTE'; abrir('/equipe/fila')
    await screen.findByRole('heading', { name: 'Meus atendimentos' }); expect(consultasFilas).toHaveLength(0)
  })
  it.each(['ATENDENTE', 'GESTOR', 'ADMIN'] as const)('equipe %s em rota do paciente vai para a Fila', async (valor) => {
    papel = valor; abrir('/paciente/novo'); await tabela()
    expect(screen.queryByRole('heading', { name: 'Novo pedido' })).toBeNull()
  })
  it.each(['/equipe/fila', '/paciente', '/'])('troca obrigatória tem prioridade em %s', async (path) => {
    servidor.use(msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(99), papel, nome: null, filas: [], trocar_senha: true })))
    abrir(path); await screen.findByRole('heading', { name: 'Troca de senha obrigatória' })
    expect(consultasFilas).toHaveLength(0); expect(screen.queryByRole('navigation', { name: 'Área da equipe' })).toBeNull()
  })
  it('B2: revalidar /me mantém a tabela e os filtros montados', async () => {
    const { client } = abrir(); const table = await tabela()
    const pendente = adiar<Response>()
    servidor.use(msw.get('*/api/v1/me', () => pendente.promise))
    let consulta!: Promise<void>
    act(() => { consulta = client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    expect(table.isConnected).toBe(true)
    await act(async () => { pendente.resolver(HttpResponse.json({ id: uuid(99), papel, nome: null, filas: [uuid(1)] })); await consulta })
    expect(table.isConnected).toBe(true)
  })
  it('B1: Sair durante busca, novo login e resposta antiga não alteram sessão nem cache novos', async () => {
    const antiga = adiar<Response>(); const iniciou = vi.fn()
    servidor.use(msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => { iniciou(); return antiga.promise }))
    const { user, client } = abrir(); await waitFor(() => expect(iniciou).toHaveBeenCalledOnce())
    await user.click(screen.getByRole('button', { name: 'Sair' })); await screen.findByRole('heading', { name: 'Entrar' })
    expect(client.getQueryCache().getAll().some((q) => q.queryKey[0] === 'fila-equipe')).toBe(false)
    servidor.use(msw.post('*/api/v1/auth/login', () => HttpResponse.json({ papel: 'GESTOR', expira_em: '2026-11-01T12:00:00Z' })),
      msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(98), papel: 'GESTOR', nome: null, filas: [uuid(1)] })),
      msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => HttpResponse.json({ total: 1, itens: [item(9, { paciente_nome: 'Nova S.' })] })))
    await user.type(screen.getByLabelText('CPF ou e-mail'), 'gestor.sintetico@exemplo.test')
    await user.type(screen.getByLabelText('Senha', { exact: true }), 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' })); await tabela()
    await act(async () => antiga.resolver(HttpResponse.json({ total: 1, itens: [item(1, { paciente_nome: 'Antiga S.' })] })))
    await waitFor(() => expect(within(screen.getByRole('table')).getByRole('link', { name: 'Nova S.' })).toBeTruthy())
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ id: uuid(98), papel: 'GESTOR' })
    expect(JSON.stringify(client.getQueryCache().getAll().map((q) => q.state.data))).not.toContain('Antiga S.')
    expect(screen.getByText('Gestor')).toBeTruthy()
  })
})
