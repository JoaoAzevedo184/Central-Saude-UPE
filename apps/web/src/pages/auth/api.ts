import type { QueryClient } from '@tanstack/react-query'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'
import { permitirNovaSessao } from '../../shared/auth/session'

export type RegistroEntrada = components['schemas']['RegistroEntrada']
export type LoginSaida = components['schemas']['LoginSaida']
export type SessaoSaida = components['schemas']['SessaoSaida']

export function trocarSenha(payload: components['schemas']['TrocaSenhaEntrada'], signal: AbortSignal) {
  return http.request('/auth/trocar-senha', { method: 'POST', body: payload, signal })
}

export const termoOptions = {
  queryKey: ['termo-vigente'],
  queryFn: ({ signal }: { signal: AbortSignal }) => http.request<components['schemas']['TermoSaida']>('/termos/vigente', { signal }),
  retry: false,
  staleTime: Infinity,
  gcTime: 0,
}

export async function limparSessaoAnterior(client: QueryClient) {
  const geracao = http.geracaoSessao()
  await client.cancelQueries()
  if (geracao !== http.geracaoSessao()) return false
  client.clear()
  permitirNovaSessao(client)
  return true
}
