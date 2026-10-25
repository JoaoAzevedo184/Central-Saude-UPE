import type { components } from '../api/generated/schema'

export const rotaTrocarSenha = '/trocar-senha'

export function exigeTrocaDeSenha(
  dados: components['schemas']['LoginSaida'] | components['schemas']['EuSaida'] | null | undefined,
): boolean {
  return dados?.trocar_senha === true
}
