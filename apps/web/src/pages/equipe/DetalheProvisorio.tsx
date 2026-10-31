import { Link, useSearchParams } from 'react-router'
import { lerEstadoFila, paramsFila } from './estado-fila'

export function DetalheProvisorio() {
  const [params] = useSearchParams()
  return <><Link className="voltar-fila" to={`/equipe/fila?${paramsFila(lerEstadoFila(params))}`}>‹ Voltar para a fila</Link><h1>Detalhe do pedido</h1></>
}
