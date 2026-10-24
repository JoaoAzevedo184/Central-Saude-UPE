import type { ReactNode } from 'react'

export function LayoutAutenticacao({ cadastro = false, children }: { cadastro?: boolean; children: ReactNode }) {
  return <div className={`autenticacao autenticacao-${cadastro ? 'cadastro' : 'login'}`}>
    <aside className="institucional" aria-label="Central de Agendamento">
      <div className="marca"><span className="marca-simbolo" aria-hidden="true">✚</span><div>
        <strong>Central de Agendamento</strong><span>Complexo Hospitalar da UPE</span>
      </div></div>
      <div className="institucional-texto">
        <h2>{cadastro ? 'Seu primeiro passo para acompanhar seus atendimentos.' : 'Seus atendimentos no Complexo Hospitalar da UPE.'}</h2>
        <p>{cadastro ? 'Tenha em mãos seu CPF e o número do cartão do SUS.' : 'Acompanhe e confirme suas consultas no CISAM, HUOC e PROCAPE.'}</p>
      </div>
      <p className="aviso-prototipo">Protótipo acadêmico. Use somente dados fictícios.</p>
    </aside>
    <main className="autenticacao-principal"><div className="formulario-autenticacao">{children}</div></main>
  </div>
}
