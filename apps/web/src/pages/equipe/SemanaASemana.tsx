import { useEffect, useId, useRef, useState } from 'react'
import type { DadosIndicadores } from './api-indicadores'
import { diaMesCivil, inteiro } from './estado-indicadores'

export function SemanaASemana({ semanas, de, ate }: Pick<DadosIndicadores, 'semanas' | 'de' | 'ate'>) {
  const titulo = useId()
  const rolagem = useRef<HTMLDivElement>(null)
  const [larguraDisponivel, setLarguraDisponivel] = useState(520)
  useEffect(() => {
    if (!rolagem.current || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entrada]) => { if (entrada) setLarguraDisponivel(entrada.contentRect.width) })
    observer.observe(rolagem.current)
    return () => observer.disconnect()
  }, [])
  const maximo = Math.ceil(Math.max(2, ...semanas.flatMap((s) => [s.solicitacoes_criadas, s.confirmadas])) / 2) * 2
  const largura = Math.max(larguraDisponivel, 520, semanas.length * 90 + 50)
  const passo = (largura - 50) / Math.max(1, semanas.length)
  const cruzaAno = de.slice(0, 4) !== ate.slice(0, 4)
  const rotuloSemana = (semana: string) => `${diaMesCivil(semana)}${cruzaAno ? `/${semana.slice(2, 4)}` : ''}`
  const intervalo = semanas.length ? `, de ${rotuloSemana(semanas[0]!.semana)} a ${rotuloSemana(semanas[semanas.length - 1]!.semana)}` : ''
  return <section className="bloco-indicadores" aria-labelledby={titulo}>
    <h2 id={titulo}>Semana a semana</h2>
    <p>Propostas feitas nesta semana que já foram confirmadas. As semanas começam na segunda-feira, em Recife; as pontas consideram apenas os dias do período.</p>
    <ul className="legenda-indicadores"><li><span className="amostra-criadas" />Pedidos criados</li><li><span className="amostra-confirmadas" />Propostas confirmadas</li></ul>
    <div className="rolagem-indicadores" ref={rolagem} tabIndex={0} role="region" aria-label="Gráfico semanal, com rolagem horizontal">
      <svg width={largura} height="250" viewBox={`0 0 ${largura} 250`} role="img" aria-label={`Pedidos criados e Propostas confirmadas em ${semanas.length} semanas${intervalo}. Propostas feitas nesta semana que já foram confirmadas. Os mesmos números estão disponíveis em Ver tabela.`}>
        {[0, 0.5, 1].map((fracao) => <g key={fracao} className="escala-indicadores"><line x1="45" x2={largura} y1={200 - fracao * 160} y2={200 - fracao * 160} /><text x="38" y={205 - fracao * 160} textAnchor="end">{inteiro(Math.ceil(maximo * fracao))}</text></g>)}
        {semanas.map((semana, i) => <g key={semana.semana}>
          <rect className="barra-criadas" data-valor={semana.solicitacoes_criadas} x={50 + i * passo + passo / 2 - 24} y={200 - semana.solicitacoes_criadas / maximo * 160} width="20" height={semana.solicitacoes_criadas / maximo * 160}><title>{rotuloSemana(semana.semana)}: {inteiro(semana.solicitacoes_criadas)} pedidos criados</title></rect>
          <rect className="barra-confirmadas" data-valor={semana.confirmadas} x={50 + i * passo + passo / 2} y={200 - semana.confirmadas / maximo * 160} width="20" height={semana.confirmadas / maximo * 160}><title>{rotuloSemana(semana.semana)}: {inteiro(semana.confirmadas)} Propostas confirmadas</title></rect>
          <text x={50 + i * passo + passo / 2} y="230" textAnchor="middle">{rotuloSemana(semana.semana)}</text>
        </g>)}
      </svg>
    </div>
    <details className="tabela-indicadores"><summary>Ver tabela</summary>
      <div className="rolagem-indicadores" tabIndex={0} role="region" aria-label="Tabela semanal, com rolagem horizontal"><table>
        <caption>Pedidos criados e Propostas confirmadas por semana no período selecionado</caption>
        <thead><tr><th scope="col">Semana</th><th scope="col">Pedidos criados</th><th scope="col">Propostas confirmadas</th></tr></thead>
        <tbody>{semanas.map((semana) => <tr key={semana.semana}><th scope="row"><time dateTime={semana.semana}>{rotuloSemana(semana.semana)}</time></th><td>{inteiro(semana.solicitacoes_criadas)}</td><td>{inteiro(semana.confirmadas)}</td></tr>)}</tbody>
      </table></div>
    </details>
  </section>
}
