import { Route, Routes } from 'react-router'
import { EquipeLayout } from '../layouts/EquipeLayout'
import { PacienteLayout } from '../layouts/PacienteLayout'
import { ExigirPapel } from '../shared/auth/ExigirPapel'
import { GerenciarSessao } from '../shared/auth/GerenciarSessao'

export function Rotas() {
  return (
    <>
      <GerenciarSessao />
      <Routes>
        <Route path="/" element={
          <main><h1>Central de Teleagendamento</h1><p>Base do frontend. Telas em desenvolvimento.</p></main>
        } />
        <Route path="/entrar" element={
          <main><h1>Entrar</h1><p>Tela de login em desenvolvimento.</p></main>
        } />
        <Route element={<ExigirPapel papeis={['PACIENTE']} />}>
          <Route path="/paciente" element={<PacienteLayout />} />
        </Route>
        <Route element={<ExigirPapel papeis={['ATENDENTE', 'GESTOR', 'ADMIN']} />}>
          <Route path="/equipe" element={<EquipeLayout />} />
        </Route>
        <Route path="*" element={<main><p role="alert">Página não encontrada.</p></main>} />
      </Routes>
    </>
  )
}
