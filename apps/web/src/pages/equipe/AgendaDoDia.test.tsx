import { QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as msw, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import type { components } from '../../shared/api/generated/schema'

type Agendamento = components['schemas']['AgendamentoDoDia']
type Fila = components['schemas']['FilaEquipeSaida']
const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const fila = (n = 10, ativa = true): Fila => ({ id: uuid(n), nome: `Fila sintética ${n}`, unidade_sigla: 'HUOC',
  especialidade: 'Dermatologia', ativa, contagem_por_status: {} })
const agendamento = (n = 1, extra: Partial<Agendamento> = {}): Agendamento => ({ id: uuid(n), solicitacao_id: uuid(n + 100),
  inicio: '2026-11-16T11:00:00Z', fim: '2026-11-16T11:30:00Z', profissional: 'Dra. Exemplo',
  paciente_nome: `Sintético ${n} S.`, status: 'CONFIRMADO', presenca_registrada: false, ...extra })
let papel: components['schemas']['Papel']
let filas: Fila[]
let itens: Agendamento[]
let consultas: URL[]
let consultasFilas: number
let escritas: { id: string; compareceu: boolean; csrf: string | null }[]
const servidor = setupServer(
  msw.get('*/api/v1/me', () => HttpResponse.json({ id: uuid(99), papel, nome: null, filas: filas.map((f) => f.id) })),
  msw.get('*/api/v1/equipe/filas', () => { consultasFilas++; return HttpResponse.json({ total: filas.length, itens: filas }) }),
  msw.get('*/api/v1/equipe/filas/:id/agendamentos', ({ request }) => {
    consultas.push(new URL(request.url)); return HttpResponse.json(itens)
  }),
  msw.post('*/api/v1/equipe/agendamentos/:id/presenca', async ({ request, params }) => {
    const { compareceu } = await request.json() as { compareceu: boolean }
    escritas.push({ id: String(params.id), compareceu, csrf: request.headers.get('X-CSRF-Token') })
    const atual = itens.find((item) => item.id === params.id)!
    itens = itens.map((item) => item.id === params.id ? { ...item, status: compareceu ? 'REALIZADO' : 'FALTOU', presenca_registrada: true } : item)
    return HttpResponse.json({ id: atual.solicitacao_id, status: compareceu ? 'ATENDIDA' : 'NA_FILA', fila_id: uuid(10),
      paciente_nome: 'Paciente Sintético', paciente_cpf: '***.482.***-10', classificacao_risco: 'VERDE', nota: 0,
      data_entrada_fila: '2026-11-16T12:00:00Z', data_pedido: '2026-11-01', turno_preferido: 'QUALQUER',
      origem_encaminhamento: null, respostas: [], historico: [],
    } satisfies components['schemas']['SolicitacaoEquipeSaida'])
  }),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-11-16T12:00:00Z'))
  papel = 'ATENDENTE'; filas = [fila()]; itens = [agendamento()]; consultas = []; consultasFilas = 0; escritas = []
  http.iniciarSessao(); document.cookie = 'csrf_token=csrf-sintetico; path=/'
})
afterEach(() => { cleanup(); servidor.resetHandlers(); vi.useRealTimers(); vi.unstubAllGlobals(); http.iniciarSessao() })
function Navegacao() {
  const location = useLocation(); const navigate = useNavigate()
  return <><output data-testid="url">{location.pathname}{location.search}</output><button onClick={() => void navigate(-1)}>História anterior</button></>
}
function abrir(path = `/equipe/agenda?fila=${uuid(10)}&data=2026-11-16`) {
  const client = criarQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Rotas /><Navegacao /></MemoryRouter></QueryClientProvider>)
  return { ...view, client, user: userEvent.setup() }
}
const tabela = () => screen.findByRole('table', { name: 'Agendamentos do dia' })
const status = () => within(screen.getByRole('main', { name: 'Área da equipe' })).getByRole('status')
const linha = (n = 1) => screen.getByRole('row', { name: new RegExp(`Sintético ${n} S\\.`) })
const problema = (tipo: string, status = 409) => HttpResponse.json({ type: `/problemas/${tipo}`, status, title: 'Falha sintética' },
  { status, headers: { 'Content-Type': 'application/problem+json' } })

describe('UC-008 / RN-013 / RN-014 — agenda da equipe', () => {
  it.each(['ATENDENTE', 'GESTOR', 'ADMIN'] as const)('inclui menu e rota para %s, com escrita só da atendente', async (valor) => {
    papel = valor; abrir(); await tabela()
    expect(screen.getByRole('link', { name: 'Agenda do dia' }).getAttribute('aria-current')).toBe('page')
    expect(Boolean(screen.queryByRole('button', { name: 'Compareceu' }))).toBe(valor === 'ATENDENTE')
    expect(Boolean(screen.queryByRole('button', { name: 'Faltou' }))).toBe(valor === 'ATENDENTE')
  })
  it('ordena os horários, mostra quatro situações e resume somente confirmados pendentes', async () => {
    itens = [agendamento(2, { status: 'PROPOSTO', inicio: '2026-11-16T13:00:00Z', fim: '2026-11-16T13:30:00Z' }),
      agendamento(), agendamento(3, { status: 'REALIZADO', presenca_registrada: true }), agendamento(4, { status: 'FALTOU', presenca_registrada: true })]
    abrir(); const table = await tabela()
    expect(within(table).getAllByRole('link').map((link) => link.textContent)).toEqual(['Sintético 1 S.', 'Sintético 3 S.', 'Sintético 4 S.', 'Sintético 2 S.'])
    expect(table.textContent).toContain('08:00'); expect(table.textContent).toContain('08:30'); expect(table.textContent).toContain('Dra. Exemplo')
    expect(within(linha(2)).getByText('Proposta aguardando o paciente')).toBeTruthy()
    expect(within(linha(3)).queryByRole('button')).toBeNull(); expect(within(linha(4)).queryByRole('button')).toBeNull()
    expect(screen.getByRole('link', { name: 'Sintético 1 S.' }).getAttribute('href')).toBe(`/equipe/solicitacoes/${uuid(101)}`)
    const resumo = screen.getByRole('region', { name: 'Resumo do dia' })
    expect(resumo.textContent).toContain('Total do dia4'); expect(resumo.textContent).toContain('Presença pendente1')
    expect(resumo.textContent).toContain('Compareceram1'); expect(resumo.textContent).toContain('Faltaram1')
  })
  it('desabilita ambas as ações antes do início e informa a hora de Recife', async () => {
    itens = [agendamento(1, { inicio: '2026-11-16T15:00:00Z', fim: '2026-11-16T15:30:00Z' })]; abrir(); await tabela()
    expect((screen.getByRole('button', { name: 'Compareceu' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Faltou' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('Disponível a partir de 12:00')).toBeTruthy()
  })
  it('presença já registrada não oferece nova escrita nem entra no resumo de pendentes', async () => {
    itens = [agendamento(1, { presenca_registrada: true })]; abrir(); await tabela()
    expect(within(linha()).queryByRole('button')).toBeNull()
    expect(screen.getByRole('region', { name: 'Resumo do dia' }).textContent).toContain('Presença pendente0')
  })
  it('compareceu no início exato envia CSRF, recarrega, invalida caches e devolve foco', async () => {
    itens = [agendamento(1, { inicio: '2026-11-16T12:00:00Z', fim: '2026-11-16T12:30:00Z' })]
    const { client, user } = abrir(); await tabela()
    const chaves = [['fila-equipe', uuid(10)], ['pedido-equipe', uuid(101)], ['agenda-equipe', uuid(10), '2026-11-15']]
    for (const chave of chaves) { client.setQueryDefaults(chave, { gcTime: Infinity }); client.setQueryData(chave, {}) }
    await user.click(screen.getByRole('button', { name: 'Compareceu' }))
    await waitFor(() => expect(within(linha()).queryByRole('button')).toBeNull())
    expect(escritas).toEqual([{ id: uuid(1), compareceu: true, csrf: 'csrf-sintetico' }])
    expect(within(linha()).getByText('Compareceu')).toBeTruthy()
    await waitFor(() => expect(status().textContent).toContain('Comparecimento registrado.'))
    expect(consultas.length).toBeGreaterThan(1); expect(consultasFilas).toBeGreaterThan(1)
    for (const chave of chaves) expect(client.getQueryState(chave)?.isInvalidated).toBe(true)
    expect(document.activeElement).toBe(linha())
  })
  it('Faltou pede confirmação; Voltar não escreve nem muda o agendamento', async () => {
    const { user } = abrir(); await tabela()
    await user.click(screen.getByRole('button', { name: 'Faltou' }))
    expect(screen.getByText('O pedido volta para o fim da fila e o paciente é avisado. Confirmar falta?')).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Confirmar' }))
    expect(escritas).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(screen.queryByRole('button', { name: 'Confirmar' })).toBeNull()
    expect(within(linha()).getByText('Confirmado')).toBeTruthy(); expect(escritas).toHaveLength(0)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Faltou' }))
  })
  it('confirma a falta e anuncia o sucesso após atualizar a agenda', async () => {
    const { user } = abrir(); await tabela()
    await user.click(screen.getByRole('button', { name: 'Faltou' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    await waitFor(() => expect(within(linha()).queryByRole('button')).toBeNull())
    expect(escritas[0]).toEqual({ id: uuid(1), compareceu: false, csrf: 'csrf-sintetico' })
    expect(within(linha()).getByText('Faltou')).toBeTruthy(); await waitFor(() => expect(status().textContent).toContain('Falta registrada.'))
    expect(document.activeElement).toBe(linha())
  })
  it.each(['tolerancia-nao-encerrada', 'transicao-invalida', 'outro-conflito'])('409 %s informa o conflito, reconsulta e preserva o confirmado', async (tipo) => {
    servidor.use(msw.post('*/api/v1/equipe/agendamentos/:id/presenca', () => problema(tipo)))
    const { user } = abrir(); await tabela()
    await user.click(screen.getByRole('button', { name: 'Faltou' }))
    await user.click(screen.getByRole('button', { name: 'Confirmar' }))
    const mensagem = tipo === 'tolerancia-nao-encerrada' ? 'Ainda dentro da tolerância de atraso desta fila. Tente de novo mais tarde.' : 'Não foi possível registrar: o horário ou a situação do agendamento mudou. A agenda foi recarregada.'
    expect(await screen.findByText(mensagem)).toBeTruthy()
    await waitFor(() => expect(consultas.length).toBeGreaterThan(1))
    expect(within(linha()).getByText('Confirmado')).toBeTruthy(); expect(screen.queryByText('Falta registrada.')).toBeNull()
  })
  it('enquanto escreve bloqueia apenas os botões daquela linha e não duplica o POST', async () => {
    let resolver!: () => void
    let chamadas = 0
    servidor.use(msw.post('*/api/v1/equipe/agendamentos/:id/presenca', async () => {
      chamadas++; await new Promise<void>((resolve) => { resolver = resolve }); return problema('transicao-invalida')
    }))
    itens = [agendamento(), agendamento(2)]
    const { user } = abrir(); await tabela()
    await user.click(within(linha()).getByRole('button', { name: 'Compareceu' }))
    await waitFor(() => expect(chamadas).toBe(1))
    expect(within(linha()).getAllByRole('button').every((botao) => (botao as HTMLButtonElement).disabled)).toBe(true)
    expect((within(linha(2)).getByRole('button', { name: 'Compareceu' }) as HTMLButtonElement).disabled).toBe(false)
    await act(async () => resolver()); await screen.findByText(/o horário ou a situação/)
    expect(chamadas).toBe(1)
  })
  it('usa hoje em Recife perto da meia-noite UTC e a primeira fila ativa', async () => {
    vi.setSystemTime(new Date('2027-01-01T02:59:59Z')); filas = [fila(11, false), fila(10)]
    abrir('/equipe/agenda'); await tabela()
    expect(consultas[0]!.searchParams.get('data')).toBe('2026-12-31')
    expect(consultas[0]!.pathname).toContain(uuid(10))
    await waitFor(() => expect(screen.getByTestId('url').textContent).toBe(`/equipe/agenda?fila=${uuid(10)}&data=2026-12-31`))
  })
  it('trocar a data atualiza a URL e reabrir mantém a fila e o dia', async () => {
    filas = [fila(10), fila(11)]
    const { user, unmount } = abrir('/equipe/agenda'); await tabela()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Fila' }), uuid(11))
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-10-29' } })
    const url = `/equipe/agenda?fila=${uuid(11)}&data=2026-10-29`
    await waitFor(() => expect(screen.getByTestId('url').textContent).toBe(url))
    unmount(); abrir(url); await tabela()
    expect((screen.getByRole('combobox', { name: 'Fila' }) as HTMLSelectElement).value).toBe(uuid(11))
    expect((screen.getByLabelText('Data') as HTMLInputElement).value).toBe('2026-10-29')
  })
  it('abrir com fila e data na URL mostra o dia informado e consulta a fila escolhida', async () => {
    filas = [fila(10), fila(11)]
    const url = `/equipe/agenda?fila=${uuid(11)}&data=2026-10-29`
    abrir(url); await tabela()
    expect((screen.getByRole('combobox', { name: 'Fila' }) as HTMLSelectElement).value).toBe(uuid(11))
    expect((screen.getByLabelText('Data') as HTMLInputElement).value).toBe('2026-10-29')
    expect(consultas[0]!.pathname).toBe(`/api/v1/equipe/filas/${uuid(11)}/agendamentos`)
    expect(consultas[0]!.searchParams.get('data')).toBe('2026-10-29')
    expect(screen.getByTestId('url').textContent).toBe(url)
  })
  it('troca dia, fila e campo de data pela URL; Voltar restaura o recorte', async () => {
    filas = [fila(10), fila(11)]; const { user } = abrir(); await tabela()
    await user.click(screen.getByRole('button', { name: 'Dia anterior' }))
    await waitFor(() => expect(consultas.at(-1)?.searchParams.get('data')).toBe('2026-11-15'))
    expect(screen.getByTestId('url').textContent).toBe(`/equipe/agenda?fila=${uuid(10)}&data=2026-11-15`)
    await user.click(screen.getByRole('button', { name: 'Próximo dia' }))
    await waitFor(() => expect(screen.getByTestId('url').textContent).toBe(`/equipe/agenda?fila=${uuid(10)}&data=2026-11-16`))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Fila' }), uuid(11))
    await waitFor(() => expect(screen.getByTestId('url').textContent).toBe(`/equipe/agenda?fila=${uuid(11)}&data=2026-11-16`))
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-12-01' } })
    await waitFor(() => expect(consultas.at(-1)?.searchParams.get('data')).toBe('2026-12-01'))
    await user.click(screen.getByRole('button', { name: 'Hoje' }))
    await waitFor(() => expect(consultas.at(-1)?.searchParams.get('data')).toBe('2026-11-16'))
    expect(screen.getByTestId('url').textContent).toBe(`/equipe/agenda?fila=${uuid(11)}&data=2026-11-16`)
    await user.click(screen.getByRole('button', { name: 'História anterior' }))
    await waitFor(() => expect((screen.getByLabelText('Data') as HTMLInputElement).value).toBe('2026-12-01'))
    expect(screen.getByTestId('url').textContent).toBe(`/equipe/agenda?fila=${uuid(11)}&data=2026-12-01`)
  })
  it('mostra estado vazio', async () => {
    itens = []; abrir()
    expect(await screen.findByText('Nenhum agendamento nesta fila neste dia.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Compareceu' })).toBeNull()
  })
  it('mostra carregamento e erro com tentativa manual sem ações antigas', async () => {
    let responder!: (resposta: Response) => void
    const pendente = new Promise<Response>((resolve) => { responder = resolve })
    servidor.use(msw.get('*/api/v1/equipe/filas/:id/agendamentos', () => pendente))
    const { user } = abrir()
    await screen.findByText('Carregando agenda…')
    await act(async () => responder(problema('falha', 503)))
    expect(await screen.findByText('Não foi possível carregar a agenda.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Compareceu' })).toBeNull()
    servidor.resetHandlers(); await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await tabela()
  })
  it('data inválida na URL não consulta a API e Hoje permite corrigir', async () => {
    const { user } = abrir(`/equipe/agenda?fila=${uuid(10)}&data=2026-02-30`)
    await screen.findByText('Informe uma data válida entre 01/01/2000 e 31/12/2100.')
    expect(consultas).toHaveLength(0)
    await user.click(screen.getByRole('button', { name: 'Hoje' })); await tabela()
    expect(consultas[0]!.searchParams.get('data')).toBe('2026-11-16')
  })
  it('sem filas orienta buscar acesso e não consulta agendamentos', async () => {
    filas = []; abrir(); await screen.findByText('Nenhuma fila liberada')
    expect(consultas).toHaveLength(0)
  })
  it.each([403, 404])('erro %s da agenda não mantém botões de escrita', async (codigo) => {
    servidor.use(msw.get('*/api/v1/equipe/filas/:id/agendamentos', () => problema('sem-permissao', codigo)))
    abrir()
    await screen.findByText(codigo === 404 ? 'Esta fila não está disponível para consulta.' : 'Não foi possível acessar a agenda. Confira seu acesso com o gestor da unidade.')
    expect(screen.queryByRole('table')).toBeNull(); expect(screen.queryByRole('button', { name: 'Compareceu' })).toBeNull()
  })
  it('troca de sessão durante o POST descarta o resultado e não reabre caches', async () => {
    let responder!: (resposta: Response) => void
    const pendente = new Promise<Response>((resolve) => { responder = resolve })
    let enviada = false
    servidor.use(msw.post('*/api/v1/equipe/agendamentos/:id/presenca', () => { enviada = true; return pendente }))
    const { client, user } = abrir(); await tabela()
    await user.click(screen.getByRole('button', { name: 'Compareceu' }))
    await waitFor(() => expect(enviada).toBe(true))
    const invalidar = vi.spyOn(client, 'invalidateQueries')
    await act(async () => { http.iniciarSessao(); client.clear(); responder(problema('transicao-invalida')); await pendente })
    await waitFor(() => expect(client.isMutating()).toBe(0))
    expect(invalidar).not.toHaveBeenCalled()
    expect(screen.queryByText('Comparecimento registrado.')).toBeNull()
  })
  it('atualiza a habilitação em 30 s e remove o temporizador ao desmontar', async () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] }); vi.setSystemTime(new Date('2026-11-16T12:00:00Z'))
    const agendar = vi.spyOn(globalThis, 'setInterval'); const limpar = vi.spyOn(globalThis, 'clearInterval')
    itens = [agendamento(1, { inicio: '2026-11-16T12:00:15Z', fim: '2026-11-16T12:30:15Z' })]
    const { unmount } = abrir(); await tabela()
    expect((screen.getByRole('button', { name: 'Compareceu' }) as HTMLButtonElement).disabled).toBe(true)
    await act(async () => { vi.advanceTimersByTime(30_000) })
    expect((screen.getByRole('button', { name: 'Compareceu' }) as HTMLButtonElement).disabled).toBe(false)
    const indice = agendar.mock.calls.findIndex(([, prazo]) => prazo === 30_000)
    expect(indice).toBeGreaterThanOrEqual(0)
    const timer = agendar.mock.results[indice]!.value
    unmount(); expect(limpar).toHaveBeenCalledWith(timer)
  })
  it('não tem violações axe na agenda e na confirmação de falta', async () => {
    const { container, user } = abrir(); await tabela()
    expect((await axe(container)).violations).toEqual([])
    await user.click(screen.getByRole('button', { name: 'Faltou' }))
    expect((await axe(container)).violations).toEqual([])
  })
})
