export function LinhaDoTempo({ itens, rotulo = 'Andamento' }: {
  itens: { data: string; texto: string }[]; rotulo?: string
}) {
  return <ol className="linha-do-tempo" role="list" aria-label={rotulo}>
    {itens.map((item, indice) => <li key={`${item.data}-${indice}`}>
      <time dateTime={item.data}>{formatarDataPedido(item.data)}</time><p>{item.texto}</p>
    </li>)}
  </ol>
}
import { formatarDataPedido } from '../datas'

