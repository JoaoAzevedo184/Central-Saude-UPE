import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { http } from '../api/http'
import { encerrarSessaoLocal } from './session'

// Mesmo fluxo do layout do paciente: a saída antiga nunca encerra uma sessão nova.
export function useSair() {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [saindo, setSaindo] = useState(false)
  const travaSaida = useRef(false)
  async function sair() {
    if (travaSaida.current) return
    travaSaida.current = true; setSaindo(true)
    const geracao = http.geracaoSessao()
    try { await http.request('/auth/logout', { method: 'POST' }) }
    catch { /* A saída local também acontece quando o servidor está indisponível. */ }
    finally {
      const encerramento = encerrarSessaoLocal(client, geracao)
      const geracaoEncerramento = http.geracaoSessao()
      if (await encerramento && geracaoEncerramento === http.geracaoSessao()) {
        await navigate('/entrar', { replace: true })
      }
    }
  }
  return { sair, saindo }
}
