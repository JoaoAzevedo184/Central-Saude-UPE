import type { UseFormReturn } from 'react-hook-form'
import { Campo } from '../../shared/ui/Campo'
import { CampoSelecao } from '../../shared/ui/CampoSelecao'
import type { CriterioPaciente } from './api'
import { turnos, validarResposta, type FormularioSolicitacao } from './formulario-solicitacao'

export function EtapaInformacoes({ criterios, formulario }: { criterios: CriterioPaciente[]; formulario: UseFormReturn<FormularioSolicitacao> }) {
  const { register, formState: { errors } } = formulario
  return <>
    <Campo rotulo="De onde veio seu encaminhamento?" ajuda="Informe o serviço ou local que encaminhou você."
      {...register('origem_encaminhamento', { validate: (valor) => {
        const tamanho = valor.trim().length
        return tamanho >= 2 && tamanho <= 200 || 'Informe a origem do encaminhamento, de 2 a 200 caracteres.'
      } })} erro={errors.origem_encaminhamento?.message} />
    <CampoSelecao rotulo="Qual turno você prefere?" {...register('turno_preferido', { validate: (valor) => Object.hasOwn(turnos, valor) || 'Escolha um turno.' })} erro={errors.turno_preferido?.message}>
      {Object.entries(turnos).map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
    </CampoSelecao>
    {criterios.length > 0 && <><h3>Perguntas sobre o atendimento</h3><p>Estas perguntas são opcionais. Você pode deixar sem resposta.</p></>}
    {criterios.map((criterio, indice) => {
      const props = { ...register(`respostas.${indice}.valor`, { validate: (valor: string) => validarResposta(criterio, valor) }),
        rotulo: criterio.descricao, ajuda: 'Opcional', erro: errors.respostas?.[indice]?.valor?.message }
      if (criterio.tipo === 'NUMERO') return <Campo key={criterio.id} {...props} type="text" inputMode="decimal" />
      // TODO(api): opcoes fornece valores literais, sem rótulos separados para códigos.
      return <CampoSelecao key={criterio.id} {...props}>
        <option value="">Sem resposta</option>
        {criterio.tipo === 'SIM_NAO' ? <><option value="sim">Sim</option><option value="nao">Não</option></> :
          criterio.opcoes?.map((opcao) => <option key={opcao} value={opcao}>{opcao}</option>)}
      </CampoSelecao>
    })}
  </>
}
