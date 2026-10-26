import type { ReactNode } from 'react'
import { Botao } from '../shared/ui/Botao'

export function TrocarSenhaLayout({ children, sair, saindo }: { children: ReactNode; sair: () => void; saindo: boolean }) {
  return <div className="troca-senha">
    <header className="troca-senha-marca"><strong>Central de Teleagendamento</strong><span>Complexo Hospitalar da UPE</span></header>
    <main className="troca-senha-conteudo">
      {children}
      <div className="troca-senha-saida"><Botao type="button" variante="secundario" carregando={saindo} onClick={sair}>Sair</Botao></div>
    </main>
  </div>
}
