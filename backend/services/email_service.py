import logging
import smtplib
from email.message import EmailMessage

from flask import current_app, render_template

logger = logging.getLogger(__name__)


def enviar_email(destinatario, assunto, texto, html=None):
    config = current_app.config
    host = config.get('EMAIL_HOST')
    if not host:
        logger.warning(
            "[EMAIL] EMAIL_HOST não configurado no .env — e-mail não enviado "
            f"para {destinatario}."
        )
        return False

    mensagem = EmailMessage()
    mensagem['From'] = config.get('EMAIL_FROM') or 'nao-responda@localhost'
    mensagem['To'] = destinatario
    mensagem['Subject'] = assunto
    mensagem.set_content(texto)
    if html:
        mensagem.add_alternative(html, subtype='html')

    porta = int(config.get('EMAIL_PORT', 587))
    usuario = config.get('EMAIL_HOST_USER', '')
    senha = config.get('EMAIL_HOST_PASSWORD', '')

    try:
        with smtplib.SMTP(host, porta, timeout=20) as servidor:
            if config.get('EMAIL_USE_TLS'):
                servidor.starttls()
            if usuario and senha:
                servidor.login(usuario, senha)
            servidor.send_message(mensagem)
        logger.info(f"[EMAIL] E-mail '{assunto}' enviado para {destinatario}.")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "[EMAIL] Falha de autenticação no SMTP — confira EMAIL_HOST_USER e "
            "EMAIL_HOST_PASSWORD (senha de aplicativo) no .env."
        )
        return False
    except Exception as erro:  
        logger.error(
            f"[EMAIL] Falha ao enviar para {destinatario}: "
            f"{type(erro).__name__}: {erro}"
        )
        return False


def enviar_email_recuperacao(destinatario, nome_usuario, link, minutos_validade):
    html = render_template(
        'email_recuperacao.html',
        nome=nome_usuario,
        link=link,
        minutos=minutos_validade,
    )
    texto = (
        f"Olá, {nome_usuario}!\n\n"
        "Recebemos uma solicitação para redefinir a senha da sua conta.\n\n"
        f"Para criar uma nova senha, acesse o link abaixo (válido por "
        f"{minutos_validade} minutos):\n\n{link}\n\n"
        "Se você não pediu isso, pode ignorar este e-mail — sua senha "
        "continua a mesma.\n\n"
        "Atenciosamente,\nEquipe do QuestionsApplication.\n"
    )
    return enviar_email(
        destinatario,
        'Redefinição de senha — QuestionsApplication',
        texto,
        html,
    )
