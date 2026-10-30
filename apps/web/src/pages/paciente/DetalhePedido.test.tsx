import { QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { http as mockHttp, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { axe } from 'vitest-axe'
import { Rotas } from '../../app/Rotas'
import { criarQueryClient } from '../../app/query-client'
import { http } from '../../shared/api/http'
import { detalhePedidoOptions, pedidosOptions } from './api'
import type { DetalhePedido as Pedido } from './api'

const unidade = { id: '00000000-0000-4000-8000-000000000002', nome: 'Hospital Sintético', sigla: 'HS' }
const base: Pedido = {
  id: '00000000-0000-4000-8000-000000000003', status: 'EM_ANALISE',
  fila: { id: '00000000-0000-4000-8000-000000000004', nome: 'Consulta sintética', unidade },
  data_pedido: '2026-10-20', criada_em: '2026-10-20T11:00:00Z',
  turno_preferido: 'TARDE', origem_encaminhamento: 'Unidade sintética de origem',
  respostas: [{ descricao: 'Usa medicamento?', valor: false }, { descricao: 'Quantidade informada', valor: 0 }],
  linha_do_tempo: [{ tipo: 'CRIADA', data: '2026-10-20', motivo: 'CONTEUDO_INTERNO' }], agendamento_ativo: null,
}
const ativo: NonNullable<Pedido['agendamento_ativo']> = {
  id: '00000000-0000-4000-8000-000000000005', status: 'PROPOSTO',
  inicio: '2026-11-02T02:30:00Z', fim: '2026-11-02T03:00:00Z', expira_em: '2026-10-31T11:00:00Z',
  unidade, endereco: 'Rua Sintética, 100', profissional: 'Profissional Sintético',
}
let pedido: Pedido
let leituras: number
function problema(status: number, tipo: string) {
  return HttpResponse.json({ status, type: `/problemas/${tipo}`, title: 'Falha sintética', detail: 'CONTEUDO_INTERNO' },
    { status, headers: { 'Content-Type': 'application/problem+json' } })
}
const servidor = setupServer(
  mockHttp.get('*/api/v1/me', () => HttpResponse.json({ id: '00000000-0000-4000-8000-000000000001', papel: 'PACIENTE', nome: null, filas: null })),
  mockHttp.get('*/api/v1/avisos/contagem', () => HttpResponse.json({ nao_lidos: 0 })),
  mockHttp.get('*/api/v1/solicitacoes/:id', () => { leituras++; return HttpResponse.json(pedido) }),
  mockHttp.get('*/api/v1/solicitacoes', ({ request }) => {
    const encerradas = new URL(request.url).searchParams.get('situacao') === 'encerradas'
    const itens = encerradas === ['ATENDIDA', 'CANCELADA'].includes(pedido.status) ? [pedido] : []
    return HttpResponse.json({ total: itens.length, itens })
  }),
)
beforeAll(() => servidor.listen({ onUnhandledFrame: 'error' }))
afterAll(() => servidor.close())
beforeEach(() => {
  pedido = structuredClone(base); leituras = 0
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-29T12:00:00Z'))
  document.cookie = 'csrf_token=csrf-sintetico; path=/'
})
afterEach(() => { vi.useRealTimers(); servidor.resetHandlers(); vi.restoreAllMocks(); http.iniciarSessao(); document.cookie = 'csrf_token=; max-age=0; path=/' })
function abrir() {
  const client = criarQueryClient()
  return { ...render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/paciente/solicitacoes/${base.id}`]}><Rotas /></MemoryRouter></QueryClientProvider>),
    client, user: userEvent.setup() }
}
async function carregou() { await screen.findByRole('heading', { name: 'Consulta sintética', level: 1 }) }
async function abrirCancelamento(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: 'Cancelar pedido' }))
  return screen.getByRole('dialog')
}

describe('UC-002/RN-007 — detalhe do pedido', () => {
  it.each([
    ['EM_ANALISE', 'Pedido em análise', 'A equipe da central está analisando o seu pedido. Avisamos quando houver novidade.', true],
    ['NA_FILA', 'Aguardando vaga', 'Estamos procurando uma vaga para você. Você não precisa fazer nada agora.', true],
    ['EM_PROPOSTA', 'Você tem uma vaga para confirmar', 'Confirme até', true],
    ['AGENDADA', 'Consulta marcada', 'Leve documento com foto, cartão do SUS e o encaminhamento.', true],
    ['ATENDIDA', 'Atendimento realizado', 'Seu atendimento foi realizado.', false],
    ['CANCELADA', 'Pedido cancelado', 'Seu pedido foi encerrado. Se precisar de novo, faça um novo pedido.', false],
  ] as const)('%s: bloco correto, selo compartilhado e ADR-007', async (status, selo, texto, podeCancelar) => {
    pedido.status = status
    if (status === 'EM_PROPOSTA' || status === 'AGENDADA') pedido.agendamento_ativo = { ...ativo, status: status === 'AGENDADA' ? 'CONFIRMADO' : 'PROPOSTO' }
    const { container } = abrir(); await carregou()
    expect(screen.getAllByText(selo).length).toBeGreaterThan(0)
    expect(screen.getByText(texto, { exact: status !== 'EM_PROPOSTA' })).toBeTruthy()
    expect(Boolean(screen.queryByRole('button', { name: 'Cancelar pedido' }))).toBe(podeCancelar)
    expect(container.textContent).not.toMatch(/posição|nota|risco/i)
    expect(container.textContent).not.toContain('CONTEUDO_INTERNO')
    expect(screen.getByRole('link', { name: '‹ Meus atendimentos' }).getAttribute('href')).toBe('/paciente')
    expect(container.querySelector('.detalhe-topo .pedido-data')?.textContent).toBe('Pedido em 20/10/2026')
  })
  it('UC-004: consulta usa data por extenso em Recife, endereço e lembretes', async () => {
    pedido.status = 'AGENDADA'; pedido.agendamento_ativo = { ...ativo, status: 'CONFIRMADO', expira_em: null }
    abrir(); await carregou()
    expect(screen.getByText(/domingo, 1 de novembro de 2026, às 23:30/i)).toBeTruthy()
    expect(screen.getByText('Rua Sintética, 100')).toBeTruthy()
    expect(screen.getByText(/Profissional Sintético/)).toBeTruthy()
    expect(screen.getByText('Chegue com antecedência. Tolerância de atraso: 1 hora.')).toBeTruthy()
  })
  it('endereço nulo orienta confirmar com a unidade', async () => {
    pedido.status = 'AGENDADA'; pedido.agendamento_ativo = { ...ativo, status: 'CONFIRMADO', endereco: null }
    abrir(); await screen.findByText('Confirme o endereço com a unidade.')
  })
  it.each(['EM_PROPOSTA', 'AGENDADA'] as const)('RN-005: %s não cancela a partir do início', async (status) => {
    pedido.status = status; pedido.agendamento_ativo = { ...ativo, status: status === 'AGENDADA' ? 'CONFIRMADO' : 'PROPOSTO', inicio: '2026-10-29T12:00:00Z' }
    abrir(); await carregou(); expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull()
  })
  it('RN-005: GET que chega depois do início nunca insere o botão de cancelar no DOM', async () => {
    const antes = Date.parse('2026-10-29T12:00:00Z')
    pedido.status = 'AGENDADA'; pedido.agendamento_ativo = { ...ativo, status: 'CONFIRMADO', inicio: '2026-10-29T12:00:01Z' }
    let liberar!: () => void
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', async () => {
      await new Promise<void>((resolve) => { liberar = resolve }); return HttpResponse.json(pedido)
    }))
    const { container } = abrir(); await waitFor(() => expect(liberar).toBeDefined())
    let inseriuCancelar = false
    const observador = new MutationObserver((registros) => {
      for (const registro of registros) for (const no of registro.addedNodes) {
        if (!(no instanceof Element)) continue
        const botoes = [...(no.matches('button') ? [no] : []), ...no.querySelectorAll('button')]
        if (botoes.some((botao) => botao.textContent === 'Cancelar pedido')) inseriuCancelar = true
      }
    })
    observador.observe(container, { childList: true, subtree: true })
    try {
      vi.mocked(Date.now).mockReturnValue(antes + 2000)
      await act(async () => { liberar() }); await carregou()
      expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull()
      expect(inseriuCancelar).toBe(false)
    } finally { observador.disconnect() }
  })
  it('RN-005: início alterado para o passado remove o botão sem esperar o próximo intervalo', async () => {
    pedido.status = 'AGENDADA'; pedido.agendamento_ativo = { ...ativo, status: 'CONFIRMADO' }
    const { client } = abrir(); await carregou()
    const agora = Date.parse('2026-10-29T12:00:00Z')
    vi.mocked(Date.now).mockReturnValue(agora + 2000)
    await act(async () => {
      client.setQueryData(detalhePedidoOptions(base.id).queryKey, {
        ...pedido, agendamento_ativo: { ...pedido.agendamento_ativo!, inicio: '2026-10-29T12:00:01Z' },
      })
    })
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull())
  })
  it('RN-005: botão some no instante em que o relógio atravessa o início com a tela aberta', async () => {
    pedido.status = 'AGENDADA'; pedido.agendamento_ativo = { ...ativo, status: 'CONFIRMADO' }
    const { client } = abrir(); await carregou()
    let agora = Date.parse('2026-10-29T12:00:00Z')
    vi.mocked(Date.now).mockImplementation(() => agora)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
    await act(async () => {
      client.setQueryData(detalhePedidoOptions(base.id).queryKey, {
        ...pedido, agendamento_ativo: { ...pedido.agendamento_ativo!, inicio: '2026-10-29T12:00:01Z' },
      })
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toBeTruthy()
    agora += 1000
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull()
  })
  it('RN-007: ordena datas civis sem deslocar dia e oculta motivos e eventos internos', async () => {
    pedido.linha_do_tempo = [
      { tipo: 'PROPOSTA_ENVIADA', data: '2026-10-22', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'CRIADA', data: '2026-10-20', motivo: null },
      { tipo: 'CLASSIFICADA', data: '2026-10-21', motivo: 'risco nota posição' },
      { tipo: 'RECLASSIFICADA', data: '2026-10-21', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'ENTROU_NA_FILA', data: '2026-10-21', motivo: null },
      { tipo: 'CONFIRMADA', data: '2026-10-22', motivo: null },
    ]
    const { container } = abrir(); await carregou()
    const linha = screen.getByRole('list', { name: 'Andamento' })
    expect(within(linha).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '20/10/2026Pedido recebido', '21/10/2026Pedido analisado. Aguardando vaga.',
      '22/10/2026Vaga oferecida', '22/10/2026Consulta confirmada',
    ])
    expect(linha.textContent).not.toMatch(/\d{2}:\d{2}/)
    expect(container.textContent).not.toMatch(/CONTEUDO_INTERNO|posição|nota|risco/i)
  })
  it('respostas ausentes não aparecem; false e zero são preservados', async () => {
    pedido.respostas.push({ descricao: 'Pergunta sem resposta', valor: '' })
    abrir(); await carregou()
    const informacoes = screen.getByRole('region', { name: 'O que você informou' })
    expect(within(informacoes).getByText('Não')).toBeTruthy(); expect(within(informacoes).getByText('0')).toBeTruthy()
    expect(screen.queryByText('Pergunta sem resposta')).toBeNull()
    expect(screen.queryByText('Sem resposta')).toBeNull()
    expect(screen.getByText('Tarde')).toBeTruthy(); expect(screen.getByText('Unidade sintética de origem')).toBeTruthy()
  })
  it('RN-007: cada evento público usa texto local e ignora o motivo', async () => {
    pedido.linha_do_tempo = [
      { tipo: 'CRIADA', data: '2026-10-20', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'ENTROU_NA_FILA', data: '2026-10-20', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'PROPOSTA_ENVIADA', data: '2026-10-21', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'RECUSADA', data: '2026-10-21', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'REENTROU_NA_FILA', data: '2026-10-21', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'PROPOSTA_EXPIRADA', data: '2026-10-22', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'CONFIRMADA', data: '2026-10-23', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'FALTOU', data: '2026-10-24', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'ATENDIDA', data: '2026-10-25', motivo: 'CONTEUDO_INTERNO' },
      { tipo: 'CANCELADA', data: '2026-10-26', motivo: 'CONTEUDO_INTERNO' },
    ]
    abrir(); await carregou()
    const linha = screen.getByRole('list', { name: 'Andamento' })
    expect(within(linha).getAllByRole('listitem').map((li) => li.querySelector('p')?.textContent)).toEqual([
      'Pedido recebido', 'Pedido analisado. Aguardando vaga.', 'Vaga oferecida', 'Você informou que esta data não serve',
      'Pedido voltou para a fila', 'Prazo para confirmar encerrado', 'Consulta confirmada', 'Falta registrada na consulta',
      'Atendimento realizado', 'Pedido cancelado',
    ])
    expect(linha.textContent).not.toContain('CONTEUDO_INTERNO')
  })
  it('mostra carregamento enquanto aguarda a consulta', async () => {
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => new Promise(() => {})))
    abrir(); await screen.findByText('Carregando seu pedido…')
  })
  it('erro de leitura permite nova tentativa', async () => {
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => HttpResponse.error()))
    const { user } = abrir(); await screen.findByRole('alert')
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => HttpResponse.json(pedido)))
    await user.click(screen.getByRole('button', { name: 'Tentar de novo' })); await carregou()
  })
  it('falha de refetch preserva dados, diálogo e motivo já escolhido', async () => {
    const { user, client } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => HttpResponse.error()))
    await act(async () => { await client.invalidateQueries({ queryKey: detalhePedidoOptions(base.id).queryKey }) })
    await screen.findByText('Não foi possível atualizar seu pedido.')
    expect(screen.getByRole('dialog')).toBe(dialogo)
    expect((within(dialogo).getByRole('combobox') as HTMLSelectElement).value).toBe('OUTRO')
    expect(screen.getByRole('heading', { name: 'Consulta sintética', level: 1 })).toBeTruthy()
  })
  it('UC-002/AM-001: 404 tem mensagem neutra e volta à lista', async () => {
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => problema(404, 'nao-encontrado')))
    abrir(); await screen.findByText('Não encontramos este pedido.')
    expect(screen.getByRole('link', { name: '‹ Meus atendimentos' }).getAttribute('href')).toBe('/paciente')
  })
})

describe('UC-004/UC-005 — proposta compartilhada', () => {
  beforeEach(() => { pedido.status = 'EM_PROPOSTA'; pedido.agendamento_ativo = { ...ativo } })
  it.each(['confirmar', 'recusar'] as const)('%s envia CSRF sem corpo e atualiza detalhe', async (acao) => {
    let envios = 0
    servidor.use(mockHttp.post(`*/api/v1/agendamentos/:id/${acao}`, async ({ request }) => {
      envios++; expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico'); expect(await request.text()).toBe('')
      pedido = { ...pedido, status: acao === 'confirmar' ? 'AGENDADA' : 'NA_FILA', agendamento_ativo: acao === 'confirmar' ? { ...ativo, status: 'CONFIRMADO' } : null }
      return HttpResponse.json(pedido)
    }))
    const { user } = abrir(); const nome = acao === 'confirmar' ? 'Confirmar consulta' : 'Esta data não serve'
    await user.click(await screen.findByRole('button', { name: nome }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: nome }))
    await screen.findByText(acao === 'confirmar' ? 'Consulta confirmada' : 'Você continua na fila e vamos procurar outra data.')
    await screen.findByText(acao === 'confirmar' ? 'Consulta marcada' : 'Aguardando vaga'); expect(envios).toBe(1)
  })
  it('UC-006: 409 proposta expirada informa e recarrega', async () => {
    servidor.use(mockHttp.post('*/api/v1/agendamentos/:id/confirmar', () => { pedido.status = 'NA_FILA'; pedido.agendamento_ativo = null; return problema(409, 'proposta-expirada') }))
    const { user } = abrir(); await user.click(await screen.findByRole('button', { name: 'Confirmar consulta' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirmar consulta' }))
    await screen.findByText('O prazo para confirmar terminou. Seu pedido voltou para a fila.')
    await screen.findByText('Aguardando vaga'); expect(leituras).toBeGreaterThan(1)
  })
  it.each(['NA_FILA', 'AGENDADA', 'outro agendamento', 'prazo expirado', 'data alterada'] as const)(
    'UC-004: detalhe recarregado com %s fecha o diálogo antigo', async (mudanca) => {
      const { user, client } = abrir()
      await user.click(await screen.findByRole('button', { name: 'Confirmar consulta' }))
      expect(screen.getByRole('dialog')).toBeTruthy()
      if (mudanca === 'NA_FILA') pedido = { ...pedido, status: 'NA_FILA', agendamento_ativo: null }
      else if (mudanca === 'AGENDADA') pedido = { ...pedido, status: 'AGENDADA', agendamento_ativo: { ...ativo, status: 'CONFIRMADO' } }
      else if (mudanca === 'outro agendamento') pedido = { ...pedido, agendamento_ativo: { ...ativo, id: '00000000-0000-4000-8000-000000000006' } }
      else if (mudanca === 'prazo expirado') pedido = { ...pedido, agendamento_ativo: { ...ativo, expira_em: '2026-10-29T11:59:59Z' } }
      else pedido = { ...pedido, agendamento_ativo: { ...ativo, inicio: '2026-11-03T02:30:00Z' } }
      await act(async () => { await client.invalidateQueries({ queryKey: detalhePedidoOptions(base.id).queryKey }) })
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
      expect(screen.getByText('Este atendimento mudou. Confira os dados atualizados do seu pedido.')).toBeTruthy()
    },
  )
  it('UC-006: prazo termina com o diálogo aberto sem oferecer confirmação antiga', async () => {
    const { client } = abrir(); await carregou()
    let agora = Date.parse('2026-10-29T12:00:00Z')
    vi.mocked(Date.now).mockImplementation(() => agora)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
    await act(async () => {
      client.setQueryData(detalhePedidoOptions(base.id).queryKey, { ...pedido, agendamento_ativo: { ...ativo, expira_em: '2026-10-29T12:00:01Z' } })
      await vi.advanceTimersByTimeAsync(0)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar consulta' }))
    expect(screen.getByRole('dialog')).toBeTruthy()
    agora += 1000
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Confirmar consulta' })).toBeNull()
  })
})

describe('RN-005 — cancelar pedido', () => {
  it('lista fechada, explicação, foco, teclado e axe na tela e diálogo', async () => {
    const { user, container } = abrir(); await carregou()
    expect((await axe(container)).violations).toEqual([])
    const acionador = screen.getByRole('button', { name: 'Cancelar pedido' })
    const dialogo = await abrirCancelamento(user)
    expect(within(dialogo).getByText('Seu pedido será encerrado. Se precisar de novo, faça um novo pedido.')).toBeTruthy()
    const motivo = within(dialogo).getByRole('combobox', { name: 'Por que você quer cancelar?' })
    expect(document.activeElement).toBe(motivo)
    expect(within(motivo).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Escolha um motivo', 'Não preciso mais', 'Consegui atendimento em outro lugar', 'Tenho dificuldade de ir até lá', 'O horário não dá', 'Outro motivo',
    ])
    expect(within(dialogo).queryByRole('textbox')).toBeNull()
    await user.selectOptions(motivo, 'OUTRO')
    await user.tab({ shift: true }); expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await user.tab(); expect(document.activeElement).toBe(motivo)
    await user.tab(); expect(document.activeElement).toBe(within(dialogo).getByRole('button', { name: 'Voltar' }))
    expect((await axe(container)).violations).toEqual([])
    await user.keyboard('{Escape}'); expect(screen.queryByRole('dialog')).toBeNull(); expect(document.activeElement).toBe(acionador)
  })
  it('envia somente motivo_codigo com CSRF; sucesso atualiza detalhe e lista', async () => {
    let envios = 0
    servidor.use(mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', async ({ request }) => {
      envios++; expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
      expect(await request.json()).toEqual({ motivo_codigo: 'NAO_PRECISO_MAIS' })
      pedido = { ...pedido, status: 'CANCELADA' }; return HttpResponse.json(pedido)
    }))
    const spies = ['setItem', 'removeItem', 'clear'].map((nome) => vi.spyOn(Storage.prototype, nome as 'setItem'))
    const { user, client } = abrir(); client.setQueryDefaults(['pedidos-paciente'], { gcTime: Infinity })
    client.setQueryData(pedidosOptions('abertas', 0).queryKey, { total: 1, itens: [base] })
    const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'NAO_PRECISO_MAIS')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await screen.findByText('Pedido cancelado.'); await screen.findByText('Pedido cancelado')
    await waitFor(() => expect(client.getQueryState(pedidosOptions('abertas', 0).queryKey)?.isInvalidated).toBe(true))
    expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull(); expect(envios).toBe(1)
    await user.click(screen.getByRole('link', { name: '‹ Meus atendimentos' }))
    await screen.findByRole('heading', { name: 'Meus atendimentos' }); await user.click(screen.getByRole('tab', { name: 'Histórico' }))
    await screen.findByText('Pedido cancelado')
    for (const spy of spies) expect(spy).not.toHaveBeenCalled()
  })
  it('409 transicao-invalida informa mudança e recarrega', async () => {
    servidor.use(mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', () => { pedido.status = 'ATENDIDA'; return problema(409, 'transicao-invalida') }))
    const { user } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await screen.findByText('Este atendimento mudou. Confira os dados atualizados do seu pedido.')
    await screen.findByText('Atendimento realizado'); expect(leituras).toBeGreaterThan(1)
  })
  it('refetch com mudança de estado fecha o diálogo e explica a mudança', async () => {
    const { user, client } = abrir(); await abrirCancelamento(user)
    pedido.status = 'ATENDIDA'
    await act(async () => { await client.invalidateQueries({ queryKey: detalhePedidoOptions(base.id).queryKey }) })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByText('Este atendimento mudou. Confira os dados atualizados do seu pedido.')).toBeTruthy()
  })
  it.each([
    ['início', 'segunda-feira, 02/11, às 23:30'], ['prazo', '01/11 às 08:00'],
  ] as const)('atualização do %s ainda futuro preserva o diálogo de cancelar, motivo e foco', async (campo, texto) => {
    pedido.status = 'EM_PROPOSTA'; pedido.agendamento_ativo = { ...ativo }
    const { user, client } = abrir(); await carregou()
    const acionador = screen.getByRole('button', { name: 'Cancelar pedido' })
    const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    pedido = { ...pedido, agendamento_ativo: { ...ativo,
      ...(campo === 'início' ? { inicio: '2026-11-03T02:30:00Z' } : { expira_em: '2026-11-01T11:00:00Z' }),
    } }
    await act(async () => { await client.invalidateQueries({ queryKey: detalhePedidoOptions(base.id).queryKey }) })
    await screen.findByText(texto)
    expect(screen.getByRole('dialog')).toBe(dialogo)
    expect((within(dialogo).getByRole('combobox') as HTMLSelectElement).value).toBe('OUTRO')
    await user.keyboard('{Escape}')
    expect(document.activeElement).toBe(acionador)
  })
  it.each([422, 403, 500])('erro %s fica no diálogo sem expor detail ou repetir POST', async (status) => {
    let envios = 0
    servidor.use(mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', () => { envios++; return problema(status, 'falha-sintetica') }))
    const { user } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await within(dialogo).findByRole('alert'); expect(dialogo.textContent).not.toContain('CONTEUDO_INTERNO'); expect(envios).toBe(1)
  })
  it('404 no GET durante envio libera a trava se o detalhe voltar a estar disponível', async () => {
    pedido.status = 'EM_PROPOSTA'; pedido.agendamento_ativo = { ...ativo }
    let liberar!: () => void
    servidor.use(mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', async () => {
      await new Promise<void>((resolve) => { liberar = resolve }); return HttpResponse.json(pedido)
    }))
    const { user, client } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(liberar).toBeDefined())
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => problema(404, 'nao-encontrado')))
    await act(async () => { await client.invalidateQueries({ queryKey: detalhePedidoOptions(base.id).queryKey }) })
    await screen.findByText('Não encontramos este pedido.')
    servidor.use(mockHttp.get('*/api/v1/solicitacoes/:id', () => HttpResponse.json(pedido)))
    await act(async () => { liberar(); await client.invalidateQueries({ queryKey: detalhePedidoOptions(base.id).queryKey }) })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmar consulta' }).hasAttribute('disabled')).toBe(false))
  })
  it('404 no POST de cancelamento fecha diálogo e recarrega o detalhe', async () => {
    let removido = false, envios = 0
    servidor.use(
      mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', () => { envios++; removido = true; return problema(404, 'nao-encontrado') }),
      mockHttp.get('*/api/v1/solicitacoes/:id', () => { leituras++; return removido ? problema(404, 'nao-encontrado') : HttpResponse.json(pedido) }),
    )
    const { user } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await screen.findByText('Não encontramos este pedido.')
    expect(envios).toBe(1); expect(leituras).toBeGreaterThan(1)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull()
  })
  it('falha de transporte após Esc não mantém alerta contraditório ao recuperar pedido cancelado', async () => {
    let liberar!: () => void
    servidor.use(mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', async () => {
      await new Promise<void>((resolve) => { liberar = resolve }); pedido.status = 'CANCELADA'; return HttpResponse.error()
    }))
    const { user } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(liberar).toBeDefined()); await user.keyboard('{Escape}')
    await act(async () => { liberar() })
    await screen.findByText('Pedido cancelado')
    expect(screen.queryByText('Não foi possível confirmar o cancelamento. Confira o pedido antes de tentar novamente.')).toBeNull()
  })
  it('resposta tardia de sessão antiga não altera a sessão nova nem mostra sucesso', async () => {
    let liberar!: () => void
    servidor.use(mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', async () => { await new Promise<void>((resolve) => { liberar = resolve }); return HttpResponse.json({ ...pedido, status: 'CANCELADA' }) }))
    const { user } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(liberar).toBeDefined()); const epoca = http.iniciarSessao()
    await act(async () => { liberar() })
    expect(http.geracaoSessao()).toBe(epoca); expect(screen.queryByText('Pedido cancelado.')).toBeNull()
    await waitFor(() => expect(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }).hasAttribute('disabled')).toBe(false))
  })
  it('logout pelo Sair durante POST pendente protege tela e cache após novo login', async () => {
    const idNovaSessao = '00000000-0000-4000-8000-000000000007'
    const pedidoNovo: Pedido = { ...base, id: '00000000-0000-4000-8000-000000000008', status: 'NA_FILA', fila: { ...base.fila, nome: 'Pedido da nova sessão' } }
    const respostaAntiga = { ...structuredClone(base), status: 'CANCELADA' }
    let liberar!: () => void, concluir!: () => void
    const concluido = new Promise<void>((resolve) => { concluir = resolve })
    const logout = vi.fn(({ request }: { request: Request }) => {
      expect(request.headers.get('X-CSRF-Token')).toBe('csrf-sintetico')
      return new HttpResponse(null, { status: 204 })
    })
    servidor.use(
      mockHttp.post('*/api/v1/solicitacoes/:id/cancelar', async () => {
        await new Promise<void>((resolve) => { liberar = resolve }); concluir(); return HttpResponse.json(respostaAntiga)
      }),
      mockHttp.post('*/api/v1/auth/logout', logout),
      mockHttp.post('*/api/v1/auth/login', () => HttpResponse.json({ papel: 'PACIENTE', expira_em: '2026-10-29T13:00:00Z' })),
    )
    const requisicoes = vi.spyOn(http, 'request')
    const { user, client } = abrir(); const dialogo = await abrirCancelamento(user)
    await user.selectOptions(within(dialogo).getByRole('combobox'), 'OUTRO')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(liberar).toBeDefined())
    const indicePost = requisicoes.mock.calls.findIndex(([path]) => path === `/solicitacoes/${base.id}/cancelar`)
    const terminouPost = (requisicoes.mock.results[indicePost]!.value as Promise<unknown>).catch((erro: unknown) => erro)
    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Sair' }))
    await screen.findByRole('heading', { name: 'Entrar' })
    expect(await terminouPost).toMatchObject({ name: 'AbortError' })
    expect(logout).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(detalhePedidoOptions(base.id).queryKey)).toBeUndefined()
    servidor.use(
      mockHttp.get('*/api/v1/me', () => HttpResponse.json({ id: idNovaSessao, papel: 'PACIENTE', nome: null, filas: null })),
      mockHttp.get('*/api/v1/solicitacoes', () => HttpResponse.json({ total: 1, itens: [pedidoNovo] })),
    )
    await user.type(screen.getByLabelText('CPF ou e-mail'), '12345678909')
    await user.type(screen.getByLabelText('Senha'), 'Senha-sintetica-123')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('heading', { name: 'Meus atendimentos' })
    await screen.findByText('Pedido da nova sessão')
    await waitFor(() => expect(client.isFetching()).toBe(0))
    const epocaNova = http.geracaoSessao()
    client.setQueryDefaults(['pedido-paciente'], { gcTime: Infinity })
    client.setQueryData(detalhePedidoOptions(pedidoNovo.id).queryKey, pedidoNovo)
    const cacheNovo = client.getQueryCache().getAll().map((query) => ({ chave: query.queryKey, dados: query.state.data }))
    await act(async () => { liberar(); await concluido; await terminouPost })
    expect(http.geracaoSessao()).toBe(epocaNova)
    expect(client.getQueryData(['sessao'])).toMatchObject({ id: idNovaSessao })
    expect(client.getQueryCache().getAll().map((query) => ({ chave: query.queryKey, dados: query.state.data }))).toEqual(cacheNovo)
    expect(client.getQueryData(detalhePedidoOptions(base.id).queryKey)).toBeUndefined()
    expect(screen.getByText('Pedido da nova sessão')).toBeTruthy()
    expect(screen.queryByText('Pedido cancelado.')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Consulta sintética' })).toBeNull()
  })
})
