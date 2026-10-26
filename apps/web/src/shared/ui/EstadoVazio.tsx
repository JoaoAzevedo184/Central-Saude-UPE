import { Link } from 'react-router'

export function EstadoVazio() {
  return <div className="estado-vazio"><h2>Você ainda não tem pedidos</h2>
    <p>Faça um pedido para acompanhar seu atendimento por aqui.</p>
    <Link className="botao botao-principal" to="/paciente/novo">Fazer um pedido</Link>
  </div>
}
