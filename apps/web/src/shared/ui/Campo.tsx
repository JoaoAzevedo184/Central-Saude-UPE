import { useId, useState } from 'react'
import type { ComponentPropsWithRef, ReactNode } from 'react'

export type CampoProps = ComponentPropsWithRef<'input'> & {
  rotulo: string
  ajuda?: ReactNode
  erro?: string
  sufixo?: ReactNode
}

export function Campo({ rotulo, ajuda, erro, sufixo, id, ...props }: CampoProps) {
  const gerado = useId()
  const campoId = id ?? gerado
  const descricao = [props['aria-describedby'], ajuda && `${campoId}-ajuda`, erro && `${campoId}-erro`].filter(Boolean).join(' ')
  return <div className="campo">
    <label htmlFor={campoId}>{rotulo}</label>
    <div className={sufixo ? 'campo-controle campo-com-sufixo' : 'campo-controle'}>
      <input {...props} id={campoId} aria-invalid={erro ? true : undefined} aria-describedby={descricao || undefined} />
      {sufixo}
    </div>
    {ajuda && <div className="campo-ajuda" id={`${campoId}-ajuda`}>{ajuda}</div>}
    {erro && <p className="campo-erro" id={`${campoId}-erro`}>{erro}</p>}
  </div>
}

export function CampoComMascara({ mascara, onChange, ...props }: CampoProps & { mascara: (valor: string) => string }) {
  return <Campo {...props} onChange={(event) => {
    event.target.value = mascara(event.target.value)
    onChange?.(event)
  }} />
}

export function CampoSenha(props: Omit<CampoProps, 'type' | 'sufixo'>) {
  const [visivel, setVisivel] = useState(false)
  const nome = props.autoComplete === 'new-password' && props.name === 'confirmar_senha' ? 'confirmação de senha' : 'senha'
  return <Campo {...props} type={visivel ? 'text' : 'password'} sufixo={
    <button className="mostrar-senha" type="button" aria-label={`${visivel ? 'Ocultar' : 'Mostrar'} ${nome}`}
      aria-pressed={visivel} onClick={() => setVisivel(!visivel)}>{visivel ? 'Ocultar' : 'Mostrar'}</button>
  } />
}
