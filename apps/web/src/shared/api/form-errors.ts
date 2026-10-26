import type { FieldPath, FieldValues, UseFormSetError } from 'react-hook-form'
import type { components } from './generated/schema'
import { ApiError } from './problem-details'

type ErroDeCampo = components['schemas']['ErroDeCampo']

function erroDeCampo(value: unknown): value is ErroDeCampo {
  if (!value || typeof value !== 'object') return false
  const error = value as Partial<ErroDeCampo>
  return Array.isArray(error.loc) && error.loc.every((part) =>
    typeof part === 'string' || (typeof part === 'number' && Number.isInteger(part) && part >= 0))
    && typeof error.msg === 'string' && error.msg.trim().length > 0 && typeof error.type === 'string'
}

// A lista explícita impede que parâmetros de query/path ou campos extras virem campos do formulário.
export function aplicarErrosDeValidacao<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  campos: readonly NoInfer<FieldPath<T>>[],
  mensagemDoCampo?: (campo: NoInfer<FieldPath<T>>, erro: ErroDeCampo) => string | undefined,
): boolean {
  if (!(error instanceof ApiError) || error.problem.status !== 422) return false
  const errors: unknown[] = Array.isArray(error.problem.errors) ? error.problem.errors : []
  const aplicados = new Set<string>()
  let erroGlobal = errors.length === 0
  for (const item of errors) {
    if (!erroDeCampo(item)) {
      erroGlobal = true
      continue
    }
    const partes = item.loc.slice(1)
    const campo = partes.join('.')
    const cadastrado = campos.find((name) => name === campo)
    if (item.loc[0] !== 'body' || !cadastrado || partes.some((part) =>
      ['__proto__', 'prototype', 'constructor'].includes(String(part)))) {
      erroGlobal = true
      continue
    }
    if (aplicados.has(campo)) continue
    // Com mapeamento local, um código desconhecido vai ao erro global seguro.
    // Não recuperar item.msg como fallback: pode conter texto técnico ou dados.
    const mensagem = mensagemDoCampo ? mensagemDoCampo(cadastrado, item) : item.msg
    if (!mensagem) { erroGlobal = true; continue }
    setError(cadastrado, { type: 'server', message: mensagem }, { shouldFocus: aplicados.size === 0 })
    aplicados.add(campo)
  }
  if (erroGlobal) setError('root.server', { type: 'server', message: error.message })
  return true
}
