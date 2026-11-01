import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { aplicarErrosDeValidacao } from '../../shared/api/form-errors'
import { buscarDetalheEquipe, detalheEquipeOptions, incorporarDetalheEquipe, invalidarFilaEquipe, type DetalheEquipe } from './api'

export const riscosEquipe = { VERMELHO: 'Alto', AMARELO: 'Médio', VERDE: 'Baixo' } as const
export const mensagemPedidoAtualizado = 'Este pedido foi atualizado por outra pessoa. Os dados foram recarregados.'
type Risco = components['schemas']['ClassificacaoRisco']
type Formulario = { classificacao_risco: Risco | ''; motivo: string }
type Confirmacao = { risco: Risco; motivo: string; anterior: DetalheEquipe }
export function podeClassificar(pedido: DetalheEquipe) { return ['EM_ANALISE', 'NA_FILA'].includes(pedido.status) }
function mudou(a: DetalheEquipe, b: DetalheEquipe) {
  return a.status !== b.status || a.classificacao_risco !== b.classificacao_risco
}

export function useClassificarRisco(pedido: DetalheEquipe) {
  const client = useQueryClient()
  const form = useForm<Formulario>({ defaultValues: { classificacao_risco: pedido.classificacao_risco ?? '', motivo: '' } })
  const { setValue, setFocus } = form
  const [confirmacao, setConfirmacao] = useState<Confirmacao | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [mensagem, setMensagem] = useState<string>()
  const [erro, setErro] = useState<string>()
  const [foco, setFoco] = useState<keyof Formulario>()
  const trava = useRef(false)
  const requisicao = useRef<AbortController | null>(null)
  const epocaOperacao = useRef(0)
  useEffect(() => () => { requisicao.current?.abort() }, [])
  useEffect(() => { setValue('classificacao_risco', pedido.classificacao_risco ?? '') }, [pedido.classificacao_risco, pedido.status, setValue])
  useEffect(() => {
    if (foco && !confirmacao && epocaOperacao.current === http.geracaoSessao() && !requisicao.current?.signal.aborted) {
      setFocus(foco); setFoco(undefined)
    }
  }, [foco, confirmacao, setFocus])
  // Uma leitura em segundo plano também pode retirar a validade da confirmação aberta.
  if (confirmacao && !ocupado && mudou(confirmacao.anterior, pedido)) {
    setConfirmacao(null); setMensagem(mensagemPedidoAtualizado)
  }

  function iniciar() {
    if (trava.current) return
    trava.current = true; setOcupado(true); setErro(undefined); setMensagem(undefined)
    const controller = new AbortController()
    requisicao.current = controller; epocaOperacao.current = http.geracaoSessao()
    const epoca = epocaOperacao.current
    const atual = () => !controller.signal.aborted && epoca === http.geracaoSessao()
    return { controller, epoca, atual }
  }
  function terminar(atual: () => boolean) {
    trava.current = false
    if (atual()) setOcupado(false)
  }
  async function recarregar(signal: AbortSignal, epoca: number) {
    await client.cancelQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey })
    if (signal.aborted || epoca !== http.geracaoSessao()) return
    const novo = await buscarDetalheEquipe(pedido.id, signal)
    await incorporarDetalheEquipe(client, novo, signal, epoca)
    return novo
  }
  function tratarErro(error: unknown) {
    if (error instanceof ApiError && [403, 404].includes(error.problem.status)) {
      setErro(error.problem.status === 404 ? 'Pedido não encontrado ou fora das suas filas.'
        : error.problem.type === '/problemas/csrf-invalido' ? error.message
          : 'Não foi possível realizar esta ação. Confira seu acesso com o gestor da unidade.')
      void client.invalidateQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey })
    } else setErro(error instanceof ApiError ? error.message : 'Não foi possível confirmar a operação. Confira o pedido antes de tentar novamente.')
  }
  async function preparar(event: FormEvent<HTMLFormElement>) {
    await form.handleSubmit(async (dados) => {
      if (!podeClassificar(pedido)) return
      const operacao = iniciar()
      if (!operacao) return
      const { controller, epoca, atual } = operacao
      try {
        const novo = await recarregar(controller.signal, epoca)
        if (!atual() || !novo) return
        if (mudou(pedido, novo)) {
          invalidarFilaEquipe(client); setMensagem(mensagemPedidoAtualizado)
        } else {
          setConfirmacao({ risco: dados.classificacao_risco as Risco, motivo: dados.motivo.trim(), anterior: novo })
        }
      } catch (error) { if (atual()) tratarErro(error) }
      finally { terminar(atual) }
    })(event)
  }
  async function confirmar() {
    if (!confirmacao || mudou(confirmacao.anterior, pedido) || !podeClassificar(pedido)) return
    const operacao = iniciar()
    if (!operacao) return
    const { controller, epoca, atual } = operacao
    const { risco, motivo } = confirmacao
    try {
      const atualizado = await http.request<DetalheEquipe>(`/equipe/solicitacoes/${encodeURIComponent(pedido.id)}/classificar`, {
        method: 'POST', signal: controller.signal,
        body: { classificacao_risco: risco, motivo } satisfies components['schemas']['ClassificacaoEntrada'],
      })
      if (!atual()) return
      await incorporarDetalheEquipe(client, atualizado, controller.signal, epoca)
      if (!atual()) return
      setConfirmacao(null); setMensagem(`Pedido classificado como ${riscosEquipe[risco]}.`)
      form.reset({ classificacao_risco: atualizado.classificacao_risco ?? '', motivo: '' })
      invalidarFilaEquipe(client)
      void client.invalidateQueries({ queryKey: detalheEquipeOptions(pedido.id).queryKey })
    } catch (error) {
      if (!atual()) return
      setConfirmacao(null)
      if (error instanceof ApiError && error.problem.status === 409 && error.problem.type === '/problemas/transicao-invalida') {
        invalidarFilaEquipe(client)
        try {
          await recarregar(controller.signal, epoca)
          if (atual()) setMensagem(mensagemPedidoAtualizado)
        } catch { if (atual()) setErro('O pedido mudou, mas não foi possível recarregar os dados. Atualize o pedido antes de tentar novamente.') }
      } else if (!aplicarErrosDeValidacao<Formulario>(error, (campo, falha) => {
        form.setError(campo, falha)
        if (campo === 'motivo' || campo === 'classificacao_risco') setFoco((primeiro) => primeiro ?? campo)
      }, ['classificacao_risco', 'motivo'], (campo, falha) => {
        if (campo === 'classificacao_risco' && ['enum', 'missing'].includes(falha.type)) return 'Escolha Alto, Médio ou Baixo.'
        if (campo === 'motivo' && ['string_too_short', 'string_too_long', 'missing', 'string_type', 'too_short', 'too_long'].includes(falha.type)) return 'Informe um motivo com 3 a 500 caracteres.'
        return undefined
      })) tratarErro(error)
    } finally { terminar(atual) }
  }
  return { form, preparar, confirmar, confirmacao, fechar: () => setConfirmacao(null), ocupado, mensagem, erro }
}
