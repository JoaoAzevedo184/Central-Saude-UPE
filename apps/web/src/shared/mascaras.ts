export const soDigitos = (valor: string) => valor.replace(/\D/g, '')

export function mascaraCpf(valor: string): string {
  return soDigitos(valor).slice(0, 11)
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/(\d{3})\.(\d{3})\.(\d{3})(\d)/, '$1.$2.$3-$4')
}

export function mascaraIdentificador(valor: string): string {
  return /^\d{0,11}$/.test(valor) ? mascaraCpf(valor) : valor
}

// Traduz a edição do texto visível para a entrada original, sem guardar os
// pontos inseridos automaticamente. Assim 2026 seguido de @ continua 2026@.
export function editarIdentificador(anterior: string, visivel: string): string {
  if (!/^\d{0,11}$/.test(anterior)) return visivel
  const formatado = mascaraIdentificador(anterior)
  let inicio = 0
  while (inicio < formatado.length && inicio < visivel.length && formatado[inicio] === visivel[inicio]) inicio++
  let fimAnterior = formatado.length
  let fimNovo = visivel.length
  while (fimAnterior > inicio && fimNovo > inicio && formatado[fimAnterior - 1] === visivel[fimNovo - 1]) { fimAnterior--; fimNovo-- }
  let de = soDigitos(formatado.slice(0, inicio)).length
  const ate = soDigitos(formatado.slice(0, fimAnterior)).length
  if (de === ate && fimNovo === inicio && fimAnterior > inicio) de = Math.max(0, de - 1)
  return anterior.slice(0, de) + visivel.slice(inicio, fimNovo) + anterior.slice(ate)
}

export function mascaraCns(valor: string): string {
  return soDigitos(valor).slice(0, 15).replace(/^(\d{3})(\d{0,4})(\d{0,4})(\d{0,4})$/, (_, a, b, c, d) =>
    [a, b, c, d].filter(Boolean).join(' '))
}

export function mascaraTelefone(valor: string): string {
  const digitos = soDigitos(valor).slice(0, 13)
  // Acima de 11 dígitos, preserva também o código do país.
  if (digitos.length > 11) return `+${digitos.slice(0, -11)} ${mascaraTelefone(digitos.slice(-11))}`
  if (digitos.length <= 2) return digitos ? `(${digitos}` : ''
  const local = digitos.slice(2)
  const corte = local.length > 8 ? 5 : 4
  return `(${digitos.slice(0, 2)}) ${local.slice(0, corte)}${local.length > corte ? `-${local.slice(corte)}` : ''}`
}
