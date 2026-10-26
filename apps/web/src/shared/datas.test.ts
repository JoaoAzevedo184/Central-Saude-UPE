import { describe, expect, it } from 'vitest'
import { avisoPrazo, formatarDataHora, formatarDataPedido, formatarPrazo } from './datas'

describe('UC-004 — datas em America/Recife', () => {
  it('converte UTC para Recife inclusive na virada do dia e do ano', () => {
    expect(formatarDataHora('2026-10-28T11:00:00Z')).toBe('quarta-feira, 28/10, às 08:00')
    expect(formatarPrazo('2027-01-01T01:30:00Z')).toBe('31/12 às 22:30')
    expect(formatarDataHora('2026-10-28T01:00:00Z')).toBe('terça-feira, 27/10, às 22:00')
  })
  it('preserva a data civil do pedido, sem voltar ao dia anterior', () => {
    expect(formatarDataPedido('2026-10-24')).toBe('24/10/2026')
  })
  it('distingue 24h, menos de 24h, singular, minutos e prazo encerrado', () => {
    const agora = Date.parse('2026-10-24T11:00:00Z')
    expect(avisoPrazo('2026-10-25T11:00:00Z', agora)).toBeUndefined()
    expect(avisoPrazo('2026-10-25T10:59:59Z', agora)).toBe('Faltam 23 horas')
    expect(avisoPrazo('2026-10-24T12:30:00Z', agora)).toBe('Falta 1 hora')
    expect(avisoPrazo('2026-10-24T11:30:00Z', agora)).toBe('Falta menos de 1 hora')
    expect(avisoPrazo('2026-10-24T11:00:00Z', agora)).toBe('O prazo para responder terminou.')
  })
})
