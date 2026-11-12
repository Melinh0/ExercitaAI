import json
import re

_VALIDOS = set('"\\/bfnrtu')
_HEX = set('0123456789abcdefABCDEF')

_COMANDOS_T = {
    'text', 'textbf', 'textit', 'texttt', 'textrm', 'textsf', 'textsc',
    'textup', 'textnormal', 'textstyle', 'times', 'theta', 'tau', 'to', 'top',
    'tag', 'triangle', 'triangledown', 'triangleleft', 'triangleright',
    'triangleq', 'therefore', 'tan', 'tanh', 'tfrac', 'tilde', 'tt',
    'thickapprox', 'thickspace', 'thinspace', 'twoheadleftarrow',
    'twoheadrightarrow', 'leftrightarrow',
}
_COMANDOS_N = {
    'nabla', 'notin', 'not', 'newcommand', 'newline', 'noindent',
    'napprox', 'nmid', 'neq', 'neg', 'nsubseteq', 'nsupseteq', 'nu', 'ni',
    'nearrow', 'nwarrow', 'ngtr', 'nleq', 'ngeq',
    'nsim', 'ncong', 'nequiv', 'nleftarrow', 'nrightarrow', 'nleftrightarrow',
    'nRightarrow', 'nLeftarrow', 'nvDash', 'nVDash', 'nVdash',
}


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
        if texto[i + 1:fim] not in _COMANDOS_T:
            return False
        if texto[fim:fim + 1] == '{':
            return True
        return not _apos_nova_linha(texto, i)
    if prox == 'n':
        fim = _fim_do_comando(texto, i + 1)
        return texto[i + 1:fim] in _COMANDOS_N
    return False


def _sanitizar_backslashes(json_str):
    saida = []
    i = 0
    n = len(json_str)
    while i < n:
        ch = json_str[i]
        if ch != '\\':
            saida.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            saida.append('\\\\')
            i += 1
            continue
        prox = json_str[i + 1]
        if prox == 'u':
            hexa = json_str[i + 2:i + 6]
            if len(hexa) == 4 and all(c in _HEX for c in hexa):
                saida.append(json_str[i:i + 6])
                i += 6
                continue
            saida.append('\\\\')
            i += 1
            continue
        if prox in _VALIDOS:
            if _escape_vira_comando(prox, json_str, i):
                saida.append('\\\\' + prox)
            else:
                saida.append(json_str[i:i + 2])
            i += 2
            continue
        saida.append('\\\\')
        i += 1
    return ''.join(saida)


def extract_json_from_response(text: str):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    candidatos = [i for i in (text.find('{'), text.find('[')) if i != -1]
    if not candidatos:
        return None
    start = min(candidatos)
    stack = []
    in_string = False
    escape = False
    end = None
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if ch in '{[':
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
                if not stack:
                    end = i
                    break
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()
                if not stack:
                    end = i
                    break
    if end is None:
        json_str = text[start:]
        if escape:
            json_str = json_str[:-1]
        if in_string:
            json_str += '"'
        for abertura in reversed(stack):
            json_str += '}' if abertura == '{' else ']'
    else:
        json_str = text[start:end + 1]
    json_str = _sanitizar_backslashes(json_str)
    json_str = re.sub(r',?\s*"[^"]*"\s*:\s*(?=[}\]])', '', json_str)
    json_str = re.sub(r'(?<=["\d}])\s+(?="[^"]*":)', ',', json_str)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        try:
            return json.loads(json_str, strict=False)
        except Exception:
            return None
