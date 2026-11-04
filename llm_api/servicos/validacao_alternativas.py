import re

ROMANOS_VALIDOS = {
    "I", "II", "III", "IV", "V", "VI",
    "VII", "VIII", "IX", "X", "XI", "XII",
}
MARCADORES_VF = {"V", "F", "T"}


def letras_alternativas(ocr_text):
    rotulos = re.findall(
        r"(?m)^\s*([a-h])\)+", ocr_text or "", flags=re.IGNORECASE
    )
    return {r.lower() for r in rotulos}


def letra_final_da_resposta(resposta):
    padrao = r"^\s*\*{0,2}([a-h])(?:\)|\.|:|\s|$)"
    m = re.match(padrao, (resposta or "").strip(), flags=re.IGNORECASE)
    return m.group(1).lower() if m else None


def alternativas_romanas_corrompidas(ocr_text):
    linhas = re.findall(
        r"(?m)^\s*[a-h]\)+[ \t]*(.+)$", ocr_text or "", flags=re.IGNORECASE
    )
    corrompidas = []
    for texto in linhas:
        t = texto.strip()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9\-\.\s]{0,28}", t):
            continue
        tokens = [p for p in re.split(r"[\s\-.]+", t) if p]
        if len(tokens) < 2:
            continue
        if not all(re.fullmatch(r"[A-Z]{1,4}", p) for p in tokens):
            continue
        if all(p in MARCADORES_VF for p in tokens):
            continue
        if any(p not in ROMANOS_VALIDOS for p in tokens):
            corrompidas.append(t)
    return corrompidas


def dica_de_correcao(questions, ocr_text):
    respostas = [
        (q or {}).get("resposta")
        for q in (questions or [])
    ]
    com_letra = [r for r in respostas if letra_final_da_resposta(r)]
    if not com_letra:
        return None

    corrompidas = alternativas_romanas_corrompidas(ocr_text)
    if corrompidas:
        return (
            "CORRECAO OBRIGATORIA: os rotulos das alternativas vieram corrompidos "
            f"no texto extraido da imagem ({'; '.join(corrompidas[:4])}). Nao "
            "arrisque atribuir uma letra: entregue apenas o conteudo da resposta "
            "(ex.: 'Resposta final: I-II-III-IV'), sem letra de alternativa, "
            "mantendo a analise completa."
        )

    letras = letras_alternativas(ocr_text)
    if len(letras) < 2:
        return None

    for resposta in com_letra:
        letra = letra_final_da_resposta(resposta)
        if letra not in letras:
            return (
                "CORRECAO OBRIGATORIA: as alternativas existentes na imagem sao "
                f"{', '.join(sorted(letras))}. Sua resposta final usou a letra "
                f"'{letra}', que nao existe no enunciado. Refaca a analise "
                "escolhendo uma das alternativas existentes (confira a letra "
                "impressa ao lado do conteudo que voce marcou como certo); se a "
                "letra nao der para ler com seguranca, responda apenas pelo "
                "conteudo, sem letra."
            )
    return None


def subitens_do_enunciado(ocr_text):
    rotulos = re.findall(r"(?m)^\s*\(?([a-h])[\).]", ocr_text or "")
    vistos = []
    for rotulo in rotulos:
        rotulo = rotulo.lower()
        if rotulo not in vistos:
            vistos.append(rotulo)
    return vistos if len(vistos) >= 2 else []


def _resposta_e_letra_unica(resposta):
    return bool(
        re.fullmatch(r"[\s*]{0,4}\(?[a-hA-H]\)?[\).:]?", (resposta or "").strip())
    )


def itens_faltando(questions, ocr_text):
    esperados = subitens_do_enunciado(ocr_text)
    if not esperados:
        return []
    perguntas = [q for q in (questions or []) if isinstance(q, dict)]
    if not perguntas:
        return []
    tipos = {(q.get("tipo") or "").strip().lower() for q in perguntas}
    if "objetiva" in tipos:
        return []
    respostas = [q.get("resposta") or "" for q in perguntas]
    if all(_resposta_e_letra_unica(r) for r in respostas):
        return []
    texto = "\n".join(
        f"{q.get('resposta') or ''}\n{q.get('explicacao') or ''}"
        for q in perguntas
    )
    faltando = []
    for rotulo in esperados:
        if not re.search(
            rf"(?<![\w])(?:\(|\s)?{re.escape(rotulo)}[\).]",
            texto,
            flags=re.IGNORECASE,
        ):
            faltando.append(rotulo)
    return faltando


def dica_de_cobertura(faltando):
    rotulos = ", ".join(f"({letra})" for letra in faltando)
    return (
        "CORRECAO OBRIGATORIA: sua resposta final nao cobriu todos os subitens "
        f"do enunciado - faltam {rotulos}. Reescreva respondendo a TODOS os "
        "subitens na ordem do enunciado, cada um no seu proprio bloco com rotulo "
        "entre parenteses, ex.: (a) ... (b) ... (c) ..., com desenvolvimento "
        "completo em cada um. Nao responda somente a primeira parte."
    )
