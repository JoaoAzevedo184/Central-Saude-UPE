import { render, screen } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import type { UseFormSetError } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from './problem-details'
import { aplicarErrosDeValidacao } from './form-errors'

type Formulario = { cpf: string; respostas: { valor: string }[] }
function validacao(errors: unknown, status = 422) {
  return new ApiError({ type: 'about:blank', title: 'Unprocessable Entity', status, errors }, new Response(null, { status }))
}

describe('RFC 9457 — validação 422 e React Hook Form', () => {
  it('leva campos simples e índices de arrays ao setError e mantém o primeiro erro', () => {
    const setError = vi.fn<UseFormSetError<Formulario>>()
    expect(aplicarErrosDeValidacao<Formulario>(validacao([
      { loc: ['body', 'cpf'], msg: 'CPF inválido.', type: 'value_error' },
      { loc: ['body', 'cpf'], msg: 'Outro erro.', type: 'value_error' },
      { loc: ['body', 'respostas', 0, 'valor'], msg: 'Preencha a resposta.', type: 'missing' },
    ]), setError, ['cpf', 'respostas.0.valor'])).toBe(true)
    expect(setError.mock.calls).toEqual([
      ['cpf', { type: 'server', message: 'CPF inválido.' }, { shouldFocus: true }],
      ['respostas.0.valor', { type: 'server', message: 'Preencha a resposta.' }, { shouldFocus: false }],
    ])
  })

  it('manda erros fora do body ou de campos não cadastrados para o formulário', () => {
    const setError = vi.fn<UseFormSetError<Formulario>>()
    aplicarErrosDeValidacao<Formulario>(validacao([
      { loc: ['query', 'cpf'], msg: 'Erro de query', type: 'value_error' },
      { loc: ['body', 'papel'], msg: 'Campo extra', type: 'extra_forbidden' },
      { loc: ['body'], msg: 'Erro global', type: 'value_error' },
    ]), setError, ['cpf'])
    expect(setError.mock.calls).toEqual([
      ['root.server', { type: 'server', message: 'Confira os campos indicados e tente novamente.' }],
    ])
  })

  it.each([undefined, null, [], 'inválido', [{ loc: null }], [{ loc: ['body', 'cpf'], msg: 42, type: 'missing' }]])('tolera errors ausentes ou inválidos: %j', (errors) => {
    const setError = vi.fn<UseFormSetError<Formulario>>()
    expect(aplicarErrosDeValidacao<Formulario>(validacao(errors), setError, ['cpf'])).toBe(true)
    expect(setError).toHaveBeenCalledWith('root.server', expect.objectContaining({ type: 'server' }))
  })

  it('ignora erros que não são validação 422', () => {
    const setError = vi.fn<UseFormSetError<Formulario>>()
    for (const error of [new Error('rede'), validacao([], 409), null]) {
      expect(aplicarErrosDeValidacao<Formulario>(error, setError, ['cpf'])).toBe(false)
    }
    expect(setError).not.toHaveBeenCalled()
  })

  it('integra com o estado real do React Hook Form', async () => {
    function FormularioSintetico() {
      const { register, setError, formState: { errors } } = useForm<Formulario>()
      return <form onSubmit={(event) => {
        event.preventDefault()
        aplicarErrosDeValidacao<Formulario>(validacao([
          { loc: ['body', 'cpf'], msg: 'CPF inválido.', type: 'value_error' },
        ]), setError, ['cpf'])
      }}>
        <input aria-label="CPF sintético" {...register('cpf')} />
        <button>Enviar</button>
        {errors.cpf && <p role="alert">{errors.cpf.message}</p>}
      </form>
    }
    render(<FormularioSintetico />)
    screen.getByRole('button').click()
    expect((await screen.findByRole('alert')).textContent).toBe('CPF inválido.')
    expect(document.activeElement).toBe(screen.getByRole('textbox'))
  })
})
