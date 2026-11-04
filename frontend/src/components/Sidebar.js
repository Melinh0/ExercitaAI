import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useConfirm } from '../contexts/ConfirmContext';
import { useTasks } from '../contexts/TaskContext';
import {
  getDownloadAllImagesUrl,
  getDownloadTextResolutionsUrl,
  getDownloadWhiteboardsUrl,
} from '../services/api';
import EmptyDownloadModal from './EmptyDownloadModal';
import { IconeChevronBaixo, IconeSpinner } from './Icons';

function Sidebar({
  topicName,
  questions,
  qIdx,
  onQuestionChange,
  collapsed,
  onOpenGenerator,
  onOpenSessions,
  onOpenFlashcards,
  onOpenStrategy,
  onOpenArticles,
  onOpenUploadFiles,
  onOpenUploadRAG
}) {
  const safeQuestions = Array.isArray(questions) ? questions : [];
  const { isRunning } = useTasks();
  const [emptyModalOpen, setEmptyModalOpen] = useState(false);
  const [emptyModalType, setEmptyModalType] = useState('images');
  const [checkingDownload, setCheckingDownload] = useState(false);
  const [exportarAberto, setExportarAberto] = useState(false);
  const [ajudaMaterial, setAjudaMaterial] = useState(false);
  const { alert } = useConfirm();

  const genQRunning = isRunning('generate_questions');
  const genFRunning = isRunning('generate_flashcards');
  const stratRunning = isRunning('study_strategy');
  const artRunning = isRunning('search_articles');
  const upFilesRunning = isRunning('upload_images') || isRunning('upload_documento');
  const upRagRunning = isRunning('upload_rag');

  const handleDownload = async (type) => {
    if (checkingDownload) return;
    setCheckingDownload(true);
    const url =
      type === 'images' ? getDownloadAllImagesUrl(topicName) :
      type === 'whiteboards' ? getDownloadWhiteboardsUrl(topicName) :
      getDownloadTextResolutionsUrl(topicName);
    try {
      const res = await fetch(url, { credentials: 'same-origin' });
      if (res.redirected && res.url.includes('/auth/login')) {
        await alert({
          title: 'Sessão expirada',
          message: 'Faça login novamente para baixar os arquivos.',
          variant: 'warning',
        });
        return;
      }
      const contentType = (res.headers.get('content-type') || '').toLowerCase();
      if (!res.ok || contentType.includes('text/html')) {
        setEmptyModalType(type);
        setEmptyModalOpen(true);
        return;
      }
      const disposition = res.headers.get('content-disposition') || '';
      const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)/i);
      const filename = match
        ? decodeURIComponent(match[1].replace(/["']/g, ''))
        : `${topicName}_download`;
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error('Erro ao baixar:', err);
      await alert({
        title: 'Erro no download',
        message: 'Não foi possível baixar os arquivos. Verifique sua conexão e tente novamente.',
        variant: 'danger',
      });
    } finally {
      setCheckingDownload(false);
    }
  };

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`} id="sidebar">
      <Link to="/" className="button">Todos os tópicos</Link>

      <div className="sidebar-secao">
        <p className="sidebar-secao-titulo">
          Material
          <button
            type="button"
            className="sidebar-secao-ajuda"
            onClick={() => setAjudaMaterial(true)}
            title="Qual a diferença entre as duas opções?"
            aria-label="Qual a diferença entre as duas opções?"
          >
            ?
          </button>
        </p>
        <button onClick={onOpenUploadFiles} className="button button-outline">
          {upFilesRunning && <IconeSpinner size={16} className="spinner-girando" style={{ marginRight: '0.4rem' }} />}
          Adicionar arquivos
        </button>
        <button onClick={onOpenUploadRAG} className="button button-outline">
          {upRagRunning && <IconeSpinner size={16} className="spinner-girando" style={{ marginRight: '0.4rem' }} />}
          Adicionar material de apoio
        </button>
      </div>

      <div className="sidebar-secao">
        <p className="sidebar-secao-titulo">Estudo</p>
        <button onClick={onOpenGenerator} className="button">
          {genQRunning && <IconeSpinner size={16} className="spinner-girando" style={{ marginRight: '0.4rem' }} />}
          Gerar questões
        </button>
        <button onClick={onOpenFlashcards} className="button">
          {genFRunning && <IconeSpinner size={16} className="spinner-girando" style={{ marginRight: '0.4rem' }} />}
          Flashcards
        </button>
        <button onClick={onOpenStrategy} className="button">
          {stratRunning && <IconeSpinner size={16} className="spinner-girando" style={{ marginRight: '0.4rem' }} />}
          Estratégia de estudo
        </button>
        <button onClick={onOpenArticles} className="button">
          {artRunning && <IconeSpinner size={16} className="spinner-girando" style={{ marginRight: '0.4rem' }} />}
          Pesquisar artigos
        </button>
      </div>

      <div className="sidebar-secao">
        <p className="sidebar-secao-titulo">Sessões</p>
        <button onClick={onOpenSessions} className="button">
          Histórico
        </button>
      </div>

      <div className="sidebar-secao">
        <button
          type="button"
          className={`sidebar-expansivel ${exportarAberto ? 'sidebar-expansivel-aberto' : ''}`}
          onClick={() => setExportarAberto((aberto) => !aberto)}
          aria-expanded={exportarAberto}
        >
          Exportar
          <IconeChevronBaixo size={16} />
        </button>
        {exportarAberto && (
          <>
            <button onClick={() => handleDownload('images')} className="button button-secundario" disabled={checkingDownload}>
              Baixar imagens
            </button>
            <button onClick={() => handleDownload('resolutions')} className="button button-secundario" disabled={checkingDownload}>
              Baixar resoluções (texto)
            </button>
            <button onClick={() => handleDownload('whiteboards')} className="button button-secundario" disabled={checkingDownload}>
              Baixar quadros brancos
            </button>
          </>
        )}
      </div>

      {safeQuestions.length > 0 && (
        <div className="question-selector">
          <label htmlFor="questao-select">Questão:</label>
          <select
            id="questao-select"
            value={qIdx}
            onChange={(e) => onQuestionChange(parseInt(e.target.value))}
          >
            {safeQuestions.map((q, idx) => (
              <option key={idx} value={idx}>Questão {q.questao || 'S/N'}</option>
            ))}
          </select>
        </div>
      )}

      <p className="dica">Anotações ficam salvas por questão.</p>

      {ajudaMaterial && (
        <div className="modal modal-aberto" onClick={() => setAjudaMaterial(false)}>
          <div className="modal-content" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0 }}>Material do tópico</h2>
              <span className="close" style={{ float: 'none', fontSize: '24px', lineHeight: 1 }} onClick={() => setAjudaMaterial(false)}>&times;</span>
            </div>
            <p className="hint-text" style={{ marginBottom: '0.75rem' }}>
              <strong>Adicionar arquivos:</strong> vira as páginas do tópico. É nelas que você
              responde, anota e usa o quadro branco.
            </p>
            <p className="hint-text" style={{ marginBottom: '0.75rem' }}>
              <strong>Adicionar material de apoio:</strong> fica só como consulta da IA nas
              respostas. Não vira página do tópico.
            </p>
            <p className="hint-text">
              Cada modal tem a própria lista de arquivos no rodapé.
            </p>
          </div>
        </div>
      )}

      <EmptyDownloadModal
        isOpen={emptyModalOpen}
        onClose={() => setEmptyModalOpen(false)}
        type={emptyModalType}
        topicName={topicName}
      />
    </aside>
  );
}

export default Sidebar;