import { Outlet, useLocation } from 'react-router'

export function PacienteLayout() {
  const { state } = useLocation()
  return <main aria-label="Área do paciente">{state?.mensagem === 'Conta criada.' && <p role="status">Conta criada.</p>}<Outlet /></main>
}
