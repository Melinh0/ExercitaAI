from flask import Blueprint, jsonify, request, url_for
from models.topic_model import TopicModel
from flask_login import current_user
import logging
import os

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

PROVEDORES_CONHECIDOS = {'openai', 'groq', 'gemini', 'openrouter', 'deepseek', 'anthropic', 'nvidia'}

PROVEDORES_PADRAO = [
    {'id': 'openai', 'nome': 'OpenAI'},
    {'id': 'groq', 'nome': 'Groq'},
    {'id': 'gemini', 'nome': 'Google Gemini'},
    {'id': 'openrouter', 'nome': 'OpenRouter'},
    {'id': 'deepseek', 'nome': 'DeepSeek'},
    {'id': 'anthropic', 'nome': 'Anthropic'},
    {'id': 'nvidia', 'nome': 'NVIDIA'},
]


def _filtrar_por_chaves(nomes, chaves):
    tem_ollama = False
    for chave in chaves:
        prefixo, separador, valor = chave.partition('=')
        if separador and prefixo in PROVEDORES_CONHECIDOS and valor.strip():
            continue
        if chave.strip():
            tem_ollama = True
            break
    if tem_ollama:
        return nomes
    return [nome for nome in nomes if '/' in nome]

@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@api_bp.route('/topics', methods=['GET'])
def get_topics():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401
    topics = TopicModel.list_topics(current_user)
    return jsonify(topics)

@api_bp.route('/topics/<topic_name>', methods=['GET'])
def get_topic(topic_name):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401
    images_folder = TopicModel.get_images_folder(current_user, topic_name)
    if not os.path.exists(images_folder):
        return jsonify({'error': 'Tópico não encontrado.'}), 404
    image_files = TopicModel.get_image_files(current_user, topic_name)
    resolutions = TopicModel.get_resolutions(current_user, topic_name)

    for item in resolutions:
        for questao in item.get('questoes', []):
            whiteboard_img = questao.get('whiteboard_img')
            if whiteboard_img:
                questao['whiteboard_url'] = url_for('static', filename=f'whiteboards/topics/{topic_name}/{whiteboard_img}', _external=False)
            else:
                questao['whiteboard_url'] = None

    return jsonify({
        'image_files': image_files,
        'resolutions': resolutions
    })

@api_bp.route('/topics', methods=['POST'])
def create_topic():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401
    nome = request.form.get('nome', '').strip()
    if not nome:
        return jsonify({'success': False, 'error': 'Nome do tópico é obrigatório.'}), 400
    safe_name = TopicModel.create_topic(current_user, nome)
    return jsonify({'success': True, 'topic': safe_name})

@api_bp.route('/topics/suggest-name', methods=['POST'])
def suggest_topic_name():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401
    data = request.get_json() or {}
    nome = (data.get('nome') or '').strip()
    descricao = (data.get('descricao') or '').strip()
    if not nome and not descricao:
        return jsonify({'success': False, 'error': 'Digite um nome ou descreva o foco antes de pedir a sugestão.'}), 400
    chaves = current_user.get_ollama_keys()
    if not chaves:
        return jsonify({
            'success': False,
            'error': 'Cadastre uma chave de API em Configurações para usar sugestões.',
            'error_code': 'missing_ollama_key',
        }), 403
    try:
        from services.rag_client import post_llm_api
        resp = post_llm_api(
            '/suggest_topic_name',
            json={'nome': nome, 'descricao': descricao},
            chaves=chaves,
            timeout=(10, 90),
        )
        if not resp.ok:
            logger.warning(f"/api/topics/suggest-name: llm_api respondeu HTTP {resp.status_code}.")
            return jsonify({'success': False, 'error': 'Não foi possível gerar a sugestão agora.'}), 502
        corpo = resp.json()
        return jsonify({
            'success': True,
            'sugestao': (corpo.get('sugestao') or '').strip(),
            'justificativa': (corpo.get('justificativa') or '').strip(),
        })
    except Exception as e:
        logger.error(f"Erro ao sugerir nome de tópico: {e}")
        return jsonify({'success': False, 'error': 'Serviço de sugestão indisponível no momento.'}), 502

@api_bp.route('/models', methods=['GET'])
def get_models():
    so_vision = request.args.get('vision', '').lower() in ('1', 'true', 'yes')
    chaves = current_user.get_ollama_keys() if current_user.is_authenticated else []
    try:
        from services.rag_client import get_llm_api
        rota = '/models?vision=true' if so_vision else '/models'
        resp = get_llm_api(rota, timeout=20, chaves=chaves)
        if resp.ok and isinstance(resp.json(), list):
            nomes = []
            for item in resp.json():
                nome = item.get('name') if isinstance(item, dict) else item
                if isinstance(nome, str) and nome.strip():
                    nomes.append(nome.strip())
            return jsonify(_filtrar_por_chaves(nomes, chaves))
        logger.warning(
            f"/api/models: llm_api respondeu HTTP {resp.status_code}; usando lista do .env."
        )
    except Exception as e:
        logger.warning(f"/api/models: catalogo dinamico indisponivel ({e}); usando lista do .env.")
    models_str = os.environ.get('OLLAMA_AVAILABLE_MODELS', '')
    all_models = [m.strip() for m in models_str.split(',') if m.strip()] if models_str else []
    try:
        from services.rag_client import get_llm_api
        resp = get_llm_api('/provedores', timeout=5, chaves=[])
        if resp.ok:
            provedores_data = resp.json()
            for p in provedores_data:
                pid = p.get('id')
                if pid in PROVEDORES_CONHECIDOS:
                    resp_m = get_llm_api(f'/models?provider={pid}', timeout=5, chaves=[])
                    if resp_m.ok:
                        for m in resp_m.json():
                            nome = m.get('name') if isinstance(m, dict) else m
                            if isinstance(nome, str) and nome.strip():
                                all_models.append(nome.strip())
    except Exception:
        pass
    if not all_models:
        default = os.getenv('DEFAULT_MODEL', 'gemma3:4b')
        all_models = [default]
    if so_vision:
        vis = {m.strip() for m in os.environ.get('OLLAMA_VISION_MODELS', '').split(',') if m.strip()}
        all_models = [m for m in all_models if m in vis]
    return jsonify(_filtrar_por_chaves(all_models, chaves))

@api_bp.route('/provedores', methods=['GET'])
def get_provedores():
    try:
        from services.rag_client import get_llm_api
        resp = get_llm_api('/provedores', timeout=15, chaves=[])
        if resp.ok and isinstance(resp.json(), list) and resp.json():
            return jsonify(resp.json())
        logger.warning(f"/api/provedores: llm_api respondeu HTTP {resp.status_code}.")
    except Exception as e:
        logger.warning(f"/api/provedores: lista de provedores indisponivel ({e}).")
    return jsonify(PROVEDORES_PADRAO)

@api_bp.route('/model_info', methods=['GET'])
def get_model_info():
    from services import model_info_service
    bruto = request.args.get('models', '')
    extras = [m for m in bruto.split(',') if m.strip()][:80]
    model_info_service.disparar_garantia(extras)
    return jsonify({'model_info': model_info_service.carregar()})