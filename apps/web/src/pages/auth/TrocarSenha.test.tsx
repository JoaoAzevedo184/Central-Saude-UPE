import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import { sessaoOptions, type Papel, type Sessao } from '../../shared/auth/session'

const conta = (papel: Papel = 'PACIENTE', trocar = true): Sessao => ({ id: '00000000-0000-4000-8000-000000000001', papel, nome: null, filas: null, ...(trocar ? { trocar_senha: true as const } : {}) })
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': status >= 400 ? 'application/problem+json' : 'application/json' } })
const problema = (status: number, type: string, extras = {}) => json({ status, type: `/problemas/${type}`, title: 'Falha sintética', ...extras }, status)
function pendente<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}
function Localizacao() { const location = useLocation(); return <span data-testid="rota">{location.pathname}:{location.key}</span> }
function abrir(papel: Papel = 'PACIENTE', trocar = true, rota = '/trocar-senha', autenticada = true) {
  let alterada = !trocar
  const transporte = vi.fn<typeof fetch>(async (url) => {
    if (url === '/api/v1/me') return autenticada ? json(conta(papel, !alterada)) : problema(401, 'nao-autenticado')
    if (url === '/api/v1/auth/refresh') return problema(401, 'nao-autenticado')
    if (url === '/api/v1/auth/trocar-senha') { alterada = true; return new Response(null, { status: 204 }) }
    if (url === '/api/v1/auth/logout') return new Response(null, { status: 204 })
    if (String(url).startsWith('/api/v1/solicitacoes')) return json({ total: 0, itens: [] })
    if (url === '/api/v1/avisos/contagem') return json({ nao_lidos: 0 })
    throw new Error('Endpoint inesperado no teste')
  })
  vi.stubGlobal('fetch', transporte)
  document.cookie = 'csrf_token=csrf-sintetico; path=/'
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[rota]}><Rotas /><Localizacao /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, transporte, user: userEvent.setup() }
}
async function preencher(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Senha atual'), 'Atual sintética')
  await user.type(screen.getByLabelText('Nova senha'), 'Nova sintética')
  await user.type(screen.getByLabelText('Confirmar nova senha'), 'Nova sintética')
}
afterEach(() => { http.iniciarSessao(); vi.unstubAllGlobals(); document.cookie = 'csrf_token=; max-age=0; path=/' })

describe('RN-022/UC-010 — Trocar senha', () => {
  it.each(['PACIENTE', 'GESTOR', 'ATENDENTE', 'ADMIN'] as const)('reconcilia /me e libera %s só depois do 204', async (papel) => {
    const { user, client, transporte } = abrir(papel)
    await preencher(user)
    const liberar = vi.spyOn(http, 'liberarTrocaDeSenha').mockImplementation((epoca) => {
      expect(epoca).toBe(http.geracaoSessao())
      expect(client.getQueryData(sessaoOptions.queryKey)).toEqual(conta(papel, false))
      return true
    })
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await waitFor(() => expect(screen.getByTestId('rota').textContent).toContain(papel === 'PACIENTE' ? '/paciente:' : '/equipe:'))
    expect(liberar).toHaveBeenCalledTimes(1)
    const chamadas = transporte.mock.calls
    const indice = chamadas.findIndex(([url]) => url === '/api/v1/auth/trocar-senha')
    expect(chamadas[indice + 1]?.[0]).toBe('/api/v1/me')
    expect(JSON.parse(String(chamadas[indice]?.[1]?.body))).toEqual({ senha_atual: 'Atual sintética', senha_nova: 'Nova sintética' })
    expect(new Headers(chamadas[indice]?.[1]?.headers).get('X-CSRF-Token')).toBe('csrf-sintetico')
  })

  it.each(['PACIENTE', 'GESTOR', 'ATENDENTE', 'ADMIN'] as const)('acesso direto sem troca vai ao início de %s', async (papel) => {
    abrir(papel, false)
    await waitFor(() => expect(screen.getByTestId('rota').textContent).toContain(papel === 'PACIENTE' ? '/paciente:' : '/equipe:'))
    expect(screen.queryByLabelText('Senha atual')).toBeNull()
  })

  it('sem sessão vai para entrar', async () => {
    abrir('PACIENTE', true, '/trocar-senha', false)
    await screen.findByRole('heading', { name: 'Entrar' })
  })

  it('B2: erro de refetch também preserva o layout do paciente', async () => {
    const { client, transporte } = abrir('PACIENTE', false, '/paciente')
    const area = await screen.findByRole('main', { name: 'Área do paciente' })
    transporte.mockRejectedValue(new TypeError('Falha sintética'))
    await act(async () => { await client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    expect(screen.getByRole('main', { name: 'Área do paciente' })).toBe(area)
  })

  it('confirmação diferente foca o campo e impede POST por teclado', async () => {
    const { user, transporte } = abrir()
    await preencher(user)
    await user.clear(screen.getByLabelText('Confirmar nova senha'))
    await user.type(screen.getByLabelText('Confirmar nova senha'), 'Diferente{Enter}')
    await screen.findByText('As senhas precisam ser iguais.')
    expect(document.activeElement).toBe(screen.getByLabelText('Confirmar nova senha'))
    expect(transporte.mock.calls.some(([url]) => url === '/api/v1/auth/trocar-senha')).toBe(false)
  })

  it('204 com /me ainda bloqueado não libera nem navega', async () => {
    const { user, transporte } = abrir()
    await preencher(user)
    transporte.mockImplementation(async (url) => url === '/api/v1/me' ? json(conta()) : new Response(null, { status: 204 }))
    const liberar = vi.spyOn(http, 'liberarTrocaDeSenha')
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByRole('button', { name: 'Verificar acesso novamente' })
    expect(liberar).not.toHaveBeenCalled()
    expect(screen.getByTestId('rota').textContent).toContain('/trocar-senha:')
  })

  it('cancela /me anterior e uma resposta antiga não restaura a flag depois do sucesso', async () => {
    const { user, transporte, client } = abrir()
    await preencher(user)
    const antigo = pendente<Response>()
    let leituraAntiga = true
    let sinal: AbortSignal | null | undefined
    transporte.mockImplementation(async (url, options) => {
      if (url === '/api/v1/me' && leituraAntiga) {
        leituraAntiga = false
        sinal = options?.signal
        return antigo.promise
      }
      if (url === '/api/v1/auth/trocar-senha') return new Response(null, { status: 204 })
      if (url === '/api/v1/me') return json(conta('PACIENTE', false))
      if (url === '/api/v1/avisos/contagem') return json({ nao_lidos: 0 })
      return json({ total: 0, itens: [] })
    })
    let revalidacao!: Promise<void>
    await act(async () => { revalidacao = client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByRole('heading', { name: 'Meus atendimentos' })
    expect(sinal?.aborted).toBe(true)
    await act(async () => { antigo.resolve(json(conta())); await revalidacao })
    expect(client.getQueryData(sessaoOptions.queryKey)).toEqual(conta('PACIENTE', false))
    expect(screen.getByTestId('rota').textContent).toContain('/paciente:')
  })

  it('nova sessão durante POST descarta valores e resposta antiga sem alterar seu cache', async () => {
    const { user, transporte, client } = abrir()
    await preencher(user)
    const antiga = pendente<Response>()
    transporte.mockImplementation(async (url) => url === '/api/v1/auth/trocar-senha' ? antiga.promise : json({ ...conta('GESTOR'), id: 'nova-identidade' }))
    const liberar = vi.spyOn(http, 'liberarTrocaDeSenha')
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await act(async () => {
      http.iniciarSessao(true)
      client.setQueryData(sessaoOptions.queryKey, (): Sessao => ({ ...conta('GESTOR'), id: 'nova-identidade' }))
    })
    await act(async () => { antiga.resolve(new Response(null, { status: 204 })) })
    expect(liberar).not.toHaveBeenCalled()
    expect(http.trocaDeSenhaObrigatoria()).toBe(true)
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ id: 'nova-identidade' })
    expect((screen.getByLabelText('Senha atual') as HTMLInputElement).value).toBe('')
    expect(screen.getByTestId('rota').textContent).toContain('/trocar-senha:')
  })

  it('rede não repete POST e mantém valores só no formulário', async () => {
    const { user, transporte } = abrir()
    await preencher(user)
    transporte.mockRejectedValue(new TypeError('Falha sintética'))
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByRole('alert')
    expect(transporte.mock.calls.filter(([url]) => url === '/api/v1/auth/trocar-senha')).toHaveLength(1)
    expect((screen.getByLabelText('Senha atual') as HTMLInputElement).value).toBe('Atual sintética')
  })

  it('logout da tela com falha também limpa sessão e vai para entrar', async () => {
    const { user, transporte, client } = abrir()
    await preencher(user)
    transporte.mockResolvedValue(new Response(null, { status: 503 }))
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    expect(client.getQueryData(sessaoOptions.queryKey)).toBeUndefined()
    expect(screen.queryByLabelText('Senha atual')).toBeNull()
  })

  it('B2: erro de refetch mantém valores e árvore conhecida', async () => {
    const { user, client, transporte } = abrir()
    await preencher(user)
    const campo = screen.getByLabelText('Senha atual')
    transporte.mockImplementation(async () => { throw new TypeError('Falha sintética') })
    await act(async () => { await client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    expect(screen.getByLabelText('Senha atual')).toBe(campo)
    expect((campo as HTMLInputElement).value).toBe('Atual sintética')
  })

  it('evento obrigatório na própria rota não navega nem perde formulário', async () => {
    const { user, transporte } = abrir()
    await preencher(user)
    const rota = screen.getByTestId('rota').textContent
    const campo = screen.getByLabelText('Senha atual')
    transporte.mockResolvedValue(problema(403, 'troca-de-senha-obrigatoria'))
    await act(async () => { await http.request('/recurso').catch(() => undefined) })
    expect(screen.getByTestId('rota').textContent).toBe(rota)
    expect(screen.getByLabelText('Senha atual')).toBe(campo)
    expect((campo as HTMLInputElement).value).toBe('Atual sintética')
  })

  it('422 atual incorreta foca o campo sem refresh nem exposição de detail', async () => {
    const { user, transporte } = abrir()
    await preencher(user)
    transporte.mockImplementation(async () => problema(422, 'invalido', { detail: 'NÃO EXIBIR', errors: [{ loc: ['body', 'senha_atual'], msg: 'TEXTO BRUTO NÃO EXIBIR', type: 'value_error' }] }))
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByText('Senha atual incorreta.')
    expect(document.activeElement).toBe(screen.getByLabelText('Senha atual'))
    expect(transporte.mock.calls.some(([url]) => url === '/api/v1/auth/refresh')).toBe(false)
    expect(screen.queryByText('NÃO EXIBIR')).toBeNull()
    expect(screen.queryByText('TEXTO BRUTO NÃO EXIBIR')).toBeNull()
  })

  it.each([
    ['curta', 'curta', 'A nova senha precisa ter pelo menos 10 caracteres.'],
    ['igual', 'Atual sintética', 'A nova senha precisa ser diferente da senha atual.'],
  ])('nova senha %s é recusada localmente, com foco e sem POST', async (_caso, senha, mensagem) => {
    const { user, transporte } = abrir()
    await preencher(user)
    await user.clear(screen.getByLabelText('Nova senha'))
    await user.type(screen.getByLabelText('Nova senha'), senha!)
    await user.clear(screen.getByLabelText('Confirmar nova senha'))
    await user.type(screen.getByLabelText('Confirmar nova senha'), senha!)
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByText(mensagem!)
    expect(document.activeElement).toBe(screen.getByLabelText('Nova senha'))
    expect(transporte.mock.calls.some(([url]) => url === '/api/v1/auth/trocar-senha')).toBe(false)
  })

  it.each([
    ['too_short', 'Value should have at least 10 items after validation, not 5', 'A nova senha precisa ter pelo menos 10 caracteres.'],
    ['value_error', 'Mensagem bruta com payload que não deve aparecer', 'A nova senha precisa ser diferente da senha atual.'],
  ])('422 senha_nova (%s) usa mensagem local, foca campo e não renova', async (type, msg, mensagem) => {
    const { user, transporte, container } = abrir()
    await preencher(user)
    transporte.mockResolvedValue(problema(422, 'invalido', { detail: 'DETAIL NÃO EXIBIR', errors: [{ loc: ['body', 'senha_nova'], msg, type }] }))
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByText(mensagem!)
    expect(document.activeElement).toBe(screen.getByLabelText('Nova senha'))
    expect(screen.getByLabelText('Nova senha').getAttribute('aria-invalid')).toBe('true')
    expect(screen.queryByText(msg!)).toBeNull()
    expect(screen.queryByText('DETAIL NÃO EXIBIR')).toBeNull()
    expect(transporte.mock.calls.filter(([url]) => url === '/api/v1/auth/trocar-senha')).toHaveLength(1)
    expect(transporte.mock.calls.some(([url]) => url === '/api/v1/auth/refresh')).toBe(false)
    expect(await axe(container)).toMatchObject({ violations: [] })
  })

  it.each([
    { loc: ['body', 'senha_nova'], type: 'codigo_desconhecido' },
    { loc: ['body', 'confirmar_senha'], type: 'value_error' },
  ])('422 não mapeável recebe erro global seguro', async (erro) => {
    const { user, transporte } = abrir()
    await preencher(user)
    transporte.mockResolvedValue(problema(422, 'invalido', { detail: 'DETAIL NÃO EXIBIR', errors: [{ ...erro, msg: 'MSG NÃO EXIBIR' }] }))
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    const alerta = await screen.findByRole('alert')
    expect(alerta.textContent).toBe('Confira os campos indicados e tente novamente.')
    await waitFor(() => expect(document.activeElement).toBe(alerta))
    expect(screen.queryByText('DETAIL NÃO EXIBIR')).toBeNull()
    expect(screen.queryByText('MSG NÃO EXIBIR')).toBeNull()
  })

  it.each([[429, 'muitas-tentativas'], [403, 'csrf-invalido'], [422, 'invalido']] as const)('erro global %s recebe foco e não renova', async (status, type) => {
    const { user, transporte } = abrir()
    await preencher(user)
    transporte.mockResolvedValue(problema(status, type, { detail: 'NÃO EXIBIR' }))
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    const alerta = await screen.findByRole('alert')
    await waitFor(() => expect(document.activeElement).toBe(alerta))
    expect(alerta.textContent).not.toContain('NÃO EXIBIR')
    expect(transporte.mock.calls.some(([url]) => url === '/api/v1/auth/refresh')).toBe(false)
  })

  it('204 seguido de falha de /me oferece só verificar, sem repetir troca', async () => {
    const { user, transporte } = abrir()
    await preencher(user)
    transporte.mockImplementation(async (url) => {
      if (url === '/api/v1/auth/trocar-senha') return new Response(null, { status: 204 })
      throw new TypeError('Falha sintética')
    })
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByText('Sua senha foi alterada. Ainda precisamos verificar seu acesso.')
    expect(screen.queryByLabelText('Senha atual')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Trocar senha' })).toBeNull()
    transporte.mockResolvedValue(json(conta('PACIENTE', false)))
    await user.click(screen.getByRole('button', { name: 'Verificar acesso novamente' }))
    await screen.findByRole('heading', { name: 'Meus atendimentos' })
    expect(transporte.mock.calls.filter(([url]) => url === '/api/v1/auth/trocar-senha')).toHaveLength(1)
  })

  it.each(['POST', 'me'] as const)('logout durante %s ignora conclusão antiga e preserva trava da nova geração', async (etapa) => {
    const { user, transporte, client } = abrir()
    await preencher(user)
    const antiga = pendente<Response>()
    const nova = pendente<Response>()
    transporte.mockImplementation(async (url) => {
      if (url === '/api/v1/auth/logout') return new Response(null, { status: 204 })
      if (url === '/api/v1/auth/trocar-senha') return etapa === 'POST' ? antiga.promise : new Response(null, { status: 204 })
      if (url === '/api/v1/me') return antiga.promise
      return nova.promise
    })
    const liberar = vi.spyOn(http, 'liberarTrocaDeSenha')
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await waitFor(() => expect(transporte.mock.calls.filter(([url]) => url === '/api/v1/me').length).toBe(etapa === 'me' ? 2 : 1))
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    http.iniciarSessao(true)
    client.setQueryData(sessaoOptions.queryKey, (): Sessao => ({ ...conta('GESTOR'), id: 'outra-conta-sintetica' }))
    await act(async () => { antiga.resolve(etapa === 'POST' ? new Response(null, { status: 204 }) : json(conta('PACIENTE', false))) })
    expect(liberar).not.toHaveBeenCalled()
    expect(http.trocaDeSenhaObrigatoria()).toBe(true)
    expect(client.getQueryData(sessaoOptions.queryKey)).toMatchObject({ id: 'outra-conta-sintetica' })
    expect(screen.getByTestId('rota').textContent).toContain('/entrar:')
  })

  it('formulário acessível, sem chamadas bloqueadas nem armazenamento', async () => {
    const gravar = vi.spyOn(Storage.prototype, 'setItem')
    const log = vi.spyOn(console, 'log')
    const { container, user, client, transporte } = abrir()
    await preencher(user)
    expect((screen.getByLabelText('Senha atual') as HTMLInputElement).autocomplete).toBe('current-password')
    expect((screen.getByLabelText('Nova senha') as HTMLInputElement).autocomplete).toBe('new-password')
    expect((screen.getByLabelText('Confirmar nova senha') as HTMLInputElement).autocomplete).toBe('new-password')
    expect(await axe(container)).toMatchObject({ violations: [] })
    expect(transporte.mock.calls.map(([url]) => url)).toEqual(['/api/v1/me'])
    await user.click(screen.getByRole('button', { name: 'Trocar senha' }))
    await screen.findByRole('heading', { name: 'Meus atendimentos' })
    expect(gravar).not.toHaveBeenCalled()
    expect(log).not.toHaveBeenCalled()
    expect(JSON.stringify(client.getQueryCache().getAll().map((q) => q.state.data))).not.toContain('sintética')
    expect(client.getMutationCache().getAll()).toHaveLength(0)
    expect(screen.getByTestId('rota').textContent).not.toContain('sintética')
  })
})
