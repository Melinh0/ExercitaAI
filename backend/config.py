import os

from dotenv import load_dotenv

load_dotenv()


def _secret_key():
    chave = os.getenv('SECRET_KEY', '').strip()
    if chave:
        return chave
    print(
        "[AVISO] SECRET_KEY não definida no .env — usando valor padrão. "
        "Gere uma chave real (ex.: python -c \"import secrets; "
        "print(secrets.token_hex(32))\") e cadastre SECRET_KEY no .env."
    )
    return 'sua_chave_secreta_aqui'


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TOPICS_FOLDER = os.path.join(BASE_DIR, 'data', 'topics')
    IMAGES_TOPICS_FOLDER = os.path.join(BASE_DIR, 'static', 'images', 'topics')
    WHITEBOARDS_TOPICS_FOLDER = os.path.join(BASE_DIR, 'static', 'whiteboards', 'topics')
    QUESTIONS_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'questions')
    SECRET_KEY = _secret_key()

    EMAIL_HOST = os.getenv('EMAIL_HOST', '')
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').strip().lower() in ('1', 'true', 'yes', 'on')
    EMAIL_FROM = os.getenv('EMAIL_FROM', '') or (EMAIL_HOST_USER or 'nao-responda@localhost')
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    RESET_TOKEN_MINUTES = int(os.getenv('RESET_TOKEN_MINUTES', '30'))

    AUTH_LOGIN_MAX_TENTATIVAS = int(os.getenv('AUTH_LOGIN_MAX_TENTATIVAS', '5'))
    AUTH_LOGIN_JANELA_MIN = int(os.getenv('AUTH_LOGIN_JANELA_MIN', '15'))
    AUTH_CADASTRO_MAX = int(os.getenv('AUTH_CADASTRO_MAX', '5'))
    AUTH_CADASTRO_JANELA_H = int(os.getenv('AUTH_CADASTRO_JANELA_H', '1'))
    AUTH_RESET_MAX = int(os.getenv('AUTH_RESET_MAX', '5'))
    AUTH_RESET_JANELA_H = int(os.getenv('AUTH_RESET_JANELA_H', '1'))
    RAG_SERVICE_URL = os.getenv('RAG_SERVICE_URL', 'http://llm_api:8001')
    OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY', '')
    DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'gemma3:4b')

    RAG_SIMILARITY_THRESHOLD = float(os.getenv('RAG_SIMILARITY_THRESHOLD', '0.60'))
    RAG_N_RESULTS = int(os.getenv('RAG_N_RESULTS', '8'))

    REFINEMENT_INTERACTIONS = int(os.getenv('REFINEMENT_INTERACTIONS', '3'))

    OCR_MAX_WORKERS = int(os.getenv('OCR_MAX_WORKERS', '16'))
    UPLOAD_MAX_FILES = int(os.getenv('UPLOAD_MAX_FILES', '100'))
    OCR_DPI = int(os.getenv('OCR_DPI', '200'))

    OCR_SPACE_CONNECT_TIMEOUT = int(os.getenv('OCR_SPACE_CONNECT_TIMEOUT', '10'))
    OCR_SPACE_READ_TIMEOUT = int(os.getenv('OCR_SPACE_READ_TIMEOUT', '30'))
    OCR_SPACE_MAX_FAILURES = int(os.getenv('OCR_SPACE_MAX_FAILURES', '3'))
    OCR_SPACE_MAX_PAGES = int(os.getenv('OCR_SPACE_MAX_PAGES', '500'))

    INDEX_CHUNK_TARGET_SIZE = int(os.getenv('INDEX_CHUNK_TARGET_SIZE', '1000'))
    INDEX_CHUNK_OVERLAP = int(os.getenv('INDEX_CHUNK_OVERLAP', '100'))
    INDEX_BATCH_SIZE = int(os.getenv('INDEX_BATCH_SIZE', '100'))
    INDEX_MAX_WORKERS = int(os.getenv('INDEX_MAX_WORKERS', '4'))

    OLLAMA_RATE_LIMIT_BACKOFF_BASE = float(os.getenv('OLLAMA_RATE_LIMIT_BACKOFF_BASE', '5'))
    OLLAMA_RATE_LIMIT_MAX_BACKOFF = float(os.getenv('OLLAMA_RATE_LIMIT_MAX_BACKOFF', '120'))


RAG_SERVICE_URL = Config.RAG_SERVICE_URL
DEFAULT_MODEL = Config.DEFAULT_MODEL
REFINEMENT_INTERACTIONS = Config.REFINEMENT_INTERACTIONS