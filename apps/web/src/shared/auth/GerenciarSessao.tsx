import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router'
import { http } from '../api/http'
import { estadoParaEntrar } from './retorno'
import { sessaoOptions } from './session'

export function GerenciarSessao() {
  const client = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => http.aoExpirarSessao(() => {
    // O cancelamento aborta os signals e impede respostas tardias de reporem o cache.
    void client.cancelQueries()
    client.clear()
    client.setQueryData(sessaoOptions.queryKey, null)
    if (location.pathname !== '/entrar') {
      void navigate('/entrar', { replace: true, state: estadoParaEntrar(location) })
    }
  }), [client, location, navigate])

  return null
}
