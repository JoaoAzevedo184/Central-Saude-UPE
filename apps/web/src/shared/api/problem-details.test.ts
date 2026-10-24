import { describe, expect, it } from 'vitest'
import contrato from './generated/schema.d.ts?raw'
import { ApiError, erroDaResposta, mensagemDoProblema, mensagensPorTipo } from './problem-details'

describe('RFC 9457 — mensagens dos problemas', () => {
  it('cobre todos os types anunciados pelo contrato gerado do backend', () => {
    const tipos = [...new Set(contrato.match(/\/problemas\/[a-z-]+/g))].sort()
    expect(Object.keys(mensagensPorTipo).sort()).toEqual(tipos)
  })

  it.each([
    ['/problemas/credenciais-invalidas', 'CPF/e-mail ou senha incorretos.'],
    ['/problemas/proposta-expirada', 'O prazo para confirmar esta vaga terminou.'],
    ['/problemas/solicitacao-duplicada', 'Você já tem um pedido aberto nesta fila.'],
  ])('escolhe a mensagem por type: %s', (type, message) => {
    const problem = { type, title: 'Título técnico', status: 409, detail: 'Detalhe interno' }
    expect(mensagemDoProblema(problem)).toBe(message)
    expect(new ApiError(problem, new Response(null, { status: 409 })).message).toBe(message)
  })

  it('usa fallback amigável sem expor title/detail desconhecidos', () => {
    expect(mensagemDoProblema({ type: '/problemas/futuro', status: 500 })).toBe('Não foi possível concluir. Tente novamente mais tarde.')
    expect(mensagemDoProblema({ type: 'about:blank', status: 422 })).toBe('Confira os campos indicados e tente novamente.')
  })

  it('preserva detalhes técnicos e extensões separados da mensagem exibida', async () => {
    const body = { type: '/problemas/proposta-expirada', title: 'Conflict', status: 409, detail: 'Detalhe sintético', solicitacao_id: 'sintetica' }
    const error = await erroDaResposta(new Response(JSON.stringify(body), {
      status: 409, headers: { 'Content-Type': 'application/problem+json' },
    }))
    expect(error.problem).toEqual(body)
    expect(error.message).toBe(mensagensPorTipo['/problemas/proposta-expirada'])
  })
})
