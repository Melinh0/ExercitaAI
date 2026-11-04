import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

const ToastContext = createContext();

export const useToast = () => useContext(ToastContext);

let idSequencial = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const remover = useCallback((id) => {
    setToasts((atual) => atual.filter((t) => t.id !== id));
    if (timersRef.current[id]) {
      clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const toast = useCallback((options) => {
    const opts = typeof options === 'string' ? { message: options } : options;
    const id = ++idSequencial;
    setToasts((atual) => [
      ...atual.slice(-3),
      {
        id,
        variante: 'info',
        titulo: null,
        duracao: 4000,
        ...opts,
      },
    ]);
    timersRef.current[id] = setTimeout(() => remover(id), opts.duracao || 4000);
  }, [remover]);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {toasts.length > 0 && (
        <div className="toast-area" role="status" aria-live="polite">
          {toasts.map((t) => (
            <div key={t.id} className={`toast toast-${t.variante}`}>
              <div className="toast-conteudo">
                {t.titulo && <strong className="toast-titulo">{t.titulo}</strong>}
                <span className="toast-mensagem">{t.message}</span>
              </div>
              <button
                type="button"
                className="toast-fechar"
                onClick={() => remover(t.id)}
                aria-label="Fechar aviso"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
