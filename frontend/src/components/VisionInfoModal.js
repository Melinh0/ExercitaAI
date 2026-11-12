import React from 'react';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

function VisionInfoModal({ isOpen, onClose, visionModels = [], ocrModel, loading = false }) {
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);
  if (!isOpen) return null;

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content model-info-modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Modelos de IA com suporte a imagens (visão)</h2>
        <p className="model-info-intro">
          Modelos com <strong>visão</strong> (multimodais) conseguem "enxergar" uma imagem e transcrever
          o que ela contém: texto, fórmulas, diagramas e gráficos. No método <strong>Via LLM</strong>,
          o modelo escolhido aqui é usado <strong>apenas na transcrição</strong> da imagem — a geração
          de questões continua usando o modelo do primeiro seletor.
        </p>

        <div className="model-info-card">
          <h3>
            Seus modelos com visão
            {!loading && visionModels.length > 0 && (
              <span className="model-info-badge">{visionModels.length} disponível(is)</span>
            )}
          </h3>
          {loading ? (
            <p>Carregando a lista de modelos com visão…</p>
          ) : visionModels.length === 0 ? (
            <p>
              Nenhum modelo com visão disponível no momento. Cadastre uma chave de API de um provedor
              com modelos multimodais (Ollama, Groq, OpenAI, Gemini, Anthropic, OpenRouter ou NVIDIA) em
              Configurações, ou escolha outro método de transcrição.
            </p>
          ) : (
            <>
              <p>Modelos compatíveis com as chaves cadastradas na sua conta:</p>
              <div className="model-info-section">
                <strong>Disponíveis na sua conta</strong>
                <ul>
                  {visionModels.map((m) => (
                    <li key={m}>
                      <code>{m}</code>
                      {m === ocrModel && (
                        <span
                          className="model-info-badge selected-badge"
                          style={{ marginLeft: '0.5rem' }}
                        >
                          Selecionado
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>

        <div className="model-info-card">
          <h3>
            Quem oferece modelos com visão
            <span className="model-info-badge">Por provedor</span>
          </h3>
          <p>
            A lista acima considera apenas as chaves da sua conta. Estes são os provedores que
            oferecem modelos multimodais:
          </p>
          <div className="model-info-section">
            <strong>Provedores com modelos de visão</strong>
            <ul>
              <li><strong>Ollama</strong> — modelos multimodais com sua chave (ex.: gemma4:31b)</li>
              <li><strong>Groq</strong> — llama-4-scout</li>
              <li><strong>OpenAI</strong> — gpt-4o, gpt-4.1, o4</li>
              <li><strong>Google Gemini</strong> — todos os modelos são multimodais</li>
              <li><strong>Anthropic</strong> — todos os Claude são multimodais</li>
              <li><strong>OpenRouter</strong> — vários modelos vision (Gemini, Llama 4…)</li>
              <li><strong>NVIDIA</strong> — llama-4, Qwen-VL e phi-4-multimodal</li>
            </ul>
          </div>
          <div className="model-info-section">
            <strong>Sem modelos com visão</strong>
            <ul>
              <li><strong>DeepSeek</strong> — apenas texto puro (não serve para OCR)</li>
            </ul>
          </div>
        </div>

        <div className="model-info-card">
          <h3>
            Dicas de uso
            <span className="model-info-badge">OCR via LLM</span>
          </h3>
          <p>
            O modelo de visão entra apenas na transcrição da imagem — o texto extraído alimenta o RAG
            e a geração de questões.
          </p>
          <div className="model-info-section">
            <strong>Boas práticas</strong>
            <ul>
              <li>Em imagens nítidas qualquer modelo serve; a diferença aparece em manuscritos e fotos</li>
              <li>Se a transcrição sair errada, troque o modelo de visão ou volte ao Tesseract</li>
              <li>Para mais opções, cadastre chaves de provedores com visão em Configurações</li>
            </ul>
          </div>
        </div>

      </div>
    </div>
  );
}

export default VisionInfoModal;
