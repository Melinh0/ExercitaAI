import React, { useState, useEffect, useRef } from 'react';
import { getNotes, addNote, updateNote, deleteNote } from '../services/api';
import { useTasks } from '../contexts/TaskContext';
import { useConfirm } from '../contexts/ConfirmContext';
import usePollingTask from '../hooks/usePollingTask';
import EditableMarkdown from './EditableMarkdown';
import { IconeSetaEsquerda, IconeSetaDireita } from './Icons';

function AnnotationEditor({ topicName, imageFilename, onAnnotationSaved, transcriptionMethod = 'tesseract', selectedModel, ocrModel }) {
  const { startTask, isRunning } = useTasks();
  const { acompanhar } = usePollingTask();
  const { confirm, alert } = useConfirm();
  const [notes, setNotes] = useState([]);
  const [text, setText] = useState('');
  const [extraPrompt, setExtraPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const analiseEmAndamento = loading || isRunning('analyze_image_insight');
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [dismissedSuggestions, setDismissedSuggestions] = useState(false);
  const [carouselIndex, setCarouselIndex] = useState(0);

  const loadNotes = () => {
    getNotes(topicName, { image_filename: imageFilename }).then(res => {
      const data = Array.isArray(res.data) ? res.data : [];
      setNotes(data);
      if (carouselIndex >= data.length) setCarouselIndex(Math.max(0, data.length - 1));
    });
  };

  useEffect(() => { loadNotes(); }, [topicName, imageFilename]);

  const autoSaveRef = useRef(null);
  useEffect(() => {
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    if (!text.trim()) return;
    autoSaveRef.current = setTimeout(() => {
      handleSave();
    }, 1500);
    return () => { if (autoSaveRef.current) clearTimeout(autoSaveRef.current); };
  }, [text, topicName, imageFilename]);

  const fetchSuggestions = async () => {
    if (loadingSuggestions || dismissedSuggestions) return;
    if (showSuggestions && suggestions.length > 0) return;
    setLoadingSuggestions(true);
    try {
      const response = await fetch('/suggest_prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'annotation_insight',
          topic: topicName,
          model: selectedModel
        })
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

  const handleClickExtraPrompt = () => {
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
    setExtraPrompt(suggestion);
    setShowSuggestions(false);
    setDismissedSuggestions(true);
  };

  const handleSave = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await addNote(topicName, { text, image_filename: imageFilename });
      setText('');
      setExtraPrompt('');
      loadNotes();
      if (onAnnotationSaved) onAnnotationSaved();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao salvar anotação.',
        variant: 'danger',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    const confirmed = await confirm({
      title: 'Remover anotação',
      message: 'Tem certeza que deseja remover esta anotação? Essa ação não pode ser desfeita.',
      confirmText: 'Remover',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    await deleteNote(topicName, id);
    loadNotes();
    if (carouselIndex > 0 && notes.length - 1 <= carouselIndex) setCarouselIndex(carouselIndex - 1);
  };

  const handleAnalyze = async () => {
    if (!imageFilename) {
      await alert({
        title: 'Aviso',
        message: 'Nenhuma imagem selecionada para análise.',
        variant: 'warning',
      });
      return;
    }
    setLoading(true);
    try {
      const idAnalise = await startTask('analyze_image_insight', {
        topic: topicName,
        image_filename: imageFilename,
        model: selectedModel || 'gemma3:4b',
        extra_prompt: extraPrompt,
        transcription_method: transcriptionMethod,
        ocr_model: transcriptionMethod === 'llm' ? (ocrModel || undefined) : undefined,
      });
      acompanhar(idAnalise, (resultado) => {
        if (resultado && resultado.insight) {
          setText(prev => (prev ? prev + '\n\n' : '') + resultado.insight);
        }
      });
      setExtraPrompt('');
      setShowSuggestions(false);
      setDismissedSuggestions(false);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar análise: ' + (err.message || err),
        variant: 'danger',
      });
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const currentNote = notes[carouselIndex] || null;
  const totalNotes = notes.length;
  const canPrev = carouselIndex > 0;
  const canNext = carouselIndex < totalNotes - 1;

  return (
    <div className="annotation-editor">
      <div className="notes-carousel">
        <div className="carousel-container">
          <div className="carousel-slide">
            {totalNotes > 0 ? (
              <div className="note-item">
                <EditableMarkdown
                  value={currentNote.text}
                  onChange={async (newText) => {
                    if (newText !== currentNote.text) {
                      await updateNote(topicName, currentNote.id, { text: newText });
                      loadNotes();
                      if (onAnnotationSaved) onAnnotationSaved();
                    }
                  }}
                  placeholder="Anotação vazia"
                />
                <div className="note-meta" style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                  <small>{new Date(currentNote.timestamp).toLocaleString()}</small>
                  <button onClick={() => handleDelete(currentNote.id)} className="button button-outline" style={{flex: '0 0 auto', marginLeft: '1rem', padding: '0.2rem 0.7rem', fontSize: '0.72rem', whiteSpace: 'nowrap'}}>Excluir</button>
                </div>
              </div>
            ) : (
              <p className="hint-text">Nenhuma anotação para esta imagem.</p>
            )}
          </div>
          <div className="carousel-actions">
            {totalNotes > 1 && (
              <>
                <span className="hint-text" style={{fontSize: '0.75rem', marginRight: '0.4rem'}}>{carouselIndex + 1} / {totalNotes}</span>
                <button onClick={() => setCarouselIndex(prev => Math.max(0, prev - 1))} disabled={!canPrev} className="button button-outline"><IconeSetaEsquerda size={14} /></button>
                <button onClick={() => setCarouselIndex(prev => Math.min(totalNotes - 1, prev + 1))} disabled={!canNext} className="button button-outline"><IconeSetaDireita size={14} /></button>
              </>
            )}
          </div>
        </div>
      </div>
      <div className="edit-area">
        <EditableMarkdown
          label="Anotação (clique para editar, Markdown/LaTeX suportado)"
          value={text}
          onChange={setText}
          minRows={8}
          placeholder="Digite sua anotação aqui... O texto será salvo automaticamente."
        />
        <div className="form-group">
          <label>Instruções para análise da imagem (opcional):</label>
          <textarea
            rows="3"
            className="form-control instruction-textarea"
            value={extraPrompt}
            onChange={(e) => setExtraPrompt(e.target.value)}
            onClick={handleClickExtraPrompt}
            placeholder="Ex: Explique o contexto da imagem, destaque os pontos principais..."
          />
          <button onClick={handleAnalyze} className="button button-outline" disabled={loading || analiseEmAndamento} style={{marginTop: '0.5rem'}}>
            {analiseEmAndamento ? 'Analisando...' : (loading ? 'Iniciando...' : 'Analisar Imagem')}
          </button>
          {loadingSuggestions && <span className="hint-text">Carregando sugestões...</span>}
          {showSuggestions && suggestions.length > 0 && (
            <div className="suggestions-container">
              <p>Sugestões de prompts:</p>
              <ul>
                {suggestions.map((suggestion, idx) => (
                  <li key={idx}>
                    <button type="button" onClick={() => applySuggestion(suggestion)} className="suggestion-button">{suggestion}</button>
                  </li>
                ))}
              </ul>
              <button type="button" onClick={handleCloseSuggestions} className="suggestion-close-btn">Fechar sugestões</button>
            </div>
          )}
          {!showSuggestions && dismissedSuggestions && (
            <button type="button" onClick={handleReopenSuggestions} className="reopen-suggestions-btn">Mostrar sugestões de prompts</button>
          )}
        </div>
        <div className="action-buttons">
          <span className="hint-text" style={{fontSize: '0.8rem', marginLeft: '1rem'}}>
            {text.trim() ? 'Alterações salvas automaticamente' : ''}
          </span>
        </div>
      </div>
    </div>
  );
}

export default AnnotationEditor;
