import { lerCsrf } from './csrf'
import { ApiError, erroDaResposta } from './problem-details'
import { exigeTrocaDeSenha } from '../auth/troca-de-senha'
import type { components } from './generated/schema'

type Metodo = 'GET' | 'HEAD' | 'OPTIONS' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
interface Opcoes {
  method?: Metodo
  body?: unknown
  headers?: HeadersInit
  signal?: AbortSignal
}

// Limita cada escrita coordenada, incluindo a leitura de seu corpo de resposta.
export const limiteOperacaoAuthMs = 15_000

function aguardarComAbort<T>(resultado: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const abortar = () => { signal.removeEventListener('abort', abortar); reject(signal.reason) }
    if (signal.aborted) abortar()
    else signal.addEventListener('abort', abortar, { once: true })
    // Mantém os dois handlers mesmo após abort: transportes tardios não geram
    // rejeições órfãs nem recuperam o controle da fila.
    resultado.then((valor) => {
      signal.removeEventListener('abort', abortar); resolve(valor)
    }, (error: unknown) => {
      signal.removeEventListener('abort', abortar); reject(error)
    })
  })
}

export function criarClienteHttp(
  fetcher: typeof fetch = (...args) => fetch(...args),
  csrf: () => string | undefined = lerCsrf,
) {
  let renovacao: Promise<void> | undefined
  let geracao = 0
  let falhaRenovacao: unknown
  let epoca = 0
  let trocaObrigatoria = false
  let escritaCookies: Promise<void> = Promise.resolve()
  const aoExpirar = new Set<() => void>()
  const aoExigirTroca = new Set<() => void>()

  function iniciarSessao(exigeTroca = false): number {
    epoca += 1
    renovacao = undefined
    falhaRenovacao = undefined
    geracao = 0
    trocaObrigatoria = exigeTroca
    return epoca
  }

  function serializarCookies<T>(acao: (signal: AbortSignal) => Promise<T>, signal?: AbortSignal): Promise<T> {
    const resultado = escritaCookies.then(async () => {
      signal?.throwIfAborted()
      const controller = new AbortController()
      const abortar = () => controller.abort(signal?.reason)
      signal?.addEventListener('abort', abortar, { once: true })
      const timer = setTimeout(() => {
        controller.abort(new DOMException('O tempo para autenticar terminou. Tente novamente.', 'TimeoutError'))
      }, limiteOperacaoAuthMs)
      try {
        return await aguardarComAbort(acao(controller.signal), controller.signal)
      } finally {
        clearTimeout(timer)
        signal?.removeEventListener('abort', abortar)
      }
    })
    // A fila sobrevive a falhas e não é descartada ao mudar a época: Set-Cookie
    // é aplicado antes do JavaScript. No limite, abortamos o fetch anterior
    // antes de liberar o próximo; apenas abandonar sua Promise seria inseguro.
    escritaCookies = resultado.then(() => undefined, () => undefined)
    return signal ? aguardarComAbort(resultado, signal) : resultado
  }

  function verificarEpoca(inicial: number) {
    if (inicial !== epoca) throw new DOMException('A sessão mudou.', 'AbortError')
  }

  function tratarTrocaObrigatoria(error: unknown): boolean {
    if (!(error instanceof ApiError) || error.problem.status !== 403
      || error.problem.type !== '/problemas/troca-de-senha-obrigatoria') return false
    trocaObrigatoria = true
    for (const listener of aoExigirTroca) listener()
    return true
  }

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
      const epocaInicial = epoca
      renovacao = (async () => {
        falhaRenovacao = undefined
        try {
          await serializarCookies(async (signal) => {
            verificarEpoca(epocaInicial)
            const response = await enviar('/api/v1/auth/refresh', { method: 'POST', signal })
            signal.throwIfAborted()
            verificarEpoca(epocaInicial)
            if (!response.ok) {
              const error = await erroDaResposta(response)
              signal.throwIfAborted()
              throw error
            }
          })
          verificarEpoca(epocaInicial)
        } catch (error) {
          verificarEpoca(epocaInicial)
          falhaRenovacao = error
          if (!tratarTrocaObrigatoria(error)) expirarSessao()
          throw error
        } finally {
          if (epocaInicial === epoca) {
            geracao += 1
            renovacao = undefined
          }
        }
      })()
    }
    return renovacao
  }

  async function realizar<T>(url: string, options: Opcoes, epocaInicial: number): Promise<T> {
    const novaSessao = options.method === 'POST' && ['/api/v1/auth/login', '/api/v1/auth/registro'].includes(url)
    // Um login explícito estabelece uma sessão nova, mesmo se a anterior
    // expirar enquanto as credenciais estão sendo verificadas.
    const verificarAtual = () => {
      options.signal?.throwIfAborted()
      if (!novaSessao) verificarEpoca(epocaInicial)
    }
    const geracaoInicial = geracao
    // Aguarda a rotação já em andamento antes de enviar novos pedidos protegidos.
    if (renovacao && !url.startsWith('/api/v1/auth/')) await renovacao
    verificarAtual()
    options.signal?.throwIfAborted()
    let response = await enviar(url, options)
    verificarAtual()
    if (response.status === 401 && !url.startsWith('/api/v1/auth/')) {
      if (geracaoInicial === geracao) await renovar()
      else if (falhaRenovacao) throw falhaRenovacao
      verificarAtual()
      options.signal?.throwIfAborted()
      // Recria os headers: o refresh também rotaciona o cookie CSRF.
      response = await enviar(url, options)
      verificarAtual()
      if (response.status === 401) expirarSessao()
    }
    if (!response.ok) {
      const error = await erroDaResposta(response)
      verificarAtual()
      tratarTrocaObrigatoria(error)
      throw error
    }
    if (response.status === 204 || response.status === 205 || options.method === 'HEAD') {
      return undefined as T
    }
    if (novaSessao) {
      // O registro retorna SessaoSaida, compatível com LoginSaida sem a flag opcional.
      const dados: components['schemas']['LoginSaida'] = await response.json()
      verificarAtual()
      iniciarSessao(exigeTrocaDeSenha(dados))
      return dados as T
    }
    const dados = await response.json() as T
    verificarAtual()
    return dados
  }

  return {
    geracaoSessao: () => epoca,
    trocaDeSenhaObrigatoria: () => trocaObrigatoria,
    iniciarSessao,
    aoExigirTrocaDeSenha(listener: () => void): () => void {
      aoExigirTroca.add(listener)
      return () => { aoExigirTroca.delete(listener) }
    },
    aoExpirarSessao(listener: () => void): () => void {
      aoExpirar.add(listener)
      return () => { aoExpirar.delete(listener) }
    },
    request<T = void>(path: string, options: Opcoes = {}): Promise<T> {
      try {
        const url = urlDaApi(path)
        const epocaInicial = epoca
        if (url.startsWith('/api/v1/auth/') && options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method)) {
          return serializarCookies((signal) => realizar<T>(url, { ...options, signal }, epocaInicial), options.signal)
        }
        return realizar<T>(url, options, epocaInicial)
      } catch (error) {
        return Promise.reject(error)
      }
    },
  }
}

export const http = criarClienteHttp()
