import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useNavigationType } from 'react-router'

function lerMensagem(estado: unknown): string | undefined {
  if (!estado || typeof estado !== 'object' || !('mensagem' in estado)) return
  const mensagem: unknown = estado.mensagem
  if (typeof mensagem === 'string' && mensagem.trim() && mensagem.length <= 200) return mensagem
}

// Apenas texto curto vindo do estado interno do Router; nunca HTML ou dados da API.
export function MensagemNavegacao() {
  const location = useLocation()
  const navigate = useNavigate()
  const tipo = useNavigationType()
  const consumida = useRef<string | null>(null)
  const mensagemRef = useRef<HTMLParagraphElement>(null)
  const entrada = lerMensagem(location.state)
  const [aviso, setAviso] = useState(() => ({ chave: location.key, texto: entrada, consumindo: Boolean(entrada) }))
  // Ajusta o próprio estado antes do commit; POP/PUSH não reapresentam o aviso.
  // Só o replace que consome a mensagem preserva sua apresentação temporária.
  if (aviso.chave !== location.key) {
    setAviso({ chave: location.key, texto: entrada ?? (aviso.consumindo && tipo === 'REPLACE' ? aviso.texto : undefined), consumindo: Boolean(entrada) })
  }
  useEffect(() => {
    if (aviso.texto) mensagemRef.current?.focus()
  }, [aviso.texto])
  useEffect(() => {
    if (!entrada || consumida.current === location.key) return
    consumida.current = location.key
    const restante = { ...location.state }; delete restante.mensagem
    void navigate({ pathname: location.pathname, search: location.search, hash: location.hash }, { replace: true, state: restante })
  }, [entrada, location, navigate])
  useEffect(() => {
    if (!aviso.texto) return
    const timer = window.setTimeout(() => setAviso((atual) => atual.chave === aviso.chave ? { ...atual, texto: undefined } : atual), 6000)
    return () => window.clearTimeout(timer)
  }, [aviso.chave, aviso.texto])
  return aviso.texto ? <p role="status" className="mensagem-sucesso" tabIndex={-1} ref={mensagemRef}>{aviso.texto}</p> : null
}
