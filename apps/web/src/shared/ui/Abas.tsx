import { useId } from 'react'
import type { ReactNode } from 'react'

export function Abas<T extends string>({ itens, valor, aoMudar, children }: {
  itens: readonly { valor: T; texto: string }[]; valor: T; aoMudar: (valor: T) => void; children: ReactNode
}) {
  const id = useId()
  return <>
    <div className="abas" role="tablist" aria-label="Situação dos pedidos">
      {itens.map((item, indice) => <button key={item.valor} id={`${id}-${item.valor}`} role="tab" type="button"
        aria-selected={item.valor === valor} aria-controls={`${id}-painel`} tabIndex={item.valor === valor ? 0 : -1}
        onClick={() => aoMudar(item.valor)} onKeyDown={(event) => {
          const destinos: Record<string, number> = { ArrowRight: (indice + 1) % itens.length,
            ArrowLeft: (indice - 1 + itens.length) % itens.length, Home: 0, End: itens.length - 1 }
          const destino = destinos[event.key]
          if (destino === undefined) return
          event.preventDefault()
          const item = itens[destino]
          if (!item) return
          document.getElementById(`${id}-${item.valor}`)?.focus()
          aoMudar(item.valor)
        }}>{item.texto}</button>)}
    </div>
    <div id={`${id}-painel`} role="tabpanel" aria-labelledby={`${id}-${valor}`} tabIndex={0}>{children}</div>
  </>
}
