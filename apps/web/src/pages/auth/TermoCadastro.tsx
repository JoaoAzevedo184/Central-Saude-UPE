import type { UseFormReturn } from 'react-hook-form'
import type { UseQueryResult } from '@tanstack/react-query'
import { termoOptions } from './api'
import type { CadastroForm } from './validacao'
import { Alerta } from '../../shared/ui/Alerta'
import { Botao } from '../../shared/ui/Botao'

export function TermoCadastro({ termo, formulario: { register, formState: { errors } }, temEmail }:
  { termo: UseQueryResult<Awaited<ReturnType<typeof termoOptions.queryFn>>>; formulario: UseFormReturn<CadastroForm>; temEmail: boolean }) {
  return <div className="consentimentos">
    {termo.isPending && <p role="status">Carregando o termo…</p>}
    {termo.isError && <Alerta>Não foi possível carregar o termo. Tente de novo para continuar.
      <Botao type="button" variante="secundario" onClick={() => void termo.refetch()}>Carregar termo de novo</Botao>
    </Alerta>}
    {termo.data && <details className="termo"><summary>Ler o termo completo</summary>
      <p className="campo-ajuda">Versão {termo.data.versao}</p>
      <div className="termo-texto">{termo.data.texto}</div>
    </details>}
    <label className="opcao"><input type="checkbox" {...register('aceite_termo')} disabled={!termo.data || termo.isError}
      aria-invalid={errors.aceite_termo ? true : undefined} aria-describedby={errors.aceite_termo ? 'aceite-termo-erro' : undefined} />Li e aceito o termo</label>
    {errors.aceite_termo && <p id="aceite-termo-erro" className="campo-erro">{errors.aceite_termo.message}</p>}
    <label className="opcao"><input type="checkbox" {...register('aceite_lembrete_email')} disabled={!temEmail}
      aria-describedby={['lembrete-ajuda', errors.aceite_lembrete_email && 'lembrete-erro'].filter(Boolean).join(' ')}
      aria-invalid={errors.aceite_lembrete_email ? true : undefined} />Quero receber lembretes por e-mail (opcional)</label>
    <p className="campo-ajuda" id="lembrete-ajuda">{temEmail ? 'Você pode escolher se quer receber lembretes.' : 'Para receber lembretes por e-mail, volte à etapa Contato e informe um e-mail.'}</p>
    {errors.aceite_lembrete_email && <p id="lembrete-erro" className="campo-erro">{errors.aceite_lembrete_email.message}</p>}
  </div>
}
