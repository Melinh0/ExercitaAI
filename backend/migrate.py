import os
import shutil
from app import app, db
from models.user_model import User
from models.topic_model import TopicModel

def sync_env_keys(user):

    atualizou = False

    ollama_key = os.getenv('OLLAMA_API_KEY', '')
    env_ollama_keys = [k.strip() for k in ollama_key.split(',') if k.strip()]
    try:
        atuais = user.get_ollama_keys()
    except Exception:
        atuais = []
    novas = [k for k in env_ollama_keys if k not in atuais]
    if novas:
        user.set_ollama_keys(atuais + novas)
        atualizou = True
        print(f"{len(novas)} chave(s) OLLAMA_API_KEY do .env adicionada(s) ao usuário Yago.")

    ocr_key = os.getenv('OCR_SPACE_API_KEY', '')
    if ocr_key:
        try:
            ocr_atuais = user.get_ocr_keys()
        except Exception:
            ocr_atuais = []
        if ocr_key not in ocr_atuais:
            user.set_ocr_keys(ocr_atuais + [ocr_key])
            atualizou = True
            print("Chave OCR_SPACE_API_KEY do .env adicionada ao usuário Yago.")

    if atualizou:
        db.session.commit()
    else:
        print("Chaves do .env já cadastradas no usuário Yago.")


def adicionar_colunas_faltantes():
    from sqlalchemy import text

    novas_colunas = {
        User.__tablename__: {
            'reset_token_hash': 'VARCHAR(64)',
            'reset_expires_at': 'DATETIME',
        },
    }

    with db.engine.begin() as conn:
        for tabela, colunas in novas_colunas.items():
            existentes = {
                linha[1] for linha in conn.execute(text(f"PRAGMA table_info({tabela})"))
            }
            for nome, tipo in colunas.items():
                if nome in existentes:
                    continue
                conn.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))
                print(f"Coluna {tabela}.{nome} adicionada.")


def reparar_textos_corrompidos():
    from sqlalchemy import text
    from services.json_modelo import reparar_texto_latex

    alvos = [
        ('question', 'explicacao'),
        ('question', 'enunciado'),
        ('question', 'resposta'),
        ('topic_image', 'texto'),
    ]

    with db.engine.begin() as conn:
        for tabela, coluna in alvos:
            atualizados = 0
            consulta = text(f"SELECT id, {coluna} FROM {tabela} WHERE {coluna} IS NOT NULL")
            for lid, valor in conn.execute(consulta):
                novo = reparar_texto_latex(valor)
                if novo != valor:
                    conn.execute(
                        text(f"UPDATE {tabela} SET {coluna} = :novo WHERE id = :lid"),
                        {'novo': novo, 'lid': lid},
                    )
                    atualizados += 1
            if atualizados:
                print(f"{atualizados} texto(s) de {tabela}.{coluna} reparado(s).")


def remover_contas_de_teste():
    padroes = ('testelan-%@example.com', 'sugtest-%@example.com', 'ragtest-%@teste.dev')
    removidos = 0
    for padrao in padroes:
        for usuario in User.query.filter(User.email.like(padrao)).all():
            db.session.delete(usuario)
            print(f"Conta de teste removida: {usuario.email}.")
            removidos += 1
    if removidos:
        db.session.commit()


def remover_pastas_orfas():
    from models.topic_model import Topic

    prefixo = 'teste-'
    removidos = 0
    for usuario in User.query.all():
        base = TopicModel.get_user_base_dir(usuario)
        if not base:
            continue
        existentes = {
            topico.nome for topico in
            Topic.query.filter_by(user_id=usuario.id).all()
        }
        pastas = [
            os.path.join(base, 'static', 'images', 'topics'),
            os.path.join(base, 'static', 'whiteboards', 'topics'),
            os.path.join(base, 'questions'),
            os.path.join(base, 'material_apoio', 'topics'),
        ]
        for pasta in pastas:
            if not os.path.isdir(pasta):
                continue
            for item in os.listdir(pasta):
                if not item.startswith(prefixo) or item in existentes:
                    continue
                caminho = os.path.join(pasta, item)
                try:
                    if os.path.isdir(caminho):
                        shutil.rmtree(caminho)
                    else:
                        os.remove(caminho)
                    removidos += 1
                except OSError:
                    pass
    if removidos:
        print(f"{removidos} pasta(s) temporaria(s) de teste removida(s).")


def migrate():
    with app.app_context():
        db.create_all()
        adicionar_colunas_faltantes()
        reparar_textos_corrompidos()
        remover_contas_de_teste()

        user = User.query.filter_by(email='yago.costa@aluno.uece.br').first()
        if not user:
            user = User(username='Yago', email='yago.costa@aluno.uece.br')
            user.set_password('yago1234')
            ollama_key = os.getenv('OLLAMA_API_KEY', '')
            ocr_key = os.getenv('OCR_SPACE_API_KEY', '')
            ollama_keys = [k.strip() for k in ollama_key.split(',') if k.strip()]
            if ollama_keys:
                user.set_ollama_keys(ollama_keys)
            if ocr_key:
                user.set_ocr_keys([ocr_key])
            db.session.add(user)
            db.session.commit()
            print("Usuário Yago criado.")
        else:
            print("Usuário Yago já existe.")
            sync_env_keys(user)

        TopicModel.create_user_dirs(user)

        old_dirs = [
            os.path.join(app.config['BASE_DIR'], 'data', 'topics'),
            os.path.join(app.config['BASE_DIR'], 'static', 'images', 'topics'),
            os.path.join(app.config['BASE_DIR'], 'static', 'whiteboards', 'topics'),
            os.path.join(app.config['BASE_DIR'], 'questions')
        ]

        user_dirs = [
            TopicModel.get_topics_folder(user),
            os.path.join(TopicModel.get_user_base_dir(user), 'static', 'images', 'topics'),
            os.path.join(TopicModel.get_user_base_dir(user), 'static', 'whiteboards', 'topics'),
            os.path.join(TopicModel.get_user_base_dir(user), 'questions')
        ]

        for src, dst in zip(old_dirs, user_dirs):
            if os.path.exists(src):
                os.makedirs(dst, exist_ok=True)
                for item in os.listdir(src):
                    src_item = os.path.join(src, item)
                    dst_item = os.path.join(dst, item)
                    if os.path.exists(dst_item):
                        if os.path.isdir(dst_item):
                            shutil.rmtree(dst_item)
                        else:
                            os.remove(dst_item)
                    shutil.move(src_item, dst_item)
                print(f"Conteúdo de {src} movido para {dst}.")
            else:
                print(f"Pasta antiga {src} não existe, ignorando.")

        print("Migração concluída.")
        remover_pastas_orfas()

if __name__ == '__main__':
    migrate()