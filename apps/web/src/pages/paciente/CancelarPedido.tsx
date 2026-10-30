import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { components } from '../../shared/api/generated/schema'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { CampoSelecao } from '../../shared/ui/CampoSelecao'
import { Dialogo } from '../../shared/ui/Dialogo'
import { detalhePedidoOptions, incorporarPedido, pedidosKey } from './api'
import type { DetalhePedido } from './api'

type Motivo = components['schemas']['MotivoCancelamento']
const motivos: Record<Motivo, string> = {
  NAO_PRECISO_MAIS: 'Não preciso mais', CONSEGUI_EM_OUTRO_LUGAR: 'Consegui atendimento em outro lugar',
  DIFICULDADE_DE_DESLOCAMENTO: 'Tenho dificuldade de ir até lá', CONFLITO_DE_HORARIO: 'O horário não dá', OUTRO: 'Outro motivo',
}

export function CancelarPedido({ id, permitido, bloqueado, sincronizandoRelogio = false, aoEnviar }: {
  id: string; permitido: boolean; bloqueado: boolean; sincronizandoRelogio?: boolean; aoEnviar: (enviando: boolean) => void
}) {
  const [aberto, setAberto] = useState(false)
  const [motivo, setMotivo] = useState<Motivo | ''>('')
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string>()
  const [mensagem, setMensagem] = useState<string>()
  const ref = useRef<HTMLParagraphElement>(null)
  const requisicao = useRef<AbortController | null>(null)
  const trava = useRef(false)
  const client = useQueryClient()
  useEffect(() => () => { requisicao.current?.abort(); aoEnviar(false) }, [aoEnviar])
  useEffect(() => { if (mensagem) ref.current?.focus() }, [mensagem])
  if (aberto && !permitido && !enviando && !sincronizandoRelogio) {
    setAberto(false)
    setMensagem('Este atendimento mudou. Confira os dados atualizados do seu pedido.')
  }
  if (!permitido && erro && !sincronizandoRelogio) setErro(undefined)

  async function cancelar() {
    if (!motivo || trava.current || bloqueado || !permitido) return
    trava.current = true; setEnviando(true); aoEnviar(true); setErro(undefined); setMensagem(undefined)
    const controller = new AbortController(); requisicao.current = controller
    const epoca = http.geracaoSessao()
    const atual = () => !controller.signal.aborted && epoca === http.geracaoSessao()
    try {
      const atualizado = await http.request<DetalhePedido>(`/solicitacoes/${encodeURIComponent(id)}/cancelar`, {
        method: 'POST', body: { motivo_codigo: motivo } satisfies components['schemas']['CancelamentoEntrada'], signal: controller.signal,
      })
      if (!atual()) return
      await incorporarPedido(client, atualizado, controller.signal, epoca)
      if (!atual()) return
      setAberto(false); setMensagem('Pedido cancelado.')
    } catch (error) {
      if (!atual() || (error instanceof DOMException && error.name === 'AbortError')) return
      if (error instanceof ApiError && [404, 409].includes(error.problem.status)) {
        setAberto(false)
        setMensagem('Este atendimento mudou. Confira os dados atualizados do seu pedido.')
        void client.invalidateQueries({ queryKey: detalhePedidoOptions(id).queryKey })
        void client.invalidateQueries({ queryKey: pedidosKey })
      } else {
        setErro(error instanceof ApiError ? error.problem.status === 422 ? 'Escolha um dos motivos da lista e tente novamente.' : error.message
          : 'Não foi possível confirmar o cancelamento. Confira o pedido antes de tentar novamente.')
        // O diálogo pode ter sido fechado com Esc enquanto o POST estava pendente.
        void client.invalidateQueries({ queryKey: detalhePedidoOptions(id).queryKey })
      }
    } finally {
      trava.current = false
      if (!controller.signal.aborted) { setEnviando(false); aoEnviar(false) }
    }
  }

  return <>
    {mensagem && <p role="status" className="mensagem-sucesso" tabIndex={-1} ref={ref}>{mensagem}</p>}
    {erro && !aberto && <Alerta>{erro}</Alerta>}
    {(permitido || (aberto && sincronizandoRelogio)) && <div className="cancelar-pedido"><Botao variante="secundario" disabled={bloqueado || enviando || sincronizandoRelogio}
      onClick={() => { setMotivo(''); setErro(undefined); setAberto(true) }}>Cancelar pedido</Botao></div>}
    {aberto && <Dialogo titulo="Cancelar pedido" aoFechar={() => setAberto(false)}>
      <p>Seu pedido será encerrado. Se precisar de novo, faça um novo pedido.</p>
      <CampoSelecao rotulo="Por que você quer cancelar?" data-foco-inicial value={motivo} disabled={enviando}
        onChange={(event) => setMotivo(event.target.value as Motivo | '')}>
        <option value="">Escolha um motivo</option>
        {Object.entries(motivos).map(([codigo, texto]) => <option key={codigo} value={codigo}>{texto}</option>)}
      </CampoSelecao>
      {erro && <Alerta>{erro}</Alerta>}
      <div className="acoes-dialogo">
        <Botao variante="secundario" onClick={() => setAberto(false)}>Voltar</Botao>
        <Botao disabled={!motivo || !permitido} carregando={enviando} onClick={() => void cancelar()}>Cancelar pedido</Botao>
      </div>
    </Dialogo>}
  </>
}
