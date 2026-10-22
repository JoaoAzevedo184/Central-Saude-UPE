import type { components } from './generated/schema'

type Problema = components['schemas']['Problema']
// O backend pode omitir os campos opcionais; extensões são validadas ao consumir.
export interface ProblemDetails extends Pick<Problema, 'type' | 'title' | 'status'> {
  detail?: Problema['detail']
  instance?: Problema['instance']
  [extension: string]: unknown
}

export const mensagensPorTipo: Readonly<Record<string, string>> = {
  '/problemas/cadastro-nao-concluido': 'Não foi possível criar sua conta. Confira seus dados ou procure ajuda da equipe.',
  '/problemas/credenciais-invalidas': 'Confira seu CPF ou e-mail e sua senha.',
  '/problemas/csrf-invalido': 'Não foi possível verificar esta ação. Atualize a página e tente novamente.',
  '/problemas/muitas-tentativas': 'Você tentou muitas vezes. Aguarde um pouco antes de tentar novamente.',
  '/problemas/nao-autenticado': 'Sua sessão terminou. Entre novamente para continuar.',
  '/problemas/nao-elegivel': 'Você não atende aos critérios desta fila. Confira as orientações da fila.',
  '/problemas/operacao-nao-permitida': 'Esta ação não está disponível para este atendimento.',
  '/problemas/proposta-expirada': 'O prazo para confirmar esta vaga terminou.',
  '/problemas/sem-consentimento': 'Aceite o termo de uso para continuar.',
  '/problemas/sem-permissao': 'Você não tem permissão para realizar esta ação.',
  '/problemas/solicitacao-duplicada': 'Você já tem um pedido aberto nesta fila.',
  '/problemas/tolerancia-nao-encerrada': 'Ainda é cedo para registrar a falta. Aguarde o prazo indicado.',
  '/problemas/transicao-invalida': 'Este atendimento mudou. Atualize a página para ver as ações disponíveis.',
}

export function mensagemDoProblema(problem: Pick<Problema, 'type' | 'status'>): string {
  if (Object.hasOwn(mensagensPorTipo, problem.type)) return mensagensPorTipo[problem.type]!
  if (problem.status === 422) return 'Confira os campos indicados e tente novamente.'
  if (problem.status === 404) return 'Não foi possível encontrar o que você procura.'
  return 'Não foi possível concluir. Tente novamente mais tarde.'
}

export class ApiError extends Error {
  constructor(readonly problem: ProblemDetails, readonly response: Response) {
    super(mensagemDoProblema(problem))
    this.name = 'ApiError'
  }
}

export async function erroDaResposta(response: Response): Promise<ApiError> {
  let data: Record<string, unknown> = {}
  if (response.headers.get('Content-Type')?.split(';')[0]?.trim() === 'application/problem+json') {
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && !Array.isArray(body)) {
        data = body as Record<string, unknown>
      }
    } catch { /* Respostas vazias ou inválidas usam a mensagem genérica. */ }
  }
  return new ApiError({
    ...data,
    type: typeof data.type === 'string' ? data.type : 'about:blank',
    title: typeof data.title === 'string' ? data.title : 'Falha na requisição',
    status: response.status,
    detail: typeof data.detail === 'string' ? data.detail : undefined,
  }, response)
}
