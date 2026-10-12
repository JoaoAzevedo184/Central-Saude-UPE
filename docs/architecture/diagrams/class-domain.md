# Diagrama de classes do domínio

Mostra as entidades de `app/dominio` com os métodos que representam as regras de negócio. Os atributos completos e as restrições estão no [modelo de dados](../data-model.md); aqui só aparecem os relevantes para o comportamento.

```mermaid
classDiagram
  direction LR

  class Paciente {
    +id
    +nome
    +cpf
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
    +prioridade_legal
    +data_pedido
    +validar()
    +marcar_em_proposta()
    +voltar_para_fila()
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
  class Oferta {
    +prazo_resposta_horas
    +ativa
  }
  class RegraPrioridade {
    +ordem
    +criterio
    +parametros
    +simulada
  }
  class Fila {
    +ordenar(solicitacoes, regras) Solicitacao[]
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
  Oferta "1" --> "*" Agenda
  Fila ..> RegraPrioridade : usa
  Fila ..> Solicitacao : ordena
  Agendamento ..> Relogio : prazos
```

Notas:

- **Oferta** é a classe de domínio para a tabela `unidade_especialidade` (uma especialidade numa unidade, com prazo de resposta).
- As transições de `Solicitacao` e `Agendamento` levantam erro de domínio quando o estado de origem não permite a operação; a API traduz esse erro em `409`.
- `Fila` é um serviço sem estado: recebe as solicitações e as regras ativas e devolve a ordem. A ordenação fica em `ordenar_fila()`, sem aging no MVP ([ADR-022](../../decisions/ADR-022-ordem-da-fila-sem-aging.md)). Com aging, passa a precisar do `Relogio`.
