export const rotaTrocarSenha = '/trocar-senha'

// Compatibilidade em runtime até o novo contrato chegar ao OpenAPI do worktree.
// Não substitui nem estende à mão os DTOs gerados.
export function exigeTrocaDeSenha(dados: unknown): boolean {
  return dados !== null && typeof dados === 'object'
    && 'trocar_senha' in dados && dados.trocar_senha === true
}
