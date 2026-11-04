import React, { useState } from 'react';
import MarkdownRenderer from './MarkdownContent';
import { evaluateAnswer } from '../services/api';
import { normalizarTexto as normalizar, ehGabaritoVerdadeiroFalso, extrairRespostaCurta } from '../utils/questoes';

function ResponderQuestao({ questao, topic, model }) {
  const [marcada, setMarcada] = useState('');
  const [respostaTexto, setRespostaTexto] = useState('');
  const [conferida, setConferida] = useState(false);
  const [acertou, setAcertou] = useState(null);
  const [avaliando, setAvaliando] = useState(false);
  const [parecer, setParecer] = useState('');

  if (!questao) {
    return <div className="info-message">Selecione uma questão na lista para responder.</div>;
  }

  const enunciado = questao.enunciado || '';
  const tipo = (questao.tipo || '').toLowerCase();
  const gabarito = extrairRespostaCurta(questao.resposta || '');
  const explicacao = questao.explicacao || '';

  const linhasEnunciado = enunciado.split('\n');
  const primeiraAlternativa = linhasEnunciado.findIndex(l => /^[A-Fa-f]\)\s*\S/.test(l.trim()));
  const alternativas = primeiraAlternativa >= 0
    ? linhasEnunciado.slice(primeiraAlternativa)
        .map(l => l.trim()).filter(l => /^[A-Fa-f]\)\s*\S/.test(l))
    : [];
  const enunciadoPrincipal = (primeiraAlternativa >= 0 && alternativas.length >= 2
    ? linhasEnunciado.slice(0, primeiraAlternativa).join('\n')
    : enunciado
  ).trim();

  const gabaritoNormalizado = normalizar(gabarito);
  const gabaritoEhVerdadeiroFalso = ehGabaritoVerdadeiroFalso(gabarito);
  const ehVf = tipo.includes('vf') || tipo.includes('verdadeiro') || gabaritoEhVerdadeiroFalso;
  const opcoesResposta = alternativas.length >= 2
    ? alternativas
    : (ehVf ? ['A) Verdadeiro', 'B) Falso'] : []);

  const conferir = async () => {
    if (opcoesResposta.length >= 2) {
      const letraMarcada = ((marcada.match(/^\s*([A-Fa-f])\)/) || [])[1] || '').toUpperCase();
      const letraGabarito = (((gabarito.match(/^\s*([A-Fa-f])\)/) || [])[1]) ||
        ((gabarito.match(/^\s*([A-Fa-f])[.)]?\s*$/) || [])[1]) || '').toUpperCase();
      const gabaritoVf = (ehVf && alternativas.length < 2)
        ? (['v', 'verdadeiro'].includes(gabaritoNormalizado) ? 'A) Verdadeiro'
          : (['f', 'falso'].includes(gabaritoNormalizado) ? 'B) Falso' : ''))
        : '';
      if (gabaritoVf) {
        setAcertou(marcada === gabaritoVf);
      } else if (letraGabarito) {
        setAcertou(!!letraMarcada && letraMarcada === letraGabarito);
      } else if (gabarito.trim()) {
        setAcertou(normalizar(gabarito) !== '' && normalizar(gabarito) === normalizar(marcada));
      } else {
        setAcertou(null);
      }
      setConferida(true);
      return;
    }

    setAvaliando(true);
    setParecer('');
    setAcertou(null);
    try {
      const res = await evaluateAnswer({
        topic,
        question: enunciado || enunciadoPrincipal,
        correct_answer: gabarito,
        explanation: explicacao,
        user_answer: respostaTexto,
        model
      });
      const dados = (res && res.data) || {};
      setAcertou(dados.correct === true);
      setParecer(dados.feedback || '');
    } catch (err) {
      console.error('Erro ao avaliar a resposta:', err);
      setAcertou(null);
      const semServico = err && err.response && (err.response.status === 404 || typeof err.response.data === 'string');
      setParecer(semServico
        ? 'O serviço de avaliação não está disponível. É preciso reiniciar o backend e o proxy para que a análise da resposta funcione.'
        : 'Não foi possível avaliar a resposta agora. Tente de novo em instantes ou compare com o gabarito abaixo.');
    } finally {
      setAvaliando(false);
      setConferida(true);
    }
  };

  const recomecar = () => {
    setMarcada('');
    setRespostaTexto('');
    setConferida(false);
    setAcertou(null);
    setParecer('');
  };

  return (
    <div className="responder-questao">
      {enunciadoPrincipal || alternativas.length < 2 ? (
        <div className="responder-enunciado">
          <MarkdownRenderer content={enunciadoPrincipal || '(sem enunciado)'} />
        </div>
      ) : null}

      {opcoesResposta.length >= 2 ? (
        <div className="responder-alternativas">
          {opcoesResposta.map(alt => (
            <label key={alt} className="responder-alternativa">
              <input
                type="radio"
                name="responder-alternativa"
                checked={marcada === alt}
                onChange={() => setMarcada(alt)}
                disabled={conferida}
              />
              <MarkdownRenderer content={alt} />
            </label>
          ))}
        </div>
      ) : (
        <textarea
          className="form-control"
          rows={4}
          value={respostaTexto}
          onChange={(e) => setRespostaTexto(e.target.value)}
          disabled={conferida}
          placeholder="Escreva sua resposta"
        />
      )}

      <div className="form-actions" style={{ marginTop: '0.75rem' }}>
        {avaliando ? (
          <span className="hint-text">Analisando sua resposta com a inteligência artificial...</span>
        ) : !conferida ? (
          <button
            type="button"
            className="save-button"
            onClick={conferir}
            disabled={opcoesResposta.length >= 2 ? !marcada : !respostaTexto.trim()}
          >
            Conferir resposta
          </button>
        ) : (
          <button type="button" className="button button-secundario" onClick={recomecar}>
            Tentar de novo
          </button>
        )}
      </div>

      {conferida && (
        <div style={{ marginTop: '0.75rem' }}>
          {acertou === true && <p className="flash-success">Você acertou!</p>}
          {acertou === false && <p className="flash-error">Sua resposta não confere com o gabarito.</p>}
          {acertou === null && (
            <p className="hint-text">Compare sua resposta com a resposta correta abaixo.</p>
          )}
          {parecer && (
            <div className="hint-text">
              <strong>Correção:</strong> {parecer}
            </div>
          )}
          {gabarito && (
            <div>
              <strong>Resposta correta:</strong>{' '}
              <MarkdownRenderer content={gabarito} />
            </div>
          )}
          {explicacao && (
            <div>
              <strong>Explicação:</strong>{' '}
              <MarkdownRenderer content={explicacao} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ResponderQuestao;
