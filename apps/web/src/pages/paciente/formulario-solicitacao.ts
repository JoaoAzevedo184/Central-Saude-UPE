import type { CriterioPaciente, NovoPedido } from './api'

// Modelo de edição em memória: os controles usam texto até a montagem do DTO gerado.
export interface FormularioSolicitacao {
  fila_id: string
  origem_encaminhamento: string
  turno_preferido: NovoPedido['turno_preferido']
  respostas: { criterio_id: string; valor: string }[]
}
export const turnos = { MANHA: 'Manhã', TARDE: 'Tarde', QUALQUER: 'Tanto faz' } as const

const decimalSimples = /^-?\d+(?:[.,]\d+)?$/
const numeroDecimal = (texto: string) => Number(texto.replace(',', '.'))

export function validarResposta(criterio: CriterioPaciente, valor: string): true | string {
  if (valor === '') return true
  if (criterio.tipo === 'SIM_NAO') return ['sim', 'nao'].includes(valor) || 'Escolha Sim ou Não.'
  if (criterio.tipo === 'OPCAO') return (valor.length <= 200 && Boolean(criterio.opcoes?.includes(valor))) || 'Escolha uma das opções disponíveis.'
  // Sem limite, faixa ou arredondamento: o contrato aceita números inteiros e decimais.
  return (decimalSimples.test(valor) && Number.isFinite(numeroDecimal(valor))) || 'Informe um número válido ou deixe em branco.'
}

export function montarPedido(dados: FormularioSolicitacao, criterios: CriterioPaciente[]) {
  const indices: number[] = []
  const respostas: NonNullable<NovoPedido['respostas']> = []
  criterios.forEach((criterio, indice) => {
    const texto = dados.respostas[indice]?.valor ?? ''
    if (texto === '') return
    indices.push(indice)
    respostas.push({ criterio_id: criterio.id, valor: criterio.tipo === 'SIM_NAO' ? texto === 'sim' : criterio.tipo === 'NUMERO' ? numeroDecimal(texto) : texto })
  })
  const payload: NovoPedido = { fila_id: dados.fila_id, origem_encaminhamento: dados.origem_encaminhamento.trim(), turno_preferido: dados.turno_preferido, respostas }
  return { payload, indices }
}
