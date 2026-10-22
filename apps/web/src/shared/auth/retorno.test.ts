import { describe, expect, it } from 'vitest'
import { estadoParaEntrar, rotaAposLogin } from './retorno'

describe('ADR-003 — retorno após o login', () => {
  it('preserva caminho, busca e fragmento no estado da navegação', () => {
    const state = estadoParaEntrar({ pathname: '/equipe', search: '?data=2026-10-21', hash: '#agenda' })
    expect(rotaAposLogin(state)).toBe('/equipe?data=2026-10-21#agenda')
  })

  it.each([undefined, null, {}, { origem: 42 }, { origem: 'https://externo.example' },
    { origem: '//externo.example' }, { origem: '/\\externo.example' }, { origem: '/entrar?erro=1' },
    { origem: '/paciente/../entrar' }, { origem: '/\n/externo.example' },
    { origem: '/paciente/..//externo.example' }, { origem: '/ENTRAR/' },
  ])('recusa destino externo, ausente ou que repita o login: %j', (state) => {
    expect(rotaAposLogin(state)).toBe('/')
  })
})
