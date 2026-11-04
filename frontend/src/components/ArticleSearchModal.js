import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTasks } from '../contexts/TaskContext';
import { useConfirm } from '../contexts/ConfirmContext';
import { useAuth } from '../contexts/AuthContext';
import usePromptSuggestions from './PromptSuggestions';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { formatarDuracao } from '../utils/tempo';

function ArticleSearchModal({ isOpen, onClose, onDescartar, initialQuery = '', externalResults = null, topicName = '', instrucoes = '' }) {
  const { startTask, isRunning, tasks } = useTasks();
  const { alert } = useConfirm();
  const { hasOllamaKey } = useAuth();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  const [phase, setPhase] = useState('input');
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState([]);
  const [refinedQuery, setRefinedQuery] = useState('');
  const [pesquisou, setPesquisou] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState('');
  const [segundos, setSegundos] = useState(0);
  const lastExternalRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const { onClick: handleSuggestionsClick, suggestionsElement } = usePromptSuggestions({
    mode: 'search_articles',
    payload: { context: query, topic: topicName, instrucoes },
    onApply: setQuery,
    resetKey: isOpen,
    label: 'Sugestões do que pesquisar:',
    reopenLabel: 'Mostrar sugestões do que pesquisar',
  });

  const sugestoesRef = useRef(null);
  sugestoesRef.current = handleSuggestionsClick;

  useEffect(() => {
    if (!isOpen) return undefined;
    const timer = setTimeout(() => {
      if (sugestoesRef.current) sugestoesRef.current();
    }, 400);
    return () => clearTimeout(timer);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && initialQuery) {
      setQuery(initialQuery);
    }
  }, [isOpen, initialQuery]);

  useEffect(() => {
    if (externalResults && externalResults !== lastExternalRef.current) {
      lastExternalRef.current = externalResults;
      setResults(Array.isArray(externalResults.results) ? externalResults.results : []);
      setRefinedQuery(externalResults.refined_query || '');
      setPesquisou(true);
      setPhase('result');
    }
  }, [externalResults]);

  const startPolling = useCallback((id) => {
    setTaskProgress(0);
    setTaskMessage('Consultando bases de dados...');
    setPhase('processing');
    const t0 = Date.now();
    setSegundos(0);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/tasks/${id}`, { credentials: 'same-origin' });
        if (!res.ok) return;
        const task = await res.json();
        setTaskProgress(task.progress || 0);
        setTaskMessage(task.message || '');
        setSegundos(Math.floor((Date.now() - t0) / 1000));
        if (task.status === 'completed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setSegundos(0);
          setResults(Array.isArray(task.result?.results) ? task.result.results : []);
          setRefinedQuery(task.result?.refined_query || '');
          setPesquisou(true);
          setPhase('result');
        } else if (task.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setPhase('input');
          setSegundos(0);
          await alert({
            title: 'Erro',
            message: task.error || 'Erro ao pesquisar artigos.',
            variant: 'danger',
          });
        }
      } catch (err) {
        console.error('Erro ao consultar status da task:', err);
      }
    }, 1000);
  }, [alert]);

  useEffect(() => {
    if (!isOpen || phase !== 'input' || pollIntervalRef.current) return;
    const tarefa = Object.values(tasks).find(
      (t) => t.name === 'search_articles' && (t.status === 'pending' || t.status === 'running')
    );
    if (tarefa) startPolling(tarefa.id);
  }, [isOpen, phase, tasks, startPolling]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    if (!hasOllamaKey) {
      await alert({
        title: 'Chave de API necessária',
        message: 'Cadastre uma chave do Ollama ou de outro provedor em Configurações antes de pesquisar artigos.',
        variant: 'warning',
      });
      return;
    }
    try {
      const idIniciada = await startTask('search_articles', { query: query.trim() });
      startPolling(idIniciada);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar busca: ' + (err.message || err),
        variant: 'danger',
      });
      console.error(err);
    }
  };

  const handleNewSearch = () => {
    setPhase('input');
    setResults([]);
    setRefinedQuery('');
    setPesquisou(false);
    setTaskProgress(0);
    setTaskMessage('');
    setSegundos(0);
    lastExternalRef.current = null;
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const handleClose = () => {
    if (phase === 'processing') {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }
    onClose();
    if (phase !== 'input') {
      setPhase('input');
      setResults([]);
      setRefinedQuery('');
      setPesquisou(false);
      setTaskProgress(0);
      setTaskMessage('');
      setSegundos(0);
      lastExternalRef.current = null;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }
  };

  useEffect(() => () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
  }, []);

  if (!isOpen) return null;

  const isRunningTask = isRunning('search_articles');
  const isSearching = phase === 'processing' || (phase === 'result' && !pesquisou);

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '850px', maxHeight: '85vh', overflowY: 'auto' }}>
        <span className="close" onClick={handleClose}>&times;</span>
        <h2>Pesquisar artigos científicos</h2>
        <p className="modal-subtitle">
          Digite um tópico, técnica de estudo, nome de autor ou palavra-chave.
        </p>

        {phase === 'input' && (
          <>
            <div className="form-group" style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type="text"
                className="form-control"
                placeholder="Ex.: Inteligência Artificial, Técnicas de Estudo..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onClick={handleSuggestionsClick}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                disabled={isRunningTask}
              />
              <button
                className="save-button"
                onClick={handleSearch}
                disabled={isRunningTask || !query.trim() || !hasOllamaKey}
                style={{ minWidth: '140px' }}
              >
                {isRunningTask ? 'Pesquisa em andamento...' : 'Pesquisar'}
              </button>
            </div>
            {suggestionsElement}
            <p className="hint-text" style={{ marginTop: '0.5rem' }}>
              Dica: use termos em inglês para melhores resultados. Artigos adicionados ao tópico alimentam a geração de questões e flashcards.
            </p>
          </>
        )}

        {phase === 'processing' && (
          <>
            <h2>Pesquisando Artigos</h2>
            <div className="rag-progress-bar">
              <div className="rag-progress-track">
                <div className="rag-progress-fill" style={{ width: `${taskProgress}%` }}></div>
              </div>
              <span className="rag-progress-text">{taskProgress}%</span>
            </div>
            <p className="hint-text">
              {taskMessage || 'Consultando CrossRef, arXiv, PubMed e Semantic Scholar...'}
              {segundos > 0 ? ` (${formatarDuracao(segundos)})` : ''}
            </p>
          </>
        )}

        {phase === 'result' && (
          <>
            {!pesquisou && results.length === 0 && (
              <p className="search-articles-empty">
                Nenhum artigo encontrado para esta busca. Tente termos mais específicos, sinônimos ou o assunto em inglês.
              </p>
            )}
            {refinedQuery && (
              <p className="search-articles-refined">
                <strong>Consulta refinada:</strong> {refinedQuery}
              </p>
            )}
            {results.length > 0 && (
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {results.map((item, idx) => (
                  <li key={idx} className="article-item" style={{
                    marginBottom: '1.5rem',
                    paddingBottom: '1rem',
                    borderBottom: '1px solid #e2e8f0'
                  }}>
                    <h4 style={{ margin: '0 0 0.25rem 0' }}>{item.title}</h4>
                    <p style={{ margin: '0.25rem 0' }}>
                      <strong>Autores:</strong> {item.authors}
                    </p>
                    <p style={{ margin: '0.25rem 0' }}>
                      <strong>Fonte:</strong> {item.source}
                    </p>
                    {item.link ? (
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="button"
                        style={{ display: 'inline-block', marginTop: '0.5rem' }}
                      >
                        Acessar artigo
                      </a>
                    ) : (
                      <span className="hint-text">Link não disponível</span>
                    )}
                    {item.doi && (
                      <p className="article-doi" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                        DOI: {item.doi}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <div className="form-actions">
              {results.length > 0 && !isSearching && (
                <button className="button" onClick={handleNewSearch}>
                  Nova pesquisa
                </button>
              )}
              <button className="button button-secundario" onClick={onDescartar || handleClose}>
                Descartar
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default ArticleSearchModal;