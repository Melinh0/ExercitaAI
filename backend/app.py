from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
import os
import shutil
import threading
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import configure_mappers
from config import Config
from models.user_model import db, User
from models.topic_model import (
    TopicModel,
    migrar_conteudo_legado,
    importar_respostas_legadas,
)
from controllers.api_controller import api_bp
from controllers.download_controller import download_bp
from controllers.question_controller import question_bp
from controllers.topic_controller import topic_bp
from controllers.upload_controller import upload_bp
from controllers.note_controller import note_bp
from controllers.article_controller import article_bp
from controllers.task_controller import task_bp
from auth import auth_bp
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, origins=['http://localhost:3000'], supports_credentials=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.config['BASE_DIR'], 'data', 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'timeout': 30},
    'pool_pre_ping': True,
}
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

if not app.config.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = os.urandom(24)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['BASE_DIR'] = BASE_DIR


@event.listens_for(Engine, 'connect')
def _configurar_sqlite(dbapi_conexao, _registro):
    cursor = dbapi_conexao.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


def _remover_pasta_do_usuario(_mapper, _conexao, usuario):
    try:
        pasta = TopicModel.get_user_base_dir(usuario)
        if os.path.isdir(pasta):
            shutil.rmtree(pasta, ignore_errors=True)
            print(f"Pasta do usuário {usuario.username} removida do disco.")
    except Exception as erro:
        print(f"Falha ao remover pasta do usuário {getattr(usuario, 'username', '?')}: {erro}")


def _reconciliar_pastas_e_registros():
    raiz = os.path.join(BASE_DIR, 'data', 'users')
    if not os.path.isdir(raiz):
        return
    donos = set()
    for usuario in User.query.all():
        pasta = TopicModel.get_user_base_dir(usuario)
        donos.add(os.path.basename(pasta))
        if not os.path.isdir(pasta):
            db.session.delete(usuario)
            print(f"Usuário {usuario.username} removido do banco: pasta inexistente.")
    db.session.commit()
    if not donos:
        return
    for pasta in os.listdir(raiz):
        caminho = os.path.join(raiz, pasta)
        if os.path.isdir(caminho) and pasta not in donos:
            shutil.rmtree(caminho, ignore_errors=True)
            print(f"Pasta órfã removida: {pasta} (sem registro no banco).")


app.register_blueprint(api_bp)
app.register_blueprint(download_bp)
app.register_blueprint(question_bp)
app.register_blueprint(topic_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(note_bp)
app.register_blueprint(article_bp)
app.register_blueprint(task_bp)
app.register_blueprint(auth_bp)

with app.app_context():
    db.create_all()
    configure_mappers()
    event.listen(User, 'after_delete', _remover_pasta_do_usuario)
    _reconciliar_pastas_e_registros()
    migrar_conteudo_legado()
    importar_respostas_legadas()

if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from services import model_info_service
        threading.Thread(
            target=model_info_service.garantir_textos,
            daemon=True,
            name='verifica_model_info',
        ).start()
    app.run(debug=True, host='0.0.0.0', exclude_patterns=['*/.venv/*'])
