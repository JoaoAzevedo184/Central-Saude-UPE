import { hojeRecife } from '../../shared/datas'

export interface EstadoAgenda { fila: string; data: string }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function validarDataAgenda(valor: string): string | undefined {
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor) && valor >= '2000-01-01' && valor <= '2100-12-31') {
    const instante = new Date(`${valor}T12:00:00Z`)
    if (Number.isFinite(instante.getTime()) && instante.toISOString().slice(0, 10) === valor) return
  }
  return 'Informe uma data válida entre 01/01/2000 e 31/12/2100.'
}
export function lerEstadoAgenda(params: URLSearchParams, hoje = hojeRecife()): EstadoAgenda {
  const fila = params.get('fila') ?? ''
  return { fila: uuid.test(fila) ? fila : '', data: params.get('data') ?? hoje }
}
export function paramsAgenda(estado: EstadoAgenda) {
  const params = new URLSearchParams()
  if (estado.fila) params.set('fila', estado.fila)
  params.set('data', estado.data)
  return params
}
export function mudarDiaAgenda(data: string, diferenca: number) {
  if (validarDataAgenda(data)) return data
  const instante = new Date(`${data}T12:00:00Z`)
  instante.setUTCDate(instante.getUTCDate() + diferenca)
  const destino = instante.toISOString().slice(0, 10)
  return validarDataAgenda(destino) ? data : destino
}
