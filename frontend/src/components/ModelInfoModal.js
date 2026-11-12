import React, { useEffect, useState } from 'react';
import { getModelInfo } from '../services/api';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

const MODEL_INFO = {
  'gemma4:cloud': {
    name: 'Gemma 4 Cloud',
    tagline: 'Equilíbrio entre velocidade e qualidade',
    description:
      'Versão do Gemma 4 hospedada na nuvem do Ollama. Modelo otimizado para tarefas do dia a dia: geração de questões, resumos, análise de imagens simples e criação de flashcards. Boa velocidade de resposta e suporta entrada de imagens (visão).',
    pros: [
      'Respostas rápidas (segundos em vez de minutos)',
      'Suporta visão para analisar imagens e diagramas',
      'Bom custo-benefício para uso contínuo',
      'Ideal para tarefas curtas e médias'
    ],
    cons: [
      'Menor precisão em raciocínio matemático complexo',
      'Menor retenção de contexto em textos muito longos',
      'Pode gerar respostas mais genéricas'
    ],
    bestFor:
      'Geração de questões objetivas, flashcards, resumos rápidos, análise de imagens de provas, recomendação de estratégia de estudo.',
    link: 'https://ollama.com/library/gemma4:cloud'
  }
};

const PROVEDORES_INFO = {
  openai: { nome: 'OpenAI', link: 'https://platform.openai.com/docs' },
  groq: { nome: 'Groq', link: 'https://console.groq.com/docs' },
  gemini: { nome: 'Google Gemini', link: 'https://ai.google.dev/gemini-api/docs' },
  openrouter: { nome: 'OpenRouter', link: 'https://openrouter.ai/models' },
  deepseek: { nome: 'DeepSeek', link: 'https://api-docs.deepseek.com' },
  anthropic: { nome: 'Anthropic', link: 'https://platform.claude.com/docs' },
  nvidia: { nome: 'NVIDIA', link: 'https://build.nvidia.com/models' }
};

const FALLBACK_OLLAMA = {
  name: '',
  tagline: 'Modelo disponível',
  description:
    'Este modelo está disponível no sistema, mas ainda não temos informações detalhadas cadastradas sobre ele. Consulte a página do Ollama para mais detalhes.',
  bestFor: 'Consulte a documentação oficial do Ollama.',
  link: 'https://ollama.com/search'
};

const fallbackPara = (modelName) => {
  const prefixo = modelName.split('/', 1)[0];
  const provedor = PROVEDORES_INFO[prefixo];
  if (!provedor) return FALLBACK_OLLAMA;
  return {
    name: '',
    tagline: 'Modelo disponível',
    description: `Este modelo está disponível no sistema, mas ainda não temos informações detalhadas cadastradas sobre ele. Consulte a documentação oficial do provedor ${provedor.nome}.`,
    bestFor: `Consulte a documentação oficial do provedor ${provedor.nome}.`,
    link: provedor.link
  };
};

function ModelInfoModal({ isOpen, onClose, selectedModel, availableModels = [] }) {
  const [infoRemota, setInfoRemota] = useState({});
  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, onClose);

  useEffect(() => {
    if (!isOpen) return undefined;
    let ativo = true;
    getModelInfo(availableModels)
      .then((res) => {
        if (ativo) setInfoRemota(res.data?.model_info || {});
      })
      .catch(() => {});
    return () => {
      ativo = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const modelsToShow = availableModels.length > 0
    ? availableModels
    : Object.keys(MODEL_INFO);

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content model-info-modal-content">
        <span className="close" onClick={onClose}>&times;</span>
        <h2>Informações sobre os modelos de IA</h2>
        <p className="model-info-intro">
          Cada modelo tem pontos fortes e limitações. Escolha o mais adequado para a tarefa:
          modelos menores são mais rápidos e baratos; modelos maiores são mais precisos, mas mais lentos.
        </p>

        {modelsToShow.map((modelName) => {
          const info = MODEL_INFO[modelName] || infoRemota[modelName] || fallbackPara(modelName);
          const ehOllama = (info.link || '').startsWith('https://ollama.com');
          const isSelected = modelName === selectedModel;
          return (
            <div
              key={modelName}
              className={`model-info-card ${isSelected ? 'selected' : ''}`}
            >
              <h3>
                {info.name || modelName}
                {isSelected && <span className="model-info-badge selected-badge">Selecionado</span>}
                {!isSelected && info.tagline && (
                  <span className="model-info-badge">{info.tagline}</span>
                )}
              </h3>
              <p><code>{modelName}</code></p>
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
                {ehOllama ? 'Ver detalhes no Ollama' : 'Ver detalhes no site do provedor'}
              </a>
            </div>
          );
        })}

      </div>
    </div>
  );
}

export default ModelInfoModal;