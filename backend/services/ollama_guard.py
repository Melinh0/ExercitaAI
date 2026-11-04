from functools import wraps

from flask import jsonify
from flask_login import current_user


def get_user_ollama_keys():

    try:
        if current_user.is_authenticated:
            keys = current_user.get_ollama_keys()
            if isinstance(keys, list):
                return [k for k in keys if isinstance(k, str) and k.strip()]
    except Exception:
        pass
    return []


def require_ollama_key(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not get_user_ollama_keys():
            return jsonify({
                'success': False,
                'error': (
                    'Nenhuma chave de API cadastrada para este usuário. '
                    'Cadastre uma chave do Ollama ou de outro provedor em '
                    'Configurações para usar os recursos de IA.'
                ),
                'error_code': 'missing_ollama_key',
            }), 403
        return fn(*args, **kwargs)

    return wrapper
