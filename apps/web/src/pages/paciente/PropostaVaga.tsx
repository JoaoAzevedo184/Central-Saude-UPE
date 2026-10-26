import { useId } from 'react'
import { Link } from 'react-router'
import { avisoPrazo, formatarDataHora, formatarDataCompleta, formatarDataPedido, formatarPrazo } from '../../shared/datas'
import { Botao } from '../../shared/ui/Botao'
import { Cartao } from '../../shared/ui/Cartao'
import { SeloStatus } from '../../shared/ui/SeloStatus'
import type { Pedido } from './api'

export type AcaoProposta = 'confirmar' | 'recusar'
export function PropostaVaga({ pedido, agora, enviando, aoResponder, aoAtualizar }: {
  pedido: Pedido; agora: number; enviando: boolean; aoResponder: (acao: AcaoProposta) => void; aoAtualizar: () => void
}) {
  const id = useId()
  const proposta = pedido.agendamento_ativo!
  const aviso = proposta.expira_em ? avisoPrazo(proposta.expira_em, agora) : undefined
  const vencida = proposta.expira_em !== null && new Date(proposta.expira_em).getTime() <= agora
  return <Cartao className="proposta-vaga" aria-labelledby={id}>
    <SeloStatus valor="EM_PROPOSTA" /><h2 id={id}>{pedido.fila.nome}</h2>
    <p className="proposta-data"><time dateTime={proposta.inicio}>{formatarDataHora(proposta.inicio)}</time><span className="sr-only">{formatarDataCompleta(proposta.inicio)}</span></p>
    <p>Local: {proposta.unidade.nome} ({proposta.unidade.sigla})</p><p>Profissional: {proposta.profissional}</p>
    <p className="pedido-data">Pedido em <time dateTime={pedido.data_pedido}>{formatarDataPedido(pedido.data_pedido)}</time></p>
    <div className="proposta-prazo">
      {proposta.expira_em ? <p><strong>Confirme até <time dateTime={proposta.expira_em}>{formatarPrazo(proposta.expira_em)}</time></strong></p> : <p>Confira o prazo em Ver detalhes.</p>}
      {aviso && <p className="prazo-urgente" role="status">{aviso}</p>}
    </div>
    {vencida ? <Botao variante="secundario" onClick={aoAtualizar}>Atualizar pedidos</Botao> : <div className="acoes-proposta">
      <Botao disabled={enviando} onClick={() => aoResponder('confirmar')}>Confirmar consulta</Botao>
      <Botao variante="secundario" disabled={enviando} onClick={() => aoResponder('recusar')}>Esta data não serve</Botao>
    </div>}
    <Link className="link-detalhes" to={`/paciente/solicitacoes/${pedido.id}`}>Ver detalhes<span className="sr-only">: {pedido.fila.nome}</span></Link>
  </Cartao>
}
