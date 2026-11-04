import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { getTopics, deleteTopic } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useConfirm } from '../contexts/ConfirmContext';
import ConfigModal from '../components/ConfigModal';
import NewTopicModal from '../components/NewTopicModal';
import HelpModal from '../components/HelpModal';
import CarregandoTela from '../components/CarregandoTela';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';
import {
  IconeEngrenagem,
  IconeSol,
  IconeLua,
  IconeMais,
  IconeSetaDireita,
  IconeSetaEsquerda,
} from '../components/Icons';

const TOPICS_PER_PAGE = 6;

function TopicsList() {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [newTopicOpen, setNewTopicOpen] = useState(false);
  const [ajudaOpen, setAjudaOpen] = useState(false);
  const [ollamaWarnOpen, setOllamaWarnOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const { user, logout } = useAuth();
  const { darkMode, toggleDarkMode } = useTheme();
  const { confirm, alert } = useConfirm();
  const location = useLocation();

  const loadTopics = useCallback(() => {
    setLoading(true);
    setError(null);
    getTopics()
      .then(res => {
        if (Array.isArray(res.data)) setTopics(res.data);
        else setError('Resposta inválida do servidor.');
      })
      .catch(() => setError('Não foi possível carregar seus tópicos. Verifique sua conexão.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadTopics();
  }, [loadTopics, location.key]);

  const avisoFlagRef = useRef(null);

  useEffect(() => {
    axios.get('/auth/current_user')
      .then(res => {
        const keys = res.data.ollama_keys || [];
        if (keys.length > 0) return;
        const flag = `aviso_chave_ollama_visto_${res.data.id}`;
        avisoFlagRef.current = flag;
        if (localStorage.getItem(flag)) return;
        setOllamaWarnOpen(true);
      })
      .catch(err => console.error('Erro ao verificar chaves de API:', err));
  }, []);

  const marcarAvisoVisto = () => {
    if (avisoFlagRef.current) {
      localStorage.setItem(avisoFlagRef.current, '1');
    }
  };

  const dismissOllamaWarning = () => {
    marcarAvisoVisto();
    setOllamaWarnOpen(false);
  };

  const { modalRef: refAviso, aoClicarFundo: aoClicarFundoAviso } = useModalAcessibilidade(ollamaWarnOpen, dismissOllamaWarning);

  const handleOpenConfigFromWarning = () => {
    marcarAvisoVisto();
    setOllamaWarnOpen(false);
    setConfigOpen(true);
  };

  const totalPages = Math.max(1, Math.ceil(topics.length / TOPICS_PER_PAGE));

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [totalPages, currentPage]);

  const handleDelete = async (topicName) => {
    const confirmed = await confirm({
      title: 'Excluir tópico',
      message: `Deseja realmente excluir o tópico "${topicName.replace(/_/g, ' ')}"? Essa ação não pode ser desfeita.`,
      confirmText: 'Excluir',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await deleteTopic(topicName);
      loadTopics();
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao excluir o tópico.',
        variant: 'danger',
      });
    }
  };

  const startIndex = (currentPage - 1) * TOPICS_PER_PAGE;
  const endIndex = startIndex + TOPICS_PER_PAGE;
  const visibleTopics = topics.slice(startIndex, endIndex);

  const goToPage = (page) => {
    const p = Math.max(1, Math.min(totalPages, page));
    setCurrentPage(p);
  };

  const renderPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let end = Math.min(totalPages, start + maxVisible - 1);
    if (end - start + 1 < maxVisible) {
      start = Math.max(1, end - maxVisible + 1);
    }
    if (start > 1) {
      pages.push(
        <button
          key={1}
          className={`pagination-btn ${currentPage === 1 ? 'active' : ''}`}
          onClick={() => goToPage(1)}
        >
          1
        </button>
      );
      if (start > 2) {
        pages.push(<span key="ellipsis-start" className="pagination-ellipsis">...</span>);
      }
    }
    for (let i = start; i <= end; i++) {
      pages.push(
        <button
          key={i}
          className={`pagination-btn ${currentPage === i ? 'active' : ''}`}
          onClick={() => goToPage(i)}
        >
          {i}
        </button>
      );
    }
    if (end < totalPages) {
      if (end < totalPages - 1) {
        pages.push(<span key="ellipsis-end" className="pagination-ellipsis">...</span>);
      }
      pages.push(
        <button
          key={totalPages}
          className={`pagination-btn ${currentPage === totalPages ? 'active' : ''}`}
          onClick={() => goToPage(totalPages)}
        >
          {totalPages}
        </button>
      );
    }
    return pages;
  };

  if (loading) return <CarregandoTela rotulo="Carregando seus tópicos..." />;
  if (error) {
    return (
      <div className="container">
        <div className="erro-tela">
          <p>{error}</p>
          <button type="button" className="button" onClick={loadTopics}>
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="top-bar">
        <div className="top-bar-left">
          <span
            className="marca-cabecalho marca-cabecalho-clicavel"
            role="button"
            tabIndex={0}
            title="Como usar o app"
            onClick={() => setAjudaOpen(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setAjudaOpen(true);
              }
            }}
          >
            <span className="marca-simbolo" aria-hidden="true">E</span>
            Exercita AI
          </span>
          <button
            onClick={() => setConfigOpen(true)}
            className="top-bar-icon-btn"
            title="Configurações"
            aria-label="Configurações"
          >
            <IconeEngrenagem size={20} />
          </button>
          <button
            onClick={toggleDarkMode}
            className="top-bar-icon-btn"
            title={darkMode ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
            aria-label="Alternar tema"
          >
            {darkMode ? <IconeSol size={20} /> : <IconeLua size={20} />}
          </button>
          <button
            onClick={() => window.open('https://forms.gle/mDtHba24bhLKrsz2A', '_blank')}
            className="top-bar-btn top-bar-btn-evaluate"
            title="Avalie a ferramenta! Sua opinião é muito importante para nós."
          >
            Avaliar
          </button>
        </div>
        <div className="top-bar-right">
          <button onClick={logout} className="top-bar-btn top-bar-btn-logout">
            Sair
          </button>
        </div>
      </div>

      <main className="content" style={{ maxWidth: '860px', margin: '0 auto' }}>
        <div className="topics-header">
          <div>
            <h1>Tópicos de estudo</h1>
            <p className="topics-subtitle">Olá, {user?.username || 'estudante'}. O que vamos estudar hoje?</p>
          </div>
        </div>

        <button type="button" onClick={() => setNewTopicOpen(true)} className="new-topic-cta">
          <span className="new-topic-cta-icon"><IconeMais size={22} /></span>
          <span className="new-topic-cta-text">
            <strong>Criar novo tópico</strong>
            <small>Comece um novo material de estudos</small>
          </span>
        </button>

        {topics.length > 0 ? (
          <>
            <ul className="topics-list">
              {visibleTopics.map(topic => (
                <li key={topic} className="topic-item">
                  <Link to={`/topic/${topic}`} className="topic-item-link">
                    <span className="topic-item-name">{topic.replace(/_/g, ' ')}</span>
                    <span className="topic-item-arrow"><IconeSetaDireita size={18} /></span>
                  </Link>
                  <button onClick={() => handleDelete(topic)} className="topic-item-delete" title="Excluir tópico">
                    Excluir
                  </button>
                </li>
              ))}
            </ul>

            {totalPages > 1 && (
              <div className="pagination-container">
                <button
                  className="pagination-btn pagination-nav-btn"
                  onClick={() => goToPage(currentPage - 1)}
                  disabled={currentPage === 1}
                >
                  <IconeSetaEsquerda size={16} />
                </button>
                {renderPageNumbers()}
                <button
                  className="pagination-btn pagination-nav-btn"
                  onClick={() => goToPage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                >
                  <IconeSetaDireita size={16} />
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="topics-guia">
            <p className="topics-guia-texto">
              Crie um tópico com o assunto que você quer dominar, adicione
              imagens de questões e textos de apoio, e use as ferramentas de
              estudo para gerar questões, flashcards e um plano de revisão a
              partir do seu material.
            </p>
          </div>
        )}
      </main>
      {ollamaWarnOpen && (
        <div className="modal modal-aberto" onClick={aoClicarFundoAviso} ref={refAviso}>
          <div className="modal-content" style={{ maxWidth: '520px' }}>
            <span className="close" onClick={dismissOllamaWarning}>&times;</span>
            <h2>Para gerar conteúdo, cadastre uma chave de IA</h2>
            <p>
              As ferramentas de estudo usam uma inteligência externa para gerar
              questões, flashcards e revisões. Para ativá-las, crie uma chave
              gratuita no{' '}
              <a href="https://ollama.com" target="_blank" rel="noopener noreferrer">
                ollama.com
              </a>{' '}
              e cadastre em Configurações. Você pode explorar a plataforma agora
              e fazer isso quando quiser.
            </p>
            <div className="form-actions">
              <button
                type="button"
                className="button"
                onClick={handleOpenConfigFromWarning}
              >
                Cadastrar chave
              </button>
              <button
                type="button"
                className="button button-secundario"
                onClick={dismissOllamaWarning}
              >
                Agora não
              </button>
            </div>
          </div>
        </div>
      )}
      <NewTopicModal
        isOpen={newTopicOpen}
        onClose={() => setNewTopicOpen(false)}
        onCreated={() => {
          setNewTopicOpen(false);
          loadTopics();
        }}
      />
      <ConfigModal isOpen={configOpen} onClose={() => setConfigOpen(false)} />
      <HelpModal isOpen={ajudaOpen} onClose={() => setAjudaOpen(false)} />
    </div>
  );
}

export default TopicsList;