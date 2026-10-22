import { lerCsrf } from './csrf'
import { erroDaResposta } from './problem-details'

type Metodo = 'GET' | 'HEAD' | 'OPTIONS' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
interface Opcoes {
  method?: Metodo
  body?: unknown
  headers?: HeadersInit
  signal?: AbortSignal
}

export function criarClienteHttp(
  fetcher: typeof fetch = (...args) => fetch(...args),
  csrf: () => string | undefined = lerCsrf,
) {
  let renovacao: Promise<void> | undefined
  let geracao = 0
  let falhaRenovacao: unknown
  const aoExpirar = new Set<() => void>()

  function expirarSessao() {
    for (const listener of aoExpirar) listener()
  }

  function urlDaApi(path: string): string {
    if (!path.startsWith('/') || path.startsWith('//') || /[\\#]/.test(path)) {
      throw new TypeError('Informe um caminho relativo à API, como /me.')
    }
    const url = new URL(`/api/v1${path}`, 'http://api.local')
    if (!url.pathname.startsWith('/api/v1/')) throw new TypeError('Caminho fora da API.')
    return `${url.pathname}${url.search}`
  }

  async function enviar(url: string, options: Opcoes): Promise<Response> {
    const method = options.method ?? 'GET'
    const headers = new Headers(options.headers)
    headers.set('Accept', 'application/json, application/problem+json')
    headers.delete('X-CSRF-Token')
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      const token = csrf()
      if (token) headers.set('X-CSRF-Token', token)
    }
    if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    return fetcher(url, {
      method, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    })
  }

  async function renovar(): Promise<void> {
    if (!renovacao) {
      renovacao = (async () => {
        falhaRenovacao = undefined
        try {
          const response = await enviar('/api/v1/auth/refresh', { method: 'POST' })
          if (!response.ok) throw await erroDaResposta(response)
        } catch (error) {
          falhaRenovacao = error
          expirarSessao()
          throw error
        } finally {
          geracao += 1
          renovacao = undefined
        }
      })()
    }
    return renovacao
  }

  return {
    aoExpirarSessao(listener: () => void): () => void {
      aoExpirar.add(listener)
      return () => { aoExpirar.delete(listener) }
    },
    async request<T = void>(path: string, options: Opcoes = {}): Promise<T> {
      const url = urlDaApi(path)
      const geracaoInicial = geracao
      // Aguarda a rotação já em andamento antes de enviar novos pedidos protegidos.
      if (renovacao && !url.startsWith('/api/v1/auth/')) await renovacao
      options.signal?.throwIfAborted()
      let response = await enviar(url, options)
      if (response.status === 401 && !url.startsWith('/api/v1/auth/')) {
        if (geracaoInicial === geracao) await renovar()
        else if (falhaRenovacao) throw falhaRenovacao
        options.signal?.throwIfAborted()
        // Recria os headers: o refresh também rotaciona o cookie CSRF.
        response = await enviar(url, options)
        if (response.status === 401) expirarSessao()
      }
      if (!response.ok) throw await erroDaResposta(response)
      if (response.status === 204 || response.status === 205 || options.method === 'HEAD') {
        return undefined as T
      }
      return await response.json() as T
    },
  }
}

export const http = criarClienteHttp()
