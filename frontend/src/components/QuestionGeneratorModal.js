import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getModels } from '../services/api';
import { useTasks } from '../contexts/TaskContext';
import { useConfirm } from '../contexts/ConfirmContext';
import { useAuth } from '../contexts/AuthContext';
import ModelInfoModal from './ModelInfoModal';
import usePromptSuggestions from './PromptSuggestions';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { formatarDuracao } from '../utils/tempo';

function QuestionGeneratorModal({ topic, isOpen, onClose, onConcluido }) {
  const { startTask, isRunning, tasks } = useTasks();
  const { alert } = useConfirm();
  const { temChaveProvedor } = useAuth();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  const [phase, setPhase] = useState('input');
  const [questionTypes, setQuestionTypes] = useState({
    objetiva: true,
    aberta: true,
    vf: true,
  });
  const [numQuestions, setNumQuestions] = useState(10);
  const [customInstructions, setCustomInstructions] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [models, setModels] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [showModelInfo, setShowModelInfo] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState('');
  const [segundos, setSegundos] = useState(0);

  const pollIntervalRef = useRef(null);
  const { onClick: handleSuggestionsClick, suggestionsElement } = usePromptSuggestions({
    mode: 'generate_questions',
    payload: { topic, model: selectedModel },
    onApply: setCustomInstructions,
    resetKey: isOpen,
  });

  const loadModels = useCallback(async () => {
    try {
      const res = await getModels();
      const list = Array.isArray(res.data) ? res.data : [];
      setModels(list);
      if (list.length > 0 && !selectedModel) setSelectedModel(list[0]);
    } catch (err) {
      console.error(err);
    }
  }, [selectedModel]);

  useEffect(() => {
    if (isOpen) {
      loadModels();
    }
  }, [isOpen, loadModels]);

  const handleTypeChange = (type) => {
    setQuestionTypes(prev => ({ ...prev, [type]: !prev[type] }));
  };

  const startPolling = useCallback((id) => {
    setTaskProgress(0);
    setTaskMessage('Iniciando...');
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
          setPhase('input');
          setTaskProgress(0);
          setTaskMessage('');
          setSegundos(0);
          onClose();
          if (onConcluido) onConcluido(task.result);
        } else if (task.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setPhase('input');
          setSegundos(0);
          await alert({
            title: 'Erro',
            message: task.error || 'Erro ao gerar questões.',
            variant: 'danger',
          });
        }
      } catch (err) {
        console.error('Erro ao consultar status da task:', err);
      }
    }, 1000);
  }, [alert, onClose, onConcluido]);

  useEffect(() => {
    if (!isOpen || phase !== 'input' || pollIntervalRef.current) return;
    const tarefa = Object.values(tasks).find(
      (t) => t.name === 'generate_questions' && (t.status === 'pending' || t.status === 'running')
    );
    if (tarefa) startPolling(tarefa.id);
  }, [isOpen, phase, tasks, startPolling]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!temChaveProvedor) {
      await alert({
        title: 'Chave de API necessária',
        message: 'Cadastre uma chave de um provedor de LLM em Configurações antes de gerar questões ou adicione mais de um provedor.',
        variant: 'warning',
      });
      return;
    }
    const typesList = Object.keys(questionTypes).filter(t => questionTypes[t]);
    if (typesList.length === 0) {
      await alert({
        title: 'Aviso',
        message: 'Selecione pelo menos um tipo de questão.',
        variant: 'warning',
      });
      return;
    }
    setSubmitting(true);
    try {
      const idIniciada = await startTask('generate_questions', {
        topic,
        question_types: typesList,
        num_questions: numQuestions,
        custom_instructions: customInstructions,
        model: selectedModel,
      });
      startPolling(idIniciada);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar geração: ' + (err.message || err),
        variant: 'danger',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    onClose();
    setPhase('input');
    setTaskProgress(0);
    setTaskMessage('');
    setSegundos(0);
  };

  useEffect(() => () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
  }, []);

  if (!isOpen) return null;

  const modelNames = Array.isArray(models)
    ? models.map(m => (typeof m === 'string' ? m : m.name))
    : [];

  const anyTypeSelected = Object.values(questionTypes).some(v => v);
  const isRunningTask = isRunning('generate_questions');

  return (
    <>
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content" style={{ maxWidth: '600px', maxHeight: '85vh', overflowY: 'auto' }}>
          <span className="close" onClick={handleClose}>&times;</span>

          {phase === 'input' && (
            <>
              <h2>Gerador de Questões Personalizadas</h2>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label>Tipos de questão:</label>
                  <div className="opcoes-linha">
                    <label className="opcao-check">
                      <input type="checkbox" checked={questionTypes.objetiva} onChange={() => handleTypeChange('objetiva')} />
                      Objetiva
                    </label>
                    <label className="opcao-check">
                      <input type="checkbox" checked={questionTypes.aberta} onChange={() => handleTypeChange('aberta')} />
                      Aberta
                    </label>
                    <label className="opcao-check">
                      <input type="checkbox" checked={questionTypes.vf} onChange={() => handleTypeChange('vf')} />
                      Verdadeiro/Falso
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <label>Quantidade de questões:</label>
                  <input type="number" min="1" max="30" value={numQuestions} onChange={(e) => setNumQuestions(parseInt(e.target.value))} className="form-control" />
                </div>
                <div className="form-group">
                  <label>Instruções de melhoria (opcional):</label>
                  <textarea
                    rows="3"
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    onClick={handleSuggestionsClick}
                    placeholder="Ex.: Aumentar dificuldade, focar em cálculo, etc."
                    className="form-control"
                  />
                  {suggestionsElement}
                </div>
                <div className="form-group">
                  <label>Modelo de IA:</label>
                  <div className="model-select-row">
                    <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} className="form-control">
                      {Array.isArray(models) && models.map(m => {
                        const name = typeof m === 'string' ? m : m.name;
                        return <option key={name} value={name}>{name}</option>;
                      })}
                    </select>
                    <button
                      type="button"
                      className="model-info-btn"
                      onClick={() => setShowModelInfo(true)}
                      title="Saber mais sobre os modelos"
                    >
                      ?
                    </button>
                  </div>
                </div>
                <p className="hint-text" style={{ margin: '0 0 0.8rem' }}>
                  Dica: quanto mais material o tópico tiver (imagens, textos de apoio, artigos), mais variadas e precisas ficam as questões.
                </p>
                <div className="form-actions">
                  <button type="submit" className="save-button" disabled={submitting || isRunningTask || !anyTypeSelected || !temChaveProvedor}>
                    {isRunningTask ? 'Geração em andamento...' : (submitting ? 'Iniciando...' : 'Gerar Questões')}
                  </button>
                </div>
              </form>
            </>
          )}

          {phase === 'processing' && (
            <>
              <h2>Gerando Questões</h2>
              <div className="rag-progress-bar">
                <div className="rag-progress-track">
                  <div className="rag-progress-fill" style={{ width: `${taskProgress}%` }}></div>
                </div>
                <span className="rag-progress-text">{taskProgress}%</span>
              </div>
              <p className="hint-text">
                {taskMessage || 'Processando...'}
                {segundos > 0 ? ` (${formatarDuracao(segundos)})` : ''}
              </p>
            </>
          )}
        </div>
      </div>

      <ModelInfoModal
        isOpen={showModelInfo}
        onClose={() => setShowModelInfo(false)}
        selectedModel={selectedModel}
        availableModels={modelNames}
      />
    </>
  );
}

export default QuestionGeneratorModal;