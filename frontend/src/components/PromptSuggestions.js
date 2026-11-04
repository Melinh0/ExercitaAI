import React, { useState, useEffect, useRef } from 'react';

function usePromptSuggestions({ mode, payload = {}, onApply, resetKey = null, label = 'Sugestões de prompts:', reopenLabel = 'Mostrar sugestões de prompts' }) {
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [dismissedSuggestions, setDismissedSuggestions] = useState(false);
  const dismissedRef = useRef(false);
  dismissedRef.current = dismissedSuggestions;

  useEffect(() => {
    setShowSuggestions(false);
    setDismissedSuggestions(false);
    setSuggestions([]);
    setLoadingSuggestions(false);
  }, [resetKey]);

  const fetchSuggestions = async (force = false) => {
    if (loadingSuggestions) return;
    if (!force) {
      if (dismissedSuggestions) return;
      if (showSuggestions && suggestions.length > 0) return;
    }
    setLoadingSuggestions(true);
    try {
      const response = await fetch('/suggest_prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, ...payload })
      });
      const data = await response.json();
      if (data.success) {
        setSuggestions(data.suggestions || []);
        setShowSuggestions(true);
      }
    } catch (err) {
      console.error('Erro ao buscar sugestões:', err);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handleClickPrompt = () => {
    if (dismissedSuggestions) return;
    fetchSuggestions();
  };

  const handleCloseSuggestions = () => {
    setShowSuggestions(false);
    setDismissedSuggestions(true);
  };

  const handleReopenSuggestions = () => {
    setDismissedSuggestions(false);
    setSuggestions([]);
    fetchSuggestions(true);
  };

  const applySuggestion = (suggestion) => {
    if (onApply) onApply(suggestion);
    setShowSuggestions(false);
    setDismissedSuggestions(true);
  };

  const suggestionsElement = (
    <>
      {loadingSuggestions && <span className="hint-text">Carregando sugestões...</span>}
      {showSuggestions && suggestions.length > 0 && (
        <div className="suggestions-container">
          <p>{label}</p>
          <ul>
            {suggestions.map((suggestion, idx) => (
              <li key={idx}>
                <button
                  type="button"
                  onClick={() => applySuggestion(suggestion)}
                  className="suggestion-button"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={handleCloseSuggestions}
            className="suggestion-close-btn"
          >
            Fechar sugestões
          </button>
        </div>
      )}
      {!showSuggestions && dismissedSuggestions && (
        <button
          type="button"
          onClick={handleReopenSuggestions}
          className="reopen-suggestions-btn"
        >
          {reopenLabel}
        </button>
      )}
    </>
  );

  return { onClick: handleClickPrompt, suggestionsElement };
}

export default usePromptSuggestions;
