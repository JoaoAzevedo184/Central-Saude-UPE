import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { formatarDataHora } from '../../shared/datas'
import { Abas } from '../../shared/ui/Abas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { Dialogo } from '../../shared/ui/Dialogo'
import { EstadoVazio } from '../../shared/ui/EstadoVazio'
import { Paginacao } from '../../shared/ui/Paginacao'
import { CartaoPedido } from './CartaoPedido'
import { PropostaVaga } from './PropostaVaga'
import type { AcaoProposta } from './PropostaVaga'
import { limitePedidos, pedidosKey, pedidosOptions, propostasOptions, temProposta } from './api'
import type { DetalhePedido, Pedido, Situacao } from './api'

const abas = [{ valor: 'abertas', texto: 'Em andamento' }, { valor: 'encerradas', texto: 'Histórico' }] as const
const mensagemExpirada = 'O prazo para confirmar terminou. Seu pedido voltou para a fila.'

export function MeusAtendimentos() {
  const [situacao, setSituacao] = useState<Situacao>('abertas')
  const [pagina, setPagina] = useState(0)
  const [agora, setAgora] = useState(Date.now)
  const [dialogo, setDialogo] = useState<{ pedido: Pedido; acao: AcaoProposta }>()
  const [enviando, setEnviando] = useState(false)
  const [falha, setFalha] = useState<string>()
  const [tentativa, setTentativa] = useState<{ pedido: Pedido; acao: AcaoProposta }>()
  const [mensagem, setMensagem] = useState<string>()
  const mensagemRef = useRef<HTMLParagraphElement>(null)
  const requisicao = useRef<AbortController | null>(null)
  const travaEnvio = useRef(false)
  const client = useQueryClient()
  const lista = useQuery(pedidosOptions(situacao, pagina))
  const propostas = useQuery(propostasOptions)

  useEffect(() => {
    const atualizar = () => setAgora(Date.now())
    const timer = window.setInterval(atualizar, 30_000)
    document.addEventListener('visibilitychange', atualizar)
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', atualizar); requisicao.current?.abort() }
  }, [])
  useEffect(() => { if (mensagem) mensagemRef.current?.focus() }, [mensagem])
  const ultimaPagina = lista.data ? Math.max(0, Math.ceil(lista.data.total / limitePedidos) - 1) : pagina
  // Ajusta o próprio estado antes do commit: não exibe a página inválida como vazia.
  // A nova queryKey busca a página válida, inclusive a página inicial com total zero.
  if (pagina > ultimaPagina) setPagina(ultimaPagina)
  function atualizar() { void client.invalidateQueries({ queryKey: pedidosKey }) }
  // O destaque também fica visível no Histórico e nas outras páginas.
  const destaques = new Map((propostas.data ?? []).map((pedido) => [pedido.id, pedido]))
  for (const pedido of lista.data?.itens ?? []) {
    if (temProposta(pedido) && !lista.isError) destaques.set(pedido.id, pedido)
    // Uma leitura antiga da lista não apaga uma proposta recém-encontrada.
    // Se a busca falhar, a lista atualizada ainda deve remover propostas já respondidas.
    else if (propostas.isError || lista.dataUpdatedAt > propostas.dataUpdatedAt) destaques.delete(pedido.id)
  }

  async function responder() {
    if (!dialogo || travaEnvio.current) return
    travaEnvio.current = true
    setEnviando(true); setFalha(undefined); setMensagem(undefined)
    const controller = new AbortController()
    requisicao.current = controller
    const { pedido, acao } = dialogo
    try {
      const atualizado = await http.request<DetalhePedido>(`/agendamentos/${pedido.agendamento_ativo!.id}/${acao}`, { method: 'POST', signal: controller.signal })
      if (controller.signal.aborted) return
      setDialogo(undefined)
      setMensagem(acao === 'confirmar' ? 'Consulta confirmada' : 'Você continua na fila e vamos procurar outra data.')
      // Cancela leituras antigas antes de incorporar a transição confirmada pela API.
      await client.cancelQueries({ queryKey: pedidosKey })
      if (controller.signal.aborted) return
      client.setQueryData<Pedido[]>(propostasOptions.queryKey, (antigos) => antigos?.filter((item) => item.id !== atualizado.id))
      client.setQueriesData<{ total: number; itens: Pedido[] }>({ queryKey: pedidosKey,
        predicate: (query) => query.queryKey[1] !== 'propostas' }, (antiga) => antiga ? {
          ...antiga, itens: antiga.itens.map((item) => item.id === atualizado.id ? atualizado : item),
        } : antiga)
      atualizar()
      void client.invalidateQueries({ queryKey: ['avisos', 'contagem'] })
    } catch (error) {
      if (controller.signal.aborted) return
      if (error instanceof ApiError && error.problem.status === 409) {
        setDialogo(undefined)
        setMensagem(error.problem.type === '/problemas/proposta-expirada' ? mensagemExpirada : 'Este atendimento mudou. Confira os dados atualizados do seu pedido.')
        atualizar()
      } else {
        setTentativa({ pedido, acao })
        setFalha(error instanceof ApiError ? error.message : 'Não foi possível conectar. Confira sua internet e tente de novo.')
      }
    } finally {
      travaEnvio.current = false
      if (!controller.signal.aborted) setEnviando(false)
    }
  }
  return <>
    <h1>Meus atendimentos</h1><p className="introducao">Acompanhe seus pedidos e confirme sua consulta quando uma vaga chegar.</p>
    {mensagem && <p role="status" className="mensagem-sucesso" ref={mensagemRef} tabIndex={-1}>{mensagem}</p>}
    {falha && !dialogo && <Alerta>{falha}
      <Botao variante="secundario" onClick={() => setDialogo(tentativa)}>Rever e tentar de novo</Botao>
    </Alerta>}
    {propostas.isPending && <p role="status">Buscando propostas de vaga…</p>}
    {propostas.isError && <Alerta>Não foi possível buscar propostas de vaga.
      <Botao variante="secundario" carregando={propostas.isFetching} onClick={() => void propostas.refetch()}>Tentar buscar propostas de novo</Botao>
    </Alerta>}
    {destaques.size > 0 && <section className="propostas" aria-label="Propostas de vaga">
      {Array.from(destaques.values()).map((pedido) => <PropostaVaga key={pedido.id} pedido={pedido} agora={agora} enviando={enviando}
        aoAtualizar={atualizar} aoResponder={(acao) => { setFalha(undefined); setDialogo({ pedido, acao }) }} />)}
    </section>}
    <Abas itens={abas} valor={situacao} aoMudar={(valor) => { setSituacao(valor); setPagina(0) }}>
      {lista.isPending && <p role="status">Carregando seus pedidos…</p>}
      {lista.isError && <Alerta>Não foi possível carregar seus pedidos.
        <Botao variante="secundario" carregando={lista.isFetching} onClick={() => void lista.refetch()}>Tentar de novo</Botao>
      </Alerta>}
      {lista.data && <>
        {lista.data.total === 0 ? <EstadoVazio /> : <>
          <div className="lista-pedidos">{lista.data.itens.map((pedido) => destaques.has(pedido.id) ? null : <CartaoPedido key={pedido.id} pedido={pedido} />)}</div>
          {lista.data.itens.length > 0 && lista.data.itens.every((pedido) => destaques.has(pedido.id)) && <p>Sua proposta está em destaque acima.</p>}
          <Paginacao total={lista.data.total} limite={limitePedidos} pagina={pagina} aoMudar={setPagina} />
        </>}
      </>}
    </Abas>
    {dialogo && <Dialogo titulo={dialogo.acao === 'confirmar' ? 'Confirmar consulta' : 'Esta data não serve'} aoFechar={() => setDialogo(undefined)}>
      <p>{dialogo.acao === 'confirmar' ? `Confirmar a consulta de ${formatarDataHora(dialogo.pedido.agendamento_ativo!.inicio)}?` : 'Você continua na fila e vamos procurar outra data.'}</p>
      {falha && <Alerta>{falha}</Alerta>}
      <div className="acoes-dialogo">
        <Botao variante="secundario" data-foco-inicial onClick={() => setDialogo(undefined)}>Voltar</Botao>
        <Botao carregando={enviando} onClick={() => void responder()}>{falha ? 'Tentar de novo' : dialogo.acao === 'confirmar' ? 'Confirmar consulta' : 'Esta data não serve'}</Botao>
      </div>
    </Dialogo>}
  </>
}
