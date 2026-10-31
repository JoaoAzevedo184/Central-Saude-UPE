import { Link } from 'react-router'
import { Cartao } from '../../shared/ui/Cartao'
import { formatarDataCompleta } from '../../shared/datas'
import type { PedidoEquipe } from './api'
import { textosStatusEquipe } from './estado-fila'

const riscos = {
  VERMELHO: { texto: 'Alto', classe: 'alto' }, AMARELO: { texto: 'Médio', classe: 'medio' }, VERDE: { texto: 'Baixo', classe: 'baixo' },
}
export function SeloRisco({ valor }: { valor: PedidoEquipe['classificacao_risco'] }) {
  const risco = valor && riscos[valor]
  return <span className={`risco-equipe risco-${risco ? risco.classe : 'neutro'}`}>{risco ? risco.texto : 'Sem classificação'}</span>
}
function Posicao({ pedido }: { pedido: PedidoEquipe }) {
  return pedido.status === 'NA_FILA' && pedido.posicao !== null ? pedido.posicao : <><span aria-hidden="true">—</span><span className="sr-only">sem posição</span></>
}
function Entrada({ valor }: { valor: PedidoEquipe['data_entrada_fila'] }) {
  return valor ? <time dateTime={valor}>{formatarDataCompleta(valor)}</time> : 'Ainda não entrou na fila'
}
const mudancas: Record<string, string> = { ENTROU_NA_FILA: 'Entrou na fila', REENTROU_NA_FILA: 'Voltou à fila', RECLASSIFICADA: 'Reclassificado' }
function UltimaMudanca({ valor }: { valor: PedidoEquipe['ultima_mudanca'] }) {
  const texto = valor && Object.hasOwn(mudancas, valor.tipo) ? mudancas[valor.tipo] : undefined
  return valor && texto ? <>{texto} · <time dateTime={valor.ocorrido_em}>{formatarDataCompleta(valor.ocorrido_em).slice(0, 5)}</time></> : '—'
}
export function PedidosFila({ itens, query }: { itens: PedidoEquipe[]; query: string }) {
  const destino = (pedido: PedidoEquipe) => `/equipe/solicitacoes/${encodeURIComponent(pedido.id)}?${query}`
  return <>
    <table className="tabela-fila">
      <caption>Pedidos da fila na ordenação selecionada</caption>
      <thead><tr>{['Posição', 'Risco', 'Nome', 'CPF', 'Entrada na fila', 'Status', 'Última mudança'].map((titulo) => <th key={titulo} scope="col">{titulo}</th>)}</tr></thead>
      <tbody>{itens.map((pedido) => <tr key={pedido.id}>
        <td><Posicao pedido={pedido} /></td><td><SeloRisco valor={pedido.classificacao_risco} /></td>
        <td><Link to={destino(pedido)}>{pedido.paciente_nome}</Link></td><td className="cpf-equipe">{pedido.paciente_cpf}</td>
        <td><Entrada valor={pedido.data_entrada_fila} /></td><td>{textosStatusEquipe[pedido.status]}</td><td><UltimaMudanca valor={pedido.ultima_mudanca} /></td>
      </tr>)}</tbody>
    </table>
    <ul className="cartoes-fila" aria-label="Pedidos da fila">{itens.map((pedido) => <li key={pedido.id}><Cartao>
      <h2><Link to={destino(pedido)}>{pedido.paciente_nome}</Link></h2>
      <dl>
        <div><dt>Posição</dt><dd><Posicao pedido={pedido} /></dd></div>
        <div><dt>Risco</dt><dd><SeloRisco valor={pedido.classificacao_risco} /></dd></div>
        <div><dt>CPF</dt><dd>{pedido.paciente_cpf}</dd></div>
        <div><dt>Entrada na fila</dt><dd><Entrada valor={pedido.data_entrada_fila} /></dd></div>
        <div><dt>Status</dt><dd>{textosStatusEquipe[pedido.status]}</dd></div>
        <div><dt>Última mudança</dt><dd><UltimaMudanca valor={pedido.ultima_mudanca} /></dd></div>
      </dl>
    </Cartao></li>)}</ul>
  </>
}
