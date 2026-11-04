import React, { useState, useEffect } from 'react';
import { getSessions, deleteSession, getStudyStrategyHistory, restoreStudyStrategy, deleteStudyStrategyHistory } from '../services/api';
import { useConfirm } from '../contexts/ConfirmContext';
import GeneratedQuestionsView from './GeneratedQuestionsView';
import FlashcardsViewer from './FlashcardsViewer';
import MarkdownRenderer from './MarkdownContent';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { IconeSetaEsquerda, IconeSetaDireita } from './Icons';

function SessionsViewer({ topicName, isOpen, onClose, onInsertQuestion, onInsertAll, onEstrategiaRestaurada, questoesDoTopico = [] }) {
  const { confirm, alert } = useConfirm();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [currentPageStrategies, setCurrentPageStrategies] = useState(0);
  const [currentPageQuestions, setCurrentPageQuestions] = useState(0);
  const [currentPageFlashcards, setCurrentPageFlashcards] = useState(0);
  const [editingSession, setEditingSession] = useState(null);
  const [editingIndex, setEditingIndex] = useState(null);
  const [editingFlashcardsSession, setEditingFlashcardsSession] = useState(null);
  const [editingFlashcardsIndex, setEditingFlashcardsIndex] = useState(null);
  const [estrategias, setEstrategias] = useState([]);
  const [loadingEstrategias, setLoadingEstrategias] = useState(false);
  const [estrategiaAberta, setEstrategiaAberta] = useState(null);
  const [gabaritosAbertos, setGabaritosAbertos] = useState({});

  const loadSessions = () => {
    setLoading(true);
    getSessions(topicName)
      .then(res => setSessions(Array.isArray(res.data) ? res.data : []))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  };

  const loadEstrategias = () => {
    setLoadingEstrategias(true);
    getStudyStrategyHistory(topicName)
      .then(res => setEstrategias(Array.isArray(res.data && res.data.historico) ? res.data.historico : []))
      .catch(err => console.error(err))
      .finally(() => setLoadingEstrategias(false));
  };

  const questionsSessions = sessions.filter(s => s.kind !== 'flashcards');
  const flashcardsSessions = sessions.filter(s => s.kind === 'flashcards');

  useEffect(() => {
    if (isOpen) {
      loadSessions();
      loadEstrategias();
      setEstrategiaAberta(null);
      setGabaritosAbertos({});
      setCurrentPage(0);
      setCurrentPageStrategies(0);
      setCurrentPageQuestions(0);
      setCurrentPageFlashcards(0);
    }
  }, [isOpen, topicName]);

  useEffect(() => {
    setCurrentPage(prev => Math.min(prev, Math.max(sessions.length - 1, 0)));
  }, [sessions]);

  const handlePrev = () => {
    if (currentPage > 0) setCurrentPage(currentPage - 1);
  };

  const handleNext = () => {
    if (currentPage < sessions.length - 1) setCurrentPage(currentPage + 1);
  };

  const handlePrevStrategies = () => {
    if (currentPageStrategies > 0) setCurrentPageStrategies(currentPageStrategies - 1);
  };

  const handleNextStrategies = () => {
    if (currentPageStrategies < estrategias.length - 1) setCurrentPageStrategies(currentPageStrategies + 1);
  };

  const handlePrevQuestions = () => {
    if (currentPageQuestions > 0) setCurrentPageQuestions(currentPageQuestions - 1);
  };

  const handleNextQuestions = () => {
    if (currentPageQuestions < questionsSessions.length - 1) setCurrentPageQuestions(currentPageQuestions + 1);
  };

  const handlePrevFlashcards = () => {
    if (currentPageFlashcards > 0) setCurrentPageFlashcards(currentPageFlashcards - 1);
  };

  const handleNextFlashcards = () => {
    if (currentPageFlashcards < flashcardsSessions.length - 1) setCurrentPageFlashcards(currentPageFlashcards + 1);
  };

  const handleEdit = (session, idx) => {
    if (session.kind === 'flashcards') {
      setEditingFlashcardsSession({ ...session });
      setEditingFlashcardsIndex(idx);
    } else {
      setEditingSession({ ...session });
      setEditingIndex(idx);
    }
  };

  const handleDelete = async (sessionIdx) => {
    const confirmed = await confirm({
      title: 'Excluir sessão',
      message: 'Tem certeza que deseja excluir esta sessão? Essa ação não pode ser desfeita.',
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await deleteSession(topicName, sessionIdx);
      await alert({
        title: 'Sucesso',
        message: 'Sessão excluída com sucesso!',
        variant: 'success',
      });
      loadSessions();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao excluir sessão.',
        variant: 'danger',
      });
      console.error(err);
    }
  };

  const handleRestaurar = async (idx) => {
    const confirmed = await confirm({
      title: 'Restaurar estratégia',
      message: 'Restaurar esta versão como a estratégia atual do tópico? A versão atual será substituída.',
      confirmText: 'Restaurar',
      cancelText: 'Cancelar',
    });
    if (!confirmed) return;
    try {
      const res = await restoreStudyStrategy(topicName, idx);
      if (onEstrategiaRestaurada) onEstrategiaRestaurada(res.data);
      await alert({
        title: 'Sucesso',
        message: 'Estratégia restaurada. Ela será exibida ao abrir a estratégia de estudo do tópico.',
        variant: 'success',
      });
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao restaurar a estratégia.',
        variant: 'danger',
      });
      console.error(err);
    }
  };

  const handleExcluirEstrategia = async (idx) => {
    const confirmed = await confirm({
      title: 'Excluir estratégia do histórico',
      message: 'Tem certeza que deseja excluir esta estratégia do histórico? A versão atual do tópico não será afetada.',
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await deleteStudyStrategyHistory(topicName, idx);
      setEstrategiaAberta(null);
      loadEstrategias();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao excluir a estratégia do histórico.',
        variant: 'danger',
      });
      console.error(err);
    }
  };

  const handlePrint = (session) => {
    const printWindow = window.open('', '_blank');
    const contentHtml = session.kind === 'flashcards'
      ? (Array.isArray(session.flashcards) ? session.flashcards.map((card, idx) => `
            <div class="question">
              <h3>Flashcard ${idx + 1}: ${card.title || 'Sem título'}</h3>
              <p><strong>Objetivo:</strong> ${card.objective || ''}</p>
              <p><strong>Explicação:</strong> ${card.explanation || ''}</p>
              <p><strong>Exemplo:</strong> ${card.example || ''}</p>
              <p><strong>Exercício:</strong> ${card.exercise || ''}</p>
              <p><strong>Resposta:</strong> ${card.answer || ''}</p>
            </div>
          `).join('') : '')
      : (Array.isArray(session.questions) ? session.questions.map((q, idx) => `
            <div class="question">
              <h3>Questão ${idx+1} (${q.type === 'objetiva' ? 'Objetiva' : q.type === 'aberta' ? 'Discursiva' : 'V/F'})</h3>
              <p>${q.text.replace(/\n/g, '<br/>')}</p>
              <div class="answer"><strong>Sua resposta:</strong> ${q.user_answer || '(não respondida)'}</div>
              <div><strong>Explicação:</strong><p>${(q.explanation || '').replace(/\n/g, '<br/>')}</p></div>
            </div>
          `).join('') : '');
    printWindow.document.write(`
      <html>
        <head>
          <title>Sessão de Questões - ${new Date(session.timestamp).toLocaleString()}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 2rem; }
            .question { margin-bottom: 2rem; border-bottom: 1px solid #ccc; padding-bottom: 1rem; }
            .question h3 { color: #1e3a8a; }
            .answer { margin-top: 1rem; background: #f5f5f5; padding: 0.5rem; border-radius: 5px; }
          </style>
        </head>
        <body>
          <h1>Sessão de Questões - ${new Date(session.timestamp).toLocaleString()}</h1>
          ${contentHtml}
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
  };

  if (!isOpen) return null;

  const semHistorico = (!Array.isArray(sessions) || sessions.length === 0) && estrategias.length === 0;

  if (semHistorico) {
    return (
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content empty-session-modal">
          <span className="close" onClick={onClose}>&times;</span>
          <h2>Nenhum histórico encontrado</h2>
          <p className="empty-download-message">Não há sessões nem estratégias de estudo salvas para este tópico.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '80vh', overflowY: 'auto' }}>
          <span className="close" onClick={onClose}>&times;</span>
          <h2>Histórico</h2>
          {loading && (
            <span className="carregando-linha">
              <span className="carregando-girar" aria-hidden="true" />
              Carregando sessões...
            </span>
          )}
          {loadingEstrategias && (
            <span className="carregando-linha">
              <span className="carregando-girar" aria-hidden="true" />
              Carregando estratégias...
            </span>
          )}
          {!loading && !loadingEstrategias && sessions.length === 0 && estrategias.length === 0 && (
            <p>Nenhum histórico encontrado.</p>
          )}
          {estrategias.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <h3>Estratégias de estudo</h3>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <button onClick={handlePrevStrategies} className="nav-btn" disabled={currentPageStrategies === 0}><IconeSetaEsquerda size={14} /></button>
                <span>{currentPageStrategies + 1} / {estrategias.length}</span>
                <button onClick={handleNextStrategies} className="nav-btn" disabled={currentPageStrategies === estrategias.length - 1}><IconeSetaDireita size={14} /></button>
              </div>
              {(() => {
                const entrada = estrategias[currentPageStrategies];
                const idx = currentPageStrategies;
                return (
                  <div className="resolucao-block" style={{ marginTop: '0.75rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <strong>Estratégia salva em {new Date(entrada.salvo_em).toLocaleString('pt-BR')}</strong>
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <button className="button button-outline" onClick={() => setEstrategiaAberta(estrategiaAberta === idx ? null : idx)}>
                          {estrategiaAberta === idx ? 'Ocultar estratégia' : 'Ver estratégia'}
                        </button>
                        <button className="button button-sucesso" onClick={() => handleRestaurar(idx)}>
                          Restaurar
                        </button>
                        <button className="delete-button-session" onClick={() => handleExcluirEstrategia(idx)}>
                          Excluir
                        </button>
                      </div>
                    </div>
                    {estrategiaAberta === idx && entrada.estrategia && (
                      <div className="markdown-content" style={{ marginTop: '1rem' }}>
                        <p><strong>Técnica:</strong> {entrada.estrategia.technique || 'não informada'}</p>
                        {entrada.estrategia.plan && (
                          <>
                            <h4>Plano personalizado</h4>
                            <MarkdownRenderer content={entrada.estrategia.plan} />
                          </>
                        )}
                        {entrada.estrategia.rationale && (
                          <>
                            <h4>Justificativa</h4>
                            <MarkdownRenderer content={entrada.estrategia.rationale} />
                          </>
                        )}
                        {entrada.estrategia.schedule && (
                          <>
                            <h4>Cronograma sugerido</h4>
                            <MarkdownRenderer content={entrada.estrategia.schedule} />
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}
          {questionsSessions.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <h3>Sessões de questões</h3>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <button onClick={handlePrevQuestions} className="nav-btn" disabled={currentPageQuestions === 0}><IconeSetaEsquerda size={14} /></button>
                <span>{currentPageQuestions + 1} / {questionsSessions.length}</span>
                <button onClick={handleNextQuestions} className="nav-btn" disabled={currentPageQuestions === questionsSessions.length - 1}><IconeSetaDireita size={14} /></button>
              </div>
              {(() => {
                const session = questionsSessions[currentPageQuestions];
                const originalIdx = sessions.findIndex(s => s === session);
                return (
                  <div className="resolucao-block">
                    <h3>Sessão {currentPageQuestions + 1} - {new Date(session.timestamp).toLocaleString()}</h3>
                    <div className="action-buttons" style={{ marginBottom: '1rem', gap: '0.5rem' }}>
                      <button onClick={() => handleEdit(session, originalIdx)} className="button button-outline">
                        Editar respostas
                      </button>
                      <button onClick={() => handlePrint(session)} className="button button-sucesso">Baixar PDF</button>
                      <button onClick={() => handleDelete(originalIdx)} className="delete-button-session">
                        Excluir sessão
                      </button>
                    </div>
                    {Array.isArray(session.questions) && session.questions.map((q, qIdx) => {
                      const chave = `q:${originalIdx}:${qIdx}`;
                      return (
                        <div key={qIdx} style={{ marginBottom: '1rem', borderTop: '1px solid #ccc', paddingTop: '0.5rem' }}>
                          <p><strong>Questão {qIdx+1}:</strong> <MarkdownRenderer content={q.text} /></p>
                          <p><strong>Sua resposta:</strong> {q.user_answer || '(não respondida)'}</p>
                          <button type="button" className="button button-outline" style={{ marginTop: '0.5rem' }} onClick={() => setGabaritosAbertos(prev => ({ ...prev, [chave]: !prev[chave] }))}>
                            {gabaritosAbertos[chave] ? 'Ocultar gabarito' : 'Ver gabarito'}
                          </button>
                          {gabaritosAbertos[chave] && (
                            <p style={{ marginTop: '0.5rem' }}>
                              <strong>Resposta correta / Explicação:</strong> <MarkdownRenderer content={q.explanation} />
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          )}
          {flashcardsSessions.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <h3>Flashcards</h3>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <button onClick={handlePrevFlashcards} className="nav-btn" disabled={currentPageFlashcards === 0}><IconeSetaEsquerda size={14} /></button>
                <span>{currentPageFlashcards + 1} / {flashcardsSessions.length}</span>
                <button onClick={handleNextFlashcards} className="nav-btn" disabled={currentPageFlashcards === flashcardsSessions.length - 1}><IconeSetaDireita size={14} /></button>
              </div>
              {(() => {
                const session = flashcardsSessions[currentPageFlashcards];
                const originalIdx = sessions.findIndex(s => s === session);
                return (
                  <div className="resolucao-block">
                    <h3>Sessão {currentPageFlashcards + 1} - {new Date(session.timestamp).toLocaleString()}</h3>
                    <div className="action-buttons" style={{ marginBottom: '1rem', gap: '0.5rem' }}>
                      <button onClick={() => handleEdit(session, originalIdx)} className="button button-outline">
                        Editar flashcards
                      </button>
                      <button onClick={() => handlePrint(session)} className="button button-sucesso">Baixar PDF</button>
                      <button onClick={() => handleDelete(originalIdx)} className="delete-button-session">
                        Excluir sessão
                      </button>
                    </div>
                    {Array.isArray(session.flashcards) && session.flashcards.map((card, cardIdx) => {
                      const chave = `f:${originalIdx}:${cardIdx}`;
                      return (
                        <div key={cardIdx} style={{ marginBottom: '1rem', borderTop: '1px solid #ccc', paddingTop: '0.5rem' }}>
                          <p><strong>Flashcard {cardIdx + 1}:</strong> {card.title || '(sem título)'}</p>
                          <p><strong>Objetivo:</strong> <MarkdownRenderer content={card.objective || ''} /></p>
                          <p><strong>Explicação:</strong> <MarkdownRenderer content={card.explanation || ''} /></p>
                          <p><strong>Exemplo:</strong> <MarkdownRenderer content={card.example || ''} /></p>
                          <p><strong>Exercício:</strong> <MarkdownRenderer content={card.exercise || ''} /></p>
                          <button type="button" className="button button-outline" style={{ marginTop: '0.5rem' }} onClick={() => setGabaritosAbertos(prev => ({ ...prev, [chave]: !prev[chave] }))}>
                            {gabaritosAbertos[chave] ? 'Ocultar resposta' : 'Ver resposta'}
                          </button>
                          {gabaritosAbertos[chave] && (
                            <p style={{ marginTop: '0.5rem' }}>
                              <strong>Resposta:</strong> <MarkdownRenderer content={card.answer || ''} />
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      </div>

      {editingSession && (
        <GeneratedQuestionsView
          topic={topicName}
          questions={editingSession.questions}
          onClose={() => { setEditingSession(null); setEditingIndex(null); loadSessions(); }}
          onSaved={loadSessions}
          editMode={true}
          sessionIdx={editingIndex}
          questoesDoTopico={questoesDoTopico}
          initialAnswers={(() => {
            const ans = {};
            if (Array.isArray(editingSession.questions)) {
              editingSession.questions.forEach((q, i) => {
                ans[i] = { value: q.user_answer, type: q.type, alternativeIndex: q.alternative_index };
              });
            }
            return ans;
          })()}
          onInsertQuestion={onInsertQuestion}
          onInsertAll={onInsertAll}
        />
      )}
      {editingFlashcardsSession && (
        <FlashcardsViewer
          topic={topicName}
          sessionData={editingFlashcardsSession}
          onClose={() => { setEditingFlashcardsSession(null); setEditingFlashcardsIndex(null); loadSessions(); }}
          onSaved={loadSessions}
          editMode={true}
          sessionIdx={editingFlashcardsIndex}
        />
      )}
    </>
  );
}

export default SessionsViewer;