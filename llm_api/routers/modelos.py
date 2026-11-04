import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from llm import provedores
from core.config import AVAILABLE_MODELS_LIST
from llm.modelos_catalogo import e_modelo_vision, listar_modelos

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=list)
def get_models(vision: bool = False):
    def _fetch():
        try:
            return listar_modelos()
        except Exception as e:
            logger.warning(f"[modelos] Falha ao montar catalogo: {e}")
            return list(AVAILABLE_MODELS_LIST)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch)
        try:
            nomes = future.result(timeout=10)
        except FuturesTimeoutError:
            logger.warning("[modelos] Timeout ao montar catalogo; usando fallback .env")
            nomes = list(AVAILABLE_MODELS_LIST)

    if vision:
        nomes = [m for m in nomes if e_modelo_vision(m)]
    result = []
    for model in nomes:
        result.append({
            "name": model,
            "vision_support": e_modelo_vision(model)
        })
    try:
        prefixados = provedores.listar_modelos_prefixados()
        if vision:
            prefixados = [m for m in prefixados if provedores.eh_modelo_vision(m.get("name"))]
        result.extend(prefixados)
    except Exception as e:
        logger.warning(f"[provedores] Falha ao montar catalogo externo: {e}")
    return result


@router.get("/provedores", response_model=list)
def get_provedores():
    return [
        {"id": pid, "nome": cfg["nome"]}
        for pid, cfg in provedores.PROVEDORES.items()
    ]


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/update_config")
def update_config(data: dict):
    ollama_key = data.get('OLLAMA_API_KEY')
    ocr_key = data.get('OCR_SPACE_API_KEY')
    if ollama_key is not None:
        os.environ['OLLAMA_API_KEY'] = ollama_key
    if ocr_key is not None:
        os.environ['OCR_SPACE_API_KEY'] = ocr_key
    return {"status": "ok"}
