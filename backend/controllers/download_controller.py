from flask import Blueprint, send_file, send_from_directory, redirect, url_for, flash, request, jsonify
from models.topic_model import TopicModel
from flask_login import current_user
import os
import io
import zipfile
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageOps
except ImportError:
    logger.info("Pillow não encontrado. Tentando instalar...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageOps

download_bp = Blueprint('download', __name__)


def _empty_download_response(title, message):
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8fafc; color: #0f172a; display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; padding:1rem; }}
.card {{ background:#fff; padding:2rem 2.5rem; border-radius:16px; box-shadow:0 6px 24px rgba(0,0,0,0.08); max-width:520px; text-align:center; border-top:4px solid #eab308; }}
h1 {{ color:#1e3a8a; font-size:1.3rem; margin:0 0 0.75rem 0; }}
p {{ color:#475569; line-height:1.55; margin:0 0 1.5rem 0; }}
a {{ display:inline-block; background:#1e3a8a; color:#fff; text-decoration:none; padding:0.6rem 1.4rem; border-radius:8px; font-weight:600; transition:background 0.15s; }}
a:hover {{ background:#172554; }}
</style>
</head>
<body>
<div class="card">
<h1>{title}</h1>
<p>{message}</p>
<a href="javascript:window.close()">Fechar</a>
</div>
</body>
</html>"""
    return html, 200


def make_white_background(image_path):
    try:
        img = Image.open(image_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        cores = img.getcolors(maxcolors=2)
        if cores is not None and len(cores) == 1:
            vazio = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            output = io.BytesIO()
            vazio.save(output, format='PNG')
            output.seek(0)
            return output
        white_bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        white_bg.paste(img, (0, 0), img)
        result = white_bg.convert('RGB')
        output = io.BytesIO()
        result.save(output, format='PNG')
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Erro ao processar imagem {image_path}: {e}")
        with open(image_path, 'rb') as f:
            return io.BytesIO(f.read())


@download_bp.route('/topic/<topic_name>/download_status')
def download_status(topic_name):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401

    images_folder = TopicModel.get_images_folder(current_user, topic_name)
    has_images = False
    if os.path.exists(images_folder):
        image_files = [f for f in os.listdir(images_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        has_images = len(image_files) > 0

    whiteboards_folder = TopicModel.get_whiteboards_folder(current_user, topic_name)
    has_whiteboards = False
    if os.path.exists(whiteboards_folder):
        wb_files = [f for f in os.listdir(whiteboards_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        has_whiteboards = len(wb_files) > 0

    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    has_resolutions = False
    for item in resolutions:
        for q in item.get('questoes', []):
            if q.get('resposta') or q.get('explicacao'):
                has_resolutions = True
                break
        if has_resolutions:
            break

    return jsonify({
        'images': has_images,
        'whiteboards': has_whiteboards,
        'resolutions': has_resolutions
    })


@download_bp.route('/topic/<topic_name>/download_image/<filename>')
def download_image(topic_name, filename):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    images_folder = TopicModel.get_images_folder(current_user, topic_name)
    filepath = TopicModel.arquivo_dentro(images_folder, filename)
    if not os.path.exists(filepath):
        flash('Arquivo não encontrado.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name))
    return send_file(filepath, as_attachment=True, download_name=filename)


@download_bp.route('/topic/<topic_name>/download_all_images')
def download_all_images(topic_name):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    images_folder = TopicModel.get_images_folder(current_user, topic_name)
    if not os.path.exists(images_folder):
        return _empty_download_response(
            'Nenhuma imagem disponível',
            f'O tópico <strong>{topic_name}</strong> ainda não possui imagens para download. Faça o upload de arquivos primeiro.'
        )
    image_files = [f for f in os.listdir(images_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not image_files:
        return _empty_download_response(
            'Nenhuma imagem disponível',
            f'O tópico <strong>{topic_name}</strong> ainda não possui imagens para download. Faça o upload de arquivos primeiro.'
        )
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for filename in image_files:
            filepath = TopicModel.arquivo_dentro(images_folder, filename)
            zf.write(filepath, arcname=filename)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f'{topic_name}_imagens.zip', as_attachment=True)


@download_bp.route('/topic/<topic_name>/download_text_resolutions')
def download_text_resolutions(topic_name):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    has_content = False
    for item in resolutions:
        for q in item.get('questoes', []):
            if q.get('resposta') or q.get('explicacao'):
                has_content = True
                break
        if has_content:
            break
    if not resolutions or not has_content:
        return _empty_download_response(
            'Nenhuma resolução disponível',
            f'O tópico <strong>{topic_name}</strong> ainda não possui resoluções geradas. Analise imagens primeiro para criar resoluções.'
        )
    lines = []
    lines.append(f"Resoluções do tópico: {topic_name}\n")
    lines.append("=" * 50 + "\n")
    for item in resolutions:
        image = item.get("imagem", "desconhecida")
        questoes = item.get("questoes", [])
        if not questoes:
            continue
        lines.append(f"Imagem: {image}\n")
        for q in questoes:
            lines.append(f"  Questão {q.get('questao', '?')}:\n")
            lines.append(f"    Tipo: {q.get('tipo', 'não especificado')}\n")
            lines.append(f"    Resposta: {q.get('resposta', '')}\n")
            lines.append(f"    Explicação:\n{q.get('explicacao', '')}\n\n")
        lines.append("-" * 40 + "\n")
    content = "\n".join(lines)
    mem_file = io.BytesIO()
    mem_file.write(content.encode('utf-8'))
    mem_file.seek(0)
    return send_file(mem_file, as_attachment=True, download_name=f"{topic_name}_resolucoes.txt", mimetype='text/plain')


@download_bp.route('/topic/<topic_name>/download_whiteboards')
def download_whiteboards(topic_name):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    whiteboards_folder = TopicModel.get_whiteboards_folder(current_user, topic_name)
    if not os.path.exists(whiteboards_folder):
        return _empty_download_response(
            'Nenhum quadro branco disponível',
            f'O tópico <strong>{topic_name}</strong> ainda não possui quadros brancos salvos. Crie anotações no quadro branco primeiro.'
        )
    image_files = [f for f in os.listdir(whiteboards_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not image_files:
        return _empty_download_response(
            'Nenhum quadro branco disponível',
            f'O tópico <strong>{topic_name}</strong> ainda não possui quadros brancos salvos. Crie anotações no quadro branco primeiro.'
        )
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for filename in image_files:
            filepath = TopicModel.arquivo_dentro(whiteboards_folder, filename)
            zf.write(filepath, arcname=filename)
    memory_file.seek(0)
    return send_file(memory_file, download_name=f'{topic_name}_quadros_brancos.zip', as_attachment=True)


@download_bp.route('/topic/<topic_name>/download_question_text/<path:image_filename>/<int:q_idx>')
def download_question_text(topic_name, image_filename, q_idx):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    idx = request.args.get('idx', 0)
    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    item = next((item for item in resolutions if item.get("imagem") == image_filename), None)
    if not item:
        flash('Imagem não encontrada.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))
    questoes = item.get("questoes", [])
    if q_idx < 0 or q_idx >= len(questoes):
        flash('Índice de questão inválido.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))
    q = questoes[q_idx]
    content = f"Questão: {q.get('questao', '?')}\n"
    content += f"Tipo: {q.get('tipo', 'não especificado')}\n"
    content += f"Enunciado:\n{q.get('enunciado', '')}\n\n"
    content += f"Resposta: {q.get('resposta', '')}\n"
    content += f"Explicação:\n{q.get('explicacao', '')}\n"
    mem_file = io.BytesIO()
    mem_file.write(content.encode('utf-8'))
    mem_file.seek(0)
    safe_name = f"{topic_name}_questao_{q.get('questao', q_idx)}.txt"
    return send_file(mem_file, as_attachment=True, download_name=safe_name, mimetype='text/plain')


@download_bp.route('/topic/<topic_name>/download_question_whiteboard/<path:image_filename>/<int:q_idx>')
def download_question_whiteboard(topic_name, image_filename, q_idx):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    idx = request.args.get('idx', 0)
    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    item = next((item for item in resolutions if item.get("imagem") == image_filename), None)
    if not item:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Imagem não encontrada.'}), 404
        flash('Imagem não encontrada.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    questoes = item.get("questoes", [])
    if q_idx < 0 or q_idx >= len(questoes):
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Índice de questão inválido.'}), 404
        flash('Índice de questão inválido.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    whiteboard_img = questoes[q_idx].get('whiteboard_img')
    whiteboard_folder = TopicModel.get_whiteboards_folder(current_user, topic_name)
    filepath = None

    if whiteboard_img:
        whiteboard_img = os.path.basename(whiteboard_img)
        candidate = TopicModel.arquivo_dentro(whiteboard_folder, whiteboard_img)
        if os.path.exists(candidate):
            filepath = candidate
            logger.info(f"Usando whiteboard_img do JSON: {filepath}")
        else:
            logger.warning(f"Arquivo não encontrado no caminho do JSON: {candidate}")

    if not filepath:
        base_name = os.path.splitext(os.path.basename(image_filename))[0]
        fallback_filename = f"whiteboard_{base_name}_q{q_idx}.png"
        candidate = TopicModel.arquivo_dentro(whiteboard_folder, fallback_filename)
        if os.path.exists(candidate):
            filepath = candidate
            logger.info(f"Usando fallback: {filepath}")
        else:
            logger.error(f"Fallback também não encontrado: {candidate}")

    if not filepath:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Arquivo de quadro branco não encontrado no servidor.'}), 404
        flash('Arquivo de quadro branco não encontrado no servidor.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    try:
        img_data = make_white_background(filepath)
        return send_file(img_data, as_attachment=True,
                         download_name=os.path.basename(filepath),
                         mimetype='image/png')
    except Exception as e:
        logger.exception(f"Erro ao processar imagem {filepath}: {e}")
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': f'Erro ao processar imagem: {str(e)}'}), 500
        flash(f'Erro ao processar imagem: {str(e)}', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))


@download_bp.route('/topic/<topic_name>/download_whiteboard_livre/<path:image_filename>')
def download_whiteboard_livre(topic_name, image_filename):
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    idx = request.args.get('idx', 0)
    resolutions = TopicModel.get_resolutions(current_user, topic_name)
    item = next((item for item in resolutions if item.get("imagem") == image_filename), None)
    if not item:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Imagem não encontrada.'}), 404
        flash('Imagem não encontrada.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    whiteboard_folder = TopicModel.get_whiteboards_folder(current_user, topic_name)
    filepath = None
    whiteboard_img = item.get('whiteboard_livre')
    if whiteboard_img:
        candidate = TopicModel.arquivo_dentro(whiteboard_folder, os.path.basename(whiteboard_img))
        if os.path.exists(candidate):
            filepath = candidate
    if not filepath:
        base_name = os.path.splitext(os.path.basename(image_filename))[0]
        candidate = TopicModel.arquivo_dentro(
            whiteboard_folder, f"whiteboard_{base_name}_livre.png"
        )
        if os.path.exists(candidate):
            filepath = candidate

    if not filepath:
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': 'Arquivo de quadro branco não encontrado no servidor.'}), 404
        flash('Arquivo de quadro branco não encontrado no servidor.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))

    try:
        img_data = make_white_background(filepath)
        return send_file(img_data, as_attachment=True,
                         download_name=os.path.basename(filepath),
                         mimetype='image/png')
    except Exception as e:
        logger.exception(f"Erro ao processar imagem {filepath}: {e}")
        if request.accept_mimetypes.accept_json:
            return jsonify({'error': f'Erro ao processar imagem: {str(e)}'}), 500
        flash(f'Erro ao processar imagem: {str(e)}', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name, idx=idx))


@download_bp.route('/whiteboard_image/<topic_name>/<filename>')
def serve_whiteboard_image(topic_name, filename):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Não autenticado'}), 401
    whiteboard_folder = TopicModel.get_whiteboards_folder(current_user, topic_name)
    logger.info(f"Tentando servir arquivo: {filename} da pasta {whiteboard_folder}")
    if not os.path.isdir(whiteboard_folder):
        logger.error(f"Pasta não encontrada: {whiteboard_folder}")
        return jsonify({'error': 'Pasta não encontrada'}), 404
    try:
        response = send_from_directory(whiteboard_folder, filename, as_attachment=False)
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        return response
    except FileNotFoundError:
        logger.error(f"Arquivo não encontrado: {filename}")
        return jsonify({'error': 'Arquivo não encontrado'}), 404