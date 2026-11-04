import logging
import os

from llm import provedores
from core.config import AVAILABLE_MODELS_LIST
from llm.modelos_catalogo import listar_modelos
from llm.ollama_client import padrao_para_o_usuario

logger = logging.getLogger(__name__)


def get_available_models():
    nomes = []
    try:
        nomes = listar_modelos()
    except Exception as e:
        logger.warning(f"[modelos] Catalogo dinamico indisponivel: {e}")
    for model in AVAILABLE_MODELS_LIST:
        if model not in nomes:
            nomes.append(model)
    return nomes


def get_default_model():
    padrao_provedor = padrao_para_o_usuario()
    if padrao_provedor:
        return padrao_provedor
    explicito = os.getenv('DEFAULT_MODEL', '').strip()
    models = get_available_models()
    if explicito and (not models or explicito in models):
        return explicito
    if models:
        return models[0]
    return explicito or 'gemma3:4b'


def validate_model(model):
    if not model:
        return get_default_model()
    if provedores.eh_modelo(model):
        parsed = provedores.parsear_modelo(model)
        if provedores.chaves_efetivas(parsed[0]):
            return model
        alvo = padrao_para_o_usuario() or get_default_model()
        logger.warning(
            f"Modelo '{model}' sem chave de provedor cadastrada; usando '{alvo}'."
        )
        return alvo
    alvo_provedor = padrao_para_o_usuario()
    if alvo_provedor:
        logger.warning(
            f"Modelo '{model}' indisponivel para este usuario; usando '{alvo_provedor}'."
        )
        return alvo_provedor
    available = get_available_models()
    if available and model in available:
        return model
    if available:
        logger.warning(
            f"Modelo '{model}' fora do catalogo disponivel; usando '{available[0]}'."
        )
        return available[0]
    return get_default_model()
