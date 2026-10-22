import { queryOptions, useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import type { components } from '../api/generated/schema'
import { http } from '../api/http'
import { ApiError } from '../api/problem-details'

export const papelSchema = z.enum(['PACIENTE', 'ATENDENTE', 'GESTOR', 'ADMIN'])
export type Papel = z.infer<typeof papelSchema>
export type Sessao = Omit<components['schemas']['EuSaida'], 'papel'> & { papel: Papel }

export const sessaoOptions = queryOptions({
  queryKey: ['sessao'],
  queryFn: async ({ signal }): Promise<Sessao | null> => {
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
  gcTime: 0,
  retry: false,
})

export function useSessao() {
  return useQuery(sessaoOptions)
}
