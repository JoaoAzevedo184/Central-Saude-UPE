import { QueryClientProvider, useQuery } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import { Avisos } from './Avisos'
import { avisosOptions, listaAvisosKey, type Aviso } from './api'

const pedidoId = '00000000-0000-4000-8000-000000000001'
function aviso(id = 'aviso-1', extra: Partial<Aviso> = {}): Aviso {
  return { id, tipo: 'SOLICITACAO_CRIADA', titulo: 'Recebemos seu pedido', corpo: 'Seu pedido está em análise.',
    solicitacao_id: pedidoId, criado_em: '2026-10-29T02:30:00Z', lido_em: null, ...extra }
}
const json = (valor: unknown, status = 200) => new Response(JSON.stringify(valor), { status, headers: { 'Content-Type': 'application/json' } })
let itens: Aviso[]
let posts: string[]
let leituras: string[]
let fetcher: ReturnType<typeof vi.fn<typeof fetch>>
beforeEach(() => {
  itens = [aviso()]; posts = []; leituras = []
  document.cookie = 'csrf_token=csrf-sintetico; path=/'
  http.iniciarSessao()
  fetcher = vi.fn<typeof fetch>(async (url, options) => {
    const caminho = String(url)
    if (caminho === '/api/v1/avisos/contagem') return json({ nao_lidos: itens.filter((item) => !item.lido_em).length })
    if (options?.method === 'POST') {
      posts.push(caminho)
      expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('csrf-sintetico')
      expect(options.body).toBeUndefined()
      itens = itens.map((item) => caminho.endsWith('/lidos') || caminho.includes(`/${item.id}/lido`) ? { ...item, lido_em: '2026-10-29T12:00:00Z' } : item)
      return new Response(null, { status: 204 })
    }
    leituras.push(caminho)
    const params = new URL(caminho, 'http://localhost').searchParams
    const offset = Number(params.get('offset'))
    expect(params.get('limit')).toBe('10')
    expect(params.has('somente_nao_lidos')).toBe(false)
    return json({ total: itens.length, itens: itens.slice(offset, offset + 10) })
  })
  vi.stubGlobal('fetch', fetcher)
})
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); http.iniciarSessao() })
function Contador() {
  const consulta = useQuery(avisosOptions)
  return <p>Contagem: {consulta.data?.nao_lidos}</p>
}
function abrir(client = criarQueryClient()) {
  const resultado = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/paciente/avisos']}>
    <Contador /><Routes><Route path="/paciente/avisos" element={<main><Avisos /></main>} />
      <Route path="/paciente/solicitacoes/:id" element={<h1>Detalhe de destino</h1>} />
      <Route path="/outra" element={<h1>Outra página</h1>} /></Routes>
  </MemoryRouter></QueryClientProvider>)
  return { ...resultado, client, user: userEvent.setup() }
}
async function carregou() { return screen.findByRole('list', { name: 'Seus avisos' }) }
function adiar<T>() { let resolver!: (valor: T) => void; const promise = new Promise<T>((resolve) => { resolver = resolve }); return { promise, resolver } }

describe('RF-019 — avisos do paciente', () => {
  it('lista lidos e não lidos com data em Recife e sem marcação automática', async () => {
    itens.push(aviso('aviso-2', { titulo: 'Consulta confirmada', lido_em: '2026-10-29T12:00:00Z' }))
    abrir(); const lista = await carregou()
    expect(within(lista).getAllByRole('listitem')).toHaveLength(2)
    const [novo, lido] = within(lista).getAllByRole('listitem')
    expect(within(novo!).getByText('Novo').getAttribute('aria-hidden')).toBeNull()
    expect(within(lido!).queryByText(/^(Novo|Lido|Não lido)$/)).toBeNull()
    expect(within(lista).getAllByText('28/10/2026, às 23:30')).toHaveLength(2)
    expect(posts).toHaveLength(0)
  })

  it('preserva literalmente os textos da API, inclusive antigos, HTML e palavras sem filtro', async () => {
    itens = [aviso('antigo', { titulo: 'Voltou para o fim da fila', corpo: '<img src=x onerror=alert(1)> posição nota risco' })]
    abrir(); await carregou()
    expect(screen.getByRole('heading', { name: 'Voltou para o fim da fila' })).toBeTruthy()
    expect(screen.getByText('<img src=x onerror=alert(1)> posição nota risco')).toBeTruthy()
    expect(document.querySelector('main img')).toBeNull()
  })

  it('usa fallback por campo ausente/vazio e fallback genérico para tipo desconhecido', async () => {
    itens = [aviso('1', { titulo: '  ', corpo: 'Corpo da API', tipo: 'PROPOSTA_RECUSADA' }),
      aviso('2', { titulo: 'Título da API', corpo: undefined } as unknown as Partial<Aviso>),
      aviso('3', { tipo: 'NOVO_TIPO', titulo: undefined, corpo: '  ' } as unknown as Partial<Aviso>),
      aviso('4', { tipo: 'OUTRO_TIPO', titulo: 'Texto futuro', corpo: 'Corpo futuro' } as unknown as Partial<Aviso>)]
    abrir(); await carregou()
    expect(screen.getByRole('heading', { name: 'Recebemos sua recusa' })).toBeTruthy()
    expect(screen.getByText('Corpo da API')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Título da API' })).toBeTruthy()
    expect(screen.getByText('Seu pedido está em análise.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Atualização no atendimento' })).toBeTruthy()
    expect(screen.getByText('Há uma atualização no seu atendimento.')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Texto futuro' })).toBeTruthy()
    expect(screen.getByText('Corpo futuro')).toBeTruthy()
  })

  it('exibe vazio sem ações de marcação', async () => {
    itens = []; abrir()
    expect(await screen.findByRole('heading', { name: 'Nenhum aviso por enquanto' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Marcar todos como lidos' })).toBeNull()
  })

  it('contagem zero oculta Marcar todos mesmo com itens não lidos e mais páginas', async () => {
    itens = Array.from({ length: 11 }, (_, indice) => aviso(`aviso-${indice}`))
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => String(url).endsWith('/avisos/contagem') ? Promise.resolve(json({ nao_lidos: 0 })) : original(url, options))
    abrir(); await carregou()
    await screen.findByText('Contagem: 0')
    expect(screen.getAllByText('Novo')).toHaveLength(10)
    expect(screen.getByRole('button', { name: 'Carregar mais' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Marcar todos como lidos' })).toBeNull()
  })

  it.each(['lista vazia', 'só lidos'])('contagem positiva exibe Marcar todos com %s e compartilha a consulta', async (cenario) => {
    itens = cenario === 'lista vazia' ? [] : [aviso('lido', { lido_em: '2026-10-29T12:00:00Z' })]
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => String(url).endsWith('/avisos/contagem') ? Promise.resolve(json({ nao_lidos: 3 })) : original(url, options))
    abrir()
    await screen.findByText('Contagem: 3')
    expect(await screen.findByRole('button', { name: 'Marcar todos como lidos' })).toBeTruthy()
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/avisos/contagem'))).toHaveLength(1)
  })

  it('recupera falha inicial de lista com nova tentativa', async () => {
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => String(url).includes('offset=') ? Promise.reject(new TypeError('offline')) : original(url, options))
    const { user } = abrir()
    expect((await screen.findByRole('alert')).textContent).toContain('Não foi possível carregar seus avisos.')
    fetcher.mockImplementation(original)
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    await carregou()
  })

  it('pagina de dez em dez, deduplica por id e preserva itens ao falhar Carregar mais', async () => {
    itens = Array.from({ length: 12 }, (_, indice) => aviso(`aviso-${indice}`, { titulo: `Aviso ${indice}` }))
    const { user } = abrir(); await carregou()
    expect(screen.getAllByRole('listitem')).toHaveLength(10)
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => String(url).endsWith('offset=10') ? Promise.reject(new TypeError('offline')) : original(url, options))
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Não foi possível carregar mais avisos.')
    expect(screen.getAllByRole('listitem')).toHaveLength(10)
    fetcher.mockImplementation((url, options) => String(url).endsWith('offset=10') ? Promise.resolve(json({ total: 12, itens: [itens[9], itens[10]] })) : original(url, options))
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(11))
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).toBeNull()
    expect(leituras[0]).toBe('/api/v1/avisos?limit=10&offset=0')
  })

  it('Ver pedido é um link real, aguarda POST com CSRF, bloqueia repetição e navega', async () => {
    const resposta = adiar<Response>()
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => options?.method === 'POST' ? resposta.promise : original(url, options))
    const { user } = abrir(); await carregou()
    const link = screen.getByRole('link', { name: /Ver pedido/ })
    expect(link.getAttribute('href')).toBe(`/paciente/solicitacoes/${pedidoId}`)
    await user.click(link)
    expect(link.textContent).toContain('Abrindo…'); expect(link.getAttribute('aria-busy')).toBe('true')
    fireEvent.click(link); fireEvent.click(link)
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    expect(screen.queryByText('Detalhe de destino')).toBeNull()
    const [, options] = fetcher.mock.calls.find(([, options]) => options?.method === 'POST')!
    expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('csrf-sintetico')
    await act(async () => resposta.resolver(new Response(null, { status: 204 })))
    expect(await screen.findByRole('heading', { name: 'Detalhe de destino' })).toBeTruthy()
  })

  it('navega em 3 segundos, aborta o POST e não atualiza cache em resposta tardia', async () => {
    const resposta = adiar<Response>()
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => options?.method === 'POST' ? resposta.promise : original(url, options))
    const { client } = abrir(); await carregou()
    const invalidar = vi.spyOn(client, 'invalidateQueries')
    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('link', { name: /Ver pedido/ }))
    await act(async () => { await vi.advanceTimersByTimeAsync(2_999) })
    expect(screen.queryByText('Detalhe de destino')).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(screen.getByRole('heading', { name: 'Detalhe de destino' })).toBeTruthy()
    expect(fetcher.mock.calls.find(([, options]) => options?.method === 'POST')![1]?.signal?.aborted).toBe(true)
    expect(screen.getByText('Contagem: 1')).toBeTruthy()
    await act(async () => resposta.resolver(new Response(null, { status: 204 })))
    expect(invalidar).not.toHaveBeenCalled()
  })

  it.each(['rede', 'HTTP 500'])('falha de marcação individual (%s) navega sem alerta, retry ou leitura no cache', async (falha) => {
    const client = criarQueryClient()
    // Retém a query sem observadores apenas para inspecionar o cache após navegar.
    client.setQueryDefaults(listaAvisosKey, { gcTime: Infinity })
    const { user } = abrir(client); await carregou()
    const anterior = client.getQueryData(listaAvisosKey)
    const invalidar = vi.spyOn(client, 'invalidateQueries')
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => options?.method === 'POST'
      ? falha === 'rede' ? Promise.reject(new TypeError('offline')) : Promise.resolve(json({ status: 500, title: 'Falha sintética' }, 500))
      : original(url, options))
    await user.click(screen.getByRole('link', { name: /Ver pedido/ }))
    expect(await screen.findByText('Detalhe de destino')).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(client.getQueryData(listaAvisosKey)).toBe(anterior)
    const cache = client.getQueryData<{ pages: { itens: Aviso[] }[] }>(listaAvisosKey)
    expect(cache?.pages[0]?.itens[0]?.lido_em).toBeNull()
    expect(client.getQueryData(avisosOptions.queryKey)).toEqual({ nao_lidos: 1 })
    expect(invalidar).not.toHaveBeenCalled()
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
  })

  it('abre aviso já lido sem POST e só Marcar todos marca os sem pedido', async () => {
    itens = [aviso('lido', { lido_em: '2026-10-29T12:00:00Z' }), aviso('sem-pedido', { solicitacao_id: null })]
    const { user } = abrir(); await carregou()
    expect(screen.getAllByRole('link')).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Marcar todos como lidos' }))
    const mensagem = await screen.findByText('Todos os avisos foram marcados como lidos.')
    expect(mensagem.getAttribute('role')).toBe('status')
    expect(mensagem.tabIndex).toBe(-1)
    expect(document.activeElement).toBe(mensagem)
    await waitFor(() => expect(screen.queryByText('Novo')).toBeNull())
    expect(screen.queryByText('Lido')).toBeNull()
    expect(screen.getByText('Contagem: 0')).toBeTruthy()
    expect(posts).toEqual(['/api/v1/avisos/lidos'])
    await user.click(screen.getByRole('link', { name: /Ver pedido/ }))
    await screen.findByText('Detalhe de destino')
    expect(posts).toHaveLength(1)
  })

  it('Marcar todos não é otimista, bloqueia repetição, preserva páginas e atualiza contador', async () => {
    itens = Array.from({ length: 11 }, (_, indice) => aviso(`aviso-${indice}`))
    const { user } = abrir(); await carregou()
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(11))
    const resposta = adiar<Response>()
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => options?.method === 'POST' ? resposta.promise : original(url, options))
    const botao = screen.getByRole('button', { name: 'Marcar todos como lidos' })
    await user.click(botao); fireEvent.click(botao)
    expect((botao as HTMLButtonElement).disabled).toBe(true)
    expect(botao.getAttribute('aria-busy')).toBe('true')
    expect(screen.getAllByText('Novo')).toHaveLength(11)
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    itens = itens.map((item) => ({ ...item, lido_em: '2026-10-29T12:00:00Z' }))
    await act(async () => resposta.resolver(new Response(null, { status: 204 })))
    await waitFor(() => expect(screen.queryByText('Novo')).toBeNull())
    expect(screen.getAllByRole('listitem')).toHaveLength(11)
    expect(screen.queryByText('Lido')).toBeNull()
    expect(screen.getByText('Contagem: 0')).toBeTruthy()
  })

  it('erro em Marcar todos preserva contador e permite nova tentativa', async () => {
    const { user } = abrir(); await carregou()
    fetcher.mockRejectedValueOnce(new TypeError('offline'))
    await user.click(screen.getByRole('button', { name: 'Marcar todos como lidos' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Não foi possível marcar todos os avisos.')
    expect(screen.getByText('Contagem: 1')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Marcar todos como lidos' }))
    await screen.findByText('Todos os avisos foram marcados como lidos.')
  })

  it.each(['individual', 'todos'])('mantém refresh após 401 e relê CSRF na marcação %s', async (tipo) => {
    const { user } = abrir(); await carregou()
    const original = fetcher.getMockImplementation()!
    let tentativas = 0
    fetcher.mockImplementation(async (url, options) => {
      if (String(url) === '/api/v1/auth/refresh') {
        document.cookie = 'csrf_token=csrf-renovado; path=/'
        return new Response(null, { status: 204 })
      }
      if (options?.method === 'POST') {
        tentativas++
        if (tentativas === 1) return json({ status: 401, title: 'Não autenticado' }, 401)
        expect(new Headers(options.headers).get('X-CSRF-Token')).toBe('csrf-renovado')
        itens = itens.map((item) => ({ ...item, lido_em: '2026-10-29T12:00:00Z' }))
        return new Response(null, { status: 204 })
      }
      return original(url, options)
    })
    await user.click(tipo === 'individual' ? screen.getByRole('link', { name: /Ver pedido/ }) : screen.getByRole('button', { name: 'Marcar todos como lidos' }))
    await screen.findByText(tipo === 'individual' ? 'Detalhe de destino' : 'Todos os avisos foram marcados como lidos.')
    expect(tentativas).toBe(2)
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'))).toHaveLength(1)
  })

  it('aborta ao desmontar e ignora escrita antiga após troca de sessão', async () => {
    const resposta = adiar<Response>()
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => options?.method === 'POST' ? resposta.promise : original(url, options))
    const { user, unmount, client } = abrir(); await carregou()
    await user.click(screen.getByRole('link', { name: /Ver pedido/ }))
    const signal = fetcher.mock.calls.find(([, options]) => options?.method === 'POST')![1]?.signal
    unmount(); expect(signal?.aborted).toBe(true)
    http.iniciarSessao()
    client.setQueryData(avisosOptions.queryKey, { nao_lidos: 55 })
    client.setQueryData(listaAvisosKey, { pages: [{ total: 0, itens: [] }], pageParams: [0] })
    const invalidar = vi.spyOn(client, 'invalidateQueries')
    await act(async () => resposta.resolver(new Response(null, { status: 204 })))
    expect(client.getQueryData(avisosOptions.queryKey)).toEqual({ nao_lidos: 55 })
    expect(invalidar).not.toHaveBeenCalled()
  })

  it('limpa pendência após troca de época sem aplicar resultado antigo na página ainda montada', async () => {
    const resposta = adiar<Response>()
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((url, options) => options?.method === 'POST' ? resposta.promise : original(url, options))
    const { user, client } = abrir(); await carregou()
    const invalidar = vi.spyOn(client, 'invalidateQueries')
    await user.click(screen.getByRole('button', { name: 'Marcar todos como lidos' }))
    http.iniciarSessao()
    await act(async () => resposta.resolver(new Response(null, { status: 204 })))
    expect((screen.getByRole('button', { name: 'Marcar todos como lidos' }) as HTMLButtonElement).disabled).toBe(false)
    expect(screen.queryByText('Todos os avisos foram marcados como lidos.')).toBeNull()
    expect(invalidar).not.toHaveBeenCalled()
  })

  it('permite teclado, passa axe e não grava em storage', async () => {
    const gravar = vi.spyOn(Storage.prototype, 'setItem')
    const { user, container } = abrir(); await carregou()
    expect((await axe(container)).violations).toEqual([])
    const link = screen.getByRole('link', { name: /Ver pedido/ })
    link.focus(); await user.keyboard('{Enter}')
    await screen.findByText('Detalhe de destino')
    expect(gravar).not.toHaveBeenCalled()
  })
})
