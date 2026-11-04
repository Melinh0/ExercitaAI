import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  getTopic,
  updateQuestion,
  deleteQuestion,
  addQuestion,
  saveWhiteboard,
  renameTopic,
  getDownloadQuestionWhiteboardUrl,
  addTextQuestion,
  addTextQuestions
} from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { useConfirm } from '../contexts/ConfirmContext';
import { useAuth } from '../contexts/AuthContext';
import Sidebar from '../components/Sidebar';
import ImageViewer from '../components/ImageViewer';
import QuestionEditor from '../components/QuestionEditor';
import Whiteboard from '../components/Whiteboard';
import QuestionGeneratorModal from '../components/QuestionGeneratorModal';
import FlashcardGeneratorModal from '../components/FlashcardGeneratorModal';
import FlashcardsViewer from '../components/FlashcardsViewer';
import GeneratedQuestionsView from '../components/GeneratedQuestionsView';
import TimerControl from '../components/TimerControl';
import SessionsViewer from '../components/SessionsViewer';
import AnnotationEditor from '../components/AnnotationEditor';
import ResponderQuestao from '../components/ResponderQuestao';
import StudyStrategyModal from '../components/StudyStrategyModal';
import ArticleSearchModal from '../components/ArticleSearchModal';
import UploadFilesModal from '../components/UploadFilesModal';
import UploadRAGModal from '../components/UploadRAGModal';
import ConfigModal from '../components/ConfigModal';
import CarregandoTela from '../components/CarregandoTela';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { montarPayloadQuestaoGerada } from '../utils/questoes';
import { IconeMenu, IconeSol, IconeLua } from '../components/Icons';

const chaveArquivoDaImagem = (nome) => {
  const m = (nome || '').match(/^(.+)_pag\d{3}\.(png|jpe?g)$/i);
  return m ? m[1] : nome;
};

function TopicView() {
  const { topicName } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { darkMode, toggleDarkMode } = useTheme();
  const { confirm, alert } = useConfirm();
  const { hasOllamaKey } = useAuth();
  const [showBannerConfig, setShowBannerConfig] = useState(false);

  const [images, setImages] = useState([]);
  const [resolutions, setResolutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentIdx, setCurrentIdx] = useState(parseInt(searchParams.get('idx') || '0'));
  const [qIdx, setQIdx] = useState(parseInt(searchParams.get('q') || '0'));
  const [filtro, setFiltro] = useState('tudo');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newQuestion, setNewQuestion] = useState({ questao_num: '', tipo: '', resposta: '', explicacao: '' });
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [newTopicName, setNewTopicName] = useState(topicName);
  const [renameError, setRenameError] = useState('');
  const [activeTab, setActiveTab] = useState('responder');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { modalRef: refAddModal, aoClicarFundo: aoClicarFundoAdd } = useModalAcessibilidade(showAddModal, () => setShowAddModal(false));
  const { modalRef: refRenameModal, aoClicarFundo: aoClicarFundoRename } = useModalAcessibilidade(showRenameModal, () => setShowRenameModal(false));
  const [selectedModel, setSelectedModel] = useState('');
  const [transcriptionMethod, setTranscriptionMethod] = useState('tesseract');
  const [ocrModel, setOcrModel] = useState('');
  const [originalQuestionJson, setOriginalQuestionJson] = useState(null);
  const [showGeneratorModal, setShowGeneratorModal] = useState(false);
  const [showFlashcardsModal, setShowFlashcardsModal] = useState(false);
  const [showSessionsModal, setShowSessionsModal] = useState(false);
  const [showStrategyModal, setShowStrategyModal] = useState(false);
  const [strategyResult, setStrategyResult] = useState(null);
  const [showArticlesModal, setShowArticlesModal] = useState(false);
  const [generatedFlashcards, setGeneratedFlashcards] = useState(null);
  const [showFlashcardsView, setShowFlashcardsView] = useState(false);
  const [generatedQuestions, setGeneratedQuestions] = useState(null);
  const [showGeneratedView, setShowGeneratedView] = useState(false);

  const STORAGE_KEY_QUESTOES = `generated_questions_${topicName}`;
  const STORAGE_KEY_FLASHCARDS = `generated_flashcards_${topicName}`;

  useEffect(() => {
    try {
      const savedQuestoes = localStorage.getItem(STORAGE_KEY_QUESTOES);
      if (savedQuestoes) {
        setGeneratedQuestions(JSON.parse(savedQuestoes));
      }
      const savedFlashcards = localStorage.getItem(STORAGE_KEY_FLASHCARDS);
      if (savedFlashcards) {
        setGeneratedFlashcards(JSON.parse(savedFlashcards));
      }
    } catch (e) {
      console.warn('Erro ao restaurar conteúdo gerado:', e);
    }
  }, [topicName]);

  const persistirQuestoes = (q) => {
    if (q) localStorage.setItem(STORAGE_KEY_QUESTOES, JSON.stringify(q));
    else localStorage.removeItem(STORAGE_KEY_QUESTOES);
  };

  const persistirFlashcards = (f) => {
    if (f) localStorage.setItem(STORAGE_KEY_FLASHCARDS, JSON.stringify(f));
    else localStorage.removeItem(STORAGE_KEY_FLASHCARDS);
  };
  const [articleSearchQuery, setArticleSearchQuery] = useState('');
  const [articleSearchInstrucoes, setArticleSearchInstrucoes] = useState('');
  const [showUploadFilesModal, setShowUploadFilesModal] = useState(false);
  const [showUploadRAGModal, setShowUploadRAGModal] = useState(false);

  const loadTopicData = useCallback((silent = false) => {
    const isSilent = silent === true;
    if (!isSilent) setLoading(true);
    getTopic(topicName)
      .then(res => {
        const imageFiles = Array.isArray(res.data.image_files) ? res.data.image_files : [];
        const resolutionsData = Array.isArray(res.data.resolutions) ? res.data.resolutions : [];
        const textQuestions = resolutionsData
          .filter(item => item.is_text_question === true)
          .map(item => item.imagem);
        const allImages = [...imageFiles, ...textQuestions];
        setImages(allImages);
        setResolutions(resolutionsData);
        setCurrentIdx(prev => {
          if (allImages.length > 0 && prev >= allImages.length) {
            setSearchParams({ idx: 0, q: 0 });
            return 0;
          }
          return prev;
        });
      })
      .catch(err => console.error(err))
      .finally(() => { if (!isSilent) setLoading(false); });
  }, [topicName, setSearchParams]);

  const loadTopicDataRef = useRef(loadTopicData);
  useEffect(() => { loadTopicDataRef.current = loadTopicData; }, [loadTopicData]);

  useEffect(() => {
    setFiltro('tudo');
    loadTopicDataRef.current();
  }, [topicName]);

  useEffect(() => {
    setCurrentIdx(parseInt(searchParams.get('idx') || '0'));
    setQIdx(parseInt(searchParams.get('q') || '0'));
  }, [searchParams]);

  const currentImage = images[currentIdx] || null;
  const currentRes = resolutions.find(r => r.imagem === currentImage) || { questoes: [] };
  const questions = currentRes.questoes || [];
  const currentQuestion = questions[qIdx] || null;

  useEffect(() => {
    if (currentQuestion && !originalQuestionJson) {
      setOriginalQuestionJson({
        numero: currentQuestion.questao,
        tipo: currentQuestion.tipo,
        enunciado: currentQuestion.enunciado,
        resposta: currentQuestion.resposta,
        explicacao: currentQuestion.explicacao
      });
    }
  }, [currentQuestion, originalQuestionJson]);

  const imagemAnteriorRef = useRef(null);
  useEffect(() => {
    if (imagemAnteriorRef.current && imagemAnteriorRef.current !== currentImage) {
      setActiveTab('responder');
    }
    imagemAnteriorRef.current = currentImage;
  }, [currentImage]);

  const resumoResolucoes = useMemo(() => {
    const mapa = {};
    resolutions.forEach(r => { if (r && r.imagem) mapa[r.imagem] = r; });
    return mapa;
  }, [resolutions]);

  const indicesFiltrados = useMemo(() => {
    if (filtro === 'tudo') return images.map((_, i) => i);
    const saida = [];
    images.forEach((nome, i) => {
      const res = resumoResolucoes[nome];
      const ehTexto = !!(res && res.is_text_question === true);
      if (filtro === 'gerador') {
        if (ehTexto && (res.fonte || '') !== 'manual') saida.push(i);
      } else if (filtro === 'manual') {
        if (ehTexto && (res.fonte || '') === 'manual') saida.push(i);
      } else if (filtro.startsWith('arquivo:') && !ehTexto && chaveArquivoDaImagem(nome) === filtro.slice(8)) {
        saida.push(i);
      }
    });
    return saida;
  }, [images, filtro, resumoResolucoes]);

  const opcoesFiltro = useMemo(() => {
    const grupos = new Map();
    let nGerador = 0;
    let nManual = 0;
    images.forEach(nome => {
      const res = resumoResolucoes[nome];
      if (res && res.is_text_question === true) {
        if ((res.fonte || '') === 'manual') nManual += 1;
        else nGerador += 1;
        return;
      }
      const chave = chaveArquivoDaImagem(nome);
      const anterior = grupos.get(chave);
      if (anterior) {
        anterior.total += 1;
      } else {
        grupos.set(chave, {
          chave,
          rotulo: chave !== nome ? chave.replace(/_/g, ' ') : nome,
          total: 1,
        });
      }
    });
    return {
      arquivos: Array.from(grupos.values()),
      nGerador,
      nManual,
      totalGrupos: grupos.size + (nGerador > 0 ? 1 : 0) + (nManual > 0 ? 1 : 0),
    };
  }, [images, resumoResolucoes]);

  useEffect(() => {
    if (filtro === 'tudo') return;
    if (indicesFiltrados.length === 0) { setFiltro('tudo'); return; }
    if (!indicesFiltrados.includes(currentIdx)) setSearchParams({ idx: indicesFiltrados[0], q: 0 });
  }, [filtro, indicesFiltrados, currentIdx, setSearchParams]);

  const posNoFiltro = indicesFiltrados.indexOf(currentIdx);
  const posicaoNoFiltro = posNoFiltro >= 0 ? posNoFiltro + 1 : currentIdx + 1;
  const totalVisivel = filtro === 'tudo' ? images.length : Math.max(indicesFiltrados.length, 1);
  const podeAnterior = indicesFiltrados.some(i => i < currentIdx);
  const podeProximo = indicesFiltrados.some(i => i > currentIdx);

  const qIdxEfetivo = currentQuestion ? qIdx : -1;
  const whiteboardUrl = currentImage
    ? getDownloadQuestionWhiteboardUrl(topicName, currentImage, qIdxEfetivo, currentIdx)
    : null;

  const handlePrev = () => {
    for (let i = currentIdx - 1; i >= 0; i--) {
      if (indicesFiltrados.includes(i)) { setSearchParams({ idx: i, q: 0 }); return; }
    }
  };
  const handleNext = () => {
    for (let i = currentIdx + 1; i < images.length; i++) {
      if (indicesFiltrados.includes(i)) { setSearchParams({ idx: i, q: 0 }); return; }
    }
  };
  const handleQuestionChange = (newQIdx) => { setSearchParams({ idx: currentIdx, q: newQIdx }); };

  const handleSaveQuestion = (updatedData) => {
    const dataToSend = {
      ...updatedData,
      original_json: originalQuestionJson ? JSON.stringify(originalQuestionJson) : null
    };
    updateQuestion(topicName, currentImage, qIdx, dataToSend)
      .then(() => {
        const newRes = resolutions.map(r => {
          if (r.imagem === currentImage) {
            const newQuestoes = [...r.questoes];
            newQuestoes[qIdx] = { ...newQuestoes[qIdx], ...updatedData };
            return { ...r, questoes: newQuestoes };
          }
          return r;
        });
        setResolutions(newRes);
        setOriginalQuestionJson(null);
      })
      .catch(err => console.error(err));
  };

  const handleDeleteQuestion = async () => {
    const confirmed = await confirm({
      title: 'Deletar questão',
      message: 'Tem certeza que deseja deletar esta questão? Essa ação não pode ser desfeita.',
      confirmText: 'Deletar',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    deleteQuestion(topicName, currentImage, qIdx, currentIdx)
      .then(() => {
        const newRes = resolutions.map(r => {
          if (r.imagem === currentImage) {
            const newQuestoes = r.questoes.filter((_, i) => i !== qIdx);
            return { ...r, questoes: newQuestoes };
          }
          return r;
        });
        setResolutions(newRes);
        setQIdx(0);
      })
      .catch(err => console.error(err));
  };

  const handleAddQuestion = () => {
    if (!newQuestion.questao_num) {
      alert({
        title: 'Campo obrigatório',
        message: 'Número da questão é obrigatório.',
        variant: 'warning',
      });
      return;
    }
    addQuestion(topicName, currentImage, { ...newQuestion, idx: currentIdx })
      .then(() => {
        return getTopic(topicName).then(res => {
          setResolutions(res.data.resolutions);
          const newRes = res.data.resolutions.find(r => r.imagem === currentImage);
          const newQIdx = newRes ? newRes.questoes.length - 1 : 0;
          setSearchParams({ idx: currentIdx, q: newQIdx });
        });
      })
      .catch(err => console.error(err))
      .finally(() => {
        setShowAddModal(false);
        setNewQuestion({ questao_num: '', tipo: '', resposta: '', explicacao: '' });
      });
  };

  const aplicarWhiteboard = (res) => {
    const newFilename = res.data.filename;
    const newRes = resolutions.map(r => {
      if (r.imagem === currentImage) {
        if (qIdxEfetivo >= 0) {
          const newQuestoes = [...r.questoes];
          newQuestoes[qIdxEfetivo] = { ...newQuestoes[qIdxEfetivo], whiteboard_img: newFilename };
          return { ...r, questoes: newQuestoes };
        }
        return { ...r, whiteboard_livre: newFilename };
      }
      return r;
    });
    setResolutions(newRes);
  };

  const handleSaveWhiteboard = (imageData) => {
    saveWhiteboard(topicName, {
      topic: topicName,
      image_filename: currentImage,
      q_idx: qIdxEfetivo,
      image_data: imageData
    })
      .then(res => {
        alert({
          title: 'Sucesso',
          message: 'Quadro salvo com sucesso!',
          variant: 'success',
        });
        aplicarWhiteboard(res);
      })
      .catch(err => alert({
        title: 'Erro',
        message: 'Erro ao salvar quadro.',
        variant: 'danger',
      }));
  };

  const handleAutoSaveWhiteboard = (imageData) => {
    saveWhiteboard(topicName, {
      topic: topicName,
      image_filename: currentImage,
      q_idx: qIdxEfetivo,
      image_data: imageData
    })
      .then(res => {
        aplicarWhiteboard(res);
      })
      .catch(err => console.error('Erro ao salvar quadro automaticamente:', err));
  };

  const handleRename = (e) => {
    e.preventDefault();
    if (!newTopicName.trim()) {
      setRenameError('O nome não pode estar vazio.');
      return;
    }
    if (newTopicName.trim().replace(/[^\w\-]/g, '_') === topicName) {
      setShowRenameModal(false);
      setRenameError('');
      return;
    }
    renameTopic(topicName, newTopicName)
      .then(res => {
        if (res.data.success) {
          const prefixo = `quadro:${topicName}:`;
          const novoPrefixo = `quadro:${res.data.new_name}:`;
          for (let i = localStorage.length - 1; i >= 0; i--) {
            const k = localStorage.key(i);
            if (k && k.startsWith(prefixo)) {
              try {
                localStorage.setItem(novoPrefixo + k.slice(prefixo.length), localStorage.getItem(k));
                localStorage.removeItem(k);
              } catch (e) {}
            }
          }
          setShowRenameModal(false);
          setRenameError('');
          navigate(`/topic/${res.data.new_name}`);
        } else {
          setRenameError(res.data.error || 'Erro ao renomear.');
        }
      })
      .catch(err => setRenameError(err.response?.data?.error || 'Erro ao renomear.'));
  };

  const toggleSidebar = () => { setSidebarCollapsed(prev => !prev); };
  const refreshData = useCallback((silent) => { loadTopicDataRef.current(silent === true); }, []);

  const handleInsertGeneratedQuestion = async (questionData) => {
    try {
      await addTextQuestion(topicName, montarPayloadQuestaoGerada(questionData));
      await alert({
        title: 'Sucesso',
        message: 'Questão inserida no tópico. Use as setas de navegação para chegar até ela: as questões inseridas aparecem depois das imagens. Para responder sem ver o gabarito, use a aba Responder.',
        variant: 'success',
      });
      await refreshData(true);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao adicionar questão textual.',
        variant: 'danger',
      });
      console.error(err);
      throw err;
    }
  };

  const handleInsertAllGeneratedQuestions = async (questionsList) => {
    const lista = Array.isArray(questionsList) ? questionsList : [];
    if (lista.length === 0) return;
    try {
      const res = await addTextQuestions(topicName, lista.map(montarPayloadQuestaoGerada));
      const count = res.data.count || lista.length;
      await alert({
        title: 'Sucesso',
        message: (count === 1
          ? '1 questão inserida no tópico.'
          : `${count} questões inseridas no tópico.`)
          + ' Elas aparecem na navegação, depois das imagens. Para responder sem ver o gabarito, use a aba Responder.',
        variant: 'success',
      });
      await refreshData(true);
      setGeneratedQuestions(null);
      setShowGeneratedView(false);
      persistirQuestoes(null);
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao inserir as questões no tópico.',
        variant: 'danger',
      });
      console.error(err);
      throw err;
    }
  };

  const openArticlesWithQuery = (query, instrucoes) => {
    setArticleSearchQuery(typeof query === 'string' ? query : '');
    setArticleSearchInstrucoes(typeof instrucoes === 'string' ? instrucoes : '');
    setShowArticlesModal(true);
  };

  const descartarResultadosQuestoes = async () => {
    const ok = await confirm({
      title: 'Descartar questões',
      message: 'Jogar fora as questões restantes? Você pode gerar de novo.',
      confirmText: 'Descartar',
      variant: 'danger',
    });
    if (!ok) return;
    setGeneratedQuestions(null);
    setShowGeneratedView(false);
    persistirQuestoes(null);
  };

  const descartarResultadosFlashcards = async () => {
    const ok = await confirm({
      title: 'Descartar flashcards',
      message: 'Jogar fora este plano? Você pode gerar de novo.',
      confirmText: 'Descartar',
      variant: 'danger',
    });
    if (!ok) return;
    setGeneratedFlashcards(null);
    setShowFlashcardsView(false);
    persistirFlashcards(null);
  };

  const abrirGeradorQuestoes = () => {
    if (generatedQuestions && Array.isArray(generatedQuestions.questions) && generatedQuestions.questions.length > 0) {
      setShowGeneratedView(true);
    } else {
      setShowGeneratorModal(true);
    }
  };

  const abrirGeradorFlashcards = () => {
    if (generatedFlashcards && Array.isArray(generatedFlashcards.flashcards) && generatedFlashcards.flashcards.length > 0) {
      setShowFlashcardsView(true);
    } else {
      setShowFlashcardsModal(true);
    }
  };

  if (loading) return <CarregandoTela rotulo="Carregando o tópico..." />;

  const isEmptyTopic = images.length === 0;

  return (
    <div className="container">
      <Sidebar
        topicName={topicName}
        questions={questions}
        qIdx={qIdx}
        onQuestionChange={handleQuestionChange}
        collapsed={sidebarCollapsed}
        onOpenGenerator={abrirGeradorQuestoes}
        onOpenFlashcards={abrirGeradorFlashcards}
        onOpenSessions={() => setShowSessionsModal(true)}
        onOpenStrategy={() => setShowStrategyModal(true)}
        onOpenArticles={openArticlesWithQuery}
        onOpenUploadFiles={() => setShowUploadFilesModal(true)}
        onOpenUploadRAG={() => setShowUploadRAGModal(true)}
      />
      <main className="content">
        <div className="title-with-button">
          <button
            className="toggle-sidebar-btn"
            onClick={toggleSidebar}
            title={sidebarCollapsed ? 'Abrir painel de navegação' : 'Fechar painel de navegação'}
            aria-label="Alternar painel de navegação"
          >
            <IconeMenu size={20} />
          </button>
          <h1>{topicName.replace(/_/g, ' ')}</h1>
          <button className="rename-btn" onClick={() => { setRenameError(''); setNewTopicName(topicName.replace(/_/g, ' ')); setShowRenameModal(true); }} title="Renomear tópico">
            <img
              src={darkMode ? '/pen-dark.png' : '/pen-white.png'}
              alt="Renomear"
              className="rename-btn-icon whiteboard-pen-icon"
            />
          </button>
          <div className="title-right-actions">
            <TimerControl />
            <button
              className="theme-toggle-btn"
              onClick={toggleDarkMode}
              title={darkMode ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
              aria-label="Alternar tema"
            >
              {darkMode ? <IconeSol size={20} /> : <IconeLua size={20} />}
            </button>
          </div>
        </div>
        <hr />
        {!hasOllamaKey && (
          <div className="flash-warning" role="alert">
            <span>
              <strong>Chave da Ollama não cadastrada.</strong>{' '}
              Cadastre em Configurações para gerar questões, flashcards e estratégias.
            </span>
            <button
              type="button"
              className="button"
              onClick={() => setShowBannerConfig(true)}
            >
              Configurações
            </button>
          </div>
        )}
        {isEmptyTopic ? (
          <div className="topic-empty-state">
            <div className="topic-empty-card">
              <h2>Vamos começar</h2>
              <p>
                Adicione imagens de questões ou textos de apoio para este
                tópico. Com material aqui, as ferramentas de estudo passam a
                gerar questões, flashcards e um plano de revisão a partir do
                que você enviou.
              </p>
              <div className="topic-empty-actions">
                <button className="button" onClick={() => setShowUploadFilesModal(true)}>
                  Adicionar arquivos
                </button>
                <button className="button button-outline" onClick={() => setShowUploadRAGModal(true)}>
                  Adicionar material de apoio
                </button>
              </div>
              <div className="topic-empty-tools">
                <p className="topic-empty-tools-titulo">
                  Ferramentas de estudo deste tópico:
                </p>
                <div className="topic-empty-tools-grid">
                  <button className="topic-empty-tool" onClick={abrirGeradorQuestoes}>
                    <strong>Gerar questões</strong>
                    <span>Monte uma lista de exercícios sobre o tema, escolhendo os tipos de questão.</span>
                  </button>
                  <button className="topic-empty-tool" onClick={abrirGeradorFlashcards}>
                    <strong>Flashcards</strong>
                    <span>Crie cartões de revisão a partir do tema deste tópico.</span>
                  </button>
                  <button className="topic-empty-tool" onClick={() => setShowStrategyModal(true)}>
                    <strong>Estratégia de estudo</strong>
                    <span>Informe sua dedicação diária e receba um plano com cronograma e revisões.</span>
                  </button>
                  <button className="topic-empty-tool" onClick={openArticlesWithQuery}>
                    <strong>Pesquisar artigos</strong>
                    <span>Encontre referências acadêmicas para aprofundar o assunto.</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="two-columns" id="twoColumns">
            <div className="image-viewer-wrapper">
              <ImageViewer
                topicName={topicName}
                currentImage={currentImage}
                total={images.length}
                filtro={filtro}
                opcoesFiltro={opcoesFiltro}
                onFiltroChange={setFiltro}
                posicao={posicaoNoFiltro}
                totalVisivel={totalVisivel}
                podeAnterior={podeAnterior}
                podeProximo={podeProximo}
                onPrev={handlePrev}
                onNext={handleNext}
                onAddQuestion={() => setShowAddModal(true)}
                onImageDeleted={() => {
                  const newImages = images.filter((_, i) => i !== currentIdx);
                  setImages(newImages);
                  if (newImages.length === 0) {
                    navigate('/');
                  } else {
                    const newIdx = Math.min(currentIdx, newImages.length - 1);
                    setSearchParams({ idx: newIdx, q: 0 });
                  }
                }}
                onAnalysisComplete={refreshData}
                selectedModel={selectedModel}
                onModelChange={setSelectedModel}
                transcriptionMethod={transcriptionMethod}
                onTranscriptionMethodChange={setTranscriptionMethod}
                ocrModel={ocrModel}
                onOcrModelChange={setOcrModel}
                resolutions={resolutions}
              />
            </div>
            <div className="resolution-col">
              <h2>Conteúdo da resolução</h2>
              <div className="resolution-tabs">
                <button
                  className={`tab-button ${activeTab === 'texto' ? 'active' : ''}`}
                  onClick={() => setActiveTab('texto')}
                >
                  Texto
                </button>
                <button
                  className={`tab-button ${activeTab === 'whiteboard' ? 'active' : ''}`}
                  onClick={() => setActiveTab('whiteboard')}
                >
                  Quadro branco
                </button>
                <button
                  className={`tab-button ${activeTab === 'anotacoes' ? 'active' : ''}`}
                  onClick={() => setActiveTab('anotacoes')}
                >
                  Anotações
                </button>
                <button
                  className={`tab-button ${activeTab === 'responder' ? 'active' : ''}`}
                  onClick={() => setActiveTab('responder')}
                >
                  Responder
                </button>
              </div>
              <div className={`tab-content ${activeTab === 'texto' ? 'active' : ''}`} id="tab-texto">
                {currentQuestion ? (
                  <QuestionEditor
                    question={currentQuestion}
                    onSave={handleSaveQuestion}
                    onDelete={handleDeleteQuestion}
                    topicName={topicName}
                    imageFilename={currentImage}
                    qIdx={qIdx}
                    currentIdx={currentIdx}
                    selectedModel={selectedModel}
                  />
                ) : (
                  <div className="info-message">Nenhuma questão encontrada para esta imagem.</div>
                )}
              </div>
              <div className={`tab-content ${activeTab === 'whiteboard' ? 'active' : ''}`} id="tab-whiteboard">
                {currentImage ? (
                  <>
                    <Whiteboard
                      key={`${currentImage}-${currentQuestion ? qIdx : 'livre'}`}
                      chave={`${topicName}:${currentImage}:${currentQuestion ? `q${qIdx}` : 'livre'}`}
                      initialImage={whiteboardUrl}
                      onSave={handleSaveWhiteboard}
                      onAutoSave={handleAutoSaveWhiteboard}
                    />
                    {currentQuestion && currentQuestion.whiteboard_img && (
                      <div style={{ marginTop: '8px', textAlign: 'center' }}>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="info-message">Selecione uma imagem para usar o quadro branco.</div>
                )}
              </div>
              <div className={`tab-content ${activeTab === 'anotacoes' ? 'active' : ''}`} id="tab-anotacoes">
                {currentImage ? (
                  <AnnotationEditor
                    topicName={topicName}
                    imageFilename={currentImage}
                    onAnnotationSaved={refreshData}
                    transcriptionMethod={transcriptionMethod}
                    selectedModel={selectedModel}
                    ocrModel={ocrModel}
                  />
                ) : (
                  <div className="info-message">Selecione uma imagem para adicionar anotações.</div>
                )}
              </div>
              <div className={`tab-content ${activeTab === 'responder' ? 'active' : ''}`} id="tab-responder">
                {currentQuestion ? (
                  <ResponderQuestao
                    key={`${currentImage}-${qIdx}`}
                    questao={currentQuestion}
                    topic={topicName}
                    model={selectedModel}
                  />
                ) : (
                  <div className="info-message">Selecione uma questão na lista para responder.</div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {showAddModal && (
        <div className="modal modal-aberto" onClick={aoClicarFundoAdd} ref={refAddModal}>
          <div className="modal-content">
            <span className="close" onClick={() => setShowAddModal(false)}>&times;</span>
            <h2>Adicionar nova questão</h2>
            <form onSubmit={(e) => { e.preventDefault(); handleAddQuestion(); }}>
              <input type="hidden" name="image_filename" value={currentImage} />
              <input type="hidden" name="idx" value={currentIdx} />
              <div className="form-group">
                <label htmlFor="questao_num">Número da questão *</label>
                <input type="text" id="questao_num" className="form-control" value={newQuestion.questao_num}
                  onChange={(e) => setNewQuestion({ ...newQuestion, questao_num: e.target.value })} required />
              </div>
              <div className="form-group">
                <label htmlFor="tipo">Tipo (opcional)</label>
                <input type="text" id="tipo" className="form-control" placeholder="ex: objetiva, discursiva"
                  value={newQuestion.tipo} onChange={(e) => setNewQuestion({ ...newQuestion, tipo: e.target.value })} />
              </div>
              <div className="form-group">
                <label htmlFor="resposta">Resposta (Markdown/LaTeX) (opcional)</label>
                <textarea id="resposta" rows="4" className="form-control" value={newQuestion.resposta}
                  onChange={(e) => setNewQuestion({ ...newQuestion, resposta: e.target.value })}></textarea>
              </div>
              <div className="form-group">
                <label htmlFor="explicacao">Resolução (Markdown/LaTeX) (opcional)</label>
                <textarea id="explicacao" rows="6" className="form-control" value={newQuestion.explicacao}
                  onChange={(e) => setNewQuestion({ ...newQuestion, explicacao: e.target.value })}></textarea>
              </div>
              <button type="submit" className="save-button">Salvar questão</button>
            </form>
          </div>
        </div>
      )}

      {showRenameModal && (
        <div className="modal modal-aberto" onClick={aoClicarFundoRename} ref={refRenameModal}>
          <div className="modal-content">
            <span className="close" onClick={() => setShowRenameModal(false)}>&times;</span>
            <h2>Renomear tópico</h2>
            <form onSubmit={handleRename}>
              <div className="form-group">
                <label htmlFor="new_name">Novo nome:</label>
                <input type="text" id="new_name" className="form-control" value={newTopicName}
                  onChange={(e) => setNewTopicName(e.target.value)} required />
              </div>
              {renameError && <div className="flash-error">{renameError}</div>}
              <div className="form-actions">
                <button type="submit" className="save-button">Renomear</button>
              </div>
            </form>
          </div>
        </div>
      )}

      <QuestionGeneratorModal
        topic={topicName}
        isOpen={showGeneratorModal}
        onClose={() => setShowGeneratorModal(false)}
        onConcluido={(resultado) => {
          setGeneratedQuestions(resultado);
          persistirQuestoes(resultado);
          setShowGeneratedView(true);
        }}
      />

      <FlashcardGeneratorModal
        topic={topicName}
        isOpen={showFlashcardsModal}
        onClose={() => setShowFlashcardsModal(false)}
        onConcluido={(resultado) => {
          setGeneratedFlashcards(resultado);
          persistirFlashcards(resultado);
          setShowFlashcardsView(true);
        }}
      />

      {generatedQuestions && showGeneratedView && (
        <GeneratedQuestionsView
          topic={topicName}
          questions={generatedQuestions.questions}
          contexto={generatedQuestions.contexto || null}
          onClose={() => setShowGeneratedView(false)}
          onDescartar={descartarResultadosQuestoes}
          onSaved={() => {
            refreshData();
            setGeneratedQuestions(null);
            setShowGeneratedView(false);
            persistirQuestoes(null);
          }}
          onInsertQuestion={handleInsertGeneratedQuestion}
          onInsertAll={handleInsertAllGeneratedQuestions}
          onAdicionarTextos={() => setShowUploadRAGModal(true)}
          onPesquisarArtigos={(q, inst) => openArticlesWithQuery(typeof q === 'string' && q ? q : topicName, inst)}
          questoesDoTopico={resolutions}
        />
      )}

      {generatedFlashcards && showFlashcardsView && (
        <FlashcardsViewer
          topic={topicName}
          sessionData={generatedFlashcards}
          onClose={() => setShowFlashcardsView(false)}
          onDescartar={descartarResultadosFlashcards}
          onSaved={() => {
            refreshData();
            setGeneratedFlashcards(null);
            setShowFlashcardsView(false);
            persistirFlashcards(null);
          }}
          onAdicionarTextos={() => setShowUploadRAGModal(true)}
          onPesquisarArtigos={(q, inst) => openArticlesWithQuery(typeof q === 'string' && q ? q : topicName, inst)}
        />
      )}

      <SessionsViewer
        topicName={topicName}
        isOpen={showSessionsModal}
        onClose={() => setShowSessionsModal(false)}
        onInsertQuestion={handleInsertGeneratedQuestion}
        onInsertAll={handleInsertAllGeneratedQuestions}
        onEstrategiaRestaurada={setStrategyResult}
        questoesDoTopico={resolutions}
      />

      <StudyStrategyModal
        topicName={topicName}
        isOpen={showStrategyModal}
        onClose={() => { setShowStrategyModal(false); setStrategyResult(null); }}
        externalStrategy={strategyResult}
        onOpenArticles={openArticlesWithQuery}
        onAdicionarTextos={() => setShowUploadRAGModal(true)}
      />

      <ArticleSearchModal
        isOpen={showArticlesModal}
        onClose={() => setShowArticlesModal(false)}
        initialQuery={articleSearchQuery}
        topicName={topicName}
        instrucoes={articleSearchInstrucoes}
      />

      <UploadFilesModal
        topicName={topicName}
        isOpen={showUploadFilesModal}
        onClose={() => setShowUploadFilesModal(false)}
        onUploadSuccess={refreshData}
      />

      <UploadRAGModal
        topicName={topicName}
        isOpen={showUploadRAGModal}
        onClose={() => setShowUploadRAGModal(false)}
        onUploadSuccess={refreshData}
      />

      <ConfigModal
        isOpen={showBannerConfig}
        onClose={() => setShowBannerConfig(false)}
      />
    </div>
  );
}

export default React.memo(TopicView);