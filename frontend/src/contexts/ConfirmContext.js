import React, { createContext, useContext, useState, useCallback } from 'react';
import { useToast } from './ToastContext';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const ConfirmContext = createContext();

export const useConfirm = () => useContext(ConfirmContext);

export function ConfirmProvider({ children }) {
  const { toast } = useToast();
  const [confirmState, setConfirmState] = useState(null);
  const [alertState, setAlertState] = useState(null);

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      setConfirmState({
        title: 'Confirmação',
        confirmText: 'Confirmar',
        cancelText: 'Cancelar',
        variant: 'danger',
        ...options,
        onConfirm: () => {
          setConfirmState(null);
          resolve(true);
        },
        onCancel: () => {
          setConfirmState(null);
          resolve(false);
        },
      });
    });
  }, []);

  const alert = useCallback((options) => {
    const opts = typeof options === 'string' ? { message: options } : options;
    if (opts.variant === 'success') {
      toast({ titulo: opts.title === 'Sucesso' ? null : opts.title, message: opts.message, variante: 'sucesso' });
      return Promise.resolve(true);
    }
    return new Promise((resolve) => {
      setAlertState({
        title: 'Aviso',
        confirmText: 'OK',
        variant: 'info',
        ...opts,
        onClose: () => {
          setAlertState(null);
          resolve(true);
        },
      });
    });
  }, [toast]);

  const cancelarConfirm = confirmState ? confirmState.onCancel : null;
  const fecharAlert = alertState ? alertState.onClose : null;

  const { modalRef: refConfirm, aoClicarFundo: fundoConfirm } = useModalAcessibilidade(!!confirmState, cancelarConfirm);
  const { modalRef: refAlert, aoClicarFundo: fundoAlert } = useModalAcessibilidade(!!alertState, fecharAlert);

  return (
    <ConfirmContext.Provider value={{ confirm, alert }}>
      {children}
      {confirmState && (
        <div className="modal modal-aberto" onClick={fundoConfirm} ref={refConfirm}>
          <div className="modal-content confirm-modal">
            <h2>{confirmState.title}</h2>
            <p className="confirm-modal-message">{confirmState.message}</p>
            <div className="form-actions confirm-modal-actions">
              <button
                type="button"
                className="button confirm-btn-cancel"
                onClick={confirmState.onCancel}
              >
                {confirmState.cancelText}
              </button>
              <button
                type="button"
                className={`button confirm-btn-confirm confirm-btn-${confirmState.variant}`}
                onClick={confirmState.onConfirm}
              >
                {confirmState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
      {alertState && (
        <div className="modal modal-aberto" onClick={fundoAlert} ref={refAlert}>
          <div className="modal-content confirm-modal">
            <h2>{alertState.title}</h2>
            <p className="confirm-modal-message">{alertState.message}</p>
            <div className="form-actions confirm-modal-actions">
              <button
                type="button"
                className={`button confirm-btn-confirm confirm-btn-${alertState.variant}`}
                onClick={alertState.onClose}
              >
                {alertState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}
