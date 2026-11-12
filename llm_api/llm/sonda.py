import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from core.config import OLLAMA_API_KEYS, OLLAMA_HOST, OLLAMA_MAX_CONCURRENT_REQUESTS
from llm import provedores
from llm.ollama_client import (
    _resposta_200_indica_limite_transitorio,
    chaves_do_usuario,
)

logger = logging.getLogger(__name__)

TTL = 900
TTL_INCONCLUSIVO = 60
TIMEOUT_CURTO = 10
TIMEOUT_LONGO = 90
TRABALHADORES_PROVEDOR = 12

_cache = {}
_travas = {}
_trava_geral = threading.Lock()


def _trava_de(fp):
    with _trava_geral:
        return _travas.setdefault(fp, threading.Lock())


def _capturar_chaves():
    chaves = {"ollama": [c for c in (chaves_do_usuario.get() or OLLAMA_API_KEYS) if c]}
    for pid in provedores.PROVEDORES:
        efetivas = [c for c in provedores.chaves_efetivas(pid) if c]
        if efetivas:
            chaves[pid] = efetivas
    return chaves


def _impressao_das_chaves(chaves):
    return "v2|" + "|".join(f"{k}:{','.join(v)}" for k, v in sorted(chaves.items()))


def _grupo_de(nome):
    parsed = provedores.parsear_modelo(nome)
    return parsed[0] if parsed else "ollama"


def _sonda(nome, chaves, timeout):
    parsed = provedores.parsear_modelo(nome)
    if parsed:
        pid, identificador = parsed
        cfg = provedores.PROVEDORES[pid]
        grupo = chaves.get(pid) or []
        eh_anthropic = cfg["api"] == "anthropic"
        if eh_anthropic:
            url = f"{cfg['base_url']}/messages"
            corpo = {
                "model": identificador,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "oi"}],
            }
        else:
            url = f"{cfg['base_url']}/chat/completions"
            corpo = {
                "model": identificador,
                "max_tokens": 1,
                "stream": False,
                "messages": [{"role": "user", "content": "oi"}],
            }
    else:
        url = f"{OLLAMA_HOST}/api/chat"
        corpo = {
            "model": nome,
            "stream": False,
            "messages": [{"role": "user", "content": "oi"}],
            "options": {"num_predict": 1},
        }
        grupo = chaves.get("ollama") or []
        eh_anthropic = False
    if not grupo:
        return "sem_chave"
    for chave in grupo:
        if eh_anthropic:
            headers = {
                "x-api-key": chave,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        else:
            headers = {
                "Authorization": f"Bearer {chave}",
                "Content-Type": "application/json",
            }
        try:
            resp = requests.post(url, headers=headers, json=corpo, timeout=timeout)
        except requests.exceptions.Timeout:
            return "timeout"
        except requests.exceptions.RequestException:
            return "erro"
        if resp.status_code == 200 and not _resposta_200_indica_limite_transitorio(resp):
            return "ok"
        if resp.status_code in (401, 402, 403):
            continue
        if resp.status_code == 429:
            return "transitorio"
        return "falhou"
    return "falhou"


def _testar_grupo(grupo, nomes, chaves, timeout):
    trabalhadores = (
        max(1, OLLAMA_MAX_CONCURRENT_REQUESTS)
        if grupo == "ollama"
        else TRABALHADORES_PROVEDOR
    )
    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        return dict(
            zip(nomes, executor.map(lambda m: _sonda(m, chaves, timeout), nomes))
        )


def _testar(chaves, alvos, timeout):
    resultados = {}
    inconclusivos = []
    grupos = {}
    for nome in alvos:
        grupos.setdefault(_grupo_de(nome), []).append(nome)
    conclusivos = True
    with ThreadPoolExecutor(max_workers=max(1, len(grupos))) as executor:
        futuros = {
            grupo: executor.submit(_testar_grupo, grupo, nomes, chaves, timeout)
            for grupo, nomes in grupos.items()
        }
        respostas_por_grupo = {
            grupo: futuro.result() for grupo, futuro in futuros.items()
        }
    for grupo, respostas in respostas_por_grupo.items():
        tem_definitiva = any(
            v in ("ok", "falhou", "sem_chave") for v in respostas.values()
        )
        if not tem_definitiva:
            conclusivos = False
        for nome, estado in respostas.items():
            if estado == "ok":
                resultados[nome] = True
            elif estado in ("falhou", "sem_chave"):
                resultados[nome] = False
            elif tem_definitiva:
                resultados[nome] = False
                inconclusivos.append(nome)
            else:
                resultados[nome] = True
    return resultados, conclusivos, inconclusivos


def _reavaliar(fp, chaves, alvos, timeout):
    resultados, _, _ = _testar(chaves, alvos, timeout)
    with _trava_de(fp):
        entrada = _cache.get(fp)
        atual = dict(entrada["resultados"]) if entrada else {}
        atual.update(resultados)
        _cache[fp] = {"expira": time.time() + TTL, "resultados": atual}


def filtrar_testados(nomes):
    if not nomes:
        return nomes
    chaves = _capturar_chaves()
    fp = hashlib.sha256(_impressao_das_chaves(chaves).encode("utf-8")).hexdigest()
    with _trava_de(fp):
        entrada = _cache.get(fp) or {"expira": 0.0, "resultados": {}}
        resultados = dict(entrada["resultados"])
        pendentes = [m for m in nomes if m not in resultados]
        if not pendentes:
            if entrada["expira"] > time.time():
                return [m for m in nomes if resultados.get(m)]
            threading.Thread(
                target=_reavaliar,
                args=(fp, chaves, list(nomes), TIMEOUT_LONGO),
                daemon=True,
                name="sonda_modelos",
            ).start()
            return [m for m in nomes if resultados.get(m)]
        novos, conclusivos, retestar = _testar(chaves, pendentes, TIMEOUT_CURTO)
        resultados.update(novos)
        _cache[fp] = {
            "expira": time.time() + (TTL if conclusivos else TTL_INCONCLUSIVO),
            "resultados": resultados,
        }
        if retestar:
            threading.Thread(
                target=_reavaliar,
                args=(fp, chaves, retestar, TIMEOUT_LONGO),
                daemon=True,
                name="sonda_modelos",
            ).start()
        logger.info(
            f"[sonda] {len(nomes)} modelo(s) verificados; "
            f"{sum(1 for m in nomes if resultados.get(m))} respondem."
        )
        return [m for m in nomes if resultados.get(m)]
