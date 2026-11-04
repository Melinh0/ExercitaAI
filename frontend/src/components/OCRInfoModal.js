import React from 'react';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const OCR_INFO = {
  tesseract: {
    name: 'Tesseract OCR',
    tagline: 'Padrão e offline',
    description:
      'Mecanismo de OCR de código aberto mantido pelo Google. Roda localmente no servidor da aplicação, sem depender de APIs externas. É o método padrão e o mais rápido para a maioria dos casos.',
    pros: [
      'Totalmente offline e gratuito',
      'Rápido para documentos digitalizados com boa qualidade',
      'Não envia dados para servidores externos',
      'Suporte a vários idiomas (português e inglês configurados)'
    ],
    cons: [
      'Menor precisão em imagens com baixa resolução ou ruído',
      'Pode falhar em manuscritos ou fontes decorativas',
      'Não interpreta fórmulas matemáticas complexas'
    ],
    bestFor:
      'Provas digitalizadas, PDFs com texto nítido, imagens de scanner, documentos impressos em geral.',
    link: 'https://github.com/tesseract-ocr/tesseract'
  },
  llm: {
    name: 'Via LLM',
    tagline: 'Modelos multimodais (Ollama e provedores)',
    description:
      'Transcrição feita por um modelo de linguagem multimodal (com visão) — pode ser um modelo do Ollama (com sua chave) ou de outro provedor (Groq, OpenAI, Gemini, Anthropic, NVIDIA). Além de extrair o texto, o modelo consegue interpretar o contexto visual e corrigir erros de leitura automaticamente. Ao escolher este método, um seletor de "modelo de visão" aparece abaixo para você escolher o modelo usado apenas na transcrição.',
    pros: [
      'Alta precisão em imagens complexas e manuscritos',
      'Interpreta o contexto visual e corrige erros de OCR',
      'Reconhece fórmulas matemáticas e diagramas',
      'Permite escolher qualquer modelo multimodal disponível (Ollama + provedores)'
    ],
    cons: [
      'Requer chave de API (Ollama ou provedor) configurada',
      'Mais lento que o Tesseract',
      'Envia a imagem para o provedor do modelo selecionado'
    ],
    bestFor:
      'Imagens de baixa qualidade, manuscritos, questões com fórmulas matemáticas, diagramas e gráficos.',
    link: 'https://ollama.com/search?q=vision'
  },
  ocrspace: {
    name: 'OCR.space',
    tagline: 'API online especializada',
    description:
      'Serviço de OCR baseado em nuvem que oferece alta precisão para uma ampla variedade de documentos. Requer uma chave de API gratuita (até um limite mensal de requisições).',
    pros: [
      'Alta precisão para documentos variados',
      'Boa performance em imagens de recibos, notas e formulários',
      'Suporta vários idiomas e formatos',
      'Plano gratuito disponível'
    ],
    cons: [
      'Requer chave de API configurada',
      'Limite mensal de requisições no plano gratuito',
      'Envia a imagem para servidores externos',
      'Pode falhar em imagens muito grandes'
    ],
    bestFor:
      'Documentos variados, recibos, notas fiscais, formulários e imagens que não são bem atendidas pelo Tesseract.',
    link: 'https://ocr.space/'
  }
};

function OCRInfoModal({ isOpen, onClose, selectedOCR }) {
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);
  if (!isOpen) return null;

  const ocrList = Object.keys(OCR_INFO);

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content model-info-modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Informações sobre os métodos de OCR</h2>
        <p className="model-info-intro">
          O OCR (Reconhecimento Óptico de Caracteres) converte texto presente em imagens para texto
          editável. Cada método tem características diferentes de precisão, velocidade e privacidade.
        </p>

        {ocrList.map((ocrKey) => {
          const info = OCR_INFO[ocrKey];
          const isSelected = ocrKey === selectedOCR;
          return (
            <div
              key={ocrKey}
              className={`model-info-card ${isSelected ? 'selected' : ''}`}
            >
              <h3>
                {info.name}
                {isSelected && <span className="model-info-badge selected-badge">Selecionado</span>}
                {!isSelected && info.tagline && (
                  <span className="model-info-badge">{info.tagline}</span>
                )}
              </h3>
              <p>{info.description}</p>

              {info.pros && info.pros.length > 0 && (
                <div className="model-info-section">
                  <strong>Pontos positivos</strong>
                  <ul>
                    {info.pros.map((p, i) => <li key={i}>{p}</li>)}
                  </ul>
                </div>
              )}

              {info.cons && info.cons.length > 0 && (
                <div className="model-info-section">
                  <strong>Pontos negativos</strong>
                  <ul>
                    {info.cons.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}

              <div className="model-info-section">
                <strong>Ideal para</strong>
                <p style={{ margin: 0 }}>{info.bestFor}</p>
              </div>

              <a
                className="model-info-link"
                href={info.link}
                target="_blank"
                rel="noopener noreferrer"
              >
                Ver detalhes no site oficial
              </a>
            </div>
          );
        })}

      </div>
    </div>
  );
}

export default OCRInfoModal;