import { QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as msw, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import { sessaoOptions } from '../../shared/auth/session'
import { pedidosKey, type DetalheFila, type DetalhePedido, type Fila, type NovoPedido } from './api'

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const filaA: Fila = { id: uuid(1), nome: 'Atendimento sintético A', descricao_paciente: 'Descrição sintética do atendimento A.',
  especialidade: { id: uuid(11), nome: 'Especialidade sintética' }, unidade: { id: uuid(12), nome: 'Hospital Sintético', sigla: 'HS' }, elegivel: true, motivo_inelegivel: null }
const filaB: Fila = { ...filaA, id: uuid(2), nome: 'Atendimento sintético B' }
const inelegivel: Fila = { ...filaA, id: uuid(3), nome: 'Atendimento indisponível', elegivel: false, motivo_inelegivel: 'Seu cadastro não atende às condições deste atendimento.' }
const detalheA: DetalheFila = { ...filaA, criterios: [
  { id: uuid(20), codigo: 'OPCIONAL', descricao: 'Pergunta sem resposta', tipo: 'SIM_NAO', opcoes: null },
  { id: uuid(21), codigo: 'BOOLEANO', descricao: 'Pergunta de sim ou não', tipo: 'SIM_NAO', opcoes: null },
  { id: uuid(22), codigo: 'NUMERICO', descricao: 'Pergunta numérica', tipo: 'NUMERO', opcoes: null },
  { id: uuid(23), codigo: 'ESCOLHA', descricao: 'Pergunta de escolha', tipo: 'OPCAO', opcoes: ['VALOR_LITERAL', 'OUTRA_OPCAO'] },
] }
const detalheB: DetalheFila = { ...filaB, criterios: [{ ...detalheA.criterios[0]!, id: uuid(24), descricao: 'Pergunta exclusiva B' }] }
const criado: DetalhePedido = { id: uuid(30), fila: { id: filaA.id, nome: filaA.nome, unidade: filaA.unidade }, status: 'EM_ANALISE',
  criada_em: '2026-10-25T12:00:00-03:00', data_pedido: '2026-10-25', turno_preferido: 'QUALQUER', origem_encaminhamento: 'Serviço Sintético', respostas: [], agendamento_ativo: null, linha_do_tempo: [] }
const sessao = { id: uuid(40), papel: 'PACIENTE', nome: null, filas: null }
let pedidos = false
let payloads: NovoPedido[] = []
const servidor = setupServer(
  msw.get('*/api/v1/me', () => HttpResponse.json(sessao)),
  msw.get('*/api/v1/avisos/contagem', () => HttpResponse.json({ nao_lidos: 0 })),
  msw.get('*/api/v1/filas', () => HttpResponse.json({ total: 3, itens: [filaA, filaB, inelegivel] })),
  msw.get('*/api/v1/filas/:id', ({ params }) => HttpResponse.json(params.id === filaB.id ? detalheB : detalheA)),
  msw.get('*/api/v1/solicitacoes', () => HttpResponse.json({ total: pedidos ? 1 : 0, itens: pedidos ? [criado] : [] })),
  msw.post('*/api/v1/solicitacoes', async ({ request }) => { payloads.push(await request.json() as NovoPedido); pedidos = true; return HttpResponse.json(criado, { status: 201 }) }),
  msw.post('*/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => { pedidos = false; payloads = []; document.cookie = 'csrf_token=csrf-sintetico; path=/' })
afterEach(() => { servidor.resetHandlers(); vi.restoreAllMocks(); http.iniciarSessao(); document.cookie = 'csrf_token=; max-age=0; path=/' })
function problema(status: number, tipo = 'about:blank', errors?: unknown[]) {
  return HttpResponse.json({ type: tipo, status, title: 'Falha sintética', errors }, { status, headers: { 'Content-Type': 'application/problem+json' } })
}
function descricao(elemento: HTMLElement) { return (elemento.getAttribute('aria-describedby') ?? '').split(' ').map((id) => document.getElementById(id)?.textContent ?? '').join(' ') }
function adiar<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((r) => { resolve = r }); return { promise, resolve } }
function Navegacao() {
  const location = useLocation(); const navigate = useNavigate()
  return <><output data-testid="localizacao">{JSON.stringify({ pathname: location.pathname, state: location.state })}</output>
    <button onClick={() => void navigate(-1)}>História anterior</button><button onClick={() => void navigate(1)}>História seguinte</button></>
}
function abrir(path = '/paciente/novo') {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/paciente', path]} initialIndex={1}><Rotas /><Navegacao /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, user: userEvent.setup() }
}
async function selecionar(user: ReturnType<typeof userEvent.setup>, nome = filaA.nome) {
  await user.click(await screen.findByRole('radio', { name: nome }))
  await waitFor(() => expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(false))
}
async function informacoes(user: ReturnType<typeof userEvent.setup>) {
  await selecionar(user); await user.click(screen.getByRole('button', { name: 'Continuar' }))
  await user.type(screen.getByLabelText('De onde veio seu encaminhamento?'), '  Serviço Sintético  ')
}
async function revisar(user: ReturnType<typeof userEvent.setup>) {
  await informacoes(user); await user.click(screen.getByRole('button', { name: 'Continuar' }))
  expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Revisar' }))
}

describe('UC-002 — atendimento e contrato', () => {
  it.each(['ATENDENTE', 'GESTOR', 'ADMIN'])('rota nega papel %s sem consultar filas', async (papel) => {
    const lista = vi.fn(() => HttpResponse.json({ total: 0, itens: [] }))
    servidor.use(msw.get('*/api/v1/me', () => HttpResponse.json({ ...sessao, papel })), msw.get('*/api/v1/filas', lista))
    abrir(); await screen.findByText('Acesso não permitido.'); expect(lista).not.toHaveBeenCalled()
  })
  it('rota anônima guarda origem e não abre formulário', async () => {
    servidor.use(msw.get('*/api/v1/me', () => problema(401, '/problemas/nao-autenticado')), msw.post('*/api/v1/auth/refresh', () => problema(401, '/problemas/nao-autenticado')))
    abrir(); await screen.findByRole('heading', { name: 'Entrar' })
    expect(screen.queryByRole('heading', { name: 'Novo pedido' })).toBeNull()
    expect(JSON.parse(screen.getByTestId('localizacao').textContent!).state.origem).toBe('/paciente/novo')
  })
  it('carrega opções reais; inelegível tem motivo acessível e não é selecionável', async () => {
    const { user } = abrir()
    expect((await screen.findByRole('navigation', { name: 'Etapas da nova solicitação' })).textContent).toContain('Etapa 1 de 3 — Atendimento')
    expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
    const motivo = await screen.findByText(inelegivel.motivo_inelegivel!, { exact: false })
    expect((motivo).getAttribute('tabindex')).toBe('0'); expect(descricao(motivo)).toBe(inelegivel.nome)
    expect(screen.queryByRole('radio', { name: inelegivel.nome })).toBeNull()
    await selecionar(user)
    expect(payloads).toEqual([])
  })
  it('loading inicial, erro e retry das opções', async () => {
    const resposta = adiar<Response>()
    servidor.use(msw.get('*/api/v1/filas', () => resposta.promise))
    const { user } = abrir(); await screen.findByText('Carregando atendimentos…')
    await act(async () => resposta.resolve(problema(503)))
    await screen.findByText('Não foi possível carregar os atendimentos.')
    servidor.use(msw.get('*/api/v1/filas', () => HttpResponse.json({ total: 1, itens: [filaA] })))
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await selecionar(user)
  })
  it('estado vazio de atendimentos', async () => {
    servidor.use(msw.get('*/api/v1/filas', () => HttpResponse.json({ total: 0, itens: [] })))
    abrir(); await screen.findByText('Nenhum atendimento está disponível no momento.')
    expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
  })
  it('loading, erro 404 e retry do detalhe', async () => {
    const resposta = adiar<Response>()
    servidor.use(msw.get('*/api/v1/filas/:id', () => resposta.promise))
    const { user } = abrir(); await user.click(await screen.findByRole('radio', { name: filaA.nome }))
    await screen.findByText('Carregando informações do atendimento…')
    expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
    await act(async () => resposta.resolve(problema(404)))
    await screen.findByText('Não foi possível carregar este atendimento.')
    servidor.use(msw.get('*/api/v1/filas/:id', () => HttpResponse.json(detalheA)))
    await user.click(screen.getByRole('button', { name: 'Tentar carregar atendimento de novo' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(false))
  })
  it('paginação incremental usa offset/limit, deduplica, preserva seleção e para ao total', async () => {
    const offsets: number[] = []
    servidor.use(msw.get('*/api/v1/filas', ({ request }) => {
      const params = new URL(request.url).searchParams; expect(params.get('limit')).toBe('10')
      const offset = Number(params.get('offset')); offsets.push(offset)
      return HttpResponse.json(offset === 0 ? { total: 4, itens: [filaA, filaB] } : { total: 4, itens: [filaA, inelegivel] })
    }))
    const { user } = abrir(); await selecionar(user)
    await user.dblClick(screen.getByRole('button', { name: 'Carregar mais' }))
    await screen.findByText(inelegivel.nome)
    expect(offsets).toEqual([0, 2]); expect(screen.getAllByRole('radio', { name: filaA.nome })).toHaveLength(1)
    expect((screen.getByRole('radio', { name: filaA.nome }) as HTMLInputElement).checked).toBe(true)
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).toBeNull()
  })
  it('página vazia antes do total encerra paginação sem loop', async () => {
    const offsets: number[] = []
    servidor.use(msw.get('*/api/v1/filas', ({ request }) => {
      const offset = Number(new URL(request.url).searchParams.get('offset')); offsets.push(offset)
      return HttpResponse.json({ total: 50, itens: offset ? [] : [filaA] })
    }))
    const { user } = abrir(); await selecionar(user); await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Carregar mais' })).toBeNull())
    expect(offsets).toEqual([0, 1])
  })
  it('falha incremental repete apenas a página pendente', async () => {
    let falhar = true; const offsets: number[] = []
    servidor.use(msw.get('*/api/v1/filas', ({ request }) => {
      const offset = Number(new URL(request.url).searchParams.get('offset')); offsets.push(offset)
      return offset === 0 ? HttpResponse.json({ total: 2, itens: [filaA] }) : falhar ? problema(503) : HttpResponse.json({ total: 2, itens: [filaB] })
    }))
    const { user } = abrir(); await selecionar(user); await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    await screen.findByText('Não foi possível carregar os atendimentos.'); falhar = false
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await screen.findByRole('radio', { name: filaB.nome })
    expect(offsets).toEqual([0, 1, 1]); expect((screen.getByRole('radio', { name: filaA.nome }) as HTMLInputElement).checked).toBe(true)
  })
  it('detalhe atrasado A nunca substitui B', async () => {
    const respostaA = adiar<Response>(); const iniciouA = vi.fn()
    servidor.use(msw.get('*/api/v1/filas/:id', ({ params }) => { if (params.id === filaA.id) { iniciouA(); return respostaA.promise }; return HttpResponse.json(detalheB) }))
    const { user } = abrir(); await user.click(await screen.findByRole('radio', { name: filaA.nome }))
    await waitFor(() => expect(iniciouA).toHaveBeenCalledOnce())
    await selecionar(user, filaB.nome); await user.click(screen.getByRole('button', { name: 'Continuar' }))
    await screen.findByLabelText('Pergunta exclusiva B')
    await act(async () => respostaA.resolve(HttpResponse.json(detalheA)))
    expect((screen.getByLabelText('Pergunta exclusiva B')).isConnected).toBe(true); expect(screen.queryByLabelText('Pergunta numérica')).toBeNull()
  })
})

describe('UC-002 — informações, revisão e envio', () => {
  it('valida origem sem truncar e foca primeiro erro', async () => {
    const { user } = abrir(); await selecionar(user); await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Informações' }))
    const origem = screen.getByLabelText('De onde veio seu encaminhamento?')
    expect(origem.hasAttribute('maxlength')).toBe(false); expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
    await user.type(origem, ' '); await user.keyboard('{Enter}')
    expect(document.activeElement).toBe(origem); expect((origem).getAttribute('aria-invalid')).toBe('true')
    expect(descricao(origem)).toMatch(/de 2 a 200 caracteres/)
  })
  it('origem acima de 200 preserva texto colado, mostra erro e impede avanço', async () => {
    const { user } = abrir(); await selecionar(user); await user.click(screen.getByRole('button', { name: 'Continuar' }))
    const origem = screen.getByLabelText('De onde veio seu encaminhamento?') as HTMLInputElement
    const texto = 'x'.repeat(201)
    await user.click(origem); await user.paste(texto)
    expect(origem.value).toBe(texto)
    await screen.findByText('Informe a origem do encaminhamento, de 2 a 200 caracteres.')
    expect(origem.getAttribute('aria-invalid')).toBe('true')
    expect(screen.getByRole('button', { name: 'Continuar' }).hasAttribute('disabled')).toBe(true)
    await user.keyboard('{Enter}')
    expect(document.activeElement).toBe(origem)
    expect(screen.getByRole('heading', { name: 'Informações' })).not.toBeNull()
    expect(payloads).toEqual([])
    await user.clear(origem); await user.paste(`  ${'x'.repeat(200)}  `)
    expect(origem.value).toBe(`  ${'x'.repeat(200)}  `)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Continuar' }).hasAttribute('disabled')).toBe(false))
  })
  it('perguntas opcionais; vazio não vira zero e número inválido impede avanço', async () => {
    const { user } = abrir(); await informacoes(user)
    const numero = screen.getByLabelText('Pergunta numérica')
    expect((numero as HTMLInputElement).value).toBe(''); expect((numero).hasAttribute('min')).not.toBe(true); expect((numero).hasAttribute('max')).not.toBe(true)
    await user.type(numero, 'Infinity'); expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
    await user.clear(numero); await user.type(numero, '-1.25'); expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(false)
  })
  it('voltar preserva origem/turno; trocar atendimento apaga apenas respostas anteriores', async () => {
    const { user } = abrir(); await informacoes(user)
    await user.selectOptions(screen.getByLabelText('Qual turno você prefere?'), 'TARDE')
    await user.selectOptions(screen.getByLabelText('Pergunta de sim ou não'), 'nao')
    await user.click(screen.getByRole('button', { name: 'Voltar' })); expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Atendimento' }))
    expect((screen.getByRole('radio', { name: filaA.nome }) as HTMLInputElement).checked).toBe(true)
    await selecionar(user, filaB.nome); await user.click(screen.getByRole('button', { name: 'Continuar' }))
    expect((screen.getByLabelText('De onde veio seu encaminhamento?') as HTMLInputElement).value).toBe('  Serviço Sintético  ')
    expect((screen.getByLabelText('Qual turno você prefere?') as HTMLInputElement).value).toBe('TARDE')
    expect((screen.getByLabelText('Pergunta exclusiva B') as HTMLInputElement).value).toBe('')
  })
  it('resumo, voltar, payload exato com false/0/string, CSRF e sucesso único', async () => {
    let csrf: string | null = null
    servidor.use(msw.post('*/api/v1/solicitacoes', async ({ request }) => { csrf = request.headers.get('X-CSRF-Token'); payloads.push(await request.json() as NovoPedido); pedidos = true; return HttpResponse.json(criado, { status: 201 }) }))
    const { user, client } = abrir(); const invalidar = vi.spyOn(client, 'invalidateQueries')
    await informacoes(user)
    await user.selectOptions(screen.getByLabelText('Pergunta de sim ou não'), 'nao'); await user.type(screen.getByLabelText('Pergunta numérica'), '0')
    await user.selectOptions(screen.getByLabelText('Pergunta de escolha'), 'VALOR_LITERAL')
    await user.click(screen.getByRole('button', { name: 'Continuar' }))
    const resumo = screen.getByRole('heading', { name: 'Revisar' }).closest('form')!
    expect((resumo).textContent).toContain('Hospital Sintético (HS)'); expect((resumo).textContent).toContain('VALOR_LITERAL'); expect((resumo).textContent).toContain('Sem resposta')
    await user.click(screen.getByRole('button', { name: 'Voltar' })); expect((screen.getByLabelText('Pergunta numérica') as HTMLInputElement).value).toBe('0')
    await user.click(screen.getByRole('button', { name: 'Continuar' })); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Pedido enviado com sucesso.'); await screen.findByRole('heading', { name: filaA.nome })
    expect(payloads).toEqual([{ fila_id: filaA.id, origem_encaminhamento: 'Serviço Sintético', turno_preferido: 'QUALQUER', respostas: [
      { criterio_id: uuid(21), valor: false }, { criterio_id: uuid(22), valor: 0 }, { criterio_id: uuid(23), valor: 'VALOR_LITERAL' },
    ] }]); expect(csrf).toBe('csrf-sintetico')
    expect(invalidar).toHaveBeenCalledWith({ queryKey: pedidosKey })
    expect(invalidar).not.toHaveBeenCalledWith({ queryKey: ['avisos', 'contagem'] })
    await waitFor(() => expect(JSON.parse(screen.getByTestId('localizacao').textContent!).state?.mensagem).toBeUndefined())
    await user.click(screen.getByRole('button', { name: 'História anterior' })); await user.click(screen.getByRole('button', { name: 'História seguinte' }))
    expect(screen.queryByText('Pedido enviado com sucesso.')).toBeNull()
  })
  it('envia sem respostas opcionais e bloqueia duplo clique durante POST', async () => {
    const pendente = adiar<Response>(); const post = vi.fn(async ({ request }: { request: Request }) => { payloads.push(await request.json() as NovoPedido); return pendente.promise })
    servidor.use(msw.post('*/api/v1/solicitacoes', post))
    const { user } = abrir(); await revisar(user); await user.dblClick(screen.getByRole('button', { name: 'Enviar pedido' }))
    await waitFor(() => expect(post).toHaveBeenCalledOnce())
    expect(payloads[0]?.respostas).toEqual([])
    expect((screen.getByRole('button', { name: 'Aguarde…' })).hasAttribute('disabled')).toBe(true)
    await act(async () => pendente.resolve(HttpResponse.json(criado, { status: 201 })))
    await screen.findByText('Pedido enviado com sucesso.')
  })
  it('máximo de 50 respostas informa o limite sem tornar perguntas obrigatórias', async () => {
    const criterios = Array.from({ length: 51 }, (_, i) => ({ id: uuid(100 + i), codigo: `Q${i}`, descricao: `Pergunta sintética ${i}`, tipo: 'SIM_NAO' as const, opcoes: null }))
    servidor.use(msw.get('*/api/v1/filas/:id', () => HttpResponse.json({ ...detalheA, criterios })))
    const { user } = abrir(); await informacoes(user)
    const controles = screen.getAllByRole('combobox').slice(1)
    await act(async () => { controles.forEach((controle) => fireEvent.change(controle, { target: { value: 'nao' } })) })
    await screen.findByText('Você pode responder até 50 perguntas. Deixe as demais sem resposta.')
    expect(screen.getByRole('button', { name: 'Continuar' }).hasAttribute('disabled')).toBe(true)
    await user.selectOptions(screen.getByLabelText(criterios[0]!.descricao), '')
    expect(screen.getByRole('button', { name: 'Continuar' }).hasAttribute('disabled')).toBe(false)
  })
  it.each(['10', '-10', '1.5', '1,5', '0', '-1.25', '2.5'])('NUMERO aceita decimal %s sem limites inventados e envia número', async (valor) => {
    const { user } = abrir(); await informacoes(user); await user.type(screen.getByLabelText('Pergunta numérica'), valor)
    await user.click(screen.getByRole('button', { name: 'Continuar' })); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Pedido enviado com sucesso.'); expect(payloads[0]?.respostas).toEqual([{ criterio_id: uuid(22), valor: Number(valor.replace(',', '.')) }])
  })
  it.each(['0x10', '1e3', 'texto', 'Infinity', '-', '1.2.3'])('NUMERO rejeita formato %s e preserva o texto para correção', async (valor) => {
    const { user } = abrir(); await informacoes(user)
    const numero = screen.getByLabelText('Pergunta numérica') as HTMLInputElement
    await user.type(numero, valor)
    expect(numero.value).toBe(valor)
    await screen.findByText('Informe um número válido ou deixe em branco.')
    expect(screen.getByRole('button', { name: 'Continuar' }).hasAttribute('disabled')).toBe(true)
    await user.keyboard('{Enter}')
    expect(document.activeElement).toBe(numero)
    expect(payloads).toEqual([])
  })
  it('falha ambígua não repete POST e orienta conferir lista', async () => {
    const post = vi.fn(() => HttpResponse.error()); servidor.use(msw.post('*/api/v1/solicitacoes', post))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Não foi possível confirmar se o pedido foi enviado. Confira Meus atendimentos antes de tentar novamente.')
    expect(post).toHaveBeenCalledOnce(); expect((screen.getByRole('link', { name: 'Ver meus atendimentos' })).getAttribute('href')).toBe('/paciente')
  })
})

describe('UC-002 — Problem Details', () => {
  it.each(['valor', 'criterio_id'])('422 indexado em %s mapeia índice compacto ao campo original, sem refresh', async (campo) => {
    const refresh = vi.fn(); servidor.use(msw.post('*/api/v1/auth/refresh', refresh), msw.post('*/api/v1/solicitacoes', () => problema(422, 'about:blank', [
      { loc: ['body', 'respostas', 0, campo], msg: 'Resposta sintética inválida.', type: 'value_error' },
    ])))
    const { user } = abrir(); await informacoes(user); await user.type(screen.getByLabelText('Pergunta numérica'), '2')
    await user.click(screen.getByRole('button', { name: 'Continuar' })); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Resposta sintética inválida.')
    expect(document.activeElement).toBe(screen.getByLabelText('Pergunta numérica')); expect((screen.getByLabelText('Pergunta numérica')).getAttribute('aria-invalid')).toBe('true')
    expect((screen.getByLabelText('Pergunta sem resposta')).getAttribute('aria-invalid')).not.toBe('true'); expect(refresh).not.toHaveBeenCalled()
  })
  it.each(['origem_encaminhamento', 'fila_id'])('422 em %s volta à etapa e foca o controle', async (campo) => {
    servidor.use(msw.post('*/api/v1/solicitacoes', () => problema(422, 'about:blank', [{ loc: ['body', campo], msg: 'Confira este campo sintético.', type: 'value_error' }])))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Confira este campo sintético.')
    expect(document.activeElement).toBe(campo === 'fila_id' ? screen.getByRole('radio', { name: filaA.nome }) : screen.getByLabelText('De onde veio seu encaminhamento?'))
  })
  it.each<{ errors: unknown[] | undefined }>([
    { errors: undefined },
    { errors: [{ loc: ['body', 'campo_desconhecido'], msg: 'Erro sintético.', type: 'value_error' }] },
    { errors: [{ loc: ['query', 'fila_id'], msg: 'Erro sintético.', type: 'value_error' }] },
    { errors: [{ loc: [], msg: 'Erro sintético.', type: 'value_error' }] },
  ])('422 sem loc mapeável ($errors) permanece na revisão, preserva dados e foca alerta', async ({ errors }) => {
    servidor.use(msw.post('*/api/v1/solicitacoes', () => problema(422, 'about:blank', errors)))
    const { user } = abrir(); await informacoes(user)
    await user.selectOptions(screen.getByLabelText('Qual turno você prefere?'), 'TARDE')
    await user.selectOptions(screen.getByLabelText('Pergunta de sim ou não'), 'nao')
    await user.type(screen.getByLabelText('Pergunta numérica'), '0')
    await user.click(screen.getByRole('button', { name: 'Continuar' })); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    const erro = await screen.findByRole('alert'); expect((erro).textContent).toContain('Confira os campos indicados e tente novamente.')
    expect(screen.getByRole('heading', { name: 'Revisar' })).not.toBeNull()
    expect(screen.getByRole('navigation', { name: 'Etapas da nova solicitação' }).textContent).toContain('Etapa 3 de 3 — Revisar')
    expect(screen.getByText('Serviço Sintético')).not.toBeNull()
    expect(screen.getByText('Tarde')).not.toBeNull()
    expect(screen.getByText('Não')).not.toBeNull()
    expect(screen.getByText('0', { selector: 'dd' })).not.toBeNull()
    expect(document.activeElement).toBe(erro.parentElement)
    await user.click(screen.getByRole('button', { name: 'Voltar' }))
    expect((screen.getByLabelText('De onde veio seu encaminhamento?') as HTMLInputElement).value).toBe('  Serviço Sintético  ')
    expect((screen.getByLabelText('Qual turno você prefere?') as HTMLSelectElement).value).toBe('TARDE')
    expect((screen.getByLabelText('Pergunta de sim ou não') as HTMLSelectElement).value).toBe('nao')
    expect((screen.getByLabelText('Pergunta numérica') as HTMLInputElement).value).toBe('0')
  })
  it('422 com campos de etapas diferentes foca a etapa do primeiro erro', async () => {
    servidor.use(msw.post('*/api/v1/solicitacoes', () => problema(422, 'about:blank', [
      { loc: ['body', 'origem_encaminhamento'], msg: 'Confira a origem sintética.', type: 'value_error' },
      { loc: ['body', 'fila_id'], msg: 'Confira o atendimento sintético.', type: 'value_error' },
    ])))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Confira a origem sintética.')
    expect(document.activeElement).toBe(screen.getByLabelText('De onde veio seu encaminhamento?'))
  })
  it('5xx no POST também permite conferir se houve criação sem repetir envio', async () => {
    const post = vi.fn(() => problema(503)); servidor.use(msw.post('*/api/v1/solicitacoes', post))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Não foi possível confirmar se o pedido foi enviado. Confira Meus atendimentos antes de tentar novamente.')
    expect(post).toHaveBeenCalledOnce()
  })
  it('409 duplicada usa type, não depende de ID e oferece a lista', async () => {
    servidor.use(msw.post('*/api/v1/solicitacoes', () => problema(409, '/problemas/solicitacao-duplicada')))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByText('Você já tem um pedido em andamento para este atendimento. Acompanhe-o em Meus atendimentos.')
    expect((screen.getByRole('link', { name: 'Ver meus atendimentos' })).getAttribute('href')).toBe('/paciente')
  })
  it('409 inelegível revalida lista/detalhe e bloqueia novo envio', async () => {
    const { user } = abrir(); await revisar(user)
    const resposta = adiar<Response>(); const lista = vi.fn(async () => (await resposta.promise).clone()); const detalhe = vi.fn(async () => (await resposta.promise).clone())
    servidor.use(msw.get('*/api/v1/filas', lista), msw.get('*/api/v1/filas/:id', detalhe), msw.post('*/api/v1/solicitacoes', () => problema(409, '/problemas/nao-elegivel')))
    await user.click(screen.getByRole('button', { name: 'Enviar pedido' })); await screen.findByText('Atualizando atendimentos…')
    expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
    expect(lista).toHaveBeenCalledOnce(); expect(detalhe).toHaveBeenCalledOnce()
    await act(async () => resposta.resolve(problema(503)))
    await screen.findByRole('button', { name: 'Atualizar atendimento' }); expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
    servidor.use(msw.get('*/api/v1/filas', () => HttpResponse.json({ total: 1, itens: [{ ...filaA, elegivel: false, motivo_inelegivel: 'Indisponível após atualização.' }] })), msw.get('*/api/v1/filas/:id', () => HttpResponse.json({ ...detalheA, elegivel: false, motivo_inelegivel: 'Indisponível após atualização.' })))
    await user.click(screen.getByRole('button', { name: 'Atualizar atendimento' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Atualizar atendimento' })).toBeNull())
    expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(true)
  })
  it.each(['sem-permissao', 'csrf-invalido', 'sem-consentimento'])('403 %s não encerra sessão nem faz refresh', async (tipo) => {
    const refresh = vi.fn(); servidor.use(msw.post('*/api/v1/auth/refresh', refresh), msw.post('*/api/v1/solicitacoes', () => problema(403, `/problemas/${tipo}`)))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByRole('alert'); expect((screen.getByRole('heading', { name: 'Novo pedido' })).isConnected).toBe(true); expect(refresh).not.toHaveBeenCalled()
    if (tipo === 'sem-consentimento') { expect((screen.getByRole('button', { name: 'Enviar pedido' })).hasAttribute('disabled')).toBe(true); expect(screen.queryByRole('checkbox')).toBeNull() }
  })
})

describe('UC-002 — sessão, acessibilidade e privacidade', () => {
  it.each([false, true])('B2: refetch de /me preserva wizard e POST pendente (%s)', async (enviando) => {
    const pendente = adiar<Response>(); const post = vi.fn(() => pendente.promise)
    servidor.use(msw.post('*/api/v1/solicitacoes', post))
    const { user, client } = abrir(); await revisar(user)
    if (enviando) { await user.click(screen.getByRole('button', { name: 'Enviar pedido' })); await waitFor(() => expect(post).toHaveBeenCalledOnce()) }
    const me = adiar<Response>(); servidor.use(msw.get('*/api/v1/me', () => me.promise))
    let refetch!: Promise<void>
    act(() => { refetch = client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    expect((screen.getByRole('heading', { name: 'Revisar' })).isConnected).toBe(true)
    await act(async () => { me.resolve(HttpResponse.json(sessao)); await refetch })
    expect((screen.getByText('Serviço Sintético')).isConnected).toBe(true)
    if (enviando) { await act(async () => pendente.resolve(HttpResponse.json(criado, { status: 201 }))); await screen.findByText('Pedido enviado com sucesso.'); expect(post).toHaveBeenCalledOnce() }
  })
  it.each(['revogada', 'papel', 'troca'])('background fecha acesso: %s', async (tipo) => {
    const { user, client } = abrir(); await revisar(user)
    servidor.use(msw.get('*/api/v1/me', () => tipo === 'revogada' ? problema(401, '/problemas/nao-autenticado') : HttpResponse.json({ ...sessao, ...(tipo === 'papel' ? { papel: 'GESTOR' } : { trocar_senha: true }) })), msw.post('*/api/v1/auth/refresh', () => problema(401, '/problemas/nao-autenticado')))
    await act(async () => { await client.invalidateQueries({ queryKey: sessaoOptions.queryKey }) })
    await screen.findByText(tipo === 'revogada' ? 'Entrar' : tipo === 'papel' ? 'Acesso não permitido.' : 'Troca de senha obrigatória', { selector: tipo === 'papel' ? 'p' : 'h1' })
    expect(screen.queryByRole('heading', { name: 'Revisar' })).toBeNull()
  })
  it('403 troca obrigatória no POST redireciona sem refresh', async () => {
    const refresh = vi.fn(); servidor.use(msw.post('*/api/v1/auth/refresh', refresh), msw.post('*/api/v1/solicitacoes', () => problema(403, '/problemas/troca-de-senha-obrigatoria')))
    const { user } = abrir(); await revisar(user); await user.click(screen.getByRole('button', { name: 'Enviar pedido' }))
    await screen.findByRole('heading', { name: 'Troca de senha obrigatória' }); expect(refresh).not.toHaveBeenCalled()
  })
  it.each([false, true])('logout com formulário ou POST pendente (%s) descarta resposta antiga após login novo', async (enviando) => {
    const resposta = adiar<Response>(); const post = vi.fn(() => resposta.promise)
    servidor.use(msw.post('*/api/v1/solicitacoes', post), msw.post('*/api/v1/auth/login', () => HttpResponse.json({ papel: 'PACIENTE', expira_em: '2026-10-25T16:00:00Z' })))
    const { user, client } = abrir(); await revisar(user)
    if (enviando) { await user.click(screen.getByRole('button', { name: 'Enviar pedido' })); await waitFor(() => expect(post).toHaveBeenCalledOnce()) }
    await user.click(screen.getByRole('button', { name: 'Sair' })); await screen.findByRole('heading', { name: 'Entrar' })
    await user.type(screen.getByLabelText('CPF ou e-mail'), 'sintetico@exemplo.test'); await user.type(screen.getByLabelText('Senha'), 'Sintetica!123')
    await user.click(screen.getByRole('button', { name: 'Entrar' })); await screen.findByRole('heading', { name: 'Meus atendimentos' })
    client.setQueryDefaults(['sessao-nova'], { gcTime: Infinity }); client.setQueryData(['sessao-nova'], 'preservado')
    await act(async () => resposta.resolve(HttpResponse.json(criado, { status: 201 })))
    expect(screen.queryByText('Pedido enviado com sucesso.')).toBeNull(); expect(client.getQueryData(['sessao-nova'])).toBe('preservado')
  })
  it('axe nas três etapas, erro e sucesso; teclado, foco, ADR-007 e nenhum storage', async () => {
    const storage = [vi.spyOn(Storage.prototype, 'setItem'), vi.spyOn(Storage.prototype, 'removeItem'), vi.spyOn(Storage.prototype, 'clear')]
    const { user, container } = abrir(); await screen.findByRole('radio', { name: filaA.nome })
    expect((await axe(container)).violations).toEqual([])
    screen.getByRole('radio', { name: filaA.nome }).focus(); await user.keyboard(' ')
    await waitFor(() => expect((screen.getByRole('button', { name: 'Continuar' })).hasAttribute('disabled')).toBe(false))
    await user.tab(); // próxima opção elegível
    screen.getByRole('button', { name: 'Continuar' }).focus(); await user.keyboard('{Enter}')
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Informações' }))
    await user.tab(); await user.type(screen.getByLabelText('De onde veio seu encaminhamento?'), 'x'); await user.keyboard('{Enter}')
    expect((await axe(container)).violations).toEqual([])
    await user.type(screen.getByLabelText('De onde veio seu encaminhamento?'), ' sintético'); expect((await axe(container)).violations).toEqual([])
    screen.getByRole('button', { name: 'Continuar' }).focus(); await user.keyboard('{Enter}')
    expect((await axe(container)).violations).toEqual([])
    expect(container.textContent).not.toMatch(/posição|tamanho da fila|nota|risco|score|priority/i)
    screen.getByRole('button', { name: 'Enviar pedido' }).focus(); await user.keyboard('{Enter}')
    await screen.findByText('Pedido enviado com sucesso.'); expect((await axe(container)).violations).toEqual([])
    storage.forEach((spy) => expect(spy).not.toHaveBeenCalled())
  })
  it('cadastro conserva rótulo padrão e três etapas', async () => {
    servidor.use(msw.get('*/api/v1/termos/vigente', () => HttpResponse.json({ versao: 'sintetica', texto: 'Termo sintético' })))
    abrir('/criar-conta')
    const indicador = screen.getByRole('navigation', { name: 'Etapas do cadastro' })
    expect((indicador).textContent).toContain('Etapa 1 de 3 — Seus dados'); expect(within(indicador).getAllByRole('listitem')).toHaveLength(3)
  })
})
