import type { components } from '../api/generated/schema'

type Status = components['schemas']['StatusSolicitacao']
const status: Record<Status, { texto: string; icone: string }> = {
  EM_ANALISE: { texto: 'Pedido em análise', icone: '◷' },
  NA_FILA: { texto: 'Aguardando vaga', icone: '◷' },
  EM_PROPOSTA: { texto: 'Você tem uma vaga para confirmar', icone: '!' },
  AGENDADA: { texto: 'Consulta marcada', icone: '✓' },
  ATENDIDA: { texto: 'Atendimento realizado', icone: '✓' },
  CANCELADA: { texto: 'Pedido cancelado', icone: '×' },
}
export function SeloStatus({ valor }: { valor: Status }) {
  const selo = status[valor]
  return <span className={`selo-status selo-${valor.toLowerCase()}`}><span aria-hidden="true">{selo.icone}</span>{selo.texto}</span>
}
