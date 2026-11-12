import React, { useState, useEffect } from 'react';
import { saveAnswers, updateSession } from '../services/api';
import { useConfirm } from '../contexts/ConfirmContext';
import MarkdownRenderer from './MarkdownContent';
import SugestoesContexto from './SugestoesContexto';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { IconeSetaEsquerda, IconeSetaDireita } from './Icons';

function FlashcardsViewer({ topic, sessionData, onClose, onDescartar, onSaved, editMode = false, sessionIdx = null, onAdicionarTextos, onPesquisarArtigos }) {
  const { alert } = useConfirm();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(true, onClose);
  const [session, setSession] = useState(() => ({
    kind: 'flashcards',
    timestamp: new Date().toISOString(),
    subject: '',
    model: '',
    instructions: '',
    flashcards: [],
    metadata: {},
    ...sessionData
  }));
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editandoConteudo, setEditandoConteudo] = useState(false);

  useEffect(() => {
    setSession(prev => ({ ...prev, ...sessionData }));
  }, [sessionData]);

  useEffect(() => {
    setCurrentIndex(0);
    setShowAnswer(false);
    setEditandoConteudo(false);
  }, [sessionData]);

  let safeFlashcards = Array.isArray(session.flashcards) ? session.flashcards : [];

  const hasRecommendation = session.metadata && session.metadata.recommendation;

  if (!sessionData || safeFlashcards.length === 0) {
    return (
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content">
          <span className="close" onClick={onClose}>&times;</span>
          <h2>Flashcards</h2>
          <p>Não há flashcards disponíveis para exibir.</p>
        </div>
      </div>
    );
  }

  const currentCard = safeFlashcards[currentIndex] || {};

  const updateCardField = (index, field, value) => {
    setSession(prev => {
      const newCards = prev.flashcards.map((card, idx) => idx === index ? { ...card, [field]: value } : card);
      return { ...prev, flashcards: newCards };
    });
  };

  const handleSave = async () => {
    const payload = {
      ...session,
      kind: 'flashcards',
      timestamp: new Date().toISOString(),
    };
    setSaving(true);
    try {
      if (editMode && sessionIdx !== null) {
        await updateSession(topic, sessionIdx, payload);
        await alert({
          title: 'Sucesso',
          message: 'Plano de flashcards atualizado com sucesso!',
          variant: 'success',
        });
      } else {
        await saveAnswers(topic, payload);
        await alert({
          title: 'Sucesso',
          message: 'Plano de flashcards salvo com sucesso!',
          variant: 'success',
        });
      }
      if (onSaved) onSaved();
      onClose();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao salvar o plano de flashcards.',
        variant: 'danger',
      });
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '850px', maxHeight: '85vh', overflowY: 'auto' }}>
        <span className="close" onClick={onClose}>&times;</span>
        <h2>{editMode ? 'Editar plano de flashcards' : 'Plano de estudos em flashcards'}</h2>

        <div className="flashcard-meta">
          <p><strong>Assunto:</strong> {session.subject || 'Não informado'}</p>
          <p><strong>Modelo:</strong> {session.model || 'Padrão'}</p>
          {session.instructions && <p><strong>Personalização:</strong> {session.instructions}</p>}
        </div>

        {session.contexto && session.contexto.insuficiente && (
          <div className="contexto-aviso">
            <p>
              Pouco material sobre o assunto foi encontrado neste tópico, então os flashcards podem repetir conceitos.
              Adicione mais imagens, textos de apoio ou pesquise artigos para deixar a geração mais variada; abaixo ficam sugestões do que pesquisar.
            </p>
            {(onAdicionarTextos || onPesquisarArtigos) && (
              <div className="contexto-aviso-acoes">
                {onAdicionarTextos && (
                  <button type="button" className="button button-secundario" onClick={onAdicionarTextos}>
                    Adicionar material de apoio
                  </button>
                )}
                {onPesquisarArtigos && (
                  <button type="button" className="button button-secundario" onClick={() => onPesquisarArtigos('', session.contexto.instrucoes || '')}>
                    Pesquisar artigos
                  </button>
                )}
              </div>
            )}
            <SugestoesContexto ativo topico={topic} instrucoes={session.contexto.instrucoes} />
          </div>
        )}

        {hasRecommendation && (
          <div className="info-message flashcard-recommendation">
            <strong>Recomendação da plataforma:</strong>
            <MarkdownRenderer content={session.metadata.recommendation} />
          </div>
        )}

        <div className="flashcard-navigation">
          <button
            onClick={() => { setCurrentIndex(prev => Math.max(0, prev - 1)); setShowAnswer(false); setEditandoConteudo(false); }}
            disabled={currentIndex <= 0}
            className="nav-btn"
          >
            <IconeSetaEsquerda size={14} />
          </button>
          <span className="flashcard-counter">{currentIndex + 1} / {safeFlashcards.length}</span>
          <button
            onClick={() => { setCurrentIndex(prev => Math.min(safeFlashcards.length - 1, prev + 1)); setShowAnswer(false); setEditandoConteudo(false); }}
            disabled={currentIndex >= safeFlashcards.length - 1}
            className="nav-btn"
          >
            <IconeSetaDireita size={14} />
          </button>
        </div>

        <div className="resolucao-block flashcard-viewer">
          <h3>{currentCard.title || `Flashcard ${currentIndex + 1}`}</h3>
          <div className="flashcard-field">
            <strong>Objetivo:</strong>
            <MarkdownRenderer content={currentCard.objective || 'Este flashcard apresenta um objetivo didático.'} />
          </div>
          <div className="flashcard-field">
            <strong>Explicação simples:</strong>
            <MarkdownRenderer content={currentCard.explanation || 'Não há explicação disponível.'} />
          </div>
          <div className="flashcard-field">
            <strong>Exemplo muito simples:</strong>
            <MarkdownRenderer content={currentCard.example || 'Exemplo não disponível.'} />
          </div>
          <div className="flashcard-field">
            <strong>Exercício rápido:</strong>
            <MarkdownRenderer content={currentCard.exercise || 'Sem exercício disponível.'} />
          </div>
          <div className="flashcard-field">
            <button type="button" onClick={() => setShowAnswer(prev => !prev)} className="button" style={{ marginBottom: '1rem' }}>
              {showAnswer ? 'Esconder resposta' : 'Mostrar resposta'}
            </button>
            {showAnswer && (
              <div className="info-message">
                <strong>Resposta:</strong>
                <MarkdownRenderer content={currentCard.answer || 'Sem resposta disponível.'} />
              </div>
            )}
          </div>
          {editMode && (
            <div style={{ marginTop: '1.5rem' }}>
              <button
                type="button"
                className="button button-outline"
                onClick={() => setEditandoConteudo(prev => !prev)}
              >
                {editandoConteudo ? 'Ocultar edição do card' : 'Editar conteúdo do card'}
              </button>
              {editandoConteudo && (
                <div className="edit-form" style={{ marginTop: '1rem' }}>
                  <div className="form-group">
                    <label>Título</label>
                    <input
                      className="form-control"
                      value={currentCard.title || ''}
                      onChange={(e) => updateCardField(currentIndex, 'title', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Objetivo</label>
                    <textarea
                      className="form-control"
                      rows="2"
                      value={currentCard.objective || ''}
                      onChange={(e) => updateCardField(currentIndex, 'objective', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Explicação</label>
                    <textarea
                      className="form-control"
                      rows="3"
                      value={currentCard.explanation || ''}
                      onChange={(e) => updateCardField(currentIndex, 'explanation', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Exemplo</label>
                    <textarea
                      className="form-control"
                      rows="2"
                      value={currentCard.example || ''}
                      onChange={(e) => updateCardField(currentIndex, 'example', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Exercício</label>
                    <textarea
                      className="form-control"
                      rows="2"
                      value={currentCard.exercise || ''}
                      onChange={(e) => updateCardField(currentIndex, 'exercise', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Resposta</label>
                    <textarea
                      className="form-control"
                      rows="2"
                      value={currentCard.answer || ''}
                      onChange={(e) => updateCardField(currentIndex, 'answer', e.target.value)}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {editMode && (
          <div className="form-group" style={{ marginTop: '1rem' }}>
            <label>Assunto</label>
            <input
              className="form-control"
              value={session.subject}
              onChange={(e) => setSession(prev => ({ ...prev, subject: e.target.value }))}
            />
          </div>
        )}

        <div className="form-actions" style={{ marginTop: '1.5rem' }}>
          <button onClick={handleSave} className="save-button" disabled={saving}>
            {saving ? 'Salvando...' : (editMode ? 'Salvar alterações' : 'Salvar plano')}
          </button>
          {!editMode && (
            <button
              onClick={onDescartar || onClose}
              className="button button-perigo"
            >
              Descartar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default FlashcardsViewer;