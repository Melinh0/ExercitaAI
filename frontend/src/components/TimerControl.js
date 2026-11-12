import React, { useState, useEffect, useRef } from 'react';
import { useConfirm } from '../contexts/ConfirmContext';

function TimerControl() {
  const { alert } = useConfirm();
  const [minutes, setMinutes] = useState(25);
  const [timeLeft, setTimeLeft] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(() => {
        setTimeLeft(prev => {
          if (prev === null || prev <= 1) {
            clearInterval(intervalRef.current);
            setIsRunning(false);
            alert({
              title: 'Tempo de estudo concluído',
              message: 'Seu tempo de estudo acabou. Faça uma pausa e retorne quando estiver descansado.',
              variant: 'success',
            });
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [isRunning, alert]);

  const startTimer = () => {
    if (minutes <= 0) {
      alert({
        title: 'Tempo inválido',
        message: 'Defina um tempo válido (mínimo 1 minuto).',
        variant: 'warning',
      });
      return;
    }
    if (timeLeft === null || timeLeft === 0) {
      setTimeLeft(minutes * 60);
    }
    setIsRunning(true);
  };

  const pauseTimer = () => {
    setIsRunning(false);
  };

  const resetTimer = () => {
    setIsRunning(false);
    setTimeLeft(null);
    setMinutes(25);
  };

  const formatTime = (seconds) => {
    if (seconds === null) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="timer-control">
      {timeLeft !== null ? (
        <>
          <span className="timer-digits">{formatTime(timeLeft)}</span>
          {isRunning ? (
            <button onClick={pauseTimer} className="button timer-button">Pausar</button>
          ) : (
            <button onClick={startTimer} className="button timer-button">Iniciar</button>
          )}
          <button onClick={resetTimer} className="button timer-button reset">Reset</button>
        </>
      ) : (
        <>
          <input type="number" min="1" max="180" value={minutes} onChange={(e) => setMinutes(parseInt(e.target.value))} className="timer-input" />
          <span className="timer-label">min</span>
          <button onClick={startTimer} className="button timer-button">Iniciar Estudo</button>
        </>
      )}
    </div>
  );
}

export default TimerControl;