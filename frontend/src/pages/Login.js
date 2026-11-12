import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import PasswordToggleIcon from '../components/PasswordToggleIcon';

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const success = await login(email, password);
      if (success) navigate('/');
      else setError('Credenciais inválidas. Verifique e-mail e senha.');
    } catch (err) {
      const mensagem = err.response?.data?.error;
      setError(mensagem || 'Erro ao fazer login. Tente novamente.');
    }
  };

  return (
    <div className="auth-container">
      <span className="marca-cabecalho">
        <span className="marca-simbolo" aria-hidden="true">E</span>
        Exercita AI
      </span>
      <div className="auth-box">
        <h1 className="auth-titulo">Entrar</h1>
        <form onSubmit={handleSubmit}>
          {error && <div className="flash-error">{error}</div>}
          <div className="form-group">
            <label>E-mail</label>
            <input
              type="email"
              className="form-control"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Senha</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                className="form-control"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
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
            <div style={{ textAlign: 'right', marginTop: '0.4rem' }}>
              <Link to="/esqueci-senha" style={{ fontSize: '0.85rem' }}>
                Esqueci minha senha
              </Link>
            </div>
          </div>
          <button type="submit" className="save-button" style={{ width: '100%' }}>
            Entrar
          </button>
          <p style={{ marginTop: '1rem', textAlign: 'center' }}>
            Não tem uma conta? <Link to="/register">Registre-se</Link>
          </p>
        </form>
      </div>
    </div>
  );
}

export default Login;