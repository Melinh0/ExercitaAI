import React, { useState, useEffect, useRef, useCallback } from 'react';
import { uploadRAG, getTaskStatus, listMaterialFiles, deleteFile } from '../services/api';
import { useConfirm } from '../contexts/ConfirmContext';
import { useTasks } from '../contexts/TaskContext';
import { useToast } from '../contexts/ToastContext';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { coletarImagensColadas, obterTextoPlano } from '../utils/areaTransferencia';

const ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'bmp'];

const RAG_FILE_EXTENSIONS = [
  'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'txt', 'docx', 'pptx',
  'json', 'md', 'markdown', 'ipynb', 'py', 'js', 'ts', 'jsx', 'tsx',
  'java', 'cpp', 'c', 'h', 'hpp', 'cs', 'go', 'rs', 'rb', 'php',
  'swift', 'kt', 'scala', 'r', 'm', 'sh', 'bash', 'ps1', 'sql',
  'html', 'css', 'scss', 'sass', 'less', 'xml', 'yaml', 'yml',
  'toml', 'ini', 'cfg', 'conf', 'vue', 'svelte', 'dart', 'lua',
  'pl', 'pm', 'tcl', 'vb', 'fs', 'fsx', 'ml', 'mli', 'ex', 'exs',
  'erl', 'hrl', 'jl', 'nim', 'cr', 'zig', 'tf', 'tfvars', 'bat',
  'cmd', 'psm1', 'psd1', 'asm', 's', 'pas', 'dpr', 'dpk', 'lpr',
  'pp', 'inc', 'bas', 'cls', 'frm', 'ctl', 'vbp', 'vbw',
  'dockerfile', 'makefile', 'gradle'
];

const RAG_ACCEPT = RAG_FILE_EXTENSIONS.map(e => '.' + e).join(',');

function UploadRAGModal({ topicName, isOpen, onClose, onUploadSuccess }) {
  const { confirm, alert } = useConfirm();
  const { isRunning } = useTasks();
  const { toast } = useToast();
  const ragIndexando = isRunning('upload_rag');
  const ragIndexandoAnteriorRef = useRef(ragIndexando);
  const [files, setFiles] = useState([]);
  const [materialFiles, setMaterialFiles] = useState([]);
  const [loadingMaterial, setLoadingMaterial] = useState(false);
  const [erroMaterial, setErroMaterial] = useState('');
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [pasteMessage, setPasteMessage] = useState('');
  const [textInput, setTextInput] = useState('');
  const [previewUrls, setPreviewUrls] = useState({});
  const [, setTaskId] = useState(null);
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState('');
  const [polling, setPolling] = useState(false);
  const fileInputRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen && !polling, onClose);

  const formatSize = (bytes) => {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  };

  const loadMaterialFiles = useCallback(async () => {
    if (!isOpen) return;
    setLoadingMaterial(true);
    setErroMaterial('');
    try {
      const res = await listMaterialFiles(topicName);
      if (!Array.isArray(res.data)) {
        throw new Error('Resposta invalida do servidor');
      }
      setMaterialFiles(res.data);
    } catch (err) {
      console.error('Erro ao listar material de apoio:', err);
      setErroMaterial('Não foi possível carregar a lista de material de apoio. Feche e abra o modal para tentar de novo.');
    } finally {
      setLoadingMaterial(false);
    }
  }, [isOpen, topicName]);

  useEffect(() => {
    loadMaterialFiles();
  }, [loadMaterialFiles]);

  useEffect(() => {
    if (ragIndexandoAnteriorRef.current && !ragIndexando && isOpen) {
      loadMaterialFiles();
    }
    ragIndexandoAnteriorRef.current = ragIndexando;
  }, [ragIndexando, isOpen, loadMaterialFiles]);

  const handleDeleteMaterial = async (filename) => {
    const ok = await confirm({
      title: 'Excluir material de apoio',
      message: `Excluir "${filename}"? O conteúdo indexado dele deixa de ser usado nas respostas.`,
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await deleteFile(topicName, filename);
      await loadMaterialFiles();
      if (onUploadSuccess) onUploadSuccess();
      await alert({
        title: 'Sucesso',
        message: 'Material excluído.',
        variant: 'success',
      });
    } catch (err) {
      console.error('Erro ao excluir material de apoio:', err);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      setFiles([]);
      setTextInput('');
      setError('');
      setSuccess(false);
      setPasteMessage('');
      setTaskId(null);
      setTaskProgress(0);
      setTaskMessage('');
      setPolling(false);
      setUploading(false);
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      Object.values(previewUrls).forEach(url => URL.revokeObjectURL(url));
      setPreviewUrls({});
    }
  }, [isOpen]);

  useEffect(() => {
    const newPreviewUrls = { ...previewUrls };
    files.forEach(file => {
      if (file.type && file.type.startsWith('image/')) {
        if (!newPreviewUrls[file.name]) {
          newPreviewUrls[file.name] = URL.createObjectURL(file);
        }
      }
    });
    Object.keys(newPreviewUrls).forEach(key => {
      if (!files.some(f => f.name === key)) {
        URL.revokeObjectURL(newPreviewUrls[key]);
        delete newPreviewUrls[key];
      }
    });
    setPreviewUrls(newPreviewUrls);
  }, [files]);

  useEffect(() => {
    const handlePaste = async (event) => {
      if (!isOpen) return;
      const itens = event.clipboardData?.items
        ? Array.from(event.clipboardData.items)
        : [];
      if (itens.some(item => item.type.startsWith('image/'))) {
        event.preventDefault();
      }

      const textContent = await obterTextoPlano(event.clipboardData);
      const { arquivos, encontrouImagem } = await coletarImagensColadas(
        event.clipboardData,
        ALLOWED_IMAGE_EXTENSIONS,
        { usarHtml: !textContent }
      );

      if (arquivos.length > 0) {
        setFiles(prev => [...prev, ...arquivos]);
        setTextInput('');
        setPasteMessage(
          arquivos.length === 1
            ? `Imagem "${arquivos[0].name}" colada com sucesso.`
            : `${arquivos.length} imagens coladas com sucesso.`
        );
        setTimeout(() => setPasteMessage(''), 3000);
        event.preventDefault();
        return;
      }

      if (encontrouImagem) {
        setError('Não foi possível processar a imagem colada.');
        setTimeout(() => setError(''), 3000);
        event.preventDefault();
        return;
      }

      if (textContent && textContent.trim()) {
        const timestamp = Date.now();
        const fileName = `paste_text_${timestamp}.txt`;
        const blob = new Blob([textContent], { type: 'text/plain' });
        const textFile = new File([blob], fileName, { type: 'text/plain' });
        setFiles(prev => [...prev, textFile]);
        setTextInput(textContent);
        setPasteMessage(`Texto colado (${textContent.length} caracteres) pronto para upload.`);
        setTimeout(() => setPasteMessage(''), 4000);
        event.preventDefault();
        return;
      }

      try {
        const clipboardText = await navigator.clipboard.readText();
        if (clipboardText && clipboardText.trim()) {
          const timestamp = Date.now();
          const fileName = `paste_text_${timestamp}.txt`;
          const blob = new Blob([clipboardText], { type: 'text/plain' });
          const textFile = new File([blob], fileName, { type: 'text/plain' });
          setFiles(prev => [...prev, textFile]);
          setTextInput(clipboardText);
          setPasteMessage(`Texto colado (${clipboardText.length} caracteres) pronto para upload.`);
          setTimeout(() => setPasteMessage(''), 4000);
          event.preventDefault();
        }
      } catch (err) {
      }
    };

    if (isOpen) {
      window.addEventListener('paste', handlePaste);
    }
    return () => {
      window.removeEventListener('paste', handlePaste);
    };
  }, [isOpen]);

  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files);
    if (selected.length === 0) return;

    const invalidFiles = selected.filter(f => {
      const ext = (f.name.split('.').pop() || '').toLowerCase();
      return f.type && f.type.startsWith('image/') && !ALLOWED_IMAGE_EXTENSIONS.includes(ext);
    });

    if (invalidFiles.length > 0) {
      setError('Somente imagens PNG, JPG, JPEG, GIF e BMP são aceitas.');
      setTimeout(() => setError(''), 3000);
      return;
    }

    setFiles(prev => [...prev, ...selected]);
    setTextInput('');
    setPasteMessage('');
    setError('');
  };

  const handleRemoveFile = (fileName) => {
    setFiles(prev => {
      const fileToRemove = prev.find(f => f.name === fileName);
      if (fileToRemove && previewUrls[fileName]) {
        URL.revokeObjectURL(previewUrls[fileName]);
      }
      return prev.filter(f => f.name !== fileName);
    });
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleTextInput = (e) => {
    const text = e.target.value;
    setTextInput(text);
    if (text.trim()) {
      const timestamp = Date.now();
      const fileName = `typed_text_${timestamp}.txt`;
      const blob = new Blob([text], { type: 'text/plain' });
      const textFile = new File([blob], fileName, { type: 'text/plain' });
      setFiles(prev => {
        const filtered = prev.filter(f => !f.name.startsWith('typed_text_'));
        return [...filtered, textFile];
      });
    } else {
      setFiles(prev => prev.filter(f => !f.name.startsWith('typed_text_')));
      setPasteMessage('');
    }
  };

  const startPolling = (taskId) => {
    setPolling(true);
    setTaskProgress(0);
    setTaskMessage('Iniciando...');
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await getTaskStatus(taskId);
        const task = res.data;
        setTaskProgress(task.progress || 0);
        setTaskMessage(task.message || '');
        if (task.status === 'completed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setPolling(false);
          setSuccess(true);
          setTaskProgress(100);
          setTaskMessage('Concluído!');
          toast({ titulo: 'Sucesso', message: 'Material indexado com sucesso!', variante: 'sucesso' });
          if (onUploadSuccess) onUploadSuccess();
          loadMaterialFiles();
          setTimeout(() => {
            setSuccess(false);
            setFiles([]);
            setTextInput('');
            setPasteMessage('');
            setTaskId(null);
            setTaskProgress(0);
            setTaskMessage('');
            Object.values(previewUrls).forEach(url => URL.revokeObjectURL(url));
            setPreviewUrls({});
            onClose();
          }, 2000);
        } else if (task.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setPolling(false);
          setError(task.error || 'Erro ao processar arquivos.');
        }
      } catch (err) {
        console.error('Erro ao consultar status da task:', err);
      }
    }, 1000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (files.length === 0 && !textInput.trim()) {
      setError('Selecione, cole ou digite um conteúdo.');
      return;
    }
    setUploading(true);
    setError('');
    setSuccess(false);

    const filesToUpload = [...files];
    if (textInput.trim()) {
      const timestamp = Date.now();
      const blob = new Blob([textInput], { type: 'text/plain' });
      const textFile = new File([blob], `typed_text_${timestamp}.txt`, { type: 'text/plain' });
      filesToUpload.push(textFile);
    }

    try {
      const res = await uploadRAG(topicName, filesToUpload);
      if (res.data.success && res.data.task_id) {
        setTaskId(res.data.task_id);
        setTaskProgress(0);
        setTaskMessage('Iniciando...');
        setUploading(false);
        startPolling(res.data.task_id);
      } else {
        setError(res.data.error || 'Erro ao iniciar upload.');
        setUploading(false);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao enviar arquivo(s).');
      setUploading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '640px' }}>
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Adicionar material de apoio</h2>
        {error && <div className="flash-error">{error}</div>}
        {pasteMessage && <div className="flash-success">{pasteMessage}</div>}
        {success && (
          <div className="flash-success">
            Arquivos indexados com sucesso!
          </div>
        )}
        {polling && (
          <div className="rag-progress-bar" style={{ marginBottom: '1rem' }}>
            <div className="rag-progress-track">
              <div className="rag-progress-fill" style={{ width: `${taskProgress}%` }}></div>
            </div>
            <span className="rag-progress-text">{taskProgress}%</span>
          </div>
        )}
        {polling && taskMessage && (
          <p className="hint-text" style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
            {taskMessage}
          </p>
        )}
        <form onSubmit={handleSubmit} encType="multipart/form-data" className="edit-form">
          <div className="form-group">
            <label htmlFor="file">Arquivos (PDF, imagens, TXT, DOCX, JSON, MD, código):</label>
            <input
              type="file"
              id="file"
              name="file"
              accept={RAG_ACCEPT}
              className="form-control"
              onChange={handleFileChange}
              disabled={uploading || polling}
              ref={fileInputRef}
              multiple
            />
            <small>Vários arquivos por envio, ou cole o texto direto no campo abaixo.</small>
          </div>

          <div className="form-group">
            <label htmlFor="textInput">Texto livre:</label>
            <textarea
              id="textInput"
              className="form-control"
              rows="6"
              value={textInput}
              onChange={handleTextInput}
              placeholder="Conteúdo para indexar..."
              disabled={uploading || polling}
            />
            {textInput && (
              <div className="hint-text" style={{ marginTop: '0.5rem' }}>
                {textInput.length} caracteres digitados.
              </div>
            )}
          </div>

          {files.length > 0 && (
            <div className="upload-file-preview">
              <div className="upload-file-preview-header">
                <strong>Arquivos selecionados ({files.length}):</strong>
              </div>
              <div className="upload-file-list">
                {files.map((f, idx) => (
                  <div key={`${f.name}-${idx}`} className="upload-file-item">
                    <span className="upload-file-name">{f.name} <span className="hint-text">({Math.round(f.size / 1024)} KB)</span></span>
                    <button
                      type="button"
                      className="upload-file-remove-btn"
                      onClick={() => handleRemoveFile(f.name)}
                      disabled={uploading || polling}
                      title="Remover arquivo"
                      aria-label={`Remover ${f.name}`}
                    >
                      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true" focusable="false">
                        <path d="M6 6l12 12M18 6L6 18" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="upload-paste-hint">
            <p className="upload-paste-hint-title">
              Ctrl+V (Cmd+V) para colar imagem ou texto
            </p>
          </div>

          <div className="form-actions" style={{ marginTop: '1.5rem' }}>
            <button type="submit" className="save-button" disabled={uploading || polling || (files.length === 0 && !textInput.trim())}>
              {uploading ? 'Enviando...' : polling ? 'Processando...' : 'Enviar e indexar'}
            </button>
          </div>
        </form>

        <div style={{ marginTop: '1.5rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
          <h3 style={{ margin: 0 }}>Material de apoio enviado</h3>
          {ragIndexando ? (
            <p className="hint-text" style={{ margin: '0.5rem 0 0' }}>
              Indexando... o material aparece aqui quando a tarefa concluir.
            </p>
          ) : (
            <>
              {materialFiles.length > 0 && (
                <p className="hint-text" style={{ margin: '0.15rem 0 0.5rem' }}>
                  {materialFiles.length} arquivo(s) já enviado(s) a este tópico, indexado(s) para a IA consultar.
                </p>
              )}
              {erroMaterial ? (
                <p className="flash-error">{erroMaterial}</p>
              ) : loadingMaterial ? (
                <span className="carregando-linha">
                  <span className="carregando-girar" aria-hidden="true" />
                  Carregando material...
                </span>
              ) : materialFiles.length === 0 ? (
                <p className="hint-text">Nenhum material de apoio enviado ainda.</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {materialFiles.map((file) => (
                    <li
                      key={file.name}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid #e2e8f0',
                        flexWrap: 'wrap',
                      }}
                    >
                      <span style={{ wordBreak: 'break-all', flex: 1 }}>
                        <strong>{file.name}</strong>
                        <span className="hint-text" style={{ marginLeft: '0.5rem' }}>
                          ({formatSize(file.size)})
                        </span>
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteMaterial(file.name)}
                        className="upload-file-remove-btn"
                        style={{ marginLeft: '0.5rem' }}
                      >
                        Excluir
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  );
}

export default UploadRAGModal;