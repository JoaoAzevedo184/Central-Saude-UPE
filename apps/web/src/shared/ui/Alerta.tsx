import type { ReactNode } from 'react'

export function Alerta({ children }: { children: ReactNode }) {
  return <div role="alert" className="alerta">{children}</div>
}
