import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import PasswordToggleIcon from '../components/PasswordToggleIcon';

function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setEnviando(true);
    const result = await register(username, email, password);
    setEnviando(false);
    if (result.success) {
      navigate('/');
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="auth-container">
      <span className="marca-cabecalho">
        <span className="marca-simbolo" aria-hidden="true">E</span>
        Exercita AI
      </span>
      <div className="auth-box">
        <h1 className="auth-titulo">Criar conta</h1>
        <form onSubmit={handleSubmit}>
          {error && <div className="flash-error">{error}</div>}
          <div className="form-group">
            <label>Nome de usuário</label>
            <input
              type="text"
              className="form-control"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
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
          </div>
          <button type="submit" className="save-button" style={{ width: '100%' }} disabled={enviando}>
            {enviando ? 'Criando conta...' : 'Criar conta'}
          </button>
          <p style={{ marginTop: '1rem', textAlign: 'center' }}>
            Já tem uma conta? <Link to="/login">Faça login</Link>
          </p>
        </form>
      </div>
    </div>
  );
}

export default Register;