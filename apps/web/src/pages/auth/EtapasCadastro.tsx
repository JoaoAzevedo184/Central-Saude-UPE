import type { UseFormReturn } from 'react-hook-form'
import type { CadastroForm } from './validacao'
import { hojeRecife } from './validacao'
import { Campo, CampoComMascara, CampoSenha } from '../../shared/ui/Campo'
import { mascaraCns, mascaraCpf, mascaraTelefone } from '../../shared/mascaras'

type Props = { formulario: UseFormReturn<CadastroForm> }

export function SeusDados({ formulario: { register, formState: { errors } } }: Props) {
  return <>
    <Campo rotulo="Nome completo" autoComplete="name" maxLength={200} {...register('nome')} erro={errors.nome?.message} />
    <CampoComMascara rotulo="CPF" inputMode="numeric" mascara={mascaraCpf} {...register('cpf')} erro={errors.cpf?.message} />
    <CampoComMascara rotulo="Cartão do SUS (CNS)" inputMode="numeric" mascara={mascaraCns} {...register('cns')} erro={errors.cns?.message} />
    <Campo rotulo="Data de nascimento" type="date" autoComplete="bday" max={hojeRecife()} {...register('data_nascimento')} erro={errors.data_nascimento?.message} />
    <fieldset className="sexo" aria-describedby={`sexo-ajuda${errors.sexo ? ' sexo-erro' : ''}`}><legend>Sexo (opcional)</legend>
      <p id="sexo-ajuda" className="campo-ajuda">Usado só para mostrar as filas em que você pode entrar.</p>
      {[['', 'Não informar'], ['FEMININO', 'Feminino'], ['MASCULINO', 'Masculino']].map(([valor, texto]) =>
        <label className="opcao" key={valor}><input type="radio" value={valor} {...register('sexo')}
          aria-invalid={errors.sexo ? true : undefined} aria-describedby={errors.sexo ? 'sexo-ajuda sexo-erro' : 'sexo-ajuda'} />{texto}</label>)}
      {errors.sexo && <p className="campo-erro" id="sexo-erro">{errors.sexo.message}</p>}
    </fieldset>
  </>
}

export function Contato({ formulario: { register, formState: { errors } } }: Props) {
  return <>
    <Campo rotulo="Município" autoComplete="address-level2" maxLength={100} {...register('municipio')} erro={errors.municipio?.message} />
    <CampoComMascara rotulo="Telefone com DDD" type="tel" inputMode="numeric" autoComplete="tel" mascara={mascaraTelefone}
      {...register('telefone')} erro={errors.telefone?.message} />
    <Campo rotulo="E-mail (opcional)" type="email" autoComplete="email" maxLength={254} autoCapitalize="none" spellCheck={false}
      ajuda="Sem e-mail, os avisos aparecem só no site." {...register('email')} erro={errors.email?.message} />
  </>
}

export function SenhasCadastro({ formulario: { register, formState: { errors } } }: Props) {
  return <>
    <CampoSenha rotulo="Crie uma senha" autoComplete="new-password" maxLength={256} ajuda="Use pelo menos 10 caracteres."
      {...register('senha')} erro={errors.senha?.message} />
    <CampoSenha rotulo="Confirmar senha" autoComplete="new-password" maxLength={256}
      {...register('confirmar_senha')} erro={errors.confirmar_senha?.message} />
  </>
}
