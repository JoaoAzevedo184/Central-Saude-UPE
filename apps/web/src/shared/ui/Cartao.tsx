import type { ComponentProps } from 'react'

export function Cartao({ className = '', ...props }: ComponentProps<'article'>) {
  return <article {...props} className={`cartao ${className}`} />
}
