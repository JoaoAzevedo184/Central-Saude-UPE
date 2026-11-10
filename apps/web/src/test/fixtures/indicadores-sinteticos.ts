import type { DadosIndicadores } from '../../pages/equipe/api-indicadores'

export const resumoSintetico: DadosIndicadores['totais'] = {
  confirmadas: 29, recusadas: 9, expiradas: 2, propostas_encerradas: 40, propostas_canceladas_sem_resposta: 1,
  taxa_confirmacao: .725, taxa_recusa: .225, taxa_expiracao: .05, realizadas: 9, faltas: 1, taxa_faltas: .1,
  solicitacoes_criadas: 1234, desistencias: 12, taxa_desistencia: .0097,
  vagas_ofertadas: 80, vagas_ocupadas: 50, vagas_reaproveitadas: 14, vagas_perdidas: 8,
}
export function indicadoresSinteticos(extra: Partial<DadosIndicadores> = {}): DadosIndicadores {
  return {
    de: '2026-10-13', ate: '2026-11-09', unidade_id: null, fila_id: null,
    totais: { ...resumoSintetico }, tempo_de_espera: { confirmacoes: 21, mediana_dias: 4.2, p90_dias: 12.8 },
    fila_atual: { VERMELHO: 15, AMARELO: 34, VERDE: 52 },
    semanas: [
      { ...resumoSintetico, semana: '2026-11-02', solicitacoes_criadas: 12, confirmadas: 8 },
      { ...resumoSintetico, semana: '2026-11-09', solicitacoes_criadas: 18, confirmadas: 11 },
    ], ...extra,
  }
}
