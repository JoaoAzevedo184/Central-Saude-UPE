import type { QueryClient } from '@tanstack/react-query'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'

export type RegistroEntrada = components['schemas']['RegistroEntrada']
export type SessaoSaida = components['schemas']['SessaoSaida']

export const termoOptions = {
  queryKey: ['termo-vigente'],
  queryFn: ({ signal }: { signal: AbortSignal }) => http.request<components['schemas']['TermoSaida']>('/termos/vigente', { signal }),
  retry: false,
  staleTime: Infinity,
  gcTime: 0,
}

export async function limparSessaoAnterior(client: QueryClient) {
  await client.cancelQueries()
  client.clear()
}
