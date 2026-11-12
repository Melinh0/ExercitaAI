import React from 'react';

function TelaManutencao({ recarregar = false }) {
  return (
    <div className="manutencao-tela" role="alert">
      <img src="/favicon.svg" alt="Exercita AI" className="manutencao-logo" />
      <h1 className="manutencao-titulo">Exercita AI</h1>
      <h2 className="manutencao-subtitulo">Sistema em manutenção</h2>
      <p className="manutencao-texto">
        Estamos realizando uma manutenção para melhorar o sistema. O acesso
        está temporariamente indisponível; tente novamente em instantes.
      </p>
      {recarregar && (
        <button
          type="button"
          className="save-button manutencao-botao"
          onClick={() => window.location.reload()}
        >
          Tentar novamente
        </button>
      )}
    </div>
  );
}

export default TelaManutencao;
