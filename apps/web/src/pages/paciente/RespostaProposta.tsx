import { useEffect, useRef } from 'react'
import { formatarDataHora } from '../../shared/datas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { Dialogo } from '../../shared/ui/Dialogo'
import type { useProposta } from './useProposta'

type Resposta = ReturnType<typeof useProposta>
export function MensagensProposta({ resposta }: { resposta: Resposta }) {
  const { mensagem, falha, dialogo, tentativa, setDialogo } = resposta
  const ref = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (mensagem) ref.current?.focus() }, [mensagem])
  return <>
    {mensagem && <p role="status" className="mensagem-sucesso" ref={ref} tabIndex={-1}>{mensagem}</p>}
    {falha && !dialogo && <Alerta>{falha}
      <Botao variante="secundario" onClick={() => setDialogo(tentativa)}>Rever e tentar de novo</Botao>
    </Alerta>}
  </>
}
export function DialogoProposta({ resposta }: { resposta: Resposta }) {
  const { dialogo, setDialogo, falha, enviando, responder } = resposta
  if (!dialogo) return null
  return <Dialogo titulo={dialogo.acao === 'confirmar' ? 'Confirmar consulta' : 'Esta data não serve'} aoFechar={() => setDialogo(undefined)}>
    <p>{dialogo.acao === 'confirmar' ? `Confirmar a consulta de ${formatarDataHora(dialogo.pedido.agendamento_ativo!.inicio)}?` : 'Você continua na fila e vamos procurar outra data.'}</p>
    {falha && <Alerta>{falha}</Alerta>}
    <div className="acoes-dialogo">
      <Botao variante="secundario" data-foco-inicial onClick={() => setDialogo(undefined)}>Voltar</Botao>
      <Botao carregando={enviando} onClick={() => void responder()}>{falha ? 'Tentar de novo' : dialogo.acao === 'confirmar' ? 'Confirmar consulta' : 'Esta data não serve'}</Botao>
    </div>
  </Dialogo>
}
