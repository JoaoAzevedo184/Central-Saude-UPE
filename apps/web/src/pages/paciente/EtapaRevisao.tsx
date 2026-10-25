import type { DetalheFila } from './api'
import { turnos, type FormularioSolicitacao } from './formulario-solicitacao'

export function EtapaRevisao({ fila, dados }: { fila: DetalheFila; dados: FormularioSolicitacao }) {
  return <>
    <p>Confira as informações antes de enviar seu pedido.</p>
    <dl className="resumo-pedido">
      <div><dt>Atendimento</dt><dd>{fila.nome}</dd></div>
      <div><dt>Especialidade</dt><dd>{fila.especialidade.nome}</dd></div>
      <div><dt>Unidade</dt><dd>{fila.unidade.nome} ({fila.unidade.sigla})</dd></div>
      <div><dt>Origem do encaminhamento</dt><dd>{dados.origem_encaminhamento.trim()}</dd></div>
      <div><dt>Turno preferido</dt><dd>{turnos[dados.turno_preferido]}</dd></div>
      {fila.criterios.map((criterio, indice) => {
        const valor = dados.respostas[indice]?.valor ?? ''
        return <div key={criterio.id}><dt>{criterio.descricao}</dt><dd>{valor === '' ? 'Sem resposta' : criterio.tipo === 'SIM_NAO' ? valor === 'sim' ? 'Sim' : 'Não' : valor}</dd></div>
      })}
    </dl>
    <p>Após o envio, acompanhe seu pedido em Meus atendimentos.</p>
  </>
}
