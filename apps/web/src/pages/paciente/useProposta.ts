import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { detalhePedidoOptions, incorporarPedido, pedidosKey } from './api'
import type { DetalhePedido, Pedido } from './api'
import type { AcaoProposta } from './PropostaVaga'

export function useProposta(referencia?: { pedido: Pedido; agora: number }) {
  const [dialogo, setDialogo] = useState<{ pedido: Pedido; acao: AcaoProposta }>()
  const [enviando, setEnviando] = useState(false)
  const [falha, setFalha] = useState<string>()
  const [tentativa, setTentativa] = useState<{ pedido: Pedido; acao: AcaoProposta }>()
  const [mensagem, setMensagem] = useState<string>()
  const requisicao = useRef<AbortController | null>(null)
  const travaEnvio = useRef(false)
  const client = useQueryClient()
  useEffect(() => () => { requisicao.current?.abort() }, [])
  // Só o detalhe fornece a referência atual. A lista mantém o comportamento existente.
  // Não fecha durante um envio: a própria resposta do POST pode estar atualizando o cache.
  if (dialogo && referencia && !enviando) {
    const atual = referencia.pedido.agendamento_ativo
    const anterior = dialogo.pedido.agendamento_ativo!
    if (referencia.pedido.status !== 'EM_PROPOSTA' || atual?.status !== 'PROPOSTO'
      || atual.id !== anterior.id || atual.inicio !== anterior.inicio || atual.expira_em !== anterior.expira_em
      || (atual.expira_em !== null && new Date(atual.expira_em).getTime() <= referencia.agora)) {
      setDialogo(undefined); setTentativa(undefined); setFalha(undefined)
      setMensagem('Este atendimento mudou. Confira os dados atualizados do seu pedido.')
    }
  }
  async function responder() {
    if (!dialogo || travaEnvio.current) return
    travaEnvio.current = true
    setEnviando(true); setFalha(undefined); setMensagem(undefined)
    const controller = new AbortController()
    requisicao.current = controller
    const epoca = http.geracaoSessao()
    const atual = () => !controller.signal.aborted && epoca === http.geracaoSessao()
    const { pedido, acao } = dialogo
    try {
      const atualizado = await http.request<DetalhePedido>(`/agendamentos/${pedido.agendamento_ativo!.id}/${acao}`, { method: 'POST', signal: controller.signal })
      if (!atual()) return
      await incorporarPedido(client, atualizado, controller.signal, epoca)
      if (!atual()) return
      setDialogo(undefined)
      setMensagem(acao === 'confirmar' ? 'Consulta confirmada' : 'Você continua na fila e vamos procurar outra data.')
    } catch (error) {
      if (!atual()) return
      if (error instanceof ApiError && error.problem.status === 409) {
        setDialogo(undefined)
        setMensagem(error.problem.type === '/problemas/proposta-expirada' ? 'O prazo para confirmar terminou. Seu pedido voltou para a fila.' : 'Este atendimento mudou. Confira os dados atualizados do seu pedido.')
        void client.invalidateQueries({ queryKey: pedidosKey })
        void client.invalidateQueries(detalhePedidoOptions(pedido.id))
      } else if (!(error instanceof DOMException && error.name === 'AbortError')) {
        setTentativa({ pedido, acao })
        setFalha(error instanceof ApiError ? error.message : 'Não foi possível conectar. Confira sua internet e tente de novo.')
      }
    } finally {
      travaEnvio.current = false
      if (!controller.signal.aborted) setEnviando(false)
    }
  }
  return { dialogo, setDialogo, enviando, falha, setFalha, tentativa, mensagem, responder }
}
