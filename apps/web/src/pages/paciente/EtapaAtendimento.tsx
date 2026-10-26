import { useId } from 'react'
import type { UseFormReturn } from 'react-hook-form'
import { Botao } from '../../shared/ui/Botao'
import { Cartao } from '../../shared/ui/Cartao'
import type { Fila } from './api'
import type { FormularioSolicitacao } from './formulario-solicitacao'

export function EtapaAtendimento({ filas, formulario, aoEscolher }: {
  filas: Fila[]; formulario: UseFormReturn<FormularioSolicitacao>; aoEscolher: (id: string) => void
}) {
  const id = useId()
  const erro = formulario.formState.errors.fila_id?.message
  return <fieldset className="campos-etapa" aria-describedby={erro ? `${id}-erro` : undefined}>
    <legend>Qual atendimento você procura?</legend>
    {erro && <p className="campo-erro" id={`${id}-erro`}>{erro}</p>}
    <div className="opcoes-atendimento">{filas.map((fila) => <Cartao key={fila.id} className="opcao-atendimento" aria-labelledby={`${id}-${fila.id}-nome`}>
      {fila.elegivel ? <label className="opcao" htmlFor={`${id}-${fila.id}`}>
        <input type="radio" id={`${id}-${fila.id}`} value={fila.id}
          {...formulario.register('fila_id', { required: 'Escolha um atendimento.' })}
          onChange={() => aoEscolher(fila.id)} aria-invalid={Boolean(erro)}
          aria-describedby={`${id}-${fila.id}-descricao`} />
        <strong id={`${id}-${fila.id}-nome`}>{fila.nome}</strong>
      </label> : <h3 id={`${id}-${fila.id}-nome`}>{fila.nome}</h3>}
      <p>{fila.especialidade.nome}</p>
      <p>{fila.unidade.nome} ({fila.unidade.sigla})</p>
      <p id={`${id}-${fila.id}-descricao`}>{fila.descricao_paciente}</p>
      {!fila.elegivel && <p className="atendimento-indisponivel" tabIndex={0} aria-describedby={`${id}-${fila.id}-nome`}>
        <strong>Indisponível para você.</strong> {fila.motivo_inelegivel ?? 'Este atendimento não está disponível para seu cadastro.'}
      </p>}
    </Cartao>)}</div>
  </fieldset>
}

export function CarregarMaisAtendimentos({ carregando, aoCarregar }: { carregando: boolean; aoCarregar: () => void }) {
  return <Botao type="button" variante="secundario" carregando={carregando} onClick={aoCarregar}>Carregar mais</Botao>
}
