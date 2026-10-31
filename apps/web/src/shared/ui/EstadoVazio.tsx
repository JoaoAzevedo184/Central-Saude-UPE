import { Link } from 'react-router'
import type { ReactNode } from 'react'

export function EstadoVazio({ titulo = 'Você ainda não tem pedidos', descricao = 'Faça um pedido para acompanhar seu atendimento por aqui.',
  acao = <Link className="botao botao-principal" to="/paciente/novo">Fazer um pedido</Link> }: { titulo?: string; descricao?: string; acao?: ReactNode }) {
  return <div className="estado-vazio"><h2>{titulo}</h2>
    <p>{descricao}</p>
    {acao}
  </div>
}
