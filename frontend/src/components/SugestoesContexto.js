import { useRef, useEffect } from 'react';
import usePromptSuggestions from './PromptSuggestions';

function SugestoesContexto({ ativo, topico, instrucoes, onAplicar }) {
  const aplicar = (sugestao) => {
    if (onAplicar) {
      onAplicar(sugestao);
      return;
    }
    window.open(`https://www.google.com/search?q=${encodeURIComponent(sugestao)}`, '_blank', 'noopener,noreferrer');
  };

  const { onClick, suggestionsElement } = usePromptSuggestions({
    mode: 'search_articles',
    payload: { context: topico, topic: topico, instrucoes: instrucoes || '' },
    onApply: aplicar,
    label: 'Sugestões do que pesquisar:',
    reopenLabel: 'Mostrar sugestões do que pesquisar',
    resetKey: ativo ? 'ativo' : 'inativo',
  });

  const sugestoesRef = useRef(null);
  sugestoesRef.current = onClick;
  const autoRef = useRef(false);

  useEffect(() => {
    if (ativo && !autoRef.current) {
      autoRef.current = true;
      const timer = setTimeout(() => {
        if (sugestoesRef.current) sugestoesRef.current();
      }, 400);
      return () => clearTimeout(timer);
    }
    if (!ativo) autoRef.current = false;
    return undefined;
  }, [ativo]);

  if (!ativo) return null;
  return suggestionsElement;
}

export default SugestoesContexto;
