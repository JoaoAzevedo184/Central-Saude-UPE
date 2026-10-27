import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Rotas } from './Rotas'
import { criarQueryClient } from './query-client'
import { sessaoOptions } from '../shared/auth/session'
import { http } from '../shared/api/http'
import { rotaAposLogin } from '../shared/auth/retorno'
import { ExigirPapel } from '../shared/auth/ExigirPapel'
import type { components } from '../shared/api/generated/schema'

afterEach(() => { vi.unstubAllGlobals(); http.iniciarSessao() })

function abrir(path: string, anteriores: string[] = []) {
  const client = criarQueryClient()
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[...anteriores, path]}><Rotas /><Localizacao /></MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

function Localizacao() {
  const location = useLocation()
  const navigate = useNavigate()
  return <>
    <div data-testid="localizacao">{JSON.stringify({ pathname: location.pathname, state: location.state })}</div>
    <button onClick={() => void navigate(-1)}>Voltar no histórico</button>
  </>
}

function responderPapel(papel: string, trocarSenha?: components['schemas']['EuSaida']['trocar_senha']) {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async (url) => new Response(
    JSON.stringify(String(url).includes('/solicitacoes') ? { total: 0, itens: [] } : String(url).endsWith('/avisos/contagem') ? { nao_lidos: 0 } : { id: '00000000-0000-4000-8000-000000000001', papel, nome: null, filas: [], ...(trocarSenha === undefined ? {} : { trocar_senha: trocarSenha }) }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  )))
}

describe('ADR-003/ADR-025/ADR-028 — rotas e proteção por papel', () => {
  it('preserva trocar_senha de /me e encaminha ao fluxo provisório', async () => {
    const dados = { id: '00000000-0000-4000-8000-000000000001', papel: 'PACIENTE', nome: null, filas: [], trocar_senha: true } satisfies components['schemas']['EuSaida']
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(dados))))
    const client = abrir('/paciente')
    await screen.findByRole('heading', { name: 'Troca de senha obrigatória' })
    expect(client.getQueryData(sessaoOptions.queryKey)).toEqual(dados)
    expect(screen.queryByRole('main', { name: 'Área do paciente' })).toBeNull()
  })

  it('transiciona de /me sem bloqueio para troca obrigatória após revalidação', async () => {
    responderPapel('PACIENTE')
    const client = abrir('/paciente')
    await screen.findByRole('main', { name: 'Área do paciente' })
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({
      id: '00000000-0000-4000-8000-000000000001', papel: 'PACIENTE', nome: null, filas: [], trocar_senha: true,
    }))))
    await act(async () => { await client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    await screen.findByRole('heading', { name: 'Troca de senha obrigatória' })
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ trocar_senha: true })
  })

  it.each([undefined, null])('preserva a sessão normal de /me com trocar_senha %s', async (trocarSenha) => {
    responderPapel('PACIENTE', trocarSenha)
    const client = abrir('/paciente')
    await screen.findByRole('main', { name: 'Área do paciente' })
    const sessao = client.getQueryData<components['schemas']['EuSaida']>(sessaoOptions.queryKey)
    expect(sessao?.papel).toBe('PACIENTE')
    expect(sessao?.trocar_senha).toBe(trocarSenha)
    expect(http.trocaDeSenhaObrigatoria()).toBe(false)
    expect(JSON.parse(screen.getByTestId('localizacao').textContent!).pathname).toBe('/paciente')
  })

  it.each(['/me', '/recurso-autenticado'])('403 troca obrigatória em %s redireciona sem limpar sessão nem renovar', async (path) => {
    responderPapel('PACIENTE')
    const client = abrir('/paciente')
    await screen.findByRole('main', { name: 'Área do paciente' })
    const sessao = client.getQueryData(sessaoOptions.queryKey)
    client.setQueryDefaults(['dados-sinteticos'], { gcTime: Infinity })
    client.setQueryData(['dados-sinteticos'], { id: 'preservado' })
    const limpar = vi.spyOn(client, 'clear')
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify({
      type: '/problemas/troca-de-senha-obrigatoria', status: 403, title: 'Troca obrigatória',
    }), { status: 403, headers: { 'Content-Type': 'application/problem+json' } }))
    vi.stubGlobal('fetch', fetcher)
    await act(async () => {
      if (path === '/me') await client.invalidateQueries({ queryKey: sessaoOptions.queryKey })
      else await http.request(path).catch(() => undefined)
    })
    await screen.findByRole('heading', { name: 'Troca de senha obrigatória' })
    expect(client.getQueryData(sessaoOptions.queryKey)).toEqual(sessao)
    expect(client.getQueryData(['dados-sinteticos'])).toEqual({ id: 'preservado' })
    expect(limpar).not.toHaveBeenCalled()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1${path}`)
  })
  it.each([
    [null, undefined, '/entrar', 'Entrar'],
    ['PACIENTE', undefined, '/paciente', 'Meus atendimentos'],
    ['ATENDENTE', undefined, '/equipe', null],
    ['GESTOR', undefined, '/equipe', null],
    ['ADMIN', undefined, '/equipe', null],
    ['PACIENTE', true, '/trocar-senha', 'Troca de senha obrigatória'],
    ['GESTOR', true, '/trocar-senha', 'Troca de senha obrigatória'],
  ] as const)('redireciona / com papel %s e trocar_senha %s para %s substituindo o histórico', async (papel, trocarSenha, destino, titulo) => {
    if (papel) responderPapel(papel, trocarSenha)
    else vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(null, { status: 401 })))
    const user = userEvent.setup()
    abrir('/', ['/anterior'])
    await waitFor(() => expect(JSON.parse(screen.getByTestId('localizacao').textContent!).pathname).toBe(destino))
    if (titulo) await screen.findByRole('heading', { name: titulo })
    expect(screen.queryByText('Base do frontend. Telas em desenvolvimento.')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Voltar no histórico' }))
    await waitFor(() => expect(JSON.parse(screen.getByTestId('localizacao').textContent!).pathname).toBe('/anterior'))
  })

  it.each([
    ['PACIENTE', '/paciente', 'Área do paciente'],
    ['ATENDENTE', '/equipe', 'Área da equipe'],
    ['GESTOR', '/equipe', 'Área da equipe'],
    ['ADMIN', '/equipe', 'Área da equipe'],
  ])('permite %s em %s com o layout do papel', async (papel, path, label) => {
    responderPapel(papel)
    abrir(path)
    const layout = await screen.findByRole('main', { name: label })
    if (papel === 'PACIENTE') expect(within(layout).getByRole('heading', { name: 'Meus atendimentos' })).toBeTruthy()
    else expect(layout.childElementCount).toBe(0)
  })

  it.each([
    ['PACIENTE', '/equipe'], ['ATENDENTE', '/paciente'],
    ['GESTOR', '/paciente'], ['ADMIN', '/paciente'],
  ])('nega %s em %s', async (papel, path) => {
    responderPapel(papel)
    abrir(path)
    expect((await screen.findByRole('alert')).textContent).toBe('Acesso não permitido.')
    expect(screen.queryByRole('main')).toBeNull()
  })

  it('falha fechada para papel desconhecido recebido do servidor', async () => {
    responderPapel('DESCONHECIDO')
    abrir('/equipe')
    expect((await screen.findByRole('alert')).textContent).toBe('Não foi possível verificar a sessão.')
    expect(screen.queryByRole('main')).toBeNull()
  })

  it('redireciona sessão ausente ou revogada para entrar preservando a origem', async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetcher)
    abrir('/paciente?aba=abertas#pedido')
    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeTruthy()
    const location = JSON.parse(screen.getByTestId('localizacao').textContent!)
    expect(location).toEqual({ pathname: '/entrar', state: { origem: '/paciente' } })
    expect(rotaAposLogin(location.state)).toBe('/paciente')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('a própria guarda manda quem não tem sessão para entrar com a origem', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(null, { status: 401 })))
    render(<QueryClientProvider client={criarQueryClient()}>
      <MemoryRouter initialEntries={['/equipe?ordenacao=chegada#fila']}>
        <Routes>
          <Route element={<ExigirPapel papeis={['ATENDENTE']} />}>
            <Route path="/equipe" element={<main>Protegido</main>} />
          </Route>
          <Route path="/entrar" element={<h1>Entrar</h1>} />
        </Routes>
        <Localizacao />
      </MemoryRouter>
    </QueryClientProvider>)
    await screen.findByRole('heading', { name: 'Entrar' })
    expect(JSON.parse(screen.getByTestId('localizacao').textContent!)).toEqual({
      pathname: '/entrar', state: { origem: '/equipe' },
    })
    expect(screen.queryByRole('main')).toBeNull()
  })

  it.each([401, 403, 503, 'rede'])('encerra a sessão quando refresh de qualquer consulta falha: %s', async (falha) => {
    responderPapel('PACIENTE')
    const client = abrir('/paciente?aba=abertas#pedido')
    await screen.findByRole('main', { name: 'Área do paciente' })
    client.setQueryData(['dados-do-paciente'], { id: 'sintetico' })
    let sinalPendente: AbortSignal | undefined
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url, options) => {
      if (url === '/api/v1/avisos') {
        sinalPendente = options?.signal ?? undefined
        return new Promise<Response>((resolve) => {
          // Mesmo um transporte que termine tarde não pode repor dados no cache.
          sinalPendente?.addEventListener('abort', () => resolve(new Response(JSON.stringify({ id: 'tardio' }))))
        })
      }
      if (url === '/api/v1/auth/refresh') {
        if (falha === 'rede') throw new TypeError('Falha de rede sintética')
        return new Response(null, { status: Number(falha) })
      }
      return new Response(null, { status: 401 })
    })
    vi.stubGlobal('fetch', fetcher)
    let pendente!: Promise<unknown>
    await act(async () => {
      pendente = client.fetchQuery({ queryKey: ['avisos'], queryFn: ({ signal }) => http.request('/avisos', { signal }) }).catch(() => undefined)
      await vi.waitFor(() => expect(sinalPendente).toBeDefined())
      // A sessão /me continua em cache: a falha acontece em outra consulta.
      await client.fetchQuery({ queryKey: ['filas'], queryFn: ({ signal }) => http.request('/filas', { signal }) }).catch(() => undefined)
    })
    await screen.findByRole('heading', { name: 'Entrar' })
    await pendente
    expect(sinalPendente?.aborted).toBe(true)
    expect(client.getQueryData(sessaoOptions.queryKey)).toBeUndefined()
    expect(client.getQueryData(['dados-do-paciente'])).toBeUndefined()
    expect(client.getQueryData(['avisos'])).toBeUndefined()
    expect(client.isFetching()).toBe(0)
    expect(JSON.parse(screen.getByTestId('localizacao').textContent!)).toEqual({
      pathname: '/entrar', state: { origem: '/paciente' },
    })
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/auth/refresh')).toHaveLength(1)
  })

  it('mostra estado de espera sem abrir o layout protegido', async () => {
    let resolve!: (value: Response) => void
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockReturnValue(new Promise((done) => { resolve = done })))
    abrir('/paciente')
    expect(screen.getByRole('status').textContent).toBe('Verificando sessão…')
    expect(screen.queryByRole('main')).toBeNull()
    resolve(new Response(null, { status: 503 }))
    await screen.findByRole('alert')
  })

  it('não confunde falha de rede/servidor com sessão anônima nem faz retries', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 503 }))
    vi.stubGlobal('fetch', fetcher)
    abrir('/equipe')
    expect((await screen.findByRole('alert')).textContent).toBe('Não foi possível verificar a sessão.')
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('main')).toBeNull()
  })

  it('revalida o papel no servidor e fecha o layout quando o papel muda', async () => {
    responderPapel('PACIENTE')
    const client = abrir('/paciente')
    await screen.findByRole('main', { name: 'Área do paciente' })
    responderPapel('ATENDENTE')
    await client.invalidateQueries({ queryKey: sessaoOptions.queryKey })
    await waitFor(() => expect(screen.queryByRole('main')).toBeNull())
    expect((await screen.findByRole('alert')).textContent).toBe('Acesso não permitido.')
  })

  it('não abre layouts para rotas não cadastradas', () => {
    abrir('/inexistente')
    expect(screen.getByRole('alert').textContent).toBe('Página não encontrada.')
  })
})
