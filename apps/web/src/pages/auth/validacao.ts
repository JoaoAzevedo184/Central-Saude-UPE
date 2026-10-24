import { z } from 'zod'
import type { FieldValues, Resolver, FieldErrors, FieldError } from 'react-hook-form'
import { soDigitos } from '../../shared/mascaras'

export function cpfValido(valor: string): boolean {
  const cpf = valor.replace(/[.\-\s]/g, '')
  if (!/^\d{11}$/.test(cpf) || new Set(cpf).size === 1) return false
  const digitos = [...cpf.slice(0, 9)].map(Number)
  for (const tamanho of [9, 10]) {
    const soma = digitos.reduce((total, digito, i) => total + digito * (tamanho + 1 - i), 0)
    digitos.push(soma % 11 < 2 ? 0 : 11 - soma % 11)
  }
  return digitos.join('') === cpf
}

export function cnsValido(valor: string): boolean {
  const cns = valor.replace(/[.\-\s]/g, '')
  if (!/^\d{15}$/.test(cns)) return false
  const soma = (numero: string) => [...numero].reduce((total, digito, i) => total + Number(digito) * (15 - i), 0)
  if ('789'.includes(cns.charAt(0))) return soma(cns) % 11 === 0
  if (!'12'.includes(cns.charAt(0))) return false
  const pis = cns.slice(0, 11)
  let dv = 11 - soma(pis) % 11
  if (dv === 11) dv = 0
  if (dv === 10) return cns === `${pis}001${11 - (soma(pis) + 2) % 11}`
  return cns === `${pis}000${dv}`
}

export function hojeRecife(): string {
  const partes = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Recife', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const parte = (tipo: string) => partes.find((item) => item.type === tipo)!.value
  return `${parte('year')}-${parte('month')}-${parte('day')}`
}

export function nascimentoValido(valor: string, hoje = hojeRecife()): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valor)) return false
  const data = new Date(`${valor}T12:00:00Z`)
  if (Number.isNaN(data.getTime()) || data.toISOString().slice(0, 10) !== valor || valor > hoje) return false
  const idade = Number(hoje.slice(0, 4)) - Number(valor.slice(0, 4)) - (hoje.slice(5) < valor.slice(5) ? 1 : 0)
  return idade <= 130
}

// Mesmo formato aceito por RegistroEntrada._email no servidor.
const emailValido = (valor: string) => !valor || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(valor)
export const loginSchema = z.object({
  identificador: z.string().trim().min(1, 'Informe seu CPF ou e-mail.').max(254, 'Use até 254 caracteres.'),
  senha: z.string().min(1, 'Informe sua senha.').max(256, 'Use até 256 caracteres.'),
})

export const cadastroSchema = z.object({
  nome: z.string().trim().min(2, 'Informe seu nome completo.').max(200, 'Use até 200 caracteres.'),
  cpf: z.string().refine(cpfValido, 'Confira os 11 números do CPF.'),
  cns: z.string().refine(cnsValido, 'Confira os 15 números do cartão do SUS.'),
  data_nascimento: z.string().refine((valor) => nascimentoValido(valor), 'Informe uma data válida, não futura, com idade até 130 anos.'),
  sexo: z.enum(['', 'FEMININO', 'MASCULINO']),
  municipio: z.string().trim().min(2, 'Informe seu município.').max(100, 'Use até 100 caracteres.'),
  telefone: z.string().refine((valor) => /^\d{10,13}$/.test(soDigitos(valor)), 'Informe o telefone com DDD, de 10 a 13 números.'),
  email: z.string().trim().max(254, 'Use até 254 caracteres.').refine(emailValido, 'Informe um e-mail válido ou deixe em branco.'),
  senha: z.string().min(10, 'Crie uma senha com pelo menos 10 caracteres.').max(256, 'Use até 256 caracteres.'),
  confirmar_senha: z.string(),
  aceite_termo: z.boolean().refine((valor) => valor, 'Leia e aceite o termo para criar sua conta.'),
  aceite_lembrete_email: z.boolean(),
}).refine((dados) => dados.senha === dados.confirmar_senha, { path: ['confirmar_senha'], message: 'As senhas precisam ser iguais.' })
  .refine((dados) => !dados.aceite_lembrete_email || Boolean(dados.email), { path: ['aceite_lembrete_email'], message: 'Informe um e-mail para receber lembretes.' })

export type LoginForm = z.infer<typeof loginSchema>
export type CadastroForm = z.infer<typeof cadastroSchema>

// O resolver mantém somente o primeiro erro de cada campo, como o adaptador 422.
export function resolverZod<T extends FieldValues>(schema: z.ZodType<T>): Resolver<T> {
  return (values) => {
    const resultado = schema.safeParse(values)
    if (resultado.success) return { values: resultado.data, errors: {} }
    const erros: Record<string, FieldError> = {}
    for (const issue of resultado.error.issues) {
      const campo = issue.path.join('.')
      if (!erros[campo]) erros[campo] = { type: 'validate', message: issue.message }
    }
    return { values: {}, errors: erros as FieldErrors<T> }
  }
}
