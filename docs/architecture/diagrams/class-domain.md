# Diagrama de classes do domínio

Mostra as entidades de `app/dominio` com os métodos que representam as regras de negócio. Os atributos completos e as restrições estão no [modelo de dados](../data-model.md); aqui só aparecem os relevantes para o comportamento.

```mermaid
classDiagram
  direction LR

  class Paciente {
    +id
    +nome
    +cpf
    +sexo
    +data_nascimento
    +tem_consentimento_vigente(finalidade) bool
  }
  class Consentimento {
    +finalidade
    +versao_termo
    +concedido_em
    +revogado_em
    +revogar(agora)
  }
  class Solicitacao {
    +status: StatusSolicitacao
    +classificacao_risco
    +nota
    +data_entrada_fila
    +validar()
    +marcar_em_proposta()
    +reentrar_no_fim_da_fila(agora, motivo)
    +marcar_agendada()
    +cancelar()
  }
  class Agendamento {
    +status: StatusAgendamento
    +expira_em
    +respondido_em
    +confirmar(agora)
    +cancelar(motivo, agora)
    +expirar(agora)
    +registrar_comparecimento()
    +registrar_falta()
  }
  class Vaga {
    +inicio
    +fim
    +status_admin
    +bloquear()
    +desbloquear()
  }
  class Agenda {
    +dias_semana
    +hora_inicio
    +hora_fim
    +duracao_min
    +gerar_vagas(periodo) Vaga[]
  }
  class Fila {
    +descricao_paciente
    +sexo_elegivel
    +idade_minima
    +idade_maxima
    +prazo_confirmacao_horas
    +tolerancia_atraso_min
    +verificar_elegibilidade(paciente, hoje) bool
    +ordenar(solicitacoes) Solicitacao[]
  }
  class CriterioFila {
    +codigo
    +tipo
    +peso
    +parametros
    +simulado
    +calcular_pontos(valor) int
  }
  class RespostaCriterio {
    +valor
    +pontos
  }
  class CanalNotificacao {
    <<interface>>
    +enviar(aviso)
  }
  class ReguladorGateway {
    <<interface>>
    +obter_encaminhamento(paciente)
  }
  class Relogio {
    <<interface>>
    +agora()
  }

  Paciente "1" --> "*" Consentimento
  Paciente "1" --> "*" Solicitacao
  Solicitacao "1" --> "*" Agendamento : propostas
  Agendamento "*" --> "1" Vaga
  Agenda "1" --> "*" Vaga
  Fila "1" --> "*" Agenda
  Fila "1" --> "*" CriterioFila : protocolo
  Fila "1" --> "*" Solicitacao : contem
  Solicitacao "1" --> "*" RespostaCriterio
  RespostaCriterio "*" --> "1" CriterioFila
  Agendamento ..> Relogio : prazos e tolerancia
```

Notas:

- **Fila** é uma especialidade numa unidade, com descrição, elegibilidade, prazos e protocolo próprios ([ADR-027](../../decisions/ADR-027-fila-como-entidade.md)). Uma especialidade pode ter várias filas.
- As transições de `Solicitacao` e `Agendamento` levantam erro de domínio quando o estado de origem não permite a operação; a API traduz esse erro em `409`.
- A ordem da fila é risco → nota → hora de chegada, calculada por `ordenar_fila()` e nunca gravada ([ADR-024](../../decisions/ADR-024-protocolo-por-fila.md)). A nota é a soma dos pontos das respostas aos critérios da fila.
- Voltar ao fim da fila (proposta expirada ou falta) é uma nova `data_entrada_fila` ([ADR-026](../../decisions/ADR-026-prazos-e-volta-ao-fim-da-fila.md)).
