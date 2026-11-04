import { useEffect, useState } from 'react';
import {
  EVENTO_SISTEMA_INDISPONIVEL,
  EVENTO_SISTEMA_DISPONIVEL,
  verificarSaude,
} from '../services/api';
import TelaManutencao from './TelaManutencao';

function MonitorDisponibilidade() {
  const [indisponivel, setIndisponivel] = useState(false);

  useEffect(() => {
    const aoIndisponivel = () => setIndisponivel(true);
    const aoDisponivel = () => setIndisponivel(false);
    window.addEventListener(EVENTO_SISTEMA_INDISPONIVEL, aoIndisponivel);
    window.addEventListener(EVENTO_SISTEMA_DISPONIVEL, aoDisponivel);
    return () => {
      window.removeEventListener(EVENTO_SISTEMA_INDISPONIVEL, aoIndisponivel);
      window.removeEventListener(EVENTO_SISTEMA_DISPONIVEL, aoDisponivel);
    };
  }, []);

  useEffect(() => {
    if (!indisponivel) return undefined;
    const verificar = async () => {
      try {
        await verificarSaude();
      } catch (err) {
        console.error('Sistema ainda indisponível:', err);
      }
    };
    const intervalo = setInterval(verificar, 15000);
    return () => clearInterval(intervalo);
  }, [indisponivel]);

  if (!indisponivel) return null;
  return <TelaManutencao recarregar />;
}

export default MonitorDisponibilidade;
