import { QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { delay, http as mockHttp, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import documentos from '../../test/fixtures/documentos-sinteticos.json'
import { http } from '../../shared/api/http'
import type { components } from '../../shared/api/generated/schema'

const sessao = { id: '00000000-0000-4000-8000-000000000001', papel: 'PACIENTE', nome: 'Pessoa Sintética', filas: null } satisfies components['schemas']['EuSaida']
const sucesso = { papel: 'PACIENTE', expira_em: '2026-10-21T12:00:00-03:00' } satisfies components['schemas']['LoginSaida']
const termo = { versao: 'teste-v7', texto: '# Termo sintético\n\nTexto completo do termo de teste.\n\nSua escolha sobre lembretes é opcional.' }
const servidor = setupServer(
  mockHttp.get('*/api/v1/equipe/filas', () => HttpResponse.json({ total: 0, itens: [] })),
  mockHttp.get('*/api/v1/solicitacoes', () => HttpResponse.json({ total: 0, itens: [] })),
  mockHttp.get('*/api/v1/avisos/contagem', () => HttpResponse.json({ nao_lidos: 0 })),
  mockHttp.get('*/api/v1/me', () => HttpResponse.json(sessao)),
  mockHttp.post('*/api/v1/auth/login', () => HttpResponse.json(sucesso)),
  mockHttp.post('*/api/v1/auth/registro', () => HttpResponse.json(sucesso, { status: 201 })),
  mockHttp.get('*/api/v1/termos/vigente', () => HttpResponse.json(termo)),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterEach(() => { servidor.resetHandlers(); http.iniciarSessao() })
afterAll(() => servidor.close())

function Localizacao() {
  const location = useLocation()
  return <output data-testid="localizacao">{JSON.stringify({ pathname: location.pathname, search: location.search, hash: location.hash, state: location.state })}</output>
}
function abrir(path: string, state?: unknown) {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[{ pathname: path, state }]}>
    <Rotas /><Localizacao />
  </MemoryRouter></QueryClientProvider>)
  return { ...view, user: userEvent.setup(), client }
}
function mudar(rotulo: string, valor: string) { fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } }) }
function localizacao() { return JSON.parse(screen.getByTestId('localizacao').textContent!) }
function problema(status: number, tipo: string, extras = {}) {
  return HttpResponse.json({ type: `/problemas/${tipo}`, status, title: 'Falha sintética', ...extras },
    { status, headers: { 'Content-Type': 'application/problem+json' } })
}
async function primeiraEtapa(user: ReturnType<typeof userEvent.setup>) {
  mudar('Nome completo', 'Pessoa Sintética')
  mudar('CPF', documentos.cpf)
  mudar('Cartão do SUS (CNS)', documentos.cns)
  mudar('Data de nascimento', '2000-01-01')
  await user.click(screen.getByRole('button', { name: 'Continuar' }))
  await screen.findByLabelText('Município')
}
async function segundaEtapa(user: ReturnType<typeof userEvent.setup>, email = '') {
  mudar('Município', 'Olinda')
  mudar('Telefone com DDD', '81900000000')
  mudar('E-mail (opcional)', email)
  await user.click(screen.getByRole('button', { name: 'Continuar' }))
  await screen.findByLabelText('Crie uma senha')
  await screen.findByText('Ler o termo completo')
}
async function terceiraEtapa(user: ReturnType<typeof userEvent.setup>) {
  mudar('Crie uma senha', 'Sintetica!123')
  mudar('Confirmar senha', 'Sintetica!123')
  await user.click(screen.getByLabelText('Li e aceito o termo'))
}
async function cadastrarAteTermo(email = '') {
  const view = abrir('/criar-conta')
  await primeiraEtapa(view.user)
  await segundaEtapa(view.user, email)
  return view
}

describe('ADR-003 — entrar', () => {
  it('encaminha senha temporária à troca protegida, consultando só a sessão', async () => {
    servidor.use(mockHttp.post('*/api/v1/auth/login', () => HttpResponse.json({ ...sucesso, trocar_senha: true } satisfies components['schemas']['LoginSaida'])))
    const consultar = vi.fn(() => HttpResponse.json(sessao))
    servidor.use(mockHttp.get('*/api/v1/me', consultar))
    const { user } = abrir('/entrar', { origem: '/paciente' })
    mudar('CPF ou e-mail', documentos.cpf); mudar('Senha', 'Temporaria!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('heading', { name: 'Troca de senha obrigatória' })
    expect(localizacao().pathname).toBe('/trocar-senha')
    expect(http.trocaDeSenhaObrigatoria()).toBe(true)
    expect(consultar).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('Senha atual')).toBeTruthy()
    expect(screen.queryByRole('main', { name: 'Área do paciente' })).toBeNull()
  })
  it.each([undefined, null])('envia CPF sem máscara e senha sem alterações; login normal com trocar_senha %s', async (trocarSenha) => {
    let recebido: unknown
    servidor.use(mockHttp.post('*/api/v1/auth/login', async ({ request }) => {
      recebido = await request.json()
      return HttpResponse.json({ ...sucesso, ...(trocarSenha === undefined ? {} : { trocar_senha: trocarSenha }) } satisfies components['schemas']['LoginSaida'])
    }))
    const { user } = abrir('/entrar')
    mudar('CPF ou e-mail', documentos.cpf)
    expect((screen.getByLabelText('CPF ou e-mail') as HTMLInputElement).value).toContain('.')
    mudar('Senha', ' Sintetica!123 ')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(recebido).toEqual({ identificador: documentos.cpf, senha: ' Sintetica!123 ' })
    expect(localizacao().pathname).toBe('/paciente')
    expect(http.trocaDeSenhaObrigatoria()).toBe(false)
  })
  it.each(['ATENDENTE', 'GESTOR', 'ADMIN'])('redireciona %s para equipe', async (papel) => {
    servidor.use(mockHttp.post('*/api/v1/auth/login', () => HttpResponse.json({ ...sucesso, papel })))
    servidor.use(mockHttp.get('*/api/v1/me', () => HttpResponse.json({ ...sessao, papel, nome: null, filas: [] })))
    const { user } = abrir('/entrar')
    mudar('CPF ou e-mail', 'equipe@exemplo.test'); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('main', { name: 'Área da equipe' })
    expect(localizacao().pathname).toBe('/equipe/fila')
  })
  it.each(['2026@exemplo.test', '1234.5@exemplo.test', '123456789012345@exemplo.test'])('preserva e-mail com início numérico durante a digitação: %s', async (email) => {
    let recebido: unknown
    servidor.use(mockHttp.post('*/api/v1/auth/login', async ({ request }) => { recebido = await request.json(); return HttpResponse.json(sucesso) }))
    const { user } = abrir('/entrar')
    await user.type(screen.getByLabelText('CPF ou e-mail'), email)
    expect((screen.getByLabelText('CPF ou e-mail') as HTMLInputElement).value).toBe(email)
    mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(recebido).toEqual({ identificador: email, senha: 'Sintetica!123' })
  })
  it('volta para a origem interna do próprio papel', async () => {
    const { user } = abrir('/entrar', { origem: '/paciente' })
    mudar('CPF ou e-mail', documentos.cpf); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(localizacao().pathname).toBe('/paciente')
  })
  it('retorna ao detalhe da equipe após login, mesmo com a home em /equipe/fila', async () => {
    servidor.use(mockHttp.post('*/api/v1/auth/login', () => HttpResponse.json({ ...sucesso, papel: 'GESTOR' })),
      mockHttp.get('*/api/v1/me', () => HttpResponse.json({ ...sessao, papel: 'GESTOR', nome: null, filas: [] })))
    const { user } = abrir('/entrar', { origem: '/equipe/solicitacoes/00000000-0000-4000-8000-000000000010' })
    mudar('CPF ou e-mail', 'gestor.sintetico@exemplo.test'); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('heading', { name: 'Detalhe do pedido' })
    expect(localizacao().pathname).toBe('/equipe/solicitacoes/00000000-0000-4000-8000-000000000010')
  })
  it('origem de outra área cai na home do papel, sem "Acesso não permitido"', async () => {
    const { user } = abrir('/entrar', { origem: '/equipe' })
    mudar('CPF ou e-mail', documentos.cpf); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(localizacao().pathname).toBe('/paciente')
    expect(screen.queryByText('Acesso não permitido')).toBeNull()
  })
  it.each(['https://externo.example', '//externo.example', '/\\externo.example', '/entrar'])('recusa origem insegura: %s', async (origem) => {
    const { user } = abrir('/entrar', { origem })
    mudar('CPF ou e-mail', documentos.cpf); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(localizacao().pathname).toBe('/paciente')
  })
  it.each([
    [401, 'credenciais-invalidas', 'CPF/e-mail ou senha incorretos.'],
    [429, 'muitas-tentativas', 'Muitas tentativas. Aguarde alguns minutos e tente de novo.'],
  ])('mostra erro genérico em alerta no %s', async (status, tipo, mensagem) => {
    servidor.use(mockHttp.post('*/api/v1/auth/login', () => problema(status, tipo, { detail: 'Dado interno que não pode aparecer' })))
    const { user } = abrir('/entrar')
    mudar('CPF ou e-mail', documentos.cpf); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    expect((await screen.findByRole('alert')).textContent).toBe(mensagem)
    expect(screen.queryByText('Dado interno que não pode aparecer')).toBeNull()
  })
  it('permite repetir uma falha de rede e desabilita durante envio', async () => {
    servidor.use(mockHttp.post('*/api/v1/auth/login', () => HttpResponse.error()))
    const { user } = abrir('/entrar')
    mudar('CPF ou e-mail', documentos.cpf); mudar('Senha', 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('button', { name: 'Tentar de novo' })
    servidor.use(mockHttp.post('*/api/v1/auth/login', async () => { await delay(150); return HttpResponse.json(sucesso) }))
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect((screen.getByRole('button', { name: 'Aguarde…' }) as HTMLButtonElement).disabled).toBe(true)
    await screen.findByRole('main', { name: 'Área do paciente' })
  })
  it('tem rótulos, foco no primeiro erro e botão acessível para mostrar senha', async () => {
    const { user, container } = abrir('/entrar')
    expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(document.activeElement).toBe(screen.getByLabelText('CPF ou e-mail'))
    expect(screen.getByLabelText('CPF ou e-mail').getAttribute('aria-describedby')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Mostrar senha' }))
    expect((screen.getByLabelText('Senha') as HTMLInputElement).type).toBe('text')
    expect(screen.getByRole('button', { name: 'Ocultar senha' }).getAttribute('aria-pressed')).toBe('true')
  })
})

describe('UC-001 — criar conta', () => {
  it('não avança com erros; valida CPF e CNS e foca o primeiro campo', async () => {
    const { user } = abrir('/criar-conta')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(document.activeElement).toBe(screen.getByLabelText('Nome completo'))
    expect(screen.getByText('Confira os 11 números do CPF.')).toBeTruthy()
    expect(screen.getByText('Confira os 15 números do cartão do SUS.')).toBeTruthy()
    expect(screen.queryByLabelText('Município')).toBeNull()
    mudar('Nome completo', 'Pessoa Sintética'); mudar('CPF', '11111111111'); mudar('Cartão do SUS (CNS)', '700000000000001')
    mudar('Data de nascimento', '2999-01-01')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(document.activeElement).toBe(screen.getByLabelText('CPF'))
    expect(screen.getByLabelText('Data de nascimento').getAttribute('aria-invalid')).toBe('true')
  })
  it('valida contato, senha, confirmação e aceite obrigatório nas suas etapas', async () => {
    const { user } = abrir('/criar-conta')
    await primeiraEtapa(user)
    mudar('E-mail (opcional)', 'invalido')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(document.activeElement).toBe(screen.getByLabelText('Município'))
    expect(screen.getByText('Informe o telefone com DDD, de 10 a 13 números.')).toBeTruthy()
    expect(screen.getByText('Informe um e-mail válido ou deixe em branco.')).toBeTruthy()
    await segundaEtapa(user)
    mudar('Crie uma senha', 'curta'); mudar('Confirmar senha', 'outra')
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    expect(document.activeElement).toBe(screen.getByLabelText('Crie uma senha'))
    expect(screen.getByText('As senhas precisam ser iguais.')).toBeTruthy()
    expect(screen.getByText('Leia e aceite o termo para criar sua conta.')).toBeTruthy()
  })
  it('desabilita lembretes sem e-mail, explica e desmarca se o e-mail for removido', async () => {
    const { user } = await cadastrarAteTermo('sintetica@exemplo.test')
    const lembrete = () => screen.getByLabelText('Quero receber lembretes por e-mail (opcional)') as HTMLInputElement
    expect(lembrete().disabled).toBe(false)
    await user.click(lembrete())
    await user.click(screen.getByRole('button', { name: 'Voltar' }))
    mudar('E-mail (opcional)', '')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(lembrete().disabled).toBe(true)
    expect(lembrete().checked).toBe(false)
    expect(screen.getByText('Para receber lembretes por e-mail, volte à etapa Contato e informe um e-mail.')).toBeTruthy()
  })
  it('envia versão da API, documentos sem máscara e somente os campos do contrato; sessão iniciada no 201', async () => {
    let recebido: Record<string, unknown> | undefined
    servidor.use(mockHttp.post('*/api/v1/auth/registro', async ({ request }) => { recebido = await request.json() as Record<string, unknown>; return HttpResponse.json(sucesso, { status: 201 }) }))
    const { user } = await cadastrarAteTermo()
    await user.click(screen.getByText('Ler o termo completo'))
    expect(screen.getByText((_, elemento) => elemento?.className === 'termo-texto').textContent).toBe(termo.texto)
    await terceiraEtapa(user)
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(screen.getByText('Conta criada.').getAttribute('role')).toBe('status')
    expect(recebido).toEqual({ nome: 'Pessoa Sintética', cpf: documentos.cpf, cns: documentos.cns, data_nascimento: '2000-01-01',
      sexo: null, municipio: 'Olinda', telefone: '81900000000', email: null, senha: 'Sintetica!123',
      aceite_termo: true, versao_termo: termo.versao, aceite_lembrete_email: false })
  })
  it.each([['cpf', 'CPF', 1], ['telefone', 'Telefone com DDD', 2]])('leva o erro 422 de %s para etapa %s com foco', async (campo, rotulo, etapa) => {
    servidor.use(mockHttp.post('*/api/v1/auth/registro', () => problema(422, 'validacao', { errors: [{ loc: ['body', campo], msg: 'Confira este campo sintético.', type: 'value_error' }] })))
    const { user } = await cadastrarAteTermo()
    await terceiraEtapa(user)
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    await screen.findByLabelText(rotulo)
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText(rotulo)))
    expect(screen.getByText(new RegExp(`Etapa ${etapa} de 3`))).toBeTruthy()
    expect(screen.getByText('Confira este campo sintético.')).toBeTruthy()
  })
  it('mantém o sucesso do registro se /me falhar, sem permitir outro POST de cadastro', async () => {
    const registrar = vi.fn(() => HttpResponse.json(sucesso, { status: 201 }))
    servidor.use(mockHttp.post('*/api/v1/auth/registro', registrar), mockHttp.get('*/api/v1/me', () => problema(503, 'indisponivel')))
    const { user } = await cadastrarAteTermo()
    await terceiraEtapa(user)
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Não foi possível verificar a sessão.')
    expect(localizacao().pathname).toBe('/paciente')
    expect(screen.queryByRole('button', { name: 'Criar conta' })).toBeNull()
    expect(registrar).toHaveBeenCalledTimes(1)
  })
  it('pede novo aceite se a versão do termo for recusada pelo servidor', async () => {
    servidor.use(mockHttp.post('*/api/v1/auth/registro', () => problema(422, 'validacao', { errors: [{ loc: ['body', 'versao_termo'], msg: 'Versão não vigente.', type: 'value_error' }] })))
    const { user } = await cadastrarAteTermo()
    await terceiraEtapa(user)
    servidor.use(mockHttp.get('*/api/v1/termos/vigente', () => HttpResponse.json({ ...termo, versao: 'teste-v8' })))
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    await screen.findByText('O termo foi atualizado. Leia e aceite o termo atual para continuar.')
    expect((screen.getByLabelText('Li e aceito o termo') as HTMLInputElement).checked).toBe(false)
    await screen.findByText('teste-v8', { exact: false })
  })
  it('mostra no 409 somente mensagem genérica e link, sem revelar o campo duplicado', async () => {
    servidor.use(mockHttp.post('*/api/v1/auth/registro', () => problema(409, 'cadastro-nao-concluido', { detail: 'CNS duplicado: dado interno' })))
    const { user } = await cadastrarAteTermo()
    await terceiraEtapa(user)
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    expect((await screen.findByRole('alert')).textContent).toContain('Não foi possível concluir o cadastro. Se você já tem conta, entre com seu CPF.')
    expect(screen.queryByText(/CNS duplicado/)).toBeNull()
    expect(screen.getByRole('link', { name: 'Entrar com seu CPF' }).getAttribute('href')).toBe('/entrar')
  })
  it('mostra a mensagem pedida no 429', async () => {
    servidor.use(mockHttp.post('*/api/v1/auth/registro', () => problema(429, 'muitas-tentativas')))
    const { user } = await cadastrarAteTermo()
    await terceiraEtapa(user)
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    expect((await screen.findByRole('alert')).textContent).toBe('Muitas tentativas. Aguarde alguns minutos e tente de novo.')
  })
  it('recupera falha do termo; sem termo não aceita nem envia cadastro', async () => {
    servidor.use(mockHttp.get('*/api/v1/termos/vigente', () => HttpResponse.error()))
    const { user } = abrir('/criar-conta')
    await primeiraEtapa(user)
    mudar('Município', 'Olinda'); mudar('Telefone com DDD', '81900000000')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    await screen.findByRole('button', { name: 'Carregar termo de novo' })
    expect((screen.getByLabelText('Li e aceito o termo') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Criar conta' }) as HTMLButtonElement).disabled).toBe(true)
    servidor.use(mockHttp.get('*/api/v1/termos/vigente', () => HttpResponse.json(termo)))
    await user.click(screen.getByRole('button', { name: 'Carregar termo de novo' }))
    await screen.findByText('Ler o termo completo')
    expect((screen.getByLabelText('Li e aceito o termo') as HTMLInputElement).disabled).toBe(false)
  })
  it('não grava em localStorage/sessionStorage durante as etapas, retorno ou envio', async () => {
    const escrever = vi.spyOn(Storage.prototype, 'setItem')
    const remover = vi.spyOn(Storage.prototype, 'removeItem')
    const limpar = vi.spyOn(Storage.prototype, 'clear')
    const { user } = await cadastrarAteTermo('sintetica@exemplo.test')
    await terceiraEtapa(user)
    await user.click(screen.getByRole('button', { name: 'Voltar' }))
    expect((screen.getByLabelText('E-mail (opcional)') as HTMLInputElement).value).toBe('sintetica@exemplo.test')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    await user.click(screen.getByRole('button', { name: 'Criar conta' }))
    await screen.findByRole('main', { name: 'Área do paciente' })
    expect(escrever).not.toHaveBeenCalled(); expect(remover).not.toHaveBeenCalled(); expect(limpar).not.toHaveBeenCalled()
  })
  it('passa axe em cada etapa e no termo expandido, com rótulos nos campos', async () => {
    const { user, container } = abrir('/criar-conta')
    const conferir = async () => expect((await axe(container, { rules: { 'color-contrast': { enabled: false } } })).violations).toEqual([])
    await act(async () => { await delay(10) })
    await conferir()
    await primeiraEtapa(user); await conferir()
    await segundaEtapa(user); await user.click(screen.getByText('Ler o termo completo')); await conferir()
  })
})
