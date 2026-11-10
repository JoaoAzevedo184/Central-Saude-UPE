import { queryOptions } from '@tanstack/react-query'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import type { EstadoIndicadores } from './estado-indicadores'

export type DadosIndicadores = components['schemas']['IndicadoresSaida']
export const indicadoresOptions = (estado: EstadoIndicadores, epoca: number) => queryOptions({
  queryKey: ['indicadores', epoca, estado.de, estado.ate, estado.fila],
  queryFn: ({ signal }) => {
    const params = new URLSearchParams({ de: estado.de, ate: estado.ate })
    if (estado.fila) params.set('fila_id', estado.fila)
    return http.request<DadosIndicadores>(`/equipe/indicadores?${params}`, { signal })
  },
  retry: false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
})

export function prazoNovaTentativa(error: unknown, recebidoEm: number): number {
  if (!(error instanceof ApiError) || error.problem.status !== 503 || error.problem.type !== '/problemas/consulta-demorada') return 0
  const header = error.response.headers.get('Retry-After')?.trim()
  if (!header) return 0
  const prazo = /^\d+$/.test(header) ? recebidoEm + Number(header) * 1000
    : /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT$/.test(header) ? Date.parse(header) : NaN
  return Number.isFinite(prazo) && prazo > recebidoEm ? prazo : 0
}
export function mensagemErroIndicadores(error: unknown) {
  if (error instanceof ApiError) {
    if (error.problem.status === 403) return 'Não foi possível acessar os indicadores. Confira seu acesso com a administração.'
    if (error.problem.status === 404) return 'A fila selecionada não está disponível para consulta.'
    if (error.problem.status === 503 && error.problem.type === '/problemas/consulta-demorada') return 'A consulta demorou demais. Tente um período menor.'
  }
  return 'Não foi possível carregar os indicadores. Tente de novo.'
}
