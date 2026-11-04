import re

MIN_USABLE_CHUNK_CHARS = 120
MAX_DIGIT_RATIO = 0.18
MAX_DOTS_RUN = 5
INDEX_LINE_MIN_COUNT = 6
REF_LINE_MIN_COUNT = 3
COVER_PATTERNS = re.compile(
    r"\bISBN\b|Todos os direitos reservados|All rights reserved|"
    r"Copyright\s+©?\s*\d{4}",
    re.IGNORECASE,
)
INDEX_TERM_PAGE = re.compile(r"[A-Za-zÀ-ÿ]{3,}\s*,\s*\d+")
REF_PAGE_PATTERN = re.compile(r"\b(?:p\.|pp\.)\s*\d+")
TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$")


def is_usable_chunk(text):
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < MIN_USABLE_CHUNK_CHARS:
        return False

    digits = sum(c.isdigit() for c in stripped)
    if digits / len(stripped) > MAX_DIGIT_RATIO:
        return False

    if re.search(r"\.{" + str(MAX_DOTS_RUN) + r",}", stripped):
        return False

    if COVER_PATTERNS.search(stripped):
        return False

    lines = [l for l in stripped.split("\n") if l.strip()]
    if not lines:
        return False

    if len(lines) >= 5:
        toc_like = sum(1 for l in lines if TOC_LINE.search(l))
        if toc_like / len(lines) >= 0.35:
            return False

        index_like = sum(1 for l in lines if INDEX_TERM_PAGE.search(l))
        if index_like / len(lines) >= 0.4:
            return False

    if len(INDEX_TERM_PAGE.findall(stripped)) >= INDEX_LINE_MIN_COUNT:
        return False

    if len(REF_PAGE_PATTERN.findall(stripped)) >= REF_LINE_MIN_COUNT:
        return False

    return True
