import logging
import re

logger = logging.getLogger(__name__)


def merge_subitems_into_question(questions):
    if not questions:
        return questions
    merged = []
    i = 0
    while i < len(questions):
        q = questions[i]
        num = q.get("numero", "").strip()
        is_subitem = bool(re.match(r'^[IVXLCDM]+$', num.upper())) or bool(
            re.match(r'^[a-z]$', num.lower())
        )
        if i == 0 or not is_subitem:
            current = q.copy()
            current["enunciado"] = current.get("enunciado", "")
            j = i + 1
            while j < len(questions):
                next_num = questions[j].get("numero", "").strip()
                next_is_subitem = bool(re.match(r'^[IVXLCDM]+$', num.upper())) or bool(
                    re.match(r'^[a-z]$', next_num.lower())
                )
                if next_is_subitem:
                    current["enunciado"] += "\n\n" + questions[j].get("enunciado", "")
                    j += 1
                else:
                    break
            merged.append(current)
            i = j
        else:
            merged.append(q)
            i += 1
    return merged


def remove_loops(text: str) -> str:
    if len(text) < 100:
        return text
    for length in range(15, min(50, len(text) // 3)):
        candidate = text[-length:]
        count = text.count(candidate)
        if count > 3 and len(candidate) > 20:
            last = text.rfind(candidate)
            if last > 0:
                return text[:last + len(candidate)]
    return text


def _alinhar_resposta_com_explicacao(q):
    explicacao = (q.get("explicacao") or "").strip()
    resposta = (q.get("resposta") or "").strip()
    if not explicacao or not resposta:
        return

    def _norm(texto):
        return re.sub(r"\s+", " ", texto).strip().rstrip(".").strip().lower()

    if _norm(resposta) in _norm(explicacao):
        return

    encontradas = re.findall(
        r"resposta final\s*[:\-]\s*(.+)", explicacao, flags=re.IGNORECASE
    )
    if not encontradas:
        return
    nova_resposta = encontradas[-1].strip()
    if _norm(nova_resposta) != _norm(resposta):
        logger.info(
            "[resposta] campo 'resposta' divergia do corpo; corrigido: "
            f"'{resposta[:90]}' -> '{nova_resposta[:90]}'"
        )
        q["resposta"] = nova_resposta


def build_final_questions(parsed_questions, generated_text, ocr_text):
    if parsed_questions and len(parsed_questions) > 0:
        for q in parsed_questions:
            if not q.get("resposta"):
                q["resposta"] = "Nao informada automaticamente"
            if not q.get("explicacao"):
                q["explicacao"] = "Resolucao nao disponivel."
            _alinhar_resposta_com_explicacao(q)
        final = merge_subitems_into_question(parsed_questions)

        has_numbered = any(
            q.get("numero", "").strip().isdigit()
            and int(q.get("numero", "0") or "0") > 1
            for q in final
        )
        if len(final) > 1 and not has_numbered:
            full_text = "\n\n".join([q.get("enunciado", "") for q in final])
            placeholders = {"Nao informada automaticamente", "Resolucao nao disponivel."}
            respostas = "\n\n".join(
                v for v in (q.get("resposta", "").strip() for q in final)
                if v and v not in placeholders
            )
            explicacoes = "\n\n".join(
                v for v in (q.get("explicacao", "").strip() for q in final)
                if v and v not in placeholders
            )
            final = [{
                "numero": "1",
                "tipo": "interpretacao",
                "enunciado": full_text,
                "resposta": respostas or "Consulte o enunciado",
                "explicacao": explicacoes or "Resolucao nao disponivel."
            }]

        for q in final:
            if "enunciado" in q:
                q["enunciado"] = remove_loops(q["enunciado"])
                if len(q["enunciado"]) > 8000:
                    q["enunciado"] = q["enunciado"][:8000] + "..."
        return final

    clean_text = re.sub(
        r'[^\x20-\x7F\u00C0-\u00FF\n]+', '', (generated_text or "").strip()
    )
    clean_text = remove_loops(clean_text)[:4000]
    enunciado = clean_text if clean_text else ocr_text[:4000]
    return [{
        "numero": "1",
        "tipo": "interpretacao",
        "enunciado": enunciado,
        "resposta": "Consulte o enunciado",
        "explicacao": (
            "O modelo nao retornou JSON estruturado. "
            "Abaixo esta a saida bruta gerada:\n\n"
            + (generated_text[:3000] if generated_text else "(vazio)")
        )
    }]
