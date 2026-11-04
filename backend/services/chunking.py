import re


def chunk_text(text, target_size=1500, overlap=200, min_size=300):
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        para_len = len(para)
        current_len = len(current)

        if current_len == 0:
            if para_len <= target_size:
                current = para
            else:
                chunks.extend(_split_long_text(para, target_size, overlap))
                current = ""
            continue

        if current_len + para_len + 2 <= target_size:
            current = current + "\n\n" + para
        else:
            if current:
                chunks.append(current)
                tail = current[-overlap:] if overlap > 0 else ""
            else:
                tail = ""
            if para_len <= target_size:
                current = (tail + "\n\n" + para).strip() if tail else para
            else:
                if tail:
                    chunks.extend(_split_long_text(tail + "\n\n" + para, target_size, overlap))
                else:
                    chunks.extend(_split_long_text(para, target_size, overlap))
                current = ""

    if current:
        chunks.append(current)

    merged = []
    for c in chunks:
        if merged and len(c) < min_size:
            merged[-1] = merged[-1] + "\n\n" + c
        else:
            merged.append(c)

    return [c for c in merged if c.strip()]


def _split_long_text(text, target_size, overlap, _depth=0):
    if not text or not text.strip():
        return []

    if len(text) <= target_size:
        return [text]

    if _depth >= 10:
        step = max(1, target_size - overlap)
        pieces = []
        for i in range(0, len(text), step):
            piece = text[i:i + target_size]
            if piece.strip():
                pieces.append(piece)
        return pieces

    sentences = re.split(r'(?<=[.!?])\s+', text)

    if len(sentences) <= 1:
        step = max(1, target_size - overlap)
        pieces = []
        for i in range(0, len(text), step):
            piece = text[i:i + target_size]
            if piece.strip():
                pieces.append(piece)
        return pieces

    chunks = []
    buffer = ""
    for sent in sentences:
        if len(buffer) + len(sent) + 1 <= target_size:
            buffer = (buffer + " " + sent).strip() if buffer else sent
        else:
            if buffer:
                chunks.append(buffer)
                tail = buffer[-overlap:] if overlap > 0 else ""
            else:
                tail = ""
            if len(sent) > target_size:
                chunks.extend(_split_long_text(sent, target_size, overlap, _depth + 1))
                buffer = ""
            else:
                buffer = (tail + " " + sent).strip() if tail else sent
    if buffer:
        chunks.append(buffer)
    return chunks