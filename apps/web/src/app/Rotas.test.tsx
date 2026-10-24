import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Rotas } from './Rotas'
import { criarQueryClient } from './query-client'
import { sessaoOptions } from '../shared/auth/session'
import { http } from '../shared/api/http'
import { rotaAposLogin } from '../shared/auth/retorno'
import { ExigirPapel } from '../shared/auth/ExigirPapel'

afterEach(() => vi.unstubAllGlobals())

function abrir(path: string) {
  const client = criarQueryClient()
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}><Rotas /><Localizacao /></MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

function Localizacao() {
  const location = useLocation()
  return <div data-testid="localizacao">{JSON.stringify({ pathname: location.pathname, state: location.state })}</div>
}

function responderPapel(papel: string) {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => new Response(
    JSON.stringify({ id: '00000000-0000-4000-8000-000000000001', papel, nome: null, filas: [] }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  )))
}

describe('ADR-003/ADR-025/ADR-028 — rotas e proteção por papel', () => {
  it('mantém a entrada pública sem consultar sessão nem renderizar telas de negócio', () => {
    const fetcher = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetcher)
    abrir('/')
    expect(screen.getByRole('heading', { name: 'Central de Teleagendamento' })).toBeTruthy()
    expect(fetcher).not.toHaveBeenCalled()
  })

  it.each([
    ['PACIENTE', '/paciente', 'Área do paciente'],
    ['ATENDENTE', '/equipe', 'Área da equipe'],
    ['GESTOR', '/equipe', 'Área da equipe'],
    ['ADMIN', '/equipe', 'Área da equipe'],
  ])('permite %s em %s com layout vazio', async (papel, path, label) => {
    responderPapel(papel)
    abrir(path)
    const layout = await screen.findByRole('main', { name: label })
    expect(layout.childElementCount).toBe(0)
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
