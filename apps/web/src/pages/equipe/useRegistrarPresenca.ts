import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { detalheEquipeOptions, invalidarFilaEquipe, type AgendamentoDoDia, type DetalheEquipe } from './api'

type Operacao = { compareceu: boolean; controller: AbortController; epoca: number }
function atual(operacao: Operacao) { return !operacao.controller.signal.aborted && operacao.epoca === http.geracaoSessao() }
export function useRegistrarPresenca(item: AgendamentoDoDia, aoResultado: (mensagem: string) => void) {
  const client = useQueryClient()
  const requisicao = useRef<AbortController | null>(null)
  const trava = useRef(false)
  const [confirmacao, setConfirmacao] = useState(false)
  const [erro, setErro] = useState<string>()
  const [finalizacao, setFinalizacao] = useState(0)
  useEffect(() => () => { requisicao.current?.abort() }, [])

  const mutacao = useMutation({
    mutationFn: (operacao: Operacao) => http.request<DetalheEquipe>(`/equipe/agendamentos/${encodeURIComponent(item.id)}/presenca`, {
      method: 'POST', signal: operacao.controller.signal,
      body: { compareceu: operacao.compareceu } satisfies components['schemas']['PresencaEntrada'],
    }),
    onSuccess: async (_pedido, operacao) => {
      if (!atual(operacao)) return
      invalidarFilaEquipe(client)
      await Promise.all([
        client.invalidateQueries({ queryKey: ['agenda-equipe'] }),
        client.invalidateQueries({ queryKey: detalheEquipeOptions(item.solicitacao_id).queryKey }),
      ])
      if (!atual(operacao)) return
      setConfirmacao(false)
      aoResultado(operacao.compareceu ? 'Comparecimento registrado.' : 'Falta registrada. O pedido voltou para o fim da fila e o paciente será avisado.')
      setFinalizacao((valor) => valor + 1)
    },
    onError: async (error, operacao) => {
      if (!atual(operacao)) return
      setConfirmacao(false)
      if (error instanceof ApiError && error.problem.status === 409) {
        setErro(error.problem.type === '/problemas/tolerancia-nao-encerrada'
          ? 'Ainda dentro da tolerância de atraso desta fila. Tente de novo mais tarde.'
          : 'Não foi possível registrar: o horário ou a situação do agendamento mudou. A agenda foi recarregada.')
        await client.invalidateQueries({ queryKey: ['agenda-equipe'] })
      } else if (error instanceof ApiError && error.problem.status === 404) {
        setErro('Agendamento não encontrado ou fora das suas filas.')
        await client.invalidateQueries({ queryKey: ['agenda-equipe'] })
      } else setErro(error instanceof ApiError ? error.message : 'Não foi possível confirmar o registro. Atualize a agenda antes de tentar novamente.')
      if (atual(operacao)) setFinalizacao((valor) => valor + 1)
    },
    onSettled: () => { trava.current = false },
  })
  function registrar(compareceu: boolean) {
    if (trava.current || item.status !== 'CONFIRMADO' || item.presenca_registrada) return
    trava.current = true
    const controller = new AbortController()
    requisicao.current = controller
    setErro(undefined); aoResultado('')
    mutacao.mutate({ compareceu, controller, epoca: http.geracaoSessao() })
  }
  return { registrar, ocupado: mutacao.isPending, confirmacao, setConfirmacao, erro, finalizacao }
}
