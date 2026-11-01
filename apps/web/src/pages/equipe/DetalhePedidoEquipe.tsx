import { useQuery } from '@tanstack/react-query'
import { Link, useOutletContext, useParams, useSearchParams } from 'react-router'
import { ApiError } from '../../shared/api/problem-details'
import type { Sessao } from '../../shared/auth/session'
import { formatarDataPedido } from '../../shared/datas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { detalheEquipeOptions, filasEquipeOptions } from './api'
import { ClassificarRisco } from './ClassificarRisco'
import { lerEstadoFila, paramsFila, textosStatusEquipe } from './estado-fila'
import { HistoricoPedidoEquipe } from './HistoricoPedidoEquipe'
import { SeloRisco } from './PedidosFila'
import { RespostasPedidoEquipe } from './RespostasPedidoEquipe'

// Contrato pós-MVP: faltam posição, agendamento ativo, perguntas não respondidas,
// critérios por nível de risco e controle de versão para concorrência.
export function DetalhePedidoEquipe() {
  const { id = '' } = useParams()
  return <ConteudoDetalhe key={id} id={id} />
}
function ConteudoDetalhe({ id }: { id: string }) {
  const [params] = useSearchParams()
  const sessao = useOutletContext<Sessao>()
  const consulta = useQuery(detalheEquipeOptions(id))
  const filas = useQuery(filasEquipeOptions)
  const pedido = consulta.data
  const codigo = consulta.error instanceof ApiError ? consulta.error.problem.status : undefined
  const acessoNegado = codigo === 403 || codigo === 404
  const fila = filas.isError ? undefined : filas.data?.find((item) => item.id === pedido?.fila_id)
  const nomeFila = fila ? `${fila.nome} · ${fila.unidade_sigla}` : 'Fila'
  return <div className="detalhe-equipe">
    <Link className="voltar-fila" to={`/equipe/fila?${paramsFila(lerEstadoFila(params))}`}>‹ Voltar para a fila</Link>
    <h1>Detalhe do pedido</h1>
    {consulta.isPending && <p role="status">Carregando pedido…</p>}
    {consulta.isError && <Alerta>
      <p>{codigo === 404 ? 'Pedido não encontrado ou fora das suas filas.' : codigo === 403
        ? 'Não foi possível acessar este pedido. Confira seu acesso com o gestor da unidade.'
        : 'Não foi possível carregar o pedido.'}</p>
      {!acessoNegado && <Botao variante="secundario" carregando={consulta.isFetching} onClick={() => void consulta.refetch()}>Tentar de novo</Botao>}
    </Alerta>}
    {pedido && !acessoNegado && <>
      <header className="topo-detalhe-equipe">
        <div><h2>{pedido.paciente_nome}</h2><p className="cpf-equipe">CPF: {pedido.paciente_cpf}</p><p>{nomeFila}</p>
          <p className="data-detalhe-equipe">Pedido em <time dateTime={pedido.data_pedido}>{formatarDataPedido(pedido.data_pedido)}</time></p></div>
        <div className="situacao-detalhe-equipe"><span className="status-detalhe-equipe">{textosStatusEquipe[pedido.status]}</span><SeloRisco valor={pedido.classificacao_risco} /></div>
      </header>
      <div className="conteudo-detalhe-equipe">
        <RespostasPedidoEquipe pedido={pedido} />
        {sessao.papel === 'ATENDENTE' && <ClassificarRisco pedido={pedido} nomeFila={nomeFila} leituraFalhou={consulta.isError} />}
      </div>
      <HistoricoPedidoEquipe eventos={pedido.historico} />
    </>}
  </div>
}
