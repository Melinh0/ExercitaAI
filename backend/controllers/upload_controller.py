from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, jsonify
)
from models.topic_model import TopicModel
from services.image_service import (
    allowed_file, extract_images_from_pdf, save_uploaded_images,
    ALLOWED_IMAGE_EXTENSIONS
)
from services.ocr_service import (
    extract_text_from_uploaded_file, extract_text_from_pdf_bytes
)
from services import office_service
from services.rag_client import index_documents, remove_topic_vectors
from services.chunking import chunk_text
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest
from concurrent.futures import ThreadPoolExecutor, as_completed
from services import task_manager
from config import Config
import os
import re
import logging
import uuid

upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)

CHUNK_TARGET_SIZE = int(os.getenv("INDEX_CHUNK_TARGET_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("INDEX_CHUNK_OVERLAP", "100"))
INDEX_BATCH_SIZE = int(os.getenv("INDEX_BATCH_SIZE", "100"))
INDEX_MAX_WORKERS = int(os.getenv("INDEX_MAX_WORKERS", "4"))

EXTENSOES_DOCUMENTO = ('.pdf', '.pptx', '.ppt', '.docx', '.doc')

EXTENSOES_PERMITIDAS_RAG = {
    'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'txt', 'docx', 'pptx',
    'json', 'md', 'markdown', 'ipynb', 'py', 'js', 'ts', 'jsx', 'tsx',
    'java', 'cpp', 'c', 'h', 'hpp', 'cs', 'go', 'rs', 'rb', 'php',
    'swift', 'kt', 'scala', 'r', 'm', 'sh', 'bash', 'ps1', 'sql',
    'html', 'css', 'scss', 'sass', 'less', 'xml', 'yaml', 'yml',
    'toml', 'ini', 'cfg', 'conf', 'vue', 'svelte', 'dart', 'lua',
    'pl', 'pm', 'tcl', 'vb', 'fs', 'fsx', 'ml', 'mli', 'ex', 'exs',
    'erl', 'hrl', 'jl', 'nim', 'cr', 'zig', 'dockerfile', 'makefile',
    'gradle', 'tf', 'tfvars', 'bat', 'cmd', 'psm1', 'psd1', 'asm',
    's', 'pas', 'dpr', 'dpk', 'lpr', 'pp', 'inc', 'bas', 'cls',
    'frm', 'ctl', 'vbp', 'vbw'
}


def _validate_rag_file(file):
    if file.filename == '':
        return 'Nenhum arquivo selecionado.'
    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if file_ext not in EXTENSOES_PERMITIDAS_RAG:
        return 'Tipo de arquivo não suportado.'
    return None


def _process_single_rag_file(file, topic_name, user, ao_progresso=None):
    filename = secure_filename(file.filename)
    if ao_progresso:
        ao_progresso(3, 'Extraindo texto')
    try:
        raw_text = extract_text_from_uploaded_file(file, lang='por')
    except Exception as e:
        return {'success': False, 'filename': filename, 'error': f'Erro na extração: {str(e)}'}

    if not raw_text.strip():
        return {'success': False, 'filename': filename, 'error': 'Nenhum texto pôde ser extraído do arquivo.'}

    txt_path, txt_filename = save_extracted_text(user, topic_name, raw_text, filename)

    if ao_progresso:
        ao_progresso(8, 'Texto extraído, indexando')

    indexed_count = _index_text_in_batches(
        topic_name, txt_filename, raw_text, user.id,
        source_type='document', ao_progresso=ao_progresso
    )

    if indexed_count > 0:
        return {
            'success': True,
            'filename': filename,
            'chunks': indexed_count,
            'text_length': len(raw_text),
            'txt_file': txt_filename,
            'txt_path': txt_path
        }
    return {'success': False, 'filename': filename, 'error': 'Falha ao indexar documento.'}


@upload_bp.route('/topic/<topic_name>/upload_rag', methods=['POST'])
@login_required
def upload_rag(topic_name):
    if 'files' not in request.files and 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo enviado.'}), 400

    files = request.files.getlist('files') or request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado.'}), 400

    errors = []
    file_data_list = []
    for f in files:
        err = _validate_rag_file(f)
        if err:
            errors.append(f"{f.filename}: {err}")
        else:
            f.seek(0)
            file_bytes = f.read()
            file_data_list.append({
                'filename': secure_filename(f.filename),
                'content': file_bytes,
                'content_type': f.content_type or 'application/octet-stream'
            })

    if errors:
        return jsonify({'success': False, 'error': '; '.join(errors)}), 400

    task_id, repetida = task_manager.create_task('upload_rag', current_user.id, {
        'topic_name': topic_name,
        'file_count': len(file_data_list)
    }, dedup_key=topic_name)

    if repetida:
        return jsonify({'success': True, 'task_id': task_id, 'reused': True, 'message': 'O envio deste material ja esta em andamento. Acompanhe o progresso pelo indicador de tarefas.'})

    user_snap = type('UserSnap', (), {
        'id': current_user.id,
        'username': current_user.username,
        'get_ollama_keys': lambda: current_user.get_ollama_keys()
    })()

    task_manager.run_async(task_id, _worker_upload_rag, task_id, user_snap, topic_name, file_data_list)

    return jsonify({'success': True, 'task_id': task_id, 'message': 'Upload e indexação iniciados. Acompanhe o progresso pelo indicador de tarefas.'})


def _worker_upload_rag(task_id, user_snap, topic_name, file_data_list):
    results = []
    total_chunks = 0
    n_arquivos = len(file_data_list)

    for indice, file_data in enumerate(file_data_list):
        class _FileObj:
            def __init__(self, data):
                self._data = data
                self._pos = 0
            def seek(self, pos):
                self._pos = pos
            def read(self, size=-1):
                if size == -1:
                    result = self._data[self._pos:]
                    self._pos = len(self._data)
                else:
                    result = self._data[self._pos:self._pos+size]
                    self._pos += len(result)
                return result
            @property
            def filename(self):
                return file_data['filename']

        def ao_progresso(pct_interno, mensagem, _indice=indice, _nome=file_data['filename']):
            amplitude = 100 / n_arquivos
            progresso = int((_indice * amplitude) + (pct_interno * amplitude / 100))
            task_manager.update_task(
                task_id,
                progress=min(progresso, 99),
                message=f'{_nome}: {mensagem}'
            )

        task_manager.update_task(
            task_id,
            message=f'Processando {indice + 1}/{n_arquivos}: {file_data["filename"]}'
        )
        file_obj = _FileObj(file_data['content'])
        result = _process_single_rag_file(file_obj, topic_name, user_snap, ao_progresso)
        results.append(result)
        if result.get('success'):
            total_chunks += result.get('chunks', 0)

    return {
        'files': results,
        'total_chunks': total_chunks,
        'file_count': n_arquivos
    }


def _index_text_in_batches(topic_name, source_name, text, user_id,
                           source_type='document',
                           batch_size=None,
                           max_workers=None,
                           ao_progresso=None):
    if not text or not text.strip():
        return 0

    if batch_size is None:
        batch_size = INDEX_BATCH_SIZE
    if max_workers is None:
        max_workers = INDEX_MAX_WORKERS

    chunks = chunk_text(
        text, target_size=CHUNK_TARGET_SIZE, overlap=CHUNK_OVERLAP
    )
    if not chunks:
        return 0

    batches = [
        chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)
    ]
    logger.info(
        f"Indexando '{source_name}' em {len(batches)} lotes "
        f"({len(chunks)} chunks no total)."
    )

    def send_batch(batch_start_idx, batch):
        metadatas = []
        for i in range(len(batch)):
            metadatas.append({
                'topic': topic_name,
                'source': source_name,
                'chunk_index': batch_start_idx + i,
                'type': source_type,
                'user_id': str(user_id)
            })
        return index_documents(batch, metadatas)

    success = 0
    concluidos = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(send_batch, i * batch_size, batch)
            for i, batch in enumerate(batches)
        ]
        for fut in as_completed(futures):
            try:
                result = fut.result()
                if result and result.get('status') == 'ok':
                    success += result.get('count', 0)
            except Exception as e:
                logger.error(f"Falha ao indexar lote: {e}")
            concluidos += 1
            if ao_progresso:
                ao_progresso(
                    10 + int((concluidos / len(batches)) * 88),
                    f'Indexando lote {concluidos}/{len(batches)}'
                )

    logger.info(f"Indexação de '{source_name}': {success} chunks indexados.")
    return success


@upload_bp.route('/topic/<topic_name>/upload', methods=['GET', 'POST'])
@login_required
def upload_pdf(topic_name):
    if request.method == 'POST':
        if 'pdf' not in request.files:
            if request.accept_mimetypes.accept_json:
                return jsonify({
                    'success': False, 'error': 'Nenhum arquivo enviado.'
                }), 400
            flash('Nenhum arquivo enviado.', 'error')
            return redirect(request.url)

        arquivos = [
            f for f in request.files.getlist('pdf') if f and f.filename
        ]
        if not arquivos:
            if request.accept_mimetypes.accept_json:
                return jsonify({
                    'success': False, 'error': 'Nenhum arquivo selecionado.'
                }), 400
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)

        extensoes_invalidas = [
            f.filename for f in arquivos
            if os.path.splitext(f.filename)[1].lower()
            not in EXTENSOES_DOCUMENTO
        ]
        if extensoes_invalidas:
            if request.accept_mimetypes.accept_json:
                return jsonify({
                    'success': False,
                    'error': (
                        'Tipo de arquivo não permitido. Envie PDF, '
                        'PowerPoint (.pptx/.ppt) ou Word (.docx/.doc).'
                    )
                }), 400
            flash(
                'Tipo de arquivo não permitido. Envie PDF, PowerPoint ou Word.',
                'error'
            )
            return redirect(request.url)

        file_data_list = [
            {
                'filename': secure_filename(f.filename),
                'content': f.read(),
                'content_type': f.content_type or 'application/octet-stream'
            }
            for f in arquivos
        ]

        if request.accept_mimetypes.accept_json:
            task_id, repetida = task_manager.create_task(
                'upload_documento', current_user.id,
                {
                    'topic_name': topic_name,
                    'file_count': len(file_data_list)
                },
                dedup_key=topic_name
            )
            if repetida:
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'reused': True,
                    'message': 'O envio destes documentos ja esta em andamento. Acompanhe o progresso pelo indicador de tarefas.'
                })
            user_snap = type('UserSnap', (), {
                'id': current_user.id,
                'username': current_user.username,
                'get_ollama_keys': lambda: current_user.get_ollama_keys()
            })()
            task_manager.run_async(
                task_id, _worker_upload_documento, task_id, user_snap,
                topic_name, file_data_list
            )
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': 'Upload e processamento iniciados. Acompanhe o progresso pelo indicador de tarefas.'
            })

        questions_folder = TopicModel.get_questions_folder(
            current_user, topic_name
        )
        os.makedirs(questions_folder, exist_ok=True)
        resultados = [
            _processar_documento(
                file_data, topic_name, current_user, questions_folder
            )
            for file_data in file_data_list
        ]
        falha = next(
            (r for r in resultados if not r.get('success')), None
        )
        if falha:
            flash(falha['error'], 'error')
            return redirect(request.url)
        ultimo = resultados[-1]
        flash('Arquivo enviado com sucesso!', 'success')
        session['ultimo_pdf'] = ultimo['pdf_path']
        return render_template(
            'upload_success.html', topic=topic_name,
            pdf_path=ultimo['pdf_path']
        )

    return render_template('upload_pdf.html', topic=topic_name)


def _processar_documento(file_data, topic_name, user, questions_folder,
                         ao_progresso=None):
    filename = secure_filename(file_data['filename'])
    extensao = os.path.splitext(filename)[1].lower()
    pdf_path = os.path.join(questions_folder, filename)
    with open(pdf_path, 'wb') as arquivo:
        arquivo.write(file_data['content'])

    caminho_documento = pdf_path
    pasta_temp = None
    if extensao != '.pdf':
        if ao_progresso:
            ao_progresso(5, 'Convertendo para PDF')
        try:
            caminho_documento, pasta_temp = office_service.converter_para_pdf(
                pdf_path
            )
        except Exception as e:
            logger.error(f"Erro ao converter '{filename}' para PDF: {e}")
            try:
                os.remove(pdf_path)
            except OSError:
                pass
            return {
                'success': False,
                'filename': filename,
                'error': (
                    'Não foi possível converter o documento. '
                    'Verifique se o arquivo não está corrompido.'
                )
            }

    try:
        if ao_progresso:
            ao_progresso(25, 'Extraindo imagens das páginas')
        imagens_extraidas = []
        try:
            imagens_extraidas = extract_images_from_pdf(
                caminho_documento,
                TopicModel.get_images_folder(user, topic_name)
            )
        except Exception as e:
            logger.error(f"Erro ao extrair imagens do documento: {e}")

        if ao_progresso:
            ao_progresso(40, 'Extraindo texto')
        progresso_indice = None
        if ao_progresso:
            def progresso_indice(pct, msg):
                ao_progresso(45 + int((pct - 10) * 0.55), msg)
        try:
            if extensao == '.pdf':
                raw_text = extract_text_from_uploaded_file(
                    _ObjetoArquivoMemoria(file_data), lang='por'
                )
            else:
                with open(caminho_documento, 'rb') as arquivo_convertido:
                    raw_text = extract_text_from_pdf_bytes(
                        arquivo_convertido.read(), lang='por'
                    )
            if raw_text.strip():
                _index_text_in_batches(
                    topic_name, filename, raw_text, user.id,
                    source_type='document',
                    ao_progresso=progresso_indice
                )
        except Exception as e:
            logger.error(f"Erro ao indexar texto do documento: {e}")

        if ao_progresso:
            ao_progresso(100, 'Concluído')
        return {
            'success': True,
            'filename': filename,
            'pdf_path': pdf_path,
            'extracted_images': len(imagens_extraidas)
        }
    finally:
        if pasta_temp:
            office_service.limpar(pasta_temp)


def _worker_upload_documento(task_id, user_snap, topic_name, file_data_list):
    results = []
    n_arquivos = len(file_data_list)
    questions_folder = TopicModel.get_questions_folder(user_snap, topic_name)
    os.makedirs(questions_folder, exist_ok=True)

    for indice, file_data in enumerate(file_data_list):
        nome = secure_filename(file_data['filename'])

        def ao_progresso(pct_interno, mensagem, _indice=indice, _nome=nome):
            amplitude = 100 / n_arquivos
            progresso = int(
                (_indice * amplitude) + (pct_interno * amplitude / 100)
            )
            task_manager.update_task(
                task_id,
                progress=min(progresso, 99),
                message=f'{_nome}: {mensagem}'
            )

        task_manager.update_task(
            task_id,
            message=f'Processando {indice + 1}/{n_arquivos}: {nome}'
        )
        results.append(
            _processar_documento(
                file_data, topic_name, user_snap, questions_folder,
                ao_progresso
            )
        )

    return {'files': results, 'file_count': n_arquivos}


@upload_bp.route(
    '/topic/<topic_name>/upload_images', methods=['GET', 'POST']
)
@login_required
def upload_images(topic_name):
    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'endpoint': 'upload_images',
            'method': 'POST',
            'message': 'Utilize POST multipart/form-data com o campo "images".'
        }), 200

    if 'images' not in request.files:
        return jsonify({
            'success': False, 'error': 'Nenhum arquivo enviado.'
        }), 400

    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        return jsonify({
            'success': False, 'error': 'Nenhum arquivo selecionado.'
        }), 400
    if len(files) > Config.UPLOAD_MAX_FILES:
        return jsonify({
            'success': False,
            'error': f'Máximo de {Config.UPLOAD_MAX_FILES} arquivos por vez.'
        }), 400

    nao_suportados = [
        f.filename for f in files
        if not allowed_file(f.filename, ALLOWED_IMAGE_EXTENSIONS)
    ]
    if nao_suportados:
        return jsonify({
            'success': False,
            'error': 'Formatos não suportados: '
                     + ', '.join(nao_suportados)
                     + '. Envie imagens PNG, JPG ou JPEG.'
        }), 400

    files_data = []
    for f in files:
        f.seek(0)
        files_data.append({
            'filename': f.filename,
            'content': f.read(),
            'content_type': f.content_type or 'application/octet-stream'
        })

    task_id, repetida = task_manager.create_task('upload_images', current_user.id, {
        'topic_name': topic_name,
        'file_count': len(files_data)
    }, dedup_key=topic_name)

    if repetida:
        return jsonify({'success': True, 'task_id': task_id, 'reused': True, 'message': 'O envio destes arquivos ja esta em andamento. Acompanhe o progresso pelo indicador de tarefas.'})

    user_snap = type('UserSnap', (), {
        'id': current_user.id,
        'username': current_user.username,
        'get_ollama_keys': lambda: current_user.get_ollama_keys()
    })()

    task_manager.run_async(
        task_id, _worker_upload_images, task_id, user_snap, topic_name,
        files_data
    )

    return jsonify({
        'success': True,
        'task_id': task_id,
        'count': len(files_data),
        'message': 'Envio iniciado. Acompanhe o progresso pelo indicador de tarefas.'
    })


class _ObjetoArquivoMemoria:
    def __init__(self, dados):
        self._dados = dados
        self._pos = 0

    @property
    def filename(self):
        return self._dados['filename']

    @property
    def content_type(self):
        return self._dados.get('content_type', '')

    def seek(self, pos):
        self._pos = pos

    def read(self, size=-1):
        if size == -1:
            resultado = self._dados['content'][self._pos:]
            self._pos = len(self._dados['content'])
        else:
            resultado = self._dados['content'][self._pos:self._pos + size]
            self._pos += len(resultado)
        return resultado

    def save(self, caminho):
        with open(caminho, 'wb') as arquivo:
            arquivo.write(self._dados['content'])


def _worker_upload_images(task_id, user_snap, topic_name, files_data):
    objetos = [_ObjetoArquivoMemoria(dados) for dados in files_data]
    destino = TopicModel.get_images_folder(user_snap, topic_name)
    saved_count, saved_names = save_uploaded_images(
        objetos, destino, max_files=Config.UPLOAD_MAX_FILES
    )

    erros = []
    total = len(objetos)
    for indice, arquivo in enumerate(objetos):
        task_manager.update_task(
            task_id,
            progress=int((indice / max(total, 1)) * 100),
            message=f'Reconhecendo texto {indice + 1}/{total}: {arquivo.filename}'
        )
        try:
            arquivo.seek(0)
            raw_text = extract_text_from_uploaded_file(arquivo, lang='por')
            if raw_text.strip():
                _index_text_in_batches(
                    topic_name, arquivo.filename, raw_text, user_snap.id,
                    source_type='image'
                )
        except Exception as e:
            logger.error(f"Erro ao indexar imagem {arquivo.filename}: {e}")
            erros.append(arquivo.filename)

    return {
        'count': saved_count,
        'names': saved_names,
        'erros': erros
    }


@upload_bp.route('/topic/<topic_name>/extrair', methods=['POST'])
@login_required
def extrair_imagens(topic_name):
    pdf_path = request.form.get('pdf_path')
    if pdf_path:
        try:
            base_usuario = TopicModel.get_user_base_dir(current_user)
            pdf_path = TopicModel.garantir_dentro(base_usuario, pdf_path)
        except BadRequest:
            logger.warning(
                f"[UPLOAD] pdf_path fora da pasta do usuário recusado "
                f"(user={current_user.username})."
            )
            pdf_path = None
    if not pdf_path or not os.path.exists(pdf_path):
        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': False, 'error': 'Arquivo PDF não encontrado.'
            }), 400
        flash('Arquivo PDF não encontrado.', 'error')
        return redirect(url_for('topic.ver_topic', topic_name=topic_name))

    destino = TopicModel.get_images_folder(current_user, topic_name)
    try:
        imagens_geradas = extract_images_from_pdf(pdf_path, destino)

        def process_image(img):
            img_path = os.path.join(destino, img)
            try:
                with open(img_path, 'rb') as f:
                    raw_text = extract_text_from_uploaded_file(f, lang='por')
                if raw_text.strip():
                    _index_text_in_batches(
                        topic_name, img, raw_text, current_user.id,
                        source_type='image'
                    )
            except Exception as e:
                logger.error(f"Erro ao indexar imagem extraída {img}: {e}")

        if imagens_geradas:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(process_image, img)
                    for img in imagens_geradas
                ]
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception as e:
                        logger.warning(f"Falha em worker de indexação: {e}")

        if request.accept_mimetypes.accept_json:
            return jsonify({
                'success': True, 'count': len(imagens_geradas)
            })
        flash(
            f'{len(imagens_geradas)} imagens extraídas com sucesso!',
            'success'
        )
    except Exception as e:
        if request.accept_mimetypes.accept_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Erro ao extrair imagens: {str(e)}', 'error')

    return redirect(url_for('topic.ver_topic', topic_name=topic_name))


@upload_bp.route('/topic/<topic_name>/upload_rag', methods=['GET'])
@login_required
def upload_rag_page(topic_name):
    return jsonify({
        'status': 'ok',
        'endpoint': 'upload_rag',
        'method': 'POST',
        'message': 'Utilize POST multipart/form-data com o campo "file".'
    }), 200


def save_extracted_text(user, topic_name, text, base_filename):
    folder = TopicModel.get_material_folder(user, topic_name)
    if not folder:
        raise ValueError('Usuário inválido para salvar o texto extraído.')
    os.makedirs(folder, exist_ok=True)
    txt_filename = (
        os.path.splitext(base_filename)[0] + '_texto_extraido.txt'
    )
    txt_path = os.path.join(folder, txt_filename)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return txt_path, txt_filename


SUFIXO_TEXTO_EXTRAIDO = '_texto_extraido.txt'


def _arquivos_da_pasta(pasta, tipo, base):
    arquivos = []
    if not pasta or not os.path.exists(pasta):
        return arquivos
    for nome in os.listdir(pasta):
        caminho = os.path.join(pasta, nome)
        if not os.path.isfile(caminho):
            continue
        arquivos.append({
            'name': nome,
            'type': tipo,
            'folder': base,
            'size': os.path.getsize(caminho),
            'modified': os.path.getmtime(caminho)
        })
    return arquivos


@upload_bp.route('/topic/<topic_name>/files', methods=['GET'])
@login_required
def list_files(topic_name):
    images_folder = TopicModel.get_images_folder(
        current_user, topic_name
    )
    questions_folder = TopicModel.get_questions_folder(
        current_user, topic_name
    )
    arquivos = _arquivos_da_pasta(images_folder, 'image', 'images')
    for arquivo in _arquivos_da_pasta(questions_folder, 'document', 'questions'):
        if arquivo['name'].endswith(SUFIXO_TEXTO_EXTRAIDO):
            continue
        arquivos.append(arquivo)
    padrao_pagina = re.compile(r'_pag\d{3}\.png$', re.IGNORECASE)
    arquivos = [a for a in arquivos if not (a['type'] == 'image' and padrao_pagina.search(a['name']))]
    response = jsonify(arquivos)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@upload_bp.route('/topic/<topic_name>/material_files', methods=['GET'])
@login_required
def list_material_files(topic_name):
    material_folder = TopicModel.get_material_folder(
        current_user, topic_name
    )
    questions_folder = TopicModel.get_questions_folder(
        current_user, topic_name
    )
    arquivos = _arquivos_da_pasta(material_folder, 'document', 'material')
    for arquivo in _arquivos_da_pasta(questions_folder, 'document', 'questions'):
        if not arquivo['name'].endswith(SUFIXO_TEXTO_EXTRAIDO):
            continue
        arquivos.append(arquivo)
    arquivos.sort(key=lambda a: a['modified'], reverse=True)
    response = jsonify(arquivos)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@upload_bp.route(
    '/topic/<topic_name>/delete_file/<filename>', methods=['POST']
)
@login_required
def delete_file(topic_name, filename):
    images_folder = TopicModel.get_images_folder(
        current_user, topic_name
    )
    questions_folder = TopicModel.get_questions_folder(
        current_user, topic_name
    )
    whiteboards_folder = TopicModel.get_whiteboards_folder(
        current_user, topic_name
    )
    material_folder = TopicModel.get_material_folder(
        current_user, topic_name
    )
    deleted = False
    filepath = None
    fontes_removidas = []

    if os.path.exists(TopicModel.arquivo_dentro(questions_folder, filename)):
        filepath = TopicModel.arquivo_dentro(questions_folder, filename)
    elif os.path.exists(TopicModel.arquivo_dentro(material_folder, filename)):
        filepath = TopicModel.arquivo_dentro(material_folder, filename)
    elif os.path.exists(TopicModel.arquivo_dentro(images_folder, filename)):
        filepath = TopicModel.arquivo_dentro(images_folder, filename)
    elif os.path.exists(TopicModel.arquivo_dentro(whiteboards_folder, filename)):
        filepath = TopicModel.arquivo_dentro(whiteboards_folder, filename)

    if not filepath:
        return jsonify({
            'success': False, 'error': 'Arquivo não encontrado.'
        }), 404

    extensao = os.path.splitext(filename)[1].lower()
    if extensao in EXTENSOES_DOCUMENTO:
        base_name = os.path.splitext(filename)[0]
        if os.path.exists(images_folder):
            for img_file in os.listdir(images_folder):
                if (img_file.startswith(base_name)
                        and img_file.lower().endswith(
                            ('.png', '.jpg', '.jpeg')
                        )):
                    try:
                        os.remove(os.path.join(images_folder, img_file))
                        fontes_removidas.append(img_file)
                    except Exception:
                        pass
        if os.path.exists(whiteboards_folder):
            for wb_file in os.listdir(whiteboards_folder):
                if wb_file.startswith('whiteboard_' + base_name):
                    try:
                        os.remove(os.path.join(whiteboards_folder, wb_file))
                    except Exception:
                        pass
        TopicModel.delete_image_references(
            current_user, topic_name, base_name
        )
        os.remove(filepath)
        fontes_removidas.append(filename)
        deleted = True
    else:
        if filepath.startswith(images_folder):
            if TopicModel.delete_image_file(
                current_user, topic_name, filename
            ):
                deleted = True
                fontes_removidas.append(filename)
        else:
            os.remove(filepath)
            deleted = True
            fontes_removidas.append(filename)

    if deleted:
        for fonte in fontes_removidas:
            try:
                remove_topic_vectors(
                    topic_name, user_id=current_user.id, source=fonte
                )
            except Exception as e:
                logger.warning(
                    f"Falha ao remover vetores de '{fonte}': {e}"
                )
        return jsonify({'success': True})
    return jsonify({
        'success': False, 'error': 'Falha ao excluir arquivo.'
    }), 500