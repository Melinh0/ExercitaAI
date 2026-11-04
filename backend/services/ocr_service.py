import os
import io
import base64
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz
import docx
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import requests

from config import Config
from services.rag_client import extract_text_from_image

logger = logging.getLogger(__name__)

OCR_SPACE_API_KEY = Config.OCR_SPACE_API_KEY
OCR_MAX_WORKERS = Config.OCR_MAX_WORKERS
OCR_DPI = Config.OCR_DPI

OCR_SPACE_CONNECT_TIMEOUT = Config.OCR_SPACE_CONNECT_TIMEOUT
OCR_SPACE_READ_TIMEOUT = Config.OCR_SPACE_READ_TIMEOUT
OCR_SPACE_MAX_FAILURES = Config.OCR_SPACE_MAX_FAILURES
OCR_SPACE_MAX_PAGES = Config.OCR_SPACE_MAX_PAGES

NATIVE_TEXT_MIN_CHARS_PER_PAGE = 400
NATIVE_MIN_DIGIT_LETTER_RATIO = 0.02
NATIVE_MAX_SUSPICIOUS_RATIO = 0.02

_ocrspace_consecutive_failures = 0
_ocrspace_disabled = False
_ocrspace_pages_used = 0


def _strip_toc_lines(text):
    cleaned = []
    for line in text.split("\n"):
        line = line.rstrip()
        if not line.strip():
            cleaned.append("")
            continue
        if re.search(r"\.{3,}\s*\d+\s*$", line):
            continue
        if re.match(r"^\s*\d+\s+[A-Za-zÀ-ÿ].{3,}\.{3,}", line):
            continue
        if line.count(".") >= 6 and len(line) < 200:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _looks_like_toc_page(text):
    if not text or len(text.strip()) < 50:
        return False
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) < 8:
        return False
    toc_hits = 0
    for l in lines:
        if re.search(r"\.{3,}\s*\d+\s*$", l):
            toc_hits += 1
        elif re.search(r"\b\d{2,4}\s*$", l) and "." in l:
            toc_hits += 1
    ratio = toc_hits / len(lines)
    if ratio >= 0.45:
        return True
    digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
    if digit_ratio > 0.22 and "." in text:
        return True
    return False


def _looks_like_cover_page(text):
    if not text:
        return False
    if len(text.strip()) < 200 and re.search(
        r"(ISBN|EDIÇÃO|EDITION|Copyright|Todos os direitos)", text, re.IGNORECASE
    ):
        return True
    return False


SUSPICIOUS_OCR_PATTERNS = [
    re.compile(r"\bl\d+\b"),
    re.compile(r"\bl\s+int\b", re.IGNORECASE),
    re.compile(r"\bcom\d+\b"),
    re.compile(r"\bO\s+int\b", re.IGNORECASE),
    re.compile(r"\bquadr\w*\s+de\s+pagina\b", re.IGNORECASE),
]


def _native_text_quality_score(text):
    if not text or len(text.strip()) < 100:
        return 0.0
    stripped = text.strip()
    words = re.findall(r"\b[a-zA-ZÀ-ÿ]+\b", stripped)
    if not words:
        return 0.0
    digit_count = sum(c.isdigit() for c in stripped)
    letter_count = sum(c.isalpha() for c in stripped)
    total = max(len(stripped), 1)
    digit_ratio = digit_count / total
    letter_ratio = letter_count / total
    suspicious_hits = 0
    for pat in SUSPICIOUS_OCR_PATTERNS:
        suspicious_hits += len(pat.findall(stripped))
    suspicious_ratio = suspicious_hits / max(len(words), 1)
    score = 1.0
    if digit_ratio < 0.005 and re.search(r"\d{2,}", stripped) is None:
        score -= 0.15
    if suspicious_ratio > NATIVE_MAX_SUSPICIOUS_RATIO:
        score -= min(0.6, suspicious_ratio * 5)
    if letter_ratio < 0.5:
        score -= 0.3
    if len(words) < 20:
        score -= 0.3
    return max(0.0, score)


def _extract_page_text_column_aware(page):
    try:
        blocks = page.get_text("blocks")
    except Exception as e:
        logger.warning(f"[PDF] Falha em get_text(blocks): {e}")
        return ""

    blocks = [b for b in blocks if len(b) >= 5 and isinstance(b[4], str) and b[4].strip()]
    if not blocks:
        return ""

    page_w = page.rect.width
    block_widths = [max(1.0, b[2] - b[0]) for b in blocks]
    median_w = sorted(block_widths)[len(block_widths) // 2]
    is_multicol = median_w < page_w * 0.55

    def sort_key(b):
        return (round(b[1], 1), round(b[0], 1))

    if is_multicol:
        mid = page_w / 2
        left = sorted([b for b in blocks if b[0] < mid], key=sort_key)
        right = sorted([b for b in blocks if b[0] >= mid], key=sort_key)
        ordered = left + right
    else:
        ordered = sorted(blocks, key=sort_key)

    parts = []
    for b in ordered:
        txt = b[4].strip()
        if not txt:
            continue
        parts.append(txt)
    return "\n".join(parts)


def _ocr_single_page_image(image_bytes, lang='por+eng'):
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'L':
            img = img.convert('L')
        if img.width > 1600:
            ratio = 1600 / img.width
            img = img.resize((1600, int(img.height * ratio)), Image.Resampling.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=1)
        best = ""
        best_score = -1.0
        for psm in (6, 4, 3):
            try:
                text = pytesseract.image_to_string(
                    img, lang=lang, config=f'--oem 3 --psm {psm}'
                ).strip()
                if text:
                    sc = _native_text_quality_score(text)
                    if sc > best_score:
                        best_score = sc
                        best = text
            except Exception:
                continue
        return best
    except Exception as e:
        logger.warning(f"[PDF] OCR de página falhou: {e}")
        return ""


def _extract_native_text(doc):
    pages = []
    qualities = []
    for i in range(len(doc)):
        try:
            page = doc[i]
            txt = _extract_page_text_column_aware(page)
            if not txt:
                txt = page.get_text("text", sort=True) or ""
            txt = txt.strip()
            pages.append(txt)
            qualities.append(_native_text_quality_score(txt))
        except Exception as e:
            logger.warning(f"[PDF] Falha na extração nativa da página {i+1}: {e}")
            pages.append("")
            qualities.append(0.0)
    return pages, qualities


def _clean_native_text(text):
    if not text:
        return ""
    lines = text.split("\n")
    clean_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(clean_lines)


def preprocess_image_for_ocr(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'L':
        img = img.convert('L')
    img = ImageEnhance.Contrast(img).enhance(2.0)
    max_width = 2000
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.Resampling.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageOps.autocontrast(img, cutoff=2)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    return img


def postprocess_text(text):
    if not text:
        return ""
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            clean_lines.append("")
            continue
        if line.endswith('-'):
            line = line[:-1]
        if len(line) > 1:
            clean_lines.append(line)
    return '\n'.join(clean_lines)


def ocr_image_bytes(image_bytes, lang='por'):
    try:
        img = preprocess_image_for_ocr(image_bytes)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, lang=lang, config=custom_config)
        return postprocess_text(text)
    except Exception as e:
        logger.error(f"Tesseract OCR falhou: {e}")
        return ""


def ocr_with_ocrspace(image_bytes):
    global _ocrspace_consecutive_failures, _ocrspace_disabled, _ocrspace_pages_used

    if _ocrspace_disabled:
        return ""
    if not OCR_SPACE_API_KEY:
        return ""
    if _ocrspace_pages_used >= OCR_SPACE_MAX_PAGES:
        return ""
    if len(image_bytes) > 1.5 * 1024 * 1024:
        return ""

    files = {'file': ('image.png', image_bytes, 'image/png')}
    data = {
        'apikey': OCR_SPACE_API_KEY,
        'language': 'por',
        'isOverlayRequired': False,
        'filetype': 'PNG'
    }

    try:
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files=files,
            data=data,
            timeout=(OCR_SPACE_CONNECT_TIMEOUT, OCR_SPACE_READ_TIMEOUT)
        )
        if response.status_code == 200:
            result = response.json()
            if result.get('OCRExitCode') == 1:
                _ocrspace_consecutive_failures = 0
                _ocrspace_pages_used += 1
                return result['ParsedResults'][0]['ParsedText']
    except requests.exceptions.Timeout:
        _ocrspace_consecutive_failures += 1
        logger.warning(
            f"OCR.space timeout (falha {_ocrspace_consecutive_failures}/{OCR_SPACE_MAX_FAILURES})."
        )
    except requests.exceptions.ConnectionError:
        _ocrspace_consecutive_failures += 1
        logger.warning(
            f"OCR.space indisponivel (falha {_ocrspace_consecutive_failures}/{OCR_SPACE_MAX_FAILURES})."
        )
    except Exception as e:
        _ocrspace_consecutive_failures += 1
        logger.warning(f"OCR.space falhou: {e}")

    if _ocrspace_consecutive_failures >= OCR_SPACE_MAX_FAILURES:
        _ocrspace_disabled = True
        logger.warning(
            f"OCR.space desabilitado para esta sessao apos {OCR_SPACE_MAX_FAILURES} falhas consecutivas."
        )
    return ""


def _vision_ocr_bytes(img_bytes):
    try:
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        text = extract_text_from_image(img_b64)
        if text and text.strip():
            return text.strip()
    except Exception as e:
        logger.warning(f"Vision OCR falhou: {e}")
    return ""


def _reocr_bad_pages(doc, bad_page_indices, lang='por+eng', dpi=300):
    results = {}
    for i in bad_page_indices:
        try:
            page = doc[i]
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            new_text = _ocr_single_page_image(img_bytes, lang)
            if new_text:
                results[i] = new_text
        except Exception as e:
            logger.warning(f"[PDF] Re-OCR falhou na página {i+1}: {e}")
    return results


def _ocr_pages_worker(pdf_bytes, page_nums, lang, dpi):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    result = {}
    try:
        for pn in page_nums:
            try:
                page = doc[pn]
                pix = page.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes("png")

                text = ocr_image_bytes(img_bytes, lang)
                method = "tesseract"

                if not text.strip():
                    text = ocr_with_ocrspace(img_bytes)
                    method = "ocrspace" if text.strip() else "none"

                if not text.strip():
                    text = _vision_ocr_bytes(img_bytes)
                    method = "vision" if text.strip() else "lost"

                result[pn] = text
                result[f"__method_{pn}"] = method
            except Exception as e:
                logger.warning(f"Falha OCR na página {pn + 1}: {e}")
                result[pn] = ""
                result[f"__method_{pn}"] = "error"
    finally:
        doc.close()
    return result


def extract_text_from_pdf_bytes(pdf_bytes, lang='por', max_workers=None, dpi=None):
    if max_workers is None:
        max_workers = OCR_MAX_WORKERS
    if dpi is None:
        dpi = OCR_DPI

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.error(f"Falha ao abrir PDF: {e}")
        return ""

    num_pages = len(doc)
    native_text = ""

    try:
        logger.info(f"[PDF] Abrindo PDF com {num_pages} páginas.")
        native_pages, qualities = _extract_native_text(doc)

        total_chars = sum(len(p) for p in native_pages)
        avg_chars = total_chars / max(1, num_pages)
        avg_quality = sum(qualities) / max(1, num_pages)
        bad_pages = [i for i, q in enumerate(qualities) if q < 0.5 and native_pages[i]]

        logger.info(
            f"[PDF] Extração nativa: {total_chars} chars em {num_pages} páginas "
            f"({avg_chars:.0f} chars/pág, qualidade média={avg_quality:.2f}). "
            f"Páginas com baixa qualidade: {len(bad_pages)}."
        )

        if avg_chars >= NATIVE_TEXT_MIN_CHARS_PER_PAGE:
            if bad_pages and len(bad_pages) / max(1, num_pages) > 0.2:
                logger.warning(
                    f"[PDF] {len(bad_pages)} páginas com texto nativo suspeito "
                    f"(provável OCR embutido de baixa qualidade). Re-processando com Tesseract..."
                )
                reocr = _reocr_bad_pages(doc, bad_pages, lang=lang, dpi=max(300, dpi or 300))
                for i, new_text in reocr.items():
                    if new_text and _native_text_quality_score(new_text) > qualities[i]:
                        native_pages[i] = new_text
                        qualities[i] = _native_text_quality_score(new_text)

            kept = []
            dropped_toc = 0
            dropped_cover = 0
            dropped_quality = 0
            for idx, p in enumerate(native_pages):
                if not p:
                    continue
                if _looks_like_toc_page(p):
                    dropped_toc += 1
                    continue
                if idx < 3 and _looks_like_cover_page(p):
                    dropped_cover += 1
                    continue
                cleaned_page = _strip_toc_lines(p)
                if len(cleaned_page.strip()) < 100:
                    dropped_quality += 1
                    continue
                kept.append(cleaned_page)
            if dropped_toc or dropped_cover or dropped_quality:
                logger.info(
                    f"[PDF] Páginas descartadas: TOC={dropped_toc} capa={dropped_cover} "
                    f"curtas={dropped_quality}. Páginas úteis: {len(kept)}/{num_pages}."
                )
            if kept:
                logger.info("[PDF] Camada de texto nativa utilizável. OCR ignorado.")
                native_text = "\n\n".join(kept)
    finally:
        doc.close()

    if native_text:
        result = _clean_native_text(native_text)
        logger.info(f"[PDF] Texto final (nativo): {len(result)} chars.")
        return result

    logger.info("[PDF] Texto nativo insuficiente. Executando pipeline de OCR completo.")

    pages = list(range(num_pages))
    chunk_size = max(1, (len(pages) + max_workers - 1) // max_workers)
    chunks = [pages[i:i + chunk_size] for i in range(0, len(pages), chunk_size)]

    page_texts = {}
    page_methods = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_ocr_pages_worker, pdf_bytes, chunk, lang, dpi)
            for chunk in chunks
        ]
        for fut in as_completed(futures):
            try:
                partial = fut.result()
                for k, v in partial.items():
                    if isinstance(k, str) and k.startswith("__method_"):
                        page_methods[int(k.replace("__method_", ""))] = v
                    else:
                        page_texts[k] = v
            except Exception as e:
                logger.warning(f"Falha em worker de OCR: {e}")

    ordered = []
    stats = {"tesseract": 0, "ocrspace": 0, "native": 0, "vision": 0, "lost": 0, "error": 0}
    lost_pages = []

    for i in range(num_pages):
        t = page_texts.get(i, "").strip()
        method = page_methods.get(i, "lost")
        stats[method] = stats.get(method, 0) + 1
        if t:
            ordered.append(t)
        else:
            lost_pages.append(i + 1)

    full_text = "\n\n".join(ordered)

    logger.info(f"OCR concluído: {len(full_text)} caracteres de {num_pages} páginas.")
    logger.info(
        f"Resumo por método -> tesseract={stats.get('tesseract', 0)} | "
        f"ocrspace={stats.get('ocrspace', 0)} | native={stats.get('native', 0)} | "
        f"vision={stats.get('vision', 0)} | "
        f"vazias={stats.get('lost', 0) + stats.get('error', 0)}"
    )
    if lost_pages:
        amostra = lost_pages[:20]
        sufixo = f" ... (+{len(lost_pages) - 20})" if len(lost_pages) > 20 else ""
        logger.warning(f"{len(lost_pages)} páginas ficaram sem texto: {amostra}{sufixo}")

    return postprocess_text(full_text)


def extract_text_from_image_bytes(image_bytes, lang='por'):
    text = ocr_image_bytes(image_bytes, lang)
    if not text.strip():
        text = ocr_with_ocrspace(image_bytes)
    if not text.strip():
        text = _vision_ocr_bytes(image_bytes)
    return postprocess_text(text)


def _extract_text_from_json(file_bytes):

    try:
        text = file_bytes.decode('utf-8')
    except Exception:
        text = file_bytes.decode('latin-1', errors='ignore')
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        im
        return text
    if isinstance(data, (dict, list)):
        s
        return json.dumps(data, ensure_ascii=False, indent=2)
    return str(data)


EXTENSOES_TEXTO_SIMPLES = {
    '.txt', '.md', '.markdown', '.ipynb', '.py', '.js', '.ts', '.jsx',
    '.tsx', '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.go', '.rs',
    '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.m', '.sh',
    '.bash', '.ps1', '.sql', '.html', '.css', '.scss', '.sass', '.less',
    '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.vue',
    '.svelte', '.dart', '.lua', '.pl', '.pm', '.tcl', '.vb', '.fs',
    '.fsx', '.ml', '.mli', '.ex', '.exs', '.erl', '.hrl', '.jl', '.nim',
    '.cr', '.zig', '.tf', '.tfvars', '.bat', '.cmd', '.psm1', '.psd1',
    '.asm', '.s', '.pas', '.dpr', '.dpk', '.lpr', '.pp', '.inc', '.bas',
    '.cls', '.frm', '.ctl', '.vbp', '.vbw', '.dockerfile', '.makefile',
    '.gradle'
}

def _is_text_file(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in EXTENSOES_TEXTO_SIMPLES)


def extract_text_from_uploaded_file(file_storage, lang='por'):
    file_storage.seek(0)
    filename = (file_storage.filename or '').lower()
    file_bytes = file_storage.read()

    if _is_text_file(filename):
        try:
            return file_bytes.decode('utf-8')
        except Exception:
            return file_bytes.decode('latin-1', errors='ignore')

    if filename.endswith('.json'):
        return _extract_text_from_json(file_bytes)

    if filename.endswith('.pdf'):
        return extract_text_from_pdf_bytes(file_bytes, lang)

    if filename.endswith('.docx'):
        return _extract_text_from_docx(file_bytes)

    if filename.endswith('.pptx'):
        return _extract_text_from_pptx(file_bytes)

    return extract_text_from_image_bytes(file_bytes, lang)


def _extract_text_from_docx(file_bytes):
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error(f"Falha ao abrir DOCX: {e}")
        return ""

    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    for section in doc.sections:
        for container in (section.header, section.footer):
            if container is None:
                continue
            for para in container.paragraphs:
                if para.text.strip():
                    parts.append(para.text)

    return postprocess_text("\n".join(parts))


def _extract_text_from_pptx(file_bytes):
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(file_bytes))
        parts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    parts.append(shape.text)
        return postprocess_text("\n".join(parts))
    except Exception as e:
        logger.error(f"Falha ao extrair PPTX: {e}")
        return ""


def save_extracted_text(topic_name, text, base_filename):
    from flask import current_app
    folder = os.path.join(current_app.config['QUESTIONS_UPLOAD_FOLDER'], topic_name)
    os.makedirs(folder, exist_ok=True)
    txt_filename = os.path.splitext(base_filename)[0] + '_texto_extraido.txt'
    txt_path = os.path.join(folder, txt_filename)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return txt_path, txt_filename