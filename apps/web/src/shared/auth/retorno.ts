import type { Location } from 'react-router'
import type { Papel } from './session'

export function rotaInicial(papel: Papel): string {
  return papel === 'PACIENTE' ? '/paciente' : '/equipe/fila'
}

// Guarda só o pathname: query e hash não vão para o history.state (AM-003).
export function estadoParaEntrar(location: Pick<Location, 'pathname'>) {
  return { origem: location.pathname }
}

// A futura tela de login consome o state do Router após autenticar, sem persistir dados no navegador.
export function rotaAposLogin(state: unknown): string {
  const origem = state && typeof state === 'object' && 'origem' in state ? state.origem : undefined
  if (typeof origem !== 'string' || !origem.startsWith('/') || origem.startsWith('//') || /[\\\s]/.test(origem)) return '/'
  const url = new URL(origem, 'http://app.local')
  if (url.origin !== 'http://app.local' || url.pathname.startsWith('//')
    || url.pathname.replace(/\/+$/, '').toLowerCase() === '/entrar') return '/'
  return `${url.pathname}${url.search}${url.hash}`
}
