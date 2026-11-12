import React, { lazy, Suspense, useLayoutEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { TaskProvider } from './contexts/TaskContext';
import { ConfirmProvider } from './contexts/ConfirmContext';
import { ToastProvider } from './contexts/ToastContext';
import ErrorBoundary from './components/ErrorBoundary';
import MonitorDisponibilidade from './components/MonitorDisponibilidade';
import CarregandoTela from './components/CarregandoTela';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import './App.css';

const TopicsList = lazy(() => import('./pages/TopicsList'));
const TopicView = lazy(() => import('./pages/TopicView'));

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <CarregandoTela rotulo="Verificando sua sessão..." />;
  return user ? children : <Navigate to="/login" />;
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <ConfirmProvider>
            <TaskProvider>
              <Router>
                <ScrollToTop />
                <ErrorBoundary>
                  <Suspense fallback={<CarregandoTela />}>
                    <Routes>
                      <Route path="/login" element={<Login />} />
                      <Route path="/register" element={<Register />} />
                      <Route path="/esqueci-senha" element={<ForgotPassword />} />
                      <Route path="/redefinir-senha" element={<ResetPassword />} />
                      <Route path="/" element={<PrivateRoute><TopicsList /></PrivateRoute>} />
                      <Route path="/topic/:topicName" element={<PrivateRoute><TopicView /></PrivateRoute>} />
                      <Route path="*" element={<Navigate to="/" />} />
                    </Routes>
                  </Suspense>
                  <MonitorDisponibilidade />
                </ErrorBoundary>
              </Router>
            </TaskProvider>
          </ConfirmProvider>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;