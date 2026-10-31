import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { ApiError } from '../../shared/api/problem-details'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { CampoSelecao } from '../../shared/ui/CampoSelecao'
import { EstadoVazio } from '../../shared/ui/EstadoVazio'
import { Paginacao } from '../../shared/ui/Paginacao'
import { formatarHora } from '../../shared/datas'
import { filasEquipeOptions, limitePedidosEquipe, pedidosEquipeOptions, type FilaEquipe } from './api'
import { lerEstadoFila, paramsFila, textosStatusEquipe, type EstadoFila } from './estado-fila'
import { PedidosFila } from './PedidosFila'

function nomeFila(fila: FilaEquipe) { return `${fila.nome} · ${fila.unidade_sigla}${fila.ativa ? '' : ' (inativa)'}` }
function mensagemErro(erro: unknown) {
  if (erro instanceof ApiError && erro.problem.status === 403) return 'Não foi possível acessar esta fila. Confira seu acesso com o gestor da unidade.'
  if (erro instanceof ApiError && erro.problem.status === 404) return 'Esta fila não está disponível para consulta.'
  return 'Não foi possível carregar a fila.'
}
export function Fila() {
  const [params, setParams] = useSearchParams()
  const filas = useQuery(filasEquipeOptions)
  const estado = lerEstadoFila(params)
  const selecionada = filas.data?.find((fila) => fila.id === estado.fila) ?? filas.data?.[0]
  estado.fila = selecionada?.id ?? ''
  const pedidos = useQuery({ ...pedidosEquipeOptions(estado), enabled: Boolean(selecionada) && !filas.isError })
  const total = pedidos.data?.total ?? 0
  const ultimaPagina = Math.max(1, Math.ceil(total / limitePedidosEquipe))
  // Um total reduzido pode invalidar a página. Busca a válida antes de exibir o resultado.
  const corrigirPagina = pedidos.isSuccess && estado.pagina > ultimaPagina
  const canonico = paramsFila({ ...estado, pagina: corrigirPagina ? ultimaPagina : estado.pagina }).toString()
  useEffect(() => {
    if (filas.isSuccess && params.toString() !== canonico) setParams(canonico, { replace: true })
  }, [canonico, filas.isSuccess, params, setParams])
  function mudar(mudanca: Partial<EstadoFila>) { setParams(paramsFila({ ...estado, pagina: 1, ...mudanca })) }
  const buscando = filas.isFetching || pedidos.isFetching
  async function atualizar() { await Promise.all([filas.refetch(), selecionada && pedidos.refetch()]) }
  const erro = filas.isError ? filas.error : pedidos.isError ? pedidos.error : undefined
  return <section className="pagina-fila" aria-labelledby="titulo-fila">
    <div className="topo-fila"><div><p className="sobretitulo-equipe">Central de atendimento</p><h1 id="titulo-fila">Fila</h1></div>
      <div className="atualizacao-fila"><Botao variante="secundario" carregando={buscando} onClick={() => void atualizar()}>Atualizar</Botao>
        {pedidos.dataUpdatedAt > 0 && !pedidos.isError && <p>Atualizado às {formatarHora(pedidos.dataUpdatedAt)}</p>}
      </div>
    </div>
    {filas.isPending && <p role="status">Carregando filas…</p>}
    {erro && <Alerta><p>{mensagemErro(erro)}</p><Botao variante="secundario" carregando={buscando} onClick={() => void atualizar()}>Tentar de novo</Botao></Alerta>}
    {filas.isSuccess && filas.data.length === 0 && <EstadoVazio titulo="Nenhuma fila liberada" descricao="Você ainda não tem filas liberadas. Fale com o gestor da unidade." acao={null} />}
    {selecionada && <>
      <div className="controles-fila">
        {filas.data!.length === 1 ? <div className="fila-unica"><span>Fila</span><p>{nomeFila(selecionada)}</p></div> :
          <CampoSelecao rotulo="Fila" value={estado.fila} onChange={(event) => mudar({ fila: event.target.value })}>
            {filas.data!.map((fila) => <option key={fila.id} value={fila.id}>{nomeFila(fila)}</option>)}
          </CampoSelecao>}
        <CampoSelecao rotulo="Ordenação" value={estado.ordem} onChange={(event) => mudar({ ordem: event.target.value as EstadoFila['ordem'] })}>
          <option value="prioridade">Prioridade</option><option value="chegada">Ordem de chegada</option>
        </CampoSelecao>
        <CampoSelecao rotulo="Status" value={estado.status} onChange={(event) => mudar({ status: event.target.value as EstadoFila['status'] })}>
          <option value="todos">Todos ({Object.values(selecionada.contagem_por_status).reduce((soma, valor) => soma + valor, 0)})</option>
          {Object.entries(textosStatusEquipe).map(([status, texto]) => <option key={status} value={status}>{texto} ({selecionada.contagem_por_status[status as keyof typeof textosStatusEquipe] ?? 0})</option>)}
        </CampoSelecao>
      </div>
      {estado.ordem === 'chegada' && <p className="nota-ordenacao">A posição segue a prioridade da fila.</p>}
      {!erro && (pedidos.isPending || corrigirPagina) && <p role="status">Carregando pedidos…</p>}
      {!erro && pedidos.isSuccess && !corrigirPagina && <>
        <p role="status" aria-atomic="true">Mostrando {pedidos.data.itens.length} de {total} pedidos · Página {estado.pagina} de {ultimaPagina} · {estado.status === 'todos' ? 'Todos os status' : textosStatusEquipe[estado.status]}</p>
        {pedidos.data.itens.length ? <PedidosFila itens={pedidos.data.itens} query={paramsFila(estado).toString()} /> :
          <EstadoVazio titulo="Nenhum pedido" descricao="Nenhum pedido com este status nesta fila." acao={null} />}
        <Paginacao total={total} limite={limitePedidosEquipe} pagina={estado.pagina - 1} aoMudar={(pagina) => mudar({ pagina: pagina + 1 })} rotulo="Páginas da fila" />
      </>}
    </>}
  </section>
}
