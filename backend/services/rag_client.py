import requests
import logging
import time
from config import Config
from flask_login import current_user
from services.ollama_guard import get_user_ollama_keys

logger = logging.getLogger(__name__)


def mensagem_de_erro_requisicao(resp):
    try:
        corpo = resp.json() or {}
    except Exception:
        corpo = {}
    return str(corpo.get("detail") or f"Falha ao consultar o servico de IA (HTTP {resp.status_code})")


def post_llm_api(endpoint, json=None, timeout=90, chaves=None, headers=None, **kwargs):
    if chaves is None:
        chaves = get_user_ollama_keys()
    chaves = [c.strip() for c in chaves if isinstance(c, str) and c.strip()]
    hdrs = dict(headers or {})
    if chaves:
        hdrs["X-Ollama-Keys"] = ",".join(chaves)
    return requests.post(
        f"{Config.RAG_SERVICE_URL}{endpoint}",
        json=json,
        headers=hdrs or None,
        timeout=timeout,
        **kwargs,
    )


def get_llm_api(endpoint, timeout=20, chaves=None, headers=None, **kwargs):
    if chaves is None:
        chaves = get_user_ollama_keys()
    chaves = [c.strip() for c in chaves if isinstance(c, str) and c.strip()]
    hdrs = dict(headers or {})
    if chaves:
        hdrs["X-Ollama-Keys"] = ",".join(chaves)
    return requests.get(
        f"{Config.RAG_SERVICE_URL}{endpoint}",
        headers=hdrs or None,
        timeout=timeout,
        **kwargs,
    )


def extract_text_from_image(image_base64: str) -> str:
    try:
        resp = post_llm_api(
            "/extract_text_from_image",
            json={"image_base64": image_base64},
            timeout=120
        )
        if resp.ok:
            return resp.json().get("text", "")
        logger.error(f"Falha ao extrair texto da imagem: {resp.status_code} - {resp.text}")
        return ""
    except Exception as e:
        logger.exception(f"Erro ao chamar extract_text_from_image: {e}")
        return ""


def index_documents(chunks: list, metadatas: list, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{Config.RAG_SERVICE_URL}/index_documents",
                json={"chunks": chunks, "metadatas": metadatas},
                timeout=300
            )
            if resp.ok:
                return resp.json()
            logger.error(
                f"Falha ao indexar documentos (tentativa {attempt + 1}/{max_retries}): "
                f"{resp.status_code} - {resp.text[:200]}"
            )
        except requests.exceptions.Timeout as e:
            logger.warning(
                f"Timeout em index_documents (tentativa {attempt + 1}/{max_retries}): {e}"
            )
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Erro de rede em index_documents (tentativa {attempt + 1}/{max_retries}): {e}"
            )
        except Exception as e:
            logger.exception(
                f"Erro inesperado em index_documents (tentativa {attempt + 1}/{max_retries}): {e}"
            )

        if attempt < max_retries - 1:
            delay = 3 * (attempt + 1)
            logger.info(f"Aguardando {delay}s antes da proxima tentativa...")
            time.sleep(delay)

    logger.error(
        f"index_documents falhou apos {max_retries} tentativas. "
        f"Lote de {len(chunks)} chunks foi PERDIDO."
    )
    return None


def retrieve_context(user_id: int, topic: str, query: str, n_results: int = 5,
                     max_retries: int = 2, ollama_keys=None,
                     similarity_threshold: float = None) -> str:
    if ollama_keys is None:
        ollama_keys = []
        try:
            if current_user and current_user.is_authenticated:
                ollama_keys = current_user.get_ollama_keys()
        except Exception:
            ollama_keys = []

    if similarity_threshold is None:
        similarity_threshold = Config.RAG_SIMILARITY_THRESHOLD

    for attempt in range(max_retries):
        try:
            payload = {
                "topic": topic,
                "query": query,
                "n_results": n_results,
                "similarity_threshold": similarity_threshold,
                "user_id": user_id,
                "ollama_keys": ollama_keys,
            }
            resp = requests.post(
                f"{Config.RAG_SERVICE_URL}/retrieve_context",
                json=payload,
                timeout=90
            )
            if resp.ok:
                return resp.json().get("context", "")
            logger.error(
                f"Falha ao recuperar contexto (tentativa {attempt + 1}): "
                f"{resp.status_code} - {resp.text[:200]}"
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return ""
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout ao recuperar contexto (tentativa {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return ""
        except Exception as e:
            logger.exception(f"Erro ao chamar retrieve_context: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return ""
    return ""


def remove_topic_vectors(topic, user_id=None, source=None, max_retries=2):
    payload = {"topic": topic}
    if user_id is not None:
        payload["user_id"] = user_id
    if source:
        payload["source"] = source
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{Config.RAG_SERVICE_URL}/remove_topic_vectors",
                json=payload,
                timeout=30
            )
            if resp.ok:
                return True
            logger.warning(
                f"remove_topic_vectors falhou (tentativa {attempt + 1}): "
                f"{resp.status_code} - {resp.text[:200]}"
            )
        except Exception as e:
            logger.warning(
                f"Erro ao chamar remove_topic_vectors "
                f"(tentativa {attempt + 1}): {e}"
            )
        if attempt < max_retries - 1:
            time.sleep(1)
    return False


def rename_topic_vectors(old_topic, new_topic, user_id=None, max_retries=2):
    payload = {"old_topic": old_topic, "new_topic": new_topic}
    if user_id is not None:
        payload["user_id"] = user_id
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{Config.RAG_SERVICE_URL}/rename_topic_vectors",
                json=payload,
                timeout=30
            )
            if resp.ok:
                return True
            logger.warning(
                f"rename_topic_vectors falhou (tentativa {attempt + 1}): "
                f"{resp.status_code} - {resp.text[:200]}"
            )
        except Exception as e:
            logger.warning(
                f"Erro ao chamar rename_topic_vectors "
                f"(tentativa {attempt + 1}): {e}"
            )
        if attempt < max_retries - 1:
            time.sleep(1)
    return False