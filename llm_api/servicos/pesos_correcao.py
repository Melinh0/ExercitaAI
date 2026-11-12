import json
import logging
import os

logger = logging.getLogger(__name__)

CORRECTION_WEIGHTS_FILE = os.getenv(
    "CORRECTION_WEIGHTS_FILE",
    "/app/correction_weights.json"
)
correction_weights = {}


def load_correction_weights():
    global correction_weights
    correction_weights = {}
    path = CORRECTION_WEIGHTS_FILE

    if not os.path.exists(path):
        logger.info(f"[weights] {path} nao existe. Iniciando com dicionario vazio.")
        return

    if os.path.isdir(path):
        logger.warning(
            f"[weights] {path} e um DIRETORIO (bind mount mal configurado). "
            f"Ignorando carregamento."
        )
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            correction_weights = data
            logger.info(f"[weights] Carregados {len(correction_weights)} pesos de {path}.")
        else:
            logger.warning(
                f"[weights] Conteudo de {path} nao e um dict JSON. "
                f"Iniciando com dicionario vazio."
            )
    except json.JSONDecodeError as e:
        logger.warning(f"[weights] JSON invalido em {path}: {e}. Iniciando vazio.")
    except Exception as e:
        logger.warning(f"[weights] Falha ao ler {path}: {e}. Iniciando vazio.")


def save_correction_weights():
    path = CORRECTION_WEIGHTS_FILE
    if os.path.isdir(path):
        logger.warning(f"[weights] Nao foi possivel salvar: {path} e um diretorio.")
        return
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(correction_weights, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[weights] Falha ao salvar {path}: {e}")


load_correction_weights()
