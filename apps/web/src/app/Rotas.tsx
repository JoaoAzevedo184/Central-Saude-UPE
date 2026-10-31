import { Navigate, Route, Routes, useOutletContext } from 'react-router'
import { EquipeLayout } from '../layouts/EquipeLayout'
import { PacienteLayout } from '../layouts/PacienteLayout'
import { ExigirPapel } from '../shared/auth/ExigirPapel'
import { GerenciarSessao } from '../shared/auth/GerenciarSessao'
import { Entrar } from '../pages/auth/Entrar'
import { MeusAtendimentos } from '../pages/paciente/MeusAtendimentos'
import { NovaSolicitacao } from '../pages/paciente/NovaSolicitacao'
import { DetalhePedido } from '../pages/paciente/DetalhePedido'
import { Avisos } from '../pages/paciente/Avisos'
import { Fila } from '../pages/equipe/Fila'
import { DetalheProvisorio } from '../pages/equipe/DetalheProvisorio'
import { CriarConta } from '../pages/auth/CriarConta'
import { TrocarSenha } from '../pages/auth/TrocarSenha'
import { rotaTrocarSenha } from '../shared/auth/troca-de-senha'
import { rotaInicial } from '../shared/auth/retorno'
import type { Sessao } from '../shared/auth/session'

function Inicio() {
  const sessao = useOutletContext<Sessao>()
  return <Navigate to={rotaInicial(sessao.papel)} replace />
}

export function Rotas() {
  return (
    <>
      <GerenciarSessao />
      <Routes>
        <Route element={<ExigirPapel papeis={['PACIENTE', 'ATENDENTE', 'GESTOR', 'ADMIN']} />}>
          <Route path="/" element={<Inicio />} />
        </Route>
        <Route path="/entrar" element={<Entrar />} />
        <Route path="/criar-conta" element={<CriarConta />} />
        <Route element={<ExigirPapel papeis={['PACIENTE', 'ATENDENTE', 'GESTOR', 'ADMIN']} permitirTrocaDeSenha />}>
          <Route path={rotaTrocarSenha} element={<TrocarSenha />} />
        </Route>
        <Route element={<ExigirPapel papeis={['PACIENTE']} />}>
          <Route path="/paciente" element={<PacienteLayout />}>
            <Route index element={<MeusAtendimentos />} />
            <Route path="novo" element={<NovaSolicitacao />} />
            <Route path="solicitacoes/:id" element={<DetalhePedido />} />
            <Route path="avisos" element={<Avisos />} />
          </Route>
        </Route>
        <Route element={<ExigirPapel papeis={['ATENDENTE', 'GESTOR', 'ADMIN']} />}>
          <Route path="/equipe" element={<EquipeLayout />}>
            <Route index element={<Navigate to="/equipe/fila" replace />} />
            <Route path="fila" element={<Fila />} />
            <Route path="solicitacoes/:id" element={<DetalheProvisorio />} />
          </Route>
        </Route>
        <Route path="*" element={<main><p role="alert">Página não encontrada.</p></main>} />
      </Routes>
    </>
  )
}
