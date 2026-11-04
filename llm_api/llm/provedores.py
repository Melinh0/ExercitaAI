import contextvars
import logging
import os
import re
import threading
import time

import requests

logger = logging.getLogger(__name__)

PROVEDORES = {
    "openai": {
        "nome": "OpenAI",
        "modelo_padrao": "gpt-4o-mini",
        "api": "openai",
        "lista": "openai",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "env_modelos": "OPENAI_MODELS",
        "modelos_padrao": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        "vision": True,
        "padrao_vision": "^(gpt-4o|gpt-4\\.1|gpt-5|o[1-9])",
        "site": "https://platform.openai.com",
        "link_padrao": "https://platform.openai.com/docs",
        "somente_gratuitos": False,
    },
    "groq": {
        "nome": "Groq",
        "modelo_padrao": "llama-3.3-70b-versatile",
        "api": "openai",
        "lista": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "env_modelos": "GROQ_MODELS",
        "modelos_padrao": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3-32b",
            "qwen/qwen3.8-27b",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ],
        "vision": True,
        "padrao_vision": "vision|llama-4-|moondream",
        "site": "https://groq.com",
        "link_padrao": "https://console.groq.com/docs",
        "somente_gratuitos": False,
    },
    "gemini": {
        "nome": "Google Gemini",
        "modelo_padrao": "gemini-2.5-flash",
        "api": "openai",
        "lista": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "base_lista": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GEMINI_API_KEY",
        "env_modelos": "GEMINI_MODELS",
        "modelos_padrao": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
        "vision": True,
        "padrao_vision": ".*",
        "site": "https://ai.google.dev",
        "link_padrao": "https://ai.google.dev/gemini-api/docs",
        "somente_gratuitos": False,
    },
    "openrouter": {
        "nome": "OpenRouter",
        "modelo_padrao": "meta-llama/llama-3.3-70b-instruct",
        "api": "openai",
        "lista": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "env_modelos": "OPENROUTER_MODELS",
        "modelos_padrao": [
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat-v3-0324",
            "google/gemma-3-27b-it",
            "qwen/qwen3-235b-a22b",
            "mistralai/mistral-small-3.1-24b-instruct",
        ],
        "vision": False,
        "padrao_vision": "gemini|claude|gpt-4o|gpt-4\\.1|gpt-5|o[1-9]-|llama-4|vision|vl|moondream",
        "site": "https://openrouter.ai",
        "link_padrao": "https://openrouter.ai/models",
        "somente_gratuitos": True,
    },
    "deepseek": {
        "nome": "DeepSeek",
        "modelo_padrao": "deepseek-chat",
        "api": "openai",
        "lista": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "env_modelos": "DEEPSEEK_MODELS",
        "modelos_padrao": ["deepseek-chat", "deepseek-reasoner"],
        "vision": False,
        "site": "https://www.deepseek.com",
        "link_padrao": "https://api-docs.deepseek.com",
        "somente_gratuitos": False,
    },
    "anthropic": {
        "nome": "Anthropic",
        "modelo_padrao": "claude-haiku-4-5",
        "api": "anthropic",
        "lista": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "env_modelos": "ANTHROPIC_MODELS",
        "modelos_padrao": ["claude-haiku-4-5", "claude-sonnet-5-5", "claude-opus-5-5"],
        "vision": True,
        "padrao_vision": ".*",
        "site": "https://www.anthropic.com",
        "link_padrao": "https://platform.claude.com/docs",
        "somente_gratuitos": False,
    },
    "nvidia": {
        "nome": "NVIDIA",
        "modelo_padrao": "meta/llama-3.3-70b-instruct",
        "api": "openai",
        "lista": "openai",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_API_KEY",
        "env_modelos": "NVIDIA_MODELS",
        "modelos_padrao": [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "meta/llama-4-scout-17b-16e-instruct",
            "qwen/qwen2.5-7b-instruct",
        ],
        "exclusos": (
            "flux",
            "sdxl",
            "florence",
            "kosmos",
            "paligemma",
            "canary",
            "parakeet",
            "riva",
            "speech",
            "paddle",
        ),
        "vision": True,
        "padrao_vision": "llama-4|vision|multimodal|vl-|pixtral|gemma-3",
        "site": "https://build.nvidia.com",
        "link_padrao": "https://build.nvidia.com/models",
        "somente_gratuitos": False,
    },
}

chaves_de_provedores = contextvars.ContextVar("chaves_de_provedores", default=None)

TTL_FRESCO = 900
TTL_FALHA = 60
TIMEOUT_LISTA = 12
RECUPERACAO_CHAVE = 600
COOLDOWN_CHAVE = 15

EXCLUSOS_DE_CHAT = (
    "whisper",
    "tts",
    "dall-e",
    "image",
    "embedding",
    "embed",
    "rerank",
    "diffusion",
    "moderation",
    "transcribe",
    "audio",
    "guard",
    "safeguard",
    "compound",
    "ft:",
    "search-preview",
    "computer-use",
    "veo",
    "imagen",
)

_cache = {}
_estados = {}
_trava = threading.Lock()


def separar_chaves(chaves):
    ollama = []
    por_provedor = {}
    for chave in chaves or []:
        if "=" in chave:
            prefixo, _, valor = chave.partition("=")
            if prefixo in PROVEDORES and valor.strip():
                por_provedor.setdefault(prefixo, []).append(valor.strip())
                continue
        if chave:
            ollama.append(chave)
    return ollama, por_provedor


def parsear_modelo(model):
    if not model or "/" not in model:
        return None
    prefixo, _, identificador = model.partition("/")
    if prefixo not in PROVEDORES or not identificador:
        return None
    return prefixo, identificador


def eh_modelo(model):
    return parsear_modelo(model) is not None


def e_vision(model):
    parsed = parsear_modelo(model)
    if not parsed:
        return False
    return bool(PROVEDORES[parsed[0]]["vision"])


def eh_modelo_vision(modelo):
    parsed = parsear_modelo(modelo)
    if not parsed:
        return False
    padrao = PROVEDORES[parsed[0]].get("padrao_vision")
    if not padrao:
        return False
    return re.search(padrao, parsed[1]) is not None


def _chaves_do_contexto(pid):
    por_provedor = chaves_de_provedores.get()
    if isinstance(por_provedor, dict):
        return [c for c in por_provedor.get(pid, []) if c]
    return []


def _chaves_do_env(pid):
    bruto = os.getenv(PROVEDORES[pid]["env_key"], "")
    return [c.strip() for c in bruto.split(",") if c.strip()]


def chaves_efetivas(pid):
    return _chaves_do_contexto(pid) or _chaves_do_env(pid)


def padrao_disponivel():
    por_provedor = chaves_de_provedores.get()
    if not isinstance(por_provedor, dict):
        return None
    for pid, cfg in PROVEDORES.items():
        if [c for c in por_provedor.get(pid, []) if c]:
            return f"{pid}/{cfg['modelo_padrao']}"
    return None


def _cabecalho_lista(pid, cfg, chave):
    if cfg["lista"] == "anthropic":
        return {
            "x-api-key": chave,
            "anthropic-version": "2023-06-01",
        }
    if cfg["lista"] == "gemini":
        return {"x-goog-api-key": chave}
    return {"Authorization": f"Bearer {chave}"}


def _itens_da_lista(pid, cfg, chave):
    if cfg["lista"] == "gemini":
        url = f"{cfg['base_lista']}/models"
    else:
        url = f"{cfg['base_url']}/models"
    for tentativa in range(3):
        try:
            resp = requests.get(
                url,
                headers=_cabecalho_lista(pid, cfg, chave),
                timeout=TIMEOUT_LISTA,
            )
        except requests.exceptions.RequestException as e:
            if tentativa == 2:
                logger.warning(f"[provedores] Falha ao listar modelos do {cfg['nome']}: {e}")
                return None
            time.sleep(1 + tentativa)
            continue
        if resp.status_code in (401, 403):
            logger.warning(
                f"[provedores] Chave recusada ao listar modelos do {cfg['nome']} "
                f"(HTTP {resp.status_code})."
            )
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(1 + tentativa)
            continue
        if not resp.ok:
            logger.warning(
                f"[provedores] {cfg['nome']} listagem respondeu HTTP {resp.status_code}."
            )
            return None
        try:
            dados = resp.json()
        except ValueError:
            return None
        return _normalizar_itens(cfg, dados)
    return None


def _normalizar_itens(cfg, dados):
    itens = []
    if cfg["lista"] == "gemini":
        for modelo in dados.get("models") or []:
            if not isinstance(modelo, dict):
                continue
            nome = modelo.get("name") or ""
            if nome.startswith("models/"):
                nome = nome[len("models/"):]
            metodos = modelo.get("supportedGenerationMethods") or []
            if nome and "generateContent" in metodos:
                itens.append({"id": nome, "preco": None})
        return itens
    for item in dados.get("data") or []:
        if not isinstance(item, dict):
            continue
        identificador = item.get("id")
        if not isinstance(identificador, str) or not identificador.strip():
            continue
        preco = None
        precos = item.get("pricing")
        if isinstance(precos, dict):
            preco = precos.get("prompt")
        itens.append({"id": identificador.strip(), "preco": preco})
    return itens


def _eh_gratuito(item):
    if item["id"].endswith(":free"):
        return True
    preco = item.get("preco")
    if preco is None:
        return True
    try:
        return float(preco) == 0
    except (TypeError, ValueError):
        return False


def _filtrar_itens(cfg, itens):
    exclusos = EXCLUSOS_DE_CHAT + tuple(cfg.get("exclusos", ()))
    ids = [
        i["id"]
        for i in itens
        if not any(token in i["id"] for token in exclusos)
    ]
    env = os.getenv(cfg["env_modelos"], "").strip()
    if env == "*":
        return sorted(ids)
    if env:
        permitidos = {m.strip() for m in env.split(",") if m.strip()}
        escolhidos = [i for i in ids if i in permitidos]
        if escolhidos:
            return sorted(escolhidos)
        return sorted(permitidos)
    if cfg["somente_gratuitos"]:
        livres = [i["id"] for i in itens if _eh_gratuito(i)]
        livres = [
            i for i in livres
            if not any(token in i for token in exclusos)
        ]
        if livres:
            return sorted(livres)
        return list(cfg["modelos_padrao"])
    return sorted(ids)


def _listar_ids(pid):
    cfg = PROVEDORES[pid]
    agora = time.time()
    with _trava:
        entrada = _cache.get(pid)
        if entrada and entrada[0] > agora:
            return list(entrada[1])
    chaves = chaves_efetivas(pid)
    if not chaves:
        return list(cfg["modelos_padrao"])
    itens = None
    for chave in chaves:
        itens = _itens_da_lista(pid, cfg, chave)
        if itens is not None:
            break
    if itens is None:
        with _trava:
            _cache[pid] = (agora + TTL_FALHA, list(cfg["modelos_padrao"]))
        return list(cfg["modelos_padrao"])
    if not itens:
        with _trava:
            _cache[pid] = (agora + TTL_FALHA, list(cfg["modelos_padrao"]))
        return list(cfg["modelos_padrao"])
    ids = _filtrar_itens(cfg, itens)
    if not ids:
        ids = list(cfg["modelos_padrao"])
    with _trava:
        _cache[pid] = (agora + TTL_FRESCO, list(ids))
    return ids


def listar_modelos_prefixados():
    resultado = []
    for pid in PROVEDORES:
        if not chaves_efetivas(pid):
            continue
        for identificador in _listar_ids(pid):
            nome = f"{pid}/{identificador}"
            resultado.append({
                "name": nome,
                "vision_support": eh_modelo_vision(nome),
            })
    return resultado


def _estado_de(pid):
    with _trava:
        if pid not in _estados:
            _estados[pid] = {"ordem": 0, "esgotadas": {}, "cooldowns": {}}
        return _estados[pid]


def _limpar_estado(estado):
    agora = time.time()
    for chave in [
        c for c, marca in estado["esgotadas"].items()
        if agora - marca >= RECUPERACAO_CHAVE
    ]:
        del estado["esgotadas"][chave]
    for chave in [
        c for c, liberada in estado["cooldowns"].items()
        if liberada <= agora
    ]:
        del estado["cooldowns"][chave]


def _proxima_chave_provedor(pid, chaves, excluir=None):
    estado = _estado_de(pid)
    with _trava:
        _limpar_estado(estado)
        total = len(chaves)
        for passo in range(total):
            indice = (estado["ordem"] + passo) % total
            chave = chaves[indice]
            if chave == excluir or chave in estado["esgotadas"] or chave in estado["cooldowns"]:
                continue
            estado["ordem"] = indice
            return chave
        return None


def _marcar_esgotada(pid, chave):
    estado = _estado_de(pid)
    with _trava:
        estado["esgotadas"][chave] = time.time()


def _marcar_cooldown(pid, chave, atraso):
    estado = _estado_de(pid)
    with _trava:
        estado["cooldowns"][chave] = time.time() + atraso


def _limpar_cooldowns(pid):
    estado = _estado_de(pid)
    with _trava:
        estado["cooldowns"].clear()


def _mime_da_imagem(base64):
    if base64.startswith("/9j/"):
        return "image/jpeg"
    if base64.startswith("UklGR"):
        return "image/webp"
    if base64.startswith("R0lGOD"):
        return "image/gif"
    return "image/png"


def _conteudo_openai(prompt, images_base64):
    if not images_base64:
        return prompt
    conteudo = [{"type": "text", "text": prompt}]
    for imagem in images_base64:
        mime = _mime_da_imagem(imagem)
        conteudo.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{imagem}"},
        })
    return conteudo


def _conteudo_anthropic(prompt, images_base64):
    if not images_base64:
        return [{"type": "text", "text": prompt}]
    conteudo = [{"type": "text", "text": prompt}]
    for imagem in images_base64:
        conteudo.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": _mime_da_imagem(imagem),
                "data": imagem,
            },
        })
    return conteudo


def _corpo_de_erro(resp):
    try:
        texto = " ".join((resp.text or "").split())
    except Exception:
        texto = ""
    return texto[:300]


def _variaveis_openai(base):
    variantes = [dict(base)]
    sem_seed = dict(base)
    sem_seed.pop("seed", None)
    variantes.append(sem_seed)
    sem_formato = dict(sem_seed)
    sem_formato.pop("response_format", None)
    variantes.append(sem_formato)
    minimo = {
        "model": base["model"],
        "messages": base["messages"],
        "stream": False,
    }
    variantes.append(minimo)
    return variantes


def _gerar_openai(pid, cfg, identificador, prompt, images_base64, temperature, seed, json_mode, max_retries, timeout):
    pid_nome = cfg["nome"]
    chaves = chaves_efetivas(pid)
    if not chaves:
        raise Exception(
            f"Nenhuma chave da API do {pid_nome} cadastrada para este usuário. "
            "Cadastre uma em Configurações."
        )
    base = {
        "model": identificador,
        "messages": [{"role": "user", "content": _conteudo_openai(prompt, images_base64)}],
        "stream": False,
        "temperature": temperature,
    }
    if seed is not None:
        base["seed"] = seed
    if json_mode:
        base["response_format"] = {"type": "json_object"}
    variantes = _variaveis_openai(base)
    url = f"{cfg['base_url']}/chat/completions"
    limite = max(3, min(len(chaves) * 2 + 2, 10))
    indice_variante = 0
    ultimo_erro = None
    for tentativa in range(limite):
        chave = _proxima_chave_provedor(pid, chaves)
        if chave is None:
            _limpar_cooldowns(pid)
            chave = _proxima_chave_provedor(pid, chaves)
        if chave is None:
            break
        payload = variantes[min(indice_variante, len(variantes) - 1)]
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {chave}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
        except requests.exceptions.RequestException as e:
            ultimo_erro = Exception(f"Erro na API do {pid_nome}: {e}")
            logger.warning(
                f"[provedores] Falha de rede no {pid_nome} "
                f"(tentativa {tentativa + 1}/{limite}): {e}"
            )
            continue
        if resp.status_code in (401, 402, 403):
            _marcar_esgotada(pid, chave)
            ultimo_erro = Exception(
                f"Chave do {pid_nome} esgotada ou inválida (HTTP {resp.status_code})."
            )
            logger.warning(
                f"[provedores] Chave do {pid_nome} recusada "
                f"(HTTP {resp.status_code}) - alternando."
            )
            continue
        if resp.status_code == 429:
            _marcar_cooldown(pid, chave, COOLDOWN_CHAVE)
            ultimo_erro = Exception(f"Limite de requisições do {pid_nome} (HTTP 429).")
            logger.warning(f"[provedores] 429 no {pid_nome} - cooldown de {COOLDOWN_CHAVE}s.")
            continue
        if resp.status_code == 400 and indice_variante < len(variantes) - 1:
            indice_variante += 1
            logger.warning(
                f"[provedores] {pid_nome} recusou os parâmetros "
                f"(HTTP 400) - nova tentativa sem parâmetros opcionais."
            )
            continue
        if resp.status_code >= 500:
            ultimo_erro = Exception(f"HTTP {resp.status_code} na API do {pid_nome}.")
            logger.warning(
                f"[provedores] {pid_nome} HTTP {resp.status_code} "
                f"(tentativa {tentativa + 1}/{limite})."
            )
            continue
        if not resp.ok:
            raise Exception(
                f"Erro na API do {pid_nome}: HTTP {resp.status_code} - {_corpo_de_erro(resp)}"
            )
        try:
            dados = resp.json()
        except ValueError:
            raise Exception(f"Resposta inválida da API do {pid_nome}.")
        escolhas = dados.get("choices") or []
        conteudo = ""
        if escolhas and isinstance(escolhas[0], dict):
            mensagem = escolhas[0].get("message") or {}
            conteudo = mensagem.get("content") or ""
            if escolhas[0].get("finish_reason") == "length":
                logger.warning(
                    f"[provedores] Resposta do {pid_nome} truncada por limite de tokens "
                    f"para modelo={identificador}."
                )
        if conteudo:
            return conteudo
        ultimo_erro = Exception(f"Resposta vazia da API do {pid_nome}.")
    if ultimo_erro is None:
        ultimo_erro = Exception(f"Falha ao chamar a API do {pid_nome}.")
    raise ultimo_erro


def _gerar_anthropic(pid, cfg, identificador, prompt, images_base64, temperature, seed, json_mode, max_retries, timeout):
    pid_nome = cfg["nome"]
    chaves = chaves_efetivas(pid)
    if not chaves:
        raise Exception(
            f"Nenhuma chave da API do {pid_nome} cadastrada para este usuário. "
            "Cadastre uma em Configurações."
        )
    base = {
        "model": identificador,
        "max_tokens": 16000,
        "messages": [
            {"role": "user", "content": _conteudo_anthropic(prompt, images_base64)}
        ],
        "temperature": max(0.0, min(temperature, 1.0)),
    }
    variantes = [dict(base), {"model": base["model"], "max_tokens": 4096, "messages": base["messages"]}]
    url = f"{cfg['base_url']}/messages"
    limite = max(3, min(len(chaves) * 2 + 2, 10))
    indice_variante = 0
    ultimo_erro = None
    for tentativa in range(limite):
        chave = _proxima_chave_provedor(pid, chaves)
        if chave is None:
            _limpar_cooldowns(pid)
            chave = _proxima_chave_provedor(pid, chaves)
        if chave is None:
            break
        payload = variantes[min(indice_variante, len(variantes) - 1)]
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={
                    "x-api-key": chave,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
        except requests.exceptions.RequestException as e:
            ultimo_erro = Exception(f"Erro na API do {pid_nome}: {e}")
            logger.warning(
                f"[provedores] Falha de rede no {pid_nome} "
                f"(tentativa {tentativa + 1}/{limite}): {e}"
            )
            continue
        if resp.status_code in (401, 402, 403):
            _marcar_esgotada(pid, chave)
            ultimo_erro = Exception(
                f"Chave do {pid_nome} esgotada ou inválida (HTTP {resp.status_code})."
            )
            continue
        if resp.status_code == 429:
            atraso = COOLDOWN_CHAVE
            try:
                cabecalho = resp.headers.get("Retry-After")
                if cabecalho:
                    atraso = min(float(cabecalho), 60)
            except ValueError:
                pass
            _marcar_cooldown(pid, chave, atraso)
            ultimo_erro = Exception(f"Limite de requisições do {pid_nome} (HTTP 429).")
            continue
        if resp.status_code == 400 and indice_variante < len(variantes) - 1:
            indice_variante += 1
            logger.warning(
                f"[provedores] {pid_nome} recusou max_tokens=16000 - "
                "reduzindo para 4096."
            )
            continue
        if resp.status_code >= 500:
            ultimo_erro = Exception(f"HTTP {resp.status_code} na API do {pid_nome}.")
            continue
        if not resp.ok:
            raise Exception(
                f"Erro na API do {pid_nome}: HTTP {resp.status_code} - {_corpo_de_erro(resp)}"
            )
        try:
            dados = resp.json()
        except ValueError:
            raise Exception(f"Resposta inválida da API do {pid_nome}.")
        blocos = dados.get("content") or []
        conteudo = "".join(
            b.get("text", "")
            for b in blocos
            if isinstance(b, dict) and b.get("type") == "text"
        )
        if dados.get("stop_reason") == "max_tokens":
            logger.warning(
                f"[provedores] Resposta do {pid_nome} truncada por limite de tokens "
                f"para modelo={identificador}."
            )
        if conteudo:
            return conteudo
        ultimo_erro = Exception(f"Resposta vazia da API do {pid_nome}.")
    if ultimo_erro is None:
        ultimo_erro = Exception(f"Falha ao chamar a API do {pid_nome}.")
    raise ultimo_erro


def gerar(model, prompt, images_base64=None, temperature=0.0, seed=None,
          json_mode=False, max_retries=3, timeout=600):
    parsed = parsear_modelo(model)
    if not parsed:
        raise Exception(f"Modelo de provedor inválido: {model}")
    pid, identificador = parsed
    cfg = PROVEDORES[pid]
    if cfg["api"] == "anthropic":
        return _gerar_anthropic(
            pid, cfg, identificador, prompt, images_base64, temperature, seed,
            json_mode, max_retries, timeout,
        )
    return _gerar_openai(
        pid, cfg, identificador, prompt, images_base64, temperature, seed,
        json_mode, max_retries, timeout,
    )
