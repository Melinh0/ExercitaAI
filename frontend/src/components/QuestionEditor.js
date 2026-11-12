import React, { useState, useEffect, useRef } from 'react';
import { getDownloadQuestionTextUrl } from '../services/api';
import { useTasks } from '../contexts/TaskContext';
import usePollingTask from '../hooks/usePollingTask';
import EditableMarkdown from './EditableMarkdown';
import Carousel from './Carousel';

const TIPO_LABELS = {
  interpretacao: 'Interpretação',
  objetiva: 'Objetiva',
  discursiva: 'Discursiva',
  aberta: 'Aberta',
  vf: 'Verdadeiro/Falso',
};

const formatTipo = (tipo) => {
  if (!tipo) return '';
  const key = String(tipo).toLowerCase().trim();
  return TIPO_LABELS[key] || tipo;
};

function QuestionEditor({ question, onSave, onDelete, topicName, imageFilename, qIdx, currentIdx, selectedModel }) {
  const { startTask, isRunning } = useTasks();
  const { acompanhar } = usePollingTask();
  const [enunciado, setEnunciado] = useState(question.enunciado || '');
  const [resposta, setResposta] = useState(question.resposta || '');
  const [explicacao, setExplicacao] = useState(question.explicacao || '');
  const [customPrompt, setCustomPrompt] = useState('');
  const [originalEnunciado, setOriginalEnunciado] = useState(question.enunciado || '');
  const [originalResposta, setOriginalResposta] = useState(question.resposta || '');
  const [originalExplicacao, setOriginalExplicacao] = useState(question.explicacao || '');
  const [enhancing, setEnhancing] = useState(false);
  const melhoriaEmAndamento = enhancing || isRunning('enhance_question');
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [dismissedSuggestions, setDismissedSuggestions] = useState(false);
  const [slideIndex, setSlideIndex] = useState(0);
  const [dirty, setDirty] = useState(false);
  const autoSaveRef = useRef(null);

  useEffect(() => {
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    if (!enunciado && !resposta && !explicacao) return undefined;
    autoSaveRef.current = setTimeout(() => {
      onSave({ enunciado, resposta, explicacao, idx: currentIdx });
      fetch('/save_example', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: topicName,
          image_filename: imageFilename,
          q_idx: qIdx,
          enunciado,
          resposta,
          explicacao,
        }),
      }).catch((err) => console.error('Erro ao salvar exemplo:', err));
      setOriginalEnunciado(enunciado);
      setOriginalResposta(resposta);
      setOriginalExplicacao(explicacao);
      setDirty(false);
    }, 1500);
    return () => {
      if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    };
  }, [enunciado, resposta, explicacao, onSave, topicName, imageFilename, qIdx, currentIdx]);

  useEffect(() => {
    setEnunciado(question.enunciado || '');
    setResposta(question.resposta || '');
    setExplicacao(question.explicacao || '');
    setOriginalEnunciado(question.enunciado || '');
    setOriginalResposta(question.resposta || '');
    setOriginalExplicacao(question.explicacao || '');
    setDirty(false);
    setShowSuggestions(false);
    setDismissedSuggestions(false);
    setSuggestions([]);
    setCustomPrompt('');
  }, [question]);

  const fetchSuggestions = async () => {
    if (loadingSuggestions || dismissedSuggestions) return;
    if (showSuggestions && suggestions.length > 0) return;
    setLoadingSuggestions(true);
    try {
      const response = await fetch('/suggest_prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'enhance_question',
          topic: topicName,
          image_filename: imageFilename,
          q_idx: qIdx,
          enunciado,
          resposta,
          explicacao,
          instrucoes: customPrompt,
          model: selectedModel,
        }),
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
    fetchSuggestions();
  };

  const applySuggestion = (suggestion) => {
    setCustomPrompt(suggestion);
    setShowSuggestions(false);
    setDismissedSuggestions(true);
  };

  const enhanceWithRAG = async () => {
    if (!enunciado && !explicacao && !resposta) {
      alert('Não há conteúdo para melhorar.');
      return;
    }
    setEnhancing(true);
    try {
      const idMelhoria = await startTask('enhance_question', {
        topic: topicName,
        image_filename: imageFilename,
        q_idx: qIdx,
        enunciado,
        explicacao,
        resposta,
        custom_prompt: customPrompt,
        model: selectedModel,
      });
      acompanhar(idMelhoria, (resultado) => {
        if (resultado && resultado.explicacao) {
          setExplicacao(resultado.explicacao);
          if (resultado.resposta) {
            setResposta(resultado.resposta);
          }
          setDirty(true);
        }
      });
      setCustomPrompt('');
      setShowSuggestions(false);
      setDismissedSuggestions(false);
    } catch (err) {
      alert('Erro ao iniciar melhoria: ' + (err.message || err));
    } finally {
      setEnhancing(false);
    }
  };

  const alternativas = Array.isArray(question.alternativas) ? question.alternativas : [];

  const slides = [
    {
      key: 'enunciado',
      label: 'Enunciado',
      content: (
        <div className="carousel-slide-inner">
          {alternativas.length > 0 && (
            <div className="alternatives-display">
              <strong>Alternativas:</strong>
              <ul>
                {alternativas.map((alt, idx) => (
                  <li key={idx}>{alt}</li>
                ))}
              </ul>
            </div>
          )}
          <EditableMarkdown
            label="Enunciado (clique para editar)"
            value={enunciado}
            placeholder="Transcrição do enunciado da questão"
            minRows={10}
            onChange={(v) => { setEnunciado(v); setDirty(true); }}
          />
        </div>
      ),
    },
    {
      key: 'resposta',
      label: 'Resposta',
      content: (
        <div className="carousel-slide-inner">
          <EditableMarkdown
            label="Resposta (clique para editar)"
            value={resposta}
            placeholder="Resposta da questão"
            minRows={6}
            onChange={(v) => { setResposta(v); setDirty(true); }}
          />
          <div className="form-group">
            <label><strong>Instruções adicionais (opcional):</strong></label>
            <div className="enhance-column">
              <textarea
                rows="4"
                className="form-control"
                placeholder="Ex: Explique de forma mais simples, use exemplos práticos..."
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                onClick={handleClickPrompt}
              />
              <button
                type="button"
                onClick={enhanceWithRAG}
                className="button button-outline"
                disabled={enhancing || melhoriaEmAndamento}
              >
                {melhoriaEmAndamento ? 'Processando...' : (enhancing ? 'Iniciando...' : 'Melhorar com Contexto')}
              </button>
            </div>
            {loadingSuggestions && <span className="hint-text">Carregando sugestões...</span>}
            {showSuggestions && suggestions.length > 0 && (
              <div className="suggestions-container">
                <p>Sugestões de prompts:</p>
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
                Mostrar sugestões de prompts
              </button>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'resolucao',
      label: 'Resolução',
      content: (
        <div className="carousel-slide-inner">
          <EditableMarkdown
            label="Resolução e interpretação (clique para editar)"
            value={explicacao}
            placeholder="Explicação/resolução da questão"
            minRows={12}
            onChange={(v) => { setExplicacao(v); setDirty(true); }}
          />
          <small className="hint-text">
            Use **negrito**, *itálico* e LaTeX ($...$ ou $$...$$).
          </small>
        </div>
      ),
    },
  ];

  return (
    <div className="edit-form">
      <div className="resolucao-block">
        <div className="resolucao-block-header">
          <h3>Questão {question.questao || 'S/N'}</h3>
          {question.tipo && <span className="question-type-badge">{formatTipo(question.tipo)}</span>}
        </div>
        <Carousel slides={slides} activeIndex={slideIndex} onIndexChange={setSlideIndex} />
        <div className="action-buttons">
          <span className="auto-save-status" style={{fontSize: '0.8rem', color: '#64748b', marginRight: '1rem'}}>
            {dirty ? 'Salvando...' : 'Salvo automaticamente'}
          </span>
          <button type="button" onClick={onDelete} className="delete-button">Deletar Questão</button>
          <a
            href={getDownloadQuestionTextUrl(topicName, imageFilename, qIdx, currentIdx)}
            className="button button-secundario"
          >
            Baixar Resolução (Texto)
          </a>
        </div>
      </div>
    </div>
  );
}

export default React.memo(QuestionEditor);