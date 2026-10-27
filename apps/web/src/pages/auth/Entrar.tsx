import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { aplicarErrosDeValidacao } from '../../shared/api/form-errors'
import { rotaAposLogin, rotaInicial } from '../../shared/auth/retorno'
import { soDigitos } from '../../shared/mascaras'
import { CampoSenha } from '../../shared/ui/Campo'
import { CampoIdentificador } from '../../shared/ui/CampoIdentificador'
import { papelSchema } from '../../shared/auth/session'
import { exigeTrocaDeSenha, rotaTrocarSenha } from '../../shared/auth/troca-de-senha'
import { Botao } from '../../shared/ui/Botao'
import { Alerta } from '../../shared/ui/Alerta'
import { LayoutAutenticacao } from './LayoutAutenticacao'
import { loginSchema, resolverZod } from './validacao'
import type { LoginForm } from './validacao'
import { limparSessaoAnterior } from './api'
import type { LoginSaida } from './api'

export function Entrar() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const [falha, setFalha] = useState<{ mensagem: string; rede: boolean }>()
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<LoginForm>({
    resolver: resolverZod(loginSchema), defaultValues: { identificador: '', senha: '' },
  })

  const enviar = handleSubmit(async (dados) => {
    setFalha(undefined)
    try {
      const sessao = await http.request<LoginSaida>('/auth/login', { method: 'POST', body: {
        identificador: /^[\d.\-\s]+$/.test(dados.identificador) ? soDigitos(dados.identificador) : dados.identificador,
        senha: dados.senha,
      } })
      const papel = papelSchema.parse(sessao.papel)
      if (!await limparSessaoAnterior(client)) return
      if (exigeTrocaDeSenha(sessao)) {
        await navigate(rotaTrocarSenha, { replace: true })
        return
      }
      const home = rotaInicial(papel)
      const origem = rotaAposLogin(location.state)
      // Origem de outra área (ex.: paciente com /equipe) cai na home do papel, sem "Acesso não permitido".
      const daMinhaArea = origem === home || origem.startsWith(`${home}/`)
      await navigate(daMinhaArea ? origem : home, { replace: true })
    } catch (error) {
      if (aplicarErrosDeValidacao(error, setError, ['identificador', 'senha'])) return
      setFalha({ mensagem: error instanceof ApiError ? error.message : 'Não foi possível conectar. Confira sua internet e tente de novo.', rede: !(error instanceof ApiError) })
    }
  })

  return <LayoutAutenticacao>
    <h1>Entrar</h1>
    <p className="introducao">Use seu CPF ou o e-mail da equipe.</p>
    <form noValidate onSubmit={enviar}>
      {(falha || errors.root?.server || Object.keys(errors).some((key) => key !== 'root')) && <Alerta>
        {falha?.mensagem ?? errors.root?.server?.message ?? 'Confira os campos indicados.'}
        {falha?.rede && <Botao type="submit" variante="secundario" carregando={isSubmitting}>Tentar de novo</Botao>}
      </Alerta>}
      <CampoIdentificador rotulo="CPF ou e-mail" autoComplete="username" maxLength={254} autoCapitalize="none" spellCheck={false}
        {...register('identificador')} erro={errors.identificador?.message} />
      <CampoSenha rotulo="Senha" autoComplete="current-password" maxLength={256} {...register('senha')} erro={errors.senha?.message} />
      {/* TODO(api): adicionar recuperação de senha quando houver endpoint e rota de página. */}
      <Botao type="submit" carregando={isSubmitting}>Entrar</Botao>
    </form>
    <div className="primeiro-acesso"><p>Primeiro acesso?</p><Link className="botao botao-secundario" to="/criar-conta">Criar conta</Link></div>
  </LayoutAutenticacao>
}
