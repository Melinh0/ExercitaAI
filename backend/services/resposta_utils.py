import re

RESPOSTAS_VERDADEIRO_FALSO = ('v', 'verdadeiro', 'f', 'falso')


def _normalizar(texto):
    return re.sub(r'\s+', ' ', texto or '').strip().rstrip('.:;').strip().lower()


def extrair_resposta_curta(gabarito):
    texto = (gabarito or '').strip()
    finais = re.findall(r'resposta\s*final\s*[:\-]\s*([^\n]+)', texto, flags=re.IGNORECASE)
    if finais:
        return finais[-1].strip()
    simples = re.search(r'resposta\s*[:\-]\s*([^\n]+)', texto, flags=re.IGNORECASE)
    if simples:
        return simples.group(1).strip()
    return texto


def eh_resposta_verdadeiro_falso(resposta):
    normalizada = re.sub(r'[^a-z]+', ' ', _normalizar(extrair_resposta_curta(resposta))).strip()
    if normalizada in RESPOSTAS_VERDADEIRO_FALSO:
        return True
    return re.sub(r'^(verdadeiro|falso)\s+', '', normalizada) in RESPOSTAS_VERDADEIRO_FALSO


def normalizar_tipo_questao(tipo, resposta):
    tipo_atual = (tipo or '').strip().lower()
    if 'vf' in tipo_atual or 'verdadeiro' in tipo_atual or 'falso' in tipo_atual:
        return tipo_atual or 'vf'
    if eh_resposta_verdadeiro_falso(resposta):
        return 'vf'
    return tipo_atual


def _limpar(candidata):
    candidata = re.sub(r'^[\s*#:>\-–]+', '', candidata.strip())
    candidata = re.sub(r'[\s*]+$', '', candidata)
    return candidata.strip()


def extrair_resposta_da_explicacao(explicacao, resposta_atual=''):
    texto = explicacao or ''
    atual = (resposta_atual or '').strip()
    padroes = [
        r'resposta\s+final\s*\**\s*[:\-]+\s*\**\s*(.+)',
        r'\*\*\s*resposta\s*\**\s*[:\-]+\s*\**\s*(.+)',
        r'^\s*resposta\s*[:\-]+\s*(.+)$',
    ]
    for padrao in padroes:
        achadas = re.findall(padrao, texto, flags=re.IGNORECASE | re.MULTILINE)
        candidatas = [_limpar(a.splitlines()[0]) for a in achadas if a.strip()]
        candidatas = [c for c in candidatas if c]
        if candidatas:
            candidata = candidatas[-1]
            if atual and _normalizar(atual) == _normalizar(candidata):
                return atual
            return candidata
    return atual
