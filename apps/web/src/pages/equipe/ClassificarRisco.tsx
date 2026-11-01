import { useRef } from 'react'
import type { DetalheEquipe } from './api'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'
import { Dialogo } from '../../shared/ui/Dialogo'
import { podeClassificar, riscosEquipe, useClassificarRisco } from './useClassificarRisco'

export function ClassificarRisco({ pedido, nomeFila, leituraFalhou }: { pedido: DetalheEquipe; nomeFila: string; leituraFalhou: boolean }) {
  const acao = useClassificarRisco(pedido)
  const acionador = useRef<HTMLButtonElement>(null)
  const { register, watch, formState: { errors } } = acao.form
  const reclassificando = pedido.status === 'NA_FILA'
  const motivo = watch('motivo')
  const riscoAtual = acao.confirmacao?.anterior.classificacao_risco
  return <div className="area-classificacao-equipe">
    {acao.mensagem && <p role="status" className="mensagem-sucesso">{acao.mensagem}</p>}
    {acao.erro && <Alerta>{acao.erro}</Alerta>}
    {errors.root?.server && <Alerta>{errors.root.server.message}</Alerta>}
    {podeClassificar(pedido) && <section className="bloco-detalhe-equipe" aria-labelledby="titulo-classificar">
      <h2 id="titulo-classificar">{reclassificando ? 'Reclassificar risco' : 'Classificar risco'}</h2>
      <p>{reclassificando ? 'O pedido já está na fila. Uma mudança de risco pode alterar sua prioridade.' : 'Ao classificar, o pedido entra na fila e pode receber uma vaga automaticamente.'}</p>
      <form noValidate onSubmit={(event) => { void acao.preparar(event) }}>
        <fieldset className="opcoes-risco-equipe" disabled={acao.ocupado || leituraFalhou} aria-describedby={errors.classificacao_risco ? 'risco-erro' : undefined}>
          <legend>Nível de risco</legend>
          {Object.entries(riscosEquipe).map(([valor, texto]) => <label key={valor} className={`opcao-risco-equipe risco-${texto === 'Alto' ? 'alto' : texto === 'Médio' ? 'medio' : 'baixo'}`}>
            <input type="radio" value={valor} aria-invalid={errors.classificacao_risco ? true : undefined}
              aria-describedby={errors.classificacao_risco ? 'risco-erro' : undefined} {...register('classificacao_risco', { required: 'Escolha Alto, Médio ou Baixo.' })} />{texto}
          </label>)}
        </fieldset>
        {errors.classificacao_risco && <p role="alert" className="campo-erro" id="risco-erro">{errors.classificacao_risco.message}</p>}
        <div className="campo"><label htmlFor="motivo-classificacao">Motivo</label>
          <textarea id="motivo-classificacao" rows={5} disabled={acao.ocupado || leituraFalhou}
            aria-invalid={errors.motivo ? true : undefined} aria-describedby={`motivo-ajuda${errors.motivo ? ' motivo-erro' : ''}`}
            {...register('motivo', { validate: (valor) => {
              const tamanho = Array.from(valor.trim()).length
              return tamanho >= 3 && tamanho <= 500 || 'Informe um motivo com 3 a 500 caracteres.'
            } })} />
          <div className="campo-ajuda" id="motivo-ajuda">Obrigatório, de 3 a 500 caracteres. {Array.from(motivo.trim()).length}/500</div>
          {errors.motivo && <p role="alert" className="campo-erro" id="motivo-erro">{errors.motivo.message}</p>}
        </div>
        <Botao ref={acionador} type="submit" carregando={acao.ocupado} disabled={leituraFalhou}>{reclassificando ? 'Reclassificar' : 'Classificar'}</Botao>
      </form>
    </section>}
    {acao.confirmacao && <Dialogo titulo={reclassificando ? 'Confirmar reclassificação' : 'Confirmar classificação'} aoFechar={acao.fechar} retornarFoco={acionador}>
      <p>{acao.confirmacao.anterior.status === 'NA_FILA'
        ? <>Reclassificar {riscoAtual ? <>de <strong>{riscosEquipe[riscoAtual]}</strong> </> : ''}para <strong>{riscosEquipe[acao.confirmacao.risco]}</strong>. A prioridade do pedido pode mudar e ele pode receber uma vaga automaticamente.</>
        : <>Classificar como <strong>{riscosEquipe[acao.confirmacao.risco]}</strong>. O pedido entra na fila de {nomeFila} e pode receber uma vaga automaticamente.</>}</p>
      <div className="acoes-dialogo"><Botao variante="secundario" data-foco-inicial onClick={acao.fechar}>Voltar</Botao>
        <Botao carregando={acao.ocupado} onClick={() => void acao.confirmar()}>Confirmar</Botao></div>
    </Dialogo>}
  </div>
}
