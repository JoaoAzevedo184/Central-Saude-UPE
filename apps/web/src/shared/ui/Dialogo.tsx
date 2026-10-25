import { useEffect, useId, useRef } from 'react'
import type { ReactNode } from 'react'

export function Dialogo({ titulo, children, aoFechar }: { titulo: string; children: ReactNode; aoFechar: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => {
    const anterior = document.activeElement
    const dialogo = ref.current!
    dialogo.showModal()
    dialogo.querySelector<HTMLElement>('[data-foco-inicial]')?.focus()
    return () => {
      dialogo.close()
      if (anterior instanceof HTMLElement && anterior.isConnected) anterior.focus()
    }
  }, [])
  return <dialog ref={ref} className="dialogo" aria-labelledby={id} onCancel={(event) => { event.preventDefault(); aoFechar() }}
    onKeyDown={(event) => {
      if (event.key === 'Escape') { event.preventDefault(); aoFechar(); return }
      if (event.key !== 'Tab') return
      const alvos = Array.from(ref.current!.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], [tabindex="0"]'))
      const primeiro = alvos[0], ultimo = alvos.at(-1)
      if (event.shiftKey && document.activeElement === primeiro) { event.preventDefault(); ultimo?.focus() }
      else if (!event.shiftKey && document.activeElement === ultimo) { event.preventDefault(); primeiro?.focus() }
    }}>
    <h2 id={id}>{titulo}</h2>{children}
  </dialog>
}
