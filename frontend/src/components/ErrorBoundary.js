import React from 'react';
import TelaManutencao from './TelaManutencao';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Erro capturado:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <TelaManutencao recarregar />;
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
