import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router'
import { http } from '../api/http'
import { estadoParaEntrar } from './retorno'
import { encerrarSessaoLocal } from './session'
import { rotaTrocarSenha } from './troca-de-senha'

export function GerenciarSessao() {
  const client = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => http.aoExpirarSessao(() => {
    // O HTTP só notifica a geração atual. Navega antes de aguardar cancelamentos,
    // impedindo que a árvore expirada inicie novas consultas durante a limpeza.
    void encerrarSessaoLocal(client)
    if (location.pathname !== '/entrar') {
      void navigate('/entrar', { replace: true, state: estadoParaEntrar(location) })
    }
  }), [client, location, navigate])

  useEffect(() => http.aoExigirTrocaDeSenha(() => {
    void navigate(rotaTrocarSenha, { replace: true })
  }), [navigate])

  return null
}
