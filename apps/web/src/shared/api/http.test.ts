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
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

describe('ADR-003 — cliente HTTP e sessão', () => {
  it.each([
    ['logout', 'login'], ['logout', 'registro'], ['refresh', 'login'], ['refresh', 'registro'],
  ].flatMap(([bloqueador, entrada]) => [[bloqueador, entrada, 'ok'], [bloqueador, entrada, 'erro']]))(
    'limita %s travado, libera %s e ignora a resposta antiga (%s) sem perder a fila', async (bloqueador, entrada, respostaAntiga) => {
    vi.useFakeTimers()
    try {
      const antigo = deferred<Response>()
      const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
        if (url === `/api/v1/auth/${bloqueador}`) return antigo.promise
        if (url === `/api/v1/auth/${entrada}`) return json({ papel: 'PACIENTE', trocar_senha: true })
        if (url === '/api/v1/recurso') return unauthorized()
        return json({ ok: true })
      })
      const api = criarClienteHttp(fetcher)
      const expirar = vi.fn(), trocar = vi.fn()
      api.aoExpirarSessao(expirar); api.aoExigirTrocaDeSenha(trocar)
      const anterior = (bloqueador === 'logout' ? api.request('/auth/logout', { method: 'POST' })
        : api.request('/recurso')).catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(0)
      const signal = fetcher.mock.calls.find(([url]) => url === `/api/v1/auth/${bloqueador}`)?.[1]?.signal
      api.iniciarSessao()
      const autenticar = api.request(`/auth/${entrada}`, { method: 'POST' })
      await vi.advanceTimersByTimeAsync(14_999)
      expect(fetcher.mock.calls.some(([url]) => url === `/api/v1/auth/${entrada}`)).toBe(false)
      await vi.advanceTimersByTimeAsync(1)
      expect(signal?.aborted).toBe(true)
      await expect(autenticar).resolves.toMatchObject({ trocar_senha: true })
      expect(await anterior).toMatchObject({ name: bloqueador === 'logout' ? 'TimeoutError' : 'AbortError' })
      const epocaNova = api.geracaoSessao()
      // O transporte falso ignora abort: mesmo assim a continuação perde autoridade.
      antigo.resolve(respostaAntiga === 'ok' ? new Response(null, { status: 204 }) : new Response(JSON.stringify({ type: '/problemas/troca-de-senha-obrigatoria', status: 403 }), {
        status: 403, headers: { 'Content-Type': 'application/problem+json' },
      }))
      await vi.advanceTimersByTimeAsync(0)
      expect(api.geracaoSessao()).toBe(epocaNova)
      expect(api.trocaDeSenhaObrigatoria()).toBe(true)
      expect(expirar).not.toHaveBeenCalled(); expect(trocar).not.toHaveBeenCalled()
      await expect(api.request('/me')).resolves.toEqual({ ok: true })
      await expect(api.request(`/auth/${entrada}`, { method: 'POST' })).resolves.toMatchObject({ trocar_senha: true })
      expect(vi.getTimerCount()).toBe(0)
    } finally { vi.useRealTimers() }
  })

  it('abort de login enfileirado termina imediatamente, não envia e não bloqueia a próxima autenticação', async () => {
    const antigo = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) =>
      url === '/api/v1/auth/logout' ? antigo.promise : json({ papel: 'PACIENTE' }))
    const api = criarClienteHttp(fetcher)
    const logout = api.request('/auth/logout', { method: 'POST' })
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1))
    const controller = new AbortController()
    let concluido = false
    const abortado = api.request('/auth/login', { method: 'POST', signal: controller.signal })
      .catch((error: unknown) => error).finally(() => { concluido = true })
    controller.abort()
    await vi.waitFor(() => expect(concluido).toBe(true))
    expect(await abortado).toMatchObject({ name: 'AbortError' })
    const registro = api.request('/auth/registro', { method: 'POST' })
    antigo.resolve(new Response(null, { status: 204 }))
    await logout
    await expect(registro).resolves.toMatchObject({ papel: 'PACIENTE' })
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/api/v1/auth/logout', '/api/v1/auth/registro'])
  })

  it.each(['logout', 'refresh'])('rejeição tardia de %s após timeout não gera efeitos ou rejeições órfãs', async (bloqueador) => {
    vi.useFakeTimers()
    try {
      const antigo = deferred<Response>()
      const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
        if (url === `/api/v1/auth/${bloqueador}`) return antigo.promise
        return url === '/api/v1/me' ? unauthorized() : json({ papel: 'PACIENTE' })
      })
      const api = criarClienteHttp(fetcher)
      const anterior = (bloqueador === 'logout' ? api.request('/auth/logout', { method: 'POST' })
        : api.request('/me')).catch(() => undefined)
      await vi.advanceTimersByTimeAsync(0)
      const login = api.request('/auth/login', { method: 'POST' })
      await vi.advanceTimersByTimeAsync(15_000)
      await Promise.all([anterior, login])
      const expirar = vi.fn(), trocar = vi.fn(), epoca = api.geracaoSessao()
      api.aoExpirarSessao(expirar); api.aoExigirTrocaDeSenha(trocar)
      antigo.reject(new TypeError('Rede sintética encerrada tarde'))
      await vi.advanceTimersByTimeAsync(0)
      expect(api.geracaoSessao()).toBe(epoca)
      expect(expirar).not.toHaveBeenCalled(); expect(trocar).not.toHaveBeenCalled()
      expect(vi.getTimerCount()).toBe(0)
    } finally { vi.useRealTimers() }
  })

  it('timeout também cobre corpo de login travado e não permite que ele inicie sessão tarde', async () => {
    vi.useFakeTimers()
    try {
      const corpo = deferred<unknown>()
      const resposta = json({})
      vi.spyOn(resposta, 'json').mockReturnValue(corpo.promise)
      const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(resposta).mockResolvedValue(json({ papel: 'PACIENTE' }))
      const api = criarClienteHttp(fetcher)
      const primeiro = api.request('/auth/login', { method: 'POST' }).catch((error: unknown) => error)
      await vi.advanceTimersByTimeAsync(0)
      const proximo = api.request('/auth/registro', { method: 'POST' })
      await vi.advanceTimersByTimeAsync(15_000)
      expect(await primeiro).toMatchObject({ name: 'TimeoutError' })
      await proximo
      const epocaNova = api.geracaoSessao()
      corpo.resolve({ papel: 'PACIENTE', trocar_senha: true })
      await vi.advanceTimersByTimeAsync(0)
      expect(api.geracaoSessao()).toBe(epocaNova)
      expect(api.trocaDeSenhaObrigatoria()).toBe(false)
      expect(vi.getTimerCount()).toBe(0)
    } finally { vi.useRealTimers() }
  })

  it('403 de troca obrigatória no refresh bloqueia o fluxo sem expirar a sessão', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(new Response(JSON.stringify({
      type: '/problemas/troca-de-senha-obrigatoria', status: 403, title: 'Troca obrigatória',
    }), { status: 403, headers: { 'Content-Type': 'application/problem+json' } }))
    const api = criarClienteHttp(fetcher)
    const expirar = vi.fn(), trocar = vi.fn()
    api.aoExpirarSessao(expirar); api.aoExigirTrocaDeSenha(trocar)
    await expect(api.request('/me')).rejects.toMatchObject({ problem: { status: 403 } })
    expect(expirar).not.toHaveBeenCalled()
    expect(trocar).toHaveBeenCalledTimes(1)
    expect(api.trocaDeSenhaObrigatoria()).toBe(true)
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('B1: refresh antigo não altera a renovação já iniciada pela nova sessão', async () => {
    const antigo = deferred<Response>(), atual = deferred<Response>()
    let renovado = false, numeroRefresh = 0
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      if (url === '/api/v1/auth/refresh') {
        numeroRefresh += 1
        if (numeroRefresh === 1) return antigo.promise
        const resposta = await atual.promise
        renovado = true
        return resposta
      }
      return renovado ? json({ ok: true }) : unauthorized()
    })
    const api = criarClienteHttp(fetcher)
    const anterior = api.request('/a').catch((error: unknown) => error)
    await vi.waitFor(() => expect(numeroRefresh).toBe(1))
    api.iniciarSessao()
    const nova = api.request('/b')
    expect(numeroRefresh).toBe(1)
    antigo.resolve(unauthorized())
    expect(await anterior).toMatchObject({ name: 'AbortError' })
    await vi.waitFor(() => expect(numeroRefresh).toBe(2))
    const concorrente = api.request('/c')
    expect(fetcher.mock.calls.filter(([url]) => url === '/api/v1/c')).toHaveLength(0)
    atual.resolve(json({}))
    await expect(Promise.all([nova, concorrente])).resolves.toEqual([{ ok: true }, { ok: true }])
    expect(numeroRefresh).toBe(2)
  })

  it.each([
    ['/auth/logout', '/auth/login'], ['/auth/logout', '/auth/registro'],
    ['/auth/refresh', '/auth/login'], ['/auth/refresh', '/auth/registro'],
  ])('B1: %s termina de alterar cookies antes de %s', async (pendente, entrada) => {
    const resposta = deferred<Response>()
    let cookieSessao = 'antiga'
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      if (url === `/api/v1${pendente}`) {
        const response = await resposta.promise
        // Simula a aplicação de Set-Cookie antes da resolução do fetch.
        cookieSessao = pendente === '/auth/logout' ? '' : 'antiga-renovada'
        return response
      }
      if (url === `/api/v1${entrada}`) {
        cookieSessao = 'nova'
        return json({ papel: 'PACIENTE', trocar_senha: true })
      }
      return cookieSessao === 'antiga' ? unauthorized() : json({ ok: true })
    })
    const api = criarClienteHttp(fetcher)
    const anterior = (pendente === '/auth/logout'
      ? api.request(pendente, { method: 'POST' }) : api.request('/recurso')).catch(() => undefined)
    await vi.waitFor(() => expect(fetcher.mock.calls.some(([url]) => url === `/api/v1${pendente}`)).toBe(true))
    const login = api.request(entrada, { method: 'POST', body: { senha: 'Sintetica!123' } })
    expect(fetcher.mock.calls.filter(([url]) => url === `/api/v1${entrada}`)).toHaveLength(0)
    resposta.resolve(new Response(null, { status: 204 }))
    await Promise.all([anterior, login])
    expect(cookieSessao).toBe('nova')
    expect(api.trocaDeSenhaObrigatoria()).toBe(true)
  })

  it.each([true, false])('B1: falha de refresh antigo não expira a nova sessão (troca obrigatória: %s)', async (trocarSenha) => {
    const refresh = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) =>
      url === '/api/v1/auth/refresh' ? refresh.promise : unauthorized())
    const api = criarClienteHttp(fetcher)
    const expirar = vi.fn()
    api.aoExpirarSessao(expirar)
    const antigo = api.request('/me').catch((error: unknown) => error)
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
    const geracaoNova = api.iniciarSessao(trocarSenha)
    refresh.resolve(unauthorized())
    expect(await antigo).toMatchObject({ name: 'AbortError' })
    expect(expirar).not.toHaveBeenCalled()
    expect(api.geracaoSessao()).toBe(geracaoNova)
    expect(api.trocaDeSenhaObrigatoria()).toBe(trocarSenha)
  })

  it.each([401, 403])('B1: resposta %s de sessão antiga não afeta a nova', async (status) => {
    const resposta = deferred<Response>()
    const fetcher = vi.fn<typeof fetch>().mockReturnValue(resposta.promise)
    const api = criarClienteHttp(fetcher)
    const expirar = vi.fn(), trocar = vi.fn()
    api.aoExpirarSessao(expirar); api.aoExigirTrocaDeSenha(trocar)
    const antigo = api.request('/recurso').catch((error: unknown) => error)
    api.iniciarSessao()
    resposta.resolve(new Response(JSON.stringify({ type: '/problemas/troca-de-senha-obrigatoria' }), {
      status, headers: { 'Content-Type': 'application/problem+json' },
    }))
    expect(await antigo).toMatchObject({ name: 'AbortError' })
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(expirar).not.toHaveBeenCalled()
    expect(trocar).not.toHaveBeenCalled()
    expect(api.trocaDeSenhaObrigatoria()).toBe(false)
  })

  it('422 de trocar-senha preserva o erro de senha_atual e envia CSRF sem refresh', async () => {
    const errors = [{ loc: ['body', 'senha_atual'], msg: 'Senha atual incorreta.', type: 'value_error' }]
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
      type: '/problemas/validacao', status: 422, title: 'Validação', errors,
    }), { status: 422, headers: { 'Content-Type': 'application/problem+json' } }))
    const api = criarClienteHttp(fetcher, () => 'csrf-sintetico')
    const expirar = vi.fn(), trocar = vi.fn()
    api.aoExpirarSessao(expirar); api.aoExigirTrocaDeSenha(trocar)
    await expect(api.request('/auth/trocar-senha', { method: 'POST', body: {
      senha_atual: 'Temporaria!123', senha_nova: 'NovaSintetica!123',
    } })).rejects.toMatchObject({ problem: { status: 422, errors } })
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(new Headers(fetcher.mock.calls[0]?.[1]?.headers).get('X-CSRF-Token')).toBe('csrf-sintetico')
    expect(expirar).not.toHaveBeenCalled()
    expect(trocar).not.toHaveBeenCalled()
  })

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
    const sinalRefresh = fetcher.mock.calls[1]?.[1]?.signal
    expect(sinalRefresh).not.toBe(controller.signal)
    controller.abort()
    expect(sinalRefresh?.aborted).toBe(false)
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
