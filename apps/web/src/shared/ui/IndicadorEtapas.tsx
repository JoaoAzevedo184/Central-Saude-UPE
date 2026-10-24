export function IndicadorEtapas({ etapa, nomes }: { etapa: number; nomes: readonly string[] }) {
  return <nav className="etapas" aria-label="Etapas do cadastro">
    <p aria-live="polite">Etapa {etapa + 1} de {nomes.length} — {nomes[etapa]}</p>
    <ol>{nomes.map((nome, indice) => <li key={nome} aria-current={indice === etapa ? 'step' : undefined}
      className={indice <= etapa ? 'etapa-atingida' : ''}><span className="sr-only">{nome}{indice < etapa ? ': concluída' : ''}</span></li>)}</ol>
  </nav>
}
