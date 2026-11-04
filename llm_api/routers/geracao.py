import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.json_utils import extract_json_from_response
from servicos.link_utils import get_link_summary
from llm.ollama_client import get_ollama_response
from core.prompt_loader import load_prompt
from servicos.rag import generate_explanation
from servicos.modelos import get_available_models, get_default_model, validate_model
from servicos.sugestoes_cache import obter_sugestoes_em_cache, guardar_sugestoes_em_cache

logger = logging.getLogger(__name__)

router = APIRouter()


class GenerateRequest(BaseModel):
    question_text: str
    question_type: str | None = None
    model: str | None = None
    temperature: float | None = None
    no_rag: bool = False
    skip_fallback: bool = False
    seed: int | None = None
    user_id: int | None = None


class GenerateResponse(BaseModel):
    explanation: str
    similar_questions: list


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    try:
        valid_model = validate_model(req.model)
        return generate_explanation(
            req.question_text,
            req.question_type,
            valid_model,
            temperature=req.temperature,
            no_rag=req.no_rag,
            skip_fallback=req.skip_fallback,
            seed=req.seed,
            user_id=req.user_id
        )
    except Exception as e:
        logger.exception(f"Erro em /generate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class GenerateCustomQuestionsRequest(BaseModel):
    context: str
    question_types: list[str]
    num_questions: int = 10
    custom_instructions: str = ""
    model: str
    subject: str = ""
    user_id: int | None = None
    existing_questions: list[str] = []


@router.post("/generate_custom_questions")
def generate_custom_questions(req: GenerateCustomQuestionsRequest):
    try:
        valid_model = validate_model(req.model)
        from servicos.rag import generate_custom_questions as gen_custom
        subject = req.subject or "conteudo geral"
        return gen_custom(
            req.context,
            req.question_types,
            req.num_questions,
            req.custom_instructions,
            valid_model,
            subject,
            user_id=req.user_id,
            existing_questions=req.existing_questions
        )
    except Exception as e:
        logger.exception(f"Erro em /generate_custom_questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class GenerateFlashcardsRequest(BaseModel):
    subject: str
    context: str
    max_flashcards: int = 12
    custom_instructions: str = ""
    model: str


@router.post("/generate_flashcards")
def generate_flashcards(req: GenerateFlashcardsRequest):
    try:
        valid_model = validate_model(req.model)
        from servicos.rag import generate_flashcards as gen_flashcards
        return gen_flashcards(
            req.subject,
            req.context,
            req.max_flashcards,
            req.custom_instructions,
            valid_model
        )
    except Exception as e:
        logger.exception(f"Erro em /generate_flashcards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _resposta_json_completa(texto):
    base = (texto or "").strip()
    base = re.sub(r'^```[a-zA-Z]*\s*', '', base)
    base = re.sub(r'\s*```$', '', base)
    base = base.strip()
    return base.endswith("}") or base.endswith("]")


class StudyStrategyRequest(BaseModel):
    context: str
    dedication: dict
    topic_name: str = ""
    model: str | None = None


@router.post("/recommend_study_strategy")
def recommend_study_strategy(req: StudyStrategyRequest):
    try:
        dedication = req.dedication
        hours_per_day = dedication.get('hours_per_day', 2)
        days_per_week = dedication.get('days_per_week', 5)
        target_date = dedication.get('target_date', 'nao informada')
        custom_instructions = dedication.get('custom_instructions', '')
        topic_name = req.topic_name or "o topico"

        prompt_template = load_prompt("recommend_strategy")
        if not prompt_template:
            raise HTTPException(status_code=500, detail="Prompt de estrategia nao encontrado.")

        is_generic = len(req.context.strip()) < 100
        generic_instruction = ""
        if is_generic:
            generic_instruction = (
                f"O usuario nao forneceu material especifico sobre '{topic_name}'. "
                "Alem da estrategia, inclua uma recomendacao de pesquisa personalizada no campo "
                "'research_recommendation' do JSON, com sugestoes de busca no Google "
                f"(incluindo o termo '{topic_name}') e orientacao para usar a funcionalidade "
                "'Pesquisar Artigos'."
            )

        prompt = prompt_template.format(
            context=req.context,
            topic_name=topic_name,
            hours_per_day=hours_per_day,
            days_per_week=days_per_week,
            target_date=target_date,
            custom_instructions=custom_instructions + "\n" + generic_instruction
        )

        valid_model = validate_model(req.model)
        response = get_ollama_response(
            model=valid_model,
            prompt=prompt,
            temperature=0.0,
            json_mode=True,
            min_chars=200,
        )
        parsed = extract_json_from_response(response)

        if (not parsed or "technique" not in parsed) or not _resposta_json_completa(response):
            logger.warning(
                "Estrategia truncada ou invalida - repetindo a geracao com instrucao de concisao."
            )
            response_retry = get_ollama_response(
                model=valid_model,
                prompt=prompt
                + "\n\nIMPORTANTE: retorne um JSON curto e completo, sem bloco de codigo e sem "
                "linhas em branco entre os campos. Mantenha 'plan' com no maximo 1200 caracteres "
                "e 'rationale' com no maximo 400 caracteres.",
                temperature=0.0,
                json_mode=True,
                min_chars=200,
            )
            parsed_retry = extract_json_from_response(response_retry)
            response = response_retry
            if parsed_retry and "technique" in parsed_retry:
                parsed = parsed_retry

        if not parsed or "technique" not in parsed:
            logger.error(f"Falha no parse da estrategia. Resposta: {(response or '')[:500]}")
            parsed = {
                "technique": "Revisao Ativa com Repeticao Espacada",
                "plan": (
                    f"1. Defina claramente o objetivo de estudo para '{topic_name}'.\n"
                    "2. Crie flashcards com perguntas e respostas.\n"
                    "3. Revise os flashcards em intervalos crescentes (1 dia, 3 dias, 7 dias, 15 dias).\n"
                    "4. Teste seus conhecimentos com exercicios praticos.\n"
                    "5. Explique os conceitos em voz alta para consolidar o aprendizado."
                ),
                "rationale": (
                    "Esta tecnica e eficaz para reter informacoes a longo prazo, combinando "
                    "recuperacao ativa e distribuicao das revisoes, o que combate a curva do esquecimento."
                ),
                "schedule": (
                    f"Estude {hours_per_day} horas por dia, {days_per_week} dias por semana. "
                    "Dedique 30 minutos para leitura, 30 minutos para criacao de flashcards, "
                    "30 minutos para revisao e 30 minutos para exercicios."
                ),
                "research_recommendation": (
                    f"Recomendacao: pesquise no Google por 'introducao a {topic_name}' e utilize "
                    "a funcionalidade 'Pesquisar Artigos' para encontrar referencias academicas. "
                    "Faca upload de PDFs e imagens para enriquecer o contexto."
                ),
                "references": [
                    {
                        "title": (
                            "Test-enhanced learning: Taking memory tests improves "
                            "long-term retention"
                        ),
                        "authors": "Roediger, H. L., & Karpicke, J. D.",
                        "source": "Psychological Science, 17(3), 249-255",
                        "doi_or_link": "10.1111/j.1467-9280.2006.01693.x"
                    },
                    {
                        "title": (
                            "Distributed practice in verbal recall tasks: "
                            "A review and quantitative synthesis"
                        ),
                        "authors": (
                            "Cepeda, N. J., Pashler, H., Vul, E., "
                            "Wixted, J. T., & Rohrer, D."
                        ),
                        "source": "Psychological Bulletin, 132(3), 354-380",
                        "doi_or_link": "10.1037/0033-2909.132.3.354"
                    }
                ]
            }

        references = parsed.get("references", [])
        enriched_refs = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_ref = {}
            for ref in references:
                link = ref.get("doi_or_link", "")
                if link:
                    future = executor.submit(get_link_summary, link)
                    future_to_ref[future] = ref
            for future in as_completed(future_to_ref):
                ref = future_to_ref[future]
                try:
                    summary = future.result()
                    ref["enriched"] = summary if summary else None
                except Exception:
                    ref["enriched"] = None
                enriched_refs.append(ref)

        parsed["references"] = enriched_refs
        if is_generic and "research_recommendation" not in parsed:
            parsed["research_recommendation"] = (
                f"Recomendacao: pesquise no Google por 'introducao a {topic_name}' e utilize "
                "a funcionalidade 'Pesquisar Artigos' para encontrar referencias academicas. "
                "Faca upload de PDFs e imagens para enriquecer o contexto."
            )

        return parsed

    except Exception as e:
        logger.exception(f"Erro em /recommend_study_strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SuggestTopicNameRequest(BaseModel):
    nome: str
    descricao: str = ""


@router.post("/suggest_topic_name")
def suggest_topic_name(req: SuggestTopicNameRequest):
    nome = (req.nome or "").strip()
    descricao = (req.descricao or "").strip()
    if not nome and not descricao:
        raise HTTPException(status_code=400, detail="Informe o nome ou a descricao do estudo.")
    try:
        prompt_template = load_prompt("suggest_topic_name")
        if not prompt_template:
            raise HTTPException(status_code=500, detail="Prompt de sugestao de nome nao encontrado.")
        prompt = prompt_template.replace("{nome}", nome[:200] if nome else "(nao informado)").replace(
            "{descricao}", descricao[:600] if descricao else "(nao informada)"
        )
        valid_model = validate_model(None)
        response = get_ollama_response(
            model=valid_model,
            prompt=prompt,
            temperature=0.3,
            json_mode=True,
            min_chars=10,
        )
        parsed = extract_json_from_response(response)
        if not parsed or "sugestao" not in parsed:
            logger.warning(f"Falha no parse da sugestao de nome. Resposta: {(response or '')[:300]}")
            raise HTTPException(status_code=502, detail="Nao foi possivel gerar a sugestao.")
        return {
            "sugestao": str(parsed.get("sugestao") or "").strip()[:120],
            "justificativa": str(parsed.get("justificativa") or "").strip()[:300],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Erro em /suggest_topic_name: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RefineQueryRequest(BaseModel):
    query: str


@router.post("/refine_search_query")
def refine_search_query(req: RefineQueryRequest):
    try:
        prompt = (
            "You are an academic search expert. Convert the following topic into an "
            "optimized English search query for CrossRef, PubMed, arXiv, and Google Scholar.\n"
            "Rules:\n"
            "- Use 3 to 6 specific technical keywords in English.\n"
            "- Do NOT include generic words like 'study', 'research', 'approach'.\n"
            "- Do NOT use boolean operators unless essential.\n"
            "- Return ONLY the query string, nothing else.\n\n"
            f"Topic: {req.query}\n\n"
            "Optimized query:"
        )
        candidates = []
        for m in get_available_models():
            lower = m.lower()
            if "gpt-oss" in lower:
                continue
            candidates.append(m)
        model = candidates[0] if candidates else get_default_model()
        logger.info(f"[refine_search_query] input='{req.query}' model={model}")
        refined = get_ollama_response(
            model, prompt, temperature=0.0, min_chars=15
        )
        refined = (refined or "").strip().strip('"').strip("'")
        if not refined or len(refined) > 200 or "\n" in refined:
            refined = req.query
        logger.info(f"[refine_search_query] output='{refined}'")
        return {"refined_query": refined}
    except Exception as e:
        logger.exception(f"Erro em refine_search_query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SuggestPromptsRequest(BaseModel):
    mode: str = "enhance_question"
    context: str = ""
    question: str = ""
    answer: str = ""
    explanation: str = ""
    model: str = ""


@router.post("/suggest_prompts")
def suggest_prompts(req: SuggestPromptsRequest):
    try:
        valid_model = validate_model(req.model)

        cache_modes = ("generate_questions", "generate_flashcards", "study_strategy", "search_articles", "flashcard_subjects")

        if req.mode in cache_modes:
            cached = obter_sugestoes_em_cache(req.mode, req.context or "", valid_model)
            if cached:
                logger.info(f"[suggest_prompts] Cache hit para mode={req.mode}")
                return {"suggestions": cached}

        if req.mode == "analyze_image":
            prompt = (
                "Voce e um especialista em analise de imagens de provas, exames e documentos academicos.\n"
                "O usuario esta prestes a analisar uma imagem ou um documento completo para extrair "
                "questoes e resolve-las. Gere 3 a 5 sugestoes de instrucoes adicionais curtas e "
                "praticas que o usuario pode usar como prioridade para direcionar a analise.\n\n"
                "As sugestoes devem ser frases diretas, sem numeracao, sem explicacoes, relacionadas a:\n"
                "- Corrigir erros comuns de OCR (troca de letras, numeros, simbolos)\n"
                "- Focar em formulas matematicas ou equacoes quimicas\n"
                "- Destacar alternativas de questoes objetivas\n"
                "- Preservar a formatacao original de tabelas e listas\n"
                "- Verificar a ordem e numeracao das questoes\n"
                "- Priorizar as questoes mais visiveis na pagina\n\n"
                "Responda APENAS com uma lista numerada (1., 2., 3., ...) de sugestoes curtas. "
                "Cada sugestao deve ter no maximo 15 palavras."
            )
        elif req.mode == "annotation_insight":
            prompt = (
                "Voce e um especialista em sintese e explicacao de conteudos visuais para estudo.\n"
                "O usuario esta prestes a analisar uma imagem para gerar um insight, resumo ou "
                "anotacao de estudo. Gere 3 a 5 sugestoes de instrucoes adicionais curtas e praticas "
                "para direcionar essa analise.\n\n"
                "As sugestoes devem ser frases diretas, sem numeracao, sem explicacoes, relacionadas a:\n"
                "- Resumir o conteudo em topicos ou pontos-chave\n"
                "- Explicar conceitos complexos com analogias simples\n"
                "- Destacar tendencias visuais em graficos e diagramas\n"
                "- Relacionar o conteudo com exemplos praticos\n"
                "- Sugerir aplicacoes ou desdobramentos do tema\n"
                "- Comparar com conceitos proximos\n\n"
                "Responda APENAS com uma lista numerada (1., 2., 3., ...) de sugestoes curtas. "
                "Cada sugestao deve ter no maximo 15 palavras."
            )
        elif req.mode in cache_modes:
            prompt = load_prompt(f"suggest_{req.mode}").replace(
                "{context}", req.context or "(topico nao informado)"
            )
        else:
            prompt = (
                "Liste 3 a 5 sugestoes de prompts curtos e praticos para melhorar a resolucao "
                "da questao abaixo. As sugestoes devem ser frases diretas, sem explicacoes adicionais.\n\n"
                f"Contexto: {req.context}\n"
                f"Questao: {req.question}\n"
                f"Resposta: {req.answer}\n"
                f"Explicacao atual: {req.explanation}\n\n"
                "Responda APENAS com a lista numerada (1., 2., 3., ...). "
                "Nao inclua texto antes ou depois."
            )

        if req.context and req.mode in ("analyze_image", "annotation_insight"):
            prompt += (
                "\n\nTopico/contexto do usuario (use-o para tornar as sugestoes "
                "especificas deste topico):\n" + req.context[:3000]
            )

        response = get_ollama_response(
            valid_model, prompt, temperature=0.0, min_chars=50, timeout=15
        )
        lines = (response or "").split('\n')
        suggestions = []
        for line in lines:
            line = line.strip()
            if re.match(r'^\d+[\.\)]\s*', line):
                cleaned = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if cleaned:
                    suggestions.append(cleaned)
        if len(suggestions) >= 3:
            if req.mode in cache_modes:
                guardar_sugestoes_em_cache(req.mode, req.context or "", valid_model, suggestions[:5])
            return {"suggestions": suggestions[:5]}
        for line in lines:
            line = line.strip()
            if line and len(line) > 5 and not line.startswith('---'):
                suggestions.append(line)
        if len(suggestions) >= 3:
            if req.mode in cache_modes:
                guardar_sugestoes_em_cache(req.mode, req.context or "", valid_model, suggestions[:5])
            return {"suggestions": suggestions[:5]}

        return {"suggestions": suggestions[:5] if suggestions else []}

    except Exception as e:
        logger.exception(f"Erro em /suggest_prompts: {e}")
        return {"suggestions": []}
