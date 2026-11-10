import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { SeloRisco } from './PedidosFila'
import { filasEquipeOptions } from './api'
import { indicadoresOptions, mensagemErroIndicadores, prazoNovaTentativa, type DadosIndicadores } from './api-indicadores'
import { diaMesCivil, hojeRecife, inteiro, lerIndicadores, paramsIndicadores, validarFila, validarPeriodo, type EstadoIndicadores } from './estado-indicadores'
import { FiltrosIndicadores } from './FiltrosIndicadores'
import { ResumoIndicadores } from './ResumoIndicadores'
import { SemanaASemana } from './SemanaASemana'
import '../../styles/indicadores.css'

function temMovimento(dados: DadosIndicadores) {
  return dados.tempo_de_espera.confirmacoes > 0 || Object.entries(dados.totais).some(([campo, valor]) => !campo.startsWith('taxa_') && typeof valor === 'number' && valor > 0)
}
export default function Indicadores() {
  const [params, setParams] = useSearchParams()
  const hoje = hojeRecife()
  const estado = lerIndicadores(params, hoje)
  const [epoca] = useState(() => http.geracaoSessao())
  const sessaoAtual = epoca === http.geracaoSessao()
  const erroPeriodoLocal = validarPeriodo(estado.de, estado.ate, hoje)
  const erroFila = validarFila(estado.fila) ? undefined : 'Selecione uma fila válida.'
  const filas = useQuery({ ...filasEquipeOptions, enabled: sessaoAtual, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const consulta = useQuery({
    ...indicadoresOptions(estado, epoca), enabled: sessaoAtual && !erroPeriodoLocal && !erroFila,
    placeholderData: (anterior, queryAnterior) => queryAnterior?.queryKey[1] === epoca ? anterior : undefined,
  })
  const canonico = paramsIndicadores(estado).toString()
  useEffect(() => {
    if (!erroPeriodoLocal && !erroFila && params.toString() !== canonico) setParams(canonico, { replace: true })
  }, [canonico, erroFila, erroPeriodoLocal, params, setParams])
  function mudar(novo: EstadoIndicadores) {
    if (paramsIndicadores(novo).toString() !== canonico) setParams(paramsIndicadores(novo))
  }
  const erroServidorPeriodo = consulta.error instanceof ApiError && consulta.error.problem.status === 422
  const erroPeriodo = erroPeriodoLocal ?? (erroServidorPeriodo ? 'Confira as datas: período de até 366 dias, com término até hoje em Recife.' : undefined)
  const prazo = prazoNovaTentativa(consulta.error, consulta.errorUpdatedAt)
  const [prazoLiberado, setPrazoLiberado] = useState(0)
  useEffect(() => {
    if (!prazo) return
    let timer: ReturnType<typeof setTimeout>
    function aguardar(restante: number) {
      const intervalo = Math.min(restante, 2_147_483_647)
      timer = setTimeout(() => restante > intervalo ? aguardar(restante - intervalo) : setPrazoLiberado(prazo), intervalo)
    }
    aguardar(Math.max(0, prazo - Date.now()))
    return () => clearTimeout(timer)
  }, [prazo])
  const bloqueado = prazo > 0 && prazoLiberado !== prazo
  const dados = consulta.data
  const mostrar = sessaoAtual && dados && !erroPeriodo && !erroFila && !consulta.isError
  const filtroResposta = dados?.fila_id ? filas.data?.find((fila) => fila.id === dados.fila_id)?.nome ?? 'fila selecionada' : 'todas as filas'
  return <section className="pagina-indicadores" aria-labelledby="titulo-indicadores">
    <header className="topo-indicadores"><h1 id="titulo-indicadores">Indicadores</h1><p>Movimento das filas do seu escopo.</p></header>
    <FiltrosIndicadores key={`${estado.de}:${estado.ate}`} estado={estado} hoje={hoje} filas={filas.data ?? []} filasCarregadas={filas.isSuccess}
      erroPeriodo={erroPeriodo} erroFila={erroFila ?? (filas.isError ? 'Não foi possível carregar as opções de fila.' : undefined)}
      aoTentarFilas={filas.isError ? () => { void filas.refetch() } : undefined} aoMudar={mudar} />
    {consulta.isError && !erroServidorPeriodo && <Alerta><p>{mensagemErroIndicadores(consulta.error)}</p>
      <Botao variante="secundario" disabled={bloqueado || consulta.isFetching} onClick={() => void consulta.refetch()}>Tentar de novo</Botao>
      {bloqueado && <p>Aguarde o prazo indicado pelo serviço para tentar novamente.</p>}
    </Alerta>}
    {!dados && consulta.isFetching && <p aria-live="polite">Carregando indicadores…</p>}
    <p role="status" aria-atomic="true">{mostrar && !consulta.isFetching && `Indicadores de ${diaMesCivil(dados.de)} a ${diaMesCivil(dados.ate)}, ${filtroResposta}`}</p>
    {mostrar && <div className={`resultado-indicadores${consulta.isFetching ? ' atualizando' : ''}`} aria-busy={consulta.isFetching}>
      {consulta.isFetching && <p>Atualizando indicadores… Os números abaixo são do período anterior.</p>}
      {!temMovimento(dados) && <p className="vazio-indicadores">Nenhum movimento neste período.</p>}
      <ResumoIndicadores dados={dados} />
      <section className="bloco-indicadores fila-agora" aria-labelledby="titulo-fila-agora"><div><h2 id="titulo-fila-agora">Fila agora</h2><p>Pedidos aguardando vaga. Não depende do período escolhido.</p></div>
        <dl>{(['VERMELHO', 'AMARELO', 'VERDE'] as const).map((risco) => <div key={risco}><dt><SeloRisco valor={risco} /></dt><dd>{inteiro(dados.fila_atual[risco] ?? 0)}</dd></div>)}</dl>
      </section>
      <SemanaASemana semanas={dados.semanas} de={dados.de} ate={dados.ate} />
    </div>}
  </section>
}
