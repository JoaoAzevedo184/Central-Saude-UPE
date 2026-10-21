"""`CanalNotificacao` por SMTP (ADR-010). Em desenvolvimento, aponta para o mailpit."""

import smtplib
from email.message import EmailMessage

from app.config import Settings
from app.dominio.notificacoes.canal import Mensagem


class CanalEmailSmtp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def enviar(self, mensagem: Mensagem) -> None:
        cfg = self.settings
        email = EmailMessage()
        email["From"] = cfg.smtp_from
        email["To"] = mensagem.destino
        email["Subject"] = mensagem.assunto
        email.set_content(mensagem.corpo)
        # O timeout vale para conectar e para cada operação: SMTP lento não trava o Worker.
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=cfg.smtp_timeout_s) as smtp:
            if cfg.smtp_starttls:
                smtp.starttls()
            if cfg.smtp_user:
                smtp.login(cfg.smtp_user, cfg.smtp_password.get_secret_value())
            smtp.send_message(email)
