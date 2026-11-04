import json
import logging
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import pytesseract
from core.config import VISION_MODELS_LIST
from core.corrections_store import corrections_store
from core.json_utils import extract_json_from_response
from llm.ollama_client import get_ollama_response, get_ollama_response_with_image_multi
from core.prompt_loader import ANALYZE_PROMPT_TEMPLATE, REFINEMENT_PROMPT_TEMPLATE, load_prompt
from servicos.contexto import build_context_block
from servicos.modelos import validate_model
from servicos.ocr import (
    extract_text_with_tesseract_robust,
    fallback_vision_transcription,
    is_text_valid,
    ocr_space_extract_text,
)
from servicos.questoes import build_final_questions
from servicos.validacao_alternativas import (
    dica_de_correcao,
    dica_de_cobertura,
    itens_faltando,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ANALYZE_TEMPERATURE_WITH_RAG = float(os.getenv("ANALYZE_TEMPERATURE_WITH_RAG", "0.0"))
ANALYZE_TEMPERATURE_WITHOUT_RAG = float(os.getenv("ANALYZE_TEMPERATURE_WITHOUT_RAG", "0.0"))


class ModelInfoRequest(BaseModel):
    model_name: str


@router.post("/generate_model_info")
def generate_model_info(req: ModelInfoRequest):
    from llm.model_info import gerar_info_modelo
    nome = (req.model_name or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="model_name é obrigatório")
    info = gerar_info_modelo(nome)
    if not info:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao gerar texto informativo para '{nome}'",
        )
    return {"info": info}


class AnalyzeImageRequest(BaseModel):
    image_base64: str
    context_images: list[str] = []
    context_texts: list[str] = []
    model: str
    prompt: str | None = None
    output_format: str = "text"
    extra_prompt: str | None = None
    analysis_type: str = "questions"
    transcription_method: str | None = None
    ocr_model: str | None = None
    temperature: float | None = None
    input_text: str = ""


class AnalyzeImageResponse(BaseModel):
    explanation: str = ""
    questions: list = []
    insight: str = ""


def _modelo_de_visao(ocr_model):
    if ocr_model and isinstance(ocr_model, str) and ocr_model.strip():
        return validate_model(ocr_model.strip())
    return VISION_MODELS_LIST[0] if VISION_MODELS_LIST else None


def _run_ocr_chain(image_base64: str, method: str, extra_prompt: str = "", ocr_model: str | None = None) -> str:
    if method in ("llm", "ollama"):
        modelo_vision = _modelo_de_visao(ocr_model)
        if not modelo_vision:
            raise HTTPException(status_code=500, detail="Nenhum modelo de visao configurado ou selecionado.")
        vision_text = fallback_vision_transcription(image_base64, extra_prompt, modelo=modelo_vision)
        if is_text_valid(vision_text):
            return vision_text
        raise HTTPException(status_code=500, detail=f"Modelo de visao '{modelo_vision}' retornou texto invalido.")

    if method == "ocrspace":
        if not os.getenv('OCR_SPACE_API_KEY'):
            raise HTTPException(status_code=500, detail="Chave da API OCR.space nao configurada.")
        ocr_space_text = ocr_space_extract_text(image_base64, engine=2)
        if is_text_valid(ocr_space_text):
            return ocr_space_text
        raise HTTPException(status_code=500, detail="OCR.space retornou texto invalido.")

    tesseract_text = extract_text_with_tesseract_robust(image_base64, lang='por+eng')
    if is_text_valid(tesseract_text):
        return tesseract_text

    logger.warning(
        f"Tesseract retornou texto invalido ({len(tesseract_text)} chars). Tentando fallbacks..."
    )

    if VISION_MODELS_LIST:
        vision_text = fallback_vision_transcription(image_base64, extra_prompt)
        if is_text_valid(vision_text):
            logger.info("Fallback: Ollama Vision bem-sucedido.")
            return vision_text

    if os.getenv('OCR_SPACE_API_KEY'):
        ocr_space_text = ocr_space_extract_text(image_base64, engine=2)
        if is_text_valid(ocr_space_text):
            logger.info("Fallback: OCR.space bem-sucedido.")
            return ocr_space_text

    if tesseract_text and len(tesseract_text.strip()) >= 15:
        logger.warning("Nenhum fallback valido; usando Tesseract mesmo com qualidade duvidosa.")
        return tesseract_text

    raise HTTPException(
        status_code=500,
        detail=(
            "Nao foi possivel extrair texto valido da imagem. "
            "Verifique se a imagem contem texto legivel. "
            "Considere trocar o metodo de transcricao para 'llm' ou 'ocrspace'."
        )
    )


def _analisar_questao_salva(req, valid_model):
    texto = req.input_text
    prompt = req.prompt if req.prompt else (load_prompt("analyze_text_question") or ANALYZE_PROMPT_TEMPLATE)

    context_block, rag_blocks, rag_chars = build_context_block(req.context_texts)
    if context_block:
        prompt = context_block + "\n\n" + prompt

    if req.extra_prompt:
        priority_block = (
            "\n\n**INSTRUÇÕES PRIORITÁRIAS DO USUÁRIO "
            "(devem ser seguidas antes de qualquer outra regra):**\n"
            f"{req.extra_prompt}\n\n"
        )
        prompt = priority_block + prompt

    prompt = prompt.replace("{ocr_text}", texto)

    if req.temperature is not None:
        temperature = req.temperature
        logger.info(f"[analyze_text_question] temperature override={temperature}")
    else:
        temperature = (
            ANALYZE_TEMPERATURE_WITH_RAG
            if rag_blocks > 0
            else ANALYZE_TEMPERATURE_WITHOUT_RAG
        )
        logger.info(
            f"[analyze_text_question] temperature default={temperature} "
            f"(rag_blocks={rag_blocks})"
        )

    logger.info(
        f"[analyze_text_question] prompt final: {len(prompt)} chars | "
        f"rag_blocks={rag_blocks} | texto_chars={len(texto)}"
    )

    generated_text = ""
    parsed_questions = None
    for attempt in range(3):
        attempt_prompt = prompt
        if attempt > 0:
            attempt_prompt = (
                prompt
                + "\n\n**LEMBRETE FINAL:** a resposta anterior não era JSON válido. "
                "Responda APENAS com o JSON da chave `questions`, sem texto fora dele."
            )
        generated_text = get_ollama_response(
            valid_model,
            attempt_prompt,
            temperature=temperature,
            json_mode=True,
            min_chars=150,
        ) or ""
        parsed = extract_json_from_response(generated_text)
        if parsed and isinstance(parsed.get("questions"), list) and parsed["questions"]:
            parsed_questions = parsed["questions"]
            logger.info(f"[analyze_text_question] parse OK na tentativa {attempt + 1}.")
            break
        logger.warning(
            f"[analyze_text_question] tentativa {attempt + 1} falhou no parse "
            f"({len(generated_text)} chars)."
        )

    if parsed_questions is None:
        raise HTTPException(
            status_code=500,
            detail="O modelo nao retornou a questao em formato valido. Tente novamente.",
        )

    final_questions = build_final_questions(parsed_questions, generated_text, texto)
    logger.info(f"[analyze_text_question] {len(final_questions)} questao(oes).")
    return AnalyzeImageResponse(questions=final_questions)


@router.post("/analyze_image", response_model=AnalyzeImageResponse)
def analyze_image(req: AnalyzeImageRequest):
    try:
        valid_model = validate_model(req.model)
        method = req.transcription_method or "tesseract"

        if req.input_text and req.input_text.strip():
            return _analisar_questao_salva(req, valid_model)

        ocr_text = _run_ocr_chain(req.image_base64, method, req.extra_prompt or "", ocr_model=req.ocr_model)

        prompt = req.prompt if req.prompt else ANALYZE_PROMPT_TEMPLATE

        context_block, rag_blocks, rag_chars = build_context_block(req.context_texts)
        if context_block:
            prompt = context_block + "\n\n" + prompt

        if req.extra_prompt:
            priority_block = (
                "\n\n**INSTRUÇÕES PRIORITÁRIAS DO USUÁRIO "
                "(devem ser seguidas antes de qualquer outra regra):**\n"
                f"{req.extra_prompt}\n\n"
            )
            prompt = priority_block + prompt

        prompt = prompt.replace("{ocr_text}", ocr_text)

        correction_examples = corrections_store.retrieve_similar(prompt, n_results=1)
        if correction_examples:
            correction_text = correction_examples[0]["document"][:1000]
            prompt += "\n\n**Correcao anterior relevante:**\n" + correction_text

        logger.info(
            f"[analyze_image] prompt final: {len(prompt)} chars | "
            f"rag_blocks={rag_blocks} rag_chars={rag_chars} | "
            f"ocr_chars={len(ocr_text)}"
        )

        try:
            with open("/tmp/last_analyze_prompt.txt", "w", encoding="utf-8") as f:
                f.write(prompt)
        except Exception:
            pass

        if req.temperature is not None:
            temperature = req.temperature
            logger.info(f"[analyze_image] temperature override={temperature}")
        else:
            temperature = (
                ANALYZE_TEMPERATURE_WITH_RAG
                if rag_blocks > 0
                else ANALYZE_TEMPERATURE_WITHOUT_RAG
            )
            logger.info(
                f"[analyze_image] temperature default={temperature} (rag_blocks={rag_blocks})"
            )

        generated_text = ""
        parsed_questions = None
        dica_correcao = ""
        reserva_cobertura = None
        faltando_reserva = []

        for attempt in range(3):
            if attempt == 0:
                attempt_prompt = prompt
            elif attempt == 1:
                attempt_prompt = (
                    REFINEMENT_PROMPT_TEMPLATE
                    + f"\n\nTexto original (OCR):\n{ocr_text[:6000]}\n\n"
                    + f"Resposta anterior (invalida):\n{generated_text[:6000]}\n\n"
                    + "Retorne APENAS o JSON valido com a chave 'questions' conforme o schema."
                )
            else:
                attempt_prompt = (
                    "Voce recebera o texto (OCR) de uma imagem de prova. "
                    "Retorne APENAS um JSON valido no formato:\n"
                    '{"questions": [{"numero": "1", "tipo": "interpretacao", '
                    '"enunciado": "...", "resposta": "...", "explicacao": "..."}]}\n\n'
                    "Texto OCR:\n"
                    f"{ocr_text[:5000]}\n\n"
                    "Responda APENAS com o JSON, sem explicacoes."
                )

            if dica_correcao:
                attempt_prompt = f"{attempt_prompt}\n\n{dica_correcao}"

            generated_text = get_ollama_response(
                valid_model,
                attempt_prompt,
                temperature=temperature,
                json_mode=True,
                min_chars=150,
            )
            generated_text = generated_text or ""

            parsed = extract_json_from_response(generated_text)
            if parsed and "questions" in parsed and isinstance(parsed["questions"], list):
                dica = dica_de_correcao(parsed["questions"], ocr_text)
                faltando = (
                    itens_faltando(parsed["questions"], ocr_text)
                    if dica is None else []
                )
                if faltando and attempt < 2:
                    logger.warning(
                        f"[analyze_image] resposta sem os subitens {faltando} do "
                        f"enunciado na tentativa {attempt + 1}; repetindo com "
                        "correcao de cobertura."
                    )
                    reserva_cobertura = parsed["questions"]
                    faltando_reserva = faltando
                    dica_correcao = dica_de_cobertura(faltando)
                    continue
                if dica and attempt < 2:
                    logger.warning(
                        f"[analyze_image] resposta inconsistente com as alternativas "
                        f"do OCR na tentativa {attempt + 1}; repetindo com correcao."
                    )
                    dica_correcao = dica
                    continue
                parsed_questions = parsed["questions"]
                logger.info(f"[analyze_image] parse OK na tentativa {attempt + 1}.")
                break

            logger.warning(
                f"[analyze_image] tentativa {attempt + 1} falhou no parse "
                f"({len(generated_text)} chars)."
            )

        if reserva_cobertura is not None:
            if parsed_questions is None:
                parsed_questions = reserva_cobertura
            elif len(itens_faltando(parsed_questions, ocr_text)) > len(faltando_reserva):
                parsed_questions = reserva_cobertura

        final_questions = build_final_questions(
            parsed_questions, generated_text, ocr_text
        )

        logger.info(f"Finalizadas {len(final_questions)} questoes.")

        if req.output_format == "structured":
            return AnalyzeImageResponse(questions=final_questions)
        return AnalyzeImageResponse(
            explanation=json.dumps(final_questions, ensure_ascii=False)
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Erro em /analyze_image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze_image_insight")
def analyze_image_insight(req: AnalyzeImageRequest):
    try:
        valid_model = validate_model(req.model)
        method = req.transcription_method or "tesseract"

        priority_block = ""
        if req.extra_prompt:
            priority_block = (
                "\n\n**INSTRUÇÕES PRIORITÁRIAS DO USUÁRIO "
                "(devem ser seguidas antes de qualquer outra regra):**\n"
                f"{req.extra_prompt}\n\n"
            )

        if method in ("llm", "ollama") and not (req.input_text and req.input_text.strip()):
            modelo_vision = _modelo_de_visao(req.ocr_model)
            if not modelo_vision:
                raise HTTPException(status_code=500, detail="Nenhum modelo de visao configurado ou selecionado.")
            insight_prompt = (
                "Voce e um assistente educacional especializado em analisar imagens de provas, "
                "exercicios ou conteudos academicos. Analise a imagem fornecida e gere um insight "
                "util, explicacao ou resumo sobre o conteudo apresentado.\n\n"
                f"**Instrucoes do usuario:**\n{priority_block or 'Nenhuma instrucao adicional.'}\n\n"
                "**Resposta:** Forneca um insight claro, objetivo e relevante sobre o conteudo."
            )
            response = get_ollama_response_with_image_multi(
                modelo_vision,
                insight_prompt,
                [req.image_base64],
                min_chars=100,
            )
            if not response or len(response) < 30:
                raise HTTPException(
                    status_code=500,
                    detail="O modelo de visao nao retornou uma resposta valida."
                )
            return {"insight": response.strip()}

        ocr_text = req.input_text if req.input_text and req.input_text.strip() else _run_ocr_chain(req.image_base64, method, req.extra_prompt or "", ocr_model=req.ocr_model)

        insight_prompt = load_prompt("insight_image")
        if not insight_prompt:
            insight_prompt = (
                "Voce e um assistente educacional especializado em fornecer insights sobre imagens "
                "de provas, exercicios ou conteudos academicos.\n\n"
                "Sua tarefa e analisar a imagem fornecida (descrita pelo OCR abaixo) e gerar um "
                "insight util, explicacao ou resumo sobre o conteudo apresentado.\n\n"
                "**Instrucoes do usuario:**\n{extra_prompt}\n\n"
                "**Transcricao da imagem (OCR):**\n{ocr_text}\n\n"
                "**Resposta:** Forneca um insight claro, objetivo e relevante sobre o conteudo."
            )

        prompt = insight_prompt.format(
            extra_prompt=priority_block or "Nenhuma instrucao adicional.",
            ocr_text=ocr_text
        )
        temperature = req.temperature if req.temperature is not None else 0.0
        response = get_ollama_response(
            valid_model,
            prompt,
            temperature=temperature,
            min_chars=100,
        )
        return {"insight": (response or "").strip()}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Erro em /analyze_image_insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class VerifyResponseRequest(BaseModel):
    context: str
    question: str
    answer: str
    model: str | None = None


@router.post("/verify_response")
def verify_response(req: VerifyResponseRequest):
    try:
        valid_model = validate_model(req.model)
        if not req.context or len(req.context) < 200:
            return {"verified_answer": req.answer}

        prompt = (
            "Voce e um verificador de respostas. Sua tarefa e analisar a resposta gerada para "
            "uma pergunta, com base no contexto fornecido.\n\n"
            f"Contexto:\n{req.context}\n\n"
            f"Pergunta:\n{req.question}\n\n"
            f"Resposta gerada:\n{req.answer}\n\n"
            "Observacao importante: o contexto acima e material de referencia (texto do compendio), "
            "NAO a fonte exclusiva da resposta. Afirmacoes que derivam dos proprios dados da "
            "pergunta (numeros, matrizes, valores, calculos) NAO precisam estar no contexto para "
            "serem validas.\n\n"
            "Instrucoes:\n"
            "1. Mantenha as afirmacoes suportadas pelo contexto ou consistentes com a pergunta.\n"
            "2. Apenas remova ou marque afirmacoes que contradigam claramente o contexto ou que "
            "sejam inventacoes sem base no contexto nem na pergunta.\n"
            "3. NUNCA substitua valores, matrizes ou numeros vindos da pergunta por exemplos "
            "numericos do contexto; se os exemplos do contexto usarem outros numeros, ignore-os.\n"
            "4. Responda \"Nao encontrei essa informacao no material disponivel.\" SOMENTE quando "
            "a resposta inteira for fabricada e nenhum conteudo puder ser aproveitado.\n\n"
            "Responda APENAS com a resposta verificada, sem texto adicional."
        )
        response = get_ollama_response(
            valid_model, prompt, temperature=0.0, min_chars=50
        )
        if response:
            return {"verified_answer": response.strip()}
        return {"verified_answer": req.answer}
    except Exception as e:
        logger.exception(f"Erro em verify_response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class EvaluateAnswerRequest(BaseModel):
    question: str
    correct_answer: str
    user_answer: str
    explanation: str = ""
    context: str = ""
    model: str | None = None


@router.post("/evaluate_answer")
def evaluate_answer(req: EvaluateAnswerRequest):
    try:
        if not req.user_answer.strip() or not req.correct_answer.strip():
            return {
                "correct": False,
                "feedback": "Nao ha resposta do aluno ou gabarito para comparar.",
            }

        valid_model = validate_model(req.model)
        logger.info(f"[evaluate_answer] modelo={valid_model}")
        prompt = (
            "Voce e um professor corrigindo a resposta de um aluno em uma questao aberta.\n\n"
            f"Pergunta:\n{req.question}\n\n"
            f"Resposta correta (gabarito):\n{req.correct_answer}\n\n"
        )
        if req.explanation.strip():
            prompt += f"Explicacao do gabarito:\n{req.explanation}\n\n"
        if req.context.strip():
            prompt += (
                "Contexto do material do topico (use apenas como referencia, nao como "
                "fonte exclusiva da correcao):\n"
                f"{req.context}\n\n"
            )
        prompt += (
            f"Resposta do aluno:\n{req.user_answer}\n\n"
            "Regras da correcao:\n"
            "1. Compare o SENTIDO da resposta do aluno com o gabarito: palavras "
            "diferentes, reordenacao, exemplos a mais, paragrafos ou formulas "
            "equivalentes nao invalidam a resposta.\n"
            "2. Nao exija copia literal do gabarito: o que importa e se a resposta "
            "do aluno responde ao que a pergunta pede.\n"
            "3. Julgue como CORRETA a resposta que atinge o ponto central, ainda que "
            "resumida, ou que traga detalhes adicionais que nao contradigam o gabarito.\n"
            "4. Julgue como INCORRETA a resposta que deixa de responder a pergunta, que "
            "contradiz o gabarito, ou que seja apenas ruido sem conteudo (texto sem "
            "sentido, copia do enunciado, resposta em branco).\n"
            "5. Resposta parcialmente correta conta como incorreta, mas o comentario "
            "deve apontar o que falta.\n"
            "6. Escreva o comentario em portugues, em uma ou duas frases, sem "
            "repetir o gabarito.\n\n"
            "Responda APENAS no formato abaixo, em uma unica linha, sem texto "
            "antes ou depois:\n"
            "CORRETA | <comentario>\n"
            "ou\n"
            "INCORRETA | <comentario>"
        )

        response = get_ollama_response(
            model=valid_model,
            prompt=prompt,
            temperature=0.0,
            min_chars=10,
        )
        texto = (response or '').strip()
        if not texto:
            return {
                "correct": False,
                "feedback": "Nao foi possivel avaliar a resposta automaticamente. "
                            "Compare com o gabarito abaixo.",
            }
        primeira = texto.split('\n', 1)[0].strip()
        partes = primeira.split('|', 1)
        marca = partes[0].strip().upper()
        parecer = partes[1].strip() if len(partes) > 1 else ''
        if 'INCORRETA' in marca:
            return {"correct": False, "feedback": parecer or primeira}
        if 'CORRETA' in marca:
            return {"correct": True, "feedback": parecer or primeira}
        achado = re.search(r'\b(CORRETA|INCORRETA)\b', texto, re.IGNORECASE)
        if achado:
            veredito = achado.group(1).upper()
            resto = (texto[:achado.start()] + ' ' + texto[achado.end():]).strip(' |:.-')
            return {
                "correct": veredito == 'CORRETA',
                "feedback": resto or veredito,
            }
        logger.warning("[evaluate_answer] Resposta sem veredito reconhecivel.")
        return {
            "correct": False,
            "feedback": "Nao foi possivel avaliar a resposta automaticamente. "
                        "Compare com o gabarito abaixo.",
        }
    except Exception as e:
        logger.exception(f"Erro em evaluate_answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))
