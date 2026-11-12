import json
import re

VALIDOS = set('"\\/bfnrtu')
HEX = set('0123456789abcdefABCDEF')

COMANDOS_T = {
    'text', 'textbf', 'textit', 'texttt', 'textrm', 'textsf', 'textsc',
    'textup', 'textnormal', 'textstyle', 'times', 'theta', 'tau', 'to', 'top',
    'tag', 'triangle', 'triangledown', 'triangleleft', 'triangleright',
    'triangleq', 'therefore', 'tan', 'tanh', 'tfrac', 'tilde', 'tt',
    'thickapprox', 'thickspace', 'thinspace', 'twoheadleftarrow',
    'twoheadrightarrow', 'leftrightarrow',
}
COMANDOS_N = {
    'nabla', 'notin', 'not', 'newcommand', 'newline', 'noindent',
    'napprox', 'nmid', 'neq', 'neg', 'nsubseteq', 'nsupseteq', 'nu', 'ni',
    'nearrow', 'nwarrow', 'ngtr', 'nleq', 'ngeq',
    'nsim', 'ncong', 'nequiv', 'nleftarrow', 'nrightarrow', 'nleftrightarrow',
    'nRightarrow', 'nLeftarrow', 'nvDash', 'nVDash', 'nVdash',
}
COMANDOS_R = {
    'rho', 'right', 'rightarrow', 'rightarrowtail', 'rightleftharpoons',
    'rightleftarrows', 'rightrightarrows', 'rightthreetimes', 'rule',
    'renewcommand', 'rm', 'Rightarrow', 'rangle',
}
_CONTROLE_LETRA = {'\x08': '\\b', '\x0b': '\\v', '\x0c': '\\f'}


def _e_letra(ch):
    return bool(ch) and ch.isascii() and ch.isalpha()


def _fim_do_comando(texto, inicio):
    fim = inicio
    n = len(texto)
    while fim < n and _e_letra(texto[fim]):
        fim += 1
    return fim


def _apos_nova_linha(texto, i):
    if i >= 2 and texto[i - 2] == '\\' and texto[i - 1] in 'nr':
        return True
    return i >= 1 and texto[i - 1] in '\n\r'


def _escape_vira_comando(prox, texto, i):
    if prox in 'bfr':
        return _e_letra(texto[i + 2:i + 3])
    if prox == 't':
        fim = _fim_do_comando(texto, i + 1)
        if texto[i + 1:fim] not in COMANDOS_T:
            return False
        if texto[fim:fim + 1] == '{':
            return True
        return not _apos_nova_linha(texto, i)
    if prox == 'n':
        fim = _fim_do_comando(texto, i + 1)
        return texto[i + 1:fim] in COMANDOS_N
    return False


def sanitizar_backslashes(texto):
    saida = []
    i = 0
    n = len(texto)
    while i < n:
        ch = texto[i]
        if ch != '\\':
            saida.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            saida.append('\\\\')
            i += 1
            continue
        prox = texto[i + 1]
        if prox == 'u':
            hexa = texto[i + 2:i + 6]
            if len(hexa) == 4 and all(c in HEX for c in hexa):
                saida.append(texto[i:i + 6])
                i += 6
                continue
            saida.append('\\\\')
            i += 1
            continue
        if prox in VALIDOS:
            if _escape_vira_comando(prox, texto, i):
                saida.append('\\\\' + prox)
            else:
                saida.append(texto[i:i + 2])
            i += 2
            continue
        saida.append('\\\\')
        i += 1
    return ''.join(saida)


def carregar_json_do_modelo(texto):
    if not texto or not isinstance(texto, str):
        return None
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    sanitizado = sanitizar_backslashes(texto)
    try:
        return json.loads(sanitizado)
    except json.JSONDecodeError:
        try:
            return json.loads(sanitizado, strict=False)
        except Exception:
            return None


def _reparar_parte(parte):
    def troca_controle(m):
        ch = m.group(0)
        if not _e_letra(parte[m.end():m.end() + 1]):
            return ch
        return _CONTROLE_LETRA[ch]

    def troca_tab(m):
        fim = _fim_do_comando(parte, m.end())
        if 't' + parte[m.end():fim] in COMANDOS_T:
            return '\\t'
        return m.group(0)

    def troca_nova_linha(m):
        fim = _fim_do_comando(parte, m.end())
        if 'n' + parte[m.end():fim] in COMANDOS_N:
            return '\\n'
        return m.group(0)

    def troca_retorno(m):
        fim = _fim_do_comando(parte, m.end())
        if 'r' + parte[m.end():fim] in COMANDOS_R:
            return '\\r'
        return m.group(0)

    parte = re.sub('[\x08\x0b\x0c]', troca_controle, parte)
    parte = re.sub('\t', troca_tab, parte)
    parte = re.sub('\n', troca_nova_linha, parte)
    parte = re.sub('\r', troca_retorno, parte)
    return parte


def reparar_texto_latex(texto):
    if not texto or not isinstance(texto, str):
        return texto
    partes = re.split(r'(```[\s\S]*?```|`[^`\n]*`)', texto)
    for i in range(0, len(partes), 2):
        partes[i] = _reparar_parte(partes[i])
    return ''.join(partes)
