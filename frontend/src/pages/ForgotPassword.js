import React, { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [mensagem, setMensagem] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro('');
    setMensagem('');
    setEnviando(true);
    try {
      const res = await axios.post('/auth/forgot_password', { email });
      setMensagem(
        res.data.message ||
        'Se este e-mail estiver cadastrado, você receberá as instruções.'
      );
      setEnviado(true);
    } catch (err) {
      setErro(
        err.response?.data?.error ||
        'Não foi possível processar a solicitação. Tente novamente.'
      );
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-box">
        <h1>Esqueci minha senha</h1>
        <p style={{ marginBottom: '1.2rem', color: '#6b7280' }}>
          Informe o e-mail da sua conta. Enviaremos um link para você criar
          uma nova senha.
        </p>

        {erro && <div className="flash-error">{erro}</div>}
        {mensagem && (
          <div
            className="flash-error"
            style={{ background: '#e6f7ed', color: '#137a45', borderColor: '#b7e4cd' }}
          >
            {mensagem}
          </div>
        )}

        {!enviado && (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>E-mail</label>
              <input
                type="email"
                className="form-control"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <button
              type="submit"
              className="save-button"
              style={{ width: '100%' }}
              disabled={enviando}
            >
              {enviando ? 'Enviando...' : 'Enviar link de redefinição'}
            </button>
          </form>
        )}

        <p style={{ marginTop: '1rem', textAlign: 'center' }}>
          Lembrou a senha? <Link to="/login">Voltar para o login</Link>
        </p>
      </div>
    </div>
  );
}

export default ForgotPassword;
