import { useState } from 'react'
import { Campo } from './Campo'
import type { CampoProps } from './Campo'
import { editarIdentificador, mascaraIdentificador } from '../mascaras'

export function CampoIdentificador({ onChange, ...props }: Omit<CampoProps, 'value' | 'defaultValue'>) {
  const [entrada, setEntrada] = useState('')
  return <Campo {...props} value={mascaraIdentificador(entrada)} onChange={(event) => {
    const original = editarIdentificador(entrada, event.target.value)
    setEntrada(original)
    event.target.value = mascaraIdentificador(original)
    onChange?.(event)
  }} />
}
