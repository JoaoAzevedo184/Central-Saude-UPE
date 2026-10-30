import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { http } from '../../shared/api/http'
import { formatarDataHoraCompleta } from '../../shared/datas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { avisosOptions, listaAvisosKey, listaAvisosOptions, type Aviso } from './api'

const generico = ['Atualização no atendimento', 'Há uma atualização no seu atendimento.'] as const
const fallback: Record<Aviso['tipo'], readonly [string, string]> = {
  SOLICITACAO_CRIADA: ['Recebemos seu pedido', 'Seu pedido está em análise.'],
  SOLICITACAO_NA_FILA: ['Seu pedido entrou na fila', 'Avisaremos quando houver uma vaga para você.'],
  PROPOSTA_ENVIADA: ['Você tem uma proposta de vaga', 'Confira a data e o prazo para confirmar no seu pedido.'],
  AGENDAMENTO_CONFIRMADO: ['Consulta confirmada', 'Confira os dados da consulta no seu pedido.'],
  PROPOSTA_RECUSADA: ['Recebemos sua recusa', 'Seu pedido continua aguardando uma nova vaga.'],
  PROPOSTA_EXPIRADA: ['O prazo para confirmar acabou', 'Seu pedido continua aguardando uma nova vaga.'],
  AGENDAMENTO_CANCELADO: ['Cancelamento registrado', 'Sua consulta foi cancelada e seu pedido foi encerrado.'],
  SOLICITACAO_CANCELADA: ['Cancelamento registrado', 'Seu pedido foi cancelado.'],
  FALTA_REGISTRADA: ['Registramos sua falta', 'Confira a atualização no seu pedido.'],
  ATENDIMENTO_REGISTRADO: ['Atendimento registrado', 'Seu atendimento foi registrado.'],
  LEMBRETE: ['Lembrete da consulta', 'Confira os dados da consulta no seu pedido.'],
}

// O trim só detecta ausência: o texto recebido é exibido inteiro e escapado pelo React.
function textos(aviso: Aviso) {
  const padrao = Object.hasOwn(fallback, aviso.tipo) ? fallback[aviso.tipo] : generico
  return [aviso.titulo?.trim() ? aviso.titulo : padrao[0], aviso.corpo?.trim() ? aviso.corpo : padrao[1]]
}

export function Avisos() {
  const lista = useInfiniteQuery(listaAvisosOptions)
  const contagem = useQuery(avisosOptions)
  const client = useQueryClient()
  const navigate = useNavigate()
  const [pendente, setPendente] = useState<string>()
  const [erro, setErro] = useState<string>()
  const [mensagem, setMensagem] = useState<string>()
  const mensagemRef = useRef<HTMLParagraphElement>(null)
  const montado = useRef(false)
  const operacao = useRef<{ controller: AbortController; timer?: ReturnType<typeof setTimeout> } | null>(null)
  useEffect(() => {
    montado.current = true
    return () => {
      montado.current = false
      operacao.current?.controller.abort()
      clearTimeout(operacao.current?.timer)
    }
  }, [])
  useEffect(() => { if (mensagem) mensagemRef.current?.focus() }, [mensagem])

  const itens = Array.from(new Map(lista.data?.pages.flatMap((pagina) => pagina.itens).map((aviso) => [aviso.id, aviso])).values())

  async function atualizar(epoca: number) {
    await Promise.all([client.cancelQueries({ queryKey: listaAvisosKey }), client.cancelQueries(avisosOptions)])
    if (epoca !== http.geracaoSessao()) return
    void client.invalidateQueries({ queryKey: listaAvisosKey })
    void client.invalidateQueries(avisosOptions)
  }

  async function marcar(aviso?: Aviso) {
    if (operacao.current) return
    const destino = aviso?.solicitacao_id ? `/paciente/solicitacoes/${aviso.solicitacao_id}` : undefined
    if (aviso?.lido_em) { if (destino) void navigate(destino); return }
    const controller = new AbortController()
    const atual = { controller, timer: undefined as ReturnType<typeof setTimeout> | undefined }
    operacao.current = atual
    const epoca = http.geracaoSessao()
    const vigente = () => !controller.signal.aborted && epoca === http.geracaoSessao()
    setPendente(aviso?.id ?? 'todos'); setErro(undefined); setMensagem(undefined)
    if (destino) atual.timer = setTimeout(() => {
      const podeNavegar = vigente()
      controller.abort()
      if (podeNavegar) void navigate(destino)
    }, 3_000)
    try {
      await http.request(aviso ? `/avisos/${encodeURIComponent(aviso.id)}/lido` : '/avisos/lidos', { method: 'POST', signal: controller.signal })
      if (!vigente()) return
      clearTimeout(atual.timer)
      void atualizar(epoca)
      if (destino) void navigate(destino)
      else setMensagem('Todos os avisos foram marcados como lidos.')
    } catch {
      if (!vigente()) return
      if (destino) void navigate(destino)
      else setErro('Não foi possível marcar todos os avisos. Tente de novo.')
    } finally {
      clearTimeout(atual.timer)
      if (operacao.current === atual) {
        operacao.current = null
        if (montado.current) setPendente(undefined)
      }
    }
  }

  function abrir(event: MouseEvent<HTMLAnchorElement>, aviso: Aviso) {
    if (operacao.current) { event.preventDefault(); return }
    // Preserva abrir em outra aba/janela e copiar endereço como em qualquer link.
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    void marcar(aviso)
  }

  return <div className="pagina-avisos">
    <h1>Avisos</h1>
    <p className="introducao">Acompanhe as novidades dos seus atendimentos.</p>
    {(contagem.data?.nao_lidos ?? 0) > 0 && <div className="acoes-avisos"><Botao variante="secundario" disabled={Boolean(pendente)}
      carregando={pendente === 'todos'} onClick={() => void marcar()}>Marcar todos como lidos</Botao></div>}
    {mensagem && <p role="status" className="mensagem-sucesso" ref={mensagemRef} tabIndex={-1}>{mensagem}</p>}
    {erro && <Alerta>{erro}</Alerta>}
    {lista.isPending && <p role="status">Carregando seus avisos…</p>}
    {lista.isError && <Alerta>{lista.isFetchNextPageError ? 'Não foi possível carregar mais avisos.' : 'Não foi possível carregar seus avisos.'}
      <Botao variante="secundario" carregando={lista.isFetching} onClick={() => void (lista.isFetchNextPageError ? lista.fetchNextPage() : lista.refetch())}>Tentar de novo</Botao>
    </Alerta>}
    {lista.data && itens.length === 0 && <div className="estado-vazio"><h2>Nenhum aviso por enquanto</h2><p>Quando houver novidade, ela aparecerá aqui.</p></div>}
    {itens.length > 0 && <ul className="lista-avisos" aria-label="Seus avisos">
      {itens.map((aviso) => {
        const [titulo, corpo] = textos(aviso)
        return <li key={aviso.id} className={`cartao aviso${aviso.lido_em ? '' : ' aviso-nao-lido'}`}>
          <div className="aviso-meta">{!aviso.lido_em && <span className="aviso-leitura">Novo</span>}
            <time dateTime={aviso.criado_em}>{formatarDataHoraCompleta(aviso.criado_em)}</time></div>
          <h2>{titulo}</h2><p className="aviso-corpo">{corpo}</p>
          {aviso.solicitacao_id && <a className="link-detalhes" href={`/paciente/solicitacoes/${aviso.solicitacao_id}`}
            aria-busy={pendente === aviso.id || undefined} aria-disabled={Boolean(pendente) || undefined}
            onClick={(event) => abrir(event, aviso)}>{pendente === aviso.id ? 'Abrindo…' : 'Ver pedido'}<span className="sr-only">: {titulo}</span></a>}
        </li>
      })}
    </ul>}
    {lista.hasNextPage && <div className="carregar-avisos"><Botao variante="secundario" carregando={lista.isFetchingNextPage}
      disabled={lista.isFetching || Boolean(pendente)} onClick={() => void lista.fetchNextPage()}>Carregar mais</Botao></div>}
  </div>
}
