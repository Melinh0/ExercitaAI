import threading
import time

_SUGESTAO_CACHE = {}
_SUGESTAO_CACHE_TTL = 300
_SUGESTAO_CACHE_LOCK = threading.Lock()


def _cache_key(mode: str, context: str, model: str) -> str:
    return f"{mode}:{model}:{hash(context)}"


def obter_sugestoes_em_cache(mode: str, context: str, model: str):
    key = _cache_key(mode, context, model)
    with _SUGESTAO_CACHE_LOCK:
        entry = _SUGESTAO_CACHE.get(key)
        if entry and time.time() - entry['ts'] < _SUGESTAO_CACHE_TTL:
            return entry['suggestions']
    return None


def guardar_sugestoes_em_cache(mode: str, context: str, model: str, suggestions: list):
    key = _cache_key(mode, context, model)
    with _SUGESTAO_CACHE_LOCK:
        _SUGESTAO_CACHE[key] = {'ts': time.time(), 'suggestions': suggestions}
