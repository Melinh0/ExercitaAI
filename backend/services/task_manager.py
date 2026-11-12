import uuid
import time
import threading
import logging
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)

_tasks = {}
_lock = threading.Lock()
TASK_TTL_SECONDS = 7200


def _now():
    return datetime.utcnow().isoformat()


def _cleanup_locked():
    cutoff = datetime.utcnow() - timedelta(seconds=TASK_TTL_SECONDS)
    to_remove = []
    for tid, t in _tasks.items():
        if t['status'] in ('completed', 'failed'):
            try:
                if datetime.fromisoformat(t['updated_at']) < cutoff:
                    to_remove.append(tid)
            except Exception:
                pass
    for tid in to_remove:
        _tasks.pop(tid, None)


def _tarefa_ativa_com_chave(nome, user_id, dedup_key):
    for t in _tasks.values():
        if t['user_id'] != user_id or t['name'] != nome:
            continue
        if t.get('dedup_key') != dedup_key:
            continue
        if t['status'] in ('pending', 'running'):
            return t['id']
    return None


def create_task(name, user_id, params=None, dedup_key=None):
    with _lock:
        _cleanup_locked()
        if dedup_key:
            existente = _tarefa_ativa_com_chave(name, user_id, dedup_key)
            if existente:
                return existente, True
        tid = str(uuid.uuid4())
        _tasks[tid] = {
            'id': tid,
            'name': name,
            'user_id': user_id,
            'status': 'pending',
            'progress': 0,
            'message': 'Aguardando...',
            'created_at': _now(),
            'updated_at': _now(),
            'result': None,
            'error': None,
            'params': params or {},
            'dedup_key': dedup_key,
        }
        return tid, False


def get_task(tid):
    with _lock:
        t = _tasks.get(tid)
        return dict(t) if t else None


def list_user_tasks(user_id, include_result=False):
    with _lock:
        out = []
        for t in _tasks.values():
            if t['user_id'] != user_id:
                continue
            d = dict(t)
            if not include_result:
                d.pop('result', None)
            out.append(d)
        return out


def update_task(tid, **kwargs):
    with _lock:
        t = _tasks.get(tid)
        if t:
            if kwargs.get('progress') is not None:
                kwargs['progress'] = max(kwargs['progress'], t.get('progress') or 0)
            t.update(kwargs)
            t['updated_at'] = _now()


def _batida_progresso(tid):
    while True:
        time.sleep(2)
        with _lock:
            t = _tasks.get(tid)
            if not t or t['status'] != 'running':
                return
            atual = t.get('progress') or 0
            if atual < 95:
                t['progress'] = atual + 1
                t['updated_at'] = _now()


def delete_task(tid):
    with _lock:
        _tasks.pop(tid, None)


def run_async(tid, fn, *args, **kwargs):
    app = current_app._get_current_object()

    def wrapper():
        with app.app_context():
            update_task(tid, status='running', message='Processando...')
            threading.Thread(target=_batida_progresso, args=(tid,), daemon=True).start()
            try:
                result = fn(*args, **kwargs)
                update_task(tid, status='completed', result=result, progress=100, message='Concluído')
            except Exception as e:
                logger.exception(f"Task {tid} falhou: {e}")
                update_task(tid, status='failed', error=str(e), message='Erro')

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread