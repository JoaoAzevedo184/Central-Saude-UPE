import { Navigate, Outlet, useLocation } from 'react-router'
import { useSessao } from './session'
import type { Papel } from './session'
import { estadoParaEntrar } from './retorno'

export function ExigirPapel({ papeis }: { papeis: readonly Papel[] }) {
  const sessao = useSessao()
  const location = useLocation()
  if (sessao.isPending || sessao.isFetching) return <p role="status">Verificando sessão…</p>
  if (sessao.isError) return <p role="alert">Não foi possível verificar a sessão.</p>
  if (!sessao.data) return <Navigate to="/entrar" replace state={estadoParaEntrar(location)} />
  if (!papeis.includes(sessao.data.papel)) return <p role="alert">Acesso não permitido.</p>
  return <Outlet />
}
