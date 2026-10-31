import type { components } from '../../shared/api/generated/schema'

export const textosStatusEquipe: Record<components['schemas']['StatusSolicitacao'], string> = {
  EM_ANALISE: 'Em análise', NA_FILA: 'Aguardando vaga', EM_PROPOSTA: 'Aguardando confirmação',
  AGENDADA: 'Agendado', ATENDIDA: 'Atendimento realizado', CANCELADA: 'Cancelado',
}
export type EstadoFila = {
  fila: string
  ordem: 'prioridade' | 'chegada'
  status: keyof typeof textosStatusEquipe | 'todos'
  pagina: number
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function lerEstadoFila(params: URLSearchParams): EstadoFila {
  const status = params.get('status') ?? 'todos'
  const pagina = Number(params.get('pagina') ?? 1)
  const fila = params.get('fila') ?? ''
  return {
    fila: uuid.test(fila) ? fila : '',
    ordem: params.get('ordem') === 'chegada' ? 'chegada' : 'prioridade',
    status: Object.hasOwn(textosStatusEquipe, status) ? status as EstadoFila['status'] : 'todos',
    pagina: Number.isSafeInteger(pagina) && pagina > 0 && pagina <= Math.floor(Number.MAX_SAFE_INTEGER / 20) ? pagina : 1,
  }
}
// Só filtros conhecidos: nenhum dado de pessoa é copiado para links ou histórico.
export function paramsFila(estado: EstadoFila) {
  const params = new URLSearchParams()
  if (estado.fila) params.set('fila', estado.fila)
  params.set('ordem', estado.ordem)
  if (estado.status !== 'todos') params.set('status', estado.status)
  params.set('pagina', String(estado.pagina))
  return params
}
