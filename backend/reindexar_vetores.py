import argparse
import logging
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

from services.chunking import chunk_text
from services.ocr_service import (
    EXTENSOES_TEXTO_SIMPLES,
    extract_text_from_uploaded_file,
)

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE_DIR, 'data', 'users')
DB_PATH = os.path.join(BASE_DIR, 'data', 'users.db')

ALVO_CHUNK = int(os.getenv('INDEX_CHUNK_TARGET_SIZE', '1000'))
SOBREPOSICAO_CHUNK = int(os.getenv('INDEX_CHUNK_OVERLAP', '100'))
TAMANHO_LOTE = int(os.getenv('INDEX_BATCH_SIZE', '100'))
TRABALHADORES_PADRAO = int(os.getenv('INDEX_MAX_WORKERS', '4'))

PADRAO_PAGINA = re.compile(r'_pag\d{3}\.png$', re.IGNORECASE)
EXTENSOES_DOCUMENTO = EXTENSOES_TEXTO_SIMPLES | {'.json', '.pdf', '.docx', '.pptx'}
EXTENSOES_IMAGEM = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}

logger = logging.getLogger('reindexacao')


class _ArquivoMemoria:
    def __init__(self, nome, dados):
        self.filename = nome
        self._dados = dados
        self._pos = 0

    def seek(self, pos):
        self._pos = pos

    def read(self, tamanho=-1):
        if tamanho < 0:
            parte = self._dados[self._pos:]
            self._pos = len(self._dados)
        else:
            parte = self._dados[self._pos:self._pos + tamanho]
            self._pos += len(parte)
        return parte


def _username_seguro(nome):
    return re.sub(r'[^\w\-_]', '_', nome)


def carregar_usuarios():
    conexao = sqlite3.connect(DB_PATH)
    try:
        linhas = conexao.execute('SELECT id, username FROM user').fetchall()
    finally:
        conexao.close()
    return {_username_seguro(username): user_id for user_id, username in linhas}


def coletar_tarefas(pular_imagens):
    usuarios = carregar_usuarios()
    tarefas = []
    for nome_dir in sorted(os.listdir(USERS_DIR)):
        pasta_usuario = os.path.join(USERS_DIR, nome_dir)
        if not os.path.isdir(pasta_usuario):
            continue
        user_id = usuarios.get(nome_dir)
        if user_id is None:
            logger.warning(f"Pasta de usuario '{nome_dir}' sem cadastro no banco - ignorada")
            continue
        fontes_por_topico = {}
        for relativa, tipo in (
            ('questions', 'documento'),
            ('material_apoio/topics', 'documento'),
            ('static/images/topics', 'imagem'),
        ):
            pasta_base = os.path.join(pasta_usuario, relativa)
            if not os.path.isdir(pasta_base):
                continue
            for nome_topico in os.listdir(pasta_base):
                pasta_topico = os.path.join(pasta_base, nome_topico)
                if not os.path.isdir(pasta_topico):
                    continue
                fontes_por_topico.setdefault(nome_topico, []).append((pasta_topico, tipo))
        for nome_topico, fontes in fontes_por_topico.items():
            for pasta_topico, tipo in fontes:
                if tipo == 'imagem' and pular_imagens:
                    continue
                for nome_arquivo in sorted(os.listdir(pasta_topico)):
                    caminho = os.path.join(pasta_topico, nome_arquivo)
                    if not os.path.isfile(caminho) or nome_arquivo.startswith('.'):
                        continue
                    extensao = os.path.splitext(nome_arquivo)[1].lower()
                    if tipo == 'imagem':
                        if PADRAO_PAGINA.search(nome_arquivo):
                            continue
                        if extensao not in EXTENSOES_IMAGEM:
                            continue
                    elif extensao not in EXTENSOES_DOCUMENTO:
                        continue
                    tarefas.append({
                        'caminho': caminho,
                        'nome': nome_arquivo,
                        'topico': nome_topico,
                        'tipo': tipo,
                        'user_id': user_id,
                    })
    return tarefas


def extrair_lotes(tarefa):
    try:
        with open(tarefa['caminho'], 'rb') as arquivo:
            dados = arquivo.read()
        texto = extract_text_from_uploaded_file(
            _ArquivoMemoria(tarefa['nome'], dados), lang='por'
        )
    except Exception as e:
        logger.error(f"Falha ao extrair '{tarefa['nome']}' ({tarefa['topico']}): {e}")
        return ('falha_extracao', tarefa, [])
    if not texto or not texto.strip():
        return ('vazio', tarefa, [])
    chunks = chunk_text(texto, target_size=ALVO_CHUNK, overlap=SOBREPOSICAO_CHUNK)
    if not chunks:
        return ('vazio', tarefa, [])
    metadatas = [
        {
            'topic': tarefa['topico'],
            'source': tarefa['nome'],
            'chunk_index': indice,
            'type': tarefa['tipo'],
            'user_id': str(tarefa['user_id']),
        }
        for indice in range(len(chunks))
    ]
    lotes = [
        (chunks[i:i + TAMANHO_LOTE], metadatas[i:i + TAMANHO_LOTE])
        for i in range(0, len(chunks), TAMANHO_LOTE)
    ]
    return ('ok', tarefa, lotes)


def processar_arquivo(servidor, tarefa):
    situacao, _, lotes = extrair_lotes(tarefa)
    if situacao != 'ok':
        return situacao, 0, 0, 0
    aceitos = 0
    novos = 0
    falhas = 0
    for chunks, metadatas in lotes:
        resultado = enviar_lote(servidor, chunks, metadatas)
        if resultado and resultado.get('status') == 'ok':
            aceitos += resultado.get('count', 0)
            novos += resultado.get('novos', 0)
        else:
            falhas += 1
    return 'ok', aceitos, novos, falhas


def enviar_lote(servidor, chunks, metadatas, tentativas=4):
    corpo = {'chunks': chunks, 'metadatas': metadatas}
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(
                f'{servidor}/index_documents', json=corpo, timeout=300
            )
            if resp.ok:
                return resp.json()
            logger.warning(
                f'/index_documents recusou lote ({resp.status_code}): {resp.text[:160]}'
            )
        except requests.RequestException as e:
            logger.warning(f'Erro ao enviar lote (tentativa {tentativa}): {e}')
        time.sleep(3 * tentativa)
    return None


def enviar_exemplo(servidor, exemplo, tentativas=4):
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(
                f'{servidor}/add_example', json=exemplo, timeout=60
            )
            if resp.ok:
                return True
            logger.warning(
                f'/add_example recusou exemplo ({resp.status_code}): {resp.text[:160]}'
            )
        except requests.RequestException as e:
            logger.warning(f'Erro ao enviar exemplo (tentativa {tentativa}): {e}')
        time.sleep(2 * tentativa)
    return False


def carregar_exemplos():
    conexao = sqlite3.connect(DB_PATH)
    try:
        linhas = conexao.execute(
            '''
            SELECT t.user_id, t.nome, ti.imagem, q.posicao,
                   COALESCE(NULLIF(TRIM(IFNULL(q.enunciado, '')), ''),
                            IFNULL(q.questao, '')),
                   IFNULL(q.resposta, ''),
                   IFNULL(q.explicacao, '')
            FROM question q
            JOIN topic_image ti ON ti.id = q.image_id
            JOIN topic t ON t.id = ti.topic_id
            '''
        ).fetchall()
    finally:
        conexao.close()
    exemplos = []
    for user_id, topico, imagem, posicao, enunciado, resposta, explicacao in linhas:
        enunciado = (enunciado or '').strip()
        resposta = (resposta or '').strip()
        explicacao = (explicacao or '').strip()
        exemplos.append({
            'document': (
                f'Questao: {enunciado}\n'
                f'Resposta: {resposta}\n'
                f'Explicacao: {explicacao}'
            ),
            'metadata': {
                'topic': topico,
                'image': imagem,
                'question_index': posicao,
                'enunciado': enunciado,
                'resposta': resposta,
                'explicacao': explicacao,
                'user_id': str(user_id),
            },
        })
    return exemplos


def resumo_por_topico(tarefas):
    por_topico = {}
    for tarefa in tarefas:
        chave = (tarefa['user_id'], tarefa['topico'])
        contagem = por_topico.setdefault(chave, {'documento': 0, 'imagem': 0})
        contagem[tarefa['tipo']] += 1
    for (user_id, topico), contagem in sorted(por_topico.items()):
        logger.info(
            f'  user={user_id} topico={topico!r} '
            f"documentos={contagem['documento']} imagens={contagem['imagem']}"
        )
    return por_topico


def main():
    parser = argparse.ArgumentParser(
        description='Reindexa material de apoio e exemplos existentes no banco de vetores.'
    )
    parser.add_argument('--servidor', default='http://127.0.0.1:8001', help='URL do llm_api')
    parser.add_argument('--listar', action='store_true', help='Apenas lista o que seria indexado')
    parser.add_argument('--pular-imagens', action='store_true')
    parser.add_argument('--pular-exemplos', action='store_true')
    parser.add_argument('--trabalhadores', type=int, default=TRABALHADORES_PADRAO)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    logger.info(
        f'Servidor: {args.servidor} | chunk={ALVO_CHUNK} sobreposicao={SOBREPOSICAO_CHUNK} '
        f'lote={TAMANHO_LOTE} trabalhadores={args.trabalhadores}'
    )

    tarefas = coletar_tarefas(args.pular_imagens)
    logger.info(f'{len(tarefas)} arquivos de material encontrados')
    resumo_por_topico(tarefas)

    if args.listar:
        exemplos = [] if args.pular_exemplos else carregar_exemplos()
        logger.info(f'{len(exemplos)} exemplos (questoes com resposta) seriam reenviados')
        return 0

    contagem = {'ok': 0, 'vazio': 0, 'falha_extracao': 0}
    aceitos_total = 0
    novos_total = 0
    lotes_com_falha = 0
    concluidos = 0

    with ThreadPoolExecutor(max_workers=args.trabalhadores) as executor:
        futuros = {
            executor.submit(processar_arquivo, args.servidor, tarefa): tarefa
            for tarefa in tarefas
        }
        for futuro in as_completed(futuros):
            tarefa = futuros[futuro]
            situacao, aceitos, novos, falhas = futuro.result()
            concluidos += 1
            contagem[situacao] += 1
            aceitos_total += aceitos
            novos_total += novos
            lotes_com_falha += falhas
            detalhe = f' - {aceitos} chunks ({novos} novos)' if situacao == 'ok' else ''
            logger.info(
                f'[{concluidos}/{len(tarefas)}] {tarefa["nome"]}: {situacao}{detalhe}'
            )

    exemplos_salvos = 0
    exemplos_com_falha = 0
    if not args.pular_exemplos:
        exemplos = carregar_exemplos()
        logger.info(f'Enviando {len(exemplos)} exemplos de questoes...')
        with ThreadPoolExecutor(max_workers=8) as executor:
            futuros = [
                executor.submit(enviar_exemplo, args.servidor, exemplo)
                for exemplo in exemplos
            ]
            for indice, futuro in enumerate(as_completed(futuros), start=1):
                if futuro.result():
                    exemplos_salvos += 1
                else:
                    exemplos_com_falha += 1
                if indice % 50 == 0:
                    logger.info(f'  exemplos {indice}/{len(exemplos)}')

    logger.info('=' * 60)
    logger.info(
        f"Material: {contagem['ok']} indexados, {contagem['vazio']} sem texto, "
        f"{contagem['falha_extracao']} com falha de extracao"
    )
    logger.info(
        f'Chunks aceitos: {aceitos_total} ({novos_total} novos, '
        f'{aceitos_total - novos_total} reaproveitados) | lotes com falha: {lotes_com_falha}'
    )
    if not args.pular_exemplos:
        logger.info(
            f'Exemplos: {exemplos_salvos} salvos, {exemplos_com_falha} com falha'
        )
    logger.info('=' * 60)

    problemas = (
        contagem['falha_extracao'] + lotes_com_falha + exemplos_com_falha
    )
    return 1 if problemas else 0


if __name__ == '__main__':
    raise SystemExit(main())
