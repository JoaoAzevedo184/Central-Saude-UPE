import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { Link, Outlet, useLocation, useOutletContext } from 'react-router'
import type { Papel, Sessao } from '../shared/auth/session'
import { useSair } from '../shared/auth/useSair'
import { Botao } from '../shared/ui/Botao'
import { lerEstadoFila, paramsFila } from '../pages/equipe/estado-fila'

const papeis: Record<Papel, string> = { PACIENTE: 'Paciente', ATENDENTE: 'Atendente', GESTOR: 'Gestor', ADMIN: 'Administrador' }
// Novas telas entram aqui com os papéis permitidos quando a rota existir.
const itensMenu: { texto: string; rota: string; destino: (queryFila: string) => string; papeis: readonly Papel[] }[] = [
  { texto: 'Fila', rota: '/equipe/fila', destino: (query) => `/equipe/fila?${query}`, papeis: ['ATENDENTE', 'GESTOR', 'ADMIN'] },
  { texto: 'Indicadores', rota: '/equipe/indicadores', destino: () => '/equipe/indicadores', papeis: ['GESTOR', 'ADMIN'] },
]
export function EquipeLayout() {
  const sessao = useOutletContext<Sessao>()
  const location = useLocation()
  const { sair, saindo } = useSair()
  const [aberto, setAberto] = useState(false)
  const menu = useRef<HTMLButtonElement>(null)
  const main = useRef<HTMLElement>(null)
  const focarConteudo = useRef(false)
  useEffect(() => {
    if (!focarConteudo.current) return
    focarConteudo.current = false
    main.current?.focus()
  }, [location.key])
  function fechar() { setAberto(false); menu.current?.focus() }
  function navegar(event: MouseEvent<HTMLAnchorElement>) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    setAberto(false); focarConteudo.current = true
  }
  const naFila = location.pathname === '/equipe/fila' || location.pathname.startsWith('/equipe/solicitacoes/')
  const query = paramsFila(lerEstadoFila(new URLSearchParams(naFila ? location.search : ''))).toString()
  return <div className="area-equipe">
    <a className="pular-conteudo" href="#conteudo-equipe">Pular para o conteúdo</a>
    <header className="lateral-equipe" onKeyDown={(event) => { if (aberto && event.key === 'Escape') fechar() }}>
      <div className="marca-equipe"><Link to="/equipe/fila" onClick={navegar}><span className="marca-simbolo" aria-hidden="true">+</span><span>Central de Teleagendamento<small>Complexo Hospitalar da UPE</small></span></Link>
        <button type="button" className="botao botao-secundario menu-equipe" ref={menu} aria-controls="menu-equipe" aria-expanded={aberto} onClick={() => aberto ? fechar() : setAberto(true)}>Menu</button>
      </div>
      <div id="menu-equipe" className={`conteudo-menu-equipe${aberto ? ' aberto' : ''}`}>
        <nav aria-label="Área da equipe">{itensMenu.filter((item) => item.papeis.includes(sessao.papel)).map((item) =>
          <Link key={item.rota} to={item.destino(query)} aria-current={location.pathname === item.rota || (item.rota === '/equipe/fila' && location.pathname.startsWith('/equipe/solicitacoes/')) ? 'page' : undefined} onClick={navegar}>{item.texto}</Link>)}
        </nav>
        <div className="identificacao-equipe"><p>{papeis[sessao.papel]}</p><Botao variante="secundario" carregando={saindo} onClick={() => void sair()}>Sair</Botao></div>
      </div>
    </header>
    <main id="conteudo-equipe" className="equipe-principal" aria-label="Área da equipe" tabIndex={-1} ref={main}><Outlet context={sessao} /></main>
  </div>
}
