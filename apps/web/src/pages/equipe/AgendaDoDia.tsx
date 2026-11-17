import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useOutletContext, useSearchParams } from 'react-router'
import { ApiError } from '../../shared/api/problem-details'
import type { Sessao } from '../../shared/auth/session'
import { formatarHora, hojeRecife } from '../../shared/datas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { Campo } from '../../shared/ui/Campo'
import { CampoSelecao } from '../../shared/ui/CampoSelecao'
import { EstadoVazio } from '../../shared/ui/EstadoVazio'
import { agendaEquipeOptions, filasEquipeOptions } from './api'
import { lerEstadoAgenda, mudarDiaAgenda, paramsAgenda, validarDataAgenda, type EstadoAgenda } from './estado-agenda'
import { AgendamentosDoDia } from './AgendamentosDoDia'

function mensagemErro(erro: unknown) {
  if (erro instanceof ApiError && erro.problem.status === 404) return 'Esta fila não está disponível para consulta.'
  if (erro instanceof ApiError && erro.problem.status === 403) return 'Não foi possível acessar a agenda. Confira seu acesso com o gestor da unidade.'
  return 'Não foi possível carregar a agenda.'
}
export function AgendaDoDia() {
  const sessao = useOutletContext<Sessao>()
  const [params, setParams] = useSearchParams()
  const [agora, setAgora] = useState(() => Date.now())
  const [mensagem, setMensagem] = useState('')
  useEffect(() => {
    const timer = setInterval(() => setAgora(Date.now()), 30_000)
    return () => clearInterval(timer)
  }, [])
  const filas = useQuery(filasEquipeOptions)
  const estadoUrl = lerEstadoAgenda(params)
  const selecionada = filas.data?.find((fila) => fila.id === estadoUrl.fila) ?? filas.data?.find((fila) => fila.ativa) ?? filas.data?.[0]
  const estado: EstadoAgenda = { ...estadoUrl, fila: selecionada?.id ?? '' }
  const erroData = validarDataAgenda(estado.data)
  const consulta = useQuery({ ...agendaEquipeOptions(estado), enabled: Boolean(selecionada) && !filas.isError && !erroData })
  const canonico = paramsAgenda(estado).toString()
  useEffect(() => {
    if (filas.isSuccess && !erroData && params.toString() !== canonico) setParams(canonico, { replace: true })
  }, [canonico, erroData, filas.isSuccess, params, setParams])
  function mudar(mudanca: Partial<EstadoAgenda>) { setMensagem(''); setParams(paramsAgenda({ ...estado, ...mudanca }), { replace: false }) }
  const buscando = filas.isFetching || consulta.isFetching
  const erro = filas.isError ? filas.error : consulta.isError ? consulta.error : undefined
  async function atualizar() { await Promise.all([filas.refetch(), selecionada && !erroData && consulta.refetch()]) }
  const itens = consulta.data ?? []
  const mostrar = consulta.isSuccess && !erro && !erroData
  return <section className="pagina-fila pagina-agenda" aria-labelledby="titulo-agenda">
    <div className="topo-fila"><div><p className="sobretitulo-equipe">Central de atendimento</p><h1 id="titulo-agenda">Agenda do dia</h1></div>
      <div className="atualizacao-fila"><Botao variante="secundario" carregando={buscando} onClick={() => void atualizar()}>Atualizar</Botao>
        {consulta.dataUpdatedAt > 0 && !erro && <p>Atualizado às {formatarHora(consulta.dataUpdatedAt)}</p>}
      </div>
    </div>
    {filas.isPending && <p role="status">Carregando filas…</p>}
    {erro && <Alerta><p>{mensagemErro(erro)}</p><Botao variante="secundario" carregando={buscando} onClick={() => void atualizar()}>Tentar de novo</Botao></Alerta>}
    {filas.isSuccess && !filas.data.length && <EstadoVazio titulo="Nenhuma fila liberada" descricao="Você ainda não tem filas liberadas. Fale com o gestor da unidade." acao={null} />}
    {selecionada && <>
      <div className="controles-fila controles-agenda">
        <CampoSelecao rotulo="Fila" value={estado.fila} onChange={(event) => mudar({ fila: event.target.value })}>
          {filas.data!.map((fila) => <option key={fila.id} value={fila.id}>{fila.nome} · {fila.unidade_sigla}{!fila.ativa && ' (inativa)'}</option>)}
        </CampoSelecao>
        <Campo rotulo="Data" type="date" min="2000-01-01" max="2100-12-31" value={estado.data} erro={erroData} onChange={(event) => mudar({ data: event.target.value })} />
        <div className="dias-agenda" role="group" aria-label="Mudar dia">
          <Botao variante="secundario" aria-label="Dia anterior" disabled={Boolean(erroData) || estado.data === '2000-01-01'} onClick={() => mudar({ data: mudarDiaAgenda(estado.data, -1) })}>‹ Anterior</Botao>
          <Botao variante="secundario" onClick={() => mudar({ data: hojeRecife() })}>Hoje</Botao>
          <Botao variante="secundario" aria-label="Próximo dia" disabled={Boolean(erroData) || estado.data === '2100-12-31'} onClick={() => mudar({ data: mudarDiaAgenda(estado.data, 1) })}>Próximo ›</Botao>
        </div>
      </div>
      {!erro && !erroData && consulta.isPending && <p role="status">Carregando agenda…</p>}
      {mostrar && <>
        <section className="resumo-agenda" aria-label="Resumo do dia"><dl>
          <div><dt>Total do dia</dt><dd>{itens.length}</dd></div>
          <div><dt>Presença pendente</dt><dd>{itens.filter((item) => item.status === 'CONFIRMADO' && !item.presenca_registrada).length}</dd></div>
          <div><dt>Compareceram</dt><dd>{itens.filter((item) => item.status === 'REALIZADO').length}</dd></div>
          <div><dt>Faltaram</dt><dd>{itens.filter((item) => item.status === 'FALTOU').length}</dd></div>
        </dl></section>
        {itens.length ? <AgendamentosDoDia key={`${estado.fila}:${estado.data}`} itens={itens} papel={sessao.papel} agora={agora} aoResultado={setMensagem} />
          : <EstadoVazio titulo="Nenhum agendamento" descricao="Nenhum agendamento nesta fila neste dia." acao={null} />}
      </>}
    </>}
    <p role="status" aria-atomic="true">{mensagem}</p>
  </section>
}
