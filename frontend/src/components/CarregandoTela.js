import React from 'react';

function CarregandoTela({ rotulo = 'Carregando...' }) {
  return (
    <div className="carregando-tela" role="status" aria-live="polite">
      <span className="carregando-girar" aria-hidden="true" />
      <p>{rotulo}</p>
    </div>
  );
}

export default CarregandoTela;
