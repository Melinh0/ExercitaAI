import contextvars
from concurrent.futures import Future, ThreadPoolExecutor


def submeter_com_contexto(executor: ThreadPoolExecutor, funcao, *args, **kwargs) -> Future:
    contexto = contextvars.copy_context()
    return executor.submit(contexto.run, funcao, *args, **kwargs)
