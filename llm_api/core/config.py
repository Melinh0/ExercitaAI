import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PACOTE_DIR = Path(__file__).resolve().parent.parent
TOPICS_FOLDER = BASE_DIR / "backend" / "data" / "topics"
IMAGES_TOPICS_FOLDER = BASE_DIR / "backend" / "static" / "images" / "topics"

CHROMA_DIR = PACOTE_DIR / "chroma_db"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"

HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN
    os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_API_KEYS = [k.strip() for k in (OLLAMA_API_KEY or "").split(",") if k.strip()]
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")

OLLAMA_AVAILABLE_MODELS = os.getenv("OLLAMA_AVAILABLE_MODELS", "")
AVAILABLE_MODELS_LIST = [m.strip() for m in OLLAMA_AVAILABLE_MODELS.split(",") if m.strip()]

OLLAMA_VISION_MODELS = os.getenv("OLLAMA_VISION_MODELS", "")
VISION_MODELS_LIST = [m.strip() for m in OLLAMA_VISION_MODELS.split(",") if m.strip()]

OLLAMA_FREE_MODELS = os.getenv("OLLAMA_FREE_MODELS", "")
FREE_MODELS_LIST = [m.strip() for m in OLLAMA_FREE_MODELS.split(",") if m.strip()] or [
    "beam",
    "gemma4:31b",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "nemotron-3-nano:30b",
    "nemotron-3-super",
    "nemotron-3-ultra",
]

TOP_K = 8

CORRECTIONS_COLLECTION = "corrections"
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))

OLLAMA_MAX_CONCURRENT_REQUESTS = int(os.getenv("OLLAMA_MAX_CONCURRENT_REQUESTS", "4"))
OLLAMA_MIN_REQUEST_INTERVAL = float(os.getenv("OLLAMA_MIN_REQUEST_INTERVAL", "0.5"))
OLLAMA_RATE_LIMIT_BACKOFF_BASE = float(os.getenv("OLLAMA_RATE_LIMIT_BACKOFF_BASE", "5"))
OLLAMA_RATE_LIMIT_MAX_BACKOFF = float(os.getenv("OLLAMA_RATE_LIMIT_MAX_BACKOFF", "120"))
OLLAMA_KEY_RECOVERY_SECONDS = int(os.getenv("OLLAMA_KEY_RECOVERY_SECONDS", "900"))