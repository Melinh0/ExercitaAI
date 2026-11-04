from flask import Blueprint, request, redirect, url_for, flash, jsonify
from models.topic_model import TopicModel
from services.rag_client import retrieve_context, post_llm_api
from services.ollama_guard import require_ollama_key
from services.resposta_utils import extrair_resposta_da_explicacao, normalizar_tipo_questao
from services.analise_utils import texto_da_questao, aplicar_questao_texto
from services.questoes_existentes import listar_questoes_existentes
from services.json_modelo import carregar_json_do_modelo
import os
import base64
import logging
import requests
import traceback
import json as jsonlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import Config
from flask_login import login_required, current_user

question_bp = Blueprint('question', __name__)
logger = logging.getLogger(__name__)

RAG_SERVICE_URL = os.getenv('RAG_SERVICE_URL', 'http://llm_api:8001')


def _carregar_memoria_instrucoes(user, topic):
    try:
        data = TopicModel._load_json_data(user, topic)
        memoria = data.get('instruction_memory')
        if isinstance(memoria, list):
            return [m for m in memoria if isinstance(m, str) and m.strip()]
    except Exception:
        pass
    return []


def _adicionar_memoria_instrucoes(user, topic, instrucao):
    texto = (instrucao or '').strip()
    if not texto or len(texto) < 4:
        return
    try:
        data = TopicModel._load_json_data(user, topic)
        memoria = data.get('instruction_memory')
        if not isinstance(memoria, list):
            memoria = []
        if texto in memoria:
            memoria.remove(texto)
        memoria.insert(0, texto)
        data['instruction_memory'] = memoria[:20]
        TopicModel._save_json_data(user, topic, data)
    except Exception as e:
        logger.warning(f"Falha ao salvar memoria de instrucoes: {e}")


def _montar_bloco_memoria(memoria):
    if not memoria:
        return ''
    linhas = "\n".join(f"- {m}" for m in memoria[:10])
    return f"=== INSTRUÇÕES APLICADAS ANTERIORMENTE ===\n{linhas}"


def merge_subitems_into_question(questions):
    if not questions:
        return questions
    merged = []
    i = 0
    while i < len(questions):
        q = questions[i]
        num = q.get("numero", "").strip()
        is_subitem = bool(re.match(r'^[IVXLCDM]+$', num.upper())) or bool(re.match(r'^[a-z]$', num.lower()))
        if i == 0 or not is_subitem:
            current = q.copy()
            current["enunciado"] = current.get("enunciado", "")
            j = i + 1
            while j < len(questions):
                next_num = questions[j].get("numero", "").strip()
                next_is_subitem = bool(re.match(r'^[IVXLCDM]+$', num.upper())) or bool(re.match(r'^[a-z]$', next_num.lower()))
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


def _get_retrieved_context(user_id, topic, query, n_results=5, ollama_keys=None):
    try:
        retrieved = retrieve_context(user_id, topic, query, n_results, ollama_keys=ollama_keys)
        if retrieved:
            return retrieved
    except Exception as e:
        logger.warning(f"Falha na recuperacao de contexto: {e}")
    return None


def _contexto_sugestoes(user_id, topic, base, ollama_keys, instrucoes=''):
    recuperado = _get_retrieved_context(user_id, topic, base or topic, 4, ollama_keys) if topic else None
    logger.info(f"[sugestoes] user_id={user_id} topic={topic} base={base[:50] if base else None} "
                f"recuperado_chars={len(recuperado) if recuperado else 0} "
                f"recuperado_preview={(recuperado or '')[:200]}")
    foco = f"Foco pedido pelo usuario (instrucoes de personalizacao): {instrucoes}" if instrucoes else ''
    memoria = _montar_bloco_memoria(_carregar_memoria_instrucoes(current_user, topic)) if topic else ''
    partes = [p for p in (topic, base, foco, memoria, recuperado) if p]
    return '\n\n'.join(partes)[:3500]


def _contexto_completo_sugestoes(user_id, topic, base, ollama_keys, instrucoes=''):
    query_text = " ".join(t for t in (topic, base, instrucoes) if t).strip()
    retrieved_context = _get_retrieved_context(user_id, topic, query_text, 14, ollama_keys)
    context_text = retrieved_context if retrieved_context and len(retrieved_context) >= 500 else ""

    context_parts = []
    if context_text:
        context_parts.append(f"=== CONTEXTO RAG ===\n{context_text}")

    resolutions = TopicModel.get_resolutions(current_user, topic)
    if resolutions:
        qa_parts = []
        for item in resolutions[:5]:
            for q in item.get('questoes', [])[:3]:
                enun = q.get('enunciado', '').strip()
                resp = q.get('resposta', '').strip()
                expl = q.get('explicacao', '').strip()
                if enun:
                    qa_parts.append(f"Questão: {enun}")
                    if resp:
                        qa_parts.append(f"  Resposta: {resp}")
                    if expl:
                        qa_parts.append(f"  Explicação: {expl[:500]}")
        if qa_parts:
            context_parts.append("=== QUESTÕES/RESPOSTAS EXISTENTES ===\n" + "\n".join(qa_parts))

    mat_folder = TopicModel.get_material_folder(current_user, topic)
    if mat_folder and os.path.isdir(mat_folder):
        for fname in sorted(os.listdir(mat_folder)):
            if fname.endswith('.txt'):
                try:
                    with open(os.path.join(mat_folder, fname), 'r', encoding='utf-8') as f:
                        txt = f.read()[:3000]
                        if txt.strip():
                            context_parts.append(f"=== MATERIAL APOIO: {fname} ===\n{txt}")
                except Exception:
                    pass

    wb_folder = TopicModel.get_whiteboards_folder(current_user, topic)
    if wb_folder and os.path.isdir(wb_folder):
        for fname in sorted(os.listdir(wb_folder)):
            if fname.endswith('_texto_extraido.txt'):
                try:
                    with open(os.path.join(wb_folder, fname), 'r', encoding='utf-8') as f:
                        txt = f.read()[:2000]
                        if txt.strip():
                            context_parts.append(f"=== WHITEBOARD: {fname} ===\n{txt}")
                except Exception:
                    pass

    memoria = _carregar_memoria_instrucoes(current_user, topic)
    if memoria:
        context_parts.append(_montar_bloco_memoria(memoria))

    if context_parts:
        full_context = "\n\n".join(context_parts)
        if base:
            full_context = f"{base}\n\n{full_context}"
        if instrucoes:
            full_context += f"\n\nFoco pedido pelo usuario: {instrucoes}"
        return full_context[:12000]
    elif context_text:
        return context_text[:12000]
    elif base:
        return f"{base}\n\nFoco: {instrucoes}" if instrucoes else base
    else:
        return f"Tópico: {topic}\nFoco: {instrucoes}" if instrucoes else f"Tópico: {topic}"


_SUGESTAO_CACHE = {}
_SUGESTAO_CACHE_LOCK = threading.Lock()


def _fallback_contextual(mode, topic, instrucoes=''):
    t = topic or 'este conteúdo'
    foco = f" com foco em {instrucoes}" if instrucoes else ''
    mapa = {
        'generate_questions': [
            f"Gerar questões de múltipla escolha sobre {t}{foco}",
            f"Criar questões dissertativas sobre {t}{foco}",
            f"Incluir questões de verdadeiro ou falso sobre {t}",
            f"Focar nos conceitos mais difíceis de {t}",
            f"Adaptar a dificuldade ao nível do conteúdo de {t}"
        ],
        'generate_flashcards': [
            f"Criar cartões sobre os conceitos-chave de {t}",
            f"Focar em definições e fórmulas de {t}",
            f"Incluir exemplos práticos de {t}",
            f"Priorizar termos mais cobrados em {t}",
            f"Deixar as perguntas curtas sobre {t}"
        ],
        'study_strategy': [
            f"Montar plano de estudo de 4 semanas para {t}{foco}",
            f"Priorizar os temas mais importantes de {t}",
            f"Incluir revisão espaçada para {t}",
            f"Adaptar o plano a 1 hora de estudo por dia",
            f"Definir metas semanais para {t}"
        ],
        'search_articles': [
            f"Buscar artigos recentes sobre {t}{foco}",
            f"Encontrar revisões sistemáticas sobre {t}",
            f"Procurar periódicos de alto impacto sobre {t}",
            f"Filtrar por autores referência em {t}",
            f"Priorizar artigos com revisão por pares"
        ],
        'flashcard_subjects': [
            f"Conceitos fundamentais de {t}",
            f"Fórmulas e leis essenciais de {t}",
            f"Aplicações práticas de {t}",
            f"Temas mais cobrados em provas sobre {t}",
            f"Erros comuns em {t}"
        ]
    }
    return mapa.get(mode, [])


def _verify_answer_with_context(context, question, answer, model=None, ollama_keys=None):
    try:
        resp = post_llm_api(
            "/verify_response",
            json={"context": context, "question": question, "answer": answer, "model": model},
            timeout=(10, 300),
            chaves=ollama_keys
        )
        if resp.ok:
            return resp.json().get("verified_answer", answer)
        return answer
    except Exception as e:
        logger.warning(f"Falha na verificacao: {e}")
        return answer


@question_bp.route('/save', methods=['POST'])
@login_required
def save():
    topic = request.form.get('topic')
    image_filename = request.form.get('image_filename')
    q_idx = request.form.get('q_idx')
    resposta = request.form.get('resposta')
    explicacao = request.form.get('explicacao')
    enunciado = request.form.get('enunciado')
    idx = request.form.get('idx')
    original_json_str = request.form.get('original_json')

    if not all([topic, image_filename, q_idx, idx]):
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Dados incompletos'}), 400
        return "Dados incompletos", 400

    try:
        q_idx = int(q_idx)
        idx = int(idx)
    except ValueError:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Indice invalido'}), 400
        return "Indice invalido", 400

    updated_data = {'resposta': resposta, 'explicacao': explicacao}
    if enunciado is not None:
        updated_data['enunciado'] = enunciado

    resolutions = TopicModel.get_resolutions(current_user, topic)
    original_question = None
    for item in resolutions:
        if item.get("imagem") == image_filename:
            if 0 <= q_idx < len(item["questoes"]):
                original_question = item["questoes"][q_idx].copy()
            break

    if original_question is not None:
        tipo_normalizado = normalizar_tipo_questao(
            original_question.get('tipo', ''), resposta
        )
        if tipo_normalizado != (original_question.get('tipo', '') or '').strip().lower():
            updated_data['tipo'] = tipo_normalizado

    updated = TopicModel.update_question(current_user, topic, image_filename, q_idx, updated_data)
    if not updated:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Questao nao encontrada'}), 404
        return "Questao nao encontrada", 404

    if original_json_str and original_question:
        original_question_json = None
        try:
            original_question_json = jsonlib.loads(original_json_str)
        except Exception:
            pass
        if original_question_json and (original_question.get('resposta') != resposta or original_question.get('explicacao') != explicacao):
            try:
                corrected_question = {
                    "numero": original_question.get('questao', ''),
                    "tipo": original_question.get('tipo', ''),
                    "enunciado": original_question.get('enunciado', ''),
                    "resposta": resposta,
                    "explicacao": explicacao
                }
                payload = {
                    "original_json": {"questions": [original_question_json]},
                    "corrected_json": {"questions": [corrected_question]},
                    "metadata": {"topic": topic, "image": image_filename, "q_idx": q_idx}
                }
                requests.post(f"{RAG_SERVICE_URL}/add_correction", json=payload, timeout=5)
            except Exception as e:
                logger.warning(f"Erro ao enviar correcao: {e}")

    if request.accept_mimetypes.accept_json:
        return jsonify({'success': True})
    return redirect(url_for('topic.ver_topic', topic_name=topic, idx=idx, q=q_idx))


@question_bp.route('/topic/<topic_name>/add_question', methods=['POST'])
@login_required
def add_question(topic_name):
    image_filename = request.form.get('image_filename')
    questao_num = request.form.get('questao_num', '').strip()
    tipo = request.form.get('tipo', '').strip()
    resposta = request.form.get('resposta', '').strip()
    explicacao = request.form.get('explicacao', '').strip()
    idx = request.form.get('idx', 0)

    if not image_filename or not questao_num:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Numero da questao e obrigatorio.'}), 400
        flash('Numero da questao e obrigatorio.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    questao_data = {
        "questao": questao_num,
        "tipo": tipo,
        "resposta": resposta,
        "explicacao": explicacao,
        "whiteboard_img": None
    }
    new_q_idx = TopicModel.add_question(current_user, topic_name, image_filename, questao_data)
    if request.accept_mimetypes.accept_json:
        return jsonify({'success': True, 'index': new_q_idx})
    flash('Questao adicionada com sucesso!', 'success')
    return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx, q=new_q_idx))


@question_bp.route('/topic/<topic_name>/delete_question', methods=['POST'])
@login_required
def delete_question(topic_name):
    image_filename = request.form.get('image_filename')
    q_idx = request.form.get('q_idx')
    idx = request.form.get('idx', 0)

    if not image_filename or q_idx is None:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Parametros insuficientes.'}), 400
        flash('Parametros insuficientes.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    try:
        q_idx = int(q_idx)
        idx = int(idx)
    except ValueError:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Indice invalido.'}), 400
        flash('Indice invalido.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    deleted = TopicModel.delete_question(current_user, topic_name, image_filename, q_idx)
    if not deleted:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Questao nao encontrada.'}), 404
        flash('Questao nao encontrada.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    if request.accept_mimetypes.accept_json:
        return jsonify({'success': True})
    flash('Questao deletada com sucesso!', 'success')
    return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx, q=0))


@question_bp.route('/save_whiteboard', methods=['POST'])
@login_required
def save_whiteboard():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    topic = data.get('topic')
    image_filename = data.get('image_filename')
    q_idx = data.get('q_idx')
    image_data = data.get('image_data')

    if not all([topic, image_filename, q_idx is not None, image_data]):
        return jsonify({'error': 'Parametros incompletos'}), 400

    try:
        q_idx = int(q_idx)
    except ValueError:
        return jsonify({'error': 'Indice invalido'}), 400

    header, encoded = image_data.split(',', 1)
    decoded = base64.b64decode(encoded)

    resolutions = TopicModel.get_resolutions(current_user, topic)
    found = False
    old_filename = None
    new_filename = None
    base_name = os.path.splitext(os.path.basename(image_filename))[0]
    for item in resolutions:
        if item.get("imagem") == image_filename:
            if q_idx == -1:
                old_filename = item.get('whiteboard_livre')
                new_filename = f"whiteboard_{base_name}_livre.png"
                item['whiteboard_livre'] = new_filename
                found = True
                break
            questoes = item.get("questoes", [])
            if 0 <= q_idx < len(questoes):
                old_filename = questoes[q_idx].get('whiteboard_img')
                new_filename = f"whiteboard_{base_name}_q{q_idx}.png"
                questoes[q_idx]['whiteboard_img'] = new_filename
                found = True
            break

    if not found:
        if q_idx == -1:
            resolutions.append({
                'imagem': image_filename,
                'questoes': [],
                'whiteboard_livre': f"whiteboard_{base_name}_livre.png",
            })
            old_filename = None
            new_filename = f"whiteboard_{base_name}_livre.png"
        else:
            return jsonify({'error': 'Questao nao encontrada'}), 404

    whiteboard_folder = TopicModel.get_whiteboards_folder(current_user, topic)
    os.makedirs(whiteboard_folder, exist_ok=True)
    filepath = os.path.join(whiteboard_folder, new_filename)
    with open(filepath, 'wb') as f:
        f.write(decoded)

    if old_filename and old_filename != new_filename:
        old_path = os.path.join(whiteboard_folder, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)

    TopicModel.save_resolutions(current_user, topic, resolutions)
    return jsonify({'success': True, 'filename': new_filename})


@question_bp.route('/register_instruction', methods=['POST'])
@login_required
def register_instruction():
    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    instrucao = (data.get('instruction') or '').strip()
    if not topic or not instrucao:
        return jsonify({'error': 'Parametros incompletos'}), 400
    _adicionar_memoria_instrucoes(current_user, topic, instrucao)
    return jsonify({'success': True})


@question_bp.route('/save_example', methods=['POST'])
@login_required
def save_example():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    topic = data.get('topic')
    image_filename = data.get('image_filename')
    q_idx = data.get('q_idx')
    enunciado = data.get('enunciado', '').strip()
    resposta = data.get('resposta', '').strip()
    explicacao = data.get('explicacao', '').strip()

    if not topic or not image_filename or q_idx is None:
        return jsonify({'error': 'Parametros incompletos'}), 400

    document = f"Questao: {enunciado}\nResposta: {resposta}\nExplicacao: {explicacao}"
    metadata = {
        "topic": topic,
        "image": image_filename,
        "question_index": q_idx,
        "enunciado": enunciado,
        "resposta": resposta,
        "explicacao": explicacao,
        "user_id": str(current_user.id)
    }

    try:
        resp = requests.post(
            f"{RAG_SERVICE_URL}/add_example",
            json={"document": document, "metadata": metadata},
            timeout=10
        )
        if resp.ok:
            return jsonify({'success': True})
        logger.error(f"Falha ao salvar exemplo: {resp.text}")
        return jsonify({'error': 'Erro ao salvar exemplo'}), 500
    except Exception as e:
        logger.exception(f"Erro ao salvar exemplo: {e}")
        return jsonify({'error': str(e)}), 500


@question_bp.route('/analyze_with_image', methods=['POST', 'OPTIONS'], strict_slashes=False)
@login_required
@require_ollama_key
def analyze_with_image():
    logger.info("=" * 50)
    logger.info("Recebida requisicao para /analyze_with_image")
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Corpo da requisicao deve ser JSON'}), 400

    topic = data.get('topic')
    image_filename = data.get('image_filename')
    model = data.get('model')
    extra_prompt = data.get('extra_prompt', '')
    analysis_type = data.get('analysis_type', 'questions')
    transcription_method = data.get('transcription_method', 'tesseract')
    ocr_model = data.get('ocr_model') if transcription_method == 'llm' else None
    temperature = data.get('temperature')
    verify = bool(data.get('verify', False))

    if not topic or not image_filename:
        return jsonify({'error': 'Parametros incompletos'}), 400

    images_folder = TopicModel.get_images_folder(current_user, topic)
    image_path = os.path.join(images_folder, image_filename)
    resolutions = TopicModel.get_resolutions(current_user, topic)
    item_texto = None
    for it in resolutions:
        if it.get("imagem") == image_filename:
            item_texto = it
            break
    image_base64 = ""
    texto_base = ""
    if os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
    else:
        if not item_texto or not item_texto.get("is_text_question"):
            return jsonify({'error': 'Imagem nao encontrada'}), 404
        texto_base = texto_da_questao(item_texto)
        if not texto_base:
            return jsonify({'error': 'Imagem nao encontrada'}), 404

    payload = {
        'image_base64': image_base64,
        'model': model,
        'analysis_type': analysis_type,
        'extra_prompt': extra_prompt,
        'transcription_method': transcription_method,
        'ocr_model': ocr_model,
        'input_text': texto_base
    }

    if temperature is not None:
        payload['temperature'] = temperature

    if analysis_type == 'insight':
        try:
            rag_resp = post_llm_api(
                "/analyze_image_insight",
                json=payload,
                timeout=120
            )
            if rag_resp.ok:
                dados = rag_resp.json()
                return jsonify({'success': True, 'insight': dados.get('insight', '')})
            logger.error(f"Falha no servico RAG: {rag_resp.status_code} - {rag_resp.text}")
            return jsonify({'error': 'Falha no servico de analise de imagem'}), 500
        except Exception as e:
            logger.exception(f"Erro no processamento: {e}")
            return jsonify({'error': str(e)}), 500

    context_texts = []
    context_images = []
    if not texto_base:
        for item in resolutions:
            if item.get("imagem") == image_filename:
                for q in item.get("questoes", []):
                    q_text = f"Questao {q.get('questao', '')}:\n"
                    q_text += f"Enunciado: {q.get('enunciado', '')}\n"
                    q_text += f"Tipo: {q.get('tipo', '')}\n"
                    q_text += f"Resposta: {q.get('resposta', '')}\n"
                    q_text += f"Explicacao: {q.get('explicacao', '')}\n"
                    context_texts.append(q_text)
                    whiteboard_img = q.get('whiteboard_img')
                    if whiteboard_img:
                        whiteboard_path = TopicModel.get_whiteboards_folder(current_user, topic)
                        wb_full = os.path.join(whiteboard_path, whiteboard_img)
                        if os.path.exists(wb_full):
                            with open(wb_full, 'rb') as f:
                                base64_data = base64.b64encode(f.read()).decode('utf-8')
                                context_images.append(base64_data)
                break

    payload['context_images'] = context_images
    ocr_text = texto_base or " ".join(context_texts)
    query_text = ocr_text + " " + extra_prompt
    ollama_keys = current_user.get_ollama_keys()
    retrieved_context = _get_retrieved_context(
        current_user.id, topic, query_text, 5, ollama_keys
    )
    if retrieved_context and len(retrieved_context) >= 500:
        payload['context_texts'] = context_texts + [f"[RAG_BASE]{retrieved_context}"]
    else:
        payload['context_texts'] = context_texts
    payload['output_format'] = 'structured'
    payload['extra_prompt'] = extra_prompt

    try:
        rag_resp = post_llm_api(
            "/analyze_image",
            json=payload,
            timeout=600
        )
        if not rag_resp.ok:
            logger.error(f"Falha no servico RAG: {rag_resp.status_code} - {rag_resp.text}")
            return jsonify({'error': 'Falha no servico de analise de imagem'}), 500

        dados = rag_resp.json()
        if 'questions' not in dados:
            logger.error(f"Resposta sem 'questions': {dados}")
            return jsonify({'error': 'Formato de resposta invalido do servico RAG'}), 500

        questoes = dados['questions']
        if not isinstance(questoes, list):
            return jsonify({'error': 'Resposta nao e uma lista de questoes'}), 500

        if verify and not texto_base:
            contexto_para_verificacao = " ".join(payload['context_texts'])
            for q in questoes:
                if q.get('resposta') or q.get('explicacao'):
                    verified = _verify_answer_with_context(
                        contexto_para_verificacao,
                        q.get('enunciado', ''),
                        q.get('explicacao', ''),
                        model
                    )
                    q['explicacao'] = verified

        questoes = merge_subitems_into_question(questoes)

        if texto_base:
            nova = next((q for q in questoes if (q.get('enunciado') or '').strip()), None)
            if not nova:
                return jsonify({'error': 'Nao foi possivel analisar a questao'}), 500
            aplicar_questao_texto(item_texto, nova, texto_base)
            TopicModel.save_resolutions(current_user, topic, resolutions)
            return jsonify({'success': True, 'questions': item_texto['questoes'], 'count': 1})

        todas = TopicModel.get_resolutions(current_user, topic)
        item = None
        for it in todas:
            if it.get("imagem") == image_filename:
                item = it
                break
        if not item:
            item = {"imagem": image_filename, "questoes": []}
            todas.append(item)

        existentes = {q['questao']: q for q in item['questoes']}
        for nova in questoes:
            num = str(nova.get('numero', ''))
            if not num:
                continue
            if num in existentes:
                if not existentes[num].get('resposta') and nova.get('resposta'):
                    existentes[num]['resposta'] = nova['resposta']
                if not existentes[num].get('explicacao') and nova.get('explicacao'):
                    existentes[num]['explicacao'] = nova['explicacao']
                if not existentes[num].get('tipo') and nova.get('tipo'):
                    existentes[num]['tipo'] = nova['tipo']
                if not existentes[num].get('enunciado') and nova.get('enunciado'):
                    existentes[num]['enunciado'] = nova['enunciado']
            else:
                item['questoes'].append({
                    "questao": num,
                    "tipo": nova.get('tipo', ''),
                    "resposta": nova.get('resposta', ''),
                    "explicacao": nova.get('explicacao', ''),
                    "enunciado": nova.get('enunciado', ''),
                    "whiteboard_img": None
                })

        TopicModel.save_resolutions(current_user, topic, todas)

        return jsonify({'success': True, 'questions': item['questoes'], 'count': len(questoes)})

    except Exception as e:
        logger.exception(f"Erro no processamento: {e}")
        return jsonify({'error': str(e)}), 500


@question_bp.route('/analyze_full_document', methods=['POST', 'OPTIONS'], strict_slashes=False)
@login_required
@require_ollama_key
def analyze_full_document():
    logger.info("=" * 50)
    logger.info("Recebida requisicao para /analyze_full_document")
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Corpo da requisicao deve ser JSON'}), 400

    topic = data.get('topic')
    model = data.get('model')
    extra_prompt = data.get('extra_prompt', '')
    transcription_method = data.get('transcription_method', 'tesseract')
    ocr_model = data.get('ocr_model') if transcription_method == 'llm' else None

    if not topic:
        return jsonify({'error': 'Parametros incompletos'}), 400

    user_id = current_user.id
    ollama_keys = current_user.get_ollama_keys()

    image_files = TopicModel.get_image_files(current_user, topic)
    if not image_files:
        return jsonify({'error': 'Nenhuma imagem encontrada neste topico'}), 404

    images_folder = TopicModel.get_images_folder(current_user, topic)
    pages = []
    for filename in image_files:
        image_path = os.path.join(images_folder, filename)
        if not os.path.exists(image_path):
            continue
        with open(image_path, 'rb') as f:
            pages.append((filename, base64.b64encode(f.read()).decode('utf-8')))

    if not pages:
        return jsonify({'error': 'Nenhuma imagem valida encontrada'}), 404

    def extract_page_text(item):
        filename, image_b64 = item
        try:
            resp = post_llm_api(
                "/extract_text_from_image",
                json={'image_base64': image_b64},
                timeout=180,
                chaves=ollama_keys
            )
            if resp.ok:
                page_text = resp.json().get('text', '')
                if page_text:
                    return filename, f"--- Pagina: {filename} ---\n{page_text}"
        except Exception as e:
            logger.warning(f"Falha ao extrair texto de {filename}: {e}")
        return filename, ""

    document_texts_map = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(extract_page_text, item): item[0] for item in pages}
        for future in as_completed(futures):
            filename = futures[future]
            try:
                fname, text = future.result()
                if text:
                    document_texts_map[fname] = text
            except Exception as e:
                logger.warning(f"Erro no worker de extracao para {filename}: {e}")

    ordered_texts = [document_texts_map.get(fname, "") for fname, _ in pages if document_texts_map.get(fname)]
    full_document_text = "\n\n".join(ordered_texts)[:12000]

    todas = TopicModel.get_resolutions(current_user, topic)

    def process_page(item):
        filename, image_b64 = item
        item_ref = None
        for it in todas:
            if it.get("imagem") == filename:
                item_ref = it
                break
        if not item_ref:
            item_ref = {"imagem": filename, "questoes": []}
            todas.append(item_ref)

        context_texts = [full_document_text] if full_document_text else []
        query_text = (full_document_text + " " + extra_prompt).strip()
        retrieved_context = _get_retrieved_context(user_id, topic, query_text, 5, ollama_keys)
        if retrieved_context and len(retrieved_context) >= 500:
            context_texts.append(f"[RAG_BASE]{retrieved_context}")

        payload = {
            'image_base64': image_b64,
            'model': model,
            'analysis_type': 'questions',
            'extra_prompt': extra_prompt,
            'transcription_method': transcription_method,
            'ocr_model': ocr_model,
            'context_images': [],
            'context_texts': context_texts,
            'output_format': 'structured'
        }

        try:
            rag_resp = post_llm_api(
                "/analyze_image",
                json=payload,
                timeout=600,
                chaves=ollama_keys
            )
            if not rag_resp.ok:
                logger.error(f"Falha no servico RAG para {filename}: {rag_resp.status_code} - {rag_resp.text}")
                return filename, 0, False

            dados = rag_resp.json()
            questoes = dados.get('questions', [])
            if not isinstance(questoes, list):
                return filename, 0, False

            contexto_para_verificacao = " ".join(context_texts)
            for q in questoes:
                if q.get('resposta') or q.get('explicacao'):
                    verified = _verify_answer_with_context(
                        contexto_para_verificacao,
                        q.get('enunciado', ''),
                        q.get('explicacao', ''),
                        model,
                        ollama_keys=ollama_keys
                    )
                    q['explicacao'] = verified

            questoes = merge_subitems_into_question(questoes)

            existentes = {q['questao']: q for q in item_ref['questoes']}
            for nova in questoes:
                num = str(nova.get('numero', ''))
                if not num:
                    continue
                if num in existentes:
                    if not existentes[num].get('resposta') and nova.get('resposta'):
                        existentes[num]['resposta'] = nova['resposta']
                    if not existentes[num].get('explicacao') and nova.get('explicacao'):
                        existentes[num]['explicacao'] = nova['explicacao']
                    if not existentes[num].get('tipo') and nova.get('tipo'):
                        existentes[num]['tipo'] = nova['tipo']
                    if not existentes[num].get('enunciado') and nova.get('enunciado'):
                        existentes[num]['enunciado'] = nova['enunciado']
                else:
                    item_ref['questoes'].append({
                        "questao": num,
                        "tipo": nova.get('tipo', ''),
                        "resposta": nova.get('resposta', ''),
                        "explicacao": nova.get('explicacao', ''),
                        "enunciado": nova.get('enunciado', ''),
                        "whiteboard_img": None
                    })
                    existentes[num] = item_ref['questoes'][-1]

            return filename, len(questoes), True
        except Exception as e:
            logger.exception(f"Erro ao analisar {filename}: {e}")
            return filename, 0, False

    total_count = 0
    failed_pages = []
    max_workers = min(4, max(1, len(pages)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_page, item): item[0] for item in pages}
        for future in as_completed(futures):
            filename = futures[future]
            try:
                fname, count, ok = future.result()
                if ok:
                    total_count += count
                else:
                    failed_pages.append(fname)
            except Exception as e:
                logger.exception(f"Erro em worker de pagina {filename}: {e}")
                failed_pages.append(filename)

    TopicModel.save_resolutions(current_user, topic, todas)

    return jsonify({
        'success': True,
        'count': total_count,
        'pages_processed': len(pages),
        'failed_pages': failed_pages
    })


@question_bp.route('/evaluate_answer', methods=['POST'])
@login_required
@require_ollama_key
def evaluate_answer():
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()
    gabarito = (data.get('correct_answer') or '').strip()
    explicacao = (data.get('explanation') or '').strip()
    resposta = (data.get('user_answer') or '').strip()
    topic = (data.get('topic') or '').strip()
    model = data.get('model')

    if not question or not gabarito or not resposta:
        return jsonify({'error': 'Parametros incompletos'}), 400

    contexto = ''
    if topic:
        try:
            contexto = _get_retrieved_context(
                current_user.id, topic, question, 3, current_user.get_ollama_keys()
            )
        except Exception as e:
            logger.warning(f"Erro ao recuperar contexto para avaliacao: {e}")

    try:
        rag_resp = post_llm_api(
            '/evaluate_answer',
            json={
                'question': question,
                'correct_answer': gabarito,
                'explanation': explicacao,
                'user_answer': resposta,
                'context': contexto or '',
                'model': model,
            },
            timeout=(10, 120)
        )
    except Exception as e:
        logger.warning(f"Falha ao chamar avaliacao de resposta: {e}")
        return jsonify({'error': 'Servico de avaliacao indisponivel'}), 502

    if not rag_resp.ok:
        return jsonify({'error': 'Falha ao avaliar a resposta'}), 500

    return jsonify(rag_resp.json())


@question_bp.route('/enhance_question', methods=['POST'])
@login_required
@require_ollama_key
def enhance_question():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    topic = data.get('topic')
    image_filename = data.get('image_filename')
    q_idx = data.get('q_idx')
    enunciado = data.get('enunciado', '').strip()
    explicacao_atual = data.get('explicacao', '').strip()
    resposta = data.get('resposta', '').strip()
    custom_prompt = data.get('custom_prompt', '').strip()
    model = data.get('model')

    if not all([topic, image_filename, q_idx is not None]):
        return jsonify({'error': 'Parametros incompletos'}), 400

    user_id = current_user.id
    ollama_keys = current_user.get_ollama_keys()

    query_text = enunciado if enunciado else f"Questao {q_idx}"
    retrieved_context = _get_retrieved_context(user_id, topic, query_text, 3, ollama_keys)

    if retrieved_context and len(retrieved_context) > 200:
        exemplo_texto = "\n\n**Contexto adicional do topico (recuperado):**\n" + retrieved_context + "\n"
    else:
        exemplo_texto = "\n\n**Contexto adicional do topico (recuperado):**\nNenhum contexto adicional disponivel. Use seu conhecimento geral e, ao final, sugira pesquisas para enriquecer o material.\n"

    exemplos = []
    try:
        resp = requests.post(
            f"{RAG_SERVICE_URL}/retrieve_examples",
            json={
                "query": query_text,
                "n_results": 2,
                "user_id": current_user.id
            },
            timeout=10
        )
        if resp.ok:
            exemplos = resp.json().get("examples", [])
    except Exception as e:
        logger.warning(f"Falha ao recuperar exemplos: {e}")

    if exemplos:
        exemplo_texto += "\n\n**Exemplos de resolucoes anteriores (use como referencia):**\n"
        for ex in exemplos:
            exemplo_texto += f"\n--- Exemplo ---\n"
            exemplo_texto += f"Enunciado: {ex.get('enunciado', '')}\n"
            exemplo_texto += f"Resposta: {ex.get('resposta', '')}\n"
            exemplo_texto += f"Explicacao: {ex.get('explicacao', '')}\n"

    consulta = f"Enunciado: {enunciado}\nResposta: {resposta}\nExplicacao atual: {explicacao_atual}"
    if custom_prompt:
        consulta += f"\n\nInstrucoes adicionais: {custom_prompt}"
    else:
        consulta += "\n\nPor favor, melhore a explicacao acima, tornando-a mais clara, detalhada e didatica. Inclua raciocinio passo a passo e auto-verificacao."

    consulta += ("\n\nEscreva a nova explicacao comecando pela linha '**Resposta:** <resposta>' e "
                 "terminando pela linha '**Resposta final:** <resposta>', com o mesmo valor nas duas "
                 "linhas e desenvolvendo a resolucao entre elas. Se a resposta mudar em relacao a "
                 "informada acima, atualize as duas linhas.")

    if not retrieved_context or len(retrieved_context) < 200:
        consulta += "\n\nATENCAO: O contexto disponivel e muito limitado. Mesmo assim, tente dar uma resposta baseada no seu conhecimento geral. Apos a resposta, indique claramente que o contexto e insuficiente e sugira termos de busca e tipos de documentos que o usuario poderia adicionar para melhorar futuras respostas."

    consulta_completa = exemplo_texto + "\n\n" + consulta

    try:
        rag_resp = post_llm_api(
            "/generate",
            json={
                'question_text': consulta_completa,
                'model': model,
                'user_id': current_user.id
            },
            timeout=(10, 180)
        )
        if not rag_resp.ok:
            return jsonify({'error': 'Falha no servico RAG'}), 500

        dados = rag_resp.json()
        nova_explicacao = dados['explanation']

        if retrieved_context and len(retrieved_context) >= 200:
            context_for_verify = exemplo_texto + "\n" + consulta
            verified = _verify_answer_with_context(context_for_verify, query_text, nova_explicacao, model)
            nova_explicacao = verified
        else:
            logger.info("Contexto insuficiente, pulando verificacao para manter sugestoes de pesquisa.")

        resolutions = TopicModel.get_resolutions(current_user, topic)
        nova_resposta = extrair_resposta_da_explicacao(nova_explicacao, resposta)
        for item in resolutions:
            if item.get('imagem') == image_filename:
                if 0 <= q_idx < len(item['questoes']):
                    item['questoes'][q_idx]['explicacao'] = nova_explicacao
                    if nova_resposta and nova_resposta != resposta:
                        item['questoes'][q_idx]['resposta'] = nova_resposta
                    if enunciado:
                        item['questoes'][q_idx]['enunciado'] = enunciado
                    TopicModel.save_resolutions(current_user, topic, resolutions)
                    return jsonify({
                        'success': True,
                        'explicacao': nova_explicacao,
                        'resposta': nova_resposta
                    })
        return jsonify({'error': 'Questao nao encontrada'}), 404
    except requests.exceptions.ReadTimeout as e:
        logger.error(f"Timeout na requisicao para /enhance_question: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'O servico de IA demorou demais para responder. Tente novamente em alguns instantes ou use um modelo mais rapido.'}), 504
    except Exception as e:
        logger.error(f"Excecao em /enhance_question: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@question_bp.route('/generate_questions', methods=['POST'])
@login_required
@require_ollama_key
def generate_questions():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    topic = data.get('topic')
    question_types = data.get('question_types', ['objetiva', 'aberta', 'vf'])
    num_questions = data.get('num_questions', 10)
    custom_instructions = data.get('custom_instructions', '')
    model = data.get('model')

    if not topic:
        return jsonify({'error': 'Topico nao informado'}), 400

    user_id = current_user.id
    ollama_keys = current_user.get_ollama_keys()

    query_text = " ".join(t for t in (topic, custom_instructions) if t).strip()
    retrieved_context = _get_retrieved_context(user_id, topic, query_text, 14, ollama_keys)
    context_text = retrieved_context if retrieved_context and len(retrieved_context) >= 500 else ""

    context_parts = []
    if context_text:
        context_parts.append(f"=== CONTEXTO RAG ===\n{context_text}")

    resolutions = TopicModel.get_resolutions(current_user, topic)
    if resolutions:
        qa_parts = []
        for item in resolutions[:5]:
            for q in item.get('questoes', [])[:3]:
                enun = q.get('enunciado', '').strip()
                resp = q.get('resposta', '').strip()
                expl = q.get('explicacao', '').strip()
                if enun:
                    qa_parts.append(f"Questão: {enun}")
                    if resp:
                        qa_parts.append(f"  Resposta: {resp}")
                    if expl:
                        qa_parts.append(f"  Explicação: {expl[:500]}")
        if qa_parts:
            context_parts.append("=== QUESTÕES/RESPOSTAS EXISTENTES ===\n" + "\n".join(qa_parts))

    mat_folder = TopicModel.get_material_folder(current_user, topic)
    if mat_folder and os.path.isdir(mat_folder):
        for fname in sorted(os.listdir(mat_folder)):
            if fname.endswith('.txt'):
                try:
                    with open(os.path.join(mat_folder, fname), 'r', encoding='utf-8') as f:
                        txt = f.read()[:3000]
                        if txt.strip():
                            context_parts.append(f"=== MATERIAL APOIO: {fname} ===\n{txt}")
                except Exception:
                    pass

    wb_folder = TopicModel.get_whiteboards_folder(current_user, topic)
    if wb_folder and os.path.isdir(wb_folder):
        for fname in sorted(os.listdir(wb_folder)):
            if fname.endswith('_texto_extraido.txt'):
                try:
                    with open(os.path.join(wb_folder, fname), 'r', encoding='utf-8') as f:
                        txt = f.read()[:2000]
                        if txt.strip():
                            context_parts.append(f"=== WHITEBOARD: {fname} ===\n{txt}")
                except Exception:
                    pass

    memoria = _carregar_memoria_instrucoes(current_user, topic)
    if memoria:
        context_parts.append(_montar_bloco_memoria(memoria))

    if context_parts:
        context_text = "\n\n".join(context_parts)
    elif not context_text:
        snippets = []
        for item in resolutions[:3]:
            for q in item.get('questoes', [])[:2]:
                snippets.append(q.get('enunciado', '')[:200])
        if snippets:
            context_text = "Algumas questoes do topico:\n" + "\n".join(snippets)

    MAX_CONTEXT_LENGTH = 12000
    if len(context_text) > MAX_CONTEXT_LENGTH:
        context_text = context_text[:MAX_CONTEXT_LENGTH] + "\n... (contexto truncado)"

    payload = {
        'context': context_text,
        'question_types': question_types,
        'num_questions': num_questions,
        'custom_instructions': custom_instructions,
        'model': model,
        'subject': topic,
        'user_id': current_user.id,
        'existing_questions': listar_questoes_existentes(current_user, topic)
    }

    try:
        rag_resp = post_llm_api("/generate_custom_questions", json=payload, timeout=600)
        if not rag_resp.ok:
            logger.error(f"Falha no servico RAG: {rag_resp.status_code} - {rag_resp.text}")
            return jsonify({'error': 'Falha no servico de geracao de questoes'}), 500
        resposta = rag_resp.json()
        if resposta.get("questions"):
            resp_str = jsonlib.dumps(resposta, ensure_ascii=False)
            verified = _verify_answer_with_context(context_text, query_text, resp_str, model)
            verificada = carregar_json_do_modelo(verified)
            if verificada is not None:
                resposta = verificada
        return jsonify(resposta)
    except Exception as e:
        logger.exception(f"Erro ao chamar servico RAG: {e}")
        return jsonify({'error': str(e)}), 500


@question_bp.route('/generate_flashcards', methods=['POST'])
@login_required
@require_ollama_key
def generate_flashcards():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    topic = data.get('topic')
    subject = (data.get('subject') or '').strip()
    custom_instructions = data.get('custom_instructions', '')
    model = data.get('model')
    max_flashcards = data.get('max_flashcards', 12)

    if not topic:
        return jsonify({'error': 'Topico nao informado'}), 400

    if not subject or len(subject) < 3:
        return jsonify({
            'error': 'Assunto dos flashcards e obrigatorio (minimo 3 caracteres). '
                     'Informe o campo "subject" no corpo da requisicao.'
        }), 400

    try:
        max_flashcards = int(max_flashcards)
    except (TypeError, ValueError):
        max_flashcards = 12
    if max_flashcards < 1:
        max_flashcards = 1
    if max_flashcards > 50:
        max_flashcards = 50

    user_id = current_user.id
    ollama_keys = current_user.get_ollama_keys()

    query_text = " ".join(t for t in (subject, custom_instructions, topic) if t).strip()
    retrieved_context = _get_retrieved_context(user_id, topic, query_text, 14, ollama_keys)
    context_text = retrieved_context if retrieved_context else ""

    context_parts = []
    if context_text:
        context_parts.append(f"=== CONTEXTO RAG ===\n{context_text}")

    resolutions = TopicModel.get_resolutions(current_user, topic)
    if resolutions:
        qa_parts = []
        for item in resolutions[:5]:
            for q in item.get('questoes', [])[:3]:
                enun = q.get('enunciado', '').strip()
                resp = q.get('resposta', '').strip()
                expl = q.get('explicacao', '').strip()
                if enun:
                    qa_parts.append(f"Questão: {enun}")
                    if resp:
                        qa_parts.append(f"  Resposta: {resp}")
                    if expl:
                        qa_parts.append(f"  Explicação: {expl[:500]}")
        if qa_parts:
            context_parts.append("=== QUESTÕES/RESPOSTAS EXISTENTES ===\n" + "\n".join(qa_parts))

    mat_folder = TopicModel.get_material_folder(current_user, topic)
    if mat_folder and os.path.isdir(mat_folder):
        for fname in sorted(os.listdir(mat_folder)):
            if fname.endswith('.txt'):
                try:
                    with open(os.path.join(mat_folder, fname), 'r', encoding='utf-8') as f:
                        txt = f.read()[:3000]
                        if txt.strip() and (subject.lower() in txt.lower() or any(w in txt.lower() for w in subject.lower().split() if len(w) > 3)):
                            context_parts.append(f"=== MATERIAL APOIO: {fname} ===\n{txt}")
                except Exception:
                    pass

    memoria = _carregar_memoria_instrucoes(current_user, topic)
    if memoria:
        context_parts.append(_montar_bloco_memoria(memoria))

    if context_parts:
        context_text = "\n\n".join(context_parts)
    elif not context_text:
        snippets = []
        for item in resolutions[:3]:
            for q in item.get('questoes', [])[:2]:
                snippets.append(q.get('enunciado', '')[:200])
        if snippets:
            context_text = "Algumas questoes do topico:\n" + "\n".join(snippets)

    MAX_CONTEXT_LENGTH = 12000
    if len(context_text) > MAX_CONTEXT_LENGTH:
        context_text = context_text[:MAX_CONTEXT_LENGTH] + "\n... (contexto truncado)"

    payload = {
        'context': context_text,
        'subject': subject,
        'max_flashcards': max_flashcards,
        'custom_instructions': custom_instructions,
        'model': model
    }

    try:
        rag_resp = post_llm_api("/generate_flashcards", json=payload, timeout=600)
        if not rag_resp.ok:
            logger.error(f"Falha no servico RAG: {rag_resp.status_code} - {rag_resp.text}")
            return jsonify({'error': 'Falha no servico de geracao de flashcards'}), 500

        resposta = rag_resp.json()
        flashcards = resposta.get("flashcards", [])

        if isinstance(flashcards, list):
            seen_titles = set()
            unique_flashcards = []
            for card in flashcards:
                title = card.get('title', '').strip().lower()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    unique_flashcards.append(card)

            if len(unique_flashcards) < max_flashcards:
                fallback_templates = [
                    {
                        "title": f"História e evolução de {subject}",
                        "objective": f"Compreender a origem e o desenvolvimento de {subject}.",
                        "explanation": f"A história de {subject} mostra como o conhecimento evoluiu ao longo do tempo.",
                        "example": f"Exemplo: A evolução de {subject} é marcada por descobertas transformadoras.",
                        "exercise": f"Descreva um marco histórico importante para {subject}.",
                        "answer": f"Marcos históricos de {subject} incluem descobertas e inovações."
                    },
                    {
                        "title": f"Principais conceitos de {subject}",
                        "objective": f"Reconhecer os conceitos fundamentais de {subject}.",
                        "explanation": f"{subject} envolve princípios fundamentais essenciais.",
                        "example": f"Exemplo: Os conceitos básicos de {subject} aparecem em situações do dia a dia.",
                        "exercise": f"Explique o que é {subject} e cite uma aplicação prática.",
                        "answer": f"{subject} é uma disciplina com aplicações em diversas áreas."
                    }
                ]
                available_templates = [t for t in fallback_templates if t["title"].lower() not in seen_titles]
                while len(available_templates) < (max_flashcards - len(unique_flashcards)):
                    idx = len(available_templates) + 1
                    available_templates.append({
                        "title": f"Aspecto {idx} de {subject}",
                        "objective": f"Compreender o aspecto {idx} de {subject}.",
                        "explanation": f"Este flashcard aborda um aspecto relevante de {subject}.",
                        "example": f"Exemplo: Ao estudar {subject}, relacione este aspecto com situações práticas.",
                        "exercise": f"Explique a relevância do aspecto {idx} de {subject}.",
                        "answer": f"O aspecto {idx} contribui para o entendimento abrangente de {subject}."
                    })

                for i in range(max_flashcards - len(unique_flashcards)):
                    unique_flashcards.append(available_templates[i])

            flashcards = unique_flashcards[:max_flashcards]

        resposta["flashcards"] = flashcards
        if len(flashcards) < max_flashcards:
            resposta.setdefault("metadata", {})["warning"] = (
                f"Gerados apenas {len(flashcards)} flashcards. "
                f"Adicionados {max_flashcards - len(flashcards)} genéricos."
            )

        return jsonify(resposta)

    except Exception as e:
        logger.exception(f"Erro ao chamar servico RAG: {e}")
        return jsonify({'error': str(e)}), 500


@question_bp.route('/save_answers', methods=['POST'])
@login_required
def save_answers():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    topic = data.get('topic')
    session_data = data.get('session_data')
    if not topic or not session_data:
        return jsonify({'error': 'Parametros incompletos'}), 400

    if not TopicModel.topic_exists(current_user, topic):
        return jsonify({'error': 'Topico nao encontrado'}), 404

    data_dict = TopicModel._load_json_data(current_user, topic)

    if 'generated_questions_sessions' not in data_dict:
        data_dict['generated_questions_sessions'] = []

    data_dict['generated_questions_sessions'].append(session_data)

    TopicModel._save_json_data(current_user, topic, data_dict)

    return jsonify({'success': True})


@question_bp.route('/topic/<topic_name>/sessions', methods=['GET'])
@login_required
def get_sessions(topic_name):
    sessions = TopicModel.get_generated_sessions(current_user, topic_name)
    return jsonify(sessions)


@question_bp.route('/topic/<topic_name>/sessions/<int:session_idx>', methods=['PUT'])
@login_required
def update_session(topic_name, session_idx):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    updated = TopicModel.update_generated_session(current_user, topic_name, session_idx, data)
    if not updated:
        return jsonify({'error': 'Sessao nao encontrada'}), 404

    return jsonify({'success': True})


@question_bp.route('/topic/<topic_name>/sessions/<int:session_idx>', methods=['DELETE'])
@login_required
def delete_session(topic_name, session_idx):
    deleted = TopicModel.delete_generated_session(current_user, topic_name, session_idx)
    if not deleted:
        return jsonify({'error': 'Sessao nao encontrada'}), 404
    return jsonify({'success': True})


@question_bp.route('/suggest_prompts', methods=['POST'])
@login_required
@require_ollama_key
def suggest_prompts():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados invalidos'}), 400

    mode = data.get('mode', 'enhance_question')
    topic = data.get('topic')
    model = data.get('model') or Config.DEFAULT_MODEL

    contexto = data.get('context', '') or ''
    instrucoes = data.get('instrucoes', '') or ''
    _cache_modes = ('generate_questions', 'generate_flashcards', 'study_strategy', 'search_articles', 'flashcard_subjects')
    if mode not in _cache_modes:
        contexto = _contexto_sugestoes(
            current_user.id, topic, contexto, current_user.get_ollama_keys(), instrucoes
        )

    if mode == 'analyze_image':
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
        try:
            rag_resp = post_llm_api(
                "/suggest_prompts",
                json={
                    "mode": "analyze_image",
                    "context": contexto,
                    "question": data.get('question', ''),
                    "answer": '',
                    "explanation": '',
                    "model": model
                },
                timeout=60
            )
            if rag_resp.ok:
                suggestions = rag_resp.json().get('suggestions', [])
                if suggestions and len(suggestions) >= 3:
                    return jsonify({'success': True, 'suggestions': suggestions[:5]})
        except Exception as e:
            logger.exception(f"Erro ao gerar sugestoes (analyze_image): {e}")

        return jsonify({'success': True, 'suggestions': [
            "Corrija erros de OCR em palavras e números",
            "Foque em fórmulas matemáticas e equações",
            "Liste todas as alternativas das questões",
            "Preserve tabelas e listas no formato original",
            "Numere as questões na ordem em que aparecem"
        ]})

    if mode == 'annotation_insight':
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
        try:
            rag_resp = post_llm_api(
                "/suggest_prompts",
                json={
                    "mode": "annotation_insight",
                    "context": contexto,
                    "question": data.get('question', ''),
                    "answer": '',
                    "explanation": '',
                    "model": model
                },
                timeout=60
            )
            if rag_resp.ok:
                suggestions = rag_resp.json().get('suggestions', [])
                if suggestions and len(suggestions) >= 3:
                    return jsonify({'success': True, 'suggestions': suggestions[:5]})
        except Exception as e:
            logger.exception(f"Erro ao gerar sugestoes (annotation_insight): {e}")

        return jsonify({'success': True, 'suggestions': [
            "Resuma em tópicos os pontos principais",
            "Explique conceitos complexos com analogias",
            "Destaque tendências visuais em gráficos",
            "Relacione com exemplos práticos do dia a dia",
            "Sugira aplicações do tema"
        ]})

    if mode in _cache_modes:
        full_ctx = _contexto_completo_sugestoes(current_user.id, topic, data.get('context', ''), current_user.get_ollama_keys(), instrucoes)
        _ctx_hash = hash(full_ctx)
        _ckey = f"{mode}:{model}:{topic}:{_ctx_hash}"
        with _SUGESTAO_CACHE_LOCK:
            _entry = _SUGESTAO_CACHE.get(_ckey)
            if _entry and time.time() - _entry['ts'] < 300:
                logger.info(f"[sugestoes] Cache hit local para mode={mode} topic={topic} ctx_hash={_ctx_hash}")
                return jsonify({'success': True, 'suggestions': _entry['suggestions']})

        try:
            response = post_llm_api(
                "/suggest_prompts",
                json={
                    "mode": mode,
                    "context": full_ctx,
                    "question": data.get('question', ''),
                    "answer": '',
                    "explanation": '',
                    "model": model
                },
                timeout=20
            )
            if response.ok:
                suggestions = response.json().get('suggestions', [])
                if suggestions and len(suggestions) >= 3:
                    with _SUGESTAO_CACHE_LOCK:
                        _SUGESTAO_CACHE[_ckey] = {'ts': time.time(), 'suggestions': suggestions[:5]}
                    logger.info(f"[sugestoes] LLM gerou sugestões contextualizadas para mode={mode} topic={topic} ctx_hash={_ctx_hash}")
                    return jsonify({'success': True, 'suggestions': suggestions[:5]})
        except Exception as e:
            logger.warning(f"[sugestoes] LLM falhou, usando fallback: {e}")

        fb = _fallback_contextual(mode, topic, instrucoes)
        with _SUGESTAO_CACHE_LOCK:
            _SUGESTAO_CACHE[_ckey] = {'ts': time.time(), 'suggestions': fb}
        return jsonify({'success': True, 'suggestions': fb})

    image_filename = data.get('image_filename')
    q_idx = data.get('q_idx')
    enunciado = data.get('enunciado', '')
    resposta = data.get('resposta', '')
    explicacao = data.get('explicacao', '')

    if not topic or not image_filename or q_idx is None:
        return jsonify({'error': 'Parametros incompletos'}), 400

    user_id = current_user.id
    ollama_keys = current_user.get_ollama_keys()

    context_query = f"{enunciado} {resposta} {explicacao}"[:2000]
    retrieved_context = _get_retrieved_context(user_id, topic, context_query, 3, ollama_keys)

    has_context = bool(retrieved_context)
    contexto = retrieved_context if retrieved_context else enunciado

    if not has_context and len(contexto) < 20:
        contexto = f"Questão sobre {topic}"

    try:
        rag_resp = post_llm_api(
            "/suggest_prompts",
            json={
                "mode": "enhance_question",
                "context": contexto,
                "question": enunciado,
                "answer": resposta,
                "explanation": explicacao,
                "model": model
            },
            timeout=60
        )
        if rag_resp.ok:
            payload = rag_resp.json()
            suggestions = payload.get('suggestions', [])
            if suggestions and len(suggestions) >= 3:
                return jsonify({'success': True, 'suggestions': suggestions[:5]})

        logger.warning(
            f"Resposta inválida da rota /suggest_prompts: "
            f"{rag_resp.text if rag_resp else 'sem resposta'}"
        )
    except Exception as e:
        logger.exception(f"Erro ao gerar sugestoes de prompts: {e}")

    if has_context:
        fallback = [
            f"Explique mais detalhadamente usando o contexto: {contexto[:100]}...",
            "Inclua exemplos práticos relacionados ao tópico",
            "Detalhe o raciocínio passo a passo",
            "Corrija possíveis erros comuns neste tipo de questão",
            "Relacione com outros conceitos do tópico"
        ]
    elif enunciado and len(enunciado) > 20:
        fallback = [
            f"Explique o enunciado de forma mais simples: {enunciado[:80]}...",
            "Inclua exemplos práticos",
            "Detalhe o raciocínio passo a passo",
            "Corrija possíveis erros",
            "Relacione com outros conceitos"
        ]
    else:
        fallback = [
            "Explique de forma mais simples",
            "Inclua exemplos práticos",
            "Detalhe o raciocínio passo a passo",
            "Corrija possíveis erros",
            "Relacione com outros conceitos"
        ]
    return jsonify({'success': True, 'suggestions': fallback})