import { queryOptions } from '@tanstack/react-query'
import type { components, operations } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'

export type Pedido = components['schemas']['SolicitacaoItem']
export type DetalhePedido = components['schemas']['SolicitacaoDetalhe']
export type Situacao = NonNullable<operations['listar_api_v1_solicitacoes_get']['parameters']['query']>['situacao'] & string
export const limitePedidos = 5
const base = ['pedidos-paciente'] as const
export const pedidosKey = base
export function listarPedidos(situacao: Situacao, limit: number, offset: number, signal: AbortSignal) {
  return http.request<components['schemas']['PaginaSolicitacoes']>(`/solicitacoes?situacao=${situacao}&limit=${limit}&offset=${offset}`, { signal })
}
export const pedidosOptions = (situacao: Situacao, pagina: number) => queryOptions({
  queryKey: [...base, situacao, pagina],
  queryFn: ({ signal }) => listarPedidos(situacao, limitePedidos, pagina * limitePedidos, signal),
})
export function temProposta(pedido: Pedido) { return pedido.status === 'EM_PROPOSTA' && pedido.agendamento_ativo?.status === 'PROPOSTO' }
export const propostasOptions = queryOptions({
  queryKey: [...base, 'propostas'],
  queryFn: async ({ signal }): Promise<Pedido[]> => {
    let offset = 0
    while (true) {
      const pagina = await listarPedidos('abertas', 100, offset, signal)
      const propostas = pagina.itens.filter(temProposta)
      if (propostas.length || !pagina.itens.length || offset + pagina.itens.length >= pagina.total) return propostas
      offset += pagina.itens.length
    }
  },
})
export const avisosOptions = queryOptions({
  queryKey: ['avisos', 'contagem'],
  queryFn: ({ signal }) => http.request<components['schemas']['ContagemSaida']>('/avisos/contagem', { signal }),
  refetchOnWindowFocus: 'always',
})
