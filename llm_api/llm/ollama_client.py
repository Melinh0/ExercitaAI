import requests
from core.config import (
    OLLAMA_API_KEYS,
    OLLAMA_HOST,
    MAX_RETRIES,
    OLLAMA_MAX_CONCURRENT_REQUESTS,
    OLLAMA_MIN_REQUEST_INTERVAL,
    OLLAMA_RATE_LIMIT_BACKOFF_BASE,
    OLLAMA_RATE_LIMIT_MAX_BACKOFF,
    OLLAMA_KEY_RECOVERY_SECONDS,
)
import contextvars
import logging
import time
import os
import random
import re
import threading
from cachetools import TTLCache
import hashlib
import json
from llm import provedores

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "16000"))
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "600"))
REPEAT_PENALTY = float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.15"))
MIN_P = float(os.getenv("OLLAMA_MIN_P", "0.02"))

response_cache = TTLCache(maxsize=1000, ttl=3600)

_rate_lock = threading.Lock()
_semaphore = threading.Semaphore(max(1, OLLAMA_MAX_CONCURRENT_REQUESTS))
_next_allowed_time = 0.0


def _wait_for_slot():
    global _next_allowed_time
    with _rate_lock:
        now = time.time()
        wait = _next_allowed_time - now
        if wait > 0:
            time.sleep(wait)
            now = time.time()
        _next_allowed_time = now + OLLAMA_MIN_REQUEST_INTERVAL


def _compute_backoff(attempt, response=None):
    retry_after = None
    if response is not None:
        header_value = response.headers.get("Retry-After")
        if header_value:
            try:
                retry_after = float(header_value)
            except ValueError:
                retry_after = None

    if retry_after is not None:
        delay = min(retry_after, OLLAMA_RATE_LIMIT_MAX_BACKOFF)
    else:
        delay = min(
            OLLAMA_RATE_LIMIT_MAX_BACKOFF,
            OLLAMA_RATE_LIMIT_BACKOFF_BASE * (2 ** attempt),
        )

    jitter = delay * 0.2 * (random.random() - 0.5)
    return max(1.0, delay + jitter)


def _push_next_allowed(delay):
    global _next_allowed_time
    with _rate_lock:
        _next_allowed_time = max(_next_allowed_time, time.time() + delay)


def _get_cache_key(model, prompt, images=None, temperature=0.0, seed=None, json_mode=False):
    data = {
        "model": model,
        "prompt": prompt,
        "temperature": temperature,
        "json_mode": json_mode,
    }
    if seed is not None:
        data["seed"] = seed
    if images:
        data["images"] = images
    key_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()


def _build_options(temperature, seed, json_mode):
    options = {
        "num_predict": MAX_OUTPUT_TOKENS,
        "temperature": temperature,
        "repeat_penalty": REPEAT_PENALTY,
        "min_p": MIN_P,
    }
    if seed is not None:
        options["seed"] = seed
    if json_mode:
        options["stop"] = ["\n\n\n"]
    return options


_KEY_ERROR_STATUSES = (401, 402, 403)

_key_lock = threading.Lock()
_keys = OLLAMA_API_KEYS if OLLAMA_API_KEYS else [None]
_estado_global = {"indice": 0, "esgotadas": {}, "cooldowns": {}}
_estados_de_pool = {}
chaves_do_usuario = contextvars.ContextVar("chaves_do_usuario", default=None)


def padrao_para_o_usuario():
    chaves_ollama = [c for c in (chaves_do_usuario.get() or []) if c]
    if chaves_ollama:
        return None
    return provedores.padrao_disponivel()


def _mascarar_chave(chave):
    if not chave:
        return "(sem chave)"
    return f"...{chave[-4:]}"


def _limpar_chaves_expiradas(estado, agora):
    esgotadas = estado["esgotadas"]
    cooldowns = estado["cooldowns"]
    for chave in [
        c for c, marca in esgotadas.items()
        if agora - marca >= OLLAMA_KEY_RECOVERY_SECONDS
    ]:
        del esgotadas[chave]
    for chave in [
        c for c, liberada_em in cooldowns.items()
        if liberada_em <= agora
    ]:
        del cooldowns[chave]


def _proxima_chave(excluir=None, pool=None, estado=None):
    pool = _keys if pool is None else pool
    estado = _estado_global if estado is None else estado
    with _key_lock:
        agora = time.time()
        _limpar_chaves_expiradas(estado, agora)
        total = len(pool)
        esgotadas = estado["esgotadas"]
        cooldowns = estado["cooldowns"]
        for passo in range(total):
            indice = (estado["indice"] + passo) % total
            chave = pool[indice]
            if (
                chave == excluir
                or chave in esgotadas
                or chave in cooldowns
            ):
                continue
            estado["indice"] = indice
            return chave
        if excluir is None and cooldowns:
            cooldowns.clear()
            for passo in range(total):
                indice = (estado["indice"] + passo) % total
                chave = pool[indice]
                if chave in esgotadas:
                    continue
                estado["indice"] = indice
                return chave
        return None


def _marcar_chave_esgotada(chave, pool=None, estado=None):
    pool = _keys if pool is None else pool
    estado = _estado_global if estado is None else estado
    with _key_lock:
        esgotadas = estado["esgotadas"]
        esgotadas[chave] = time.time()
        ativas = [c for c in pool if c not in esgotadas]
        if not ativas:
            esgotadas.clear()
            estado["indice"] = 0
            logger.warning(
                f"Todas as {len(pool)} chaves Ollama esgotadas/inválidas - "
                "reiniciando o ciclo de chaves na próxima chamada."
            )
            return False
        estado["indice"] = (estado["indice"] + 1) % len(pool)
        return True


def _marcar_chave_em_cooldown(chave, atraso, estado=None):
    estado = _estado_global if estado is None else estado
    with _key_lock:
        estado["cooldowns"][chave] = time.time() + atraso


_TERMOS_CREDITO_ESGOTADO = ("credit", "quota", "insufficient", "exceed", "balance")


def _corpo_indica_credito_esgotado(texto):
    return any(termo in texto for termo in _TERMOS_CREDITO_ESGOTADO)


def _resposta_indica_chave_esgotada(response):
    if response.status_code in _KEY_ERROR_STATUSES:
        return True
    if response.status_code in (200, 404, 429) or response.status_code >= 500:
        return False
    try:
        corpo = (response.text or "").lower()
    except Exception:
        return False
    return _corpo_indica_credito_esgotado(corpo)


def _resposta_200_indica_limite_transitorio(response):
    if response.status_code != 200:
        return False
    try:
        corpo = (response.text or "").lower()
    except Exception:
        return False
    return _corpo_indica_credito_esgotado(corpo)


def _mascarar_trecho_corpo(texto, limite=300):
    compacto = " ".join((texto or "").split())
    compacto = re.sub(
        r"\w{20,}",
        lambda m: f"{m.group(0)[:4]}...{m.group(0)[-4:]}",
        compacto,
    )
    if len(compacto) > limite:
        compacto = compacto[:limite] + "..."
    return compacto


def _post_with_retry(url, payload, max_retries, timeout):
    chaves = chaves_do_usuario.get()
    pool = None
    estado = None
    if chaves:
        pool = [c for c in chaves if c] or None
        if pool:
            estado = _estados_de_pool.get(tuple(pool))
            if estado is None:
                estado = {"indice": 0, "esgotadas": {}, "cooldowns": {}}
                _estados_de_pool[tuple(pool)] = estado
    total_chaves = len(pool) if pool else len(_keys)
    last_error = None
    attempt = 0
    trocas_de_chave = 0
    trocas_rate_limit = 0
    while attempt < max_retries:
        chave = _proxima_chave(pool=pool, estado=estado)
        headers = {
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
        }
        response = None
        _semaphore.acquire()
        try:
            _wait_for_slot()
            response = requests.post(
                url, json=payload, headers=headers, timeout=timeout
            )
        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(
                f"Ollama timeout (tentativa {attempt + 1}/{max_retries})"
            )
            if attempt < max_retries - 1:
                delay = _compute_backoff(attempt)
                _push_next_allowed(delay)
                attempt += 1
                time.sleep(delay)
                continue
            raise Exception(f"Timeout apos {max_retries} tentativas") from e
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(
                f"Ollama falha de rede (tentativa {attempt + 1}/{max_retries}): {e}"
            )
            if attempt < max_retries - 1:
                delay = _compute_backoff(attempt)
                _push_next_allowed(delay)
                attempt += 1
                time.sleep(delay)
                continue
            raise Exception(f"Erro na API do Ollama: {e}") from e
        finally:
            _semaphore.release()

        if _resposta_indica_chave_esgotada(response):
            trocas_de_chave += 1
            outra_disponivel = _marcar_chave_esgotada(chave, pool=pool, estado=estado)
            last_error = Exception(
                f"HTTP {response.status_code} - chave Ollama esgotada/invalida"
            )
            logger.warning(
                f"Chave Ollama {_mascarar_chave(chave)} esgotada/inválida "
                f"(HTTP {response.status_code}) - alternando para a próxima chave "
                f"({trocas_de_chave}/{total_chaves})"
            )
            if not outra_disponivel or trocas_de_chave > total_chaves:
                raise Exception(
                    "Todas as chaves Ollama estão esgotadas ou inválidas "
                    f"(último erro: HTTP {response.status_code})"
                ) from last_error
            continue

        limite_transitorio_200 = _resposta_200_indica_limite_transitorio(response)

        if response.status_code == 429 or limite_transitorio_200:
            delay = _compute_backoff(attempt, response)
            _push_next_allowed(delay)
            if total_chaves > 1 and trocas_rate_limit < total_chaves:
                _marcar_chave_em_cooldown(chave, delay, estado=estado)
                outra = _proxima_chave(excluir=chave, pool=pool, estado=estado)
                if outra is not None:
                    trocas_rate_limit += 1
                    motivo = (
                        "429 Too Many Requests"
                        if response.status_code == 429
                        else "limite de crédito"
                    )
                    logger.warning(
                        f"Ollama {motivo} na chave {_mascarar_chave(chave)} "
                        f"(tentativa {attempt + 1}/{max_retries}) - alternando "
                        f"para a chave {_mascarar_chave(outra)} "
                        f"(cooldown de {delay:.1f}s)."
                    )
                    attempt += 1
                    continue
            if limite_transitorio_200:
                logger.warning(
                    f"Ollama HTTP 200 com corpo indicando limite de crédito "
                    f"(tentativa {attempt + 1}/{max_retries}) - backoff de "
                    f"{delay:.1f}s e retry na MESMA chave. Trecho do corpo: "
                    f"{_mascarar_trecho_corpo(response.text)}"
                )
                last_error = Exception(
                    f"Limite transitório do Ollama após {max_retries} tentativas "
                    "(HTTP 200 com corpo indicando limite de crédito)"
                )
            else:
                logger.warning(
                    f"Ollama 429 (tentativa {attempt + 1}/{max_retries}) - "
                    f"aguardando {delay:.1f}s"
                )
                last_error = Exception(
                    f"429 Too Many Requests apos {max_retries} tentativas"
                )
            if attempt < max_retries - 1:
                attempt += 1
                time.sleep(delay)
                continue
            raise last_error

        if response.status_code >= 500:
            last_error = Exception(f"HTTP {response.status_code}")
            logger.warning(
                f"Ollama HTTP {response.status_code} "
                f"(tentativa {attempt + 1}/{max_retries})"
            )
            if attempt < max_retries - 1:
                delay = _compute_backoff(attempt)
                _push_next_allowed(delay)
                attempt += 1
                time.sleep(delay)
                continue
            raise last_error

        if response.status_code != 200:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise Exception(f"Erro na API do Ollama: {e}") from e

        return response

    if last_error is not None:
        raise last_error
    raise Exception("Falha ao chamar a API do Ollama")


def get_ollama_response(
    model,
    prompt,
    max_retries=None,
    timeout=REQUEST_TIMEOUT,
    temperature=0.0,
    seed=None,
    json_mode=False,
    min_chars=0,
    retry_on_short=True,
):
    if max_retries is None:
        max_retries = MAX_RETRIES

    cache_key = _get_cache_key(
        model, prompt, temperature=temperature, seed=seed, json_mode=json_mode
    )
    if cache_key in response_cache:
        cached = response_cache[cache_key]
        if min_chars <= 0 or len(cached) >= min_chars:
            logger.info(f"Cache hit para modelo {model}")
            return cached

    url = f"{OLLAMA_HOST}/api/chat"
    eh_provedor = provedores.eh_modelo(model)

    attempts = 0
    max_attempts = 2 if (min_chars > 0 and retry_on_short) else 1
    current_temperature = temperature

    while attempts < max_attempts:
        attempts += 1
        if eh_provedor:
            content = provedores.gerar(
                model,
                prompt,
                temperature=current_temperature,
                seed=seed,
                json_mode=json_mode,
                max_retries=max_retries,
                timeout=timeout,
            )
        else:
            options = _build_options(current_temperature, seed, json_mode)

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": options,
            }
            if json_mode:
                payload["format"] = "json"

            response = _post_with_retry(url, payload, max_retries, timeout)
            data = response.json()
            content = data.get("message", {}).get("content", "") or ""

            if data.get("done_reason") == "length":
                logger.warning(
                    f"Resposta do Ollama truncada no limite de tokens (done_reason=length) "
                    f"para modelo={model}."
                )

        if min_chars <= 0 or len(content) >= min_chars:
            response_cache[cache_key] = content
            return content

        logger.warning(
            f"[ollama_client] Resposta curta ({len(content)} chars < {min_chars}) "
            f"para modelo={model}. Tentativa {attempts}/{max_attempts}."
        )
        if attempts < max_attempts:
            current_temperature = max(current_temperature, 0.3)
            time.sleep(1.0)

    response_cache[cache_key] = content
    return content


def get_ollama_response_with_image_multi(
    model,
    prompt,
    images_base64,
    max_retries=None,
    timeout=REQUEST_TIMEOUT,
    temperature=0.0,
    seed=None,
    json_mode=False,
    min_chars=0,
):
    if max_retries is None:
        max_retries = MAX_RETRIES

    cache_key = _get_cache_key(
        model, prompt, images_base64, temperature, seed, json_mode
    )
    if cache_key in response_cache:
        cached = response_cache[cache_key]
        if min_chars <= 0 or len(cached) >= min_chars:
            logger.info(f"Cache hit (imagem) para modelo {model}")
            return cached

    url = f"{OLLAMA_HOST}/api/chat"

    if provedores.eh_modelo(model):
        content = provedores.gerar(
            model,
            prompt,
            images_base64=images_base64,
            temperature=temperature,
            seed=seed,
            json_mode=json_mode,
            max_retries=max_retries,
            timeout=timeout,
        )
        response_cache[cache_key] = content
        return content

    options = _build_options(temperature, seed, json_mode)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": images_base64,
            }
        ],
        "stream": False,
        "options": options,
    }
    if json_mode:
        payload["format"] = "json"

    response = _post_with_retry(url, payload, max_retries, timeout)
    data = response.json()
    content = data.get("message", {}).get("content", "") or ""
    if data.get("done_reason") == "length":
        logger.warning(
            f"Resposta do Ollama truncada no limite de tokens (done_reason=length) "
            f"para modelo={model}."
        )
    response_cache[cache_key] = content
    return content