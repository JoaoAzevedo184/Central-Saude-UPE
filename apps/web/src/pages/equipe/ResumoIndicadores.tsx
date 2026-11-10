import { Cartao } from '../../shared/ui/Cartao'
import type { DadosIndicadores } from './api-indicadores'
import { dias, inteiro, porcentagem } from './estado-indicadores'

function SemDados({ valor }: { valor: number | null }) { return valor === null && <p className="nota-indicador">sem dados no período</p> }
export function ResumoIndicadores({ dados }: { dados: DadosIndicadores }) {
  const { totais: t, tempo_de_espera: espera } = dados
  return <div className="resumo-indicadores">
    <Cartao><h2>Taxa de confirmação</h2><p className="numero-indicador">{porcentagem(t.taxa_confirmacao)}</p><SemDados valor={t.taxa_confirmacao} />
      <p>Propostas feitas no período e confirmadas, entre confirmadas, recusadas e expiradas.</p></Cartao>
    <Cartao><h2>Taxa de faltas</h2><p className="numero-indicador">{porcentagem(t.taxa_faltas)}</p><SemDados valor={t.taxa_faltas} />
      <p>Faltas entre consultas realizadas e faltas, pela data da consulta.</p></Cartao>
    <Cartao className="espera-indicadores"><h2>Tempo de espera</h2>
      <dl><div><dt>Mediana</dt><dd className="numero-indicador">{dias(espera.mediana_dias)}</dd></div><div><dt>P90</dt><dd className="numero-indicador">{dias(espera.p90_dias)}</dd></div></dl>
      <SemDados valor={espera.mediana_dias} /><p>{inteiro(espera.confirmacoes)} confirmações usadas.</p>
      <p>Da entrada na fila à primeira confirmação, quando ela ocorreu no período. Metade esperou até a mediana; 90% até o P90.</p></Cartao>
    <Cartao><h2>Vagas</h2><dl>
      <div><dt>Vagas reaproveitadas</dt><dd className="numero-indicador">{inteiro(t.vagas_reaproveitadas)}</dd></div>
      <div><dt>Vagas perdidas</dt><dd className="numero-indicador">{inteiro(t.vagas_perdidas)}</dd></div>
    </dl><p>Reaproveitadas: uma proposta foi desfeita e outro pedido confirmou. Perdidas: vagas do período já iniciadas sem agendamento confirmado, realizado ou com falta.</p></Cartao>
    <Cartao><h2>Pedidos</h2><dl>
      <div><dt>Pedidos criados</dt><dd className="numero-indicador">{inteiro(t.solicitacoes_criadas)}</dd></div>
      <div><dt>Desistências</dt><dd className="numero-indicador">{inteiro(t.desistencias)}</dd></div>
    </dl><p>Pedidos criados no período e, desses pedidos, os cancelados pelo paciente com motivo.</p></Cartao>
  </div>
}
