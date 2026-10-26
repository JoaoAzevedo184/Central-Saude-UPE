import { Navigate, Outlet, useLocation } from 'react-router'
import { useSessao } from './session'
import type { Papel } from './session'
import { estadoParaEntrar } from './retorno'
import { http } from '../api/http'
import { exigeTrocaDeSenha, rotaTrocarSenha } from './troca-de-senha'

export function ExigirPapel({ papeis, permitirTrocaDeSenha = false }: { papeis: readonly Papel[]; permitirTrocaDeSenha?: boolean }) {
  const sessao = useSessao()
  const location = useLocation()
  if (!permitirTrocaDeSenha && (http.trocaDeSenhaObrigatoria() || exigeTrocaDeSenha(sessao.data))) {
    return <Navigate to={rotaTrocarSenha} replace />
  }
  if (sessao.isPending) return <p role="status">Verificando sessão…</p>
  if (sessao.isError && !sessao.data) return <p role="alert">Não foi possível verificar a sessão.</p>
  if (!sessao.data) return <Navigate to="/entrar" replace state={estadoParaEntrar(location)} />
  if (!papeis.includes(sessao.data.papel)) return <p role="alert">Acesso não permitido.</p>
  return <Outlet context={sessao.data} />
}
