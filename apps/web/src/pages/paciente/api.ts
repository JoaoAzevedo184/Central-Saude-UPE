import { infiniteQueryOptions, queryOptions, type QueryClient } from '@tanstack/react-query'
import type { components, operations } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'

export type Pedido = components['schemas']['SolicitacaoItem']
export type DetalhePedido = components['schemas']['SolicitacaoDetalhe']
export type Situacao = NonNullable<operations['listar_api_v1_solicitacoes_get']['parameters']['query']>['situacao'] & string
export const limitePedidos = 5
const base = ['pedidos-paciente'] as const
export const pedidosKey = base
export const detalhePedidoOptions = (id: string) => queryOptions({
  queryKey: ['pedido-paciente', id],
  queryFn: ({ signal }) => http.request<DetalhePedido>(`/solicitacoes/${encodeURIComponent(id)}`, { signal }),
})

// Leituras anteriores não podem sobrescrever a transição nem preencher uma sessão nova.
export async function incorporarPedido(client: QueryClient, atualizado: DetalhePedido, signal: AbortSignal, epoca: number) {
  const detalhe = detalhePedidoOptions(atualizado.id)
  await Promise.all([client.cancelQueries({ queryKey: pedidosKey }), client.cancelQueries({ queryKey: detalhe.queryKey })])
  if (signal.aborted || epoca !== http.geracaoSessao()) return
  client.setQueryData(detalhe.queryKey, atualizado)
  client.setQueryData<Pedido[]>(propostasOptions.queryKey, (antigos) => antigos?.filter((item) => item.id !== atualizado.id))
  client.setQueriesData<{ total: number; itens: Pedido[] }>({ queryKey: pedidosKey,
    predicate: (query) => query.queryKey[1] !== 'propostas' }, (antiga) => antiga ? {
      ...antiga, itens: antiga.itens.map((item) => item.id === atualizado.id ? atualizado : item),
    } : antiga)
  void client.invalidateQueries({ queryKey: pedidosKey })
  void client.invalidateQueries({ queryKey: detalhe.queryKey })
  void client.invalidateQueries({ queryKey: ['avisos', 'contagem'] })
}
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

export type Fila = components['schemas']['FilaSaida']
export type DetalheFila = components['schemas']['FilaDetalheSaida']
export type CriterioPaciente = components['schemas']['CriterioPacienteSaida']
export type NovoPedido = components['schemas']['SolicitacaoEntrada']
export const filasKey = ['filas-paciente'] as const
export const limiteFilas = 10
export const filasOptions = infiniteQueryOptions({
  queryKey: filasKey,
  initialPageParam: 0,
  queryFn: ({ pageParam, signal }) => http.request<components['schemas']['PaginaFilas']>(`/filas?limit=${limiteFilas}&offset=${pageParam}`, { signal }),
  getNextPageParam: (ultima, _paginas, offset) => ultima.itens.length && offset + ultima.itens.length < ultima.total ? offset + ultima.itens.length : undefined,
})
export const filaOptions = (id: string) => queryOptions({
  queryKey: ['fila-paciente', id],
  queryFn: ({ signal }) => http.request<DetalheFila>(`/filas/${id}`, { signal }),
  enabled: Boolean(id),
})
export function criarPedido(dados: NovoPedido, signal: AbortSignal) {
  return http.request<DetalhePedido>('/solicitacoes', { method: 'POST', body: dados, signal })
}
