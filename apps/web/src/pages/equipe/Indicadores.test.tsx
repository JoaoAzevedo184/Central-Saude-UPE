import { QueryClientProvider, focusManager, onlineManager } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as msw, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import { sessaoOptions, type Sessao } from '../../shared/auth/session'
import { indicadoresSinteticos } from '../../test/fixtures/indicadores-sinteticos'
import type { DadosIndicadores } from './api-indicadores'
import type { FilaEquipe } from './api'
import { lerEstadoFila, paramsFila } from './estado-fila'

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const urlIndicadores = '*/api/v1/equipe/indicadores'
const fila: FilaEquipe = { id: uuid(1), nome: 'Fila sintética', unidade_sigla: 'CISAM', especialidade: 'Exame sintético', ativa: true, contagem_por_status: {} }
let dados: DadosIndicadores
let papel: 'ATENDENTE' | 'GESTOR' | 'ADMIN'
let consultas: URL[]
let refreshes: number
function resposta(request: Request) {
  const params = new URL(request.url).searchParams
  return HttpResponse.json({ ...dados, de: params.get('de'), ate: params.get('ate'), fila_id: params.get('fila_id') })
}
function problema(status: number, tipo = 'about:blank', headers: Record<string, string> = {}) {
  return HttpResponse.json({ status, type: tipo, title: 'Texto técnico não exibível', detail: 'Detalhe técnico não exibível', errors: [{ loc: ['query', 'de'], msg: 'Não exibir' }] }, { status, headers: { ...headers, 'Content-Type': 'application/problem+json' } })
}
function adiar<T>() { let resolver!: (valor: T) => void; const promise = new Promise<T>((resolve) => { resolver = resolve }); return { promise, resolver } }
const servidor = setupServer(
  msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(99), papel, nome: null, filas: [fila.id] })),
  msw.get('*/api/v1/equipe/filas', () => HttpResponse.json({ total: 1, itens: [fila] })),
  msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => HttpResponse.json({ total: 0, itens: [] })),
  msw.get(urlIndicadores, ({ request }) => { consultas.push(new URL(request.url)); return resposta(request) }),
  msw.post('*/api/v1/auth/logout', ({ request }) => {
    expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
    return new HttpResponse(null, { status: 204 })
  }),
  msw.post('*/api/v1/auth/refresh', () => { refreshes++; return problema(401) }),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-11-09T12:00:00Z'))
  dados = indicadoresSinteticos(); papel = 'GESTOR'; consultas = []; refreshes = 0
  http.iniciarSessao(); document.cookie = 'csrf_token=csrf-sintetico; path=/'
})
afterEach(() => { servidor.resetHandlers(); vi.restoreAllMocks(); vi.useRealTimers(); http.iniciarSessao(); focusManager.setFocused(undefined); onlineManager.setOnline(true) })
function Navegacao() {
  const location = useLocation(); const navigate = useNavigate()
  return <><span data-testid="url">{location.pathname}{location.search}</span><button onClick={() => void navigate(-1)}>Voltar no navegador</button></>
}
function abrir(path = '/equipe/indicadores') {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Rotas /><Navegacao /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, user: userEvent.setup() }
}
const pronto = () => screen.findByRole('img', { name: /Pedidos criados e Propostas confirmadas/ })
const periodo = () => screen.getByRole('combobox', { name: 'Período' })
function preencher(de: string, ate: string) {
  fireEvent.change(screen.getByLabelText('De', { exact: true }), { target: { value: de } })
  fireEvent.change(screen.getByLabelText('Até', { exact: true }), { target: { value: ate } })
}

describe('Indicadores — acesso e navegação', () => {
  it.each(['GESTOR', 'ADMIN'] as const)('menu e rota para %s', async (valor) => {
    papel = valor; abrir(); await pronto()
    expect(screen.getByRole('link', { name: 'Indicadores' }).getAttribute('aria-current')).toBe('page')
    expect(consultas).toHaveLength(1)
  })
  it('ATENDENTE na URL direta vai à Fila sem chamar indicadores', async () => {
    papel = 'ATENDENTE'; abrir(); await screen.findByRole('heading', { name: 'Fila' })
    expect(screen.queryByRole('link', { name: 'Indicadores' })).toBeNull()
    expect(consultas).toHaveLength(0)
  })
  it('destinos próprios: Indicadores não leva filtros da Fila e Fila conserva seu link', async () => {
    servidor.use(msw.get('*/api/v1/equipe/filas/:id/solicitacoes', () => HttpResponse.json({ total: 45, itens: [] })))
    const query = `fila=${fila.id}&ordem=chegada&status=NA_FILA&pagina=3`
    abrir(`/equipe/fila?${query}`); await screen.findByText(/Mostrando 0 de 45 pedidos/)
    expect(screen.getByRole('link', { name: 'Indicadores' }).getAttribute('href')).toBe('/equipe/indicadores')
    expect(screen.getByRole('link', { name: 'Fila' }).getAttribute('href')).toBe(`/equipe/fila?${query}`)
  })
  it('o link da Fila usa os padrões quando a página atual é Indicadores, sem herdar fila', async () => {
    abrir(`/equipe/indicadores?de=2026-10-06&ate=2026-11-02&fila=${fila.id}`); await pronto()
    const destino = screen.getByRole('link', { name: 'Fila' }).getAttribute('href')
    expect(destino).toBe(`/equipe/fila?${paramsFila(lerEstadoFila(new URLSearchParams()))}`)
    expect(destino).not.toContain(fila.id)
  })
})

describe('Indicadores — filtros e AM-025', () => {
  it('cada período e fila faz uma chamada; Todas omite fila_id; Voltar restaura URL e dados', async () => {
    const { user } = abrir(); await pronto()
    expect(consultas[0]!.searchParams.toString()).toBe('de=2026-10-13&ate=2026-11-09')
    await user.selectOptions(periodo(), '8')
    await waitFor(() => expect(consultas).toHaveLength(2))
    expect(consultas[1]!.searchParams.get('de')).toBe('2026-09-15')
    await user.selectOptions(periodo(), 'mes')
    await waitFor(() => expect(consultas).toHaveLength(3))
    expect(consultas[2]!.searchParams.get('de')).toBe('2026-11-01')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Fila' }), fila.id)
    await waitFor(() => expect(consultas).toHaveLength(4))
    expect(consultas[3]!.searchParams.get('fila_id')).toBe(fila.id)
    expect(screen.getByTestId('url').textContent).toBe(`/equipe/indicadores?de=2026-11-01&ate=2026-11-09&fila=${fila.id}`)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Fila' }), '')
    await waitFor(() => expect(consultas).toHaveLength(5))
    expect(consultas[4]!.searchParams.has('fila_id')).toBe(false)
    await user.click(screen.getByRole('button', { name: 'Voltar no navegador' }))
    await waitFor(() => expect(consultas).toHaveLength(6))
    expect(consultas[5]!.searchParams.get('fila_id')).toBe(fila.id)
    expect((screen.getByRole('combobox', { name: 'Fila' }) as HTMLSelectElement).value).toBe(fila.id)
  })
  it('na virada UTC ainda envia as datas do mês de Recife', async () => {
    vi.setSystemTime(new Date('2026-11-01T01:30:00Z'))
    const { user } = abrir(); await pronto()
    expect(consultas[0]!.searchParams.get('ate')).toBe('2026-10-31')
    expect(consultas[0]!.searchParams.get('de')).toBe('2026-10-04')
    await user.selectOptions(periodo(), '8')
    await waitFor(() => expect(consultas).toHaveLength(2))
    expect(consultas[1]!.searchParams.get('de')).toBe('2026-09-06')
    await user.selectOptions(periodo(), 'mes')
    await waitFor(() => expect(consultas).toHaveLength(3))
    expect(consultas[2]!.searchParams.get('de')).toBe('2026-10-01')
  })
  it('personalizado só envia ao Aplicar, aceita um dia e não repete aplicação idêntica', async () => {
    const { user } = abrir(); await pronto(); await user.selectOptions(periodo(), 'personalizado')
    preencher('2026-10-06', '2026-11-02'); expect(consultas).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Aplicar' }))
    await waitFor(() => expect(consultas).toHaveLength(2))
    expect(consultas[1]!.searchParams.toString()).toBe('de=2026-10-06&ate=2026-11-02')
    expect(screen.getByRole('status').textContent).toContain('Indicadores de 06/10 a 02/11, todas as filas')
    preencher('2026-11-09', '2026-11-09')
    await user.click(screen.getByRole('button', { name: 'Aplicar' }))
    await waitFor(() => expect(consultas).toHaveLength(3))
    expect(consultas[2]!.searchParams.toString()).toBe('de=2026-11-09&ate=2026-11-09')
    await user.click(screen.getByRole('button', { name: 'Aplicar' })); expect(consultas).toHaveLength(3)
  })
  it.each([
    ['2026-11-09', '2026-11-08', /anterior ou igual/],
    ['2026-11-09', '2026-11-10', /até hoje/],
    ['2025-11-08', '2026-11-09', /366/], ['', '2026-11-09', /válidas/],
  ])('período inválido %s–%s não consulta a API', async (de, ate, mensagem) => {
    const { user } = abrir(); await pronto(); await user.selectOptions(periodo(), 'personalizado'); preencher(de, ate)
    await user.click(screen.getByRole('button', { name: 'Aplicar' }))
    expect(screen.getByRole('alert').textContent).toMatch(mensagem)
    expect(document.activeElement).toBe(screen.getByLabelText('De', { exact: true })); expect(consultas).toHaveLength(1)
  })
  it('o limite inclusivo de 366 dias é enviado ao Aplicar', async () => {
    const { user } = abrir(); await pronto(); await user.selectOptions(periodo(), 'personalizado')
    preencher('2025-11-09', '2026-11-09')
    await user.click(screen.getByRole('button', { name: 'Aplicar' }))
    await waitFor(() => expect(consultas).toHaveLength(2))
    expect(consultas[1]!.searchParams.toString()).toBe('de=2025-11-09&ate=2026-11-09')
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it.each(['?de=2026-02-30&ate=2026-03-01', '?de=2026-11-01', '?fila=invalida'])('URL inválida %s não faz consulta', async (query) => {
    abrir(`/equipe/indicadores${query}`); await screen.findByRole('heading', { name: 'Indicadores' })
    expect(consultas).toHaveLength(0)
    expect(screen.queryByRole('img')).toBeNull()
  })
  it('não reconsulta por foco ou reconexão e não grava em storage', async () => {
    const salvar = vi.spyOn(Storage.prototype, 'setItem'); const remover = vi.spyOn(Storage.prototype, 'removeItem'); const limpar = vi.spyOn(Storage.prototype, 'clear')
    const { user } = abrir(); await pronto()
    await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true); onlineManager.setOnline(false); onlineManager.setOnline(true) })
    await user.selectOptions(periodo(), '8'); await waitFor(() => expect(consultas).toHaveLength(2))
    expect(salvar).not.toHaveBeenCalled(); expect(remover).not.toHaveBeenCalled(); expect(limpar).not.toHaveBeenCalled()
  })
  it('só informa fila indisponível após carregar o escopo com sucesso', async () => {
    const pendente = adiar<Response>()
    servidor.use(msw.get('*/api/v1/equipe/filas', () => pendente.promise))
    abrir(`/equipe/indicadores?de=2026-10-06&ate=2026-11-02&fila=${uuid(2)}`); await pronto()
    expect(screen.queryByRole('option', { name: 'Fila selecionada indisponível' })).toBeNull()
    await act(async () => pendente.resolver(HttpResponse.json({ total: 1, itens: [fila] })))
    const opcao = await screen.findByRole('option', { name: 'Fila selecionada indisponível' })
    expect((opcao as HTMLOptionElement).value).toBe(uuid(2))
    expect((screen.getByRole('combobox', { name: 'Fila' }) as HTMLSelectElement).value).toBe(uuid(2))
    expect(consultas).toHaveLength(1)
  })
  it('falha ao carregar filas mostra erro no seletor e nova tentativa, sem declarar fila indisponível', async () => {
    servidor.use(msw.get('*/api/v1/equipe/filas', () => problema(500)))
    const { user } = abrir(`/equipe/indicadores?de=2026-10-06&ate=2026-11-02&fila=${fila.id}`)
    const tentar = await screen.findByRole('button', { name: 'Tentar carregar filas' })
    expect(screen.queryByRole('option', { name: 'Fila selecionada indisponível' })).toBeNull()
    const seletor = screen.getByRole('combobox', { name: 'Fila' })
    expect(seletor.getAttribute('aria-invalid')).toBe('true')
    const erroId = seletor.getAttribute('aria-describedby')!.split(' ').find((id) => id.endsWith('-erro'))!
    expect(document.getElementById(erroId)?.textContent).toBe('Não foi possível carregar as opções de fila.')
    servidor.resetHandlers(); await user.click(tentar)
    await screen.findByRole('option', { name: 'Fila sintética · CISAM' })
    expect(seletor.getAttribute('aria-invalid')).toBeNull()
    expect((seletor as HTMLSelectElement).value).toBe(fila.id)
    expect(screen.queryByRole('option', { name: 'Fila selecionada indisponível' })).toBeNull()
    expect(screen.getByTestId('url').textContent).toContain(`fila=${fila.id}`)
    expect(consultas).toHaveLength(1)
  })
})

describe('Indicadores — números e estados', () => {
  it('formata taxas, espera e quantidade; os três riscos têm texto', async () => {
    abrir(); await pronto()
    for (const texto of ['72,5%', '10,0%', '4,2 dias', '12,8 dias', '21 confirmações usadas.', '1.234']) expect(screen.getByText(texto)).toBeTruthy()
    const agora = screen.getByRole('region', { name: 'Fila agora' })
    for (const texto of ['Alto', 'Médio', 'Baixo', '15', '34', '52']) expect(within(agora).getByText(texto)).toBeTruthy()
    expect(agora.textContent).toContain('Não depende do período escolhido')
  })
  it('nulos mostram traço e sem dados; vazio não depende da fila atual', async () => {
    dados.totais = Object.fromEntries(Object.entries(dados.totais).map(([campo]) => [campo, campo.startsWith('taxa_') ? null : 0])) as DadosIndicadores['totais']
    dados.tempo_de_espera = { confirmacoes: 0, mediana_dias: null, p90_dias: null }; dados.semanas = []
    abrir(); await pronto()
    expect(screen.getByText('Nenhum movimento neste período.')).toBeTruthy()
    expect(screen.getAllByText('—')).toHaveLength(4)
    expect(screen.getAllByText('sem dados no período')).toHaveLength(3)
    expect(screen.queryByText('0,0%')).toBeNull(); expect(document.body.textContent).not.toContain('NaN')
    expect(within(screen.getByRole('region', { name: 'Fila agora' })).getByText('52')).toBeTruthy()
  })
  it('barras e tabela apresentam os mesmos números e a segunda-feira civil correta', async () => {
    const { user } = abrir(); const grafico = await pronto()
    expect([...grafico.querySelectorAll('.barra-criadas')].map((el) => el.getAttribute('data-valor'))).toEqual(['12', '18'])
    expect([...grafico.querySelectorAll('.barra-confirmadas')].map((el) => el.getAttribute('data-valor'))).toEqual(['8', '11'])
    expect(grafico.textContent).toContain('02/11'); expect(grafico.getAttribute('aria-label')).toContain('Propostas confirmadas')
    expect(screen.getByText('Ver tabela').parentElement?.hasAttribute('open')).toBe(false)
    await user.click(screen.getByText('Ver tabela'))
    const tabela = screen.getByRole('table', { name: /Pedidos criados e Propostas confirmadas/ })
    expect(within(tabela).getAllByRole('row').map((linha) => linha.textContent)).toEqual(['SemanaPedidos criadosPropostas confirmadas', '02/11128', '09/111811'])
    expect([...tabela.querySelectorAll('th')].every((th) => th.hasAttribute('scope'))).toBe(true)
    await user.click(screen.getByText('Ver tabela')); expect(screen.getByText('Ver tabela').parentElement?.hasAttribute('open')).toBe(false)
  })
  it.each([
    { de: '2025-12-22', ate: '2026-01-05', semanas: ['2025-12-29', '2026-01-05'], rotulos: ['29/12/25', '05/01/26'] },
    { de: '2025-12-30', ate: '2026-01-01', semanas: ['2025-12-29'], rotulos: ['29/12/25'] },
  ])('período $de a $ate mostra ano em todos os rótulos semanais', async ({ de, ate, semanas, rotulos }) => {
    dados.semanas = semanas.map((semana, i) => ({ ...dados.semanas[i]!, semana }))
    const { user } = abrir(`/equipe/indicadores?de=${de}&ate=${ate}`); const grafico = await pronto()
    expect([...grafico.querySelectorAll('text')].filter((el) => el.textContent?.includes('/')).map((el) => el.textContent)).toEqual(rotulos)
    for (const rotulo of rotulos) {
      expect([...grafico.querySelectorAll('title')].filter((el) => el.textContent?.startsWith(`${rotulo}:`))).toHaveLength(2)
      expect(grafico.getAttribute('aria-label')).toContain(rotulo)
    }
    await user.click(screen.getByText('Ver tabela'))
    expect(within(screen.getByRole('table')).getAllByRole('rowheader').map((el) => el.textContent)).toEqual(rotulos)
  })
  it('primeira busca mostra espera; troca mantém os cartões esmaecidos e anuncia somente a resposta concluída', async () => {
    const primeira = adiar<Response>()
    servidor.use(msw.get(urlIndicadores, ({ request }) => { consultas.push(new URL(request.url)); return primeira.promise }))
    const { user } = abrir(); await screen.findByText('Carregando indicadores…')
    await act(async () => primeira.resolver(HttpResponse.json(dados))); await pronto()
    const segunda = adiar<Response>(); const terceira = adiar<Response>(); const sinais: AbortSignal[] = []
    servidor.use(msw.get(urlIndicadores, ({ request }) => { consultas.push(new URL(request.url)); sinais.push(request.signal); return sinais.length === 1 ? segunda.promise : terceira.promise }))
    await user.selectOptions(periodo(), '8'); await waitFor(() => expect(consultas).toHaveLength(2))
    expect(screen.getByText('72,5%').closest('.resultado-indicadores')?.classList.contains('atualizando')).toBe(true)
    expect(screen.getByRole('status').textContent).toBe('')
    await user.selectOptions(periodo(), 'mes'); await waitFor(() => expect(consultas).toHaveLength(3))
    // A busca da seleção anterior é cancelada; o HTTP recebe o sinal.
    expect(sinais[0]!.aborted).toBe(true)
    await act(async () => terceira.resolver(HttpResponse.json({ ...dados, de: '2026-11-01', ate: '2026-11-09' })))
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('01/11 a 09/11'))
    expect(screen.getByText('72,5%').closest('.resultado-indicadores')?.classList.contains('atualizando')).toBe(false)
    await act(async () => segunda.resolver(HttpResponse.json({ ...dados, de: '2026-09-15', totais: { ...dados.totais, taxa_confirmacao: .999 } })))
    expect(screen.queryByText('99,9%')).toBeNull()
    expect(screen.getByRole('status').textContent).toContain('01/11 a 09/11')
  })
  it.each([403, 404, 500])('erro %s é seguro, não repete sozinho e permite nova tentativa', async (status) => {
    servidor.use(msw.get(urlIndicadores, ({ request }) => { consultas.push(new URL(request.url)); return problema(status) }))
    const { user } = abrir(`/equipe/indicadores?de=2026-10-06&ate=2026-11-02&fila=${fila.id}`)
    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toContain(status === 403 ? 'Confira seu acesso' : status === 404 ? 'fila selecionada' : 'Não foi possível carregar')
    expect(alerta.textContent).not.toContain('técnico'); expect(consultas).toHaveLength(1)
    expect(screen.getByTestId('url').textContent).toContain(`fila=${fila.id}`)
    servidor.resetHandlers(); await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await pronto()
    expect(consultas).toHaveLength(2); expect(consultas[1]!.searchParams.get('fila_id')).toBe(fila.id)
  })
  it('erro de rede oferece nova tentativa', async () => {
    servidor.use(msw.get(urlIndicadores, () => HttpResponse.error()))
    const { user } = abrir(); await screen.findByRole('alert'); servidor.resetHandlers()
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await pronto()
  })
  it('422 aparece no período e corrigir o recorte permite nova consulta', async () => {
    servidor.use(msw.get(urlIndicadores, () => problema(422)))
    const { user } = abrir(); await screen.findByRole('alert')
    expect((periodo() as HTMLSelectElement).getAttribute('aria-invalid')).toBe('true')
    expect(screen.getByRole('alert').textContent).toContain('366')
    servidor.resetHandlers(); await user.selectOptions(periodo(), '8'); await pronto()
  })
  it.each([undefined, 'inválido'])('503 com Retry-After %s libera o botão na hora', async (header) => {
    servidor.use(msw.get(urlIndicadores, () => problema(503, '/problemas/consulta-demorada', header ? { 'Retry-After': header } : {})))
    abrir(); expect((await screen.findByRole('alert')).textContent).toContain('A consulta demorou demais. Tente um período menor.')
    expect((screen.getByRole('button', { name: 'Tentar de novo' }) as HTMLButtonElement).disabled).toBe(false)
  })
  it.each(['1', 'Mon, 09 Nov 2026 12:00:01 GMT'])('503 respeita Retry-After %s e não tenta automaticamente', async (header) => {
    const pendente = adiar<Response>()
    servidor.use(msw.get(urlIndicadores, ({ request }) => { consultas.push(new URL(request.url)); return pendente.promise }))
    abrir(); await waitFor(() => expect(consultas).toHaveLength(1))
    vi.useFakeTimers({ toFake: ['Date', 'setTimeout', 'clearTimeout'] })
    vi.setSystemTime(new Date('2026-11-09T12:00:00Z'))
    await act(async () => {
      pendente.resolver(problema(503, '/problemas/consulta-demorada', { 'Retry-After': header }))
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(screen.getByRole('alert').textContent).toContain('A consulta demorou demais.')
    const botao = screen.getByRole('button', { name: 'Tentar de novo' }) as HTMLButtonElement
    expect(botao.disabled).toBe(true)
    await act(async () => { await vi.advanceTimersByTimeAsync(999) })
    expect(botao.disabled).toBe(true)
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(botao.disabled).toBe(false)
    expect(consultas).toHaveLength(1)
  })
  it('axe na tela, personalizado e tabela aberta', async () => {
    const { user, container } = abrir(); await pronto()
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
    await user.selectOptions(periodo(), 'personalizado'); await user.click(screen.getByText('Ver tabela'))
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
  })
})

describe('Indicadores — sessão B1/B2', () => {
  it('403 atual de troca obrigatória leva a /trocar-senha sem mostrar o erro neutro de permissão', async () => {
    servidor.use(msw.get(urlIndicadores, () => problema(403, '/problemas/troca-de-senha-obrigatoria')))
    abrir(); await screen.findByRole('heading', { name: 'Troca de senha obrigatória' })
    expect(screen.getByTestId('url').textContent).toBe('/trocar-senha')
    expect(screen.queryByText('Não foi possível acessar os indicadores. Confira seu acesso com a administração.')).toBeNull()
    expect(refreshes).toBe(0)
  })
  it('401 atual usa o fluxo de refresh e encaminha à entrada quando ele falha', async () => {
    servidor.use(msw.get(urlIndicadores, () => problema(401, '/problemas/nao-autenticado')))
    abrir(); await screen.findByRole('heading', { name: 'Entrar' }); expect(refreshes).toBe(1)
  })
  it.each([200, 401, 403])('B1: resposta antiga %s após Sair e novo login não altera sessão/cache/foco', async (status) => {
    const pendente = adiar<Response>(); let signal: AbortSignal | undefined
    servidor.use(msw.get(urlIndicadores, ({ request }) => { consultas.push(new URL(request.url)); signal = request.signal; return pendente.promise }))
    const { user, client } = abrir(); await waitFor(() => expect(consultas).toHaveLength(1))
    await user.click(screen.getByRole('button', { name: 'Sair' })); await screen.findByRole('heading', { name: 'Entrar' })
    expect(signal?.aborted).toBe(true)
    servidor.use(msw.post('*/api/v1/auth/login', () => HttpResponse.json({ papel: 'GESTOR', expira_em: '2026-11-09T13:00:00Z' })),
      msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(98), papel: 'GESTOR', nome: null, filas: [fila.id] })))
    await user.type(screen.getByLabelText('CPF ou e-mail'), 'gestor.sintetico@exemplo.test')
    await user.type(screen.getByLabelText('Senha', { exact: true }), 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' })); await screen.findByRole('heading', { name: 'Fila' })
    const menu = screen.getByRole('button', { name: 'Menu' }); menu.focus()
    await act(async () => pendente.resolver(status === 200 ? HttpResponse.json({ ...dados, totais: { ...dados.totais, solicitacoes_criadas: 987654321 } }) : problema(status, status === 403 ? '/problemas/troca-de-senha-obrigatoria' : '/problemas/nao-autenticado')))
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ id: uuid(98), papel: 'GESTOR' })
    expect(JSON.stringify(client.getQueryCache().getAll().map((q) => q.state.data))).not.toContain('987654321')
    expect(document.activeElement).toBe(menu); expect(refreshes).toBe(0)
    expect(screen.getByRole('heading', { name: 'Fila' })).toBeTruthy()
  })
  it('B2: revalidar /me preserva rascunho e resultados; logout antigo não limpa uma sessão nova', async () => {
    const { user, client } = abrir(); await pronto(); await user.selectOptions(periodo(), 'personalizado')
    preencher('2026-10-06', '2026-11-02')
    await act(async () => { await client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    expect((screen.getByLabelText('De', { exact: true }) as HTMLInputElement).value).toBe('2026-10-06')
    expect(consultas).toHaveLength(1)
    const saida = adiar<Response>()
    servidor.use(msw.post('*/api/v1/auth/logout', () => saida.promise))
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await act(async () => { http.iniciarSessao(); client.setQueryData<Sessao>(sessaoOptions.queryKey, { id: uuid(97), papel: 'GESTOR', nome: null, filas: [fila.id] }) })
    await act(async () => saida.resolver(new HttpResponse(null, { status: 204 })))
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ id: uuid(97) })
    expect(screen.getByRole('heading', { name: 'Indicadores' })).toBeTruthy()
  })
})
