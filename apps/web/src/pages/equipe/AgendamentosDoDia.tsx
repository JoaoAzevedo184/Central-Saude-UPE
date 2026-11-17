import { useEffect, useId, useRef } from 'react'
import { Link } from 'react-router'
import type { Papel } from '../../shared/auth/session'
import { formatarHora } from '../../shared/datas'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import type { AgendamentoDoDia } from './api'
import { useRegistrarPresenca } from './useRegistrarPresenca'

const situacoes: Record<AgendamentoDoDia['status'], string> = {
  PROPOSTO: 'Proposta aguardando o paciente', CONFIRMADO: 'Confirmado', REALIZADO: 'Compareceu', FALTOU: 'Faltou', CANCELADO: 'Cancelado', EXPIRADO: 'Expirado',
}
function LinhaAgendamento({ item, papel, agora, aoResultado }: { item: AgendamentoDoDia; papel: Papel; agora: number; aoResultado: (mensagem: string) => void }) {
  const presenca = useRegistrarPresenca(item, aoResultado)
  const falta = useRef<HTMLButtonElement>(null)
  const confirmar = useRef<HTMLButtonElement>(null)
  const linha = useRef<HTMLTableRowElement>(null)
  const devolverFocoFalta = useRef(false)
  useEffect(() => { if (presenca.finalizacao) linha.current?.focus() }, [presenca.finalizacao])
  useEffect(() => {
    if (presenca.confirmacao) confirmar.current?.focus()
    else if (devolverFocoFalta.current) { devolverFocoFalta.current = false; falta.current?.focus() }
  }, [presenca.confirmacao])
  const descricao = useId()
  const podeRegistrar = papel === 'ATENDENTE' && item.status === 'CONFIRMADO' && !item.presenca_registrada
  const antesDoInicio = agora < Date.parse(item.inicio)
  return <tr ref={linha} tabIndex={-1}>
    <td data-rotulo="Horário"><time dateTime={item.inicio}>{formatarHora(Date.parse(item.inicio))}</time> – <time dateTime={item.fim}>{formatarHora(Date.parse(item.fim))}</time></td>
    <td data-rotulo="Profissional">{item.profissional}</td>
    <td data-rotulo="Paciente"><Link to={`/equipe/solicitacoes/${encodeURIComponent(item.solicitacao_id)}`}>{item.paciente_nome}</Link></td>
    <td data-rotulo="Situação">{situacoes[item.status]}</td>
    {papel === 'ATENDENTE' && <td data-rotulo="Presença">
      {podeRegistrar && <div className="presenca-agenda" aria-busy={presenca.ocupado}>
        {presenca.confirmacao ? <div className="confirmacao-falta" role="group" aria-labelledby={descricao}>
          <p id={descricao}>O pedido volta para o fim da fila e o paciente é avisado. Confirmar falta?</p>
          <div className="acoes-agenda"><Botao ref={confirmar} disabled={antesDoInicio} carregando={presenca.ocupado} onClick={() => presenca.registrar(false)}>Confirmar</Botao>
            <Botao variante="secundario" disabled={presenca.ocupado} onClick={() => { devolverFocoFalta.current = true; presenca.setConfirmacao(false) }}>Voltar</Botao></div>
        </div> : <div className="acoes-agenda">
          <Botao disabled={antesDoInicio || presenca.ocupado} aria-describedby={antesDoInicio ? descricao : undefined} onClick={() => presenca.registrar(true)}>Compareceu</Botao>
          <Botao ref={falta} variante="secundario" disabled={antesDoInicio || presenca.ocupado} aria-describedby={antesDoInicio ? descricao : undefined} onClick={() => presenca.setConfirmacao(true)}>Faltou</Botao>
        </div>}
        {antesDoInicio && <p className="ajuda-agenda" id={presenca.confirmacao ? undefined : descricao}>Disponível a partir de {formatarHora(Date.parse(item.inicio))}</p>}
        {presenca.ocupado && <p>Registrando presença…</p>}
      </div>}
      {presenca.erro && <Alerta><p>{presenca.erro}</p></Alerta>}
    </td>}
  </tr>
}
export function AgendamentosDoDia({ itens, papel, agora, aoResultado }: { itens: AgendamentoDoDia[]; papel: Papel; agora: number; aoResultado: (mensagem: string) => void }) {
  const ordenados = [...itens].sort((a, b) => Date.parse(a.inicio) - Date.parse(b.inicio) || a.id.localeCompare(b.id))
  return <table className="tabela-agenda">
    <caption>Agendamentos do dia</caption>
    <thead><tr>{['Horário', 'Profissional', 'Paciente', 'Situação', ...(papel === 'ATENDENTE' ? ['Presença'] : [])].map((titulo) => <th scope="col" key={titulo}>{titulo}</th>)}</tr></thead>
    <tbody>{ordenados.map((item) => <LinhaAgendamento key={item.id} item={item} papel={papel} agora={agora} aoResultado={aoResultado} />)}</tbody>
  </table>
}
