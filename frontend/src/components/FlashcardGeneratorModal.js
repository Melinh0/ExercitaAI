import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getModels } from '../services/api';
import { useTasks } from '../contexts/TaskContext';
import { useConfirm } from '../contexts/ConfirmContext';
import { useAuth } from '../contexts/AuthContext';
import ModelInfoModal from './ModelInfoModal';
import usePromptSuggestions from './PromptSuggestions';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { formatarDuracao } from '../utils/tempo';

function FlashcardGeneratorModal({ topic, isOpen, onClose, onConcluido }) {
  const { startTask, isRunning, tasks } = useTasks();
  const { alert } = useConfirm();
  const { temChaveProvedor } = useAuth();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  const [phase, setPhase] = useState('input');
  const [subject, setSubject] = useState('');
  const [customInstructions, setCustomInstructions] = useState('');
  const [numFlashcards, setNumFlashcards] = useState(10);
  const [selectedModel, setSelectedModel] = useState('');
  const [models, setModels] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [showModelInfo, setShowModelInfo] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState('');
  const [segundos, setSegundos] = useState(0);

  const pollIntervalRef = useRef(null);
  const { onClick: handleSuggestionsClick, suggestionsElement } = usePromptSuggestions({
    mode: 'generate_flashcards',
    payload: { topic, model: selectedModel },
    onApply: setCustomInstructions,
    resetKey: isOpen,
  });

  const {
    onClick: handleSubjectSuggestionsClick,
    suggestionsElement: subjectSuggestionsElement,
  } = usePromptSuggestions({
    mode: 'flashcard_subjects',
    payload: { topic, context: subject, model: selectedModel },
    onApply: setSubject,
    resetKey: isOpen,
    label: 'Sugestões de assunto:',
    reopenLabel: 'Mostrar sugestões de assunto',
  });

  const loadModels = useCallback(async () => {
    try {
      const res = await getModels();
      const modelList = Array.isArray(res.data) ? res.data : [];
      setModels(modelList);
      if (modelList.length > 0 && !selectedModel) setSelectedModel(modelList[0]);
    } catch (err) {
      console.error(err);
    }
  }, [selectedModel]);

  useEffect(() => {
    if (isOpen) {
      loadModels();
    }
  }, [isOpen, loadModels]);

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
            message: task.error || 'Erro ao gerar flashcards.',
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
      (t) => t.name === 'generate_flashcards' && (t.status === 'pending' || t.status === 'running')
    );
    if (tarefa) startPolling(tarefa.id);
  }, [isOpen, phase, tasks, startPolling]);

  useEffect(() => {
    const s = subject.trim();
    if (!s) return;
    const lower = s.toLowerCase();
    let instrucao = '';
    if (lower.includes('matem') || lower.includes('cálculo') || lower.includes('algebra') || lower.includes('geometria')) {
      instrucao = 'Focar em fórmulas, teoremas, demonstrações passo a passo e exercícios de aplicação.';
    } else if (lower.includes('física') || lower.includes('fisica')) {
      instrucao = 'Focar em leis físicas, fórmulas, exercícios numéricos e exemplos de aplicação prática.';
    } else if (lower.includes('química') || lower.includes('quimica')) {
      instrucao = 'Focar em reações químicas, tabela periódica, estequiometria e conceitos fundamentais.';
    } else if (lower.includes('biologia') || lower.includes('biologia')) {
      instrucao = 'Focar em processos biológicos, classificação, anatomia e exemplos de seres vivos.';
    } else if (lower.includes('história') || lower.includes('historia')) {
      instrucao = 'Focar em períodos históricos, personagens importantes, datas e causas/consequências.';
    } else if (lower.includes('geografia') || lower.includes('geografia')) {
      instrucao = 'Focar em mapas, climas, relevo, população e fenômenos geográficos.';
    } else if (lower.includes('programação') || lower.includes('código') || lower.includes('python') || lower.includes('java')) {
      instrucao = 'Focar em sintese de código, algoritmos, estruturas de dados e exemplos práticos.';
    } else if (lower.includes('inglês') || lower.includes('ingles') || lower.includes('espanhol') || lower.includes('francês')) {
      instrucao = 'Focar em vocabulário, gramática, tradução e exemplos de uso em frases.';
    } else {
      instrucao = `Focar nos conceitos-chave de ${s}, definições essenciais, aplicações práticas e exemplos concretos.`;
    }
    setCustomInstructions(instrucao);
  }, [subject]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!temChaveProvedor) {
      await alert({
        title: 'Chave de API necessária',
        message: 'Cadastre uma chave de um provedor de LLM em Configurações antes de gerar flashcards ou adicione mais de um provedor.',
        variant: 'warning',
      });
      return;
    }
    if (!subject.trim()) {
      await alert({
        title: 'Campo obrigatório',
        message: 'Por favor, informe o assunto.',
        variant: 'warning',
      });
      return;
    }
    if (!topic) {
      await alert({
        title: 'Erro',
        message: 'Tópico não definido.',
        variant: 'danger',
      });
      return;
    }
    setSubmitting(true);
    try {
      const idIniciada = await startTask('generate_flashcards', {
        topic,
        subject: subject.trim(),
        custom_instructions: customInstructions,
        model: selectedModel,
        max_flashcards: numFlashcards,
      });
      startPolling(idIniciada);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar geração: ' + (err.message || err),
        variant: 'danger',
      });
      console.error(err);
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

  const isRunningTask = isRunning('generate_flashcards');

  return (
    <>
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content" style={{ maxWidth: '600px', maxHeight: '85vh', overflowY: 'auto' }}>
          <span className="close" onClick={handleClose}>&times;</span>

          {phase === 'input' && (
            <>
              <h2>Gerar Plano de Estudos com Flashcards</h2>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label>Assunto (obrigatório):</label>
                  <input
                    type="text"
                    className="form-control"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    onClick={handleSubjectSuggestionsClick}
                    placeholder="Ex.: Matemática Financeira, História do Brasil..."
                    required
                  />
                  {subjectSuggestionsElement}
                </div>
                <div className="form-group">
                  <label>Quantidade de flashcards:</label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={numFlashcards}
                    onChange={(e) => setNumFlashcards(parseInt(e.target.value))}
                    className="form-control"
                  />
                </div>
                <div className="form-group">
                  <label>Instruções de personalização (opcional):</label>
                  <textarea
                    rows="4"
                    value={customInstructions}
                    onChange={(e) => setCustomInstructions(e.target.value)}
                    onClick={handleSuggestionsClick}
                    placeholder="Ex.: focar nos conceitos mais importantes..."
                    className="form-control"
                  />
                  {suggestionsElement}
                </div>
                <div className="form-group">
                  <label>Modelo de IA:</label>
                  <div className="model-select-row">
                    <select
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      className="form-control"
                    >
                      {Array.isArray(models) && models.map((model) => {
                        const name = typeof model === 'string' ? model : (model.name || model);
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
                  Dica: quanto mais material o tópico tiver (imagens, textos de apoio, artigos), mais variadas e precisas ficam os flashcards.
                </p>

                <div className="form-actions">
                  <button type="submit" className="save-button" disabled={submitting || isRunningTask || !subject.trim() || !temChaveProvedor}>
                    {isRunningTask ? 'Geração em andamento...' : (submitting ? 'Iniciando...' : 'Gerar Flashcards')}
                  </button>
                </div>
              </form>
            </>
          )}

          {phase === 'processing' && (
            <>
              <h2>Gerando Flashcards</h2>
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

export default FlashcardGeneratorModal;