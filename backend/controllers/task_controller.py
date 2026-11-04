from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from types import SimpleNamespace
import os
import base64
import json as jsonlib
import logging
import requests
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import task_manager
from services.rag_client import retrieve_context, post_llm_api
from services.ollama_guard import require_ollama_key
from services.resposta_utils import extrair_resposta_da_explicacao
from services.analise_utils import texto_da_questao, aplicar_questao_texto
from services.questoes_existentes import listar_questoes_existentes
from services.json_modelo import carregar_json_do_modelo
from models.topic_model import TopicModel
from config import Config

logger = logging.getLogger(__name__)
task_bp = Blueprint('task', __name__)
RAG_URL = os.getenv('RAG_SERVICE_URL', Config.RAG_SERVICE_URL)
REFINEMENT_INTERACTIONS = Config.REFINEMENT_INTERACTIONS


def _snapshot(user):
    keys = []
    try:
        keys = user.get_ollama_keys()
    except Exception:
        keys = []
    return SimpleNamespace(
        id=user.id,
        username=user.username,
        get_ollama_keys=lambda: keys,
    )


def _get_retrieved_context(user_snap, topic, query, n_results=5):
    try:
        return retrieve_context(
            user_snap.id, topic, query, n_results,
            ollama_keys=user_snap.get_ollama_keys()
        )
    except Exception as e:
        logger.warning(f"Falha na recuperacao de contexto: {e}")
        return ""


def _verify_answer_with_context(context, question, answer, model=None, ollama_keys=None):
    try:
        resp = post_llm_api(
            "/verify_response",
            json={"context": context, "question": question, "answer": answer, "model": model},
            timeout=60,
            chaves=ollama_keys
        )
        if resp.ok:
            return resp.json().get("verified_answer", answer)
        return answer
    except Exception as e:
        logger.warning(f"Falha na verificacao: {e}")
        return answer


def _merge_subitems_into_question(questions):
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
                next_is_subitem = bool(re.match(r'^[IVXLCDM]+$', next_num.upper())) or bool(re.match(r'^[a-z]$', next_num.lower()))
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


def _worker_generate_questions(user_snap, topic, question_types, num_questions, custom_instructions, model, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=5, message='Preparando o material do tópico...')
    query_text = " ".join(t for t in (topic, custom_instructions) if t).strip()
    context_text = _get_retrieved_context(user_snap, topic, query_text, 14) or ""
    com_rag = len(context_text) >= 500
    if not com_rag:
        context_text = ""
        resolutions = TopicModel.get_resolutions(user_snap, topic)
        snippets = []
        for item in resolutions[:3]:
            for q in item.get('questoes', [])[:2]:
                snippets.append(q.get('enunciado', '')[:200])
        if snippets:
            context_text = "Algumas questoes do topico:\n" + "\n".join(snippets)
    MAX = 12000
    if len(context_text) > MAX:
        context_text = context_text[:MAX] + "\n... (contexto truncado)"
    payload = {
        'context': context_text,
        'question_types': question_types,
        'num_questions': num_questions,
        'custom_instructions': custom_instructions,
        'model': model,
        'subject': topic,
        'user_id': user_snap.id,
        'existing_questions': listar_questoes_existentes(user_snap, topic),
    }
    if task_id:
        task_manager.update_task(task_id, progress=35, message='Consultando o modelo de IA...')
    resp = post_llm_api("/generate_custom_questions", json=payload, timeout=900, chaves=[])
    resp.raise_for_status()
    result = resp.json()
    if not isinstance(result, dict):
        raise ValueError("Resposta invalida do servico de geracao")
    questions = result.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        raise ValueError("Servico de geracao nao retornou questoes")
    result["contexto"] = {
        "chars": len(context_text),
        "com_rag": com_rag,
        "insuficiente": len(context_text) < 3000,
        "instrucoes": custom_instructions,
    }
    if task_id:
        task_manager.update_task(task_id, progress=90, message='Organizando as questões...')
    return result


def _worker_generate_flashcards(user_snap, topic, subject, custom_instructions, model, max_flashcards, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=5, message='Preparando o material do tópico...')
    query_text = " ".join(t for t in (topic, subject, custom_instructions) if t).strip()
    context_text = _get_retrieved_context(user_snap, topic, query_text, 14) or ""
    com_rag = bool(context_text)
    if not context_text:
        resolutions = TopicModel.get_resolutions(user_snap, topic)
        snippets = []
        for item in resolutions[:3]:
            for q in item.get('questoes', [])[:2]:
                snippets.append(q.get('enunciado', '')[:200])
        if snippets:
            context_text = "Algumas questoes do topico:\n" + "\n".join(snippets)
    MAX = 12000
    if len(context_text) > MAX:
        context_text = context_text[:MAX] + "\n... (contexto truncado)"
    payload = {
        'context': context_text,
        'subject': subject or topic,
        'max_flashcards': max_flashcards,
        'custom_instructions': custom_instructions,
        'model': model,
    }
    if task_id:
        task_manager.update_task(task_id, progress=35, message='Consultando o modelo de IA...')
    resp = post_llm_api("/generate_flashcards", json=payload, timeout=900,
                        chaves=user_snap.get_ollama_keys())
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        data["contexto"] = {
            "chars": len(context_text),
            "com_rag": com_rag,
            "insuficiente": len(context_text) < 3000,
            "instrucoes": custom_instructions,
        }
    if task_id:
        task_manager.update_task(task_id, progress=90, message='Organizando os flashcards...')
    return data


def _worker_search_articles(user_snap, query, task_id=None):
    from controllers.article_controller import (
        search_crossref, search_arxiv, search_pubmed, search_semantic_scholar
    )
    if task_id:
        task_manager.update_task(task_id, progress=10, message='Refinando os termos de busca...')
    refined_query = query
    try:
        r = post_llm_api("/refine_search_query", json={"query": query}, timeout=30,
                         chaves=user_snap.get_ollama_keys())
        if r.ok:
            refined_query = r.json().get('refined_query', query)
    except Exception:
        pass
    all_results = []
    if task_id:
        task_manager.update_task(task_id, progress=40, message='Consultando as bases de dados...')
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [
            ex.submit(search_crossref, refined_query, 10),
            ex.submit(search_arxiv, refined_query, 10),
            ex.submit(search_pubmed, refined_query, 10),
            ex.submit(search_semantic_scholar, refined_query, 10),
        ]
        for f in as_completed(futs):
            try:
                r = f.result()
                if r:
                    all_results.extend(r)
            except Exception:
                pass
    seen = set()
    unique = []
    for r in all_results:
        k = r['title'].lower().strip()
        if k not in seen:
            seen.add(k)
            unique.append(r)
    if task_id:
        task_manager.update_task(task_id, progress=90, message='Organizando os resultados...')
    return {
        'success': True,
        'results': unique[:30],
        'refined_query': refined_query,
        'total_sources': 4,
    }


def _worker_analyze_full_document(user_snap, topic, model, extra_prompt, transcription_method, ocr_model=None, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=5, message='Preparando as páginas do tópico...')
    image_files = TopicModel.get_image_files(user_snap, topic)
    images_folder = TopicModel.get_images_folder(user_snap, topic)
    pages = []
    for filename in image_files:
        path = os.path.join(images_folder, filename)
        if not os.path.exists(path):
            continue
        with open(path, 'rb') as f:
            pages.append((filename, base64.b64encode(f.read()).decode('utf-8'), ""))

    todas = TopicModel.get_resolutions(user_snap, topic)
    for it in todas:
        if not isinstance(it, dict) or not it.get("is_text_question"):
            continue
        texto = texto_da_questao(it)
        if texto:
            pages.append((it.get("imagem"), "", texto))
    if not pages:
        raise ValueError("Nenhuma imagem encontrada neste topico")

    existing_map = {it.get("imagem"): it for it in todas if isinstance(it, dict)}
    for filename, _, _ in pages:
        if filename not in existing_map:
            new_item = {"imagem": filename, "questoes": []}
            todas.append(new_item)
            existing_map[filename] = new_item

    qtext = (extra_prompt or topic).strip() or topic
    rc = _get_retrieved_context(user_snap, topic, qtext, 5)
    base_context_texts = [f"[RAG_BASE]{rc}"] if rc and len(rc) >= 500 else []

    lock = threading.Lock()

    def process_page(item):
        filename, b64, texto_base = item
        item_ref = existing_map.get(filename)
        if item_ref is None:
            return filename, 0, False, "Item nao encontrado"

        payload = {
            'image_base64': b64,
            'model': model,
            'analysis_type': 'questions',
            'extra_prompt': extra_prompt or '',
            'transcription_method': transcription_method,
            'ocr_model': ocr_model,
            'context_images': [],
            'context_texts': list(base_context_texts),
            'output_format': 'structured',
            'input_text': texto_base,
        }

        last_error = None
        for attempt in range(REFINEMENT_INTERACTIONS):
            try:
                r = post_llm_api("/analyze_image", json=payload, timeout=900,
                                 chaves=user_snap.get_ollama_keys())
                if not r.ok:
                    last_error = f"HTTP {r.status_code}"
                    if attempt < REFINEMENT_INTERACTIONS - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return filename, 0, False, last_error
                dados = r.json()
                questoes = dados.get('questions', [])
                if not isinstance(questoes, list):
                    last_error = "Resposta invalida do servico"
                    if attempt < REFINEMENT_INTERACTIONS - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return filename, 0, False, last_error

                ctx_verify = " ".join(base_context_texts) if base_context_texts else ""
                if ctx_verify and len(ctx_verify) >= 200 and not texto_base:
                    for q in questoes:
                        if q.get('resposta') or q.get('explicacao'):
                            try:
                                vr = post_llm_api("/verify_response",
                                                   json={"context": ctx_verify,
                                                         "question": q.get('enunciado', ''),
                                                         "answer": q.get('explicacao', ''),
                                                         "model": model},
                                                   timeout=60,
                                                   chaves=user_snap.get_ollama_keys())
                                if vr.ok:
                                    q['explicacao'] = vr.json().get('verified_answer', q.get('explicacao', ''))
                            except Exception:
                                pass

                added_count = 0
                with lock:
                    if texto_base:
                        nova = next(
                            (q for q in questoes if (q.get('enunciado') or '').strip()),
                            None
                        )
                        if not nova:
                            return filename, 0, False, "Nenhuma questao retornada"
                        aplicar_questao_texto(item_ref, nova, texto_base)
                        return filename, 1, True, None

                    existentes = {q.get('questao'): q for q in item_ref['questoes']}
                    for nova in questoes:
                        num = str(nova.get('numero', '') or nova.get('questao', '')).strip()
                        if not num:
                            continue
                        if num in existentes:
                            ex = existentes[num]
                            if not ex.get('resposta') and nova.get('resposta'):
                                ex['resposta'] = nova['resposta']
                            if not ex.get('explicacao') and nova.get('explicacao'):
                                ex['explicacao'] = nova['explicacao']
                            if not ex.get('tipo') and nova.get('tipo'):
                                ex['tipo'] = nova['tipo']
                            if not ex.get('enunciado') and nova.get('enunciado'):
                                ex['enunciado'] = nova['enunciado']
                        else:
                            item_ref['questoes'].append({
                                "questao": num,
                                "tipo": nova.get('tipo', ''),
                                "resposta": nova.get('resposta', ''),
                                "explicacao": nova.get('explicacao', ''),
                                "enunciado": nova.get('enunciado', ''),
                                "whiteboard_img": None,
                            })
                            existentes[num] = item_ref['questoes'][-1]
                            added_count += 1

                return filename, added_count, True, None
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Tentativa {attempt+1} falhou para {filename}: {e}")
                if attempt < REFINEMENT_INTERACTIONS - 1:
                    time.sleep(2 ** attempt)

        logger.error(f"Falha definitiva ao processar {filename}: {last_error}")
        return filename, 0, False, last_error or "Erro desconhecido"

    total = 0
    failed = []
    processed = 0
    max_w = min(2, max(1, len(pages)))
    with ThreadPoolExecutor(max_workers=max_w) as ex:
        futures = {ex.submit(process_page, p): p[0] for p in pages}
        for fut in as_completed(futures):
            try:
                fn, count, ok, err = fut.result()
                processed += 1
                if task_id:
                    task_manager.update_task(
                        task_id,
                        progress=10 + int(80 * processed / max(1, len(pages))),
                        message=f'Página {processed} de {len(pages)} processada'
                    )
                if ok:
                    total += count
                else:
                    failed.append(fn)
            except Exception as e:
                logger.exception(f"Erro critico em worker de pagina: {e}")
                fn = futures.get(fut, "unknown")
                failed.append(fn)

    TopicModel.save_resolutions(user_snap, topic, todas)

    pages_with_questions = sum(
        1 for it in todas if isinstance(it, dict) and it.get("questoes")
    )

    return {
        'success': True,
        'count': total,
        'pages_processed': processed,
        'pages_total': len(pages),
        'pages_with_questions': pages_with_questions,
        'failed_pages': failed,
    }


def _worker_analyze_with_image(user_snap, topic, image_filename, model, extra_prompt, transcription_method, temperature=None, ocr_model=None, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=10, message='Lendo a página...')
    images_folder = TopicModel.get_images_folder(user_snap, topic)
    image_path = os.path.join(images_folder, image_filename)
    resolutions = TopicModel.get_resolutions(user_snap, topic)
    item_texto = next((it for it in resolutions if it.get("imagem") == image_filename), None)
    image_b64 = ""
    texto_base = ""
    if os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
    else:
        if not item_texto or not item_texto.get("is_text_question"):
            raise ValueError("Imagem nao encontrada")
        texto_base = texto_da_questao(item_texto)
        if not texto_base:
            raise ValueError("Imagem nao encontrada")

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
                    wb = q.get('whiteboard_img')
                    if wb:
                        wb_folder = TopicModel.get_whiteboards_folder(user_snap, topic)
                        wb_path = os.path.join(wb_folder, wb)
                        if os.path.exists(wb_path):
                            with open(wb_path, 'rb') as f:
                                context_images.append(base64.b64encode(f.read()).decode('utf-8'))
                break

    ocr_text = texto_base or " ".join(context_texts)
    query_text = ocr_text + " " + (extra_prompt or "")
    rc = _get_retrieved_context(user_snap, topic, query_text, 5)

    payload = {
        'image_base64': image_b64,
        'model': model,
        'analysis_type': 'questions',
        'extra_prompt': extra_prompt or '',
        'transcription_method': transcription_method,
        'ocr_model': ocr_model,
        'context_images': context_images,
        'context_texts': context_texts + ([f"[RAG_BASE]{rc}"] if rc and len(rc) >= 500 else []),
        'output_format': 'structured',
        'input_text': texto_base,
    }

    if temperature is not None:
        payload['temperature'] = temperature

    if task_id:
        task_manager.update_task(task_id, progress=40, message='Enviando para o modelo de IA...')
    r = post_llm_api("/analyze_image", json=payload, timeout=900,
                     chaves=user_snap.get_ollama_keys())
    if not r.ok:
        detalhe = ""
        try:
            detalhe = str((r.json() or {}).get("detail") or "")
        except Exception:
            detalhe = ""
        raise ValueError(detalhe or "Falha no servico de analise de imagem")
    dados = r.json()
    questoes = dados.get('questions', [])
    if not isinstance(questoes, list):
        raise ValueError("Resposta invalida do servico de analise")

    if not texto_base:
        ctx_verify = " ".join(payload['context_texts'])
        for q in questoes:
            if q.get('resposta') or q.get('explicacao'):
                q['explicacao'] = _verify_answer_with_context(
                    ctx_verify, q.get('enunciado', ''), q.get('explicacao', ''), model,
                    ollama_keys=user_snap.get_ollama_keys()
                )

    questoes = _merge_subitems_into_question(questoes)

    if texto_base:
        nova = next((q for q in questoes if (q.get('enunciado') or '').strip()), None)
        if not nova:
            raise ValueError("Nao foi possivel analisar a questao")
        aplicar_questao_texto(item_texto, nova, texto_base)
        TopicModel.save_resolutions(user_snap, topic, resolutions)
        return {'success': True, 'count': 1, 'questions': item_texto['questoes']}

    todas = TopicModel.get_resolutions(user_snap, topic)
    item = next((it for it in todas if it.get("imagem") == image_filename), None)
    if not item:
        item = {"imagem": image_filename, "questoes": []}
        todas.append(item)

    existentes = {q['questao']: q for q in item['questoes']}
    for nova in questoes:
        num = str(nova.get('numero', ''))
        if not num:
            continue
        if num in existentes:
            ex = existentes[num]
            if not ex.get('resposta') and nova.get('resposta'):
                ex['resposta'] = nova['resposta']
            if not ex.get('explicacao') and nova.get('explicacao'):
                ex['explicacao'] = nova['explicacao']
            if not ex.get('tipo') and nova.get('tipo'):
                ex['tipo'] = nova['tipo']
            if not ex.get('enunciado') and nova.get('enunciado'):
                ex['enunciado'] = nova['enunciado']
        else:
            item['questoes'].append({
                "questao": num,
                "tipo": nova.get('tipo', ''),
                "resposta": nova.get('resposta', ''),
                "explicacao": nova.get('explicacao', ''),
                "enunciado": nova.get('enunciado', ''),
                "whiteboard_img": None,
            })
    TopicModel.save_resolutions(user_snap, topic, todas)
    return {'success': True, 'count': len(questoes), 'questions': item['questoes']}


def _worker_analyze_image_insight(user_snap, topic, image_filename, model, extra_prompt, transcription_method, ocr_model=None, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=10, message='Lendo a página...')
    images_folder = TopicModel.get_images_folder(user_snap, topic)
    image_path = os.path.join(images_folder, image_filename)
    image_b64 = ""
    texto_base = ""
    if os.path.exists(image_path):
        with open(image_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
    else:
        resolutions = TopicModel.get_resolutions(user_snap, topic)
        item = next((it for it in resolutions if it.get("imagem") == image_filename), None)
        if not item or not item.get("is_text_question"):
            raise ValueError("Imagem nao encontrada")
        texto_base = texto_da_questao(item)
        if not texto_base:
            raise ValueError("Imagem nao encontrada")
    payload = {
        'image_base64': image_b64,
        'model': model,
        'analysis_type': 'insight',
        'extra_prompt': extra_prompt or '',
        'transcription_method': transcription_method,
        'ocr_model': ocr_model,
        'input_text': texto_base,
    }
    if task_id:
        task_manager.update_task(task_id, progress=40, message='Enviando para o modelo de IA...')
    r = post_llm_api("/analyze_image_insight", json=payload, timeout=600,
                     chaves=user_snap.get_ollama_keys())
    if not r.ok:
        raise ValueError("Falha no servico de insight")
    dados = r.json()
    return {'success': True, 'insight': dados.get('insight', ''), 'image_filename': image_filename}


def _worker_enhance_question(user_snap, topic, image_filename, q_idx, enunciado, explicacao, resposta, custom_prompt, model, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=10, message='Preparando o contexto da questão...')
    query_text = enunciado if enunciado else f"Questao {q_idx}"
    rc = _get_retrieved_context(user_snap, topic, query_text, 3)
    if rc and len(rc) > 200:
        exemplo_texto = "\n\n**Contexto adicional do topico (recuperado):**\n" + rc + "\n"
    else:
        exemplo_texto = "\n\n**Contexto adicional do topico (recuperado):**\nNenhum contexto adicional disponivel. Use seu conhecimento geral e, ao final, sugira pesquisas para enriquecer o material.\n"

    exemplos = []
    try:
        r = requests.post(f"{RAG_URL}/retrieve_examples",
                          json={"query": query_text, "n_results": 2,
                                "user_id": user_snap.id}, timeout=10)
        if r.ok:
            exemplos = r.json().get("examples", [])
    except Exception as e:
        logger.warning(f"Falha ao recuperar exemplos: {e}")

    if exemplos:
        exemplo_texto += "\n\n**Exemplos de resolucoes anteriores (use como referencia):**\n"
        for ex in exemplos:
            exemplo_texto += f"\n--- Exemplo ---\n"
            exemplo_texto += f"Enunciado: {ex.get('enunciado', '')}\n"
            exemplo_texto += f"Resposta: {ex.get('resposta', '')}\n"
            exemplo_texto += f"Explicacao: {ex.get('explicacao', '')}\n"

    consulta = f"Enunciado: {enunciado}\nResposta: {resposta}\nExplicacao atual: {explicacao}"
    if custom_prompt:
        consulta += f"\n\nInstrucoes adicionais: {custom_prompt}"
    else:
        consulta += "\n\nPor favor, melhore a explicacao acima, tornando-a mais clara, detalhada e didatica. Inclua raciocinio passo a passo e auto-verificacao."

    consulta += ("\n\nEscreva a nova explicacao comecando pela linha '**Resposta:** <resposta>' e "
                 "terminando pela linha '**Resposta final:** <resposta>', com o mesmo valor nas duas "
                 "linhas e desenvolvendo a resolucao entre elas. Se a resposta mudar em relacao a "
                 "informada acima, atualize as duas linhas.")

    if not rc or len(rc) < 200:
        consulta += "\n\nATENCAO: O contexto disponivel e muito limitado. Mesmo assim, tente dar uma resposta baseada no seu conhecimento geral. Apos a resposta, indique claramente que o contexto e insuficiente e sugira termos de busca e tipos de documentos que o usuario poderia adicionar para melhorar futuras respostas."

    consulta_completa = exemplo_texto + "\n\n" + consulta
    if task_id:
        task_manager.update_task(task_id, progress=40, message='Melhorando a explicação com o modelo de IA...')
    r = post_llm_api("/generate",
                      json={'question_text': consulta_completa, 'model': model,
                            'user_id': user_snap.id},
                      timeout=(10, 300),
                      chaves=user_snap.get_ollama_keys())
    if not r.ok:
        raise ValueError("Falha no servico RAG")
    dados = r.json()
    nova_explicacao = dados['explanation']
    if rc and len(rc) >= 200:
        context_for_verify = exemplo_texto + "\n" + consulta
        nova_explicacao = _verify_answer_with_context(context_for_verify, query_text, nova_explicacao, model,
                                                      ollama_keys=user_snap.get_ollama_keys())

    resolutions = TopicModel.get_resolutions(user_snap, topic)
    nova_resposta = extrair_resposta_da_explicacao(nova_explicacao, resposta)
    for item in resolutions:
        if item.get('imagem') == image_filename:
            if 0 <= q_idx < len(item['questoes']):
                item['questoes'][q_idx]['explicacao'] = nova_explicacao
                if nova_resposta and nova_resposta != resposta:
                    item['questoes'][q_idx]['resposta'] = nova_resposta
                if enunciado:
                    item['questoes'][q_idx]['enunciado'] = enunciado
                TopicModel.save_resolutions(user_snap, topic, resolutions)
                return {
                    'success': True,
                    'explicacao': nova_explicacao,
                    'resposta': nova_resposta,
                    'image_filename': image_filename,
                    'q_idx': q_idx,
                }
    raise ValueError("Questao nao encontrada")


def _worker_study_strategy(user_snap, topic, dedication, task_id=None):
    if task_id:
        task_manager.update_task(task_id, progress=10, message='Reunindo o conteúdo do tópico...')
    context = TopicModel.get_all_topic_content(user_snap, topic)
    query_text = (dedication.get('custom_instructions', '') or '') + " conteudo do topico para estudo"
    rc = _get_retrieved_context(user_snap, topic, query_text, 8)
    if rc:
        context = rc + "\n\n" + context

    if task_id:
        task_manager.update_task(task_id, progress=40, message='Gerando a estratégia com o modelo de IA...')
    r = post_llm_api("/recommend_study_strategy",
                      json={"context": context, "dedication": dedication, "topic_name": topic},
                      timeout=(10, 300),
                      chaves=user_snap.get_ollama_keys())
    if not r.ok:
        raise ValueError(f"Falha ao gerar estrategia: {(r.text or '')[:300]}")
    strategy = r.json()
    strategy_text = jsonlib.dumps(strategy, ensure_ascii=False)
    if task_id:
        task_manager.update_task(task_id, progress=85, message='Verificando a estratégia gerada...')
    verified = _verify_answer_with_context(context, query_text, strategy_text, model=None,
                                           ollama_keys=user_snap.get_ollama_keys())
    verified_strategy = carregar_json_do_modelo(verified)
    if verified_strategy is None:
        verified_strategy = strategy
    TopicModel.set_study_strategy(user_snap, topic, verified_strategy)
    if isinstance(verified_strategy, dict):
        verified_strategy['contexto'] = {
            'chars': len(context),
            'com_rag': bool(rc),
            'insuficiente': len(context) < 3000,
            'instrucoes': dedication.get('custom_instructions', ''),
        }
    return verified_strategy


def _worker_suggest_prompts(user_snap, topic, image_filename, q_idx, enunciado, resposta, explicacao, model):
    context_query = f"{enunciado} {resposta} {explicacao}"[:2000]
    rc = _get_retrieved_context(user_snap, topic, context_query, 3)
    has_context = bool(rc)
    contexto = rc if rc else enunciado
    if not has_context and len(contexto) < 20:
        contexto = f"Questão sobre {topic}"

    try:
        r = post_llm_api("/suggest_prompts",
                          json={"context": contexto, "question": enunciado, "answer": resposta,
                                "explanation": explicacao, "model": model},
                          timeout=60,
                          chaves=user_snap.get_ollama_keys())
        if r.ok:
            data = r.json()
            suggestions = data.get('suggestions', [])
            if suggestions and len(suggestions) >= 3:
                return {'success': True, 'suggestions': suggestions[:5]}
    except Exception as e:
        logger.exception(f"Erro ao gerar sugestoes: {e}")

    if has_context:
        fallback = [
            f"Explique mais detalhadamente usando o contexto: {contexto[:100]}...",
            "Inclua exemplos práticos relacionados ao tópico",
            "Detalhe o raciocínio passo a passo",
            "Corrija possíveis erros comuns neste tipo de questão",
            "Relacione com outros conceitos do tópico"
        ]
    else:
        fallback = [
            "Explique de forma mais simples",
            "Inclua exemplos práticos",
            "Detalhe o raciocínio passo a passo",
            "Corrija possíveis erros",
            "Relacione com outros conceitos"
        ]
    return {'success': True, 'suggestions': fallback}


def _chave_dedup(tipo, params):
    topico = params.get('topic') or params.get('topic_name') or ''
    if tipo == 'search_articles':
        return (params.get('query') or '').strip().lower()
    if tipo in ('analyze_with_image', 'analyze_image_insight'):
        return f"{topico}|{params.get('image_filename') or ''}"
    if tipo == 'enhance_question':
        return f"{topico}|{params.get('image_filename') or ''}|{params.get('q_idx', 0)}"
    if tipo == 'suggest_prompts':
        return f"{topico}|{params.get('image_filename') or ''}|{params.get('q_idx', 0)}"
    return topico


@task_bp.route('/tasks', methods=['GET'])
@login_required
def list_tasks():
    return jsonify(task_manager.list_user_tasks(current_user.id))


@task_bp.route('/tasks/<task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    t = task_manager.get_task(task_id)
    if not t or t['user_id'] != current_user.id:
        return jsonify({'error': 'Task não encontrada'}), 404
    return jsonify(t)


@task_bp.route('/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    t = task_manager.get_task(task_id)
    if not t or t['user_id'] != current_user.id:
        return jsonify({'error': 'Task não encontrada'}), 404
    task_manager.delete_task(task_id)
    return jsonify({'success': True})


@task_bp.route('/tasks/start', methods=['POST'])
@login_required
@require_ollama_key
def start_task():
    data = request.get_json(silent=True) or {}
    task_type = data.get('type')
    params = data.get('params', {}) or {}
    user_snap = _snapshot(current_user)
    user_id = current_user.id

    if task_type == 'generate_questions':
        tid, repetida = task_manager.create_task('generate_questions', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_generate_questions, user_snap,
                params.get('topic'),
                params.get('question_types', ['objetiva', 'aberta', 'vf']),
                params.get('num_questions', 10),
                params.get('custom_instructions', ''),
                params.get('model'),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'generate_flashcards':
        tid, repetida = task_manager.create_task('generate_flashcards', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_generate_flashcards, user_snap,
                params.get('topic'),
                params.get('subject', ''),
                params.get('custom_instructions', ''),
                params.get('model'),
                params.get('max_flashcards', 12),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'search_articles':
        tid, repetida = task_manager.create_task('search_articles', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_search_articles, user_snap,
                params.get('query', ''),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'analyze_full_document':
        tid, repetida = task_manager.create_task('analyze_full_document', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_analyze_full_document, user_snap,
                params.get('topic'),
                params.get('model'),
                params.get('extra_prompt', ''),
                params.get('transcription_method', 'tesseract'),
                params.get('ocr_model'),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'analyze_with_image':
        tid, repetida = task_manager.create_task('analyze_with_image', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_analyze_with_image, user_snap,
                params.get('topic'),
                params.get('image_filename'),
                params.get('model'),
                params.get('extra_prompt', ''),
                params.get('transcription_method', 'tesseract'),
                params.get('temperature'),
                params.get('ocr_model'),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'analyze_image_insight':
        tid, repetida = task_manager.create_task('analyze_image_insight', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_analyze_image_insight, user_snap,
                params.get('topic'),
                params.get('image_filename'),
                params.get('model'),
                params.get('extra_prompt', ''),
                params.get('transcription_method', 'tesseract'),
                params.get('ocr_model'),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'enhance_question':
        tid, repetida = task_manager.create_task('enhance_question', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_enhance_question, user_snap,
                params.get('topic'),
                params.get('image_filename'),
                params.get('q_idx', 0),
                params.get('enunciado', ''),
                params.get('explicacao', ''),
                params.get('resposta', ''),
                params.get('custom_prompt', ''),
                params.get('model'),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'study_strategy':
        tid, repetida = task_manager.create_task('study_strategy', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_study_strategy, user_snap,
                params.get('topic'),
                params.get('dedication', {}),
                task_id=tid)
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    if task_type == 'suggest_prompts':
        tid, repetida = task_manager.create_task('suggest_prompts', user_id, params, dedup_key=_chave_dedup(task_type, params))
        if not repetida:
            task_manager.run_async(tid, _worker_suggest_prompts, user_snap,
                params.get('topic'),
                params.get('image_filename'),
                params.get('q_idx', 0),
                params.get('enunciado', ''),
                params.get('resposta', ''),
                params.get('explicacao', ''),
                params.get('model'))
        return jsonify({'success': True, 'task_id': tid, 'reused': repetida})

    return jsonify({'error': 'Tipo de tarefa desconhecido'}), 400