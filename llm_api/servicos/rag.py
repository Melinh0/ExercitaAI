import os
import logging
import json
import re
from pathlib import Path
from core.config import TOP_K
from core.vector_store import VectorStore
from servicos.data_loader import load_all_questions
from llm.ollama_client import get_ollama_response, padrao_para_o_usuario
from core.json_utils import extract_json_from_response
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_TEMPLATE_PATH = PROMPTS_DIR / "generate_explanation.md"
if PROMPT_TEMPLATE_PATH.exists():
    PROMPT_TEMPLATE = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
else:
    PROMPT_TEMPLATE = """Voce e um assistente especializado em resolver questoes de vestibular e concursos.
Abaixo estao exemplos de questoes resolvidas anteriormente:

{examples}

Agora, resolva a seguinte questao da mesma forma, fornecendo uma explicacao detalhada e a resposta final.

Questao: {question_text}

Resposta:"""

NEUTRAL_PROMPT_TEMPLATE = """Voce e um assistente especializado em resolver questoes de vestibular e concursos.
Responda diretamente a questao abaixo, sem se basear em exemplos de questoes anteriores.

Questao: {question_text}

Resposta:"""

DEFAULT_FLASHCARDS_TEMPLATE = """Voce e um assistente educacional especialista em criar planos de estudo em formato de flashcards.

Com base no contexto do topico e no assunto especificado, gere EXATAMENTE {max_flashcards} flashcards.

Assunto: {subject}

Regras:
1. Cada flashcard deve conter: title, objective, explanation, example, exercise, answer.
2. Comece pelos conceitos mais basicos e avance em ordem logica.
3. Use LaTeX correto (\\rightarrow, \\times, \\infty, \\leq). Nunca use asteriscos.
4. Gere EXATAMENTE {max_flashcards} flashcards. NUNCA menos que isso.
5. Cada flashcard DEVE ter titulo unico e conteudo distinto dos demais.
6. Instrucoes personalizadas: {custom_instructions}

Formato de saida (APENAS JSON valido):
{{
  "flashcards": [
    {{
      "title": "...",
      "objective": "...",
      "explanation": "...",
      "example": "...",
      "exercise": "...",
      "answer": "..."
    }}
  ]
}}

Contexto do topico:
{context}

Instrucoes adicionais: {custom_instructions}
Modelo: {model}
"""

GENERIC_BATCH_FOCUS = [
    "conceitos fundamentais, definicoes e vocabulario essencial",
    "aplicacoes praticas, exemplos do cotidiano e estudos de caso",
    "historia, origem, evolucao e marcos importantes",
    "ferramentas, tecnicas, metodologias e boas praticas",
    "comparacoes com areas relacionadas e conexoes interdisciplinares",
    "desafios atuais, controversias e perspectivas futuras",
]


def _nonce():
    return os.urandom(4).hex()


def get_default_model():
    padrao_provedor = padrao_para_o_usuario()
    if padrao_provedor:
        return padrao_provedor
    models_str = os.getenv('OLLAMA_AVAILABLE_MODELS', '')
    available = [m.strip() for m in models_str.split(',') if m.strip()]
    if available:
        return available[0]
    return os.getenv('DEFAULT_MODEL', 'gemma3:4b')





def extract_alternatives_from_text(text: str) -> List[str]:
    if not text:
        return []
    text = text.replace('\r\n', '\n')
    lines = text.split('\n')
    alternatives = []
    for line in lines:
        line = line.strip()
        if re.match(r'^[A-Da-d]\s*[).:]\s*', line):
            alternatives.append(line)
    if len(alternatives) >= 2:
        return alternatives[:4]
    pattern = r'([A-Da-d])\s*[).:]\s*([^\n]+)'
    matches = re.findall(pattern, text)
    if matches and len(matches) >= 2:
        return [f"{match[0].upper()}) {match[1].strip()}" for match in matches[:4]]
    pattern_num = r'(\d+)\s*[).:]\s*([^\n]+)'
    matches_num = re.findall(pattern_num, text)
    if matches_num and len(matches_num) >= 4:
        letters = ['A', 'B', 'C', 'D']
        return [f"{letters[i]}) {matches_num[i][1].strip()}" for i in range(4)]
    pattern_alt = r'[\(（]?([A-Da-d])[\)）]?\s*([^\n]+)'
    matches_alt = re.findall(pattern_alt, text)
    if matches_alt and len(matches_alt) >= 2:
        return [f"{match[0].upper()}) {match[1].strip()}" for match in matches_alt[:4]]
    return []


def generate_alternatives_for_question(question_text, subject, model, max_retries=2):
    prompt = f"""
Voce e um gerador de alternativas para questoes objetivas.
Dada a pergunta abaixo, gere 4 alternativas (A, B, C, D) e indique a correta.
As alternativas devem ser especificas e relevantes ao assunto.

Pergunta:
{question_text}

Assunto: {subject}

Responda APENAS com um JSON no formato:
{{
  "alternatives": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "A"
}}
Nao inclua texto adicional.
"""
    for attempt in range(max_retries):
        response = get_ollama_response(model, prompt, json_mode=True, min_chars=80)
        parsed = extract_json_from_response(response)
        if parsed and "alternatives" in parsed and len(parsed["alternatives"]) >= 4:
            alts = parsed["alternatives"]
            if all(alt.strip() and alt[0].upper() in "ABCD" for alt in alts):
                return alts, parsed.get("correct_answer", "A")
        extracted = extract_alternatives_from_text(response)
        if extracted and len(extracted) >= 4:
            return extracted, "A"
    return None, None


def _is_missing_info_response(text: str) -> bool:
    if not text:
        return True
    lower = text.lower()
    missing_patterns = [
        "não encontrei", "nao encontrei", "não há informações",
        "nao ha informacoes", "sem contexto", "informação insuficiente",
        "informacao insuficiente", "não foi possível", "nao foi possivel",
        "não disponível", "nao disponivel", "material disponivel",
        "material disponível"
    ]
    for pattern in missing_patterns:
        if pattern in lower:
            return True
    return False


def generate_explanation(question_text, question_type=None, model=None,
                         temperature=None, no_rag=False, skip_fallback=False,
                         seed=None, user_id=None):
    if not model:
        model = get_default_model()
        logger.info(f"Nenhum modelo fornecido, usando padrao: {model}")
    else:
        logger.info(f"Usando modelo fornecido: {model} | no_rag={no_rag} | skip_fallback={skip_fallback}")

    similar_docs = []

    if not no_rag:
        try:
            vector_store = VectorStore(collection_name="questions")
            results = vector_store.query(question_text, n_results=TOP_K)
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    similar_docs.append({
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i]
                    })
            doc_store = VectorStore(collection_name="documents")
            where_user = (
                {"user_id": {"$eq": str(user_id)}}
                if user_id is not None else None
            )
            doc_results = doc_store.query(
                question_text, n_results=TOP_K, where=where_user
            )
            if doc_results["documents"] and doc_results["documents"][0]:
                for i in range(len(doc_results["documents"][0])):
                    similar_docs.append({
                        "document": doc_results["documents"][0][i],
                        "metadata": doc_results["metadatas"][0][i],
                        "distance": doc_results["distances"][0][i]
                    })
            similar_docs.sort(key=lambda x: x["distance"])
        except Exception as e:
            logger.warning(f"Falha ao recuperar documentos similares: {e}")
    else:
        logger.info("[generate_explanation] no_rag=True: pulando recuperacao de contexto.")

    examples_str = ""
    max_examples = 1
    for i, doc in enumerate(similar_docs[:max_examples]):
        meta = doc["metadata"]
        examples_str += f"Exemplo {i+1}:\n"
        examples_str += f"Questao: {meta.get('question', '')}\n"
        examples_str += f"Tipo: {meta.get('type', '')}\n"
        examples_str += f"Resposta: {meta.get('answer', '')}\n"
        explanation = meta.get('explanation', '')
        if len(explanation) > 1000:
            explanation = explanation[:1000] + "..."
        examples_str += f"Explicacao: {explanation}\n\n"

    if no_rag:
        prompt = NEUTRAL_PROMPT_TEMPLATE.format(question_text=question_text)
    else:
        prompt = PROMPT_TEMPLATE.format(examples=examples_str, question_text=question_text)

    min_chars = 0 if skip_fallback else 200

    if temperature is not None:
        generated_text = get_ollama_response(
            model, prompt, temperature=temperature, min_chars=min_chars,
            seed=seed
        )
    else:
        generated_text = get_ollama_response(
            model, prompt, min_chars=min_chars, seed=seed
        )

    texto = (generated_text or "").strip()
    curto = len(texto) < 100
    resposta_e_json = bool(curto and generated_text) and extract_json_from_response(generated_text) is not None

    if generated_text and len(texto) < 80 and not resposta_e_json:
        logger.warning(
            f"[generate_explanation] Resposta muito curta ({len(texto)} chars) "
            f"para modelo={model}."
        )

    if skip_fallback:
        return {
            "explanation": generated_text,
            "similar_questions": [
                {"id": doc["metadata"].get("question", ""),
                 "topic": doc["metadata"].get("topic", ""),
                 "distance": doc["distance"]}
                for doc in similar_docs[:1]
            ]
        }

    if _is_missing_info_response(generated_text) or (curto and not resposta_e_json):
        logger.warning(
            "Resposta indicou falta de informacao ou muito curta. "
            "Usando fallback com sugestoes."
        )
        fallback_prompt = f"""
A resposta anterior indicou falta de informacao. Mesmo sem contexto completo, faca o maximo para resolver a questao abaixo.
Use seu conhecimento geral e raciocinio logico para chegar a uma resposta.
Se nao for possivel determinar a resposta com certeza, indique isso claramente e sugira pesquisas e materiais que poderiam ser adicionados ao sistema para enriquecer o contexto.

Questao: {question_text}

Sua resposta deve conter:
1. Uma tentativa de resolucao baseada no que voce sabe.
2. Uma indicacao clara de que a resposta pode nao ser completa devido a falta de informacoes.
3. Sugestoes especificas de pesquisas (termos de busca, topics, tipos de documentos) que o usuario poderia adicionar ao RAG do topico para melhorar futuras respostas.

Resposta:
"""
        if temperature is not None:
            generated_text = get_ollama_response(
                model, fallback_prompt, temperature=temperature, min_chars=200,
                seed=seed
            )
        else:
            generated_text = get_ollama_response(
                model, fallback_prompt, min_chars=200, seed=seed
            )

    return {
        "explanation": generated_text,
        "similar_questions": [
            {"id": doc["metadata"].get("question", ""),
             "topic": doc["metadata"].get("topic", ""),
             "distance": doc["distance"]}
            for doc in similar_docs[:1]
        ]
    }


def index_all():
    items = load_all_questions()
    if not items:
        return {"status": "no items found"}
    seen = set()
    unique_items = []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique_items.append(item)
    vector_store = VectorStore()
    vector_store.delete_all()
    ids = [item["id"] for item in unique_items]
    documents = [item["document"] for item in unique_items]
    metadatas = [item["metadata"] for item in unique_items]
    vector_store.add_documents(ids, documents, metadatas)
    return {"status": "indexed", "count": len(unique_items)}


def _generate_fallback_question(question_type, subject, idx, model):
    if question_type == "objetiva":
        alts, correct = generate_alternatives_for_question(
            f"Questao {idx+1} sobre {subject}", subject, model
        )
        if not alts:
            alts = ["A) Opcao A", "B) Opcao B", "C) Opcao C", "D) Opcao D"]
            correct = "A"
        return {
            "type": "objetiva",
            "text": f"Questao {idx+1} sobre {subject}",
            "alternatives": alts,
            "correct_answer": correct,
            "explanation": f"Explicacao detalhada da questao {idx+1} sobre {subject}."
        }
    if question_type == "vf":
        return {
            "type": "vf",
            "text": f"Afirmativa {idx+1} sobre {subject}",
            "correct_answer": "Verdadeiro",
            "explanation": f"Explicacao da afirmativa {idx+1} sobre {subject}."
        }
    return {
        "type": "aberta",
        "text": f"Questao aberta {idx+1} sobre {subject}",
        "expected_answer": f"Resposta esperada para a questao {idx+1} sobre {subject}",
        "explanation": f"Explicacao detalhada da questao {idx+1} sobre {subject}."
    }


def _monta_lista_questoes_existentes(existing_questions):
    itens = [str(q).strip() for q in (existing_questions or []) if str(q).strip()]
    if not itens:
        return "Nenhuma questao existente informada."
    linhas = []
    consumido = 0
    for i, texto in enumerate(itens[:120], start=1):
        corte = texto[:160]
        linhas.append(f"{i}. {corte}")
        consumido += len(corte)
        if consumido > 7000:
            break
    if len(itens) > len(linhas):
        linhas.append(f"... e mais {len(itens) - len(linhas)} questoes existentes.")
    return "\n".join(linhas)


def _fatia_contexto(context, idx, total_questoes):
    ctx_total = len(context or "")
    if ctx_total <= 800 or total_questoes <= 1:
        return context
    fatia = max(500, ctx_total // max(1, total_questoes))
    inicio = min(idx * fatia, max(0, ctx_total - fatia))
    if idx >= total_questoes - 1:
        return context[inicio:ctx_total]
    fim = min(ctx_total, inicio + fatia)
    return context[inicio:fim]


def generate_custom_questions(context, question_types, num_questions,
                               custom_instructions, model, subject,
                               user_id=None, existing_questions=None):
    if not model:
        model = get_default_model()

    MAX_CONTEXT_LENGTH = 12000
    if context and len(context) > MAX_CONTEXT_LENGTH:
        context = context[:MAX_CONTEXT_LENGTH] + "\n... (contexto truncado)"

    questoes_existentes = _monta_lista_questoes_existentes(existing_questions)

    prompt_path = PROMPTS_DIR / "generate_questions.md"
    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8")
    else:
        template = """Voce e um gerador de questoes academicas.
[seed:{nonce}]
Assunto: {subject}
Tipo: {q_type}
Questao {idx} de {num_questions} do lote.

Nao repita as questoes existentes:
{existing_questions}

Instrucoes personalizadas (OBRIGATORIAS):
{custom_instructions}

Trecho do contexto:
---
{ctx_slice}
---

Retorne APENAS um JSON valido, sem texto adicional:
{{
  "type": "{q_type}",
  "text": "Enunciado da questao",
  "alternatives": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "A",
  "expected_answer": "",
  "explanation": "**Resposta:** ...\\n\\n**Raciocinio passo a passo:**\\n1. ...\\n\\n**Auto-verificacao:** ...\\n\\n**Resposta final:** ..."
}}
"""

    is_generic = len(context.strip()) < 100

    if is_generic:
        nonce = _nonce()
        generic_prompt = f"""[seed:{nonce}]
Voce esta gerando questoes sobre o assunto "{subject}", mas o usuario NAO forneceu nenhum material de apoio sobre este assunto.

Sua tarefa e:
1. Gerar EXATAMENTE {num_questions} questoes introdutorias sobre o assunto "{subject}", baseadas no conhecimento geral.
2. Os tipos de questao devem ser: {", ".join(question_types)}.
3. Para questoes do tipo "vf", o campo "text" deve conter o enunciado completo da afirmativa, e "correct_answer" deve ser "Verdadeiro" ou "Falso".
4. Para questoes do tipo "objetiva", forneca exatamente 4 alternativas e a correta, e uma explicacao.
5. Para questoes do tipo "aberta", forneca "expected_answer" e "explanation".
6. Todos os campos sao obrigatorios.
7. Garanta que cada questao aborde um aspecto DIFERENTE do assunto. Evite repeticao.
8. Alem do JSON, inclua "research_recommendation" com a estrutura:
   {{
     "google_search_terms": ["termo1", "termo2", ...],
     "platform_guidance": "texto orientando o usuario",
     "upload_suggestion": "texto sugerindo upload"
   }}
   Forneca pelo menos 3 termos de busca.

As instrucoes personalizadas do usuario sao: {custom_instructions if custom_instructions else "Nenhuma instrucao adicional."}

Questoes que ja existem no topico (nao repita nem parafraseie nenhuma delas):
{questoes_existentes}

Responda APENAS com o JSON, sem texto adicional.
"""
        generated_text = get_ollama_response(model, generic_prompt, json_mode=True, min_chars=200)
        parsed = extract_json_from_response(generated_text)
        metadata = {
            "has_context": False,
            "research_recommendation": parsed.get("research_recommendation") if parsed else None
        }
        if parsed and "questions" in parsed:
            valid_questions = []
            for q in parsed["questions"]:
                question_text = q.get("text") or q.get("enunciado") or ""
                if not question_text or not question_text.strip():
                    logger.warning(f"Questao generica sem enunciado, ignorando. Parsed: {q}")
                    continue
                if q.get("type") == "objetiva":
                    if (not q.get("alternatives")
                            or len(q["alternatives"]) < 2
                            or all(alt.strip() == "" for alt in q["alternatives"])):
                        alts, correct = generate_alternatives_for_question(
                            question_text, subject, model
                        )
                        if alts:
                            q["alternatives"] = alts
                            if correct:
                                q["correct_answer"] = correct
                        else:
                            extracted = extract_alternatives_from_text(question_text)
                            q["alternatives"] = extracted if extracted else []
                    if not q.get("correct_answer") and q.get("alternatives"):
                        q["correct_answer"] = "A"
                valid_questions.append(q)
            parsed["questions"] = valid_questions
            while len(parsed["questions"]) < num_questions:
                idx = len(parsed["questions"])
                q_type = question_types[idx % len(question_types)]
                parsed["questions"].append(
                    _generate_fallback_question(q_type, subject, idx, model)
                )
            parsed["questions"] = parsed["questions"][:num_questions]
            return {**parsed, "metadata": metadata}
        fallback = []
        for i in range(num_questions):
            q_type = question_types[i % len(question_types)]
            fallback.append(_generate_fallback_question(q_type, subject, i, model))
        return {"questions": fallback, "metadata": metadata}

    def generate_single_question(idx):
        q_type = question_types[idx % len(question_types)]
        nonce = _nonce()
        ctx_slice = _fatia_contexto(context, idx, num_questions)
        sub_prompt = template.format(
            nonce=nonce,
            subject=subject,
            q_type=q_type,
            idx=idx + 1,
            num_questions=num_questions,
            ctx_slice=ctx_slice,
            custom_instructions=custom_instructions or "Nenhuma instrucao adicional.",
            existing_questions=questoes_existentes,
        )
        response = get_ollama_response(model, sub_prompt, json_mode=True, min_chars=100)
        parsed = extract_json_from_response(response)
        if parsed and "type" in parsed:
            question_text = parsed.get("text") or parsed.get("enunciado") or ""
            if not question_text or not question_text.strip():
                logger.warning(f"Questao gerada sem enunciado (text/enunciado vazio), usando fallback. Parsed: {parsed}")
                return _generate_fallback_question(
                    question_types[idx % len(question_types)], subject, idx, model
                )
            if parsed.get("type") == "objetiva":
                if (not parsed.get("alternatives")
                        or len(parsed["alternatives"]) < 2
                        or all(alt.strip() == "" for alt in parsed["alternatives"])):
                    alts, correct = generate_alternatives_for_question(
                        question_text, subject, model
                    )
                    if alts:
                        parsed["alternatives"] = alts
                        if correct:
                            parsed["correct_answer"] = correct
                    else:
                        extracted = extract_alternatives_from_text(question_text)
                        parsed["alternatives"] = extracted if extracted else []
                if not parsed.get("correct_answer") and parsed.get("alternatives"):
                    parsed["correct_answer"] = "A"
            return parsed
        return _generate_fallback_question(
            question_types[idx % len(question_types)], subject, idx, model
        )

    questions = []
    max_workers = min(5, max(1, num_questions))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(generate_single_question, i) for i in range(num_questions)]
        for future in as_completed(futures):
            try:
                questions.append(future.result())
            except Exception as e:
                logger.error(f"Erro ao gerar questao em paralelo: {e}")
                q_type = question_types[len(questions) % len(question_types)]
                questions.append(
                    _generate_fallback_question(q_type, subject, len(questions), model)
                )
    while len(questions) < num_questions:
        q_type = question_types[len(questions) % len(question_types)]
        questions.append(
            _generate_fallback_question(q_type, subject, len(questions), model)
        )
    questions = questions[:num_questions]
    return {"questions": questions, "metadata": {"has_context": True, "research_recommendation": None}}


def _generate_single_fallback_flashcard(subject, idx, existing_titles):
    prompt = f"""Gere UM flashcard sobre {subject}. O titulo nao pode ser nenhum destes: {existing_titles[:20]}.

Retorne APENAS um JSON valido:
{{
  "title": "Titulo conciso",
  "objective": "O que o aluno deve ser capaz de fazer",
  "explanation": "Explicacao didatica com raciocinio passo a passo",
  "example": "Exemplo curto e direto",
  "exercise": "Exercicio pratico para fixar",
  "answer": "Resposta do exercicio"
}}
"""
    try:
        response = get_ollama_response(
            get_default_model(), prompt, json_mode=True, min_chars=80
        )
        parsed = extract_json_from_response(response)
        if parsed and parsed.get("title"):
            return parsed
    except Exception as e:
        logger.warning(f"[FLASHCARDS] fallback single-card via LLM falhou: {e}")
    return None


def _generate_fallback_flashcard(subject, idx):
    templates = [
        {
            "title": f"Conceito fundamental de {subject}",
            "objective": f"Compreender o conceito básico de {subject}.",
            "explanation": f"{subject} é uma área de estudo que envolve princípios fundamentais.",
            "example": f"Exemplo: ao estudar {subject}, observe como os conceitos aparecem no dia a dia.",
            "exercise": f"Explique o que é {subject} e cite uma aplicação prática.",
            "answer": f"{subject} é uma disciplina com aplicações em diversas áreas."
        },
        {
            "title": f"Aplicações práticas de {subject}",
            "objective": f"Identificar como {subject} é aplicado em situações reais.",
            "explanation": f"{subject} possui aplicações práticas que impactam o cotidiano.",
            "example": f"Exemplo: técnicas de {subject} resolvem problemas complexos.",
            "exercise": f"Dê um exemplo de aplicação de {subject} no mundo real.",
            "answer": f"Aplicações de {subject} incluem soluções industriais e científicas."
        },
        {
            "title": f"História e evolução de {subject}",
            "objective": f"Conhecer a origem e o desenvolvimento de {subject}.",
            "explanation": f"A história de {subject} mostra como o conhecimento evoluiu.",
            "example": f"Exemplo: marcos históricos transformaram {subject}.",
            "exercise": f"Descreva um marco histórico importante para {subject}.",
            "answer": f"Marcos históricos de {subject} incluem descobertas e inovações."
        },
        {
            "title": f"Ferramentas e técnicas em {subject}",
            "objective": f"Reconhecer as principais ferramentas utilizadas em {subject}.",
            "explanation": f"Em {subject}, ferramentas específicas são cruciais para resolver problemas.",
            "example": f"Exemplo: softwares e métodos experimentais são usados em {subject}.",
            "exercise": f"Liste duas ferramentas ou técnicas comuns em {subject}.",
            "answer": f"Ferramentas comuns em {subject} incluem métodos de análise e softwares."
        },
        {
            "title": f"Desafios atuais em {subject}",
            "objective": f"Entender os principais desafios da área de {subject}.",
            "explanation": f"{subject} enfrenta desafios que exigem soluções inovadoras.",
            "example": f"Exemplo: equilibrar eficiência e sustentabilidade em {subject}.",
            "exercise": f"Cite um desafio atual na área de {subject}.",
            "answer": f"Desafios atuais em {subject} incluem questões éticas e técnicas."
        },
        {
            "title": f"Importância de {subject} no contexto atual",
            "objective": f"Analisar a relevância de {subject} hoje.",
            "explanation": f"A importância de {subject} é evidente em educação, indústria e pesquisa.",
            "example": f"Exemplo: {subject} contribui para novas tecnologias.",
            "exercise": f"Justifique a importância de {subject}.",
            "answer": f"{subject} é importante por seu impacto econômico e social."
        },
        {
            "title": f"Metodologias de estudo para {subject}",
            "objective": f"Identificar estratégias eficazes para aprender {subject}.",
            "explanation": f"Para aprender {subject}, combine teoria, prática e revisão.",
            "example": f"Exemplo: resolver exercícios após leitura teórica ajuda em {subject}.",
            "exercise": f"Descreva uma metodologia de estudo para {subject}.",
            "answer": f"Metodologias eficazes incluem repetição espaçada e prática deliberada."
        },
        {
            "title": f"Comparação de abordagens em {subject}",
            "objective": f"Comparar perspectivas dentro de {subject}.",
            "explanation": f"Existem múltiplas abordagens em {subject}, com vantagens e limitações.",
            "example": f"Exemplo: diferentes abordagens levam a resultados distintos em {subject}.",
            "exercise": f"Compare duas abordagens distintas em {subject}.",
            "answer": f"Abordagens em {subject} variam em complexidade e aplicabilidade."
        }
    ]
    return dict(templates[idx % len(templates)])


def _normalize_flashcard(card, subject):
    if not isinstance(card, dict):
        return None
    title = str(card.get("title", "")).strip()
    if not title:
        return None
    objective = str(card.get("objective", "")).strip() or f"Compreender o conceito de {title}."
    explanation = str(card.get("explanation", "")).strip() or f"Explicacao basica sobre {title}."
    example = str(card.get("example", "")).strip()
    if not example or example.lower() in ("sem exemplo", "nenhum exemplo", "sem exemplo disponivel"):
        example = f"Exemplo: situacao cotidiana onde {title} se manifesta."
    exercise = str(card.get("exercise", "")).strip() or f"O que e {title}?"
    answer = str(card.get("answer", "")).strip() or f"Resposta: {title} e um conceito fundamental."
    return {
        "title": title,
        "objective": objective,
        "explanation": explanation,
        "example": example,
        "exercise": exercise,
        "answer": answer,
    }


def _deduplicate_flashcards(cards):
    seen = set()
    unique = []
    for card in cards:
        if not card:
            continue
        key = card["title"].strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(card)
    return unique


def _try_llm_fill(cards, subject, target, existing_titles):
    attempts = 0
    max_attempts = (target - len(cards)) * 2
    while len(cards) < target and attempts < max_attempts:
        attempts += 1
        candidate = _generate_single_fallback_flashcard(
            subject, len(cards), list(existing_titles)
        )
        if candidate:
            normalized = _normalize_flashcard(candidate, subject)
            if normalized and normalized["title"].strip().lower() not in existing_titles:
                existing_titles.add(normalized["title"].strip().lower())
                cards.append(normalized)
    return cards


def _fill_flashcards_to_target(cards, subject, target):
    cards = list(cards)
    existing_titles = {c["title"].strip().lower() for c in cards}
    cards = _try_llm_fill(cards, subject, target, existing_titles)
    idx = 0
    while len(cards) < target:
        fallback = _generate_fallback_flashcard(subject, idx)
        unique_title = f"{fallback['title']} ({len(cards) + 1})"
        if unique_title.strip().lower() in existing_titles:
            idx += 1
            continue
        fallback["title"] = unique_title
        existing_titles.add(unique_title.strip().lower())
        cards.append(fallback)
        idx += 1
    return cards[:target]


def _compute_batch_ranges(total, max_batches, model=""):
    target_per_batch = 3
    n = max(1, min(max_batches, (total + target_per_batch - 1) // target_per_batch))
    size = (total + n - 1) // n
    ranges = []
    for i in range(n):
        s = i * size
        e = min(s + size, total)
        if s < e:
            ranges.append((s, e))
    return ranges


def _build_batch_context(context, batch_no, n_batches, subject, is_generic):
    if not context or not context.strip():
        focus = GENERIC_BATCH_FOCUS[batch_no % len(GENERIC_BATCH_FOCUS)]
        return (
            f"O usuario nao forneceu material de apoio sobre {subject}. "
            f"Gere conteudo introdutorio focando em: {focus}."
        )
    ctx_total = len(context)
    if ctx_total <= 500:
        return context
    chunk = max(500, ctx_total // max(1, n_batches))
    start = (batch_no * chunk) % max(1, ctx_total)
    end = min(ctx_total, start + chunk * 2)
    slice_text = context[start:end]
    if len(slice_text) < 200 and ctx_total > 200:
        slice_text = context[: chunk * 2]
    return slice_text


def _request_flashcard_batch(template, subject, n_request, custom_instructions,
                             context_slice, model, focus_hint):
    prompt = template.format(
        subject=subject,
        max_flashcards=n_request,
        custom_instructions=custom_instructions or "Nenhuma instrucao adicional.",
        context=f"[lote | ref {_nonce()}]{focus_hint}\n{context_slice}",
        model=model,
    )
    text = get_ollama_response(model, prompt, json_mode=True, min_chars=200)
    parsed = extract_json_from_response(text)
    if parsed and isinstance(parsed.get("flashcards"), list):
        return parsed["flashcards"]
    return []


def generate_flashcards(subject, context, max_flashcards, custom_instructions, model):
    if not model:
        model = get_default_model()

    if not subject or len(str(subject).strip()) < 3:
        subject = "conteudo geral"

    MAX_CONTEXT_LENGTH = 12000
    if context and len(context) > MAX_CONTEXT_LENGTH:
        context = context[:MAX_CONTEXT_LENGTH] + "\n... (contexto truncado)"

    is_generic = len(context.strip()) < 100
    metadata = {
        "has_context": not is_generic,
        "research_recommendation": None,
        "warning": None,
        "requested": max_flashcards,
        "generated_raw": 0,
        "padded": 0,
    }

    prompt_path = PROMPTS_DIR / "generate_flashcards.md"
    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8")
    else:
        template = DEFAULT_FLASHCARDS_TEMPLATE

    batch_ranges = _compute_batch_ranges(max_flashcards, 8, model=model)
    n_batches = len(batch_ranges)

    focus_tail = ""
    if n_batches > 1:
        focus_tail = (
            "\n\nEste e um lote dentro de uma geracao paralela. "
            "Gere flashcards sobre um aspecto DIFERENTE dos demais lotes. "
            "Evite repetir titulos e conceitos que provavelmente ja foram cobertos.\n"
        )

    def generate_batch(start_idx, end_idx, batch_no):
        n_needed = end_idx - start_idx
        n_request = n_needed + 8
        context_slice = _build_batch_context(
            context, batch_no, n_batches, subject, is_generic
        )
        accumulated = []
        for attempt in range(3):
            cards = _request_flashcard_batch(
                template,
                subject,
                n_request,
                custom_instructions,
                context_slice,
                model,
                focus_tail,
            )
            accumulated.extend(cards)
            if len(accumulated) >= n_needed:
                break
        return accumulated

    all_cards = []
    max_workers = max(1, min(3, n_batches))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(generate_batch, s, e, i)
            for i, (s, e) in enumerate(batch_ranges)
        ]
        for future in as_completed(futures):
            try:
                all_cards.extend(future.result())
            except Exception as e:
                logger.error(f"Erro ao gerar lote de flashcards: {e}")

    metadata["generated_raw"] = len(all_cards)

    normalized = [_normalize_flashcard(c, subject) for c in all_cards]
    unique = _deduplicate_flashcards(normalized)

    if is_generic:
        for c in normalized:
            if c and c.get("_research_recommendation"):
                metadata["research_recommendation"] = c["_research_recommendation"]
                break

    final_count = len(unique)
    if final_count < max_flashcards:
        logger.warning(
            f"[FLASHCARDS] {subject}: gerados={final_count} solicitados={max_flashcards} "
            f"raw={metadata['generated_raw']}. Tentando preencher via LLM."
        )
        unique = _fill_flashcards_to_target(unique, subject, max_flashcards)
        padded = max_flashcards - final_count
        metadata["padded"] = padded
        if padded > 0:
            metadata["warning"] = (
                f"A IA gerou {final_count} flashcards unicos; "
                f"os {padded} restantes foram preenchidos via LLM/generico. "
                f"Considere revisar o modelo ou aumentar a quantidade solicitada."
            )
    else:
        unique = unique[:max_flashcards]

    return {"flashcards": unique, "metadata": metadata, "subject": subject}