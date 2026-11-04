import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTasks } from '../contexts/TaskContext';
import { useConfirm } from '../contexts/ConfirmContext';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { saveStudyStrategyHistory } from '../services/api';
import MarkdownRenderer from './MarkdownContent';
import SugestoesContexto from './SugestoesContexto';
import usePromptSuggestions from './PromptSuggestions';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

function StudyStrategyModal({ topicName, isOpen, onClose, onDescartar, onSaved, onOpenArticles, externalStrategy, onAdicionarTextos }) {
  const { startTask, isRunning, tasks } = useTasks();
  const { alert } = useConfirm();
  const { hasOllamaKey } = useAuth();
  const { darkMode } = useTheme();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  const [phase, setPhase] = useState('input');
  const [strategy, setStrategy] = useState(null);
  const [timeValue, setTimeValue] = useState(2);
  const [timeUnit, setTimeUnit] = useState('hours');
  const [daysPerWeek, setDaysPerWeek] = useState(5);
  const [targetDate, setTargetDate] = useState('');
  const [customInstructions, setCustomInstructions] = useState('');
  const [showForm, setShowForm] = useState(true);
  const [showTechniquesTable, setShowTechniquesTable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState('');
  const [saved, setSaved] = useState(false);

  const pollIntervalRef = useRef(null);
  const { onClick: handleSuggestionsClick, suggestionsElement } = usePromptSuggestions({
    mode: 'study_strategy',
    payload: { topic: topicName },
    onApply: setCustomInstructions,
    resetKey: isOpen,
  });

  const techniques = [
    { name: 'Método SQ3R', description: 'Survey, Question, Read, Recite, Review.', reference: 'Robinson, F. P. (1941). Effective Study. Harper & Brothers.', link: 'https://scholar.google.com/scholar?q=SQ3R+Robinson+1941' },
    { name: 'Método PQ4R', description: 'Preview, Question, Read, Reflect, Recite, Review.', reference: 'Thomas, E. L., & Robinson, H. A. (1972). Improving Reading in Every Class.', link: 'https://eric.ed.gov/?id=ED075769' },
    { name: 'Recuperação Ativa', description: 'Prática de tentar recordar a informação sem consulta.', reference: 'Roediger & Karpicke (2006). Psychological Science, 17(3), 249-255.', link: 'https://doi.org/10.1111/j.1467-9280.2006.01693.x' },
    { name: 'Técnica de Feynman', description: 'Aprender ensinando.', reference: 'Chi et al. (1989). Cognitive Science, 13(2), 145-182; base da autoexplicação.', link: 'https://doi.org/10.1016/0364-0213(89)90002-5' },
    { name: 'Efeito Protégé', description: 'A expectativa de ensinar melhora a retenção.', reference: 'Koh, Lee & Lim (2018). Journal of Educational Psychology, 110(5), 625–637.', link: 'https://doi.org/10.1037/edu0000229' },
    { name: 'Repetição Espaçada', description: 'Revisões em intervalos progressivamente maiores.', reference: 'Cepeda et al. (2006). Psychological Bulletin, 132(3), 354–380.', link: 'https://doi.org/10.1037/0033-2909.132.3.354' },
    { name: 'Sistema Leitner', description: 'Flashcards com caixas para revisão espaçada.', reference: 'Leitner, S. (1972). So lernt man lernen.', link: 'https://scholar.google.com/scholar?q=Leitner+system+spaced+repetition' },
    { name: 'Método 24-7-30', description: 'Revisões em 24h, 7 dias e 30 dias.', reference: 'Kang, S. H. K. (2016). Policy Insights from the Behavioral and Brain Sciences, 3(1), 12–19.', link: 'https://doi.org/10.1177/2372732215624708' },
    { name: 'Intercalação', description: 'Misturar diferentes tópicos durante a sessão.', reference: 'Rohrer, D. (2012). Journal of Educational Psychology, 104(3), 728–741.', link: 'https://doi.org/10.1037/a0026199' },
    { name: 'Ciclo de Autorregulação', description: 'Modelo cíclico de três fases.', reference: 'Zimmerman, B. J. (2000). Handbook of self-regulation, 13-39.', link: 'https://doi.org/10.1016/B978-012109890-2/50031-7' }
  ];

  const startPolling = useCallback((id) => {
    setTaskProgress(0);
    setTaskMessage('Iniciando...');
    setPhase('processing');
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/tasks/${id}`, { credentials: 'same-origin' });
        if (!res.ok) return;
        const task = await res.json();
        setTaskProgress(task.progress || 0);
        setTaskMessage(task.message || '');
        if (task.status === 'completed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setStrategy(task.result);
          setPhase('result');
          setShowForm(false);
        } else if (task.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setPhase('input');
          setShowForm(true);
          await alert({
            title: 'Erro',
            message: task.error || 'Erro ao gerar estratégia.',
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
      (t) => t.name === 'study_strategy' && (t.status === 'pending' || t.status === 'running')
    );
    if (tarefa) startPolling(tarefa.id);
  }, [isOpen, phase, tasks, startPolling]);

  const handleGenerate = async () => {
    if (!hasOllamaKey) {
      await alert({
        title: 'Chave de API necessária',
        message: 'Cadastre uma chave do Ollama ou de outro provedor em Configurações antes de gerar a estratégia de estudo.',
        variant: 'warning',
      });
      return;
    }
    setLoading(true);
    try {
      let hoursPerDay = timeValue;
      if (timeUnit === 'minutes') {
        hoursPerDay = timeValue / 60;
      }
      const idIniciada = await startTask('study_strategy', {
        topic: topicName,
        dedication: {
          hours_per_day: hoursPerDay,
          days_per_week: daysPerWeek,
          target_date: targetDate || undefined,
          custom_instructions: customInstructions,
        },
      });
      setLoading(false);
      startPolling(idIniciada);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar geração: ' + (err.message || err),
        variant: 'danger',
      });
      setLoading(false);
    }
  };

  const handleBack = () => {
    setStrategy(null);
    setPhase('input');
    setShowForm(true);
  };

  const handleSaveHistory = async () => {
    if (!strategy) return;
    try {
      await saveStudyStrategyHistory(topicName, strategy);
      await alert({
        title: 'Sucesso',
        message: 'Estratégia salva no histórico. Você pode vê-la e restaurá-la em Histórico.',
        variant: 'success',
      });
      if (onSaved) onSaved();
      setSaved(true);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao salvar a estratégia no histórico.',
        variant: 'danger',
      });
      console.error(err);
    }
  };

  const handleSearchArticles = () => {
    if (onOpenArticles) {
      const query = customInstructions || topicName || 'estratégias de estudo';
      onOpenArticles(query, customInstructions);
    }
    onClose();
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
      setStrategy(null);
      setTaskProgress(0);
      setTaskMessage('');
      setShowForm(true);
      setSaved(false);
    }
  };

  useEffect(() => () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
  }, []);

  useEffect(() => {
    if (externalStrategy) {
      setStrategy(externalStrategy);
      setPhase('result');
      setShowForm(false);
    }
  }, [externalStrategy]);

  if (!isOpen) return null;

  const isRunningTask = isRunning('study_strategy');
  const isGenerating = loading && phase === 'input';

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '950px', maxHeight: '85vh', overflowY: 'auto' }}>
        <span className="close" onClick={handleClose}>&times;</span>
        <h2>Técnicas de estudo cientificamente validadas</h2>

        <button
          onClick={() => setShowTechniquesTable(!showTechniquesTable)}
          className="button"
          style={{ marginBottom: '1rem' }}
        >
          {showTechniquesTable ? 'Ocultar tabela de técnicas' : 'Ver tabela de técnicas'}
        </button>

        {showTechniquesTable && (
          <div className="study-strategy-references" style={{ marginBottom: '1.5rem', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ background: '#1e3a8a', color: 'white' }}>
                  <th style={{ padding: '0.75rem', textAlign: 'left', border: '1px solid #ddd' }}>Técnica</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', border: '1px solid #ddd' }}>Descrição</th>
                  <th style={{ padding: '0.75rem', textAlign: 'left', border: '1px solid #ddd' }}>Referência</th>
                </tr>
              </thead>
              <tbody>
                {techniques.map((t, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '0.5rem', verticalAlign: 'top', fontWeight: '600' }}>{t.name}</td>
                    <td style={{ padding: '0.5rem', verticalAlign: 'top' }}>{t.description}</td>
                    <td style={{ padding: '0.5rem', verticalAlign: 'top' }}>
                      {t.link ? (
                        <a href={t.link} target="_blank" rel="noopener noreferrer" className="reference-link">
                          {t.reference}
                        </a>
                      ) : (
                        <span>{t.reference}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h3>Gerar recomendação personalizada</h3>

        {phase === 'input' && showForm && !isGenerating && (
          <form onSubmit={(e) => { e.preventDefault(); handleGenerate(); }}>
            <div className="form-group">
              <label>Tempo por dia de estudo:</label>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <input
                  type="number"
                  min="0.5"
                  step="0.5"
                  value={timeValue}
                  onChange={(e) => setTimeValue(parseFloat(e.target.value))}
                  className="form-control"
                  style={{ width: '120px' }}
                  required
                />
                <select
                  value={timeUnit}
                  onChange={(e) => setTimeUnit(e.target.value)}
                  className="form-control"
                  style={{ width: '120px' }}
                >
                  <option value="hours">Horas</option>
                  <option value="minutes">Minutos</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Dias por semana:</label>
              <input
                type="number"
                min="1"
                max="7"
                value={daysPerWeek}
                onChange={(e) => setDaysPerWeek(parseInt(e.target.value))}
                className="form-control"
                required
              />
            </div>
            <div className="form-group">
              <label>Data alvo (opcional):</label>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="form-control"
                style={{ colorScheme: darkMode ? 'dark' : 'light' }}
              />
            </div>
            <div className="form-group">
              <label>Instruções adicionais (opcional):</label>
              <textarea
                rows="4"
                className="form-control"
                value={customInstructions}
                onChange={(e) => setCustomInstructions(e.target.value)}
                onClick={handleSuggestionsClick}
                placeholder="Ex.: Foque em exercícios práticos, inclua revisões semanais..."
              />
              {suggestionsElement}
            </div>
            <p className="hint-text" style={{ margin: '0 0 0.8rem' }}>
              Dica: quanto mais material o tópico tiver (imagens, textos de apoio, artigos), mais personalizada e fundamentada fica a estratégia.
            </p>
            <div className="form-actions">
              <button type="submit" className="save-button" disabled={loading || isRunningTask || !hasOllamaKey}>
                {isRunningTask ? 'Geração em andamento...' : (loading ? 'Iniciando...' : 'Gerar estratégia')}
              </button>
            </div>
          </form>
        )}

        {phase === 'processing' && (
          <>
            <h2>Gerando Estratégia de Estudo</h2>
            <div className="rag-progress-bar">
              <div className="rag-progress-track">
                <div className="rag-progress-fill" style={{ width: `${taskProgress}%` }}></div>
              </div>
              <span className="rag-progress-text">{taskProgress}%</span>
            </div>
            <p className="hint-text">{taskMessage || 'Analisando material e preparando estratégia...'}</p>
          </>
        )}

        {phase === 'result' && strategy && (
          <div>
            {strategy.contexto && strategy.contexto.insuficiente && (
              <div className="contexto-aviso">
                <p>
                  Pouco material sobre o assunto foi encontrado neste tópico, então a estratégia pode ficar genérica.
                  Adicione mais imagens, textos de apoio ou pesquise artigos; abaixo ficam sugestões do que pesquisar para fundamentar o plano.
                </p>
                {(onAdicionarTextos || onOpenArticles) && (
                  <div className="contexto-aviso-acoes">
                    {onAdicionarTextos && (
                      <button type="button" className="button button-secundario" onClick={onAdicionarTextos}>
                        Adicionar material de apoio
                      </button>
                    )}
                    {onOpenArticles && (
                      <button type="button" className="button button-secundario" onClick={handleSearchArticles}>
                        Pesquisar artigos
                      </button>
                    )}
                  </div>
                )}
                <SugestoesContexto ativo topico={topicName} instrucoes={customInstructions} />
              </div>
            )}
            <h3 style={{ color: '#1e3a8a' }}>Técnica recomendada: {strategy.technique}</h3>
            {strategy.research_recommendation && (
              <div className="strategy-research-recommendation">
                <strong>Recomendação de pesquisa:</strong>
                <div style={{ marginTop: '0.75rem' }}>
                  {typeof strategy.research_recommendation === 'object' && strategy.research_recommendation.google_search_terms && (
                    <div>
                      <p><strong>Termos sugeridos para busca:</strong></p>
                      <ul>
                        {strategy.research_recommendation.google_search_terms.map((term, idx) => (
                          <li key={idx}>
                            <a
                              href={`https://www.google.com/search?q=${encodeURIComponent(term)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {term}
                            </a>
                          </li>
                        ))}
                      </ul>
                      <p><strong>Dica:</strong> {strategy.research_recommendation.platform_guidance || ''}</p>
                      <p><strong>Indexação:</strong> {strategy.research_recommendation.upload_suggestion || 'Adicione documentos ao tópico para enriquecer as respostas.'}</p>
                      <button onClick={handleSearchArticles} className="button button-outline" style={{ marginTop: '0.5rem' }}>
                        Pesquisar artigos
                      </button>
                    </div>
                  )}
                  {typeof strategy.research_recommendation === 'string' && (
                    <MarkdownRenderer content={strategy.research_recommendation} />
                  )}
                </div>
              </div>
            )}
            <div className="markdown-content">
              <h4>Plano personalizado</h4>
              <MarkdownRenderer content={strategy.plan} />
              <h4>Justificativa</h4>
              <MarkdownRenderer content={strategy.rationale} />
              <h4>Cronograma sugerido</h4>
              <MarkdownRenderer content={strategy.schedule} />
            </div>

            <div className="study-strategy-references" style={{ marginTop: '2rem' }}>
              <h4 style={{ marginTop: 0 }}>Fundamentação científica</h4>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {strategy.references && Array.isArray(strategy.references) && strategy.references.length > 0 ? (
                  strategy.references.map((ref, idx) => {
                    let link = ref.doi_or_link || '';
                    if (link && !link.startsWith('http://') && !link.startsWith('https://')) {
                      link = `https://doi.org/${link}`;
                    }
                    if (link && (link.includes('amazon') || link.includes('google') || link === '#')) {
                      link = null;
                    }
                    return (
                      <li key={idx} style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #ddd' }}>
                        <strong>{ref.title || 'Título não disponível'}</strong><br />
                        <span style={{ color: '#333' }}>{ref.authors || 'Autor não informado'}</span><br />
                        <span style={{ color: '#555', fontStyle: 'italic' }}>{ref.source || 'Fonte não informada'}</span><br />
                        {link ? (
                          <a href={link} target="_blank" rel="noopener noreferrer" className="reference-link">
                            Acessar referência
                          </a>
                        ) : (
                          <span style={{ color: '#999', fontStyle: 'italic' }}>Link não disponível</span>
                        )}
                      </li>
                    );
                  })
                ) : (
                  <li>Nenhuma referência disponível.</li>
                )}
              </ul>
            </div>

            <div className="form-actions" style={{ marginTop: '1.5rem' }}>
              <button onClick={handleSaveHistory} className="button button-outline" disabled={saved}>
                {saved ? 'Salva' : 'Salvar no histórico'}
              </button>
              <button onClick={handleBack} className="button button-outline">Voltar e ajustar</button>
              <button onClick={onDescartar || handleClose} className="button button-secundario">Descartar</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default StudyStrategyModal;