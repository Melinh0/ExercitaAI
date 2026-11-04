import React, { useState, useEffect, useRef } from 'react';
import {
  getDownloadImageUrl,
  deleteImage,
  getModels,
  getTopicImageUrl,
} from '../services/api';
import { useTasks } from '../contexts/TaskContext';
import { useConfirm } from '../contexts/ConfirmContext';
import { useAuth } from '../contexts/AuthContext';
import usePollingTask from '../hooks/usePollingTask';
import MarkdownRenderer from './MarkdownContent';
import ModelInfoModal from './ModelInfoModal';
import OCRInfoModal from './OCRInfoModal';
import VisionInfoModal from './VisionInfoModal';
import { IconeSetaEsquerda, IconeSetaDireita } from './Icons';

const MIN_ZOOM = 25;
const MAX_ZOOM = 400;
const ZOOM_STEP = 25;

function ImageViewer({
  topicName,
  currentImage,
  total,
  filtro,
  opcoesFiltro,
  onFiltroChange,
  posicao,
  totalVisivel,
  podeAnterior,
  podeProximo,
  onPrev,
  onNext,
  onAddQuestion,
  onImageDeleted,
  onAnalysisComplete,
  selectedModel,
  onModelChange,
  transcriptionMethod,
  onTranscriptionMethodChange,
  ocrModel,
  onOcrModelChange,
  resolutions
}) {
  const { startTask, isRunning } = useTasks();
  const { acompanhar } = usePollingTask();
  const { confirm, alert } = useConfirm();
  const { versaoChaves } = useAuth();
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzingFull, setAnalyzingFull] = useState(false);
  const paginaEmAndamento = analyzing || isRunning('analyze_with_image');
  const documentoEmAndamento = analyzingFull || isRunning('analyze_full_document');
  const analiseBloqueada = paginaEmAndamento || documentoEmAndamento;
  const [models, setModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [visionModels, setVisionModels] = useState([]);
  const [loadingVision, setLoadingVision] = useState(false);
  const [extraPrompt, setExtraPrompt] = useState('');
  const [showExtraPrompt, setShowExtraPrompt] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [dismissedSuggestions, setDismissedSuggestions] = useState(false);
  const [showModelInfo, setShowModelInfo] = useState(false);
  const [showOCRInfo, setShowOCRInfo] = useState(false);
  const [showVisionInfo, setShowVisionInfo] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  useEffect(() => {
    setZoom(100);
    setPan({ x: 0, y: 0 });
    setIsDragging(false);
  }, [currentImage]);

  useEffect(() => {
    async function fetchModels() {
      setLoadingModels(true);
      try {
        const res = await getModels();
        const modelList = Array.isArray(res.data) ? res.data : [];
        setModels(modelList);
        if (modelList.length > 0 && !selectedModel) onModelChange(modelList[0]);
      } catch (err) {
        console.error('Erro ao carregar modelos', err);
        const fallback = ['llama3.2', 'gemma3:4b', 'mistral'];
        setModels(fallback);
        if (!selectedModel) onModelChange(fallback[0]);
      } finally {
        setLoadingModels(false);
      }
    }
    fetchModels();
  }, [selectedModel, onModelChange, versaoChaves]);

  useEffect(() => {
    if (transcriptionMethod !== 'llm' || visionModels.length > 0) return;
    let ativo = true;
    setLoadingVision(true);
    (async () => {
      try {
        const res = await getModels(true);
        const lista = Array.isArray(res.data) ? res.data : [];
        if (ativo) setVisionModels(lista);
      } catch (err) {
        console.error('Erro ao carregar modelos de visão', err);
        if (ativo) setVisionModels([]);
      } finally {
        if (ativo) setLoadingVision(false);
      }
    })();
    return () => {
      ativo = false;
      setLoadingVision(false);
    };
  }, [transcriptionMethod, visionModels.length, versaoChaves]);

  useEffect(() => {
    if (transcriptionMethod !== 'llm' || visionModels.length === 0) return;
    if (ocrModel && visionModels.includes(ocrModel)) return;
    onOcrModelChange(visionModels.includes(selectedModel) ? selectedModel : visionModels[0]);
  }, [transcriptionMethod, visionModels, ocrModel, selectedModel, onOcrModelChange]);

  const fetchSuggestions = async () => {
    if (loadingSuggestions || dismissedSuggestions) return;
    if (showSuggestions && suggestions.length > 0) return;
    setLoadingSuggestions(true);
    try {
      const response = await fetch('/suggest_prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'analyze_image',
          topic: topicName,
          model: selectedModel
        })
      });
      const data = await response.json();
      if (data.success) {
        setSuggestions(data.suggestions || []);
        setShowSuggestions(true);
      }
    } catch (err) {
      console.error('Erro ao buscar sugestões:', err);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handleClickExtraPrompt = () => {
    if (dismissedSuggestions) return;
    fetchSuggestions();
  };

  const handleCloseSuggestions = () => {
    setShowSuggestions(false);
    setDismissedSuggestions(true);
  };

  const handleReopenSuggestions = () => {
    setDismissedSuggestions(false);
    setSuggestions([]);
    fetchSuggestions();
  };

  const applySuggestion = (suggestion) => {
    setExtraPrompt(suggestion);
    setShowSuggestions(false);
    setDismissedSuggestions(true);
  };

  const handleDelete = async () => {
    const confirmed = await confirm({
      title: 'Excluir imagem',
      message: 'Tem certeza que deseja deletar esta imagem? Essa ação não pode ser desfeita.',
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await deleteImage(topicName, currentImage);
      await alert({
        title: 'Sucesso',
        message: 'Imagem deletada com sucesso!',
        variant: 'success',
      });
      onImageDeleted();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao deletar imagem.',
        variant: 'danger',
      });
    }
  };

  const garanteModeloVisao = async () => {
    if (transcriptionMethod !== 'llm') return true;
    if (ocrModel && visionModels.includes(ocrModel)) return true;
    await alert({
      title: 'Aviso',
      message: visionModels.length === 0
        ? 'Nenhum modelo com visão disponível para o OCR via LLM. Cadastre uma chave de API com modelos multimodais ou escolha outro método de transcrição.'
        : 'Selecione um modelo de visão para o OCR via LLM.',
      variant: 'warning',
    });
    return false;
  };

  const handleAnalyze = async () => {
    if (!selectedModel) {
      await alert({
        title: 'Aviso',
        message: 'Selecione um modelo antes de analisar.',
        variant: 'warning',
      });
      return;
    }
    if (!(await garanteModeloVisao())) return;
    setAnalyzing(true);
    try {
      const idAnalise = await startTask('analyze_with_image', {
        topic: topicName,
        image_filename: currentImage,
        model: selectedModel,
        extra_prompt: extraPrompt,
        transcription_method: transcriptionMethod,
        ocr_model: transcriptionMethod === 'llm' ? ocrModel : undefined,
      });
      acompanhar(idAnalise, () => {
        if (onAnalysisComplete) onAnalysisComplete();
      });
      setExtraPrompt('');
      setShowSuggestions(false);
      setDismissedSuggestions(false);
    } catch (err) {
      console.error('Erro na requisição:', err);
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar análise: ' + (err.message || err),
        variant: 'danger',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAnalyzeFullDocument = async () => {
    if (!selectedModel) {
      await alert({
        title: 'Aviso',
        message: 'Selecione um modelo antes de analisar.',
        variant: 'warning',
      });
      return;
    }
    if (!(await garanteModeloVisao())) return;
    setAnalyzingFull(true);
    try {
      const idDocumento = await startTask('analyze_full_document', {
        topic: topicName,
        model: selectedModel,
        extra_prompt: extraPrompt,
        transcription_method: transcriptionMethod,
        ocr_model: transcriptionMethod === 'llm' ? ocrModel : undefined,
      });
      acompanhar(idDocumento, (resultado) => {
        if (onAnalysisComplete) onAnalysisComplete();
        const r = resultado || {};
        const falhas = Array.isArray(r.failed_pages) ? r.failed_pages : [];
        if (falhas.length > 0) {
          const total = r.pages_total || r.pages_processed || 0;
          const processadas = r.pages_processed || 0;
          const count = r.count || 0;
          const listagem = falhas.slice(0, 15).join('\n');
          const sufixo = falhas.length > 15 ? `\n... e mais ${falhas.length - 15}` : '';
          alert({
            title: 'Análise concluída com avisos',
            message: `Páginas processadas: ${processadas}/${total}\nQuestões extraídas: ${count}\n\nPáginas com falha (${falhas.length}):\n${listagem}${sufixo}\n\nVocê pode rodar a análise novamente apenas para essas páginas.`,
            variant: 'warning',
          });
        }
      });
      setExtraPrompt('');
      setShowSuggestions(false);
      setDismissedSuggestions(false);
    } catch (err) {
      console.error('Erro na requisição:', err);
      await alert({
        title: 'Erro',
        message: 'Erro ao iniciar análise: ' + (err.message || err),
        variant: 'danger',
      });
    } finally {
      setAnalyzingFull(false);
    }
  };

  const handleZoomIn = () => setZoom(prev => Math.min(MAX_ZOOM, prev + ZOOM_STEP));

  const handleZoomOut = () => {
    const next = Math.max(MIN_ZOOM, zoom - ZOOM_STEP);
    setZoom(next);
    if (next <= 100) setPan({ x: 0, y: 0 });
  };

  const handleZoomReset = () => {
    setZoom(100);
    setPan({ x: 0, y: 0 });
  };

  const isPannable = zoom > 100;

  const startDrag = (clientX, clientY) => {
    if (!isPannable) return;
    setIsDragging(true);
    dragStartRef.current = {
      x: clientX,
      y: clientY,
      panX: pan.x,
      panY: pan.y
    };
  };

  const moveDrag = (clientX, clientY) => {
    if (!isDragging) return;
    const dx = clientX - dragStartRef.current.x;
    const dy = clientY - dragStartRef.current.y;
    setPan({
      x: dragStartRef.current.panX + dx,
      y: dragStartRef.current.panY + dy
    });
  };

  const endDrag = () => {
    if (isDragging) setIsDragging(false);
  };

  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    startDrag(e.clientX, e.clientY);
  };
  const handleMouseMove = (e) => moveDrag(e.clientX, e.clientY);
  const handleMouseUp = () => endDrag();

  const handleTouchStart = (e) => {
    if (e.touches.length !== 1) return;
    const t = e.touches[0];
    startDrag(t.clientX, t.clientY);
  };
  const handleTouchMove = (e) => {
    if (!isDragging || e.touches.length !== 1) return;
    const t = e.touches[0];
    moveDrag(t.clientX, t.clientY);
    e.preventDefault();
  };
  const handleTouchEnd = () => endDrag();

  const imageStyle = {
    maxWidth: '100%',
    maxHeight: '100%',
    width: 'auto',
    height: 'auto',
    objectFit: 'contain',
    transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})`,
    transformOrigin: 'center center',
    transition: isDragging ? 'none' : 'transform 0.15s ease-out',
    userSelect: 'none',
    pointerEvents: 'none',
    willChange: 'transform',
    borderRadius: '10px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
    backgroundColor: 'white',
    padding: '4px',
  };

  const currentRes = resolutions ? resolutions.find(r => r.imagem === currentImage) : null;
  const isTextQuestion = currentRes && currentRes.is_text_question === true;
  const questionText = isTextQuestion ? (currentRes.texto || '') : '';

  const modelNames = Array.isArray(models)
    ? models.map(m => (typeof m === 'string' ? m : m.name))
    : [];

  return (
    <div className="image-col">
      {currentImage ? (
        <>
          {opcoesFiltro && opcoesFiltro.totalGrupos >= 2 && (
            <div className="image-filter-row">
              <label htmlFor="filtro-carrossel">Filtro</label>
              <select
                id="filtro-carrossel"
                className="image-filter-select"
                value={filtro}
                onChange={(e) => onFiltroChange(e.target.value)}
              >
                <option value="tudo">Tudo ({total})</option>
                {opcoesFiltro.arquivos.length > 0 && (
                  <optgroup label="Arquivos enviados">
                    {opcoesFiltro.arquivos.map(op => (
                      <option key={op.chave} value={`arquivo:${op.chave}`}>
                        {op.rotulo} ({op.total})
                      </option>
                    ))}
                  </optgroup>
                )}
                {(opcoesFiltro.nGerador > 0 || opcoesFiltro.nManual > 0) && (
                  <optgroup label="Questões em texto">
                    {opcoesFiltro.nGerador > 0 && (
                      <option value="gerador">Automáticas ({opcoesFiltro.nGerador})</option>
                    )}
                    {opcoesFiltro.nManual > 0 && (
                      <option value="manual">Manuais ({opcoesFiltro.nManual})</option>
                    )}
                  </optgroup>
                )}
              </select>
            </div>
          )}

          <div className="image-nav-controls">
            <button onClick={onPrev} className="nav-btn" disabled={!podeAnterior}><IconeSetaEsquerda size={14} /></button>
            <span className="image-counter">{posicao} / {totalVisivel}</span>
            <button onClick={onNext} className="nav-btn" disabled={!podeProximo}><IconeSetaDireita size={14} /></button>
          </div>

          <div
            className={`image-frame ${isPannable ? 'is-pannable' : ''} ${isDragging ? 'is-panning' : ''}`}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            {isTextQuestion ? (
              <div className="text-question-container">
                <MarkdownRenderer content={questionText} />
              </div>
            ) : (
              <img
                src={getTopicImageUrl(topicName, currentImage)}
                alt="Questão"
                className="question-image"
                draggable={false}
                style={imageStyle}
              />
            )}
          </div>

          {!isTextQuestion && (
            <div className="zoom-controls">
              <button onClick={handleZoomOut} disabled={zoom <= MIN_ZOOM} title="Diminuir zoom">−</button>
              <span className="zoom-value">{zoom}%</span>
              <button onClick={handleZoomIn} disabled={zoom >= MAX_ZOOM} title="Aumentar zoom">+</button>
              <button className="zoom-reset-btn" onClick={handleZoomReset} title="Redefinir zoom e posição">Redefinir</button>
            </div>
          )}

          <p className="caption">Arquivo atual: {currentImage}</p>

          <div className="image-actions">
            {!isTextQuestion && (
              <a
                href={getDownloadImageUrl(topicName, currentImage)}
                className="button"
                target="_blank"
                rel="noopener noreferrer"
              >
                Download
              </a>
            )}
            <button className="button" onClick={onAddQuestion}>Adicionar Questão</button>
            <button className="delete-button" onClick={handleDelete}>Excluir</button>
          </div>

          <div className="analysis-toolbar">
            <div className="analysis-toolbar-row">
              <div className="model-select-row">
                <select
                  value={selectedModel}
                  onChange={(e) => onModelChange(e.target.value)}
                  disabled={loadingModels}
                  className="analysis-select"
                >
                  {Array.isArray(models) && models.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="model-info-btn"
                  onClick={() => setShowModelInfo(true)}
                  title="Saber mais sobre os modelos de IA"
                >
                  ?
                </button>
              </div>
              <div className="model-select-row">
                <select
                  value={transcriptionMethod}
                  onChange={(e) => onTranscriptionMethodChange(e.target.value)}
                  className="analysis-select"
                >
                  <option value="tesseract">Tesseract (padrão)</option>
                  <option value="llm">Via LLM</option>
                  <option value="ocrspace">OCR.space</option>
                </select>
                <button
                  type="button"
                  className="model-info-btn"
                  onClick={() => setShowOCRInfo(true)}
                  title="Saber mais sobre os métodos de OCR"
                >
                  ?
                </button>
              </div>
            </div>

            {transcriptionMethod === 'llm' && (
              <div className="analysis-toolbar-row">
                <div className="model-select-row">
                  <select
                    value={visionModels.includes(ocrModel) ? ocrModel : ''}
                    onChange={(e) => onOcrModelChange(e.target.value)}
                    disabled={loadingVision}
                    className="analysis-select"
                  >
                    <option value="" disabled>
                      {loadingVision
                        ? 'Carregando modelos de visão…'
                        : visionModels.length === 0
                          ? 'Nenhum modelo de visão disponível'
                          : 'Modelo de visão para o OCR…'}
                    </option>
                    {visionModels.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="model-info-btn"
                    onClick={() => setShowVisionInfo(true)}
                    title="Saber mais sobre os modelos com visão"
                  >
                    ?
                  </button>
                </div>
              </div>
            )}

            <div className="analysis-toolbar-row analysis-extra-toggle-row">
              <button
                type="button"
                className="link-toggle-btn"
                onClick={() => setShowExtraPrompt(!showExtraPrompt)}
              >
                {showExtraPrompt ? 'Ocultar instruções' : 'Instruções adicionais'}
              </button>
            </div>

            {showExtraPrompt && (
              <>
                <textarea
                  className="form-control analysis-extra-prompt"
                  rows="2"
                  value={extraPrompt}
                  onChange={(e) => setExtraPrompt(e.target.value)}
                  onClick={handleClickExtraPrompt}
                  placeholder="Ex: corrija erros de OCR, preste atenção em fórmulas matemáticas..."
                />
                {loadingSuggestions && (
                  <span className="hint-text">Carregando sugestões...</span>
                )}
                {showSuggestions && suggestions.length > 0 && (
                  <div className="suggestions-container">
                    <p>Sugestões de prompts:</p>
                    <ul>
                      {suggestions.map((suggestion, idx) => (
                        <li key={idx}>
                          <button
                            type="button"
                            onClick={() => applySuggestion(suggestion)}
                            className="suggestion-button"
                          >
                            {suggestion}
                          </button>
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      onClick={handleCloseSuggestions}
                      className="suggestion-close-btn"
                    >
                      Fechar sugestões
                    </button>
                  </div>
                )}
                {!showSuggestions && dismissedSuggestions && (
                  <button
                    type="button"
                    onClick={handleReopenSuggestions}
                    className="reopen-suggestions-btn"
                  >
                    Mostrar sugestões de prompts
                  </button>
                )}
              </>
            )}

            <div className="analysis-toolbar-row analysis-buttons-grid">
              <button
                className="button"
                onClick={handleAnalyze}
                disabled={analiseBloqueada || loadingModels}
              >
                {paginaEmAndamento ? 'Analisando...' : 'Analisar página'}
              </button>
              <button
                className="button button-outline"
                onClick={handleAnalyzeFullDocument}
                disabled={analiseBloqueada || loadingModels}
              >
                {documentoEmAndamento ? 'Analisando documento...' : 'Analisar Documento Completo'}
              </button>
            </div>
          </div>
        </>
      ) : (
        <p>Nenhuma imagem disponível neste tópico.</p>
      )}

      <ModelInfoModal
        isOpen={showModelInfo}
        onClose={() => setShowModelInfo(false)}
        selectedModel={selectedModel}
        availableModels={modelNames}
      />
      <OCRInfoModal
        isOpen={showOCRInfo}
        onClose={() => setShowOCRInfo(false)}
        selectedOCR={transcriptionMethod}
      />
      <VisionInfoModal
        isOpen={showVisionInfo}
        onClose={() => setShowVisionInfo(false)}
        visionModels={visionModels}
        ocrModel={ocrModel}
        loading={loadingVision}
      />
    </div>
  );
}

export default React.memo(ImageViewer);