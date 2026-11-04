import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import VISION_MODELS_LIST
from servicos.ocr import (
    extract_text_with_tesseract_robust,
    fallback_vision_transcription,
    is_text_valid,
    ocr_space_extract_text,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ExtractTextRequest(BaseModel):
    image_base64: str


@router.post("/extract_text_from_image")
def extract_text_from_image(req: ExtractTextRequest):
    try:
        text = ""
        if VISION_MODELS_LIST:
            logger.info("Tentando transcricao com modelo de visao para extracao de texto...")
            vision_text = fallback_vision_transcription(req.image_base64)
            if is_text_valid(vision_text):
                text = vision_text
                logger.info("Modelo de visao bem-sucedido para extracao.")
            else:
                logger.warning("Modelo de visao falhou para extracao.")

        if not is_text_valid(text):
            logger.info("Tentando Tesseract robusto para extracao...")
            tesseract_text = extract_text_with_tesseract_robust(req.image_base64, lang='por+eng')
            if is_text_valid(tesseract_text):
                text = tesseract_text
            elif tesseract_text and len(tesseract_text.strip()) > 30:
                text = tesseract_text
            else:
                logger.warning("Tesseract falhou para extracao.")

        if not is_text_valid(text) and os.getenv('OCR_SPACE_API_KEY'):
            logger.info("Tentando OCR.space para extracao...")
            ocr_space_text = ocr_space_extract_text(req.image_base64, engine=2)
            if is_text_valid(ocr_space_text):
                text = ocr_space_text
            elif ocr_space_text and len(ocr_space_text.strip()) > 30:
                text = ocr_space_text
            else:
                logger.warning("OCR.space falhou para extracao.")

        if not text or len(text.strip()) < 15:
            logger.warning("Todos os metodos retornaram texto insuficiente para extracao.")
            return {"text": ""}

        return {"text": text}
    except Exception as e:
        logger.warning(f"Erro em extract_text_from_image: {e}")
        return {"text": ""}
