import { useId, useRef, useState } from 'react'
import { Botao } from '../../shared/ui/Botao'
import { Campo } from '../../shared/ui/Campo'
import { CampoSelecao } from '../../shared/ui/CampoSelecao'
import type { FilaEquipe } from './api'
import { identificarPeriodo, periodoPronto, validarPeriodo, type EstadoIndicadores, type PeriodoIndicadores } from './estado-indicadores'

export function FiltrosIndicadores({ estado, hoje, filas, filasCarregadas, erroPeriodo, erroFila, aoTentarFilas, aoMudar }: {
  estado: EstadoIndicadores; hoje: string; filas: FilaEquipe[]; filasCarregadas: boolean; erroPeriodo?: string; erroFila?: string
  aoTentarFilas?: () => void
  aoMudar: (estado: EstadoIndicadores) => void
}) {
  const [periodo, setPeriodo] = useState<PeriodoIndicadores>(() => identificarPeriodo(estado, hoje))
  const [de, setDe] = useState(estado.de)
  const [ate, setAte] = useState(estado.ate)
  const [erroLocal, setErroLocal] = useState<string>()
  const inicial = useRef<HTMLInputElement>(null)
  const inicioId = useId()
  const erro = erroLocal ?? erroPeriodo
  return <form className="filtros-indicadores" noValidate onSubmit={(event) => {
    event.preventDefault()
    const mensagem = validarPeriodo(de, ate, hoje)
    setErroLocal(mensagem)
    if (mensagem) inicial.current?.focus()
    else aoMudar({ ...estado, de, ate })
  }}>
    <CampoSelecao rotulo="Período" value={periodo} erro={periodo !== 'personalizado' ? erro : undefined} onChange={(event) => {
      const valor = event.target.value as PeriodoIndicadores
      setPeriodo(valor); setErroLocal(undefined)
      if (valor !== 'personalizado') aoMudar({ ...estado, ...periodoPronto(valor, hoje) })
    }}>
      <option value="4">Últimas 4 semanas</option><option value="8">Últimas 8 semanas</option>
      <option value="mes">Este mês</option><option value="personalizado">Personalizado</option>
    </CampoSelecao>
    <CampoSelecao rotulo="Fila" value={estado.fila} erro={erroFila}
      ajuda={aoTentarFilas && <Botao type="button" variante="secundario" onClick={aoTentarFilas}>Tentar carregar filas</Botao>}
      onChange={(event) => aoMudar({ ...estado, fila: event.target.value })}>
      <option value="">Todas as minhas filas</option>
      {filasCarregadas && estado.fila && !filas.some((fila) => fila.id === estado.fila) && <option value={estado.fila}>Fila selecionada indisponível</option>}
      {filas.map((fila) => <option key={fila.id} value={fila.id}>{fila.nome} · {fila.unidade_sigla}{fila.ativa ? '' : ' (inativa)'}</option>)}
    </CampoSelecao>
    {periodo === 'personalizado' && <div className="periodo-personalizado">
      <Campo rotulo="De" id={inicioId} type="date" value={de} max={hoje} ref={inicial} erro={erro} onChange={(event) => { setDe(event.target.value); setErroLocal(undefined) }} />
      <Campo rotulo="Até" type="date" value={ate} max={hoje} aria-describedby={erro ? `${inicioId}-erro` : undefined} onChange={(event) => { setAte(event.target.value); setErroLocal(undefined) }} />
      <Botao type="submit">Aplicar</Botao>
      <p>Até 366 dias, incluindo o primeiro e o último dia. Datas em Recife.</p>
    </div>}
    {erro && <p role="alert" className="sr-only">{erro}</p>}
    {erroFila && <p role="alert" className="sr-only">{erroFila}</p>}
  </form>
}
