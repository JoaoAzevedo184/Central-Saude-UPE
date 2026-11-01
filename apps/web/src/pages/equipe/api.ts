import { queryOptions, type QueryClient } from '@tanstack/react-query'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'
import type { EstadoFila } from './estado-fila'

export type FilaEquipe = components['schemas']['FilaEquipeSaida']
export type PedidoEquipe = components['schemas']['ItemPainel']
export type DetalheEquipe = components['schemas']['SolicitacaoEquipeSaida']
export const detalheEquipeOptions = (id: string) => queryOptions({
  queryKey: ['pedido-equipe', id],
  queryFn: ({ signal }) => buscarDetalheEquipe(id, signal),
  refetchOnWindowFocus: 'always',
})
export function buscarDetalheEquipe(id: string, signal: AbortSignal) {
  return http.request<DetalheEquipe>(`/equipe/solicitacoes/${encodeURIComponent(id)}`, { signal })
}
export async function incorporarDetalheEquipe(client: QueryClient, pedido: DetalheEquipe, signal: AbortSignal, epoca: number) {
  await client.cancelQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey })
  if (signal.aborted || epoca !== http.geracaoSessao()) return
  client.setQueryData(detalheEquipeOptions(pedido.id).queryKey, pedido)
}
export function invalidarFilaEquipe(client: QueryClient) {
  void client.invalidateQueries({ queryKey: ['fila-equipe'] })
  void client.invalidateQueries({ queryKey: ['filas-equipe'] })
}
export const limitePedidosEquipe = 20
export const filasEquipeOptions = queryOptions({
  queryKey: ['filas-equipe'],
  queryFn: async ({ signal }): Promise<FilaEquipe[]> => {
    const filas: FilaEquipe[] = []
    let offset = 0
    while (true) {
      const pagina = await http.request<components['schemas']['PaginaFilasEquipe']>(`/equipe/filas?limit=100&offset=${offset}`, { signal })
      filas.push(...pagina.itens)
      offset += pagina.itens.length
      if (!pagina.itens.length || offset >= pagina.total) break
    }
    return [...new Map(filas.map((fila) => [fila.id, fila])).values()].sort((a, b) => Number(b.ativa) - Number(a.ativa))
  },
  refetchOnWindowFocus: 'always',
})
export const pedidosEquipeOptions = (estado: EstadoFila) => queryOptions({
  queryKey: ['fila-equipe', estado.fila, estado.ordem, estado.status, estado.pagina],
  queryFn: ({ signal }) => {
    const params = new URLSearchParams({ ordenacao: estado.ordem, limit: String(limitePedidosEquipe), offset: String((estado.pagina - 1) * limitePedidosEquipe) })
    if (estado.status !== 'todos') params.set('status', estado.status)
    return http.request<components['schemas']['PainelSaida']>(`/equipe/filas/${encodeURIComponent(estado.fila)}/solicitacoes?${params}`, { signal })
  },
  enabled: Boolean(estado.fila),
  refetchOnWindowFocus: 'always',
})
