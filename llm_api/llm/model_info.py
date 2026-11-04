import logging
import os

from core.json_utils import extract_json_from_response
from llm.ollama_client import get_ollama_response
from core.prompt_loader import load_prompt
from llm import provedores

logger = logging.getLogger(__name__)

MODELO_GERADOR = os.getenv("MODEL_INFO_MODEL", "gemma4:cloud")

LINK_PREFIXO = "https://ollama.com/"


def gerar_info_modelo(model_name):
    template = load_prompt("generate_model_info")
    if not template:
        logger.error("[model_info] Prompt 'generate_model_info' nao encontrado.")
        return None
    if not model_name:
        return None

    prompt = template.replace("{MODELO}", model_name)
    resposta = get_ollama_response(
        MODELO_GERADOR,
        prompt,
        temperature=0.4,
        json_mode=True,
        min_chars=60,
    )
    dados = extract_json_from_response(resposta or "")
    return _validar(model_name, dados)


def _validar(model_name, dados):
    if not isinstance(dados, dict):
        logger.warning(
            f"[model_info] Resposta invalida para '{model_name}': esperado objeto JSON."
        )
        return None

    def _texto(chave, limite):
        valor = dados.get(chave)
        if not isinstance(valor, str) or not valor.strip():
            return None
        return valor.strip()[:limite]

    name = _texto("name", 80) or model_name
    tagline = _texto("tagline", 80)
    description = _texto("description", 700)
    best_for = _texto("bestFor", 400)
    if not tagline or not description or not best_for:
        logger.warning(
            f"[model_info] JSON de '{model_name}' sem campos obrigatorios "
            "(tagline/description/bestFor)."
        )
        return None

    def _lista(chave):
        valor = dados.get(chave)
        if not isinstance(valor, list):
            return []
        return [
            item.strip()[:140]
            for item in valor
            if isinstance(item, str) and item.strip()
        ][:6]

    link = dados.get("link")
    link = _link_valido(model_name, link)

    return {
        "name": name,
        "tagline": tagline,
        "description": description,
        "pros": _lista("pros"),
        "cons": _lista("cons"),
        "bestFor": best_for,
        "link": link,
    }


def _link_valido(model_name, link):
    parsed = provedores.parsear_modelo(model_name)
    if parsed:
        cfg = provedores.PROVEDORES[parsed[0]]
        if isinstance(link, str) and link.startswith(cfg["site"]):
            return link
        return cfg["link_padrao"]
    if isinstance(link, str) and link.startswith(LINK_PREFIXO):
        return link
    return f"https://ollama.com/library/{model_name.split(':', 1)[0]}"
