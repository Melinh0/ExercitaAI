import json
import logging
import os
import threading
import time

import requests

from config import Config

logger = logging.getLogger(__name__)

MODELOS_COM_TEXTO_CURADO = {"gemma4:cloud", "gemma4:31b-cloud"}

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
ARQUIVO = os.path.join(_DATA_DIR, "model_info.json")

RAG_URL = os.getenv("RAG_SERVICE_URL", Config.RAG_SERVICE_URL)

_trava = threading.Lock()
_em_andamento = False


def carregar():
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"[model_info] Falha ao ler {ARQUIVO}: {e}")
        return {}


def salvar(dados):
    os.makedirs(_DATA_DIR, exist_ok=True)
    tmp = ARQUIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARQUIVO)


def _modelos_do_env():
    bruto = os.getenv("OLLAMA_AVAILABLE_MODELS", "")
    if bruto:
        return [m.strip() for m in bruto.split(",") if m.strip()]
    return [os.getenv("DEFAULT_MODEL", "gemma3:4b")]


def _modelos_atuais():
    try:
        resp = requests.get(f"{RAG_URL}/models", timeout=20)
        if resp.ok and isinstance(resp.json(), list):
            nomes = []
            for item in resp.json():
                nome = item.get("name") if isinstance(item, dict) else item
                if isinstance(nome, str) and nome.strip():
                    nomes.append(nome.strip())
            if nomes:
                return nomes
        logger.warning(
            f"[model_info] Catalogo dinamico respondeu HTTP {resp.status_code}."
        )
    except Exception as e:
        logger.warning(f"[model_info] Catalogo dinamico indisponivel: {e}")
    return _modelos_do_env()


def _esperar_llm_api(timeout_total=180):
    limite = time.time() + timeout_total
    while time.time() < limite:
        try:
            resp = requests.get(f"{RAG_URL}/health", timeout=5)
            if resp.ok:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
    return False


def _gerar(modelo):
    try:
        resp = requests.post(
            f"{RAG_URL}/generate_model_info",
            json={"model_name": modelo},
            timeout=300,
        )
        if resp.ok:
            info = (resp.json() or {}).get("info")
            if isinstance(info, dict) and info.get("description"):
                return info
        logger.warning(
            f"[model_info] Falha ao gerar texto de '{modelo}': "
            f"HTTP {resp.status_code} - {resp.text[:200]}"
        )
    except Exception as e:
        logger.warning(f"[model_info] Erro ao gerar texto de '{modelo}': {e}")
    return None


def garantir_textos(extras=None):
    global _em_andamento
    with _trava:
        if _em_andamento:
            return
        _em_andamento = True
    try:
        dados = carregar()
        extras = [
            m.strip() for m in (extras or [])
            if isinstance(m, str) and m.strip()
        ][:80]
        alvos = [
            m
            for m in _modelos_atuais() + extras
            if m not in dados and m not in MODELOS_COM_TEXTO_CURADO
        ]
        if not alvos:
            logger.info("[model_info] Todos os modelos já têm texto informativo.")
            return
        logger.info(
            f"[model_info] Modelos sem texto informativo: {alvos}. "
            "Aguardando llm_api para gerar via gemma..."
        )
        if not _esperar_llm_api():
            logger.warning(
                "[model_info] llm_api indisponível; os textos serão gerados "
                "na próxima inicialização."
            )
            return
        for modelo in alvos:
            info = _gerar(modelo)
            if info:
                dados[modelo] = info
                salvar(dados)
                logger.info(f"[model_info] Texto informativo gerado para '{modelo}'.")
    except Exception as e:
        logger.warning(f"[model_info] Verificação interrompida: {e}")
    finally:
        with _trava:
            _em_andamento = False


def disparar_garantia(extras=None):
    if _em_andamento:
        return
    threading.Thread(
        target=garantir_textos,
        args=(extras,),
        daemon=True,
        name="garantir_model_info",
    ).start()
