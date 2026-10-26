import { z } from 'zod'

const comprimento = (valor: string) => [...valor].length
const mensagens = {
  atualObrigatoria: 'Informe sua senha atual.',
  atualIncorreta: 'Senha atual incorreta.',
  novaObrigatoria: 'Informe a nova senha.',
  novaCurta: 'A nova senha precisa ter pelo menos 10 caracteres.',
  novaDiferente: 'A nova senha precisa ser diferente da senha atual.',
  limite: 'Use até 256 caracteres.',
} as const

// A localização é validada pelo adaptador compartilhado. Aqui só interpretamos
// códigos conhecidos, nunca msg/detail ou valores de senha do servidor.
export function mensagemErroTrocaSenha(campo: string, erro: { type: string }): string | undefined {
  if (campo !== 'senha_atual' && campo !== 'senha_nova') return
  switch (erro.type) {
    case 'value_error': return campo === 'senha_atual' ? mensagens.atualIncorreta : mensagens.novaDiferente
    case 'too_short':
    case 'string_too_short': return campo === 'senha_atual' ? mensagens.atualObrigatoria : mensagens.novaCurta
    case 'missing': return campo === 'senha_atual' ? mensagens.atualObrigatoria : mensagens.novaObrigatoria
    case 'too_long':
    case 'string_too_long': return mensagens.limite
    default: return undefined
  }
}

export const trocaSenhaSchema = z.object({
  senha_atual: z.string().refine((valor) => comprimento(valor) > 0, mensagens.atualObrigatoria)
    .refine((valor) => comprimento(valor) <= 256, mensagens.limite),
  senha_nova: z.string().refine((valor) => comprimento(valor) >= 10, mensagens.novaCurta)
    .refine((valor) => comprimento(valor) <= 256, mensagens.limite),
  confirmar_senha: z.string(),
}).refine((dados) => dados.senha_nova !== dados.senha_atual, {
  path: ['senha_nova'], message: mensagens.novaDiferente,
}).refine((dados) => dados.confirmar_senha === dados.senha_nova, {
  path: ['confirmar_senha'], message: 'As senhas precisam ser iguais.',
})
export type TrocaSenhaForm = z.infer<typeof trocaSenhaSchema>
