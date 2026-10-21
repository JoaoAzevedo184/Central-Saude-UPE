"""Textos dos avisos ao paciente, em português claro. Um por tipo, para revisar num lugar só.

Aviso no site (atrás do login): pode trazer unidade, profissional, data e hora.
E-mail (AM-008): só o prazo ou a data e hora, e o link para a Central. Falta,
cancelamento e prazo expirado nunca aparecem no e-mail: vai a frase neutra.
Sem nome, CPF, especialidade, fila, unidade nem profissional. Nunca posição, tamanho da
fila, nota nem risco, em nenhum dos dois (ADR-007).
"""

ASSUNTO_EMAIL = "Central de Agendamento: você tem uma atualização"

CORPO_EMAIL = """Olá.

{mensagem}

Para ver os detalhes, entre na Central de Agendamento:
{link}

Este e-mail é automático. Não é preciso responder.
A Central nunca pede sua senha por e-mail."""

# E-mail de falta, cancelamento e prazo expirado: texto igual ao de qualquer atualização (AM-008).
# O detalhe fica só no aviso do site.
FRASE_NEUTRA = "Há uma atualização no seu atendimento."

# tipo -> (título no site, corpo no site, frase do e-mail ou None se não vai por e-mail).
# Campos: {inicio} e {prazo} em "DD/MM às HH:MM"; {dia} em "DD/MM"; {local} = unidade e
# profissional; {efeito} = o que aconteceu com o pedido na fila.
TEXTOS: dict[str, tuple[str, str, str | None]] = {
    "SOLICITACAO_CRIADA": (
        "Recebemos seu pedido",
        "Seu pedido está em análise. Avisaremos aqui quando houver novidade.",
        None,
    ),
    "SOLICITACAO_NA_FILA": (
        "Seu pedido entrou na fila",
        "Quando houver uma vaga para você, avisaremos aqui.",
        None,
    ),
    "PROPOSTA_ENVIADA": (
        "Você tem uma vaga: confirme até {prazo}",
        "Consulta no dia {inicio}{local}. Se você não confirmar até {prazo}, "
        "a vaga passa para outra pessoa.",
        "Você tem uma vaga para consulta. Para ficar com ela, confirme até {prazo}.",
    ),
    "AGENDAMENTO_CONFIRMADO": (
        "Consulta confirmada para {inicio}",
        "Sua consulta está confirmada para o dia {inicio}{local}. "
        "Chegue com antecedência e leve um documento com foto.",
        "Sua consulta está confirmada para o dia {inicio}.",
    ),
    "PROPOSTA_RECUSADA": (
        "Recebemos sua recusa",
        "A vaga do dia {inicio} foi liberada. {efeito}",
        None,
    ),
    "PROPOSTA_EXPIRADA": (
        "O prazo para confirmar acabou",
        "Você não confirmou a vaga do dia {inicio} até {prazo}. {efeito}",
        FRASE_NEUTRA,
    ),
    "AGENDAMENTO_CANCELADO": (
        "Cancelamento registrado",
        "Sua consulta do dia {inicio} foi cancelada e seu pedido foi encerrado.",
        FRASE_NEUTRA,
    ),
    "SOLICITACAO_CANCELADA": (
        "Cancelamento registrado",
        "Seu pedido foi cancelado.",
        FRASE_NEUTRA,
    ),
    "FALTA_REGISTRADA": (
        "Registramos sua falta",
        "Você não compareceu à consulta do dia {dia}. {efeito}",
        FRASE_NEUTRA,
    ),
    "ATENDIMENTO_REGISTRADO": (
        "Atendimento registrado",
        "Registramos seu atendimento do dia {dia}. Seu pedido foi concluído.",
        None,
    ),
    "LEMBRETE": (
        "Lembrete: sua consulta é no dia {inicio}",
        "Sua consulta é no dia {inicio}{local}. Chegue com antecedência e leve um "
        "documento com foto. Se não puder ir, cancele pela Central.",
        "Lembrete: sua consulta é no dia {inicio}. Se não puder ir, avise pela Central.",
    ),
}

EFEITO_FIM_DA_FILA = "Seu pedido voltou para o fim da fila."
EFEITO_CONTINUA_NA_FILA = "Seu pedido continua na fila e você receberá outra data."
SEM_DATA = "a combinar"
