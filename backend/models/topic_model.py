import functools
import os
import json
import re
import shutil
import sqlite3
import threading
from flask import current_app
from datetime import datetime
from werkzeug.exceptions import BadRequest

from models.user_model import db, User
from models.topic_tables import (
    Topic,
    TopicImage,
    QuestionRow,
    TopicNote,
    TopicSession,
    TopicStrategy,
)

_travas_topicos = {}
_travas_registro = threading.Lock()

CAMPOS_ITEM = {'imagem', 'questoes', 'data', 'is_text_question', 'texto'}
CAMPOS_PERGUNTA = {
    'questao', 'tipo', 'resposta', 'explicacao', 'whiteboard_img', 'enunciado',
}
CAMPOS_NOTA = {'id', 'image_filename', 'text', 'timestamp'}
CAMPOS_TOPICO = {'items', 'notes', 'study_strategy', 'generated_questions_sessions'}


def _trava_do_topico(caminho):
    with _travas_registro:
        trava = _travas_topicos.get(caminho)
        if trava is None:
            trava = threading.RLock()
            _travas_topicos[caminho] = trava
        return trava


def com_trava_de_topico(funcao):
    @functools.wraps(funcao)
    def interna(user, topic_name, *argumentos, **argumentos_nomeados):
        caminho = TopicModel.get_json_path(user, topic_name)
        with _trava_do_topico(caminho):
            return funcao(user, topic_name, *argumentos, **argumentos_nomeados)
    return interna


def _extras_de(dicionario, campos_conhecidos):
    sobras = {
        chave: valor
        for chave, valor in dicionario.items()
        if chave not in campos_conhecidos
    }
    return json.dumps(sobras, ensure_ascii=False) if sobras else None


def _atualizar_extras(dicionario, extras):
    if not extras:
        return dicionario
    try:
        dicionario.update(json.loads(extras))
    except (TypeError, ValueError):
        pass
    return dicionario


class TopicModel:
    @staticmethod
    def get_user_base_dir(user):
        if user is None:
            return None
        username = user.username if hasattr(user, 'username') else str(user)
        safe_username = re.sub(r'[^\w\-_]', '_', username)

        return os.path.join(current_app.config['BASE_DIR'], 'data', 'users', safe_username)

    @staticmethod
    def garantir_dentro(base, *partes):
        base_real = os.path.realpath(base)
        alvo = os.path.realpath(os.path.join(base, *partes))
        if alvo != base_real and not alvo.startswith(base_real + os.sep):
            raise BadRequest('Caminho de arquivo inválido.')
        return alvo

    @staticmethod
    def arquivo_dentro(pasta, filename):
        return TopicModel.garantir_dentro(pasta, filename)

    @staticmethod
    def get_topics_folder(user):
        base = TopicModel.get_user_base_dir(user)
        if base is None:
            return None
        return os.path.join(base, 'topics')

    @staticmethod
    def get_images_folder(user, topic_name):
        base = TopicModel.get_user_base_dir(user)
        if base is None:
            return None
        base = os.path.join(base, 'static', 'images', 'topics')
        TopicModel.garantir_dentro(base, topic_name)
        return os.path.join(base, topic_name)

    @staticmethod
    def get_whiteboards_folder(user, topic_name):
        base = TopicModel.get_user_base_dir(user)
        if base is None:
            return None
        base = os.path.join(base, 'static', 'whiteboards', 'topics')
        TopicModel.garantir_dentro(base, topic_name)
        return os.path.join(base, topic_name)

    @staticmethod
    def get_questions_folder(user, topic_name):
        base = TopicModel.get_user_base_dir(user)
        if base is None:
            return None
        base = os.path.join(base, 'questions')
        TopicModel.garantir_dentro(base, topic_name)
        return os.path.join(base, topic_name)

    @staticmethod
    def get_material_folder(user, topic_name):
        base = TopicModel.get_user_base_dir(user)
        if base is None:
            return None
        base = os.path.join(base, 'material_apoio', 'topics')
        TopicModel.garantir_dentro(base, topic_name)
        return os.path.join(base, topic_name)

    @staticmethod
    def get_json_path(user, topic_name):
        base = TopicModel.get_topics_folder(user)
        if base is None:
            return None
        TopicModel.garantir_dentro(base, topic_name + '.json')
        return os.path.join(base, topic_name + '.json')

    @staticmethod
    def sanitize_topic_name(topic_name):
        return re.sub(r'[^\w\-_]', '_', topic_name)

    @staticmethod
    def create_user_dirs(user):
        base = TopicModel.get_user_base_dir(user)
        if base is None:
            return
        os.makedirs(os.path.join(base, 'topics'), exist_ok=True)
        os.makedirs(os.path.join(base, 'static', 'images', 'topics'), exist_ok=True)
        os.makedirs(os.path.join(base, 'static', 'whiteboards', 'topics'), exist_ok=True)
        os.makedirs(os.path.join(base, 'questions'), exist_ok=True)

    @staticmethod
    def _id_do_usuario(user):
        if user is None:
            return None
        if hasattr(user, 'id') and not isinstance(user, (str, bytes)):
            return user.id
        nome = str(user)
        usuario = User.query.filter_by(username=nome).first()
        if usuario is None:
            seguro = TopicModel.sanitize_topic_name(nome)
            usuario = next(
                (
                    u
                    for u in User.query.all()
                    if TopicModel.sanitize_topic_name(u.username) == seguro
                ),
                None,
            )
        return usuario.id if usuario else None

    @staticmethod
    def _linha_topico(user, topic_name):
        user_id = TopicModel._id_do_usuario(user)
        if user_id is None:
            return None
        return Topic.query.filter_by(user_id=user_id, nome=topic_name).first()

    @staticmethod
    def _pergunta_para_dict(linha):
        pergunta = {
            'questao': linha.questao,
            'tipo': linha.tipo,
            'resposta': linha.resposta,
            'explicacao': linha.explicacao,
        }
        if linha.whiteboard_img is not None:
            pergunta['whiteboard_img'] = linha.whiteboard_img
        if linha.enunciado is not None:
            pergunta['enunciado'] = linha.enunciado
        return _atualizar_extras(pergunta, linha.extras)

    @staticmethod
    def _carregar_topico(user, topic_name):
        topico = TopicModel._linha_topico(user, topic_name)
        if topico is None:
            return None

        imagens = (
            TopicImage.query
            .filter_by(topic_id=topico.id)
            .order_by(TopicImage.posicao)
            .all()
        )
        itens = []
        for imagem in imagens:
            item = {'imagem': imagem.imagem or ''}
            if imagem.data is not None:
                item['data'] = imagem.data
            if imagem.is_text_question is not None:
                item['is_text_question'] = imagem.is_text_question
            if imagem.texto is not None:
                item['texto'] = imagem.texto
            _atualizar_extras(item, imagem.extras)
            item['questoes'] = [
                TopicModel._pergunta_para_dict(pergunta)
                for pergunta in sorted(imagem.questoes, key=lambda p: p.posicao)
            ]
            itens.append(item)

        notas = (
            TopicNote.query
            .filter_by(topic_id=topico.id)
            .order_by(TopicNote.posicao)
            .all()
        )
        notas_lista = []
        for nota in notas:
            dados_nota = {
                'id': nota.note_id,
                'image_filename': nota.image_filename,
                'text': nota.text,
                'timestamp': nota.timestamp,
            }
            notas_lista.append(_atualizar_extras(dados_nota, nota.extras))

        sessoes = (
            TopicSession.query
            .filter_by(topic_id=topico.id)
            .order_by(TopicSession.posicao)
            .all()
        )
        sessoes_lista = []
        for sessao in sessoes:
            try:
                sessoes_lista.append(json.loads(sessao.dados))
            except ValueError:
                continue

        estrategia = TopicStrategy.query.filter_by(topic_id=topico.id).first()
        estrategia_dados = None
        if estrategia is not None and estrategia.dados:
            try:
                estrategia_dados = json.loads(estrategia.dados)
            except ValueError:
                estrategia_dados = None

        dados = {
            'items': itens,
            'notes': notas_lista,
            'study_strategy': estrategia_dados,
            'generated_questions_sessions': sessoes_lista,
        }
        return _atualizar_extras(dados, topico.extras)

    @staticmethod
    def _gravar_topico(user, topic_name, data, criar_ausente=True):
        user_id = TopicModel._id_do_usuario(user)
        if user_id is None:
            raise BadRequest('Usuário do tópico não encontrado no banco.')

        topico = Topic.query.filter_by(user_id=user_id, nome=topic_name).first()
        if topico is None:
            if not criar_ausente:
                return False
            topico = Topic(user_id=user_id, nome=topic_name)
            db.session.add(topico)
            db.session.flush()
        topico.extras = _extras_de(data, CAMPOS_TOPICO)

        TopicImage.query.filter_by(topic_id=topico.id).delete(synchronize_session=False)
        TopicNote.query.filter_by(topic_id=topico.id).delete(synchronize_session=False)
        TopicSession.query.filter_by(topic_id=topico.id).delete(synchronize_session=False)
        TopicStrategy.query.filter_by(topic_id=topico.id).delete(synchronize_session=False)

        for posicao, item in enumerate(data.get('items') or []):
            if not isinstance(item, dict):
                continue
            imagem = TopicImage(
                topic_id=topico.id,
                imagem=item.get('imagem'),
                posicao=posicao,
                data=item.get('data'),
                is_text_question=item.get('is_text_question'),
                texto=item.get('texto'),
                extras=_extras_de(item, CAMPOS_ITEM),
            )
            db.session.add(imagem)
            db.session.flush()
            for posicao_questao, questao in enumerate(item.get('questoes') or []):
                if not isinstance(questao, dict):
                    continue
                db.session.add(
                    QuestionRow(
                        image_id=imagem.id,
                        posicao=posicao_questao,
                        questao=questao.get('questao'),
                        tipo=questao.get('tipo'),
                        resposta=questao.get('resposta'),
                        explicacao=questao.get('explicacao'),
                        whiteboard_img=questao.get('whiteboard_img'),
                        enunciado=questao.get('enunciado'),
                        extras=_extras_de(questao, CAMPOS_PERGUNTA),
                    )
                )

        for posicao, nota in enumerate(data.get('notes') or []):
            if not isinstance(nota, dict):
                continue
            db.session.add(
                TopicNote(
                    topic_id=topico.id,
                    posicao=posicao,
                    note_id=nota.get('id'),
                    image_filename=nota.get('image_filename'),
                    text=nota.get('text'),
                    timestamp=nota.get('timestamp'),
                    extras=_extras_de(nota, CAMPOS_NOTA),
                )
            )

        for posicao, sessao in enumerate(data.get('generated_questions_sessions') or []):
            db.session.add(
                TopicSession(
                    topic_id=topico.id,
                    posicao=posicao,
                    dados=json.dumps(sessao, ensure_ascii=False),
                )
            )

        estrategia = data.get('study_strategy')
        if estrategia is not None:
            db.session.add(
                TopicStrategy(
                    topic_id=topico.id,
                    dados=json.dumps(estrategia, ensure_ascii=False),
                )
            )

        db.session.commit()

    @staticmethod
    def _load_json_data(user, topic_name):
        dados = TopicModel._carregar_topico(user, topic_name)
        return dados if dados is not None else {"items": []}

    @staticmethod
    def _save_json_data(user, topic_name, data, criar_ausente=False):
        with _trava_do_topico(TopicModel.get_json_path(user, topic_name)):
            return TopicModel._gravar_topico(
                user, topic_name, data, criar_ausente=criar_ausente
            )

    @staticmethod
    def list_topics(user):
        user_id = TopicModel._id_do_usuario(user)
        if user_id is None:
            return []
        return [
            topico.nome
            for topico in Topic.query.filter_by(user_id=user_id).order_by(Topic.nome)
        ]

    @staticmethod
    def topic_exists(user, topic_name):
        return TopicModel._linha_topico(user, topic_name) is not None

    @staticmethod
    @com_trava_de_topico
    def create_topic(user, topic_name):
        safe_name = TopicModel.sanitize_topic_name(topic_name)
        os.makedirs(TopicModel.get_images_folder(user, safe_name), exist_ok=True)
        os.makedirs(TopicModel.get_whiteboards_folder(user, safe_name), exist_ok=True)
        os.makedirs(TopicModel.get_questions_folder(user, safe_name), exist_ok=True)
        os.makedirs(TopicModel.get_material_folder(user, safe_name), exist_ok=True)
        if TopicModel._linha_topico(user, safe_name) is None:
            json_path = TopicModel.get_json_path(user, safe_name)
            if os.path.exists(json_path):
                TopicModel._importar_json_legado(user, safe_name, json_path)
            else:
                TopicModel._gravar_topico(user, safe_name, {"items": []})
        return safe_name

    @staticmethod
    def _importar_json_legado(user, topic_name, json_path):
        with open(json_path, 'r', encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
        if isinstance(dados, list):
            dados = {"items": dados}
        TopicModel._gravar_topico(user, topic_name, dados)

    @staticmethod
    def get_image_files(user, topic_name):
        folder = TopicModel.get_images_folder(user, topic_name)
        if not os.path.exists(folder):
            return []
        files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        files.sort()
        return files

    @staticmethod
    def get_resolutions(user, topic_name):
        data = TopicModel._load_json_data(user, topic_name)
        return data.get("items", [])

    @staticmethod
    @com_trava_de_topico
    def save_resolutions(user, topic_name, resolutions):
        data = TopicModel._load_json_data(user, topic_name)
        data["items"] = resolutions
        TopicModel._save_json_data(user, topic_name, data)

    @staticmethod
    def get_questions_for_image(user, topic_name, image_filename):
        resolutions = TopicModel.get_resolutions(user, topic_name)
        item = next((item for item in resolutions if item.get("imagem") == image_filename), None)
        return item.get("questoes", []) if item else []

    @staticmethod
    @com_trava_de_topico
    def add_question(user, topic_name, image_filename, questao_data):
        resolutions = TopicModel.get_resolutions(user, topic_name)
        item = next((item for item in resolutions if item.get("imagem") == image_filename), None)
        if not item:
            item = {"imagem": image_filename, "questoes": []}
            resolutions.append(item)
        item["questoes"].append(questao_data)
        TopicModel.save_resolutions(user, topic_name, resolutions)
        return len(item["questoes"]) - 1

    @staticmethod
    @com_trava_de_topico
    def update_question(user, topic_name, image_filename, q_idx, updated_data):
        resolutions = TopicModel.get_resolutions(user, topic_name)
        for item in resolutions:
            if item.get("imagem") == image_filename:
                if 0 <= q_idx < len(item["questoes"]):
                    item["questoes"][q_idx].update(updated_data)
                    TopicModel.save_resolutions(user, topic_name, resolutions)
                    return True
        return False

    @staticmethod
    @com_trava_de_topico
    def delete_question(user, topic_name, image_filename, q_idx):
        resolutions = TopicModel.get_resolutions(user, topic_name)
        for item in resolutions:
            if item.get("imagem") == image_filename:
                if 0 <= q_idx < len(item["questoes"]):
                    del item["questoes"][q_idx]
                    TopicModel.save_resolutions(user, topic_name, resolutions)
                    return True
        return False

    @staticmethod
    def rename_topic(user, old_safe, new_safe):
        caminho_antigo = TopicModel.get_json_path(user, old_safe)
        caminho_novo = TopicModel.get_json_path(user, new_safe)
        travas = [_trava_do_topico(c) for c in sorted({caminho_antigo, caminho_novo})]
        for trava in travas:
            trava.acquire()
        try:
            old_img = TopicModel.get_images_folder(user, old_safe)
            new_img = TopicModel.get_images_folder(user, new_safe)
            if os.path.exists(old_img):
                shutil.move(old_img, new_img)
            old_wb = TopicModel.get_whiteboards_folder(user, old_safe)
            new_wb = TopicModel.get_whiteboards_folder(user, new_safe)
            if os.path.exists(old_wb):
                shutil.move(old_wb, new_wb)
            old_q = TopicModel.get_questions_folder(user, old_safe)
            new_q = TopicModel.get_questions_folder(user, new_safe)
            if os.path.exists(old_q):
                shutil.move(old_q, new_q)
            old_mat = TopicModel.get_material_folder(user, old_safe)
            new_mat = TopicModel.get_material_folder(user, new_safe)
            if os.path.exists(old_mat):
                if os.path.exists(new_mat):
                    shutil.rmtree(new_mat, ignore_errors=True)
                os.makedirs(os.path.dirname(new_mat), exist_ok=True)
                shutil.move(old_mat, new_mat)
            old_json = TopicModel.get_json_path(user, old_safe)
            new_json = TopicModel.get_json_path(user, new_safe)
            if os.path.exists(old_json):
                shutil.move(old_json, new_json)
            topico = TopicModel._linha_topico(user, old_safe)
            if topico is not None:
                topico.nome = new_safe
                db.session.commit()
            return True, "OK"
        except Exception as e:
            db.session.rollback()
            return False, str(e)
        finally:
            for trava in reversed(travas):
                trava.release()

    @staticmethod
    def delete_topic(user, topic_name):
        topico = TopicModel._linha_topico(user, topic_name)
        removido = topico is not None
        if topico is not None:
            db.session.delete(topico)
            db.session.commit()
        json_path = TopicModel.get_json_path(user, topic_name)
        if os.path.exists(json_path):
            with _trava_do_topico(json_path):
                os.remove(json_path)
        return removido

    @staticmethod
    def get_all_topic_content(user, topic_name):
        content = []
        resolutions = TopicModel.get_resolutions(user, topic_name)
        for item in resolutions:
            image = item.get('imagem', '')
            for q in item.get('questoes', []):
                content.append(f"Imagem: {image}")
                content.append(f"Questão {q.get('questao', '')}:")
                content.append(f"Enunciado: {q.get('enunciado', '')}")
                content.append(f"Resposta: {q.get('resposta', '')}")
                content.append(f"Explicação: {q.get('explicacao', '')}")
                content.append("")
        questions_folder = TopicModel.get_questions_folder(user, topic_name)
        if os.path.exists(questions_folder):
            for filename in os.listdir(questions_folder):
                if filename.lower().endswith('.pdf'):
                    pdf_path = os.path.join(questions_folder, filename)
                    try:
                        import fitz
                        doc = fitz.open(pdf_path)
                        pdf_text = ""
                        for page in doc:
                            pdf_text += page.get_text()
                        doc.close()
                        if pdf_text.strip():
                            content.append(f"\n--- Conteúdo do PDF '{filename}': ---")
                            content.append(pdf_text)
                    except Exception:
                        pass
        notes = TopicModel.get_notes(user, topic_name)
        for note in notes:
            if note.get('image_filename') is None:
                content.append(f"Anotação geral: {note['text']}")
            else:
                content.append(f"Anotação para imagem {note['image_filename']}: {note['text']}")
        return "\n".join(content)

    @staticmethod
    def get_notes(user, topic_name):
        data = TopicModel._load_json_data(user, topic_name)
        return data.get("notes", [])

    @staticmethod
    @com_trava_de_topico
    def add_note(user, topic_name, note_data):
        data = TopicModel._load_json_data(user, topic_name)
        if "notes" not in data:
            data["notes"] = []
        data["notes"].append(note_data)
        TopicModel._save_json_data(user, topic_name, data)

    @staticmethod
    @com_trava_de_topico
    def update_note(user, topic_name, note_id, updated_text):
        data = TopicModel._load_json_data(user, topic_name)
        for note in data.get("notes", []):
            if note.get("id") == note_id:
                note["text"] = updated_text
                note["timestamp"] = datetime.now().isoformat()
                TopicModel._save_json_data(user, topic_name, data)
                return True
        return False

    @staticmethod
    @com_trava_de_topico
    def delete_note(user, topic_name, note_id):
        data = TopicModel._load_json_data(user, topic_name)
        data["notes"] = [n for n in data.get("notes", []) if n.get("id") != note_id]
        TopicModel._save_json_data(user, topic_name, data)

    @staticmethod
    def get_study_strategy(user, topic_name):
        data = TopicModel._load_json_data(user, topic_name)
        return data.get("study_strategy")

    @staticmethod
    @com_trava_de_topico
    def set_study_strategy(user, topic_name, strategy, salvar_historico=True):
        data = TopicModel._load_json_data(user, topic_name)
        data["study_strategy"] = strategy
        if salvar_historico:
            data["study_strategy_history"] = TopicModel.adicionar_estrategia_no_historico(
                data.get("study_strategy_history"), strategy
            )
        TopicModel._save_json_data(user, topic_name, data)

    @staticmethod
    def get_study_strategy_history(user, topic_name):
        data = TopicModel._load_json_data(user, topic_name)
        historico = data.get("study_strategy_history")
        return historico if isinstance(historico, list) else []

    @staticmethod
    @com_trava_de_topico
    def set_study_strategy_history(user, topic_name, historico):
        data = TopicModel._load_json_data(user, topic_name)
        data["study_strategy_history"] = historico
        TopicModel._save_json_data(user, topic_name, data)

    @staticmethod
    def adicionar_estrategia_no_historico(historico, strategy):
        lista = historico if isinstance(historico, list) else []
        if lista and lista[0].get("estrategia") == strategy:
            return lista
        entrada = {"salvo_em": datetime.now().isoformat(), "estrategia": strategy}
        return ([entrada] + lista)[:20]

    @staticmethod
    def get_instruction_memory(user, topic_name, tipo=None, limite=20):
        from models.topic_tables import TopicInstructionMemory
        from models.user_model import User
        
        user_id = TopicModel._id_do_usuario(user)
        if user_id is None:
            return []
        
        query = TopicInstructionMemory.query.filter_by(topic_id=TopicModel._id_do_topico(user, topic_name))
        if tipo:
            query = query.filter_by(tipo=tipo)
        query = query.order_by(TopicInstructionMemory.criado_em.desc())
        
        if limite:
            query = query.limit(limite)
        
        resultados = query.all()
        return [r.instrucao for r in resultados]

    @staticmethod
    @com_trava_de_topico
    def add_instruction_memory(user, topic_name, instrucao, tipo='geral'):
        from models.topic_tables import TopicInstructionMemory
        
        topic_id = TopicModel._id_do_topico(user, topic_name)
        if topic_id is None:
            return False
        
        recentes = TopicModel.get_instruction_memory(user, topic_name, tipo, 5)
        if instrucao in recentes:
            return True
        
        memoria = TopicInstructionMemory(
            topic_id=topic_id,
            instrucao=instrucao,
            tipo=tipo
        )
        db.session.add(memoria)
        db.session.commit()
        return True

    @staticmethod
    @com_trava_de_topico
    def limpar_instruction_memory(user, topic_name, tipo=None):
        from models.topic_tables import TopicInstructionMemory
        
        topic_id = TopicModel._id_do_topico(user, topic_name)
        if topic_id is None:
            return
        
        query = TopicInstructionMemory.query.filter_by(topic_id=topic_id)
        if tipo:
            query = query.filter_by(tipo=tipo)
        query.delete()
        db.session.commit()

    @staticmethod
    @com_trava_de_topico
    def delete_image_file(user, topic_name, filename):
        resolutions = TopicModel.get_resolutions(user, topic_name)
        new_resolutions = [item for item in resolutions if item.get("imagem") != filename]
        TopicModel.save_resolutions(user, topic_name, new_resolutions)
        whiteboard_folder = TopicModel.get_whiteboards_folder(user, topic_name)
        if os.path.isdir(whiteboard_folder):
            for item in os.listdir(whiteboard_folder):
                if filename in item:
                    try:
                        os.remove(os.path.join(whiteboard_folder, item))
                    except:
                        pass
        images_folder = TopicModel.get_images_folder(user, topic_name)
        filepath = os.path.join(images_folder, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    @staticmethod
    @com_trava_de_topico
    def delete_image_references(user, topic_name, base_name):
        data = TopicModel._load_json_data(user, topic_name)
        if 'items' not in data:
            return
        new_items = []
        for item in data['items']:
            imagem = item.get('imagem', '')
            if not imagem.startswith(base_name):
                new_items.append(item)
        data['items'] = new_items
        TopicModel._save_json_data(user, topic_name, data)

    @staticmethod
    def get_generated_sessions(user, topic_name):
        data = TopicModel._load_json_data(user, topic_name)
        return data.get("generated_questions_sessions", [])

    @staticmethod
    @com_trava_de_topico
    def update_generated_session(user, topic_name, session_idx, updated_data):
        data = TopicModel._load_json_data(user, topic_name)
        sessions = data.get("generated_questions_sessions", [])
        if 0 <= session_idx < len(sessions):
            sessions[session_idx] = updated_data
            data["generated_questions_sessions"] = sessions
            TopicModel._save_json_data(user, topic_name, data)
            return True
        return False

    @staticmethod
    @com_trava_de_topico
    def delete_generated_session(user, topic_name, session_idx):
        data = TopicModel._load_json_data(user, topic_name)
        sessions = data.get("generated_questions_sessions", [])
        if 0 <= session_idx < len(sessions):
            del sessions[session_idx]
            data["generated_questions_sessions"] = sessions
            TopicModel._save_json_data(user, topic_name, data)
            return True
        return False


def migrar_conteudo_legado():
    migrados = 0
    ignorados = 0
    com_erro = 0
    for usuario in User.query.all():
        try:
            pasta = TopicModel.get_topics_folder(usuario)
        except Exception:
            continue
        if not os.path.isdir(pasta):
            continue
        for nome_arquivo in sorted(os.listdir(pasta)):
            if not nome_arquivo.endswith('.json'):
                continue
            nome_topico = nome_arquivo[:-5]
            try:
                if TopicModel._linha_topico(usuario, nome_topico) is not None:
                    ignorados += 1
                    continue
                caminho = os.path.join(pasta, nome_arquivo)
                with open(caminho, 'r', encoding='utf-8') as arquivo:
                    dados = json.load(arquivo)
                if isinstance(dados, list):
                    dados = {"items": dados}
                TopicModel._gravar_topico(usuario, nome_topico, dados)
                migrados += 1
            except Exception as erro:
                com_erro += 1
                print(f"Erro ao migrar tópico legado '{nome_arquivo}': {erro}")
    print(
        f"Migração JSON→SQL de tópicos: {migrados} importado(s), "
        f"{ignorados} já existente(s), {com_erro} erro(s)."
    )
    return migrados


def importar_respostas_legadas():
    raiz_dados = os.path.join(current_app.config['BASE_DIR'], 'data')
    caminho_sqlite = os.path.join(raiz_dados, 'respostas_imagens.sqlite')
    if not os.path.isfile(caminho_sqlite):
        return 0

    localizacao = {}
    pasta_users = os.path.join(raiz_dados, 'users')
    if os.path.isdir(pasta_users):
        for nome_usuario in os.listdir(pasta_users):
            pasta_imagens = os.path.join(pasta_users, nome_usuario, 'static', 'images', 'topics')
            if not os.path.isdir(pasta_imagens):
                continue
            for nome_topico in os.listdir(pasta_imagens):
                pasta_topico = os.path.join(pasta_imagens, nome_topico)
                if not os.path.isdir(pasta_topico):
                    continue
                for arquivo in os.listdir(pasta_topico):
                    localizacao.setdefault(arquivo, (nome_usuario, nome_topico))

    conexao = sqlite3.connect(caminho_sqlite)
    try:
        linhas = conexao.execute(
            "SELECT imagem, questao, resposta, explicacao, timestamp, tipo FROM respostas"
        ).fetchall()
    finally:
        conexao.close()

    novas = 0
    preenchidas = 0
    respondidas = 0
    sem_imagem = 0
    conflitos = []
    dados_por_topico = {}
    for imagem, questao, resposta, explicacao, timestamp, tipo in linhas:
        local = localizacao.get(imagem)
        if not local:
            sem_imagem += 1
            continue
        nome_usuario, nome_topico = local
        dados = TopicModel._load_json_data(nome_usuario, nome_topico)
        itens = dados.setdefault('items', [])
        item = next((i for i in itens if i.get('imagem') == imagem), None)
        if item is None:
            item = {"imagem": imagem, "questoes": []}
            itens.append(item)
        existente = next(
            (q for q in item.get('questoes', []) if str(q.get('questao')) == str(questao)),
            None,
        )
        if existente is not None:
            if (existente.get('resposta') or '').strip():
                if (existente.get('resposta') or '') == (resposta or ''):
                    respondidas += 1
                else:
                    conflitos.append(f"{imagem} :: questão {questao}")
                continue
            existente['resposta'] = resposta or ''
            if not (existente.get('explicacao') or '').strip():
                existente['explicacao'] = explicacao or ''
            if not existente.get('tipo') and tipo:
                existente['tipo'] = tipo
            preenchidas += 1
        else:
            nova = {
                'questao': questao,
                'resposta': resposta or '',
                'explicacao': explicacao or '',
            }
            if tipo:
                nova['tipo'] = tipo
            if timestamp:
                nova['timestamp'] = timestamp
            item.setdefault('questoes', []).append(nova)
            novas += 1
        dados_por_topico[(nome_usuario, nome_topico)] = dados
        TopicModel._save_json_data(
            nome_usuario, nome_topico, dados, criar_ausente=True
        )

    for (nome_usuario, nome_topico), dados in sorted(dados_por_topico.items()):
        caminho_json = TopicModel.get_json_path(nome_usuario, nome_topico)
        try:
            temporario = f"{caminho_json}.tmp"
            with open(temporario, 'w', encoding='utf-8') as arquivo:
                json.dump(dados, arquivo, ensure_ascii=False, indent=2)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, caminho_json)
        except OSError as erro:
            print(f"Aviso: não foi possível atualizar o JSON legado {caminho_json}: {erro}")

    os.remove(caminho_sqlite)
    print(
        f"Respostas legadas do SQLite importadas: {novas} nova(s), "
        f"{preenchidas} preenchida(s); {respondidas} já respondida(s), "
        f"{len(conflitos)} em conflito (conteúdo do tópico preservado) e "
        f"{sem_imagem} sem imagem correspondente descartadas; "
        "arquivo respostas_imagens.sqlite removido."
    )
    for conflito in conflitos:
        print(f"  Conflito legado preservando o tópico: {conflito}")
    return novas + preenchidas
