import React, { useState, useEffect, useRef } from 'react';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import { uploadPDF, uploadImages, listFiles, deleteFile } from '../services/api';
import { useConfirm } from '../contexts/ConfirmContext';
import { useTasks } from '../contexts/TaskContext';
import { useToast } from '../contexts/ToastContext';
import usePollingTask from '../hooks/usePollingTask';
import { coletarImagensColadas } from '../utils/areaTransferencia';

const ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg'];
const ALLOWED_OFFICE_EXTENSIONS = ['pptx', 'ppt', 'docx', 'doc'];
const MAX_FILES_PER_UPLOAD = 100;

const ehDocumento = (file) => {
  const nome = file.name.toLowerCase();
  if (nome.endsWith('.pdf')) return true;
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  return ALLOWED_OFFICE_EXTENSIONS.includes(ext);
};

function FilePreview({ file, onRemove, formatSize }) {
  const [url, setUrl] = useState(null);
  const isImage = file.type && file.type.startsWith('image/');

  useEffect(() => {
    if (isImage) {
      const objectUrl = URL.createObjectURL(file);
      setUrl(objectUrl);
      return () => URL.revokeObjectURL(objectUrl);
    }
  }, [file, isImage]);

  return (
    <div className="upload-file-preview">
      <div className="upload-file-preview-header">
        <strong>{file.name}</strong>
        <button type="button" className="upload-file-remove-btn" onClick={onRemove}>
          Remover
        </button>
      </div>
      {isImage && url ? (
        <img src={url} alt={file.name} className="upload-file-preview-img" />
      ) : (
        <div className="upload-file-preview-name">
          <span className="hint-text">({formatSize(file.size)})</span>
        </div>
      )}
    </div>
  );
}

function UploadFilesModal({ topicName, isOpen, onClose, onUploadSuccess }) {
  const { confirm, alert } = useConfirm();
  const { isRunning } = useTasks();
  const { toast } = useToast();
  const { acompanhar } = usePollingTask();
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [processando, setProcessando] = useState(false);
  const [taskProgress, setTaskProgress] = useState(0);
  const [taskMessage, setTaskMessage] = useState('');
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [pasteMessage, setPasteMessage] = useState('');

  const handleFechar = () => {
    onClose();
  };

  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, handleFechar);

  const fileInputRef = useRef(null);

  const loadFiles = async () => {
    if (!isOpen) return;
    setLoadingFiles(true);
    try {
      const res = await listFiles(topicName);
      setFiles(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Erro ao listar arquivos:', err);
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadFiles();
    }
  }, [isOpen, topicName]);

  useEffect(() => {
    const handlePaste = async (event) => {
      const itens = event.clipboardData?.items
        ? Array.from(event.clipboardData.items)
        : [];
      if (itens.some(item => item.type.startsWith('image/'))) {
        event.preventDefault();
      }

      const { arquivos, encontrouImagem } = await coletarImagensColadas(
        event.clipboardData,
        ALLOWED_IMAGE_EXTENSIONS
      );

      if (arquivos.length > 0) {
        setError('');
        setSelectedFiles(prev => [...prev, ...arquivos]);
        setPasteMessage(
          arquivos.length === 1
            ? `Imagem "${arquivos[0].name}" colada com sucesso!`
            : `${arquivos.length} imagens coladas com sucesso!`
        );
        setTimeout(() => setPasteMessage(''), 3000);
        event.preventDefault();
        return;
      }

      if (!encontrouImagem) {
        setError('O conteúdo colado não é uma imagem. Cole imagens PNG, JPG ou JPEG; para textos, use "Adicionar material de apoio".');
        setTimeout(() => setError(''), 4000);
        return;
      }

      setError('Não foi possível processar a imagem colada.');
      setTimeout(() => setError(''), 4000);
    };

    if (isOpen) {
      window.addEventListener('paste', handlePaste);
    }
    return () => {
      window.removeEventListener('paste', handlePaste);
    };
  }, [isOpen]);

  const finalizarProcessamento = async (resultados) => {
    setProcessando(false);
    setTaskProgress(100);
    await loadFiles();
    if (onUploadSuccess) onUploadSuccess();
    const avisos = [];
    resultados.forEach((resultado) => {
      if (!resultado) return;
      (resultado.files || []).forEach((arquivo) => {
        if (!arquivo.success) {
          avisos.push(`${arquivo.filename}: ${arquivo.error}`);
        }
      });
      if (Array.isArray(resultado.erros) && resultado.erros.length > 0) {
        avisos.push(...resultado.erros.map(nome => `Falha ao reconhecer o texto de: ${nome}`));
      }
    });
    if (avisos.length > 0) {
      await alert({
        title: 'Envio concluído com avisos',
        message: avisos.join('\n'),
        variant: 'warning',
      });
    } else {
      toast({ titulo: 'Sucesso', message: 'Arquivos enviados e processados com sucesso!', variante: 'sucesso' });
    }
  };

  const falharProcessamento = async (msgErro) => {
    setProcessando(false);
    await loadFiles();
    await alert({
      title: 'Erro',
      message: msgErro || 'Erro ao processar os arquivos enviados.',
      variant: 'danger',
    });
  };

  const acompanharSequencia = (ids, indice = 0, base = 0, acumulados = []) => {
    const fatia = 100 / ids.length;
    acompanhar(
      ids[indice],
      async (resultado) => {
        const proximos = [...acumulados, resultado];
        if (indice + 1 < ids.length) {
          acompanharSequencia(ids, indice + 1, base + fatia, proximos);
        } else {
          await finalizarProcessamento(proximos);
        }
      },
      falharProcessamento,
      (task) => {
        const progresso = Math.min(99, Math.round(base + ((task.progress || 0) * fatia / 100)));
        setTaskProgress(progresso);
        setTaskMessage(task.message || 'Processando os arquivos enviados...');
      }
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (selectedFiles.length === 0) {
      setError('Selecione ou cole pelo menos um arquivo.');
      return;
    }

    setUploading(true);
    setError('');

    try {
      const documentos = selectedFiles.filter(ehDocumento);
      const imagens = selectedFiles.filter(f => !ehDocumento(f));

      let success = true;
      const tarefas = [];

      if (documentos.length > 0) {
        const res = await uploadPDF(topicName, documentos);
        if (!res.data.success) {
          success = false;
          setError(res.data.error || 'Erro ao enviar os documentos.');
        } else if (res.data.task_id) {
          tarefas.push(res.data.task_id);
        }
      }

      if (success && imagens.length > 0) {
        const res = await uploadImages(topicName, imagens);
        if (!res.data.success) {
          success = false;
          setError(res.data.error || 'Erro ao enviar imagens.');
        } else if (res.data.task_id) {
          tarefas.push(res.data.task_id);
        }
      }

      if (success) {
        setSelectedFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
        setPasteMessage('');
      }

      if (tarefas.length > 0) {
        setTaskProgress(0);
        setTaskMessage('Processando os arquivos enviados...');
        setProcessando(true);
        acompanharSequencia(tarefas);
      } else if (success) {
        await loadFiles();
        if (onUploadSuccess) onUploadSuccess();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao enviar arquivos.');
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files);
    const invalidFile = selected.find(f => !ehDocumento(f) && !ALLOWED_IMAGE_EXTENSIONS.includes((f.name.split('.').pop() || '').toLowerCase()));
    if (invalidFile) {
      setError(`Arquivo "${invalidFile.name}": envie PDF, PPT/PPTX, DOC/DOCX, PNG, JPG ou JPEG.`);
      setTimeout(() => setError(''), 4000);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    if (selected.length + selectedFiles.length > MAX_FILES_PER_UPLOAD) {
      setError(`Máximo de ${MAX_FILES_PER_UPLOAD} arquivos por vez.`);
      return;
    }
    setSelectedFiles(prev => [...prev, ...selected]);
    setError('');
  };

  const removeSelectedFile = (index) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleDelete = async (filename) => {
    const confirmed = await confirm({
      title: 'Excluir arquivo',
      message: `Tem certeza que deseja excluir o arquivo "${filename}"? Essa ação não pode ser desfeita.`,
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await deleteFile(topicName, filename);
      await loadFiles();
      if (onUploadSuccess) onUploadSuccess();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao excluir arquivo.',
        variant: 'danger',
      });
      console.error(err);
    }
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  };

  if (!isOpen) return null;

  const uploadEmAndamento = processando || isRunning('upload_images') || isRunning('upload_documento');

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '85vh', overflowY: 'auto' }}>
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Adicionar arquivos</h2>

        {error && <div className="flash-error">{error}</div>}
        {pasteMessage && <div className="flash-success">{pasteMessage}</div>}

        {uploadEmAndamento ? (
          <div style={{ padding: '1rem 0' }}>
            <div className="rag-progress-bar" style={{ marginBottom: '0.5rem' }}>
              <div className="rag-progress-track">
                <div className="rag-progress-fill" style={{ width: `${taskProgress}%` }}></div>
              </div>
              <span className="rag-progress-text">{taskProgress}%</span>
            </div>
            <span className="carregando-linha">
              <span className="carregando-girar" aria-hidden="true" />
              {taskMessage || 'Processando os arquivos enviados...'}
            </span>
            <p className="hint-text" style={{ marginTop: '0.75rem' }}>
              Os arquivos aparecem na lista quando a tarefa concluir. Pode fechar esta janela, o processamento continua.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} encType="multipart/form-data">
            <div className="form-group">
              <label htmlFor="files">Documentos (PDF, PPT/PPTX, DOC/DOCX) e imagens (PNG, JPG, JPEG):</label>
              <input
                type="file"
                id="files"
                name="files"
                multiple
                accept=".pdf,.pptx,.ppt,.docx,.doc,.png,.jpg,.jpeg"
                className="form-control"
                onChange={handleFileChange}
                disabled={uploading}
                ref={fileInputRef}
              />
              <small>Até {MAX_FILES_PER_UPLOAD} arquivos por envio.</small>
            </div>

            <div className="upload-paste-hint">
              <p className="upload-paste-hint-title">
                Ctrl+V (Cmd+V) cola imagens direto da área de transferência.
              </p>
            </div>

            {selectedFiles.length > 0 && (
              <div className="upload-file-preview-list">
                {selectedFiles.map((file, index) => (
                  <FilePreview
                    key={`${file.name}-${index}`}
                    file={file}
                    onRemove={() => removeSelectedFile(index)}
                    formatSize={formatSize}
                  />
                ))}
              </div>
            )}

            <button
              type="submit"
              className="save-button"
              disabled={selectedFiles.length === 0 || uploading}
              style={{ marginTop: '1rem' }}
            >
              {uploading ? 'Enviando...' : 'Enviar Arquivos'}
            </button>
          </form>
        )}

        <div style={{ marginTop: '2rem' }}>
          <h2>Arquivos enviados</h2>
          {uploadEmAndamento ? (
            <p className="hint-text">Processando os arquivos enviados... eles aparecem aqui quando a tarefa concluir.</p>
          ) : loadingFiles ? (
            <span className="carregando-linha">
              <span className="carregando-girar" aria-hidden="true" />
              Carregando arquivos...
            </span>
          ) : files.length === 0 ? (
            <p>Nenhum arquivo enviado ainda.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {files.map((file) => (
                <li
                  key={file.name}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.75rem',
                    borderBottom: '1px solid #e2e8f0',
                    flexWrap: 'wrap',
                  }}
                >
                  <span style={{ wordBreak: 'break-all', flex: 1 }}>
                    <strong>{file.name}</strong>
                    <span className="hint-text" style={{ marginLeft: '0.5rem' }}>
                      ({file.type}) {formatSize(file.size)}
                    </span>
                  </span>
                  <button
                    onClick={() => handleDelete(file.name)}
                    className="upload-file-remove-btn"
                    style={{ marginLeft: '0.5rem' }}
                  >
                    Excluir
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

      </div>
    </div>
  );
}

export default UploadFilesModal;