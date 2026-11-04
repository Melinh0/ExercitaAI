import { useEffect, useRef } from 'react';

const SELETOR_FOCO = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

let modaisAbertos = 0;

function elementosFocaveis(container) {
  return Array.from(container.querySelectorAll(SELETOR_FOCO)).filter(
    (el) => !el.disabled && el.offsetParent !== null
  );
}

function useModalAcessibilidade(aberto, aoFechar) {
  const modalRef = useRef(null);
  const aoFecharRef = useRef(aoFechar);
  aoFecharRef.current = aoFechar;

  useEffect(() => {
    if (!aberto) return undefined;
    const container = modalRef.current;
    if (!container) return undefined;

    modaisAbertos += 1;
    if (modaisAbertos === 1) document.body.style.overflow = 'hidden';

    const focoAnterior = document.activeElement;

    if (!container.contains(document.activeElement)) {
      const focaveis = elementosFocaveis(container);
      if (focaveis.length > 0) focaveis[0].focus();
    }

    const aoTeclar = (e) => {
      if (e.key === 'Escape') {
        const modais = Array.from(document.querySelectorAll('.modal'));
        if (modais[modais.length - 1] !== container) return;
        e.stopPropagation();
        if (aoFecharRef.current) aoFecharRef.current();
        return;
      }
      if (e.key !== 'Tab') return;
      const elementos = elementosFocaveis(container);
      if (elementos.length === 0) return;
      const primeiro = elementos[0];
      const ultimo = elementos[elementos.length - 1];
      if (e.shiftKey && document.activeElement === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    };

    document.addEventListener('keydown', aoTeclar, true);
    return () => {
      modaisAbertos -= 1;
      if (modaisAbertos === 0) document.body.style.overflow = '';
      document.removeEventListener('keydown', aoTeclar, true);
      if (focoAnterior && typeof focoAnterior.focus === 'function' && document.contains(focoAnterior)) {
        focoAnterior.focus();
      }
    };
  }, [aberto]);

  const aoClicarFundo = (e) => {
    if (e.target === e.currentTarget && aoFecharRef.current) aoFecharRef.current();
  };

  return { modalRef, aoClicarFundo };
}

export default useModalAcessibilidade;
