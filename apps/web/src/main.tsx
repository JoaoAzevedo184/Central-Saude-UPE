import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router'
import { criarQueryClient } from './app/query-client'
import { Rotas } from './app/Rotas'
import './styles/global.css'

const root = document.getElementById('root')
if (!root) throw new Error('Elemento raiz ausente.')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={criarQueryClient()}>
      <BrowserRouter><Rotas /></BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
