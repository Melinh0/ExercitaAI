import React, { useState, useEffect, useRef } from 'react';
import { createTopic, suggestTopicName } from '../services/api';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const EXEMPLOS_POOLS = {
  exatas: [
    'Cálculo Diferencial e Integral sobre derivadas e integrais',
    'Física Mecânica sobre cinemática e dinâmica',
    'Química Geral sobre estequiometria e equilíbrio',
    'Álgebra Linear sobre matrizes e autovalores',
    'Estatística e Probabilidade sobre distribuições',
  ],
  humanas: [
    'Direito Constitucional sobre controle de constitucionalidade',
    'História do Brasil sobre período colonial',
    'Geografia Física sobre climatologia',
    'Sociologia sobre movimentos sociais',
    'Filosofia sobre ética e moral',
  ],
  biologicas: [
    'Biologia Celular sobre divisão celular',
    'Genética sobre hereditariedade',
    'Fisiologia Humana sobre sistema nervoso',
    'Ecologia sobre cadeias alimentares',
    'Microbiologia sobre bactérias e vírus',
  ],
  tecnologia: [
    'Programação Python para automação de tarefas',
    'Estruturas de Dados e Algoritmos em Java',
    'Desenvolvimento Web com React e Node.js',
    'Banco de Dados SQL e NoSQL',
    'Machine Learning com Scikit-learn',
  ],
  saude: [
    'Anatomia Humana sobre sistema cardiovascular',
    'Farmacologia sobre antibióticos',
    'Patologia sobre doenças cardiovasculares',
    'Enfermagem em emergências',
    'Saúde Pública e epidemiologia',
  ],
  gerais: [
    'Matemática Financeira sobre juros compostos',
    'Direito Constitucional sobre controle de constitucionalidade',
    'Química Orgânica sobre reações de substituição',
  ],
};

const EXEMPLOS = EXEMPLOS_POOLS.gerais;

function getPoolAtual() {
  const pools = Object.values(EXEMPLOS_POOLS);
  const agora = Date.now();
  const indice = Math.floor(agora / (30 * 60 * 1000)) % pools.length;
  return pools[indice];
}

function getExemplosAtuais() {
  const pool = getPoolAtual();
  return pool.slice(0, 3);
}

const NOMES_VAGOS = new Set([
  'novo', 'nova', 'novos', 'novas', 'teste', 'testes', 'test',
  'aula', 'aulas', 'estudo', 'estudos', 'material', 'materiais',
  'tarefa', 'tarefas', 'atividade', 'atividades', 'assunto', 'assuntos',
  'topico', 'topicos', 'conteudo', 'conteudos', 'geral', 'gerais',
  'coisa', 'coisas', 'diversos', 'diversas', 'rascunho', 'backup',
  'arquivo', 'arquivos', 'informacao', 'informacoes', 'caderno',
  'apostila', 'prova', 'provas', 'trabalho', 'trabalhos',
]);

function nomeNormalizado(valor) {
  return valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function nomeSalvo(valor) {
  return valor.replace(/[^\p{L}\p{N}_-]/gu, '_');
}

function NewTopicModal({ isOpen, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [descricao, setDescricao] = useState('');
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [sugestaoAberta, setSugestaoAberta] = useState(false);
  const [sugestaoOculta, setSugestaoOculta] = useState(false);
  const [sugerindo, setSugerindo] = useState(false);
  const [sugestaoJustificativa, setSugestaoJustificativa] = useState('');
  const [exemplosAtuais, setExemplosAtuais] = useState(() => getExemplosAtuais());
  const nomeInputRef = useRef(null);
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  useEffect(() => {
    if (!isOpen) {
      setName('');
      setDescricao('');
      setError('');
      setCreating(false);
      setSugestaoAberta(false);
      setSugestaoOculta(false);
      setSugerindo(false);
      setSugestaoJustificativa('');
    } else {
      setExemplosAtuais(getExemplosAtuais());
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const interval = setInterval(() => {
      setExemplosAtuais(getExemplosAtuais());
    }, 30 * 60 * 1000);
    return () => clearInterval(interval);
  }, [isOpen]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('O nome do tópico é obrigatório.');
      return;
    }
    setCreating(true);
    setError('');
    createTopic(name)
      .then(res => {
        if (res.data.success) {
          setName('');
          onCreated();
        } else {
          setError(res.data.error || 'Erro ao criar o tópico.');
        }
      })
      .catch(err => {
        setError(err.response?.data?.error || 'Erro ao criar o tópico.');
      })
      .finally(() => setCreating(false));
  };

  const handleSugerir = async () => {
    if (sugerindo) return;
    if (!name.trim() && !descricao.trim()) {
      setError('Digite um nome ou descreva o foco do estudo antes de pedir a sugestão.');
      return;
    }
    setSugerindo(true);
    setError('');
    setSugestaoJustificativa('');
    try {
      const res = await suggestTopicName(name.trim(), descricao.trim());
      const sugestao = (res.data.sugestao || '').trim();
      if (sugestao) {
        setName(sugestao);
        if (nomeInputRef.current) nomeInputRef.current.focus();
      } else {
        setSugestaoJustificativa(
          res.data.justificativa || 'Descreva brevemente o foco do estudo para receber uma sugestão.'
        );
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Não foi possível gerar a sugestão.');
    } finally {
      setSugerindo(false);
    }
  };

  const fecharSugestao = () => {
    setSugestaoOculta(true);
    setSugestaoAberta(false);
    setSugestaoJustificativa('');
  };

  if (!isOpen) return null;

  const digitado = name.trim();
  const exibido = nomeSalvo(digitado).replace(/_/g, ' ');
  const mostrarPrevia = digitado.length > 0 && exibido !== digitado;
  const nomeVago = NOMES_VAGOS.has(nomeNormalizado(digitado));
  const mostrarSugestao = !sugestaoOculta && (sugestaoAberta || nomeVago);

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '560px' }}>
        <span className="close" onClick={onClose} aria-label="Fechar">&times;</span>
        <h2>Criar novo tópico</h2>
        {error && <div className="flash-error">{error}</div>}
        <form onSubmit={handleSubmit} className="edit-form">
          <div className="form-group">
            <label htmlFor="nome">O que você quer estudar?</label>
            <input
              type="text"
              id="nome"
              ref={nomeInputRef}
              className="form-control nome-topico-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ex.: Matemática Financeira sobre juros compostos"
              autoFocus
              disabled={creating}
              required
            />
            <p className="nome-topico-ajuda">
              Escreva a matéria e, se quiser, o foco dentro dela. Quanto mais
              específico, melhores as questões e os flashcards gerados.
            </p>
            {nomeVago && (
              <div className="flash-warning nome-topico-aviso" role="alert">
                Nome muito genérico. Inclua a matéria e o foco do estudo — por
                exemplo, "Direito Constitucional sobre o controle de
                constitucionalidade".
              </div>
            )}
            {mostrarPrevia && (
              <p className="nome-topico-previa">
                Aparecerá na sua lista como: <strong>{exibido}</strong>
              </p>
            )}
            {mostrarSugestao ? (
              <div className="nome-topico-sugestao-area">
                <div className="nome-topico-sugestao-cabecalho">
                  <label htmlFor="descricao">Descreva o foco do estudo (opcional)</label>
                  <button
                    type="button"
                    className="nome-topico-fechar"
                    onClick={fecharSugestao}
                    disabled={creating || sugerindo}
                  >
                    Fechar
                  </button>
                </div>
                <textarea
                  id="descricao"
                  className="form-control nome-topico-descricao"
                  rows={3}
                  value={descricao}
                  onChange={(e) => setDescricao(e.target.value)}
                  placeholder="Ex.: vou estudar tarifas de energia elétrica e como calcular contas de luz"
                  disabled={creating || sugerindo}
                />
                <button
                  type="button"
                  className="button button-secundario nome-topico-sugerir-btn"
                  onClick={handleSugerir}
                  disabled={creating || sugerindo}
                >
                  {sugerindo ? 'Sugerindo...' : 'Sugerir nome específico'}
                </button>
                {sugestaoJustificativa && (
                  <p className="nome-topico-sugestao-justificativa">{sugestaoJustificativa}</p>
                )}
              </div>
            ) : (
              <button
                type="button"
                className="nome-topico-sugerir-toggle"
                onClick={() => { setSugestaoOculta(false); setSugestaoAberta(true); }}
                disabled={creating}
              >
                Sugerir um nome mais específico
              </button>
            )}
            <div className="nome-topico-exemplos">
              <span className="nome-topico-exemplos-rotulo">Exemplos:</span>
              {exemplosAtuais.map((exemplo) => (
                <button
                  key={exemplo}
                  type="button"
                  className="nome-topico-chip"
                  onClick={() => setName(exemplo)}
                  disabled={creating}
                >
                  {exemplo}
                </button>
              ))}
            </div>
          </div>
          <div className="form-actions">
            <button type="submit" className="button" disabled={creating}>
              {creating ? 'Criando...' : 'Criar tópico'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default NewTopicModal;