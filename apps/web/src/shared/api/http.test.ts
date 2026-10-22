import { describe, expect, it, vi } from 'vitest'
import { lerCsrf } from './csrf'
import { criarClienteHttp } from './http'
import { ApiError } from './problem-details'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})
const unauthorized = () => new Response(null, { status: 401 })
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('ADR-003 — cliente HTTP e sessão', () => {
  it.each([401, 403, 500, 'rede'])('notifica a aplicação uma vez por falha do refresh compartilhado: %s', async (status) => {
    const refresh = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      if (url !== '/api/v1/auth/refresh') return unauthorized()
      await refresh.promise
      if (status === 'rede') throw new TypeError('Falha de rede')
      return new Response(null, { status: Number(status) })
    })
    const api = criarClienteHttp(fetcher)
    const expirar = vi.fn()
    const remover = api.aoExpirarSessao(expirar)
    const results = Promise.allSettled([api.request('/a'), api.request('/b')])
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3))
    refresh.resolve(unauthorized())
    await results
    expect(expirar).toHaveBeenCalledTimes(1)
    remover()
    await api.request('/c').catch(() => undefined)
    expect(expirar).toHaveBeenCalledTimes(1)
  })
  it('lê apenas o cookie CSRF e tolera cookie ausente ou malformado', () => {
    expect(lerCsrf('outro=segredo; csrf_token=abc%3D123; fim=x')).toBe('abc=123')
    expect(lerCsrf('outro=x')).toBeUndefined()
    expect(lerCsrf('csrf_token=%')).toBeUndefined()
  })

  it.each(['POST', 'PUT', 'PATCH', 'DELETE'] as const)('envia CSRF em %s com cookies e sem cache', async (method) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }))
    const api = criarClienteHttp(fetcher, () => 'csrf-sintetico')
    await expect(api.request('/recurso', { method, body: { motivo: 'OUTRO' } })).resolves.toBeUndefined()
    const options = fetcher.mock.calls[0]?.[1]
    expect(options).toMatchObject({ credentials: 'same-origin', cache: 'no-store', redirect: 'error' })
    expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('csrf-sintetico')
    expect(new Headers(options?.headers).get('Content-Type')).toBe('application/json')
  })

  it('não envia CSRF em leitura nem permite valor antigo passado pelo chamador', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ ok: true }))
    await criarClienteHttp(fetcher, () => undefined).request('/me', { headers: { 'X-CSRF-Token': 'antigo' } })
    expect(new Headers(fetcher.mock.calls[0]?.[1]?.headers).has('X-CSRF-Token')).toBe(false)
  })

  it('compartilha refresh em 401 concorrentes e relê o CSRF após a rotação', async () => {
    const refresh = deferred<Response>()
    let token = 'antigo'
    let renovado = false
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      if (url === '/api/v1/auth/refresh') {
        const response = await refresh.promise
        token = 'novo'
        renovado = true
        return response
      }
      return renovado ? json({ ok: true }) : unauthorized()
    })
    const api = criarClienteHttp(fetcher, () => token)
    const first = api.request('/a', { method: 'POST', body: {} })
    const second = api.request('/b', { method: 'POST', body: {} })
    await vi.waitFor(() => expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/auth/refresh')).toHaveLength(1))
    refresh.resolve(json({ papel: 'PACIENTE' }))
    await expect(Promise.all([first, second])).resolves.toEqual([{ ok: true }, { ok: true }])
    expect(fetcher).toHaveBeenCalledTimes(5)
    for (const [, options] of fetcher.mock.calls.slice(-2)) {
      expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('novo')
    }
  })

  it('não renova de novo quando um 401 atrasado chega após o refresh', async () => {
    const delayed = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(unauthorized()).mockReturnValueOnce(delayed.promise)
      .mockResolvedValueOnce(json({})).mockImplementation(async () => json({ ok: true }))
    const api = criarClienteHttp(fetcher, () => 'csrf')
    const first = api.request('/a')
    const second = api.request('/b')
    await first
    delayed.resolve(unauthorized())
    await second
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/auth/refresh')).toHaveLength(1)
  })

  it('aguarda refresh em andamento antes de enviar um novo pedido', async () => {
    const refresh = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      if (url === '/api/v1/auth/refresh') return refresh.promise
      return url === '/api/v1/a' ? unauthorized() : json({ ok: true })
    })
    const api = criarClienteHttp(fetcher)
    const first = api.request('/a').catch((error: unknown) => error)
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    const second = api.request('/b')
    expect(fetcher).toHaveBeenCalledTimes(2)
    refresh.resolve(json({}))
    await first
    await expect(second).resolves.toEqual({ ok: true })
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/auth/refresh')).toHaveLength(1)
  })

  it('reutiliza a falha do refresh para um 401 atrasado', async () => {
    const delayed = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(unauthorized()).mockReturnValueOnce(delayed.promise)
      .mockResolvedValue(unauthorized())
    const api = criarClienteHttp(fetcher)
    const first = api.request('/a').catch((error: unknown) => error)
    const second = api.request('/b').catch((error: unknown) => error)
    const error = await first
    delayed.resolve(unauthorized())
    expect(await second).toBe(error)
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it('propaga falha de refresh compartilhada sem loop e permite tentativa posterior', async () => {
    const refresh = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) =>
      url === '/api/v1/auth/refresh' ? refresh.promise : unauthorized())
    const api = criarClienteHttp(fetcher, () => 'csrf')
    const results = Promise.allSettled([api.request('/a'), api.request('/b')])
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3))
    refresh.resolve(unauthorized())
    expect((await results).every((result) => result.status === 'rejected')).toBe(true)
    expect(fetcher).toHaveBeenCalledTimes(3)
    await expect(api.request('/c')).rejects.toBeInstanceOf(ApiError)
    expect(fetcher).toHaveBeenCalledTimes(5)
  })

  it('repete a requisição no máximo uma vez', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(json({})).mockResolvedValue(unauthorized())
    await expect(criarClienteHttp(fetcher).request('/me')).rejects.toMatchObject({ problem: { status: 401 } })
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it.each(['/auth/login', '/auth/registro', '/auth/refresh', '/auth/logout'])('não renova recursivamente %s', async (path) => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(unauthorized())
    await expect(criarClienteHttp(fetcher).request(path, { method: 'POST' })).rejects.toBeInstanceOf(ApiError)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it.each([403, 404, 409, 422, 429, 500])('preserva Problem Details e extensões em %s sem refresh', async (status) => {
    const problem = { type: '/problemas/teste', title: 'Conflito', status, detail: 'Descrição sintética', errors: [], solicitacao_id: 'sintetica' }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(problem), {
      status, headers: { 'Content-Type': 'application/problem+json; charset=utf-8', 'Retry-After': '60' },
    }))
    try {
      await criarClienteHttp(fetcher).request('/recurso')
      expect.fail('A resposta deveria gerar ApiError')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).problem).toEqual(problem)
      expect((error as ApiError).response.headers.get('Retry-After')).toBe('60')
    }
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('usa fallback seguro para HTML e Problem Details inválido', async () => {
    for (const contentType of ['text/html', 'application/problem+json']) {
      const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>proxy</html>', { status: 502, headers: { 'Content-Type': contentType } }))
      await expect(criarClienteHttp(fetcher).request('/me')).rejects.toMatchObject({
        message: 'Não foi possível concluir. Tente novamente mais tarde.', problem: { type: 'about:blank', status: 502 },
      })
    }
  })

  it('propaga erro de rede sem reenviar escrita', async () => {
    const error = new TypeError('Falha de rede')
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(error)
    await expect(criarClienteHttp(fetcher).request('/recurso', { method: 'POST' })).rejects.toBe(error)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('cancelamento não cancela refresh compartilhado nem repete pedido abortado', async () => {
    const refresh = deferred<Response>()
    const controller = new AbortController()
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) =>
      url === '/api/v1/auth/refresh' ? refresh.promise : unauthorized())
    const api = criarClienteHttp(fetcher)
    const result = api.request('/me', { signal: controller.signal }).catch((error: unknown) => error)
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    expect(fetcher.mock.calls[1]?.[1]?.signal).toBeUndefined()
    controller.abort()
    refresh.resolve(json({}))
    expect(await result).toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it.each(['https://externo.example', '//externo.example', '/../fora', '/../../fora', '/me#fragmento', '/\\externo'])('recusa caminho inseguro %s', async (path) => {
    const fetcher = vi.fn<typeof fetch>()
    await expect(criarClienteHttp(fetcher).request(path)).rejects.toBeInstanceOf(TypeError)
    expect(fetcher).not.toHaveBeenCalled()
  })
})
