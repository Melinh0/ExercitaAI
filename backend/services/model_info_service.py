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
_validacao_paginas = {}


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


PAGINAS_MODELO_PROVEDOR = {
    "nvidia": "https://build.nvidia.com/{id}",
    "openrouter": "https://openrouter.ai/{id}",
    "groq": "https://console.groq.com/docs/model/{id}",
}


def _pagina_existe(identificador):
    if identificador in _validacao_paginas:
        return _validacao_paginas[identificador]
    resultado = None
    try:
        resp = requests.get(
            f"https://build.nvidia.com/{identificador}",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if resp.status_code == 200:
            html = resp.text
            resultado = (
                "NEXT_HTTP_ERROR_FALLBACK;404" not in html
                and "404 Error" not in html
            )
    except requests.exceptions.RequestException:
        resultado = None
    if resultado is not None:
        _validacao_paginas[identificador] = resultado
    time.sleep(0.3)
    return resultado


def _reparar_links(dados):
    reparos = 0
    for modelo, info in dados.items():
        if not isinstance(info, dict):
            continue
        provedor, _, identificador = modelo.partition("/")
        if provedor != "nvidia" or not identificador:
            continue
        existe = _pagina_existe(identificador)
        if existe is None:
            continue
        if existe:
            novo = PAGINAS_MODELO_PROVEDOR["nvidia"].format(id=identificador)
            fonte = novo
        else:
            novo = (
                "https://build.nvidia.com/search?q="
                + identificador.split("/")[-1]
            )
            fonte = ""
        if info.get("link") != novo or info.get("fonte") != fonte:
            info["link"] = novo
            info["fonte"] = fonte
            reparos += 1
    return reparos


def _modelos_atuais():
    try:
        resp = requests.get(f"{RAG_URL}/models", timeout=60)
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
        reparos = _reparar_links(dados)
        if reparos:
            salvar(dados)
            logger.info(
                f"[model_info] {reparos} link(s) da NVIDIA verificados: "
                "páginas existentes mantidas, restantes direcionados para a busca."
            )
        extras = [
            m.strip() for m in (extras or [])
            if isinstance(m, str) and m.strip()
        ][:80]
        alvos = [
            m
            for m in _modelos_atuais() + extras
            if m not in dados and m not in MODELOS_COM_TEXTO_CURADO
        ][:80]
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
            time.sleep(2)
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
