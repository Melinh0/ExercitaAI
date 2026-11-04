import { useRef, useEffect, useCallback } from 'react';

export default function usePollingTask() {
  const intervalRef = useRef(null);

  const limpar = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const acompanhar = useCallback((taskId, aoConcluir, aoFalhar, aoProgredir) => {
    limpar();
    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/tasks/${taskId}`, { credentials: 'same-origin' });
        if (!res.ok) return;
        const task = await res.json();
        if (aoProgredir) aoProgredir(task);
        if (task.status === 'completed') {
          limpar();
          if (aoConcluir) aoConcluir(task.result);
        } else if (task.status === 'failed') {
          limpar();
          if (aoFalhar) aoFalhar(task.error);
        }
      } catch (err) {
        console.error('Erro ao consultar status da tarefa:', err);
      }
    }, 1500);
  }, [limpar]);

  useEffect(() => limpar, [limpar]);

  return { acompanhar, limpar };
}