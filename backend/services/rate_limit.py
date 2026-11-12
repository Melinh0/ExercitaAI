import threading
import time
from collections import deque

_trava = threading.Lock()
_eventos = {}  


def _podar(eventos, janela_segundos, agora):
    limite = agora - janela_segundos
    while eventos and eventos[0] <= limite:
        eventos.popleft()


def consultar(chave, janela_segundos):
    agora = time.time()
    with _trava:
        eventos = _eventos.get(chave)
        if not eventos:
            return 0
        _podar(eventos, janela_segundos, agora)
        return len(eventos)


def registrar(chave, janela_segundos, maximo):
    agora = time.time()
    with _trava:
        eventos = _eventos.setdefault(chave, deque())
        _podar(eventos, janela_segundos, agora)
        if len(eventos) >= maximo:
            return len(eventos)
        eventos.append(agora)
        return len(eventos)


def bloqueado(chave, janela_segundos, maximo):
    return consultar(chave, janela_segundos) >= maximo


def segundos_para_liberar(chave, janela_segundos):
    agora = time.time()
    with _trava:
        eventos = _eventos.get(chave)
        if not eventos:
            return 0
        _podar(eventos, janela_segundos, agora)
        if not eventos:
            return 0
        return max(0, int(janela_segundos - (agora - eventos[0])))


def limpar(chave):
    with _trava:
        _eventos.pop(chave, None)


def limpar_tudo():
    with _trava:
        _eventos.clear()
