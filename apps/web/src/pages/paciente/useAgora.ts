import { useLayoutEffect, useState } from 'react'

export function useAgora(inicio?: string, expiraEm?: string | null) {
  const [leitura, setLeitura] = useState(() => ({ inicio, expiraEm, agora: Date.now() }))
  useLayoutEffect(() => {
    const atualizar = () => setLeitura({ inicio, expiraEm, agora: Date.now() })
    atualizar()
    const timer = window.setInterval(atualizar, 30_000)
    const limites = [inicio, expiraEm].map((valor) => {
      if (!valor) return () => {}
      const limite = new Date(valor).getTime()
      if (!Number.isFinite(limite)) return () => {}
      let timeout: number | undefined
      const conferir = () => {
        const restante = limite - Date.now()
        // Reconfere o relógio se o navegador antecipar o timer ou limitar seu intervalo.
        if (restante > 0) timeout = window.setTimeout(conferir, Math.min(restante, 2_147_483_647))
        else atualizar()
      }
      conferir()
      return () => window.clearTimeout(timeout)
    })
    document.addEventListener('visibilitychange', atualizar)
    return () => { window.clearInterval(timer); limites.forEach((cancelar) => cancelar()); document.removeEventListener('visibilitychange', atualizar) }
  }, [inicio, expiraEm])
  // Enquanto sincroniza novos limites, não libera ações com a leitura antiga.
  // O layout effect lê o relógio real e atualiza a tela antes da pintura.
  return leitura.inicio === inicio && leitura.expiraEm === expiraEm ? leitura.agora : Infinity
}
