import base64
import io
import logging
import os
import re

import requests
import pytesseract
from PIL import Image

from core.config import VISION_MODELS_LIST
from llm.ollama_client import get_ollama_response_with_image_multi
from servicos.imagens import decode_image, VARIANT_BUILDERS

logger = logging.getLogger(__name__)

PORTUGUESE_COMMON_WORDS = frozenset([
    "de", "a", "o", "que", "e", "do", "da", "em", "um", "para", "com",
    "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos",
    "como", "mas", "foi", "ao", "ele", "das", "tem", "seu", "sua", "ou",
    "ser", "quando", "muito", "nos", "já", "está", "eu", "também", "só",
    "pelo", "pela", "até", "isso", "ela", "entre", "era", "depois", "sem",
    "mesmo", "aos", "ter", "seus", "quem", "nas", "me", "esse", "eles",
    "estão", "você", "tinha", "foram", "essa", "num", "nem", "suas", "meu",
    "às", "minha", "têm", "numa", "pelos", "elas", "havia", "seja", "qual",
    "será", "nós", "tenho", "lhe", "deles", "essas", "esses", "pelas",
    "este", "fosse", "dele", "dela", "sobre", "todos", "todas", "onde",
    "pode", "são", "então", "agora", "aqui", "assim", "cada", "vai", "vem",
    "fazer", "tudo", "nada", "algo", "outro", "outra", "processo",
    "sistema", "tempo", "exemplo", "questao", "questão", "resposta",
    "explicacao", "explicação", "calculo", "cálculo", "formula", "fórmula",
    "valor", "total", "numero", "número"
])

PSM_MODES = [6, 4, 3, 11, 1]


def score_ocr_text(text: str) -> float:
    if not text:
        return -1.0
    score = 0.0
    stripped = text.strip()
    if len(stripped) < 10:
        return -1.0
    score += min(len(stripped), 3000) * 0.01
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]+\b', stripped.lower())
    word_count = len(words)
    if word_count == 0:
        return score
    pt_hits = sum(1 for w in words if w in PORTUGUESE_COMMON_WORDS)
    score += pt_hits * 0.8
    printable = sum(1 for c in stripped if c.isprintable())
    score += (printable / len(stripped)) * 5.0
    alnum = sum(1 for c in stripped if c.isalnum())
    if alnum / max(len(stripped), 1) < 0.25:
        score -= 5.0
    letters = sum(1 for c in stripped if c.isalpha())
    if letters > 0:
        upper_ratio = sum(1 for c in stripped if c.isupper()) / letters
        if upper_ratio > 0.7 and len(stripped) > 100:
            score -= 3.0
    rotulos = re.findall(r"(?m)^\s*([a-h])\)+", stripped, flags=re.IGNORECASE)
    if len(rotulos) >= 3:
        sequencia = [ord(r.lower()) - ord("a") for r in rotulos]
        if sequencia != list(range(sequencia[0], sequencia[0] + len(sequencia))):
            score -= 2.0
    return score


def is_text_valid(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < 15:
        return False
    words = stripped.split()
    if len(words) < 2:
        return False
    printable = sum(1 for c in stripped if c.isprintable() or c in '\n\t')
    if printable / len(stripped) < 0.85:
        return False
    alnum_or_math = sum(
        1 for c in stripped
        if c.isalnum() or c in ' \n\t.,;:!?()[]{}=+-*/<>≤≥≠∞→←↑↓∑∫√±×÷'
    )
    if alnum_or_math / len(stripped) < 0.6:
        return False
    return True


def extract_text_with_tesseract_robust(image_base64: str, lang: str = 'por+eng') -> str:
    try:
        image_bytes = decode_image(image_base64)
        if not image_bytes:
            return ""
    except Exception as e:
        logger.warning(f"Falha ao decodificar imagem: {e}")
        return ""

    candidates = []
    for variant_name, builder in VARIANT_BUILDERS:
        try:
            img = builder(image_bytes)
        except Exception as e:
            logger.warning(f"Variante {variant_name} falhou: {e}")
            continue

        for psm in PSM_MODES:
            config = f'--oem 3 --psm {psm}'
            try:
                text = pytesseract.image_to_string(img, lang=lang, config=config)
                text = text.strip()
                if not text:
                    continue
                score = score_ocr_text(text)
                candidates.append((score, variant_name, psm, text))
            except Exception as e:
                logger.debug(f"Variante {variant_name} PSM {psm} falhou: {e}")
                continue

        try:
            text_alt_lang = pytesseract.image_to_string(img, lang='por', config='--oem 3 --psm 6')
            text_alt_lang = text_alt_lang.strip()
            if text_alt_lang:
                score = score_ocr_text(text_alt_lang)
                candidates.append((score, variant_name + "_por", 6, text_alt_lang))
        except Exception:
            pass

    if not candidates:
        logger.warning("Nenhuma variante de OCR retornou texto.")
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_variant, best_psm, best_text = candidates[0]
    logger.info(
        f"[OCR] Melhor resultado: variante={best_variant} psm={best_psm} "
        f"score={best_score:.2f} chars={len(best_text)} "
        f"(de {len(candidates)} candidatos)"
    )
    if best_score <= 0:
        logger.warning("[OCR] Melhor score <= 0. Retornando texto mesmo assim.")
    return best_text


def fallback_vision_transcription(image_base64: str, extra_prompt: str = "", max_width: int = 1024, modelo: str | None = None) -> str:
    try:
        image_bytes = decode_image(image_base64)
        if not image_bytes:
            return ""
        img = Image.open(io.BytesIO(image_bytes))
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=90)
        resized_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        base_prompt = (
            "Voce e um transcritor de imagens especialista. "
            "Transcreva TODO o texto visivel na imagem, incluindo cabecalhos, enunciados, "
            "numeracoes de questoes e subitens. Preserve pontuacao, acentos e quebras de linha. "
            "Nao adicione comentarios, apenas o texto literal."
        )
        if extra_prompt:
            base_prompt += f"\nInstrucoes adicionais: {extra_prompt}\n"
        candidatos = [modelo] if modelo else list(VISION_MODELS_LIST)
        for vision_model in candidatos:
            try:
                response = get_ollama_response_with_image_multi(
                    vision_model, base_prompt, [resized_base64]
                )
                if response and len(response) > 30:
                    return response.strip()
            except Exception as e:
                logger.warning(f"Vision fallback {vision_model} falhou: {e}")
                continue
        return ""
    except Exception as e:
        logger.warning(f"Erro em fallback_vision_transcription: {e}")
        return ""


def ocr_space_extract_text(base64_image: str, engine: int = 2) -> str:
    try:
        data = decode_image(base64_image)
        if not data:
            return ""
        b64_with_prefix = (
            f"data:image/jpeg;base64,"
            f"{data.replace(chr(10), '').replace(chr(13), '')}"
        )
        url = "https://api.ocr.space/parse/image"
        payload = {
            'apikey': os.getenv('OCR_SPACE_API_KEY', ''),
            'isOverlayRequired': 'false',
            'base64Image': b64_with_prefix,
            'OCREngine': engine,
            'scale': 'true',
            'language': 'por'
        }
        logger.info(f"Enviando imagem para OCR.space (Engine {engine})...")
        response = requests.post(url, data=payload, timeout=(15, 30))
        result = response.json()
        if result.get('IsErroredOnProcessing'):
            error_msg = result.get('ErrorMessage', ['Erro desconhecido'])
            logger.error(f"Erro no OCR.space: {error_msg}")
            return ""
        parsed_text = ""
        for text_block in result.get('ParsedResults', []):
            parsed_text += text_block.get('ParsedText', '') + "\n"
        return parsed_text.strip()
    except requests.exceptions.Timeout:
        return ""
    except Exception:
        return ""
