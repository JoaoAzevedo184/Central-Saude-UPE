import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useForm, useWatch, type FieldError, type FieldPath } from 'react-hook-form'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { aplicarErrosDeValidacao } from '../../shared/api/form-errors'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { IndicadorEtapas } from '../../shared/ui/IndicadorEtapas'
import { CarregarMaisAtendimentos, EtapaAtendimento } from './EtapaAtendimento'
import { EtapaInformacoes } from './EtapaInformacoes'
import { EtapaRevisao } from './EtapaRevisao'
import { criarPedido, filaOptions, filasKey, filasOptions, pedidosKey } from './api'
import { montarPedido, validarResposta, type FormularioSolicitacao } from './formulario-solicitacao'

const etapas = ['Atendimento', 'Informações', 'Revisar'] as const
type CampoFormulario = FieldPath<FormularioSolicitacao>
const falhaAmbigua = 'Não foi possível confirmar se o pedido foi enviado. Confira Meus atendimentos antes de tentar novamente.'

export function NovaSolicitacao() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [etapa, setEtapa] = useState(0)
  const [falha, setFalha] = useState<{ texto: string; verPedidos?: boolean; consentimento?: boolean }>()
  const [bloqueioFila, setBloqueioFila] = useState<string>()
  const [reconciliando, setReconciliando] = useState(false)
  const titulo = useRef<HTMLHeadingElement>(null)
  const alerta = useRef<HTMLDivElement>(null)
  const focoTitulo = useRef(false)
  const errosPendentes = useRef<{ nome: CampoFormulario | 'root.server'; erro: FieldError }[] | null>(null)
  const focoErro = useRef<CampoFormulario | 'alerta' | null>(null)
  const trava = useRef(false)
  const requisicao = useRef<AbortController | null>(null)
  const montado = useRef(true)
  const formulario = useForm<FormularioSolicitacao>({ mode: 'onChange', shouldUnregister: false,
    defaultValues: { fila_id: '', origem_encaminhamento: '', turno_preferido: 'QUALQUER', respostas: [] } })
  const { setValue, getValues, clearErrors, setError, setFocus, trigger, formState: { errors } } = formulario
  const [filaId, origem, turno, respostas] = useWatch({ control: formulario.control, name: ['fila_id', 'origem_encaminhamento', 'turno_preferido', 'respostas'] })
  const dados: FormularioSolicitacao = { fila_id: filaId, origem_encaminhamento: origem, turno_preferido: turno, respostas }
  const filas = useInfiniteQuery(filasOptions)
  const detalhe = useQuery(filaOptions(dados.fila_id))
  const envio = useMutation({ mutationFn: ({ payload, signal }: { payload: Parameters<typeof criarPedido>[0]; signal: AbortSignal }) => criarPedido(payload, signal), retry: false, gcTime: 0 })
  const criterios = detalhe.data?.criterios ?? []
  const opcoes = [...new Map(filas.data?.pages.flatMap((pagina) => pagina.itens).map((fila) => [fila.id, fila]) ?? []).values()]
  const selecionada = opcoes.find((fila) => fila.id === dados.fila_id)
  const atendimentoValido = Boolean(selecionada?.elegivel && detalhe.data?.id === dados.fila_id && detalhe.data.elegivel && !detalhe.isError && bloqueioFila !== dados.fila_id && !reconciliando)
  const tamanhoOrigem = dados.origem_encaminhamento.trim().length
  const excessoRespostas = criterios.filter((_, i) => (dados.respostas[i]?.valor ?? '') !== '').length > 50
  const informacoesValidas = tamanhoOrigem >= 2 && tamanhoOrigem <= 200
    && criterios.every((criterio, i) => validarResposta(criterio, dados.respostas[i]?.valor ?? '') === true)
    && !excessoRespostas

  useEffect(() => {
    montado.current = true
    return () => { montado.current = false; requisicao.current?.abort() }
  }, [])
  useEffect(() => {
    if (!detalhe.data || detalhe.data.id !== getValues('fila_id')) return
    const antigas = getValues('respostas')
    if (antigas.length === detalhe.data.criterios.length && antigas.every((resposta, i) => resposta.criterio_id === detalhe.data!.criterios[i]?.id)) return
    setValue('respostas', detalhe.data.criterios.map((criterio) => ({ criterio_id: criterio.id,
      valor: antigas.find((resposta) => resposta.criterio_id === criterio.id)?.valor ?? '' })))
  }, [detalhe.data, getValues, setValue])
  useLayoutEffect(() => {
    if (errosPendentes.current) {
      const pendentes = errosPendentes.current
      errosPendentes.current = null
      pendentes.forEach(({ nome, erro }) => setError(nome, erro))
      const primeiro = pendentes.find(({ nome }) => nome !== 'root.server')
      focoErro.current = primeiro ? primeiro.nome as CampoFormulario : 'alerta'
    } else if (focoErro.current) {
      if (focoErro.current === 'alerta') alerta.current?.focus()
      else setFocus(focoErro.current)
      focoErro.current = null
    } else if (focoTitulo.current) { focoTitulo.current = false; titulo.current?.focus() }
  })

  function mudarEtapa(proxima: number) { focoTitulo.current = true; setEtapa(proxima) }
  function escolher(id: string) {
    if (getValues('fila_id') === id) return
    setValue('fila_id', id, { shouldValidate: true })
    setValue('respostas', [])
    clearErrors(); setFalha(undefined)
  }
  async function reconciliarFila() {
    const geracao = http.geracaoSessao()
    setReconciliando(true)
    try {
      await Promise.all([
        client.invalidateQueries({ queryKey: filasKey }, { throwOnError: true }),
        detalhe.refetch({ throwOnError: true }),
      ])
      if (montado.current && geracao === http.geracaoSessao()) setBloqueioFila(undefined)
    } catch { /* Mantém o bloqueio até uma reconciliação bem-sucedida. */ }
    finally { if (montado.current && geracao === http.geracaoSessao()) setReconciliando(false) }
  }
  async function continuar() {
    if (etapa === 0) {
      if (await trigger('fila_id', { shouldFocus: true }) && atendimentoValido) mudarEtapa(1)
    } else {
      if (await trigger(['origem_encaminhamento', 'turno_preferido', ...criterios.map((_, i) => `respostas.${i}.valor` as const)], { shouldFocus: true }) && informacoesValidas) mudarEtapa(2)
    }
  }

  async function enviar() {
    if (trava.current || !atendimentoValido || falha?.consentimento) return
    if (!informacoesValidas) { mudarEtapa(1); return }
    trava.current = true
    setFalha(undefined); clearErrors()
    const controller = new AbortController()
    requisicao.current = controller
    const geracao = http.geracaoSessao()
    const atual = () => montado.current && !controller.signal.aborted && geracao === http.geracaoSessao()
    const { payload, indices } = montarPedido(getValues(), criterios)
    try {
      await envio.mutateAsync({ payload, signal: controller.signal })
      if (!atual()) return
      await client.cancelQueries({ queryKey: pedidosKey })
      if (!atual()) return
      // A criação grava outbox; avisos dependem do Worker, não são parte deste POST.
      void client.invalidateQueries({ queryKey: pedidosKey })
      await navigate('/paciente', { replace: true, state: { mensagem: 'Pedido enviado com sucesso.' } })
    } catch (error) {
      if (!atual()) return
      const pendentes: NonNullable<typeof errosPendentes.current> = []
      const camposPayload: CampoFormulario[] = ['fila_id', 'origem_encaminhamento', 'turno_preferido',
        ...indices.flatMap((_, i) => [`respostas.${i}.criterio_id` as const, `respostas.${i}.valor` as const])]
      if (aplicarErrosDeValidacao<FormularioSolicitacao>(error, (nome, erro) => {
        const partes = nome.split('.')
        const destino = partes[0] === 'respostas' ? `respostas.${indices[Number(partes[1])]}.valor` as const : nome
        if (!pendentes.some((pendente) => pendente.nome === destino)) pendentes.push({ nome: destino as CampoFormulario | 'root.server', erro: { type: erro.type ?? 'server', message: erro.message } })
      }, camposPayload)) {
        focoTitulo.current = false
        const primeiroCampo = pendentes.find(({ nome }) => nome !== 'root.server')
        if (primeiroCampo) {
          errosPendentes.current = pendentes
          setEtapa(primeiroCampo.nome === 'fila_id' ? 0 : 1)
        } else {
          const erroGlobal = pendentes.find(({ nome }) => nome === 'root.server')?.erro
          if (erroGlobal) { focoErro.current = 'alerta'; setError('root.server', erroGlobal) }
        }
        return
      }
      if (error instanceof ApiError && error.problem.status < 500) {
        const tipo = error.problem.type
        if (error.problem.status === 409 && tipo === '/problemas/solicitacao-duplicada') {
          setFalha({ texto: 'Você já tem um pedido em andamento para este atendimento. Acompanhe-o em Meus atendimentos.', verPedidos: true })
          void client.invalidateQueries({ queryKey: pedidosKey })
        } else if (error.problem.status === 409 && tipo === '/problemas/nao-elegivel') {
          setFalha({ texto: 'Este atendimento não está disponível para você. Confira as opções atualizadas.' })
          setBloqueioFila(payload.fila_id); mudarEtapa(0)
          await reconciliarFila()
        } else {
          // TODO(api): não existe operação para renovar o consentimento nesta tela.
          setFalha({ texto: tipo === '/problemas/sem-consentimento' ? 'Seu pedido não pode ser enviado porque falta um consentimento válido para agendamento.' : error.message,
            consentimento: tipo === '/problemas/sem-consentimento' })
        }
      } else {
        setFalha({ texto: falhaAmbigua, verPedidos: true })
        void client.invalidateQueries({ queryKey: pedidosKey })
      }
    } finally { trava.current = false }
  }

  const erroFormulario = errors.root?.server?.message || errors.origem_encaminhamento?.message || errors.turno_preferido?.message || (Array.isArray(errors.respostas) && errors.respostas.some((resposta) => resposta?.valor))
  return <section className="nova-solicitacao" aria-labelledby="novo-pedido-titulo">
    <h1 id="novo-pedido-titulo">Novo pedido</h1>
    <p className="introducao">Escolha o atendimento e preencha as informações do seu pedido.</p>
    <IndicadorEtapas etapa={etapa} nomes={etapas} rotulo="Etapas da nova solicitação" />
    <form noValidate onSubmit={(event) => { event.preventDefault(); if (etapa < 2) void continuar(); else void enviar() }}>
      <h2 ref={titulo} tabIndex={-1} className="titulo-etapa">{etapas[etapa]}</h2>
      {(falha || erroFormulario || excessoRespostas) && <div ref={alerta} tabIndex={-1}><Alerta>{falha?.texto ?? errors.root?.server?.message ?? (excessoRespostas ? 'Você pode responder até 50 perguntas. Deixe as demais sem resposta.' : 'Confira os campos indicados.')}
        {falha?.verPedidos && <Link to="/paciente">Ver meus atendimentos</Link>}
      </Alerta></div>}
      <fieldset className="campos-etapa" disabled={envio.isPending || reconciliando}>
        <legend className="sr-only">{etapas[etapa]}</legend>
        {etapa === 0 && <>
          {filas.isPending && <p role="status">Carregando atendimentos…</p>}
          {filas.isError && <Alerta>Não foi possível carregar os atendimentos.<Botao type="button" variante="secundario" carregando={filas.isFetching} onClick={() => void (filas.isFetchNextPageError ? filas.fetchNextPage({ cancelRefetch: false }) : filas.refetch())}>Tentar de novo</Botao></Alerta>}
          {filas.data && <>
            {opcoes.length === 0 ? <p>Nenhum atendimento está disponível no momento.</p> : <EtapaAtendimento filas={opcoes} formulario={formulario} aoEscolher={escolher} />}
            {filas.hasNextPage && !filas.isFetchNextPageError && <CarregarMaisAtendimentos carregando={filas.isFetching} aoCarregar={() => { if (!filas.isFetching) void filas.fetchNextPage({ cancelRefetch: false }) }} />}
          </>}
          {dados.fila_id && detalhe.isPending && <p role="status">Carregando informações do atendimento…</p>}
          {detalhe.isError && <Alerta>Não foi possível carregar este atendimento.<Botao type="button" variante="secundario" carregando={detalhe.isFetching} onClick={() => void detalhe.refetch()}>Tentar carregar atendimento de novo</Botao></Alerta>}
          {detalhe.data && !detalhe.data.elegivel && <Alerta>{detalhe.data.motivo_inelegivel ?? 'Este atendimento não está disponível para você.'}</Alerta>}
        </>}
        {etapa === 1 && <EtapaInformacoes criterios={criterios} formulario={formulario} />}
        {etapa === 2 && detalhe.data && <EtapaRevisao fila={detalhe.data} dados={dados} />}
      </fieldset>
      {etapa > 0 && !atendimentoValido && !reconciliando && <Alerta>Confira a disponibilidade do atendimento antes de continuar.
        <Botao type="button" variante="secundario" disabled={envio.isPending} onClick={() => mudarEtapa(0)}>Rever atendimento</Botao>
      </Alerta>}
      {reconciliando && <p role="status">Atualizando atendimentos…</p>}
      {bloqueioFila === dados.fila_id && !reconciliando && <Botao type="button" variante="secundario" onClick={() => void reconciliarFila()}>Atualizar atendimento</Botao>}
      <div className="acoes-etapa">
        {etapa > 0 && <Botao type="button" variante="secundario" disabled={envio.isPending || reconciliando} onClick={() => { clearErrors(); mudarEtapa(etapa - 1) }}>Voltar</Botao>}
        <Botao type="submit" carregando={envio.isPending} disabled={!atendimentoValido || (etapa > 0 && !informacoesValidas) || Boolean(falha?.consentimento)}>{etapa < 2 ? 'Continuar' : 'Enviar pedido'}</Botao>
      </div>
    </form>
  </section>
}
