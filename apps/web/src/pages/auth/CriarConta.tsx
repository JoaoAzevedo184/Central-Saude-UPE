import { useLayoutEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import type { FieldErrors, FieldPath, UseFormSetError } from 'react-hook-form'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { http } from '../../shared/api/http'
import { ApiError } from '../../shared/api/problem-details'
import { aplicarErrosDeValidacao } from '../../shared/api/form-errors'
import { soDigitos } from '../../shared/mascaras'
import { Botao } from '../../shared/ui/Botao'
import { Alerta } from '../../shared/ui/Alerta'
import { IndicadorEtapas } from '../../shared/ui/IndicadorEtapas'
import { LayoutAutenticacao } from './LayoutAutenticacao'
import { SeusDados, Contato, SenhasCadastro } from './EtapasCadastro'
import { TermoCadastro } from './TermoCadastro'
import { cadastroSchema, resolverZod } from './validacao'
import type { CadastroForm } from './validacao'
import { limparSessaoAnterior, termoOptions } from './api'
import type { RegistroEntrada, SessaoSaida } from './api'

const nomesEtapas = ['Seus dados', 'Contato', 'Senha e termo'] as const
const camposEtapas: FieldPath<CadastroForm>[][] = [
  ['nome', 'cpf', 'cns', 'data_nascimento', 'sexo'],
  ['municipio', 'telefone', 'email'],
  ['senha', 'confirmar_senha', 'aceite_termo', 'aceite_lembrete_email'],
]
const campos = camposEtapas.flat()

export function CriarConta() {
  const [etapa, setEtapa] = useState(0)
  const [falha, setFalha] = useState<{ mensagem: string; conflito?: boolean }>()
  const alvoFoco = useRef<FieldPath<CadastroForm> | null>(null)
  const tituloEtapa = useRef<HTMLHeadingElement>(null)
  const mudarFocoTitulo = useRef(false)
  const client = useQueryClient()
  const navigate = useNavigate()
  const termo = useQuery(termoOptions)
  const formulario = useForm<CadastroForm>({ resolver: resolverZod(cadastroSchema), shouldUnregister: false,
    defaultValues: { nome: '', cpf: '', cns: '', data_nascimento: '', sexo: '', municipio: '', telefone: '', email: '',
      senha: '', confirmar_senha: '', aceite_termo: false, aceite_lembrete_email: false },
  })
  const { handleSubmit, trigger, setFocus, setError, setValue, getValues, formState: { errors, isSubmitting } } = formulario

  useLayoutEffect(() => {
    if (alvoFoco.current) { setFocus(alvoFoco.current); alvoFoco.current = null }
    else if (mudarFocoTitulo.current) { tituloEtapa.current?.focus(); mudarFocoTitulo.current = false }
  })

  function irParaErro(erros: FieldErrors<CadastroForm>) {
    const campo = campos.find((nome) => erros[nome])
    if (campo) {
      alvoFoco.current = campo
      setEtapa(camposEtapas.findIndex((lista) => lista.includes(campo)))
    }
  }

  async function continuar() {
    setFalha(undefined)
    if (await trigger(camposEtapas[etapa], { shouldFocus: true })) {
      if (!getValues('email').trim()) setValue('aceite_lembrete_email', false)
      mudarFocoTitulo.current = true
      setEtapa(etapa + 1)
    }
  }

  async function enviarDados(dados: CadastroForm) {
    setFalha(undefined)
    if (!termo.data || termo.isError) {
      setFalha({ mensagem: 'Carregue o termo e aceite para continuar.' })
      return
    }
    const payload: RegistroEntrada = {
      nome: dados.nome, cpf: soDigitos(dados.cpf), cns: soDigitos(dados.cns), data_nascimento: dados.data_nascimento,
      sexo: dados.sexo || null, municipio: dados.municipio, telefone: soDigitos(dados.telefone), email: dados.email || null,
      senha: dados.senha, aceite_termo: true, versao_termo: termo.data.versao,
      aceite_lembrete_email: Boolean(dados.email) && dados.aceite_lembrete_email,
    }
    try {
      await http.request<SessaoSaida>('/auth/registro', { method: 'POST', body: payload })
      if (!await limparSessaoAnterior(client)) return
      await navigate('/paciente', { replace: true, state: { mensagem: 'Conta criada.' } })
    } catch (error) {
      let primeiro: FieldPath<CadastroForm> | undefined
      const aplicar: UseFormSetError<CadastroForm> = (nome, erro, opcoes) => {
        setError(nome, erro, opcoes)
        if (!primeiro && campos.includes(nome as FieldPath<CadastroForm>)) primeiro = nome as FieldPath<CadastroForm>
      }
      if (aplicarErrosDeValidacao(error, aplicar, campos)) {
        if (primeiro) { alvoFoco.current = primeiro; setEtapa(camposEtapas.findIndex((lista) => lista.includes(primeiro!))) }
        // Uma versão recusada exige carregar o termo atual e um novo aceite.
        if (error instanceof ApiError && Array.isArray(error.problem.errors) && error.problem.errors.some((item: unknown) =>
          Boolean(item && typeof item === 'object' && 'loc' in item && Array.isArray(item.loc) && item.loc[0] === 'body' && item.loc[1] === 'versao_termo'))) {
          setValue('aceite_termo', false)
          void termo.refetch()
          setFalha({ mensagem: 'O termo foi atualizado. Leia e aceite o termo atual para continuar.' })
        }
        return
      }
      setFalha({ mensagem: error instanceof ApiError ? error.message : 'Não foi possível conectar. Confira sua internet e tente de novo.',
        conflito: error instanceof ApiError && error.problem.status === 409 && error.problem.type === '/problemas/cadastro-nao-concluido' })
    }
  }

  const erroNaEtapa = camposEtapas[etapa]?.some((campo) => errors[campo])
  return <LayoutAutenticacao cadastro>
    <h1>Criar conta</h1><p className="introducao">Preencha seus dados para acompanhar seus atendimentos.</p>
    <IndicadorEtapas etapa={etapa} nomes={nomesEtapas} />
    <form noValidate onSubmit={(event) => { if (etapa < 2) { event.preventDefault(); void continuar() } else void handleSubmit(enviarDados, irParaErro)(event) }}>
      <h2 className="titulo-etapa" ref={tituloEtapa} tabIndex={-1}>{nomesEtapas[etapa]}</h2>
      {(falha || errors.root?.server || erroNaEtapa) && <Alerta>{falha?.mensagem ?? errors.root?.server?.message ?? 'Confira os campos indicados.'}
        {falha?.conflito && <Link to="/entrar">Entrar com seu CPF</Link>}
      </Alerta>}
      <fieldset className="campos-etapa" disabled={isSubmitting}>
        <legend className="sr-only">{nomesEtapas[etapa]}</legend>
        {etapa === 0 && <SeusDados formulario={formulario} />}
        {etapa === 1 && <Contato formulario={formulario} />}
        {etapa === 2 && <><SenhasCadastro formulario={formulario} /><TermoCadastro termo={termo} formulario={formulario} temEmail={Boolean(getValues('email').trim())} /></>}
      </fieldset>
      <div className="acoes-etapa">
        {etapa > 0 && <Botao type="button" variante="secundario" disabled={isSubmitting} onClick={() => {
          mudarFocoTitulo.current = true; setFalha(undefined); setEtapa(etapa - 1)
        }}>Voltar</Botao>}
        <Botao type="submit" carregando={isSubmitting} disabled={etapa === 2 && (!termo.data || termo.isError)}>{etapa < 2 ? 'Continuar' : 'Criar conta'}</Botao>
      </div>
    </form>
    <p className="voltar-entrar">Já tem conta? <Link to="/entrar">Entrar</Link></p>
  </LayoutAutenticacao>
}
