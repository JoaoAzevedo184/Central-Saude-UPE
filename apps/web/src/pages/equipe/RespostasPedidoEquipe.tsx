import type { DetalheEquipe } from './api'

function textoResposta(valor: unknown): string {
  if (valor === null || valor === undefined || (typeof valor === 'string' && !valor.trim())) return 'Não respondida'
  if (typeof valor === 'boolean') return valor ? 'Sim' : 'Não'
  return typeof valor === 'number' || typeof valor === 'string' ? String(valor) : 'Não respondida'
}
const turnos = { MANHA: 'Manhã', TARDE: 'Tarde', QUALQUER: 'Qualquer turno' }

export function RespostasPedidoEquipe({ pedido }: { pedido: DetalheEquipe }) {
  const paciente = pedido.respostas.filter((resposta) => resposta.origem === 'PACIENTE')
  const equipe = pedido.respostas.filter((resposta) => ['REGULACAO', 'EQUIPE'].includes(resposta.origem))
  function lista(respostas: DetalheEquipe['respostas']) {
    return <dl className="respostas-equipe">{respostas.map((resposta) => <div key={resposta.criterio_id}>
      <dt>{resposta.descricao}</dt><dd>{textoResposta(resposta.valor)}</dd>
    </div>)}</dl>
  }
  return <div className="blocos-respostas-equipe">
    <section className="bloco-detalhe-equipe" aria-labelledby="respostas-paciente">
      <h2 id="respostas-paciente">Respostas do paciente</h2>
      {paciente.length ? lista(paciente) : <p>Nenhuma resposta do paciente registrada.</p>}
      <dl className="respostas-equipe preferencias-equipe">
        <div><dt>Encaminhamento</dt><dd>{textoResposta(pedido.origem_encaminhamento)}</dd></div>
        <div><dt>Turno preferido</dt><dd>{turnos[pedido.turno_preferido]}</dd></div>
      </dl>
    </section>
    {equipe.length > 0 && <section className="bloco-detalhe-equipe" aria-labelledby="respostas-equipe">
      <h2 id="respostas-equipe">Critérios respondidos pela equipe</h2>{lista(equipe)}
    </section>}
  </div>
}
