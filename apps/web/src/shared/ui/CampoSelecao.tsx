import { useId, type ComponentPropsWithRef, type ReactNode } from 'react'

export function CampoSelecao({ rotulo, ajuda, erro, id, children, ...props }: ComponentPropsWithRef<'select'> & {
  rotulo: string; ajuda?: ReactNode; erro?: string
}) {
  const gerado = useId()
  const campoId = id ?? gerado
  const descricao = [props['aria-describedby'], ajuda && `${campoId}-ajuda`, erro && `${campoId}-erro`].filter(Boolean).join(' ')
  return <div className="campo">
    <label htmlFor={campoId}>{rotulo}</label>
    <select {...props} id={campoId} aria-invalid={erro ? true : undefined} aria-describedby={descricao || undefined}>{children}</select>
    {ajuda && <div className="campo-ajuda" id={`${campoId}-ajuda`}>{ajuda}</div>}
    {erro && <p className="campo-erro" id={`${campoId}-erro`}>{erro}</p>}
  </div>
}
