import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [versaoChaves, setVersaoChaves] = useState(0);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      axios.get('/auth/current_user')
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('token');
          delete axios.defaults.headers.common['Authorization'];
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const refreshUser = async () => {
    try {
      const res = await axios.get('/auth/current_user');
      setUser(res.data);
      setVersaoChaves(v => v + 1);
      return res.data;
    } catch (err) {
      console.error('Erro ao atualizar dados do usuário:', err);
      return null;
    }
  };

  const login = async (email, password) => {
    const res = await axios.post('/auth/login', { email, password });
    if (res.data.success) {
      setUser(res.data.user);
      localStorage.setItem('token', res.data.token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${res.data.token}`;
      return true;
    }
    return false;
  };

  const logout = async () => {
    await axios.post('/auth/logout');
    setUser(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
  };

  const register = async (username, email, password) => {
    try {
      const res = await axios.post('/auth/register', { username, email, password });
      if (!res.data.success) return { success: false, error: res.data.error };
      try {
        const logado = await login(email, password);
        if (!logado) return { success: true, precisaLogin: true };
      } catch {
        return { success: true, precisaLogin: true };
      }
      return { success: true };
    } catch (err) {
      return { success: false, error: err.response?.data?.error || 'Erro ao registrar. Verifique os dados informados.' };
    }
  };

  const hasOllamaKey = !!(
    user && Array.isArray(user.ollama_keys) && user.ollama_keys.length > 0
  );

  return (
    <AuthContext.Provider value={{ user, loading, hasOllamaKey, versaoChaves, refreshUser, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
};