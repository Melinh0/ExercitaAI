import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from models.topic_model import TopicModel
from models.user_model import User, db
from services import email_service, rate_limit

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

EMAIL_REGEX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')
USERNAME_REGEX = re.compile(r'^[\w.\- ]{3,40}$', re.UNICODE)
SENHA_MIN = 8
SENHA_MAX = 128

MENSAGEM_RESET_GENERICA = (
    'Se este e-mail estiver cadastrado, você receberá uma mensagem com as '
    'instruções para redefinir a sua senha.'
)


def _ip_cliente():
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        ultimo = xff.split(',')[-1].strip()
        if ultimo:
            return ultimo
    real_ip = request.headers.get('X-Real-IP', '').strip()
    if real_ip:
        return real_ip
    return request.remote_addr or 'desconhecido'


def _json():
    return request.get_json(silent=True) or {}


def _buscar_por_email(email):
    normalizado = (email or '').strip().lower()
    if not normalizado:
        return None
    usuario = User.query.filter_by(email=normalizado).first()
    if usuario:
        return usuario
    return User.query.filter(func.lower(User.email) == normalizado).first()


def _validar_senha(senha):
    if not isinstance(senha, str) or not senha:
        return 'Senha é obrigatória.'
    if len(senha) < SENHA_MIN:
        return f'A senha precisa de pelo menos {SENHA_MIN} caracteres.'
    if len(senha) > SENHA_MAX:
        return f'A senha pode ter no máximo {SENHA_MAX} caracteres.'
    return None


def _erros_de_cadastro(username, email, password):
    erros = []
    if not username or not isinstance(username, str):
        erros.append('Nome de usuário é obrigatório.')
    elif not USERNAME_REGEX.match(username.strip()):
        erros.append(
            'Nome de usuário: 3 a 40 caracteres, usando apenas letras, '
            'números, espaço, ponto, hífen ou sublinhado.'
        )
    if not email or not isinstance(email, str):
        erros.append('E-mail é obrigatório.')
    elif not EMAIL_REGEX.match(email.strip()):
        erros.append('Informe um e-mail válido.')
    senha_err = _validar_senha(password)
    if senha_err:
        erros.append(senha_err)
    return erros


def _bloqueado(chave, maximo, janela_segundos, rotulo):
    if not rate_limit.bloqueado(chave, janela_segundos, maximo):
        return None
    restante = rate_limit.segundos_para_liberar(chave, janela_segundos)
    minutos = max(1, -(-restante // 60))  
    logger.warning(
        f"[AUTH] Limite de tentativas atingido ({rotulo}) — "
        f"{maximo} tentativas em {janela_segundos // 60} min."
    )
    return jsonify({
        'error': (
            f'Muitas tentativas. Aguarde aproximadamente {minutos} minuto(s) '
            'e tente novamente.'
        )
    }), 429


@auth_bp.route('/register', methods=['POST'])
def register():
    data = _json()
    username = (data.get('username') or '').strip() if isinstance(data.get('username'), str) else ''
    email = (data.get('email') or '').strip().lower() if isinstance(data.get('email'), str) else ''
    password = data.get('password')

    erros = _erros_de_cadastro(username, email, password)
    if erros:
        return jsonify({'error': ' '.join(erros)}), 400

    chave_cadastro = f"cadastro:{_ip_cliente()}"
    bloqueio = _bloqueado(
        chave_cadastro,
        current_app.config['AUTH_CADASTRO_MAX'],
        current_app.config['AUTH_CADASTRO_JANELA_H'] * 3600,
        'registro',
    )
    if bloqueio:
        return bloqueio
    rate_limit.registrar(
        chave_cadastro,
        current_app.config['AUTH_CADASTRO_JANELA_H'] * 3600,
        current_app.config['AUTH_CADASTRO_MAX'],
    )

    if _buscar_por_email(email):
        return jsonify({'error': 'Email já cadastrado'}), 400
    if User.query.filter(func.lower(User.username) == username.lower()).first():
        return jsonify({'error': 'Nome de usuário já cadastrado'}), 400

    user = User(username=username, email=email)
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as erro:  
        db.session.rollback()
        logger.error(f"[AUTH] Falha ao criar usuário: {type(erro).__name__}")
        return jsonify({'error': 'Não foi possível concluir o cadastro.'}), 400

    TopicModel.create_user_dirs(user)
    return jsonify({'success': True, 'user_id': user.id})


@auth_bp.route('/login', methods=['POST'])
def login():
    data = _json()
    email = (data.get('email') or '').strip().lower() if isinstance(data.get('email'), str) else ''
    password = data.get('password')

    chave = f"login:{_ip_cliente()}|{email}"
    janela = current_app.config['AUTH_LOGIN_JANELA_MIN'] * 60
    maximo = current_app.config['AUTH_LOGIN_MAX_TENTATIVAS']

    bloqueio = _bloqueado(chave, maximo, janela, 'login')
    if bloqueio:
        return bloqueio

    user = _buscar_por_email(email) if email else None
    if not user or not user.check_password(password or ''):
        rate_limit.registrar(chave, janela, maximo)
        return jsonify({'error': 'Credenciais inválidas'}), 401

    rate_limit.limpar(chave)
    login_user(user)
    session['user_id'] = user.id
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'ollama_keys': user.get_ollama_keys(),
            'ocr_keys': user.get_ocr_keys(),
        }
    })


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    session.pop('user_id', None)
    return jsonify({'success': True})


@auth_bp.route('/current_user', methods=['GET'])
@login_required
def current_user_info():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'ollama_keys': current_user.get_ollama_keys(),
        'ocr_keys': current_user.get_ocr_keys()
    })


@auth_bp.route('/forgot_password', methods=['POST'])
def forgot_password():
    ip = _ip_cliente()
    janela_reset = current_app.config['AUTH_RESET_JANELA_H'] * 3600
    maximo_reset = current_app.config['AUTH_RESET_MAX']
    bloqueio = _bloqueado(ip, maximo_reset, janela_reset, 'esqueci-senha')
    if bloqueio:
        return bloqueio
    rate_limit.registrar(ip, janela_reset, maximo_reset)

    data = _json()
    email = (data.get('email') or '').strip().lower() if isinstance(data.get('email'), str) else ''
    if not email or not EMAIL_REGEX.match(email):
        return jsonify({'success': True, 'message': MENSAGEM_RESET_GENERICA})

    cooldown_chave = f"esqueci_email:{email}"
    if rate_limit.bloqueado(cooldown_chave, 60, 1):
        return jsonify({'success': True, 'message': MENSAGEM_RESET_GENERICA})
    rate_limit.registrar(cooldown_chave, 60, 1)

    user = _buscar_por_email(email)
    if not user:
        logger.info("[AUTH] Solicitação de redefinição para e-mail não cadastrado.")
        return jsonify({'success': True, 'message': MENSAGEM_RESET_GENERICA})

    token = secrets.token_urlsafe(36)
    user.reset_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    minutos = current_app.config['RESET_TOKEN_MINUTES']
    user.reset_expires_at = datetime.utcnow() + timedelta(minutes=minutos)
    try:
        db.session.commit()
    except Exception as erro:  
        db.session.rollback()
        logger.error(f"[AUTH] Falha ao gravar token de redefinição: {type(erro).__name__}")
        return jsonify({'success': True, 'message': MENSAGEM_RESET_GENERICA})

    link = f"{current_app.config['FRONTEND_URL']}/redefinir-senha?token={token}"
    enviou = email_service.enviar_email_recuperacao(
        user.email, user.username, link, minutos
    )
    if not enviou:
        logger.error(
            f"[AUTH] Não foi possível enviar o e-mail de redefinição para "
            f"{user.email} — verifique a configuração SMTP no .env."
        )
    return jsonify({'success': True, 'message': MENSAGEM_RESET_GENERICA})


@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    janela_reset = current_app.config['AUTH_RESET_JANELA_H'] * 3600
    maximo_reset = current_app.config['AUTH_RESET_MAX']
    bloqueio = _bloqueado(_ip_cliente(), maximo_reset, janela_reset, 'redefinir-senha')
    if bloqueio:
        return bloqueio
    rate_limit.registrar(_ip_cliente(), janela_reset, maximo_reset)

    data = _json()
    token = data.get('token') if isinstance(data.get('token'), str) else ''
    senha = data.get('password')
    confirmacao = data.get('password_confirm')

    if not token:
        return jsonify({'error': 'Link de redefinição inválido ou ausente.'}), 400
    if confirmacao is not None and senha != confirmacao:
        return jsonify({'error': 'As senhas não conferem.'}), 400

    senha_err = _validar_senha(senha)
    if senha_err:
        return jsonify({'error': senha_err}), 400

    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    user = User.query.filter_by(reset_token_hash=token_hash).first()
    if not user:
        return jsonify({'error': 'Link de redefinição inválido ou expirado.'}), 400
    if not user.reset_expires_at or user.reset_expires_at < datetime.utcnow():
        user.reset_token_hash = None
        user.reset_expires_at = None
        db.session.commit()
        return jsonify({'error': 'Link de redefinição inválido ou expirado.'}), 400

    user.set_password(senha)
    user.reset_token_hash = None
    user.reset_expires_at = None
    try:
        db.session.commit()
    except Exception as erro:  
        db.session.rollback()
        logger.error(f"[AUTH] Falha ao redefinir senha: {type(erro).__name__}")
        return jsonify({'error': 'Não foi possível redefinir a senha.'}), 500

    rate_limit.limpar(f"login:{_ip_cliente()}|{user.email.lower()}")
    if current_user.is_authenticated and current_user.id == user.id:
        logout_user()
        session.pop('user_id', None)

    logger.info(f"[AUTH] Senha redefinida para o usuário {user.username}.")
    return jsonify({
        'success': True,
        'message': 'Senha redefinida com sucesso. Já pode entrar na sua conta.',
    })


@auth_bp.route('/update_keys', methods=['POST'])
@login_required
def update_keys():
    data = _json()
    if not data:
        logger.error("Dados inválidos (não é JSON)")
        return jsonify({'error': 'Dados inválidos'}), 400

    ollama_keys = data.get('ollama_keys')
    if ollama_keys is None:
        ollama_keys = data.get('ollamaKeys')
    ocr_keys = data.get('ocr_keys')
    if ocr_keys is None:
        ocr_keys = data.get('ocrKeys')

    if ollama_keys is not None:
        current_user.set_ollama_keys(ollama_keys)
        logger.info(
            f"Ollama keys atualizadas: {len(ollama_keys) if isinstance(ollama_keys, list) else 1} chave(s)."
        )
    if ocr_keys is not None:
        current_user.set_ocr_keys(ocr_keys)
        logger.info(
            f"OCR keys atualizadas: {len(ocr_keys) if isinstance(ocr_keys, list) else 1} chave(s)."
        )

    try:
        db.session.commit()
        logger.info("Dados salvos com sucesso no banco.")
    except Exception as e:
        logger.error(f"Erro ao salvar no banco: {e}")
        return jsonify({'error': 'Erro interno ao salvar'}), 500

    return jsonify({'success': True})
