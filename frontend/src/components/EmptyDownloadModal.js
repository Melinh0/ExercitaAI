import React from 'react';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const MESSAGES = {
  images: {
    title: 'Nenhuma imagem disponível',
    message: (topic) => (
      <>O tópico <strong>{topic}</strong> ainda não possui imagens para download. Adicione imagens primeiro.</>
    ),
  },
  whiteboards: {
    title: 'Nenhum quadro branco disponível',
    message: (topic) => (
      <>O tópico <strong>{topic}</strong> ainda não possui quadros brancos salvos. Crie anotações no quadro branco primeiro.</>
    ),
  },
  resolutions: {
    title: 'Nenhuma resolução disponível',
    message: (topic) => (
      <>O tópico <strong>{topic}</strong> ainda não possui resoluções geradas. Analise imagens primeiro para criar resoluções.</>
    ),
  },
};

function EmptyDownloadModal({ isOpen, onClose, type, topicName }) {
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);
  if (!isOpen) return null;
  const info = MESSAGES[type] || MESSAGES.images;
  const topicDisplay = (topicName || '').replace(/_/g, ' ');

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content empty-download-modal">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>{info.title}</h2>
        <p className="empty-download-message">{info.message(topicDisplay)}</p>
      </div>
    </div>
  );
}

export default EmptyDownloadModal;