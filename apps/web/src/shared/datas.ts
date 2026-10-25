const fuso = 'America/Recife'
const data = new Intl.DateTimeFormat('pt-BR', { timeZone: fuso, day: '2-digit', month: '2-digit', year: 'numeric' })
const diaMes = new Intl.DateTimeFormat('pt-BR', { timeZone: fuso, day: '2-digit', month: '2-digit' })
const hora = new Intl.DateTimeFormat('pt-BR', { timeZone: fuso, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const semana = new Intl.DateTimeFormat('pt-BR', { timeZone: fuso, weekday: 'long' })

// data_pedido é uma data civil, sem horário: não interpretar como meia-noite UTC.
export function formatarDataPedido(valor: string) {
  const [ano, mes, dia] = valor.split('-')
  return `${dia}/${mes}/${ano}`
}
export function formatarDataHora(valor: string) {
  const instante = new Date(valor)
  return `${semana.format(instante)}, ${diaMes.format(instante)}, às ${hora.format(instante)}`
}
export function formatarPrazo(valor: string) {
  const instante = new Date(valor)
  return `${diaMes.format(instante)} às ${hora.format(instante)}`
}
export function formatarDataCompleta(valor: string) { return data.format(new Date(valor)) }
export function avisoPrazo(expiraEm: string, agora: number): string | undefined {
  const restante = new Date(expiraEm).getTime() - agora
  if (restante <= 0) return 'O prazo para responder terminou.'
  if (restante >= 24 * 60 * 60 * 1000) return undefined
  const horas = Math.floor(restante / (60 * 60 * 1000))
  if (horas === 0) return 'Falta menos de 1 hora'
  return horas === 1 ? 'Falta 1 hora' : `Faltam ${horas} horas`
}
