import logging
import threading
import time

import requests

from core.config import (
    AVAILABLE_MODELS_LIST,
    FREE_MODELS_LIST,
    OLLAMA_API_KEYS,
    OLLAMA_HOST,
    VISION_MODELS_LIST,
)
from llm.ollama_client import chaves_do_usuario

logger = logging.getLogger(__name__)

TTL_FRESCO = 900
TTL_FALHA = 60
TIMEOUT_TAGS = 8

_cache = {"expira": 0.0, "nomes": []}
_trava_cache = threading.Lock()


def _pool_de_chaves():
    chaves = chaves_do_usuario.get()
    if chaves:
        return [c for c in chaves if c] or list(OLLAMA_API_KEYS)
    return list(OLLAMA_API_KEYS)


def _buscar_nomes(pool):
    for chave in pool or [None]:
        headers = {"Authorization": f"Bearer {chave}"} if chave else {}
        try:
            resp = requests.get(
                f"{OLLAMA_HOST}/api/tags", headers=headers, timeout=TIMEOUT_TAGS
            )
        except Exception as e:
            logger.warning(f"[modelos] /api/tags indisponivel: {e}")
            break
        if resp.status_code in (401, 403):
            logger.warning(
                f"[modelos] Chave Ollama recusada pelo /api/tags (HTTP {resp.status_code})."
            )
            continue
        if resp.status_code == 429:
            logger.warning("[modelos] Rate limit no /api/tags; tentando proxima chave.")
            continue
        if not resp.ok:
            logger.warning(f"[modelos] /api/tags respondeu HTTP {resp.status_code}.")
            break
        try:
            dados = resp.json()
        except ValueError:
            break
        modelos = dados.get("models") if isinstance(dados, dict) else None
        nomes = []
        for item in modelos or []:
            if isinstance(item, dict):
                nome = item.get("name") or item.get("model")
                if isinstance(nome, str) and nome.strip():
                    nomes.append(nome.strip())
        return nomes
    return None


def _so_gratuitos(nomes):
    livres = [m.strip() for m in FREE_MODELS_LIST if m and m.strip()]
    if "*" in livres:
        return list(nomes)
    conjunto = set(livres)
    return [n for n in nomes if n in conjunto]


def _carregar():
    expira = time.time() + TTL_FRESCO
    nomes = _buscar_nomes(_pool_de_chaves())
    if nomes is None:
        return time.time() + TTL_FALHA, []
    nomes = _so_gratuitos(nomes)
    if not nomes:
        logger.warning(
            "[modelos] Intersecao catalogo/gratuitos vazia; usando lista do .env."
        )
        return time.time() + TTL_FALHA, []
    return expira, sorted(nomes)
    return expira, nomes


def listar_modelos():
    agora = time.time()
    with _trava_cache:
        if _cache["expira"] > agora and _cache["nomes"]:
            return list(_cache["nomes"])
        expira, nomes = _carregar()
        if nomes:
            _cache["expira"] = expira
            _cache["nomes"] = nomes
        elif _cache["nomes"]:
            _cache["expira"] = agora + TTL_FALHA
        elif AVAILABLE_MODELS_LIST:
            return list(AVAILABLE_MODELS_LIST)
        return list(_cache["nomes"])


def e_modelo_vision(nome):
    if not nome:
        return False
    if nome in VISION_MODELS_LIST:
        return True
    base = nome.split(":", 1)[0]
    return any(v.split(":", 1)[0] == base for v in VISION_MODELS_LIST)
