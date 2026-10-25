export function IndicadorEtapas({ etapa, nomes, rotulo = 'Etapas do cadastro' }: { etapa: number; nomes: readonly string[]; rotulo?: string }) {
  return <nav className="etapas" aria-label={rotulo}>
    <p aria-live="polite">Etapa {etapa + 1} de {nomes.length} — {nomes[etapa]}</p>
    <ol>{nomes.map((nome, indice) => <li key={nome} aria-current={indice === etapa ? 'step' : undefined}
      className={indice <= etapa ? 'etapa-atingida' : ''}><span className="sr-only">{nome}{indice < etapa ? ': concluída' : ''}</span></li>)}</ol>
  </nav>
}
