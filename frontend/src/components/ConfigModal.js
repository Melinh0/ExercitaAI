import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { useConfirm } from '../contexts/ConfirmContext';
import useModalAcessibilidade from '../hooks/useModalAcessibilidade';

function ConfigModal({ isOpen, onClose }) {
  const { user, refreshUser } = useAuth();
  const { confirm } = useConfirm();
  const [ollamaKeys, setOllamaKeys] = useState([]);
  const [ocrKeys, setOcrKeys] = useState([]);
  const [baseSalva, setBaseSalva] = useState({ ollama: [], ocr: [] });
  const [provedores, setProvedores] = useState([]);
  const [provedorSel, setProvedorSel] = useState('');
  const [novaChaveProvedor, setNovaChaveProvedor] = useState('');
  const [newOllamaKey, setNewOllamaKey] = useState('');
  const [newOcrKey, setNewOcrKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const loadKeys = () => {
    if (user) {
      axios.get('/auth/current_user')
        .then(res => {
          const userKeys = res.data;
          setOllamaKeys(userKeys.ollama_keys || []);
          setOcrKeys(userKeys.ocr_keys || []);
          setBaseSalva({
            ollama: userKeys.ollama_keys || [],
            ocr: userKeys.ocr_keys || [],
          });
        })
        .catch(err => console.error('Erro ao carregar chaves:', err));
    }
  };

  const loadProvedores = () => {
    axios.get('/api/provedores')
      .then(res => {
        const itens = Array.isArray(res.data) ? res.data : [];
        setProvedores(itens);
        setProvedorSel(atual => (itens.some(p => p.id === atual) ? atual : (itens[0] ? itens[0].id : '')));
      })
      .catch(err => console.error('Erro ao carregar provedores:', err));
  };

  useEffect(() => {
    if (isOpen && user) {
      loadKeys();
      loadProvedores();
    }
  }, [isOpen, user]);

  const idsProvedores = provedores.map(p => p.id);

  const prefixoDe = (chave) => {
    const i = chave.indexOf('=');
    return i > 0 ? chave.substring(0, i) : '';
  };

  const ehProvedor = (chave) => idsProvedores.includes(prefixoDe(chave));

  const chavesOllama = ollamaKeys.filter(k => !ehProvedor(k));
  const chavesProvedores = ollamaKeys.filter(k => ehProvedor(k));

  const addKey = (type) => {
    if (type === 'ollama' && newOllamaKey.trim()) {
      const updated = [...ollamaKeys, newOllamaKey.trim()];
      setOllamaKeys(updated);
      setNewOllamaKey('');
    } else if (type === 'ocr' && newOcrKey.trim()) {
      const updated = [...ocrKeys, newOcrKey.trim()];
      setOcrKeys(updated);
      setNewOcrKey('');
    }
  };

  const addChaveProvedor = () => {
    const valor = novaChaveProvedor.trim();
    if (!valor || !provedorSel) return;
    setOllamaKeys([...ollamaKeys, `${provedorSel}=${valor}`]);
    setNovaChaveProvedor('');
  };

  const confirmarRemocao = () => confirm({
    title: 'Remover chave',
    message: 'Tem certeza que deseja remover esta chave? Essa ação não pode ser desfeita.',
    confirmText: 'Remover',
    cancelText: 'Cancelar',
    variant: 'danger',
  });

  const removeKey = async (type, index) => {
    const confirmed = await confirmarRemocao();
    if (!confirmed) return;
    if (type === 'ollama') {
      const alvo = chavesOllama[index];
      const pos = ollamaKeys.indexOf(alvo);
      if (pos >= 0) {
        setOllamaKeys(ollamaKeys.filter((_, i) => i !== pos));
      }
    } else {
      const updated = ocrKeys.filter((_, i) => i !== index);
      setOcrKeys(updated);
    }
  };

  const removeProvedorKey = async (chave) => {
    const confirmed = await confirmarRemocao();
    if (!confirmed) return;
    const pos = ollamaKeys.indexOf(chave);
    if (pos >= 0) {
      setOllamaKeys(ollamaKeys.filter((_, i) => i !== pos));
    }
  };

  const handleSave = async () => {
    let atuaisOllama = newOllamaKey.trim() ? [...ollamaKeys, newOllamaKey.trim()] : ollamaKeys;
    const pendenteProvedor = novaChaveProvedor.trim();
    if (pendenteProvedor && provedorSel) {
      atuaisOllama = [...atuaisOllama, `${provedorSel}=${pendenteProvedor}`];
    }
    const atuaisOcr = newOcrKey.trim() ? [...ocrKeys, newOcrKey.trim()] : ocrKeys;
    setOllamaKeys(atuaisOllama);
    setOcrKeys(atuaisOcr);
    setNewOllamaKey('');
    setNewOcrKey('');
    setNovaChaveProvedor('');

    setLoading(true);
    setMessage('');
    try {
      const payload = {
        ollama_keys: atuaisOllama,
        ocr_keys: atuaisOcr
      };
      const response = await axios.post('/auth/update_keys', payload);
      if (response.data.success) {
        setMessage('Chaves salvas com sucesso! Ficam vinculadas à sua conta e entram em uso imediato nas gerações.');
        await loadKeys();
        if (refreshUser) await refreshUser();
        setTimeout(() => {
          setMessage('');
          onClose();
        }, 1500);
      } else {
        setMessage('Erro ao salvar chaves. Tente novamente.');
      }
    } catch (err) {
      setMessage('Erro ao salvar chaves: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoading(false);
    }
  };

  const alteracoesPendentes =
    newOllamaKey.trim() !== '' ||
    newOcrKey.trim() !== '' ||
    novaChaveProvedor.trim() !== '' ||
    JSON.stringify(ollamaKeys) !== JSON.stringify(baseSalva.ollama) ||
    JSON.stringify(ocrKeys) !== JSON.stringify(baseSalva.ocr);

  const chavePareceProvedor = /^(sk-|gsk_|AIza|nvapi-)/.test(newOllamaKey.trim());

  const fechar = async () => {
    if (alteracoesPendentes) {
      const descartar = await confirm({
        title: 'Descartar alterações',
        message: 'Há chaves ainda não salvas. Fechar agora descarta essas alterações. Deseja descartar?',
        confirmText: 'Descartar',
        cancelText: 'Continuar editando',
        variant: 'danger',
      });
      if (!descartar) return;
    }
    onClose();
  };

  const { modalRef, aoClicarFundo } = useModalAcessibilidade(isOpen, fechar);

  if (!isOpen) return null;

  return (
    <div className="modal modal-aberto" onClick={aoClicarFundo} ref={modalRef}>
      <div className="modal-content" style={{ maxWidth: '560px' }}>
        <span className="close" onClick={fechar}>&times;</span>
        <h2>Configurações de API</h2>
        <p>Gerencie as chaves de API da sua conta.</p>
        {message && <div className={message.includes('sucesso') ? 'flash-success' : 'flash-error'}>{message}</div>}

        <div className="form-group">
          <label>Chaves Ollama (obrigatório)</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              className="form-control"
              value={newOllamaKey}
              onChange={(e) => setNewOllamaKey(e.target.value)}
              placeholder="Nova chave..."
            />
            <button className="button" onClick={() => addKey('ollama')} style={{ padding: '0 1rem' }}>Adicionar</button>
          </div>
          {chavePareceProvedor && (
            <div className="modal-hint">
              Essa chave não parece ser do Ollama. Cadastre-a em Outros provedores abaixo.
            </div>
          )}
          <div style={{ fontSize: '0.8rem', marginTop: '0.25rem', color: '#1e3a8a' }}>
            <a href="https://ollama.com" target="_blank" rel="noopener noreferrer">
              Criar conta no Ollama e gerar uma chave.
            </a>
          </div>
          <ul style={{ listStyle: 'none', padding: 0, marginTop: '0.5rem' }}>
            {chavesOllama.map((key, idx) => (
              <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.25rem 0', borderBottom: '1px solid #eee' }}>
                <span>{key.substring(0, 12)}...{key.substring(key.length - 4)}</span>
                <button className="delete-button" style={{ padding: '0.2rem 0.6rem', fontSize: '0.8rem' }} onClick={() => removeKey('ollama', idx)}>Remover</button>
              </li>
            ))}
          </ul>
        </div>

        {provedores.length > 0 && (
          <div className="form-group">
            <label>Outros provedores de modelos (opcional)</label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <select
                className="form-control"
                value={provedorSel}
                onChange={(e) => setProvedorSel(e.target.value)}
                style={{ maxWidth: '170px' }}
              >
                {provedores.map(p => (
                  <option key={p.id} value={p.id}>{p.nome}</option>
                ))}
              </select>
              <input
                type="text"
                className="form-control"
                value={novaChaveProvedor}
                onChange={(e) => setNovaChaveProvedor(e.target.value)}
                placeholder="Nova chave da API..."
              />
              <button className="button" onClick={addChaveProvedor} style={{ padding: '0 1rem' }}>Adicionar</button>
            </div>
            <div className="modal-hint">
              Chaves de outros provedores liberam seus modelos na lista, com prefixo (ex.: groq/).
            </div>
            <ul style={{ listStyle: 'none', padding: 0, marginTop: '0.5rem' }}>
              {chavesProvedores.map((chave) => {
                const pid = prefixoDe(chave);
                const nome = (provedores.find(p => p.id === pid) || {}).nome || pid;
                const valor = chave.substring(pid.length + 1);
                return (
                  <li key={chave} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.25rem 0', borderBottom: '1px solid #eee' }}>
                    <span>{nome}: {valor.substring(0, 10)}...{valor.substring(valor.length - 4)}</span>
                    <button className="delete-button" style={{ padding: '0.2rem 0.6rem', fontSize: '0.8rem' }} onClick={() => removeProvedorKey(chave)}>Remover</button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <div className="form-group">
          <label>Chaves OCR.space (opcional)</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              className="form-control"
              value={newOcrKey}
              onChange={(e) => setNewOcrKey(e.target.value)}
              placeholder="Nova chave..."
            />
            <button className="button" onClick={() => addKey('ocr')} style={{ padding: '0 1rem' }}>Adicionar</button>
          </div>
          <div style={{ fontSize: '0.8rem', marginTop: '0.25rem', color: '#1e3a8a' }}>
            <a href="https://ocr.space/OCRAPI" target="_blank" rel="noopener noreferrer">
              Criar conta no OCR.space e obter uma chave.
            </a>
          </div>
          <ul style={{ listStyle: 'none', padding: 0, marginTop: '0.5rem' }}>
            {ocrKeys.map((key, idx) => (
              <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.25rem 0', borderBottom: '1px solid #eee' }}>
                <span>{key.substring(0, 12)}...{key.substring(key.length - 4)}</span>
                <button className="delete-button" style={{ padding: '0.2rem 0.6rem', fontSize: '0.8rem' }} onClick={() => removeKey('ocr', idx)}>Remover</button>
              </li>
            ))}
          </ul>
        </div>

        <div className="form-actions">
          <button onClick={handleSave} className="save-button" disabled={loading}>{loading ? 'Salvando...' : 'Salvar'}</button>
        </div>
      </div>
    </div>
  );
}

export default ConfigModal;
