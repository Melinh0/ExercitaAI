import React, { useState, useEffect } from 'react';
import { IconeSetaEsquerda, IconeSetaDireita } from './Icons';

function Carousel({ slides, activeIndex, onIndexChange }) {
  const [internalIndex, setInternalIndex] = useState(0);
  const isControlled = typeof activeIndex === 'number';
  const index = isControlled ? activeIndex : internalIndex;

  useEffect(() => {
    if (!isControlled && slides && index >= slides.length) {
      setInternalIndex(0);
    }
  }, [slides, index, isControlled]);

  if (!slides || slides.length === 0) return null;

  const setIndex = (i) => {
    if (isControlled) {
      onIndexChange && onIndexChange(i);
    } else {
      setInternalIndex(i);
    }
  };

  const safeIndex = Math.min(index, slides.length - 1);
  const slide = slides[safeIndex];

  return (
    <div className="resolution-carousel">
      <div className="resolution-carousel-tabs">
        {slides.map((s, i) => (
          <button
            key={s.key || s.label}
            type="button"
            className={`carousel-tab-btn ${i === safeIndex ? 'active' : ''}`}
            onClick={() => setIndex(i)}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="resolution-carousel-body">{slide.content}</div>
      <div className="resolution-carousel-nav">
        <button
          type="button"
          onClick={() => setIndex(Math.max(0, safeIndex - 1))}
          disabled={safeIndex === 0}
        >
          <IconeSetaEsquerda size={16} />
        </button>
        <span className="resolution-carousel-counter">
          {safeIndex + 1} / {slides.length}
        </span>
        <button
          type="button"
          onClick={() => setIndex(Math.min(slides.length - 1, safeIndex + 1))}
          disabled={safeIndex === slides.length - 1}
        >
          <IconeSetaDireita size={16} />
        </button>
      </div>
    </div>
  );
}

export default Carousel;