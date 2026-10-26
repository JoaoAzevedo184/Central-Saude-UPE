import { describe, expect, it } from 'vitest'
import { trocaSenhaSchema } from './trocar-senha-validacao'

const dados = { senha_atual: 'Atual sintética', senha_nova: 'Nova sintética', confirmar_senha: 'Nova sintética' }
describe('RN-022 — validação da troca de senha', () => {
  it.each([
    { senha_atual: '' }, { senha_atual: 'a'.repeat(257) }, { senha_nova: '' },
    { senha_nova: 'a'.repeat(9) }, { senha_nova: '😀'.repeat(9) }, { senha_nova: 'a'.repeat(257) },
    { senha_nova: dados.senha_atual, confirmar_senha: dados.senha_atual }, { confirmar_senha: 'diferente' },
  ])('recusa campos inválidos sem enviar', (alteracao) => {
    expect(trocaSenhaSchema.safeParse({ ...dados, ...alteracao }).success).toBe(false)
  })
  it.each(['😀'.repeat(10), '😀'.repeat(256), ' '.repeat(10)])('aceita limites por code points sem trim', (senha) => {
    const entrada = { ...dados, senha_nova: senha, confirmar_senha: senha }
    expect(trocaSenhaSchema.parse(entrada)).toEqual(entrada)
  })
})
