import { describe, expect, it } from 'vitest'
import type { Location } from 'react-router'
import { estadoParaEntrar, rotaAposLogin } from './retorno'

describe('ADR-003 — retorno após o login', () => {
  it('guarda só o caminho no estado da navegação, sem busca nem fragmento', () => {
    const state = estadoParaEntrar({ pathname: '/equipe', search: '?data=2026-10-21', hash: '#agenda' } as Location)
    expect(state).toEqual({ origem: '/equipe' })
    expect(rotaAposLogin(state)).toBe('/equipe')
  })

  it.each([undefined, null, {}, { origem: 42 }, { origem: 'https://externo.example' },
    { origem: '//externo.example' }, { origem: '/\\externo.example' }, { origem: '/entrar?erro=1' },
    { origem: '/paciente/../entrar' }, { origem: '/\n/externo.example' },
    { origem: '/paciente/..//externo.example' }, { origem: '/ENTRAR/' },
  ])('recusa destino externo, ausente ou que repita o login: %j', (state) => {
    expect(rotaAposLogin(state)).toBe('/')
  })
})
