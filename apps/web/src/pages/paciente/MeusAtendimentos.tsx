import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Abas } from '../../shared/ui/Abas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { EstadoVazio } from '../../shared/ui/EstadoVazio'
import { Paginacao } from '../../shared/ui/Paginacao'
import { CartaoPedido } from './CartaoPedido'
import { PropostaVaga } from './PropostaVaga'
import { useProposta } from './useProposta'
import { useAgora } from './useAgora'
import { DialogoProposta, MensagensProposta } from './RespostaProposta'
import { limitePedidos, pedidosKey, pedidosOptions, propostasOptions, temProposta } from './api'
import type { Situacao } from './api'

const abas = [{ valor: 'abertas', texto: 'Em andamento' }, { valor: 'encerradas', texto: 'Histórico' }] as const

export function MeusAtendimentos() {
  const [situacao, setSituacao] = useState<Situacao>('abertas')
  const [pagina, setPagina] = useState(0)
  const agora = useAgora()
  const resposta = useProposta()
  const { enviando, setFalha, setDialogo } = resposta
  const client = useQueryClient()
  const lista = useQuery(pedidosOptions(situacao, pagina))
  const propostas = useQuery(propostasOptions)

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

  return <>
    <h1>Meus atendimentos</h1><p className="introducao">Acompanhe seus pedidos e confirme sua consulta quando uma vaga chegar.</p>
    <MensagensProposta resposta={resposta} />
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
    <DialogoProposta resposta={resposta} />
  </>
}
