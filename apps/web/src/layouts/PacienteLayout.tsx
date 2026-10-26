import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { useSair } from '../shared/auth/useSair'
import { avisosOptions } from '../pages/paciente/api'
import { Botao } from '../shared/ui/Botao'
import { MensagemNavegacao } from '../shared/ui/MensagemNavegacao'

export function PacienteLayout() {
  const location = useLocation()
  const avisos = useQuery(avisosOptions)
  const [menuAberto, setMenuAberto] = useState(false)
  const { sair, saindo } = useSair()
  const botaoMenu = useRef<HTMLButtonElement>(null)
  const conteudo = useRef<HTMLElement>(null)
  const focarAposNavegar = useRef(false)
  useEffect(() => {
    if (!focarAposNavegar.current) return
    focarAposNavegar.current = false
    conteudo.current?.focus()
  }, [location.key])
  function fecharMenu() { setMenuAberto(false); botaoMenu.current?.focus() }
  function navegarPeloMenu(event: MouseEvent<HTMLAnchorElement>) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    focarAposNavegar.current = true
    setMenuAberto(false)
  }
  return <div className="area-paciente">
    <a className="pular-conteudo" href="#conteudo-paciente">Pular para o conteúdo</a>
    <header className="cabecalho-paciente" onKeyDown={(event) => { if (menuAberto && event.key === 'Escape') fecharMenu() }}><div className="cabecalho-conteudo">
      <Link className="marca-paciente" to="/paciente" onClick={navegarPeloMenu}><span className="marca-simbolo" aria-hidden="true">+</span>
        <span><strong>Central de Teleagendamento</strong><span>Complexo Hospitalar da UPE</span></span>
      </Link>
      <button className="menu-paciente botao botao-secundario" type="button" ref={botaoMenu} aria-expanded={menuAberto} aria-controls="navegacao-paciente"
        onClick={() => menuAberto ? fecharMenu() : setMenuAberto(true)}>Menu</button>
      <nav id="navegacao-paciente" className={`paciente-nav${menuAberto ? ' aberto' : ''}`} aria-label="Área do paciente">
        <NavLink to="/paciente" end onClick={navegarPeloMenu}>Meus atendimentos</NavLink>
        <NavLink to="/paciente/novo" onClick={navegarPeloMenu}>Novo pedido</NavLink>
        <NavLink to="/paciente/avisos" onClick={navegarPeloMenu}>Avisos{avisos.data && <><span aria-hidden="true" className="contador-avisos">{avisos.data.nao_lidos}</span><span className="sr-only">, {avisos.data.nao_lidos} não lidos</span></>}</NavLink>
        {avisos.isPending && <span role="status">Carregando avisos…</span>}
        {avisos.isError && <div className="falha-avisos"><p role="alert">Não foi possível contar os avisos.</p>
          <Botao variante="secundario" carregando={avisos.isFetching} onClick={() => void avisos.refetch()}>Tentar contar de novo</Botao></div>}
        <Botao variante="secundario" carregando={saindo} onClick={() => void sair()}>Sair</Botao>
      </nav>
    </div></header>
    <main id="conteudo-paciente" className="paciente-principal" aria-label="Área do paciente" tabIndex={-1} ref={conteudo}>
      <MensagemNavegacao key={location.pathname} /><Outlet />
    </main>
    <footer className="rodape-paciente">CH/UPE · Protótipo acadêmico com dados sintéticos</footer>
  </div>
}
