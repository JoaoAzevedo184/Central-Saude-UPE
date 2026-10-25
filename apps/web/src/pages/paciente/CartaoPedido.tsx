import { useId } from 'react'
import { Link } from 'react-router'
import { formatarDataHora, formatarDataPedido, formatarDataCompleta } from '../../shared/datas'
import { Cartao } from '../../shared/ui/Cartao'
import { SeloStatus } from '../../shared/ui/SeloStatus'
import type { Pedido } from './api'

export function CartaoPedido({ pedido }: { pedido: Pedido }) {
  const id = useId()
  const consulta = pedido.status === 'AGENDADA' && pedido.agendamento_ativo?.status === 'CONFIRMADO' ? pedido.agendamento_ativo : null
  return <Cartao aria-labelledby={id}>
    <SeloStatus valor={pedido.status} />
    <h2 id={id}>{pedido.fila.nome}</h2>
    <p className="pedido-unidade">{pedido.fila.unidade.nome} ({pedido.fila.unidade.sigla})</p>
    <p className="pedido-data">Pedido em <time dateTime={pedido.data_pedido}>{formatarDataPedido(pedido.data_pedido)}</time></p>
    {consulta && <div className="consulta-marcada">
      <p><strong><time dateTime={consulta.inicio}>{formatarDataHora(consulta.inicio)}</time></strong> <span className="sr-only">{formatarDataCompleta(consulta.inicio)}</span></p>
      <p>Local: {consulta.unidade.nome} ({consulta.unidade.sigla})</p><p>Profissional: {consulta.profissional}</p>
      <p className="lembrete">Chegue com antecedência. Tolerância de atraso: 1 hora.</p>
    </div>}
    <Link className="link-detalhes" to={`/paciente/solicitacoes/${pedido.id}`} aria-label={`Ver detalhes: ${pedido.fila.nome}`}>Ver detalhes</Link>
  </Cartao>
}
