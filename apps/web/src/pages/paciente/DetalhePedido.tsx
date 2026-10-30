import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import type { components } from '../../shared/api/generated/schema'
import { ApiError } from '../../shared/api/problem-details'
import { formatarConsulta, formatarDataPedido } from '../../shared/datas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { LinhaDoTempo } from '../../shared/ui/LinhaDoTempo'
import { SeloStatus } from '../../shared/ui/SeloStatus'
import { CancelarPedido } from './CancelarPedido'
import { detalhePedidoOptions } from './api'
import { turnos } from './formulario-solicitacao'
import { PropostaVaga } from './PropostaVaga'
import { DialogoProposta, MensagensProposta } from './RespostaProposta'
import { useAgora } from './useAgora'
import { useProposta } from './useProposta'

const eventos: Record<components['schemas']['TipoEventoLinhaDoTempo'], string | null> = {
  CRIADA: 'Pedido recebido', ENTROU_NA_FILA: 'Pedido analisado. Aguardando vaga.', PROPOSTA_ENVIADA: 'Vaga oferecida',
  CONFIRMADA: 'Consulta confirmada', RECUSADA: 'Você informou que esta data não serve', PROPOSTA_EXPIRADA: 'Prazo para confirmar encerrado',
  FALTOU: 'Falta registrada na consulta', ATENDIDA: 'Atendimento realizado', CANCELADA: 'Pedido cancelado', REENTROU_NA_FILA: 'Pedido voltou para a fila',
  CLASSIFICADA: null, RECLASSIFICADA: null,
}

export function DetalhePedido() {
  const { id = '' } = useParams()
  // Trocar de pedido descarta diálogos e aborta escritas da página anterior.
  return <ConteudoDetalhe key={id} id={id} />
}

function ConteudoDetalhe({ id }: { id: string }) {
  const consulta = useQuery(detalhePedidoOptions(id))
  const [cancelando, setCancelando] = useState(false)
  const pedido = consulta.data
  const naoEncontrado = consulta.error instanceof ApiError && consulta.error.problem.status === 404
  const agendamento = pedido?.agendamento_ativo
  const agora = useAgora(agendamento?.inicio, agendamento?.expira_em)
  const resposta = useProposta(pedido ? { pedido, agora } : undefined)
  const podeCancelar = Boolean(pedido && ['EM_ANALISE', 'NA_FILA', 'EM_PROPOSTA', 'AGENDADA'].includes(pedido.status)
    && (!agendamento || new Date(agendamento.inicio).getTime() > agora))
  // Nunca usamos motivo, nem campos extras da resposta, para compor a apresentação.
  const andamento = (pedido?.linha_do_tempo ?? []).flatMap((evento) => {
    const texto = Object.hasOwn(eventos, evento.tipo) ? eventos[evento.tipo] : null
    return texto ? [{ data: evento.data, texto }] : []
  }).sort((a, b) => a.data.localeCompare(b.data))
  return <div className="detalhe-pedido">
    <Link className="voltar-pedidos" to="/paciente">‹ Meus atendimentos</Link>
    {consulta.isPending && <p role="status">Carregando seu pedido…</p>}
    {consulta.isError && (!pedido || naoEncontrado) && <>
      <h1>Detalhes do pedido</h1>
      {naoEncontrado
        ? <Alerta>Não encontramos este pedido.</Alerta>
        : <Alerta>Não foi possível carregar seu pedido.<Botao variante="secundario" carregando={consulta.isFetching}
          onClick={() => void consulta.refetch()}>Tentar de novo</Botao></Alerta>}
    </>}
    {pedido && !naoEncontrado && <>
      <header className="detalhe-topo">
        <h1>{pedido.fila.nome}</h1>
        <p>{pedido.fila.unidade.nome} ({pedido.fila.unidade.sigla})</p>
        <p className="pedido-data">Pedido em <time dateTime={pedido.data_pedido}>{formatarDataPedido(pedido.data_pedido)}</time></p>
        <SeloStatus valor={pedido.status} />
      </header>
      {consulta.isError && <Alerta>Não foi possível atualizar seu pedido.<Botao variante="secundario" carregando={consulta.isFetching}
        onClick={() => void consulta.refetch()}>Tentar de novo</Botao></Alerta>}
      <MensagensProposta resposta={resposta} />
      <section className="detalhe-situacao" aria-label="Situação do pedido">
        {pedido.status === 'EM_ANALISE' && <p>A equipe da central está analisando o seu pedido. Avisamos quando houver novidade.</p>}
        {pedido.status === 'NA_FILA' && <p>Estamos procurando uma vaga para você. Você não precisa fazer nada agora.</p>}
        {pedido.status === 'EM_PROPOSTA' && (agendamento?.status === 'PROPOSTO'
          ? <PropostaVaga pedido={pedido} agora={agora} enviando={resposta.enviando || cancelando} noDetalhe
            aoAtualizar={() => void consulta.refetch()}
            aoResponder={(acao) => { resposta.setFalha(undefined); resposta.setDialogo({ pedido, acao }) }} />
          : <p>Estamos atualizando os dados da sua vaga. Confira novamente em instantes.</p>)}
        {pedido.status === 'AGENDADA' && (agendamento?.status === 'CONFIRMADO' ? <>
          <h2>Sua consulta</h2>
          <p className="proposta-data"><time dateTime={agendamento.inicio}>{formatarConsulta(agendamento.inicio)}</time></p>
          <p>Local: {agendamento.unidade.nome} ({agendamento.unidade.sigla})</p>
          <p>{agendamento.endereco || 'Confirme o endereço com a unidade.'}</p>
          <p>Profissional: {agendamento.profissional}</p>
          <p className="lembrete">Chegue com antecedência. Tolerância de atraso: 1 hora.</p>
          <p>Leve documento com foto, cartão do SUS e o encaminhamento.</p>
        </> : <p>Estamos atualizando os dados da sua consulta. Confira novamente em instantes.</p>)}
        {pedido.status === 'ATENDIDA' && <p>Seu atendimento foi realizado.</p>}
        {pedido.status === 'CANCELADA' && <p>Seu pedido foi encerrado. Se precisar de novo, faça um novo pedido.</p>}
      </section>
      <section className="detalhe-secao" aria-labelledby="titulo-andamento">
        <h2 id="titulo-andamento">Andamento</h2>
        {andamento.length ? <LinhaDoTempo itens={andamento} /> : <p>Ainda não há atualizações para mostrar.</p>}
      </section>
      <section className="detalhe-secao" aria-labelledby="titulo-informacoes">
        <h2 id="titulo-informacoes">O que você informou</h2>
        <dl className="resumo-pedido">
          {pedido.origem_encaminhamento && <div><dt>Origem do encaminhamento</dt><dd>{pedido.origem_encaminhamento}</dd></div>}
          <div><dt>Turno preferido</dt><dd>{turnos[pedido.turno_preferido]}</dd></div>
          {pedido.respostas.filter(({ valor }) => valor !== null && valor !== undefined && valor !== '').map(({ descricao, valor }, indice) =>
            <div key={indice}><dt>{descricao}</dt><dd>{typeof valor === 'boolean' ? valor ? 'Sim' : 'Não' : String(valor)}</dd></div>)}
        </dl>
      </section>
      <CancelarPedido id={id} permitido={podeCancelar} bloqueado={resposta.enviando}
        sincronizandoRelogio={!Number.isFinite(agora)} aoEnviar={setCancelando} />
      <DialogoProposta resposta={resposta} />
    </>}
  </div>
}
