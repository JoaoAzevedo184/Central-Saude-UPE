import { queryOptions, useQuery, type QueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import type { components } from '../api/generated/schema'
import { http } from '../api/http'
import { ApiError } from '../api/problem-details'

export const papelSchema = z.enum(['PACIENTE', 'ATENDENTE', 'GESTOR', 'ADMIN'])
export type Papel = z.infer<typeof papelSchema>
export type Sessao = Omit<components['schemas']['EuSaida'], 'papel'> & { papel: Papel }

// Apenas em memória: falha no logout não reabre a sessão ao voltar.
const sessoesEncerradas = new WeakSet<QueryClient>()
export async function encerrarSessaoLocal(client: QueryClient, geracaoEsperada = http.geracaoSessao()) {
  if (geracaoEsperada !== http.geracaoSessao()) return false
  const geracao = http.iniciarSessao()
  sessoesEncerradas.add(client)
  await client.cancelQueries()
  if (geracao !== http.geracaoSessao()) return false
  client.clear()
  return true
}
export function permitirNovaSessao(client: QueryClient) { sessoesEncerradas.delete(client) }

export const sessaoOptions = queryOptions({
  queryKey: ['sessao'],
  queryFn: async ({ signal, client }): Promise<Sessao | null> => {
    if (sessoesEncerradas.has(client)) return null
    try {
      const data = await http.request<components['schemas']['EuSaida']>('/me', { signal })
      // Valida também em runtime: papéis futuros/desconhecidos devem falhar fechados.
      return { ...data, papel: papelSchema.parse(data.papel) }
    } catch (error) {
      if (error instanceof ApiError && error.problem.status === 401) return null
      throw error
    }
  },
  staleTime: 0,
  // Mantém a sessão em memória ao sair da árvore protegida para trocar a senha.
  // Logout/expiração e novo login fazem a limpeza explícita.
  gcTime: Infinity,
  retry: false,
})

export function useSessao() {
  return useQuery(sessaoOptions)
}
