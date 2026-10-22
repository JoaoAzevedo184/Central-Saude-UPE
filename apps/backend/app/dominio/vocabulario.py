"""Vocabulário fechado do domínio: uma definição de cada lista de valores.

O modelo (CHECK do banco), os schemas da API (enums do OpenAPI) e as regras importam daqui.
Mudar um valor exige migração (CHECK) e atualiza o contrato; o snapshot do OpenAPI falha até
`docs/architecture/openapi.json` ser regenerado.
"""

PAPEIS = ("PACIENTE", "ATENDENTE", "GESTOR", "ADMIN")
SITUACOES_USUARIO = ("ATIVO", "SUSPENSO")
RISCOS = ("VERMELHO", "AMARELO", "VERDE")
TURNOS = ("MANHA", "TARDE", "QUALQUER")
STATUS_SOLICITACAO = ("EM_ANALISE", "NA_FILA", "EM_PROPOSTA", "AGENDADA", "ATENDIDA", "CANCELADA")
STATUS_AGENDAMENTO = ("PROPOSTO", "CONFIRMADO", "CANCELADO", "EXPIRADO", "REALIZADO", "FALTOU")
# Coluna `vaga.status_admin` (bloqueio manual); a situação do painel é `SITUACOES_VAGA`.
STATUS_VAGA = ("ATIVA", "BLOQUEADA")
# Situação derivada na consulta, nunca gravada (ADR-004).
SITUACOES_VAGA = ("LIVRE", "LIVRE_SEM_PROPOSTA", "PROPOSTA", "CONFIRMADA", "BLOQUEADA", "ENCERRADA")

# Motivo do cancelamento pelo paciente: lista fechada, sem texto livre (minimização,
# docs/security/data-protection.md). O rótulo vai para a linha do tempo.
MOTIVOS_CANCELAMENTO = {
    "NAO_PRECISO_MAIS": "Não preciso mais do atendimento.",
    "CONSEGUI_EM_OUTRO_LUGAR": "Consegui atendimento em outro lugar.",
    "DIFICULDADE_DE_DESLOCAMENTO": "Dificuldade de deslocamento.",
    "CONFLITO_DE_HORARIO": "Conflito de horário.",
    "OUTRO": "Outro motivo.",
}
MOTIVOS_CANCELAMENTO_AGENDAMENTO = (
    "RECUSADO_PELO_PACIENTE",
    "CANCELADO_PELO_PACIENTE",
    "CANCELADO_PELA_EQUIPE",  # reservado
    "VAGA_BLOQUEADA",  # reservado
)
TIPOS_HISTORICO = (
    "CRIADA",
    "CLASSIFICADA",
    "ENTROU_NA_FILA",
    "PROPOSTA_ENVIADA",
    "CONFIRMADA",
    "RECUSADA",
    "PROPOSTA_EXPIRADA",
    "FALTOU",
    "ATENDIDA",
    "CANCELADA",
    "REENTROU_NA_FILA",
    "RECLASSIFICADA",
)
TIPOS_CRITERIO = ("SIM_NAO", "NUMERO", "OPCAO")
ORIGENS_CRITERIO = ("PACIENTE", "REGULACAO", "EQUIPE")
