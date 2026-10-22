import type { Location } from 'react-router'

export function estadoParaEntrar(location: Pick<Location, 'pathname' | 'search' | 'hash'>) {
  return { origem: `${location.pathname}${location.search}${location.hash}` }
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
