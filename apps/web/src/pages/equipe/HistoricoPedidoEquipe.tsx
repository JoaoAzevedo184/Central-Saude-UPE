import { formatarDataHoraCompleta } from '../../shared/datas'
import type { components } from '../../shared/api/generated/schema'
import type { DetalheEquipe } from './api'

const textos: Record<components['schemas']['TipoEventoLinhaDoTempo'], string> = {
  CRIADA: 'Pedido criado', CLASSIFICADA: 'Risco classificado', ENTROU_NA_FILA: 'Pedido entrou na fila',
  PROPOSTA_ENVIADA: 'Proposta de vaga enviada', CONFIRMADA: 'Consulta confirmada', RECUSADA: 'Paciente informou que esta data não serve',
  PROPOSTA_EXPIRADA: 'Prazo para confirmar encerrado', FALTOU: 'Falta registrada', ATENDIDA: 'Atendimento realizado',
  CANCELADA: 'Pedido cancelado', REENTROU_NA_FILA: 'Pedido voltou à fila', RECLASSIFICADA: 'Prioridade atualizada',
}
export function HistoricoPedidoEquipe({ eventos }: { eventos: DetalheEquipe['historico'] }) {
  // A API ordena por instante e sequência crescentes; o índice desempata na ordem inversa.
  const ordenados = eventos.map((evento, indice) => ({ evento, indice })).sort((a, b) =>
    Date.parse(b.evento.ocorrido_em) - Date.parse(a.evento.ocorrido_em) || b.indice - a.indice)
  return <section className="bloco-detalhe-equipe historico-equipe" aria-labelledby="titulo-historico-equipe">
    <h2 id="titulo-historico-equipe">Histórico</h2>
    {ordenados.length ? <ol className="eventos-equipe" aria-label="Histórico do pedido">{ordenados.map(({ evento, indice }) => <li key={indice}>
      <p className="evento-titulo">{Object.hasOwn(textos, evento.tipo) ? textos[evento.tipo] : 'Atualização do pedido'}</p>
      <time dateTime={evento.ocorrido_em}>{formatarDataHoraCompleta(evento.ocorrido_em)}</time>
      {evento.motivo?.trim() && <p className="evento-motivo">{evento.motivo}</p>}
    </li>)}</ol> : <p>Nenhum evento registrado.</p>}
  </section>
}
