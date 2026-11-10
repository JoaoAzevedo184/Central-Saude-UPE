import { describe, expect, it } from 'vitest'
import { ApiError } from '../../shared/api/problem-details'
import { prazoNovaTentativa } from './api-indicadores'
import { diaMesCivil, hojeRecife, periodoPronto, validarPeriodo } from './estado-indicadores'

describe('Indicadores — datas civis e espera do serviço (AM-025)', () => {
  it('usa o dia de Recife na virada UTC de mês e ano', () => {
    expect(hojeRecife(new Date('2026-11-01T01:30:00Z'))).toBe('2026-10-31')
    expect(hojeRecife(new Date('2027-01-01T02:59:59Z'))).toBe('2026-12-31')
    expect(hojeRecife(new Date('2027-01-01T03:00:00Z'))).toBe('2027-01-01')
    expect(periodoPronto('mes', '2026-10-31')).toEqual({ de: '2026-10-01', ate: '2026-10-31' })
    expect(periodoPronto('4', '2027-01-01')).toEqual({ de: '2026-12-05', ate: '2027-01-01' })
    expect(periodoPronto('8', '2027-01-01')).toEqual({ de: '2026-11-07', ate: '2027-01-01' })
  })
  it('aceita um dia e 366 dias inclusivos; rejeita 367, datas inexistentes, futuro e inversão', () => {
    expect(validarPeriodo('2026-11-09', '2026-11-09', '2026-11-09')).toBeUndefined()
    expect(validarPeriodo('2025-11-09', '2026-11-09', '2026-11-09')).toBeUndefined()
    expect(validarPeriodo('2025-11-08', '2026-11-09', '2026-11-09')).toContain('366')
    expect(validarPeriodo('2026-02-30', '2026-03-01', '2026-11-09')).toContain('válidas')
    expect(validarPeriodo('', '', '2026-11-09')).toContain('válidas')
    expect(validarPeriodo('2026-11-09', '2026-11-10', '2026-11-09')).toContain('hoje')
    expect(validarPeriodo('2026-11-09', '2026-11-08', '2026-11-09')).toContain('anterior ou igual')
    expect(diaMesCivil('2026-11-02')).toBe('02/11')
  })
  it.each([
    ['12', 12000], ['0', 0], ['Mon, 09 Nov 2026 12:00:05 GMT', 5000],
    ['Mon, 09 Nov 2026 11:59:59 GMT', 0], [null, 0], ['', 0], ['inválido', 0], ['-1', 0], ['2.5', 0], ['abc, 09 Nov 2026 12:00:05 GMT', 0],
  ])('Retry-After %s respeita o header ou libera imediatamente', (header, diferenca) => {
    const agora = Date.parse('2026-11-09T12:00:00Z')
    const response = new Response(null, { status: 503, headers: header === null ? {} : { 'Retry-After': header } })
    const erro = new ApiError({ status: 503, type: '/problemas/consulta-demorada', title: 'Falha sintética' }, response)
    expect(prazoNovaTentativa(erro, agora)).toBe(diferenca ? agora + diferenca : 0)
  })
})
