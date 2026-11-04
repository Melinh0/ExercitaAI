from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from models.topic_model import TopicModel
from services.rag_client import (
    retrieve_context, remove_topic_vectors, rename_topic_vectors, post_llm_api
)
from services.ollama_guard import get_user_ollama_keys
from services.json_modelo import carregar_json_do_modelo
from utils.markdown import markdown_to_html
from flask_login import login_required, current_user
import os
import logging
import requests
from config import Config
import uuid
import json as jsonlib

topic_bp = Blueprint('topic', __name__)
logger = logging.getLogger(__name__)

def _get_retrieved_context(topic, query, n_results=5):
    try:
        retrieved = retrieve_context(current_user.id, topic, query, n_results)
        if retrieved:
            return retrieved
    except Exception as e:
        print(f"Falha na recuperação de contexto: {e}")
    return None

def _verify_answer_with_context(context, question, answer, model=None):
    try:
        resp = post_llm_api(
            "/verify_response",
            json={"context": context, "question": question, "answer": answer, "model": model},
            timeout=(10, 300)
        )
        if resp.ok:
            return resp.json().get("verified_answer", answer)
        return answer
    except Exception as e:
        print(f"Falha na verificação: {e}")
        return answer

@topic_bp.route('/')
@login_required
def home():
    topics = TopicModel.list_topics(current_user)
    if request.accept_mimetypes.accept_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(topics)
    return render_template('topics.html', topicos=topics)

@topic_bp.route('/topic/novo', methods=['GET', 'POST'])
@login_required
def novo_topic():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            if request.accept_mimetypes.accept_json:
                return jsonify({'success': False, 'error': 'Nome do tópico é obrigatório.'}), 400
            flash('Nome do tópico é obrigatório.', 'error')
            return redirect(url_for('topic.novo_topic'))
        safe_name = TopicModel.create_topic(current_user, nome)
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': True, 'topic': safe_name})
        flash(f'Tópico "{nome}" criado com sucesso!', 'success')
        return redirect(url_for('topic.ver_topic', topic_name=safe_name))
    return render_template('novo_topic.html')

@topic_bp.route('/topic/<topic_name>')
@login_required
def ver_topic(topic_name):
    images_folder = TopicModel.get_images_folder(current_user, topic_name)
    if not os.path.exists(images_folder):
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Tópico não encontrado.'}), 404
        flash('Tópico não encontrado.', 'error')
        return redirect(url_for('topic.home'))

    image_files = TopicModel.get_image_files(current_user, topic_name)
    resolutions = TopicModel.get_resolutions(current_user, topic_name)

    if request.accept_mimetypes.accept_json:
        return jsonify({
            'image_files': image_files,
            'resolutions': resolutions
        })

    try:
        idx = int(request.args.get('idx', 0))
    except ValueError:
        idx = 0
    idx = max(0, min(idx, len(image_files)-1)) if image_files else 0
    current_img = image_files[idx] if image_files else None

    try:
        q_idx = int(request.args.get('q', 0))
    except ValueError:
        q_idx = 0

    res_data = None
    if current_img:
        res_data = next((item for item in resolutions if item.get("imagem") == current_img), None)

    questoes = res_data.get("questoes", []) if res_data else []

    if questoes:
        q_idx = max(0, min(q_idx, len(questoes)-1))
    else:
        q_idx = 0

    current_questao = None
    if questoes and q_idx < len(questoes):
        current_questao = questoes[q_idx].copy()
        current_questao['explicacao_html'] = markdown_to_html(current_questao.get('explicacao', ''))
        whiteboard_img = current_questao.get('whiteboard_img')
        if whiteboard_img:
            current_questao['whiteboard_url'] = url_for('static', filename=f'whiteboards/topics/{topic_name}/{whiteboard_img}')
        else:
            current_questao['whiteboard_url'] = None

    imagens_no_json = [item.get("imagem") for item in resolutions if isinstance(item, dict)]

    return render_template(
        'index.html',
        topic=topic_name,
        image_files=image_files,
        current_img=current_img,
        current_idx=idx,
        total=len(image_files),
        questoes=questoes,
        q_idx=q_idx,
        current_questao=current_questao,
        imagens_no_json=imagens_no_json,
    )

@topic_bp.route('/topic/<old_name>/rename', methods=['POST'])
@login_required
def rename_topic(old_name):
    new_name = request.form.get('new_name', '').strip()
    if not new_name:
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': 'O novo nome não pode estar vazio.'}), 400
        flash('O novo nome não pode estar vazio.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=old_name))

    safe_old = TopicModel.sanitize_topic_name(old_name)
    safe_new = TopicModel.sanitize_topic_name(new_name)

    if safe_old == safe_new:
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': 'O novo nome é igual ao atual.'}), 400
        flash('O novo nome é igual ao atual.', 'info')
        return redirect(url_for('topic.ver_topic', topic_name=old_name))

    if TopicModel.topic_exists(current_user, safe_new):
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': 'Já existe um tópico com este nome.'}), 400
        flash('Já existe um tópico com este nome.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=old_name))

    success, message = TopicModel.rename_topic(current_user, safe_old, safe_new)
    if success:
        try:
            if not rename_topic_vectors(
                safe_old, safe_new, user_id=current_user.id
            ):
                logger.warning(
                    f"Vetores do tópico '{safe_old}' não foram migrados "
                    f"para '{safe_new}'."
                )
        except Exception as e:
            logger.warning(f"Falha ao migrar vetores após renomear: {e}")
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': True, 'new_name': safe_new})
        flash(f'Tópico renomeado para "{new_name}" com sucesso!', 'success')
        return redirect(url_for('topic.ver_topic', topic_name=safe_new))
    else:
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': message}), 500
        flash(f'Erro ao renomear: {message}', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=old_name))

@topic_bp.route('/topic/<topic_name>/delete_image/<path:filename>', methods=['POST'])
@login_required
def delete_image(topic_name, filename):
    is_text_question = filename.startswith('text_question_')

    if not is_text_question:
        images_folder = TopicModel.get_images_folder(current_user, topic_name)
        filepath = os.path.join(images_folder, filename)
        if not os.path.exists(filepath):
            if request.accept_mimetypes.accept_json:
                return jsonify({'success': False, 'error': 'Arquivo não encontrado.'}), 404
            flash('Arquivo não encontrado.', 'error')
            return redirect(url_for('topic.ver_topic', topic_name=topic_name))

    try:
        if not is_text_question:
            os.remove(filepath)

        resolutions = TopicModel.get_resolutions(current_user, topic_name)
        new_resolutions = [item for item in resolutions if item.get("imagem") != filename]
        TopicModel.save_resolutions(current_user, topic_name, new_resolutions)

        if not is_text_question:
            try:
                remove_topic_vectors(
                    topic_name, user_id=current_user.id, source=filename
                )
            except Exception as e:
                logger.warning(f"Falha ao remover vetores da imagem: {e}")

        if not is_text_question:
            whiteboard_folder = TopicModel.get_whiteboards_folder(current_user, topic_name)
            if os.path.isdir(whiteboard_folder):
                for item in os.listdir(whiteboard_folder):
                    if filename in item:
                        whiteboard_path = os.path.join(whiteboard_folder, item)
                        try:
                            if os.path.isfile(whiteboard_path):
                                os.remove(whiteboard_path)
                        except Exception as e:
                            print(f"Erro ao remover whiteboard {whiteboard_path}: {e}")

        if request.accept_mimetypes.accept_json:
            return jsonify({'success': True})
        flash('Imagem deletada com sucesso!', 'success')

    except PermissionError:
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': 'Permissão negada para deletar o arquivo.'}), 500
        flash('Permissão negada para deletar o arquivo.', 'error')
    except Exception as e:
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Erro ao deletar imagem: {str(e)}', 'error')

    return redirect(url_for('topic.ver_topic', topic_name=topic_name))

@topic_bp.route('/topic/<topic_name>/delete', methods=['POST'])
@login_required
def delete_topic(topic_name):
    import shutil
    import os
    from models.topic_model import TopicModel
    from flask import jsonify

    try:
        pastas = [
            TopicModel.get_images_folder(current_user, topic_name),
            TopicModel.get_whiteboards_folder(current_user, topic_name),
            TopicModel.get_questions_folder(current_user, topic_name),
            TopicModel.get_material_folder(current_user, topic_name),
        ]

        for folder in pastas:
            if folder and os.path.exists(folder):
                shutil.rmtree(folder)

        TopicModel.delete_topic(current_user, topic_name)

        try:
            if not remove_topic_vectors(topic_name, user_id=current_user.id):
                logger.warning(
                    f"Vetores do tópico '{topic_name}' não foram removidos "
                    f"do índice."
                )
        except Exception as e:
            logger.warning(f"Falha ao remover vetores do tópico: {e}")

        return jsonify({'success': True, 'message': f'Tópico "{topic_name}" removido com sucesso.'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@topic_bp.route('/topic/<topic_name>/study_strategy', methods=['POST'])
@login_required
def generate_study_strategy(topic_name):
    data = request.get_json() or {}
    acao = data.get('action')
    if acao == 'salvar_historico':
        estrategia = data.get('estrategia') or TopicModel.get_study_strategy(current_user, topic_name)
        if not estrategia:
            return jsonify({'success': False, 'error': 'Nenhuma estratégia para salvar no histórico.'}), 400
        historico = TopicModel.adicionar_estrategia_no_historico(
            TopicModel.get_study_strategy_history(current_user, topic_name), estrategia
        )
        TopicModel.set_study_strategy_history(current_user, topic_name, historico)
        return jsonify({'success': True})
    if acao == 'restaurar_estrategia':
        historico = TopicModel.get_study_strategy_history(current_user, topic_name)
        indice = data.get('indice')
        if not isinstance(indice, int) or not 0 <= indice < len(historico):
            return jsonify({'success': False, 'error': 'Posição inválida no histórico.'}), 400
        estrategia = historico[indice].get('estrategia')
        TopicModel.set_study_strategy(current_user, topic_name, estrategia, salvar_historico=False)
        return jsonify(estrategia)
    if acao == 'remover_historico':
        historico = TopicModel.get_study_strategy_history(current_user, topic_name)
        indice = data.get('indice')
        if not isinstance(indice, int) or not 0 <= indice < len(historico):
            return jsonify({'success': False, 'error': 'Posição inválida no histórico.'}), 400
        del historico[indice]
        TopicModel.set_study_strategy_history(current_user, topic_name, historico)
        return jsonify({'success': True})
    if not get_user_ollama_keys():
        return jsonify({
            'success': False,
            'error': (
                'Nenhuma chave de API cadastrada para este usuário. '
                'Cadastre uma chave do Ollama ou de outro provedor em '
                'Configurações para usar os recursos de IA.'
            ),
            'error_code': 'missing_ollama_key',
        }), 403
    dedication = data.get('dedication', {})
    subject = dedication.get('subject', '').strip() or topic_name
    context = TopicModel.get_all_topic_content(current_user, topic_name)
    query_text = " ".join(t for t in (subject, dedication.get('custom_instructions', ''), "conteudo do topico para estudo") if t).strip()
    retrieved_context = _get_retrieved_context(current_user.id, topic_name, query_text, 8, current_user.get_ollama_keys())
    if retrieved_context:
        context = retrieved_context + "\n\n" + context
    try:
        resp = post_llm_api(
            "/recommend_study_strategy",
            json={
                "context": context,
                "dedication": dedication,
                "topic_name": topic_name
            },
            timeout=(10, 180)
        )
        if resp.ok:
            strategy = resp.json()
            strategy_text = jsonlib.dumps(strategy)
            verified = _verify_answer_with_context(context, query_text, strategy_text, model=None)
            verified_strategy = carregar_json_do_modelo(verified)
            if verified_strategy is None:
                verified_strategy = strategy
            TopicModel.set_study_strategy(current_user, topic_name, verified_strategy)
            return jsonify(verified_strategy)
        else:
            return jsonify({
                'error': 'Falha ao gerar estrategia',
                'detail': (resp.text or '')[:400]
            }), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@topic_bp.route('/topic/<topic_name>/study_strategy', methods=['GET'])
@login_required
def get_study_strategy(topic_name):
    if request.args.get('historico') == '1':
        return jsonify({
            'historico': TopicModel.get_study_strategy_history(current_user, topic_name)
        })
    strategy = TopicModel.get_study_strategy(current_user, topic_name)
    if strategy:
        return jsonify(strategy)
    return jsonify({'error': 'Nenhuma estratégia encontrada para este tópico.'}), 404

@topic_bp.route('/topic/<topic_name>/image/<filename>')
@login_required
def serve_topic_image(topic_name, filename):
    images_folder = TopicModel.get_images_folder(current_user, topic_name)
    filepath = os.path.join(images_folder, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Imagem nao encontrada'}), 404
    return send_file(filepath, mimetype='image/png')

@topic_bp.route('/topic/<topic_name>/add_text_question', methods=['POST'])
@login_required
def add_text_question(topic_name):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Dados inválidos'}), 400

    text = data.get('text', '')
    type_q = data.get('type', '')
    correct_answer = data.get('correct_answer', '')
    explanation = data.get('explanation', '')

    if not text:
        return jsonify({'success': False, 'error': 'Texto da questão é obrigatório.'}), 400

    image_id = f"text_question_{uuid.uuid4().hex[:8]}"
    new_item = {
        "imagem": image_id,
        "is_text_question": True,
        "texto": text,
        "questoes": []
    }
    if data.get('fonte') == 'gerador':
        new_item['fonte'] = 'gerador'

    questao = {
        "questao": "1",
        "tipo": type_q,
        "resposta": correct_answer,
        "explicacao": explanation,
        "enunciado": text,
        "whiteboard_img": None
    }

    new_item["questoes"].append(questao)

    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    resolutions.append(new_item)
    TopicModel.save_resolutions(current_user, topic_name, resolutions)

    return jsonify({'success': True, 'image_id': image_id})


@topic_bp.route('/topic/<topic_name>/add_text_questions', methods=['POST'])
@login_required
def add_text_questions(topic_name):
    data = request.get_json() or {}
    questions = data.get('questions')
    if not isinstance(questions, list) or not questions:
        return jsonify({'success': False, 'error': 'Nenhuma questão enviada.'}), 400

    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    criadas = []

    for item in questions:
        text = (item.get('text') or '').strip()
        if not text:
            continue
        image_id = f"text_question_{uuid.uuid4().hex[:8]}"
        novo_item = {
            "imagem": image_id,
            "is_text_question": True,
            "texto": text,
            "questoes": [
                {
                    "questao": "1",
                    "tipo": item.get('type', ''),
                    "resposta": item.get('correct_answer', ''),
                    "explicacao": item.get('explanation', ''),
                    "enunciado": text,
                    "whiteboard_img": None
                }
            ]
        }
        if item.get('fonte') == 'gerador':
            novo_item['fonte'] = 'gerador'
        resolutions.append(novo_item)
        criadas.append(image_id)

    if not criadas:
        return jsonify({'success': False, 'error': 'Nenhuma questão válida enviada.'}), 400

    TopicModel.save_resolutions(current_user, topic_name, resolutions)

    return jsonify({'success': True, 'image_ids': criadas, 'count': len(criadas)})