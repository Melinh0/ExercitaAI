const RESPOSTAS_VERDADEIRO_FALSO = ['v', 'verdadeiro', 'f', 'falso'];

export const normalizarTexto = (texto) => (texto || '')
  .toLowerCase()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/^[a-f]\)\s*/i, '')
  .replace(/[^a-z0-9]+/g, ' ')
  .trim();

export const extrairRespostaCurta = (gabarito) => {
  const texto = (gabarito || '').trim();
  const finais = [...texto.matchAll(/resposta\s*final\s*[:-]\s*([^\n]+)/gi)];
  if (finais.length) return finais[finais.length - 1][1].trim();
  const simples = /resposta\s*[:-]\s*([^\n]+)/i.exec(texto);
  if (simples) return simples[1].trim();
  return texto;
};

export const ehGabaritoVerdadeiroFalso = (gabarito) => {
  const g = normalizarTexto(extrairRespostaCurta(gabarito));
  if (RESPOSTAS_VERDADEIRO_FALSO.includes(g)) return true;
  return RESPOSTAS_VERDADEIRO_FALSO.includes(g.replace(/^(verdadeiro|falso)\s+/, ''));
};

export const normalizarTipoQuestao = (tipo, gabarito) => {
  const t = (tipo || '').toLowerCase().trim();
  if (t.includes('vf') || t.includes('verdadeiro') || t.includes('falso')) return t || 'vf';
  if (ehGabaritoVerdadeiroFalso(gabarito)) return 'vf';
  return t;
};

export const montarPayloadQuestaoGerada = (questionData) => {
  let fullText = questionData.text || '';
  if (Array.isArray(questionData.alternatives) && questionData.alternatives.length > 0) {
    fullText += '\n\n' + questionData.alternatives.join('\n');
  }
  const correctAnswer = questionData.correct_answer || questionData.expected_answer || '';
  return {
    text: fullText,
    type: normalizarTipoQuestao(questionData.type || '', correctAnswer),
    correct_answer: correctAnswer,
    explanation: questionData.explanation || '',
    alternatives: [],
    fonte: 'gerador'
  };
};
