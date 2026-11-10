import { formatarDataPedido } from '../../shared/datas'

export interface EstadoIndicadores { de: string; ate: string; fila: string }
export type PeriodoIndicadores = '4' | '8' | 'mes' | 'personalizado'
const diaMs = 86_400_000
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function hojeRecife(agora = new Date()) {
  const partes = new Intl.DateTimeFormat('en', { timeZone: 'America/Recife', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(agora)
  const parte = (tipo: Intl.DateTimeFormatPartTypes) => partes.find((p) => p.type === tipo)!.value
  return `${parte('year')}-${parte('month')}-${parte('day')}`
}
function instanteCivil(valor: string) { return new Date(`${valor}T12:00:00Z`) }
function dataValida(valor: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valor)) return false
  const data = instanteCivil(valor)
  return Number.isFinite(data.getTime()) && data.toISOString().slice(0, 10) === valor
}
export function periodoPronto(periodo: Exclude<PeriodoIndicadores, 'personalizado'>, hoje: string) {
  const inicio = instanteCivil(hoje)
  if (periodo === 'mes') inicio.setUTCDate(1)
  else inicio.setUTCDate(inicio.getUTCDate() - (periodo === '4' ? 27 : 55))
  return { de: inicio.toISOString().slice(0, 10), ate: hoje }
}
export function validarPeriodo(de: string, ate: string, hoje: string): string | undefined {
  if (!dataValida(de) || !dataValida(ate)) return 'Informe as duas datas válidas do período.'
  if (de > ate) return 'A data inicial deve ser anterior ou igual à data final.'
  if (ate > hoje) return 'A data final deve ser até hoje em Recife.'
  if ((instanteCivil(ate).getTime() - instanteCivil(de).getTime()) / diaMs + 1 > 366) return 'Escolha um período de até 366 dias, contando o primeiro e o último dia.'
}
export function lerIndicadores(params: URLSearchParams, hoje: string): EstadoIndicadores {
  const periodo = !params.has('de') && !params.has('ate') ? periodoPronto('4', hoje) : { de: params.get('de') ?? '', ate: params.get('ate') ?? '' }
  return { ...periodo, fila: params.get('fila') ?? '' }
}
export function validarFila(fila: string) { return !fila || uuid.test(fila) }
export function paramsIndicadores(estado: EstadoIndicadores) {
  const params = new URLSearchParams({ de: estado.de, ate: estado.ate })
  if (estado.fila) params.set('fila', estado.fila)
  return params
}
export function identificarPeriodo(estado: EstadoIndicadores, hoje: string): PeriodoIndicadores {
  return (['4', '8', 'mes'] as const).find((periodo) => {
    const datas = periodoPronto(periodo, hoje)
    return datas.de === estado.de && datas.ate === estado.ate
  }) ?? 'personalizado'
}
// A API fornece datas civis: não passá-las a formatarDiaMes como instantes UTC.
export function diaMesCivil(valor: string) { return formatarDataPedido(valor).slice(0, 5) }
export const inteiro = (valor: number) => new Intl.NumberFormat('pt-BR').format(valor)
export const dias = (valor: number | null) => valor === null ? '—' : `${valor.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} dias`
export const porcentagem = (valor: number | null) => valor === null ? '—' : valor.toLocaleString('pt-BR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 })
