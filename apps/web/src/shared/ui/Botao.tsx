import type { ComponentProps } from 'react'

export function Botao({ children, carregando, variante = 'principal', disabled, ...props }:
  ComponentProps<'button'> & { carregando?: boolean; variante?: 'principal' | 'secundario' }) {
  return <button {...props} className={`botao botao-${variante}`} disabled={disabled || carregando} aria-busy={carregando || undefined}>
    {carregando ? <><span className="carregando" aria-hidden="true" />Aguarde…</> : children}
  </button>
}
