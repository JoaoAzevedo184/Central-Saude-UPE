import { Botao } from './Botao'

export function Paginacao({ total, limite, pagina, aoMudar }: {
  total: number; limite: number; pagina: number; aoMudar: (pagina: number) => void
}) {
  const paginas = Math.max(1, Math.ceil(total / limite))
  if (paginas <= 1) return null
  return <nav className="paginacao" aria-label="Páginas dos seus pedidos">
    <Botao variante="secundario" disabled={pagina === 0} onClick={() => aoMudar(pagina - 1)}>Anterior</Botao>
    <span>Página {pagina + 1} de {paginas}</span>
    <Botao variante="secundario" disabled={pagina + 1 >= paginas} onClick={() => aoMudar(pagina + 1)}>Próxima</Botao>
  </nav>
}
