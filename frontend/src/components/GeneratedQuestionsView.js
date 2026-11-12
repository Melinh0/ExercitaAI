import React, { useState, useMemo } from 'react';
import { saveAnswers, updateSession, updateQuestion } from '../services/api';
import { useConfirm } from '../contexts/ConfirmContext';
import MarkdownRenderer from './MarkdownContent';
import SugestoesContexto from './SugestoesContexto';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const normalizarParaComparacao = (t) => (t || '').replace(/\s+/g, ' ').trim().toLowerCase();

function GeneratedQuestionsView({ topic, questions, onClose, onDescartar, onSaved, editMode = false, sessionIdx = null, initialAnswers = {}, onInsertQuestion, onInsertAll, contexto = null, onAdicionarTextos, onPesquisarArtigos, questoesDoTopico = [] }) {
  const { alert, confirm } = useConfirm();
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(true, onClose);
  const [answers, setAnswers] = useState(initialAnswers);
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [inserting, setInserting] = useState(false);
  const [insertingAll, setInsertingAll] = useState(false);
  const [inseridas, setInseridas] = useState(() => new Set());
  const safeQuestions = Array.isArray(questions) ? questions : [];
  const restantes = safeQuestions.filter(q => !inseridas.has(q));
  const todasInseridas = restantes.length === 0;
  const mostrarConcluso = !editMode && todasInseridas;

  const [edicoes, setEdicoes] = useState(() => {
    const inicial = {};
    safeQuestions.forEach((q, idx) => {
      inicial[idx] = {
        resposta: q.correct_answer || q.expected_answer || q.resposta || '',
        explicacao: q.explanation || ''
      };
    });
    return inicial;
  });
  const [avisosMostrados, setAvisosMostrados] = useState({});

  const mapaTopico = useMemo(() => {
    const lista = Array.isArray(questoesDoTopico) ? questoesDoTopico : [];
    const mapa = [];
    lista.forEach(item => {
      const questoes = Array.isArray(item.questoes) ? item.questoes : [];
      questoes.forEach((q, i) => {
        const texto = normalizarParaComparacao(q.enunciado || item.texto || '');
        if (!texto) return;
        mapa.push({ texto, imagem: item.imagem, q_idx: i, original: q || {} });
      });
    });
    return mapa;
  }, [questoesDoTopico]);

  const acharNoTopico = (textoSessao) => {
    const alvo = normalizarParaComparacao(textoSessao);
    if (!alvo || mapaTopico.length === 0) return null;
    return mapaTopico.find(item => item.texto === alvo || item.texto.startsWith(alvo) || alvo.startsWith(item.texto)) || null;
  };

  if (safeQuestions.length === 0 || mostrarConcluso) {
    return (
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content">
          <span className="close" onClick={onClose}>&times;</span>
          <h2>{(safeQuestions.length > 0 || inseridas.size > 0) ? 'Questões inseridas' : 'Nenhuma questão disponível'}</h2>
          <p>{todasInseridas
            ? 'Todas as questões geradas já foram inseridas no tópico. Use as setas de navegação para chegar até elas: as questões inseridas aparecem depois das imagens.'
            : 'Não foi possível carregar as questões. Tente novamente.'}</p>
        </div>
      </div>
    );
  }

  const handleAnswerChange = (qIndex, value, type, alternativeIndex = null) => {
    setAnswers(prev => ({
      ...prev,
      [qIndex]: { value, type, alternativeIndex }
    }));
  };

  const avisarQuestaoNoTopico = async (idx) => {
    if (avisosMostrados[idx]) return;
    const alvo = acharNoTopico(safeQuestions[idx] && safeQuestions[idx].text);
    if (!alvo) return;
    setAvisosMostrados(prev => ({ ...prev, [idx]: true }));
    await alert({
      title: 'Questão já adicionada ao tópico',
      message: 'Esta questão já está no tópico. O que for editado aqui (resposta e resolução) também será aplicado na questão do tópico ao salvar, para os dois ficarem iguais.',
      variant: 'info',
    });
  };

  const sincronizarComTopico = async () => {
    let sincronizadas = 0;
    for (let idx = 0; idx < safeQuestions.length; idx++) {
      const alvo = acharNoTopico(safeQuestions[idx] && safeQuestions[idx].text);
      if (!alvo) continue;
      const edicao = edicoes[idx];
      if (!edicao) continue;
      const original = alvo.original || {};
      const resposta = edicao.resposta !== undefined ? edicao.resposta : (original.resposta || '');
      const explicacao = edicao.explicacao !== undefined ? edicao.explicacao : (original.explicacao || '');
      if (resposta === original.resposta && explicacao === original.explicacao) continue;
      try {
        await updateQuestion(topic, alvo.imagem, alvo.q_idx, {
          resposta,
          explicacao,
          idx: 0,
          original_json: JSON.stringify(original)
        });
        sincronizadas += 1;
      } catch (err) {
        console.error('Erro ao sincronizar questão com o tópico:', err);
      }
    }
    return sincronizadas;
  };

  const handleSubmit = async () => {
    const sessionData = {
      timestamp: new Date().toISOString(),
      questions: safeQuestions.map((q, idx) => ({
        ...q,
        user_answer: answers[idx]?.value || null,
        alternative_index: answers[idx]?.alternativeIndex,
        correct_answer: edicoes[idx]?.resposta !== undefined ? edicoes[idx].resposta : q.correct_answer,
        explanation: edicoes[idx]?.explicacao !== undefined ? edicoes[idx].explicacao : q.explanation,
      }))
    };
    setSaving(true);
    try {
      if (editMode && sessionIdx !== null) {
        await updateSession(topic, sessionIdx, sessionData);
        const sincronizadas = await sincronizarComTopico();
        await alert({
          title: 'Sucesso',
          message: sincronizadas > 0
            ? `Sessão atualizada com sucesso! ${sincronizadas} questão(ões) sincronizada(s) com o tópico.`
            : 'Sessão atualizada com sucesso!',
          variant: 'success',
        });
      } else {
        await saveAnswers(topic, sessionData);
        await alert({
          title: 'Sucesso',
          message: 'Respostas salvas com sucesso!',
          variant: 'success',
        });
      }
      setSubmitted(true);
      if (onSaved) onSaved();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao salvar respostas.',
        variant: 'danger',
      });
    } finally {
      setSaving(false);
    }
  };

  const extractAlternativesFromText = (text) => {
    if (!text) return [];
    const lines = text.split('\n');
    const alternatives = [];
    const regex = /^[-–•*]*\s*([A-Da-d])([.)])\s+(.*)/;
    for (const line of lines) {
      const match = line.match(regex);
      if (match) {
        const letter = match[1].toUpperCase();
        const content = match[3].trim();
        alternatives.push(`${letter}) ${content}`);
      } else if (/^\s*[A-Da-d][.)]/.test(line)) {
        const letter = line.charAt(0).toUpperCase();
        const content = line.substring(2).trim();
        if (content) alternatives.push(`${letter}) ${content}`);
      }
    }
    if (alternatives.length === 4) return alternatives;
    const altMatches = text.match(/[A-Da-d][.)]\s+[^\n]+/g);
    if (altMatches && altMatches.length >= 2) {
      return altMatches.map(m => {
        const letter = m.charAt(0).toUpperCase();
        const content = m.substring(2).trim();
        return `${letter}) ${content}`;
      });
    }
    return [];
  };

  const normalizeAlternatives = (q) => {
    if (q.type !== 'objetiva') return null;
    if (Array.isArray(q.alternatives) && q.alternatives.length > 0) {
      return q.alternatives;
    }
    if (typeof q.alternatives === 'string' && q.alternatives.trim()) {
      const lines = q.alternatives.split('\n').filter(l => l.trim());
      if (lines.length >= 2) return lines;
    }
    if (q.text && typeof q.text === 'string') {
      const extracted = extractAlternativesFromText(q.text);
      if (extracted.length >= 2) return extracted;
      const possible = q.text.match(/[A-Da-d][.)]\s+[^A-Da-d]*?(?=[A-Da-d][.)]|$)/gs);
      if (possible && possible.length >= 2) {
        return possible.map(p => p.trim());
      }
    }
    return null;
  };

  const handleInsert = async (questionData) => {
    if (inserting || insertingAll || inseridas.has(questionData)) return;
    setInserting(true);
    try {
      if (onInsertQuestion) {
        await onInsertQuestion(questionData);
        setInseridas(prev => new Set(prev).add(questionData));
      } else {
        console.error('onInsertQuestion não está definido');
        await alert({
          title: 'Erro',
          message: 'Função de inserção não disponível.',
          variant: 'danger',
        });
      }
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao inserir questão.',
        variant: 'danger',
      });
      console.error(err);
    } finally {
      setInserting(false);
    }
  };

  const handleInsertAll = async () => {
    if (!onInsertAll || insertingAll || restantes.length === 0) return;
    const ok = await confirm({
      title: 'Inserir todas as questões',
      message: `Inserir as ${restantes.length} questões restantes no tópico?`,
      confirmText: 'Inserir todas',
      variant: 'info',
    });
    if (!ok) return;
    setInsertingAll(true);
    try {
      const lista = [...restantes];
      await onInsertAll(lista);
      setInseridas(prev => {
        const novo = new Set(prev);
        lista.forEach(q => novo.add(q));
        return novo;
      });
    } catch (err) {
      console.error(err);
    } finally {
      setInsertingAll(false);
    }
  };

  if (submitted) {
    return (
      <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
        <div className="modal-content">
          <span className="close" onClick={onClose}>&times;</span>
          <h2>{editMode ? 'Sessão Atualizada' : 'Respostas Salvas'}</h2>
          <p>{editMode ? 'Sessão atualizada com sucesso!' : 'Suas respostas foram salvas com sucesso!'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '80vh', overflowY: 'auto' }}>
        <span className="close" onClick={onClose}>&times;</span>
        <h2>{editMode ? 'Editar Respostas' : 'Questões Geradas'}</h2>
        {contexto && contexto.insuficiente && (
          <div className="contexto-aviso">
            <p>
              Pouco material sobre o assunto foi encontrado neste tópico, então as questões podem repetir conceitos.
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
                  <button type="button" className="button button-secundario" onClick={() => onPesquisarArtigos('', contexto.instrucoes || '')}>
                    Pesquisar artigos
                  </button>
                )}
              </div>
            )}
            <SugestoesContexto ativo topico={topic} instrucoes={contexto.instrucoes} />
          </div>
        )}
        <div className="insert-all-bar" style={{ gap: '0.5rem', flexWrap: 'wrap' }}>
          {onInsertAll && restantes.length > 0 && (
            <button
              type="button"
              onClick={handleInsertAll}
              className="save-button"
              disabled={insertingAll || inserting}
            >
              {insertingAll
                ? 'Inserindo...'
                : `Inserir todas no tópico (${restantes.length})`}
            </button>
          )}
          {!editMode && (
            <button
              type="button"
              onClick={handleSubmit}
              className="button button-outline"
              disabled={saving}
            >
              {saving ? 'Salvando...' : 'Salvar no histórico e finalizar (fazer depois)'}
            </button>
          )}
        </div>
        {safeQuestions.map((q, idx) => {
          const alternatives = normalizeAlternatives(q);
          const isObjetiva = q.type === 'objetiva';
          const hasAlternatives = isObjetiva && alternatives && alternatives.length > 0;
          const explanation = q.explanation || 'Explicação não disponível para esta questão.';
          const questaoEstaNoTopico = editMode && !!acharNoTopico(q.text);
          return (
            <div key={idx} className="resolucao-block" style={{ marginBottom: '1.5rem' }}>
              <h3>Questão {idx + 1} ({q.type === 'objetiva' ? 'Objetiva' : q.type === 'aberta' ? 'Discursiva' : 'Verdadeiro/Falso'})</h3>
              <MarkdownRenderer content={q.text} />
              {hasAlternatives && (
                <div className="alternatives-container" style={{ marginTop: '1rem' }}>
                  {alternatives.map((alt, altIdx) => {
                    const altText = typeof alt === 'string' ? alt : (alt.text || String(alt));
                    return (
                      <label key={altIdx} className="alternative-label" style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5rem', cursor: 'pointer' }}>
                        <input
                          type="radio"
                          name={`q${idx}`}
                          value={altText}
                          onChange={() => handleAnswerChange(idx, altText, 'objetiva', altIdx)}
                          checked={answers[idx]?.value === altText}
                          style={{ marginRight: '8px', transform: 'scale(1.1)', verticalAlign: 'middle' }}
                        />
                        <span style={{ verticalAlign: 'middle' }}>{altText}</span>
                      </label>
                    );
                  })}
                </div>
              )}
              {isObjetiva && !hasAlternatives && (
                <div className="info-message" style={{ marginTop: '1rem', color: '#d9534f' }}>
                  Nenhuma alternativa encontrada para esta questão objetiva. Entre em contato com o administrador.
                </div>
              )}
              {q.type === 'aberta' && (
                <textarea
                  rows="4"
                  className="form-control"
                  placeholder="Digite sua resposta aqui..."
                  value={answers[idx]?.value || ''}
                  onChange={(e) => handleAnswerChange(idx, e.target.value, 'aberta')}
                />
              )}
              {q.type === 'vf' && (
                <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
                  <label style={{ cursor: 'pointer' }}>
                    <input type="radio" name={`q${idx}`} value="Verdadeiro" onChange={() => handleAnswerChange(idx, 'Verdadeiro', 'vf')} checked={answers[idx]?.value === 'Verdadeiro'} style={{ marginRight: '5px' }} /> Verdadeiro
                  </label>
                  <label style={{ cursor: 'pointer' }}>
                    <input type="radio" name={`q${idx}`} value="Falso" onChange={() => handleAnswerChange(idx, 'Falso', 'vf')} checked={answers[idx]?.value === 'Falso'} style={{ marginRight: '5px' }} /> Falso
                  </label>
                </div>
              )}
              <details
                style={{ marginTop: '1rem' }}
                onToggle={(e) => { if (e.target.open && editMode) avisarQuestaoNoTopico(idx); }}
              >
                <summary style={{ cursor: 'pointer', color: '#3b82f6' }}>Ver explicação (após responder)</summary>
                <MarkdownRenderer content={editMode ? (edicoes[idx]?.explicacao || explanation) : explanation} />
                {editMode && (
                  <div className="edit-form" style={{ marginTop: '1rem' }}>
                    <div className="form-group">
                      <label>Resposta (gabarito)</label>
                      <textarea
                        className="form-control"
                        rows="2"
                        placeholder="Resposta correta da questão"
                        value={edicoes[idx]?.resposta || ''}
                        onChange={(e) => setEdicoes(prev => ({ ...prev, [idx]: { ...prev[idx], resposta: e.target.value } }))}
                      />
                    </div>
                    <div className="form-group">
                      <label>Resolução (explicação)</label>
                      <textarea
                        className="form-control"
                        rows="4"
                        placeholder="Explicação que explica a resposta"
                        value={edicoes[idx]?.explicacao || ''}
                        onChange={(e) => setEdicoes(prev => ({ ...prev, [idx]: { ...prev[idx], explicacao: e.target.value } }))}
                      />
                    </div>
                    {questaoEstaNoTopico && (
                      <p className="hint-text" style={{ marginTop: '0.25rem' }}>
                        Esta questão já está no tópico: ao salvar, a resposta e a resolução são aplicadas também lá, para os dois ficarem iguais.
                      </p>
                    )}
                  </div>
                )}
              </details>
              <button
                onClick={() => handleInsert(q)}
                className="button button-sucesso"
                style={{ marginTop: '1rem' }}
                disabled={inserting || insertingAll || inseridas.has(q)}
              >
                {inseridas.has(q) ? 'Já inserida no tópico' : (inserting ? 'Inserindo...' : 'Inserir no tópico')}
              </button>
            </div>
          );
        })}
        <div className="form-actions">
          {editMode && (
            <button onClick={handleSubmit} className="save-button" disabled={saving}>{saving ? 'Salvando...' : 'Atualizar Respostas'}</button>
          )}
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

export default GeneratedQuestionsView;