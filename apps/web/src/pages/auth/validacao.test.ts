import { describe, expect, it } from 'vitest'
import { cadastroSchema, cnsValido, cpfValido, loginSchema, nascimentoValido } from './validacao'
import { mascaraCns, mascaraCpf, mascaraIdentificador, mascaraTelefone, soDigitos } from '../../shared/mascaras'
import documentos from '../../test/fixtures/documentos-sinteticos.json'

describe('UC-001 — documentos e validações iguais ao servidor', () => {
  it('aceita documentos gerados pelos utilitários sintéticos existentes', () => {
    expect(cpfValido(documentos.cpf)).toBe(true)
    for (const cns of [...documentos.cns_definitivos, ...documentos.cns_provisorios]) expect(cnsValido(cns)).toBe(true)
  })
  it.each(['', '00000000000', '11111111111', '00000000190', '123'])('rejeita CPF inválido: %s', (cpf) => {
    expect(cpfValido(cpf)).toBe(false)
  })
  it.each(['', '000000000000000', '300000000000000', '100000000000000', '700000000000001', '123'])('rejeita CNS inválido: %s', (cns) => {
    expect(cnsValido(cns)).toBe(false)
  })
  it.each([
    ['2026-10-21', true], ['2026-10-22', false], ['1895-10-22', true], ['1895-10-21', false],
    ['1896-10-21', true], ['2024-02-29', true], ['2025-02-29', false], ['2025-02-30', false], ['', false],
  ])('confere data e idade até 130 anos completos: %s', (data, valido) => {
    expect(nascimentoValido(data, '2026-10-21')).toBe(valido)
  })
  it('aplica limites do servidor sem exigir 10 caracteres no login', () => {
    expect(loginSchema.safeParse({ identificador: documentos.cpf, senha: 'a' }).success).toBe(true)
    expect(loginSchema.safeParse({ identificador: 'a'.repeat(255), senha: 'a' }).success).toBe(false)
    const dados = { nome: 'Pessoa Sintética', cpf: documentos.cpf, cns: documentos.cns, data_nascimento: '2000-01-01',
      sexo: '' as const, municipio: 'Olinda', telefone: '81900000000', email: '', senha: 'Sintetica!123', confirmar_senha: 'Sintetica!123', aceite_termo: true, aceite_lembrete_email: false }
    expect(cadastroSchema.safeParse(dados).success).toBe(true)
    for (const alteracao of [
      { nome: 'a' }, { nome: 'a'.repeat(201) }, { municipio: 'a' }, { municipio: 'a'.repeat(101) },
      { telefone: '123' }, { telefone: '1'.repeat(14) }, { email: 'invalido' }, { email: 'a'.repeat(255) },
      { senha: 'curta' }, { senha: 'a'.repeat(257) }, { confirmar_senha: 'diferente' }, { aceite_termo: false },
      { aceite_lembrete_email: true },
    ]) expect(cadastroSchema.safeParse({ ...dados, ...alteracao }).success).toBe(false)
    expect(cadastroSchema.safeParse({ ...dados, email: 'sintetica@exemplo.test', aceite_lembrete_email: true }).success).toBe(true)
  })
})

describe('UC-001 — máscaras sem perder os números', () => {
  it('formata CPF, CNS e telefone, incluindo código do país', () => {
    expect(mascaraCpf(documentos.cpf)).toBe('000.000.001-91')
    expect(soDigitos(mascaraCns(documentos.cns))).toBe(documentos.cns)
    for (const numero of ['8190000000', '81900000000', '5581900000000']) expect(soDigitos(mascaraTelefone(numero))).toBe(numero)
    expect(mascaraIdentificador('equipe@exemplo.test')).toBe('equipe@exemplo.test')
    expect(mascaraIdentificador(documentos.cpf)).toBe(mascaraCpf(documentos.cpf))
  })
})
