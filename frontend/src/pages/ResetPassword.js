import React, { useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import PasswordToggleIcon from '../components/PasswordToggleIcon';

function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmacao, setConfirmacao] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [erro, setErro] = useState('');
  const [sucesso, setSucesso] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErro('');

    if (password !== confirmacao) {
      setErro('As senhas não conferem.');
      return;
    }
    if (password.length < 8) {
      setErro('A senha precisa de pelo menos 8 caracteres.');
      return;
    }

    setEnviando(true);
    try {
      const res = await axios.post('/auth/reset_password', {
        token,
        password,
        password_confirm: confirmacao,
      });
      if (res.data.success) {
        setSucesso(true);
        setTimeout(() => navigate('/login'), 2500);
      }
    } catch (err) {
      setErro(
        err.response?.data?.error ||
        'Não foi possível redefinir a senha. O link pode ter expirado.'
      );
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-box">
        <h1>Criar nova senha</h1>

        {erro && <div className="flash-error">{erro}</div>}

        {!token && (
          <div className="flash-error">
            Link de redefinição inválido. Solicite um novo na página
            “Esqueci minha senha”.
          </div>
        )}

        {sucesso && (
          <div
            className="flash-error"
            style={{ background: '#e6f7ed', color: '#137a45', borderColor: '#b7e4cd' }}
          >
            Senha redefinida com sucesso! Redirecionando para o login...
          </div>
        )}

        {token && !sucesso && (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Nova senha</label>
              <div className="password-input-wrapper">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="form-control"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  autoFocus
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  <PasswordToggleIcon visible={showPassword} />
                </button>
              </div>
            </div>
            <div className="form-group">
              <label>Confirmar nova senha</label>
              <div className="password-input-wrapper">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="form-control"
                  value={confirmacao}
                  onChange={(e) => setConfirmacao(e.target.value)}
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  <PasswordToggleIcon visible={showPassword} />
                </button>
              </div>
            </div>
            <button
              type="submit"
              className="save-button"
              style={{ width: '100%' }}
              disabled={enviando}
            >
              {enviando ? 'Salvando...' : 'Redefinir senha'}
            </button>
          </form>
        )}

        <p style={{ marginTop: '1rem', textAlign: 'center' }}>
          <Link to="/login">Voltar para o login</Link>
        </p>
      </div>
    </div>
  );
}

export default ResetPassword;
