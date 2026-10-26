import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate, useOutletContext } from 'react-router'
import { TrocarSenhaLayout } from '../../layouts/TrocarSenhaLayout'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { aplicarErrosDeValidacao } from '../../shared/api/form-errors'
import { sessaoOptions, type Sessao } from '../../shared/auth/session'
import { exigeTrocaDeSenha } from '../../shared/auth/troca-de-senha'
import { useSair } from '../../shared/auth/useSair'
import { Campo } from '../../shared/ui/Campo'
import { Botao } from '../../shared/ui/Botao'
import { trocarSenha } from './api'
import { resolverZod } from './validacao'
import { mensagemErroTrocaSenha, trocaSenhaSchema, type TrocaSenhaForm } from './trocar-senha-validacao'

const valoresVazios: TrocaSenhaForm = { senha_atual: '', senha_nova: '', confirmar_senha: '' }
const verificacaoPendente = 'Sua senha foi alterada. Ainda precisamos verificar seu acesso.'

export function TrocarSenha() {
  const sessao = useOutletContext<Sessao>()
  // A mudança de identidade/época descarta o formulário anterior, não o refetch.
  return <FormularioTrocaSenha key={`${http.geracaoSessao()}:${sessao.id}`} sessao={sessao} />
}

function FormularioTrocaSenha({ sessao }: { sessao: Sessao }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const { sair, saindo } = useSair()
  const [etapa, setEtapa] = useState<'formulario' | 'verificando' | 'pendente'>('formulario')
  const [falha, setFalha] = useState<string>()
  const titulo = useRef<HTMLHeadingElement>(null)
  const alerta = useRef<HTMLDivElement>(null)
  const montado = useRef(true)
  const encerrando = useRef(false)
  const trava = useRef(false)
  const requisicao = useRef<AbortController | null>(null)
  const { register, handleSubmit, setError, clearErrors, reset, formState: { errors, isSubmitting } } = useForm<TrocaSenhaForm>({
    resolver: resolverZod(trocaSenhaSchema), defaultValues: valoresVazios,
  })
  useEffect(() => {
    montado.current = true
    titulo.current?.focus()
    return () => { montado.current = false; requisicao.current?.abort() }
  }, [])
  useEffect(() => {
    if (falha || errors.root?.server) alerta.current?.focus()
  }, [falha, errors.root?.server])

  function operacaoAtual(epoca: number, controller: AbortController) {
    return montado.current && !encerrando.current && !controller.signal.aborted
      && epoca === http.geracaoSessao()
      && client.getQueryData<Sessao | null>(sessaoOptions.queryKey)?.id === sessao.id
  }
  async function verificarAcesso(epoca: number, controller: AbortController) {
    await client.cancelQueries({ queryKey: sessaoOptions.queryKey, exact: true })
    if (!operacaoAtual(epoca, controller)) return
    const nova = await client.fetchQuery(sessaoOptions)
    if (!operacaoAtual(epoca, controller)) return
    if (!nova || nova.id !== sessao.id || exigeTrocaDeSenha(nova)) {
      throw new Error('Acesso ainda não reconciliado.')
    }
    if (!http.liberarTrocaDeSenha(epoca)) return
    await navigate(nova.papel === 'PACIENTE' ? '/paciente' : '/equipe', { replace: true })
  }
  async function enviar(dados: TrocaSenhaForm) {
    if (trava.current || encerrando.current) return
    trava.current = true
    const epoca = http.geracaoSessao()
    const controller = new AbortController()
    requisicao.current = controller
    setFalha(undefined); clearErrors()
    let alterada = false
    try {
      await trocarSenha({ senha_atual: dados.senha_atual, senha_nova: dados.senha_nova }, controller.signal)
      if (!operacaoAtual(epoca, controller)) return
      alterada = true
      reset(valoresVazios)
      setEtapa('verificando')
      await verificarAcesso(epoca, controller)
    } catch (error) {
      if (!operacaoAtual(epoca, controller)) return
      if (alterada) { setEtapa('pendente'); setFalha(verificacaoPendente) }
      else if (!aplicarErrosDeValidacao(error, setError, ['senha_atual', 'senha_nova'], mensagemErroTrocaSenha)) {
        setFalha(error instanceof ApiError ? error.message : 'Não foi possível confirmar a troca de senha. Confira sua conexão antes de tentar novamente.')
      }
    } finally { if (operacaoAtual(epoca, controller)) trava.current = false }
  }
  async function tentarVerificar() {
    if (trava.current || encerrando.current) return
    trava.current = true
    const epoca = http.geracaoSessao()
    const controller = new AbortController()
    requisicao.current = controller
    setFalha(undefined); setEtapa('verificando')
    try { await verificarAcesso(epoca, controller) }
    catch {
      if (operacaoAtual(epoca, controller)) { setEtapa('pendente'); setFalha(verificacaoPendente) }
    } finally { if (operacaoAtual(epoca, controller)) trava.current = false }
  }
  function iniciarSaida() {
    encerrando.current = true
    requisicao.current?.abort()
    reset(valoresVazios)
    // A consulta pertence à operação encerrada; não pode concluir na sessão seguinte.
    void client.cancelQueries({ queryKey: sessaoOptions.queryKey, exact: true })
    void sair()
  }

  if (etapa === 'formulario' && !exigeTrocaDeSenha(sessao) && !http.trocaDeSenhaObrigatoria()) {
    return <Navigate to={sessao.papel === 'PACIENTE' ? '/paciente' : '/equipe'} replace />
  }
  return <TrocarSenhaLayout sair={iniciarSaida} saindo={saindo}>
    <h1 ref={titulo} tabIndex={-1}>Troca de senha obrigatória</h1>
    <p className="introducao">Crie uma nova senha para continuar usando o sistema.</p>
    {(falha || errors.root?.server) && <div ref={alerta} tabIndex={-1} role="alert" className="alerta">{falha ?? errors.root?.server?.message}</div>}
    {saindo ? <p role="status">Encerrando sessão…</p> : etapa === 'formulario' ? <form noValidate onSubmit={(event) => void handleSubmit(enviar)(event)} aria-label="Trocar senha">
      <Campo rotulo="Senha atual" type="password" autoComplete="current-password" readOnly={isSubmitting} {...register('senha_atual')} erro={errors.senha_atual?.message} />
      <Campo rotulo="Nova senha" type="password" autoComplete="new-password" readOnly={isSubmitting} ajuda="Use de 10 a 256 caracteres e uma senha diferente da atual." {...register('senha_nova')} erro={errors.senha_nova?.message} />
      <Campo rotulo="Confirmar nova senha" type="password" autoComplete="new-password" readOnly={isSubmitting} {...register('confirmar_senha')} erro={errors.confirmar_senha?.message} />
      <Botao type="submit" carregando={isSubmitting}>Trocar senha</Botao>
    </form> : etapa === 'verificando' ? <p role="status">Senha alterada. Verificando seu acesso…</p>
      : <Botao type="button" onClick={() => void tentarVerificar()}>Verificar acesso novamente</Botao>}
  </TrocarSenhaLayout>
}
