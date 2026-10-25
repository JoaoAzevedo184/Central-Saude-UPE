import { Route, Routes } from 'react-router'
import { EquipeLayout } from '../layouts/EquipeLayout'
import { PacienteLayout } from '../layouts/PacienteLayout'
import { ExigirPapel } from '../shared/auth/ExigirPapel'
import { GerenciarSessao } from '../shared/auth/GerenciarSessao'
import { Entrar } from '../pages/auth/Entrar'
import { MeusAtendimentos } from '../pages/paciente/MeusAtendimentos'
import { CriarConta } from '../pages/auth/CriarConta'
import { rotaTrocarSenha } from '../shared/auth/troca-de-senha'

export function Rotas() {
  return (
    <>
      <GerenciarSessao />
      <Routes>
        <Route path="/" element={
          <main><h1>Central de Teleagendamento</h1><p>Base do frontend. Telas em desenvolvimento.</p></main>
        } />
        <Route path="/entrar" element={<Entrar />} />
        <Route path="/criar-conta" element={<CriarConta />} />
        <Route path={rotaTrocarSenha} element={<main>
          <h1>Troca de senha obrigatória</h1>
          <p>Sua conta precisa de uma nova senha para continuar. Esta tela está em desenvolvimento.</p>
        </main>} />
        <Route element={<ExigirPapel papeis={['PACIENTE']} />}>
          <Route path="/paciente" element={<PacienteLayout />}>
            <Route index element={<MeusAtendimentos />} />
            <Route path="novo" element={<h1>Novo pedido</h1>} />
            <Route path="solicitacoes/:id" element={<h1>Detalhes do pedido</h1>} />
            <Route path="avisos" element={<h1>Avisos</h1>} />
          </Route>
        </Route>
        <Route element={<ExigirPapel papeis={['ATENDENTE', 'GESTOR', 'ADMIN']} />}>
          <Route path="/equipe" element={<EquipeLayout />} />
        </Route>
        <Route path="*" element={<main><p role="alert">Página não encontrada.</p></main>} />
      </Routes>
    </>
  )
}
