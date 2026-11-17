import { describe, expect, it } from 'vitest'
import { lerEstadoAgenda, mudarDiaAgenda, paramsAgenda, validarDataAgenda } from './estado-agenda'

describe('UC-008 — filtros civis da agenda', () => {
  it('normaliza somente filtros conhecidos e usa a data padrão fornecida', () => {
    expect(lerEstadoAgenda(new URLSearchParams('fila=invalida&paciente=ignorado'), '2026-11-16')).toEqual({ fila: '', data: '2026-11-16' })
    expect(paramsAgenda({ fila: '00000000-0000-4000-8000-000000000010', data: '2026-11-16' }).toString())
      .toBe('fila=00000000-0000-4000-8000-000000000010&data=2026-11-16')
  })
  it.each(['', '2026-02-30', '2026-2-01', '1999-12-31', '2101-01-01', '2026-13-01'])('rejeita data inexistente ou fora do contrato: %s', (valor) => {
    expect(validarDataAgenda(valor)).toBeDefined()
  })
  it.each(['2000-01-01', '2028-02-29', '2100-12-31'])('aceita data civil válida: %s', (valor) => {
    expect(validarDataAgenda(valor)).toBeUndefined()
  })
  it('muda o dia sem depender do fuso do navegador nem ultrapassar o contrato', () => {
    expect(mudarDiaAgenda('2027-01-01', -1)).toBe('2026-12-31')
    expect(mudarDiaAgenda('2028-02-28', 1)).toBe('2028-02-29')
    expect(mudarDiaAgenda('2000-01-01', -1)).toBe('2000-01-01')
    expect(mudarDiaAgenda('2100-12-31', 1)).toBe('2100-12-31')
  })
})
