import React, { useRef, useEffect, useState, useCallback, useLayoutEffect } from 'react';
import { useConfirm } from '../contexts/ConfirmContext';
import { IconeSol, IconeLua, IconeTelaCheia, IconeSairTelaCheia, IconeChevronEsquerda, IconeChevronDireita } from './Icons';

const quebrarTexto = (ctx, texto, larguraMax) => {
  const partirLongo = (palavra) => {
    const pedacos = [];
    let atual = '';
    for (const ch of palavra) {
      if (ctx.measureText(atual + ch).width <= larguraMax || !atual) {
        atual += ch;
      } else {
        pedacos.push(atual);
        atual = ch;
      }
    }
    if (atual) pedacos.push(atual);
    return pedacos;
  };
  const linhas = [];
  for (const paragrafo of (texto || '').split('\n')) {
    let atual = '';
    for (const palavra of paragrafo.split(' ')) {
      const teste = atual ? `${atual} ${palavra}` : palavra;
      if (ctx.measureText(teste).width <= larguraMax || !atual) {
        atual = teste;
      } else {
        linhas.push(atual);
        atual = palavra;
      }
    }
    if (ctx.measureText(atual).width > larguraMax) {
      linhas.push(...partirLongo(atual));
    } else {
      linhas.push(atual);
    }
  }
  return linhas;
};

const contornarForma = (ctx, bl) => {
  ctx.beginPath();
  if (bl.forma === 'circulo') {
    ctx.ellipse(bl.x + bl.w / 2, bl.y + bl.h / 2, bl.w / 2, bl.h / 2, 0, 0, Math.PI * 2);
  } else if (bl.forma === 'triangulo') {
    ctx.moveTo(bl.x + bl.w / 2, bl.y);
    ctx.lineTo(bl.x + bl.w, bl.y + bl.h);
    ctx.lineTo(bl.x, bl.y + bl.h);
    ctx.closePath();
  } else {
    ctx.rect(bl.x, bl.y, bl.w, bl.h);
  }
  ctx.stroke();
};

const larguraAcomodada = (bl) => {
  if (bl.forma === 'circulo') return Math.max(24, Math.round(bl.w * 0.6));
  if (bl.forma === 'triangulo') return Math.max(24, Math.round(bl.w * 0.4));
  return Math.max(24, bl.w - 16);
};

const desenharSeta = (ctx, ponta, traseira, cor) => {
  const ang = Math.atan2(ponta.y - traseira.y, ponta.x - traseira.x) + Math.PI;
  const tamanho = 11;
  const a1 = ang - 0.42;
  const a2 = ang + 0.42;
  ctx.fillStyle = cor;
  ctx.beginPath();
  ctx.moveTo(ponta.x, ponta.y);
  ctx.lineTo(ponta.x + Math.cos(a1) * tamanho, ponta.y + Math.sin(a1) * tamanho);
  ctx.lineTo(ponta.x + Math.cos(a2) * tamanho, ponta.y + Math.sin(a2) * tamanho);
  ctx.closePath();
  ctx.fill();
};

const distanciaAoSegmento = (p, a, b) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const compr2 = dx * dx + dy * dy;
  if (compr2 === 0) return Math.hypot(p.x - a.x, p.y - a.y);
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / compr2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
};

const JSON_VAZIO = JSON.stringify({ strokes: [], blocos: [], setas: [], imagens: [] });

const carregarVetores = (chave) => {
  if (!chave) return null;
  try {
    const dados = JSON.parse(localStorage.getItem(`quadro:${chave}`) || 'null');
    if (dados && dados.v === 1) return dados;
  } catch (e) {}
  return null;
};

const prepararImagens = (lista, aoCarregar) => (lista || [])
  .filter(o => o && o.src)
  .map(o => {
    const im = new Image();
    im.onload = aoCarregar;
    im.src = o.src;
    return { img: im, src: o.src, originalWidth: o.originalWidth, originalHeight: o.originalHeight, x: o.x, y: o.y, scale: o.scale };
  });

const clonarStrokes = (lista) => (lista || []).map(s => ({
  ...s,
  points: (s.points || []).map(p => ({ ...p }))
}));

function Whiteboard({ initialImage, onSave, onAutoSave, chave }) {
  const { alert } = useConfirm();
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const whiteboardContainerRef = useRef(null);
  const ctxRef = useRef(null);
  const canvasSizeRef = useRef({ width: 0, height: 0 });
  const dprRef = useRef(1);
  const redrawAllRef = useRef(null);

  const inicioRef = useRef(null);
  if (inicioRef.current === null) {
    const dados = carregarVetores(chave);
    inicioRef.current = {
      hidratou: !!dados,
      strokes: clonarStrokes(dados && dados.strokes),
      blocos: ((dados && dados.blocos) || []).map(b => ({ ...b })),
      setas: ((dados && dados.setas) || []).map(s => ({ ...s })),
      imagens: (dados && dados.imagens) || []
    };
  }
  const inicio = inicioRef.current;
  const recarregarImagem = useCallback(() => {
    redrawAllRef.current && redrawAllRef.current();
  }, []);

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [toolbarVisible, setToolbarVisible] = useState(true);
  const [imageLoadError, setImageLoadError] = useState(false);
  const [backgroundImage, setBackgroundImage] = useState(null);
  const [imageObjects, setImageObjects] = useState(() => prepararImagens(inicio.imagens, recarregarImagem));
  const [selectedImageIndex, setSelectedImageIndex] = useState(-1);

  const [color, setColor] = useState('black');
  const [brushSize, setBrushSize] = useState(3);
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentPoints, setCurrentPoints] = useState([]);
  const [strokes, setStrokes] = useState(inicio.strokes);

  const [ferramenta, setFerramenta] = useState('selecionar');
  const [isDragging, setIsDragging] = useState(false);
  const [dragType, setDragType] = useState(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [dragStartProps, setDragStartProps] = useState({ x: 0, y: 0, scale: 1 });

  const [blocos, setBlocos] = useState(inicio.blocos);
  const [setas, setSetas] = useState(inicio.setas);
  const [setaPreview, setSetaPreview] = useState(null);
  const [blocoEditando, setBlocoEditando] = useState(null);
  const [rascunhoTexto, setRascunhoTexto] = useState('');
  const [blocoSelecionado, setBlocoSelecionado] = useState(null);
  const [setaSelecionada, setSetaSelecionada] = useState(null);
  const [tamanhoTexto, setTamanhoTexto] = useState(14);
  const [arrastoBloco, setArrastoBloco] = useState(null);
  const [arrastoSeta, setArrastoSeta] = useState(null);
  const [formaCriacao, setFormaCriacao] = useState('texto');

  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('whiteboardDarkMode');
    if (saved !== null) return saved === 'true';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  const imageObjectsRef = useRef(imageObjects);
  const selectedImageIndexRef = useRef(selectedImageIndex);
  const strokesRef = useRef(strokes);
  const backgroundImageRef = useRef(backgroundImage);
  const initialImageRef = useRef(initialImage);
  const blocosRef = useRef(blocos);
  const setasRef = useRef(setas);
  const setaPreviewRef = useRef(setaPreview);
  const blocoSelecionadoRef = useRef(blocoSelecionado);
  const setaSelecionadaRef = useRef(setaSelecionada);
  const ferramentaRef = useRef(ferramenta);
  const editandoRef = useRef(blocoEditando);
  const textareaRef = useRef(null);
  const cursorPincelRef = useRef(null);
  const persistenciaRef = useRef(null);
  if (persistenciaRef.current === null) {
    persistenciaRef.current = {
      pronta: true,
      hidratou: inicio.hidratou,
      json: chave
        ? (inicio.hidratou
          ? JSON.stringify({ strokes: inicio.strokes, blocos: inicio.blocos, setas: inicio.setas, imagens: inicio.imagens })
          : null)
        : undefined,
      ultimoSalvo: null
    };
  }
  const pendenteRef = useRef(null);
  const primeiraHidratacaoRef = useRef(true);
  const pngPendenteRef = useRef(null);

  useEffect(() => {
    imageObjectsRef.current = imageObjects;
    selectedImageIndexRef.current = selectedImageIndex;
    strokesRef.current = strokes;
    backgroundImageRef.current = backgroundImage;
    initialImageRef.current = initialImage;
    blocosRef.current = blocos;
    setasRef.current = setas;
    setaPreviewRef.current = setaPreview;
    blocoSelecionadoRef.current = blocoSelecionado;
    setaSelecionadaRef.current = setaSelecionada;
    ferramentaRef.current = ferramenta;
    editandoRef.current = blocoEditando;
  }, [imageObjects, selectedImageIndex, strokes, darkMode, backgroundImage, initialImage, blocos, setas, setaPreview, blocoSelecionado, setaSelecionada, ferramenta, blocoEditando]);

  useLayoutEffect(() => {
    if (redrawAllRef.current) redrawAllRef.current();
  }, [darkMode]);

  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = 'auto';
    textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
  }, [rascunhoTexto, blocoEditando]);

  const ferramentaDesenho = ferramenta === 'pincel' || ferramenta === 'borracha';

  useEffect(() => {
    if (cursorPincelRef.current && (!ferramentaDesenho || blocoEditando)) {
      cursorPincelRef.current.style.display = 'none';
    }
  }, [ferramentaDesenho, blocoEditando]);

  const HANDLE_SIZE = 15;

  const getBackgroundColor = useCallback((darkMode) => {
    if (darkMode) {
      return '#1e293b';
    }
    return '#ffffff';
  }, []);

  const getEffectiveColor = useCallback((selectedColor, darkMode) => {
    if (selectedColor === 'eraser') return getBackgroundColor(darkMode);
    if (selectedColor === 'white' || selectedColor === '#ffffff') {
      return '#000000';
    }
    if (darkMode && selectedColor === 'black') {
      return '#ffffff';
    }
    return selectedColor;
  }, []);

  const corSelecao = useCallback((darkMode) => (darkMode ? '#90caf9' : '#1e3a8a'), []);

  const redrawAll = useCallback(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const { width, height } = canvasSizeRef.current;
    if (width === 0 || height === 0) return;

    const bg = getBackgroundColor(darkMode);
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, width, height);

    const bgImg = backgroundImageRef.current;
    if (bgImg && bgImg.img) {
      ctx.drawImage(bgImg.img, bgImg.x, bgImg.y, bgImg.width, bgImg.height);
    }

    for (let obj of imageObjectsRef.current) {
      if (!obj.img) continue;
      const w = obj.originalWidth * obj.scale;
      const h = obj.originalHeight * obj.scale;
      ctx.drawImage(obj.img, obj.x, obj.y, w, h);
    }

    for (let stroke of strokesRef.current) {
      ctx.beginPath();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.lineWidth = stroke.size;
      ctx.globalCompositeOperation = 'source-over';
      if (stroke.color === 'eraser') {
        ctx.strokeStyle = getBackgroundColor(darkMode);
      } else {
        ctx.strokeStyle = getEffectiveColor(stroke.color, darkMode);
      }
      const pts = stroke.points;
      if (pts.length === 0) continue;
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i].x, pts[i].y);
      }
      ctx.stroke();
    }
    ctx.globalCompositeOperation = 'source-over';

    const selIdx = selectedImageIndexRef.current;
    if (selIdx >= 0 && selIdx < imageObjectsRef.current.length) {
      const obj = imageObjectsRef.current[selIdx];
      const w = obj.originalWidth * obj.scale;
      const h = obj.originalHeight * obj.scale;
      ctx.strokeStyle = darkMode ? '#90caf9' : 'blue';
      ctx.lineWidth = 2;
      ctx.strokeRect(obj.x, obj.y, w, h);
      ctx.fillStyle = darkMode ? '#90caf9' : 'blue';
      const s = HANDLE_SIZE;
      ctx.fillRect(obj.x - s / 2, obj.y - s / 2, s, s);
      ctx.fillRect(obj.x + w - s / 2, obj.y - s / 2, s, s);
      ctx.fillRect(obj.x - s / 2, obj.y + h - s / 2, s, s);
      ctx.fillRect(obj.x + w - s / 2, obj.y + h - s / 2, s, s);
    }

    const desenharSetaLivre = (s, cor) => {
      ctx.beginPath();
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2;
      ctx.moveTo(s.x1, s.y1);
      ctx.lineTo(s.x2, s.y2);
      ctx.stroke();
      desenharSeta(ctx, { x: s.x2, y: s.y2 }, { x: s.x1, y: s.y1 }, cor);
    };

    for (const s of setasRef.current) {
      desenharSetaLivre(s, getEffectiveColor(s.cor, darkMode));
    }

    const preview = setaPreviewRef.current;
    if (preview) {
      desenharSetaLivre(preview, getEffectiveColor(preview.cor, darkMode));
    }

    const sSel = setasRef.current.find(s => s.id === setaSelecionadaRef.current);
    if (sSel) {
      const cor = corSelecao(darkMode);
      ctx.beginPath();
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 3]);
      ctx.moveTo(sSel.x1, sSel.y1);
      ctx.lineTo(sSel.x2, sSel.y2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = cor;
      const s = 9;
      ctx.fillRect(sSel.x1 - s / 2, sSel.y1 - s / 2, s, s);
      ctx.fillRect(sSel.x2 - s / 2, sSel.y2 - s / 2, s, s);
    }

    ctx.textBaseline = 'top';
    for (const bl of blocosRef.current) {
      const ehTexto = !bl.forma || bl.forma === 'texto' || bl.forma === 'textoSolto';
      const ehRedonda = bl.forma === 'circulo' || bl.forma === 'triangulo';
      const ehRetangulo = bl.forma === 'retangulo' || bl.forma === 'quadrado';
      const ehTextoSolto = bl.forma === 'textoSolto';
      ctx.font = `${bl.tamanho}px sans-serif`;
      const linhas = quebrarTexto(ctx, bl.texto, larguraAcomodada(bl));
      const alturaLinha = Math.round(bl.tamanho * 1.3);
      const alturaTexto = linhas.length * alturaLinha;
      if (!ehTextoSolto && ehTexto) {
        bl.h = Math.max(bl.hUser || 0, alturaTexto + 16);
      }
      if (ehRetangulo) {
        bl.h = Math.max(bl.hUser || 0, alturaTexto + 16);
      }
      const corBloco = getEffectiveColor(bl.cor, darkMode);
      if (!ehTextoSolto && (ehTexto || ehRetangulo)) {
        ctx.fillStyle = getBackgroundColor(darkMode);
        ctx.fillRect(bl.x, bl.y, bl.w, bl.h);
        ctx.strokeStyle = corBloco;
        ctx.lineWidth = 1.5;
        contornarForma(ctx, bl);
      }
      ctx.fillStyle = corBloco;
      if (ehTextoSolto) {
        linhas.forEach((linha, i) => {
          ctx.fillText(linha, bl.x, bl.y + i * alturaLinha);
        });
      } else {
        linhas.forEach((linha, i) => {
          ctx.fillText(linha, bl.x + 8, bl.y + 8 + i * alturaLinha);
        });
      }
    }

    const blocoSel = blocosRef.current.find(b => b.id === blocoSelecionadoRef.current);
    if (blocoSel) {
      ctx.strokeStyle = corSelecao(darkMode);
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 3]);
      ctx.strokeRect(blocoSel.x - 3, blocoSel.y - 3, blocoSel.w + 6, (blocoSel.h || 40) + 6);
      ctx.setLineDash([]);
      ctx.fillStyle = corSelecao(darkMode);
      ctx.fillRect(blocoSel.x + blocoSel.w - 5, blocoSel.y + (blocoSel.h || 40) - 5, 10, 10);
    }
  }, [getBackgroundColor, getEffectiveColor, corSelecao, darkMode]);

  useEffect(() => {
    redrawAllRef.current = redrawAll;
  }, [redrawAll]);

  const renderToDataURL = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return '';
    return canvas.toDataURL('image/png');
  }, []);

  const resizeCanvas = useCallback(() => {
    const container = whiteboardContainerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const rect = container.getBoundingClientRect();
    if (Math.floor(rect.width) < 2 || Math.floor(rect.height) < 2) return;
    const cssWidth = Math.max(1, Math.floor(rect.width));
    const cssHeight = Math.max(1, Math.floor(rect.height));

    const dpr = window.devicePixelRatio || 1;

    const oldWidth = canvasSizeRef.current.width;
    const oldHeight = canvasSizeRef.current.height;
    const oldDpr = dprRef.current;

    if (oldWidth === cssWidth && oldHeight === cssHeight && oldDpr === dpr) {
      return;
    }

    canvas.width = Math.floor(cssWidth * dpr);
    canvas.height = Math.floor(cssHeight * dpr);
    canvas.style.width = cssWidth + 'px';
    canvas.style.height = cssHeight + 'px';

    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctxRef.current = ctx;

    canvasSizeRef.current = { width: cssWidth, height: cssHeight };
    dprRef.current = dpr;

    if (pngPendenteRef.current) {
      const posicionar = pngPendenteRef.current;
      pngPendenteRef.current = null;
      posicionar();
    }

    redrawAllRef.current && redrawAllRef.current();
  }, []);

  const jsonPayload = useCallback(() => ({
    strokes: strokesRef.current.map(s => ({
      color: s.color,
      size: s.size,
      points: s.points.map(p => ({ x: Math.round(p.x), y: Math.round(p.y) }))
    })),
    blocos: blocosRef.current.map(b => ({
      id: b.id,
      x: Math.round(b.x),
      y: Math.round(b.y),
      w: Math.round(b.w),
      h: Math.round(b.h || 0),
      hUser: Math.round(b.hUser || 0),
      texto: b.texto || '',
      tamanho: Math.round(b.tamanho),
      cor: b.cor,
      forma: b.forma,
      tipo: b.tipo,
      resposta: b.resposta || '',
      explicacao: b.explicacao || '',
      enunciado: b.enunciado || '',
      whiteboard_img: b.whiteboard_img || ''
    })),
    setas: setasRef.current.map(s => ({
      id: s.id,
      x1: Math.round(s.x1),
      y1: Math.round(s.y1),
      x2: Math.round(s.x2),
      y2: Math.round(s.y2),
      cor: s.cor
    })),
    imagens: imageObjectsRef.current.map(o => ({
      src: typeof o.src === 'string' ? o.src : null,
      originalWidth: Math.round(o.originalWidth),
      originalHeight: Math.round(o.originalHeight),
      x: Math.round(o.x),
      y: Math.round(o.y),
      scale: Math.round(o.scale * 100) / 100
    }))
  }), []);

  const carregarPng = useCallback((url) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';

    const positionImage = () => {
      const { width, height } = canvasSizeRef.current;
      if (width === 0 || height === 0) return false;
      const escala = Math.min(width / img.width, height / img.height, 1);
      const w = img.width * escala;
      const h = img.height * escala;
      const x = (width - w) / 2;
      const y = (height - h) / 2;
      const bg = { img, x, y, width: w, height: h };
      backgroundImageRef.current = bg;
      setBackgroundImage(bg);
      redrawAllRef.current && redrawAllRef.current();
      return true;
    };

    img.onload = () => {
      if (!positionImage()) {
        pngPendenteRef.current = positionImage;
      }
      setImageLoadError(false);
    };

    img.onerror = () => {
      console.error('Erro ao carregar imagem do quadro branco');
      setImageLoadError(true);
    };

    img.src = url;
  }, []);

  useEffect(() => {
    if (primeiraHidratacaoRef.current) {
      primeiraHidratacaoRef.current = false;
      return;
    }
    if (pendenteRef.current) {
      pendenteRef.current();
      pendenteRef.current = null;
    }
    persistenciaRef.current.pronta = false;
    persistenciaRef.current.json = null;
    persistenciaRef.current.hidratou = false;
    setBackgroundImage(null);
    setImageLoadError(false);
    setBlocoSelecionado(null);
    setSetaSelecionada(null);
    setSetaPreview(null);
    setArrastoBloco(null);
    setArrastoSeta(null);
    setSelectedImageIndex(-1);
    selectedImageIndexRef.current = -1;
    setBlocoEditando(null);
    editandoRef.current = null;

    const dados = carregarVetores(chave);

    if (dados) {
      const blocosCarregados = (dados.blocos || []).map(b => ({ ...b }));
      const setasCarregadas = (dados.setas || []).map(s => ({ ...s }));
      const strokesCarregados = clonarStrokes(dados.strokes);
      const imagensCarregadas = prepararImagens(dados.imagens, recarregarImagem);
      persistenciaRef.current.pronta = true;
      persistenciaRef.current.hidratou = true;
      persistenciaRef.current.json = JSON.stringify({
        strokes: strokesCarregados,
        blocos: blocosCarregados,
        setas: setasCarregadas,
        imagens: imagensCarregadas.map(({ img, ...resto }) => resto)
      });
      persistenciaRef.current.ultimoSalvo = persistenciaRef.current.json;
      setStrokes(strokesCarregados);
      setBlocos(blocosCarregados);
      setSetas(setasCarregadas);
      setImageObjects(imagensCarregadas);
    } else {
      persistenciaRef.current.pronta = true;
      persistenciaRef.current.json = chave ? null : undefined;
      persistenciaRef.current.ultimoSalvo = JSON.stringify({ strokes: [], blocos: [], setas: [], imagens: [] });
      setStrokes([]);
      setBlocos([]);
      setSetas([]);
      setImageObjects([]);
      if (initialImageRef.current) carregarPng(initialImageRef.current);
    }
  }, [chave]);

  useEffect(() => {
    if (!chave || !persistenciaRef.current.pronta) return;
    const base = persistenciaRef.current.json;
    const atual = JSON.stringify(jsonPayload());
    if (base !== null && base === atual) {
      pendenteRef.current = null;
      return;
    }
    if (base === null && atual === JSON_VAZIO) {
      pendenteRef.current = null;
      return;
    }
    pendenteRef.current = () => {
      const payload = { v: 1, ...jsonPayload() };
      try {
        localStorage.setItem(`quadro:${chave}`, JSON.stringify(payload));
      } catch (e) {
        try {
          localStorage.setItem(`quadro:${chave}`, JSON.stringify({ ...payload, imagens: [] }));
        } catch (e2) {}
      }
      persistenciaRef.current.json = JSON.stringify(payload);
    };
    const t = setTimeout(() => {
      if (pendenteRef.current) {
        pendenteRef.current();
        pendenteRef.current = null;
      }
    }, 700);
    return () => clearTimeout(t);
  }, [chave, strokes, blocos, setas, imageObjects, jsonPayload]);

  useEffect(() => {
    if (!chave) return undefined;
    let timeoutId;
    const salvar = () => {
      const dataURL = renderToDataURL();
      if (onAutoSave) onAutoSave(dataURL);
    };
    const payloadAtual = JSON.stringify(jsonPayload());
    if (persistenciaRef.current.ultimoSalvo !== payloadAtual) {
      timeoutId = setTimeout(() => {
        salvar();
        persistenciaRef.current.ultimoSalvo = payloadAtual;
      }, 1500);
    }
    return () => clearTimeout(timeoutId);
  }, [chave, strokes, blocos, setas, imageObjects, jsonPayload, onAutoSave]);

  useEffect(() => () => {
    if (pendenteRef.current) {
      pendenteRef.current();
      pendenteRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!initialImage) return;
    if (persistenciaRef.current.hidratou) return;
    carregarPng(initialImage);
  }, [initialImage, carregarPng]);

  useEffect(() => {
    redrawAllRef.current && redrawAllRef.current();
  }, [redrawAll, darkMode, imageObjects, selectedImageIndex, backgroundImage, blocos, setas, setaPreview, blocoSelecionado, setaSelecionada]);

  useEffect(() => {
    resizeCanvas();

    const container = whiteboardContainerRef.current;
    if (!container) return;

    let rafId = null;
    const resizeObserver = new ResizeObserver(() => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        resizeCanvas();
      });
    });
    resizeObserver.observe(container);

    const onWindowResize = () => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => resizeCanvas());
    };
    window.addEventListener('resize', onWindowResize);

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      window.removeEventListener('resize', onWindowResize);
    };
  }, [resizeCanvas]);

  const getCanvasCoords = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }, []);

  const acharBloco = useCallback((coords) => {
    const lista = blocosRef.current;
    for (let i = lista.length - 1; i >= 0; i--) {
      const bl = lista[i];
      const h = bl.h || 40;
      if (bl.forma === 'circulo') {
        const dx = (coords.x - (bl.x + bl.w / 2)) / (bl.w / 2);
        const dy = (coords.y - (bl.y + h / 2)) / (h / 2);
        if (dx * dx + dy * dy <= 1) return bl;
      } else if (coords.x >= bl.x && coords.x <= bl.x + bl.w && coords.y >= bl.y && coords.y <= bl.y + h) {
        return bl;
      }
    }
    return null;
  }, []);

  const acharSeta = useCallback((coords) => {
    const lista = setasRef.current;
    for (let i = lista.length - 1; i >= 0; i--) {
      const s = lista[i];
      const d = distanciaAoSegmento(coords, { x: s.x1, y: s.y1 }, { x: s.x2, y: s.y2 });
      if (d <= 8) return s;
    }
    return null;
  }, []);

  const alcaDeSeta = useCallback((coords) => {
    const s = setasRef.current.find(x => x.id === setaSelecionadaRef.current);
    if (!s) return null;
    if (Math.abs(coords.x - s.x1) <= HANDLE_SIZE && Math.abs(coords.y - s.y1) <= HANDLE_SIZE) return 'inicio';
    if (Math.abs(coords.x - s.x2) <= HANDLE_SIZE && Math.abs(coords.y - s.y2) <= HANDLE_SIZE) return 'fim';
    return null;
  }, []);

  const limparSelecoes = useCallback(() => {
    setBlocoSelecionado(null);
    setSetaSelecionada(null);
    if (selectedImageIndexRef.current !== -1) {
      setSelectedImageIndex(-1);
      selectedImageIndexRef.current = -1;
    }
  }, []);

  const handlePointerDown = useCallback((e) => {
    if (editandoRef.current) return;
    e.preventDefault();
    try { e.target.setPointerCapture(e.pointerId); } catch (err) {}
    const coords = getCanvasCoords(e);

    if (ferramenta === 'pincel' || ferramenta === 'borracha') {
      limparSelecoes();
      setIsDrawing(true);
      setCurrentPoints([coords]);
      return;
    }

    const selAtual = blocosRef.current.find(b => b.id === blocoSelecionadoRef.current);
    if (selAtual) {
      const hSel = selAtual.h || 40;
      const noCanto = Math.abs(coords.x - (selAtual.x + selAtual.w)) <= HANDLE_SIZE
        && Math.abs(coords.y - (selAtual.y + hSel)) <= HANDLE_SIZE;
      if (noCanto) {
        setArrastoBloco({
          id: selAtual.id,
          modo: 'redimensionar',
          x0: selAtual.x,
          y0: selAtual.y,
          w0: selAtual.w,
          h0: hSel,
          t0: selAtual.tamanho,
          cx: coords.x,
          cy: coords.y,
        });
        return;
      }
    }

    const alca = alcaDeSeta(coords);
    if (alca) {
      const s = setasRef.current.find(x => x.id === setaSelecionadaRef.current);
      setArrastoSeta({
        id: s.id,
        modo: alca === 'inicio' ? 'ponta-inicio' : 'ponta-fim',
        x1: s.x1, y1: s.y1, x2: s.x2, y2: s.y2,
        cx: coords.x,
        cy: coords.y,
      });
      return;
    }

    const blocoAlvo = acharBloco(coords);
    if (blocoAlvo) {
      setBlocoSelecionado(blocoAlvo.id);
      setSetaSelecionada(null);
      if (selectedImageIndexRef.current !== -1) {
        setSelectedImageIndex(-1);
        selectedImageIndexRef.current = -1;
      }
      setArrastoBloco({
        id: blocoAlvo.id,
        modo: 'mover',
        x0: blocoAlvo.x,
        y0: blocoAlvo.y,
        w0: blocoAlvo.w,
        h0: blocoAlvo.h || 40,
        cx: coords.x,
        cy: coords.y,
      });
      return;
    }

    const setaAlvo = acharSeta(coords);
    if (setaAlvo) {
      setSetaSelecionada(setaAlvo.id);
      setBlocoSelecionado(null);
      if (selectedImageIndexRef.current !== -1) {
        setSelectedImageIndex(-1);
        selectedImageIndexRef.current = -1;
      }
      setArrastoSeta({
        id: setaAlvo.id,
        modo: 'mover',
        x1: setaAlvo.x1, y1: setaAlvo.y1, x2: setaAlvo.x2, y2: setaAlvo.y2,
        cx: coords.x,
        cy: coords.y,
      });
      return;
    }

    let hitIdx = -1, hitType = null;
    const imgs = imageObjectsRef.current;
    const selIdx = selectedImageIndexRef.current;

    for (let i = imgs.length - 1; i >= 0; i--) {
      const obj = imgs[i];
      const w = obj.originalWidth * obj.scale;
      const h = obj.originalHeight * obj.scale;
      if (i === selIdx) {
        if (Math.abs(coords.x - obj.x) < HANDLE_SIZE && Math.abs(coords.y - obj.y) < HANDLE_SIZE) {
          hitType = 'resize-tl'; hitIdx = i; break;
        } else if (Math.abs(coords.x - (obj.x + w)) < HANDLE_SIZE && Math.abs(coords.y - obj.y) < HANDLE_SIZE) {
          hitType = 'resize-tr'; hitIdx = i; break;
        } else if (Math.abs(coords.x - obj.x) < HANDLE_SIZE && Math.abs(coords.y - (obj.y + h)) < HANDLE_SIZE) {
          hitType = 'resize-bl'; hitIdx = i; break;
        } else if (Math.abs(coords.x - (obj.x + w)) < HANDLE_SIZE && Math.abs(coords.y - (obj.y + h)) < HANDLE_SIZE) {
          hitType = 'resize-br'; hitIdx = i; break;
        } else if (coords.x >= obj.x && coords.x <= obj.x + w && coords.y >= obj.y && coords.y <= obj.y + h) {
          hitType = 'move'; hitIdx = i; break;
        }
      } else {
        if (coords.x >= obj.x && coords.x <= obj.x + w && coords.y >= obj.y && coords.y <= obj.y + h) {
          hitType = 'select'; hitIdx = i; break;
        }
      }
    }

    if (hitIdx !== -1) {
      setSelectedImageIndex(hitIdx);
      setBlocoSelecionado(null);
      setSetaSelecionada(null);
      if (hitType !== 'select') {
        setIsDragging(true);
        setDragType(hitType);
        setDragStart(coords);
        const obj = imgs[hitIdx];
        setDragStartProps({ x: obj.x, y: obj.y, scale: obj.scale });
      }
      return;
    }

    limparSelecoes();

    if (ferramenta === 'texto' && formaCriacao === 'seta') {
      setSetaPreview({ x1: coords.x, y1: coords.y, x2: coords.x, y2: coords.y, cor: color });
      setArrastoSeta({ id: 'preview', modo: 'desenhar', x1: coords.x, y1: coords.y, cor: color, cx: coords.x, cy: coords.y });
      return;
    }

    if (ferramenta !== 'texto') return;

    const medidas = {
      textoSolto: { w: 200, h: tamanhoTexto + 8 },
      texto: { w: 180, h: Math.round(tamanhoTexto * 1.3) + 16 },
      retangulo: { w: 180, h: 110 },
      quadrado: { w: 140, h: 140 },
      circulo: { w: 150, h: 120 },
      triangulo: { w: 160, h: 130 },
    };
    const med = medidas[formaCriacao] || medidas.texto;
    const novo = {
      id: `b${Date.now()}`,
      x: Math.round(coords.x),
      y: Math.round(coords.y),
      w: med.w,
      h: med.h,
      hUser: med.h,
      texto: '',
      tamanho: tamanhoTexto,
      cor: color,
      forma: formaCriacao,
    };
    blocosRef.current = [...blocosRef.current, novo];
    setBlocos(blocosRef.current);
    setBlocoSelecionado(novo.id);
    setRascunhoTexto('');
    setBlocoEditando(novo.id);
    editandoRef.current = novo.id;
  }, [getCanvasCoords, acharBloco, acharSeta, alcaDeSeta, limparSelecoes, ferramenta, formaCriacao, color, tamanhoTexto]);

  const handlePointerMove = useCallback((e) => {
    e.preventDefault();
    const coords = getCanvasCoords(e);

    if (cursorPincelRef.current && (ferramentaRef.current === 'pincel' || ferramentaRef.current === 'borracha')) {
      const cur = cursorPincelRef.current;
      const tam = Math.max(brushSize, 6);
      cur.style.width = `${tam}px`;
      cur.style.height = `${tam}px`;
      cur.style.transform = `translate(${coords.x - tam / 2}px, ${coords.y - tam / 2}px)`;
      cur.style.display = 'block';
    }

    if (arrastoBloco) {
      const bl = blocosRef.current.find(b => b.id === arrastoBloco.id);
      if (bl) {
        if (arrastoBloco.modo === 'redimensionar') {
          const dw = coords.x - arrastoBloco.cx;
          const dh = coords.y - arrastoBloco.cy;
          const razao = Math.max(0.1, (arrastoBloco.w0 + dw) / arrastoBloco.w0);
          if (bl.forma === 'texto') {
            bl.w = Math.max(60, arrastoBloco.w0 + dw);
            bl.tamanho = Math.max(8, Math.round(arrastoBloco.t0 * razao));
            bl.hUser = Math.max(34, arrastoBloco.h0 + dh);
          } else if (bl.forma === 'quadrado') {
            const lado = Math.max(50, arrastoBloco.w0 + Math.max(dw, dh));
            bl.w = lado;
            bl.h = lado;
            bl.tamanho = Math.max(8, Math.round(arrastoBloco.t0 * (lado / arrastoBloco.w0)));
          } else {
            bl.w = Math.max(50, arrastoBloco.w0 + dw);
            bl.h = Math.max(40, arrastoBloco.h0 + dh);
            bl.tamanho = Math.max(8, Math.round(arrastoBloco.t0 * razao));
          }
        } else {
          bl.x = arrastoBloco.x0 + (coords.x - arrastoBloco.cx);
          bl.y = arrastoBloco.y0 + (coords.y - arrastoBloco.cy);
        }
        setBlocos([...blocosRef.current]);
        redrawAllRef.current && redrawAllRef.current();
      }
      return;
    }

    if (arrastoSeta) {
      const dx = coords.x - arrastoSeta.cx;
      const dy = coords.y - arrastoSeta.cy;
      if (arrastoSeta.modo === 'desenhar') {
        setSetaPreview({ x1: arrastoSeta.x1, y1: arrastoSeta.y1, x2: coords.x, y2: coords.y, cor: arrastoSeta.cor });
      } else {
        const s = setasRef.current.find(x => x.id === arrastoSeta.id);
        if (s) {
          if (arrastoSeta.modo === 'mover') {
            s.x1 = arrastoSeta.x1 + dx;
            s.y1 = arrastoSeta.y1 + dy;
            s.x2 = arrastoSeta.x2 + dx;
            s.y2 = arrastoSeta.y2 + dy;
          } else if (arrastoSeta.modo === 'ponta-inicio') {
            s.x1 = arrastoSeta.x1 + dx;
            s.y1 = arrastoSeta.y1 + dy;
          } else {
            s.x2 = arrastoSeta.x2 + dx;
            s.y2 = arrastoSeta.y2 + dy;
          }
          setSetas([...setasRef.current]);
          redrawAllRef.current && redrawAllRef.current();
        }
      }
      return;
    }

    if (isDragging && selectedImageIndexRef.current >= 0) {
      const obj = imageObjectsRef.current[selectedImageIndexRef.current];
      if (!obj) return;
      const dx = coords.x - dragStart.x;
      const dy = coords.y - dragStart.y;

      if (dragType === 'move') {
        obj.x = dragStartProps.x + dx;
        obj.y = dragStartProps.y + dy;
      } else if (dragType === 'resize-br') {
        const newW = Math.max(10, (obj.originalWidth * dragStartProps.scale) + dx);
        obj.scale = newW / obj.originalWidth;
      } else if (dragType === 'resize-tr') {
        const newW = Math.max(10, (obj.originalWidth * dragStartProps.scale) + dx);
        obj.scale = newW / obj.originalWidth;
        obj.y = dragStartProps.y + dy;
      } else if (dragType === 'resize-bl') {
        const newH = Math.max(10, (obj.originalHeight * dragStartProps.scale) + dy);
        obj.scale = newH / obj.originalHeight;
        obj.x = dragStartProps.x + dx;
      } else if (dragType === 'resize-tl') {
        const newW = Math.max(10, (obj.originalWidth * dragStartProps.scale) - dx);
        const newH = Math.max(10, (obj.originalHeight * dragStartProps.scale) - dy);
        obj.scale = Math.min(newW / obj.originalWidth, newH / obj.originalHeight);
        obj.x = dragStartProps.x + (obj.originalWidth * dragStartProps.scale - obj.originalWidth * obj.scale);
        obj.y = dragStartProps.y + (obj.originalHeight * dragStartProps.scale - obj.originalHeight * obj.scale);
      }

      setImageObjects([...imageObjectsRef.current]);
      redrawAllRef.current && redrawAllRef.current();
      return;
    }

    if (isDrawing) {
      setCurrentPoints(prev => [...prev, coords]);
      const ctx = ctxRef.current;
      if (ctx) {
        const actualColor = ferramentaRef.current === 'borracha' ? 'eraser' : color;
        const strokeColor = getEffectiveColor(actualColor, darkMode);
        ctx.globalCompositeOperation = 'source-over';
        ctx.beginPath();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = brushSize;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        const pts = currentPoints.length > 0 ? [...currentPoints, coords] : [coords];
        if (pts.length === 0) return;
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) {
          ctx.lineTo(pts[i].x, pts[i].y);
        }
        ctx.stroke();
      }
    }
  }, [isDragging, dragStart, dragStartProps, dragType, getCanvasCoords, isDrawing, currentPoints, color, brushSize, getEffectiveColor, arrastoBloco, arrastoSeta, darkMode]);

  const handlePointerUp = useCallback((e) => {
    e.preventDefault();
    if (arrastoBloco) {
      setArrastoBloco(null);
    }
    if (arrastoSeta) {
      if (arrastoSeta.modo === 'desenhar') {
        setSetaPreview(null);
        const larg = canvasSizeRef.current.width;
        const alt = canvasSizeRef.current.height;
        const fim = getCanvasCoords(e);
        const tracado = {
          x1: arrastoSeta.x1,
          y1: arrastoSeta.y1,
          x2: Math.max(0, Math.min(larg, fim.x)),
          y2: Math.max(0, Math.min(alt, fim.y)),
          cor: arrastoSeta.cor,
        };
        if (Math.hypot(tracado.x2 - tracado.x1, tracado.y2 - tracado.y1) >= 10) {
          const nova = { id: `s${Date.now()}`, x1: tracado.x1, y1: tracado.y1, x2: tracado.x2, y2: tracado.y2, cor: tracado.cor };
          setasRef.current = [...setasRef.current, nova];
          setSetas(setasRef.current);
          setSetaSelecionada(nova.id);
        }
      }
      setArrastoSeta(null);
      redrawAllRef.current && redrawAllRef.current();
    }
    if (isDragging) {
      setImageObjects([...imageObjectsRef.current]);
      setIsDragging(false);
      setDragType(null);
    }
    if (isDrawing) {
      if (currentPoints.length > 1) {
        const actualColor = ferramentaRef.current === 'borracha' ? 'eraser' : color;
        const newStroke = {
          color: actualColor,
          size: brushSize,
          points: currentPoints,
        };
        strokesRef.current = [...strokesRef.current, newStroke];
        setStrokes(strokesRef.current);
      }
      setIsDrawing(false);
      setCurrentPoints([]);
      redrawAllRef.current && redrawAllRef.current();
    }
    try { e.target.releasePointerCapture(e.pointerId); } catch (err) {}
  }, [isDragging, isDrawing, currentPoints, color, brushSize, arrastoBloco, arrastoSeta, getCanvasCoords]);

  const handlePointerLeave = useCallback((e) => {
    if (cursorPincelRef.current) {
      cursorPincelRef.current.style.display = 'none';
    }
    if (isDrawing) {
      if (currentPoints.length > 1) {
        const actualColor = ferramentaRef.current === 'borracha' ? 'eraser' : color;
        const newStroke = {
          color: actualColor,
          size: brushSize,
          points: currentPoints,
        };
        strokesRef.current = [...strokesRef.current, newStroke];
        setStrokes(strokesRef.current);
      }
      setIsDrawing(false);
      setCurrentPoints([]);
      redrawAllRef.current && redrawAllRef.current();
    }
  }, [isDrawing, currentPoints, color, brushSize]);

  const handleDoubleClick = useCallback((e) => {
    const coords = getCanvasCoords(e);
    const bl = acharBloco(coords);
    if (bl) {
      setBlocoSelecionado(bl.id);
      setRascunhoTexto(bl.texto);
      setTamanhoTexto(bl.tamanho);
      setBlocoEditando(bl.id);
      editandoRef.current = bl.id;
    }
  }, [getCanvasCoords, acharBloco]);

  const atualizarTextoBloco = (valor) => {
    setRascunhoTexto(valor);
    const bl = blocosRef.current.find(b => b.id === blocoEditando);
    if (bl) {
      bl.texto = valor;
      setBlocos([...blocosRef.current]);
      redrawAllRef.current && redrawAllRef.current();
    }
  };

  const fecharEdicao = useCallback(() => {
    const id = editandoRef.current;
    editandoRef.current = null;
    setBlocoEditando(null);
    const bl = blocosRef.current.find(b => b.id === id);
    const ehTexto = !bl || !bl.forma || bl.forma === 'texto';
    if (bl && ehTexto && !bl.texto.trim()) {
      blocosRef.current = blocosRef.current.filter(b => b.id !== id);
      setBlocos(blocosRef.current);
      setBlocoSelecionado(prev => (prev === id ? null : prev));
    }
    redrawAllRef.current && redrawAllRef.current();
  }, []);

  const undo = useCallback(() => {
    if (strokesRef.current.length === 0) return;
    strokesRef.current = strokesRef.current.slice(0, -1);
    setStrokes(strokesRef.current);
    redrawAllRef.current && redrawAllRef.current();
  }, []);

  const clearCanvas = useCallback(() => {
    strokesRef.current = [];
    imageObjectsRef.current = [];
    blocosRef.current = [];
    setasRef.current = [];
    setStrokes([]);
    setImageObjects([]);
    setBlocos([]);
    setSetas([]);
    setSetaPreview(null);
    setSelectedImageIndex(-1);
    selectedImageIndexRef.current = -1;
    setBlocoSelecionado(null);
    setSetaSelecionada(null);
    setBlocoEditando(null);
    editandoRef.current = null;
    persistenciaRef.current.json = '#limpo';
    redrawAllRef.current && redrawAllRef.current();
  }, []);

  const pasteImage = useCallback(async () => {
    try {
      const items = await navigator.clipboard.read();
      let blob = null;
      for (const item of items) {
        if (item.types.some(t => t.startsWith('image/'))) {
          const type = item.types.find(t => t.startsWith('image/'));
          blob = await item.getType(type);
          break;
        }
      }
      if (!blob) {
        await alert({
          title: 'Aviso',
          message: 'Nenhuma imagem encontrada na área de transferência.',
          variant: 'warning',
        });
        return;
      }
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        const { width, height } = canvasSizeRef.current;
        const maxW = width * 0.8;
        const maxH = height * 0.8;
        const scale = Math.min(maxW / img.width, maxH / img.height, 1);
        const x = (width - img.width * scale) / 2;
        const y = (height - img.height * scale) / 2;
        const obj = { img, src: null, originalWidth: img.width, originalHeight: img.height, x, y, scale };
        const leitor = new FileReader();
        leitor.onload = () => {
          obj.src = leitor.result;
        };
        leitor.readAsDataURL(blob);
        imageObjectsRef.current = [...imageObjectsRef.current, obj];
        setImageObjects(imageObjectsRef.current);
        redrawAllRef.current && redrawAllRef.current();
        URL.revokeObjectURL(url);
      };
      img.onerror = () => {
        alert({
          title: 'Erro',
          message: 'Erro ao carregar a imagem colada.',
          variant: 'danger',
        });
        URL.revokeObjectURL(url);
      };
      img.src = url;
    } catch (err) {
      await alert({
        title: 'Erro',
        message: 'Erro ao colar imagem. Verifique as permissões.',
        variant: 'danger',
      });
      console.error(err);
    }
  }, [alert]);

  const deleteSelectedImage = useCallback(() => {
    if (selectedImageIndexRef.current >= 0) {
      const idx = selectedImageIndexRef.current;
      imageObjectsRef.current = imageObjectsRef.current.filter((_, i) => i !== idx);
      setImageObjects(imageObjectsRef.current);
      setSelectedImageIndex(-1);
      selectedImageIndexRef.current = -1;
      redrawAllRef.current && redrawAllRef.current();
    }
  }, []);

  const getCanvasBounds = useCallback(() => {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

    strokesRef.current.forEach(s => {
      s.points.forEach(p => {
        minX = Math.min(minX, p.x);
        minY = Math.min(minY, p.y);
        maxX = Math.max(maxX, p.x);
        maxY = Math.max(maxY, p.y);
      });
    });

    blocosRef.current.forEach(b => {
      const h = b.h || 40;
      minX = Math.min(minX, b.x);
      minY = Math.min(minY, b.y);
      maxX = Math.max(maxX, b.x + b.w);
      maxY = Math.max(maxY, b.y + h);
    });

    setasRef.current.forEach(s => {
      minX = Math.min(minX, s.x1, s.x2);
      minY = Math.min(minY, s.y1, s.y2);
      maxX = Math.max(maxX, s.x1, s.x2);
      maxY = Math.max(maxY, s.y1, s.y2);
    });

    imageObjectsRef.current.forEach(obj => {
      const w = obj.originalWidth * obj.scale;
      const h = obj.originalHeight * obj.scale;
      minX = Math.min(minX, obj.x);
      minY = Math.min(minY, obj.y);
      maxX = Math.max(maxX, obj.x + w);
      maxY = Math.max(maxY, obj.y + h);
    });

    const bg = backgroundImageRef.current;
    if (bg && bg.img) {
      minX = Math.min(minX, bg.x);
      minY = Math.min(minY, bg.y);
      maxX = Math.max(maxX, bg.x + bg.width);
      maxY = Math.max(maxY, bg.y + bg.height);
    }

    const padding = 40;
    minX = Math.max(0, minX - padding);
    minY = Math.max(0, minY - padding);
    maxX += padding;
    maxY += padding;

    if (!isFinite(minX)) {
      const { width, height } = canvasSizeRef.current;
      return { x: 0, y: 0, width, height };
    }

    return {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY
    };
  }, []);

  const downloadFullCanvas = useCallback(() => {
    const bounds = getCanvasBounds();
    const canvas = document.createElement('canvas');
    canvas.width = bounds.width;
    canvas.height = bounds.height;
    const ctx = canvas.getContext('2d');

    const bgColor = darkMode ? '#1a1a2e' : '#ffffff';
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, bounds.width, bounds.height);

    ctx.translate(-bounds.x, -bounds.y);

    const colorMap = {
      'black': darkMode ? '#f0f0f0' : 'black',
      'red': darkMode ? '#ff6b6b' : 'red',
      'blue': darkMode ? '#4dabf7' : 'blue',
      'green': darkMode ? '#69db7c' : 'green',
    };

    const bgImg = backgroundImageRef.current;
    if (bgImg && bgImg.img) {
      ctx.drawImage(bgImg.img, bgImg.x, bgImg.y, bgImg.width, bgImg.height);
    }

    imageObjectsRef.current.forEach(obj => {
      if (!obj.img) return;
      const w = obj.originalWidth * obj.scale;
      const h = obj.originalHeight * obj.scale;
      ctx.drawImage(obj.img, obj.x, obj.y, w, h);
    });

    strokesRef.current.forEach(stroke => {
      ctx.beginPath();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.lineWidth = stroke.size;
      ctx.globalCompositeOperation = 'source-over';
      if (stroke.color === 'eraser') {
        ctx.strokeStyle = bgColor;
      } else {
        ctx.strokeStyle = colorMap[stroke.color] || stroke.color;
      }
      const pts = stroke.points;
      if (pts.length === 0) return;
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i].x, pts[i].y);
      }
      ctx.stroke();
    });
    ctx.globalCompositeOperation = 'source-over';

    const drawArrow = (s, cor) => {
      ctx.beginPath();
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2;
      ctx.moveTo(s.x1, s.y1);
      ctx.lineTo(s.x2, s.y2);
      ctx.stroke();
      const ang = Math.atan2(s.y2 - s.y1, s.x2 - s.x1) + Math.PI;
      const tamanho = 11;
      const a1 = ang - 0.42;
      const a2 = ang + 0.42;
      ctx.fillStyle = cor;
      ctx.beginPath();
      ctx.moveTo(s.x2, s.y2);
      ctx.lineTo(s.x2 + Math.cos(a1) * tamanho, s.y2 + Math.sin(a1) * tamanho);
      ctx.lineTo(s.x2 + Math.cos(a2) * tamanho, s.y2 + Math.sin(a2) * tamanho);
      ctx.closePath();
      ctx.fill();
    };

    setasRef.current.forEach(s => {
      drawArrow(s, colorMap[s.cor] || s.cor);
    });

    ctx.textBaseline = 'top';
    blocosRef.current.forEach(bl => {
      const ehTexto = !bl.forma || bl.forma === 'texto';
      const ehTextoSolto = bl.forma === 'textoSolto';
      const ehRedonda = bl.forma === 'circulo' || bl.forma === 'triangulo';
      const ehRetangulo = bl.forma === 'retangulo' || bl.forma === 'quadrado';
      ctx.font = `${bl.tamanho}px sans-serif`;
      const linhas = quebrarTexto(ctx, bl.texto, larguraAcomodada(bl));
      const alturaLinha = Math.round(bl.tamanho * 1.3);
      const alturaTexto = linhas.length * alturaLinha;
      if ((ehTexto || ehRetangulo) && !ehTextoSolto) {
        bl.h = Math.max(bl.hUser || 0, alturaTexto + 16);
      }
      const corBloco = colorMap[bl.cor] || bl.cor;
      if ((!ehTextoSolto && (ehTexto || ehRetangulo))) {
        ctx.fillStyle = bgColor;
        ctx.fillRect(bl.x, bl.y, bl.w, bl.h);
        ctx.strokeStyle = corBloco;
        ctx.lineWidth = 1.5;
        contornarForma(ctx, bl);
      }
      ctx.fillStyle = corBloco;
      if (ehTextoSolto) {
        linhas.forEach((linha, i) => {
          ctx.fillText(linha, bl.x, bl.y + i * alturaLinha);
        });
      } else if (ehRedonda) {
        ctx.textAlign = 'center';
        const deslocY = bl.forma === 'triangulo'
          ? bl.h * 0.4 + Math.max(0, (bl.h * 0.6 - alturaTexto) / 2)
          : Math.max(8, (bl.h - alturaTexto) / 2);
        const yCentral = bl.y + deslocY;
        linhas.forEach((linha, i) => {
          ctx.fillText(linha, bl.x + bl.w / 2, yCentral + i * alturaLinha);
        });
        ctx.textAlign = 'left';
      } else {
        linhas.forEach((linha, i) => {
          ctx.fillText(linha, bl.x + 8, bl.y + 8 + i * alturaLinha);
        });
      }
    });

    ctx.setTransform(1, 0, 0, 1, 0, 0);

    const dataURL = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.download = `whiteboard_${Date.now()}.png`;
    link.href = dataURL;
    link.click();
  }, [getCanvasBounds, darkMode]);

  const toggleFullscreen = () => {
    const el = whiteboardContainerRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      if (el.requestFullscreen) {
        el.requestFullscreen();
      } else if (el.webkitRequestFullscreen) {
        el.webkitRequestFullscreen();
      } else if (el.msRequestFullscreen) {
        el.msRequestFullscreen();
      }
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
      }
      setIsFullscreen(false);
    }
  };

  const toggleToolbar = () => {
    setToolbarVisible(prev => !prev);
  };

  const toggleDarkMode = () => {
    setDarkMode(prev => {
      const newVal = !prev;
      localStorage.setItem('whiteboardDarkMode', String(newVal));
      return newVal;
    });
  };

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => {
      if (localStorage.getItem('whiteboardDarkMode') === null) {
        setDarkMode(e.matches);
      }
    };
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      const fs = !!document.fullscreenElement;
      setIsFullscreen(fs);
      if (!fs) {
        setToolbarVisible(true);
      }
      setTimeout(() => {
        resizeCanvas();
      }, 50);
      setTimeout(() => {
        resizeCanvas();
      }, 250);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
    };
  }, [resizeCanvas]);

  useEffect(() => {
    const handler = (e) => {
      const alvo = e.target;
      if (alvo && (alvo.tagName === 'TEXTAREA' || alvo.tagName === 'INPUT' || alvo.isContentEditable)) return;
      if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        undo();
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (blocoSelecionadoRef.current) {
          e.preventDefault();
          const id = blocoSelecionadoRef.current;
          blocosRef.current = blocosRef.current.filter(b => b.id !== id);
          setBlocos(blocosRef.current);
          setBlocoSelecionado(null);
          setBlocoEditando(prev => (prev === id ? null : prev));
          if (editandoRef.current === id) editandoRef.current = null;
          redrawAllRef.current && redrawAllRef.current();
          return;
        }
        if (setaSelecionadaRef.current) {
          e.preventDefault();
          const id = setaSelecionadaRef.current;
          setasRef.current = setasRef.current.filter(s => s.id !== id);
          setSetas(setasRef.current);
          setSetaSelecionada(null);
          redrawAllRef.current && redrawAllRef.current();
          return;
        }
        if (selectedImageIndexRef.current >= 0) {
          e.preventDefault();
          deleteSelectedImage();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [undo, deleteSelectedImage]);

  useEffect(() => {
    const handler = (e) => {
      if (document.querySelector('.modal.modal-aberto')) return;
      if (containerRef.current && containerRef.current.offsetParent !== null) {
        e.preventDefault();
        pasteImage();
      }
    };
    window.addEventListener('paste', handler);
    return () => window.removeEventListener('paste', handler);
  }, [pasteImage]);

  const isDark = darkMode;

  const externalToolbarStyle = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.4rem',
    alignItems: 'center',
    padding: '0.45rem 0.6rem',
    backgroundColor: isDark ? '#2d2d44' : '#f1f5f9',
    border: `1px solid ${isDark ? '#444466' : '#cbd5e1'}`,
    borderRadius: '8px',
    color: isDark ? '#e2e8f0' : '#0f172a',
    flexShrink: 0,
  };

  const internalToolbarStyle = {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
    alignItems: 'center',
    padding: '0.5rem 0.75rem',
    backgroundColor: isDark ? '#2d2d44' : '#f1f5f9',
    borderBottom: isDark ? '1px solid #444466' : '1px solid #cbd5e1',
    borderRadius: '8px 8px 0 0',
    transition: 'all 0.3s ease',
    position: 'absolute',
    top: '10px',
    left: '10px',
    right: '10px',
    zIndex: 1000,
    maxWidth: 'calc(100% - 20px)',
    overflow: 'hidden',
    boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
    transform: toolbarVisible ? 'translateY(0)' : 'translateY(-120%)',
    opacity: toolbarVisible ? 1 : 0,
    pointerEvents: toolbarVisible ? 'auto' : 'none',
  };

  const containerStyle = {
    position: 'relative',
    overflow: 'hidden',
    width: '100%',
    height: '100%',
    flex: 1,
    minHeight: 0,
    backgroundColor: getBackgroundColor(darkMode),
    borderRadius: '12px',
    display: 'block',
  };

  const toggleButtonStyle = {
    position: 'absolute',
    top: '10px',
    right: '10px',
    zIndex: 1001,
    background: isDark ? '#2d2d44' : '#f1f5f9',
    border: isDark ? '1px solid #444466' : '1px solid #cbd5e1',
    borderRadius: '8px',
    padding: '6px 12px',
    cursor: 'pointer',
    fontSize: '1.2rem',
    color: isDark ? '#e2e8f0' : '#0f172a',
    display: isFullscreen ? 'block' : 'none',
    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
  };

  const colorButtonStyle = (colorName) => ({
    width: '30px',
    height: '30px',
    borderRadius: '50%',
    border: isDark ? '2px solid #555577' : '2px solid #cbd5e1',
    background: getEffectiveColor(colorName, darkMode),
    cursor: 'pointer',
    outline: (ferramenta !== 'borracha' && color === colorName) ? (isDark ? '3px solid #90caf9' : '3px solid #1e3a8a') : 'none',
    outlineOffset: '2px',
    transition: 'all 0.15s',
    flexShrink: 0,
  });

  const nomeCor = (colorName) => {
    const nomes = { black: 'Preto', red: 'Vermelho', blue: 'Azul', green: 'Verde' };
    if (colorName === 'black' && isDark) return 'Branco';
    return nomes[colorName] || colorName;
  };

  const selectFerramentaStyle = {
    padding: '0.35rem 0.4rem',
    background: isDark ? '#2d2d44' : '#f1f5f9',
    border: `1px solid ${isDark ? '#555577' : '#cbd5e1'}`,
    borderRadius: '8px',
    color: isDark ? '#e2e8f0' : '#0f172a',
    fontSize: '0.85rem',
    cursor: 'pointer',
  };

  const buttonStyle = {
    padding: '0.4rem 0.8rem',
    background: isDark ? '#3d3d5c' : '#f1f5f9',
    border: isDark ? '1px solid #555577' : '1px solid #cbd5e1',
    borderRadius: '8px',
    cursor: 'pointer',
    color: isDark ? '#e2e8f0' : '#0f172a',
    fontSize: '0.85rem',
    fontWeight: '500',
  };

  const downloadButtonStyle = {
    padding: '0.4rem 0.8rem',
    background: '#1976d2',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '0.85rem',
  };

  const themeButtonStyle = {
    padding: '0.4rem 0.8rem',
    background: isDark ? '#3d3d5c' : '#e2e8f0',
    border: isDark ? '1px solid #555577' : '1px solid #cbd5e1',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: '600',
    color: isDark ? '#e2e8f0' : '#0f172a',
  };

  const deleteSelectedButtonStyle = {
    padding: '0.4rem 0.8rem',
    background: selectedImageIndex === -1 ? (isDark ? '#2d2d44' : '#e2e8f0') : (isDark ? '#5c3d3d' : '#f8d7da'),
    border: `1px solid ${isDark ? '#555577' : '#cbd5e1'}`,
    borderRadius: '8px',
    cursor: selectedImageIndex === -1 ? 'default' : 'pointer',
    opacity: selectedImageIndex === -1 ? 0.5 : 1,
    color: isDark ? '#e2e8f0' : '#0f172a',
  };

  const ferramentaButtonStyle = (ativa) => ({
    padding: '0.4rem 0.8rem',
    background: ativa ? (isDark ? '#3d3d5c' : '#cbd5e1') : (isDark ? '#2d2d44' : '#f1f5f9'),
    border: `1px solid ${isDark ? '#555577' : '#cbd5e1'}`,
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: ativa ? '700' : '400',
    color: isDark ? '#e2e8f0' : '#0f172a',
    fontSize: '0.85rem',
  });

  const blocoEmEdicao = blocos.find(b => b.id === blocoEditando);

  const cursorCanvas = ferramenta === 'pincel' || ferramenta === 'borracha'
    ? (ferramenta === 'borracha' ? 'cell' : 'crosshair')
    : (ferramenta === 'texto' ? (formaCriacao === 'seta' ? 'crosshair' : 'text') : 'default');

  const canvasStyle = {
    display: 'block',
    position: 'absolute',
    top: 0,
    left: 0,
    touchAction: 'none',
    cursor: cursorCanvas,
    backgroundColor: getBackgroundColor(darkMode),
  };

  const escolherCor = (nome) => {
    setColor(nome);
    if (ferramenta === 'borracha') setFerramenta('pincel');
  };

  const renderControls = (inFullscreen) => (
    <>
      <button
        type="button"
        onClick={toggleDarkMode}
        style={themeButtonStyle}
        title={isDark ? 'Alternar para claro' : 'Alternar para escuro'}
      >
        {isDark ? <><IconeSol size={15} /> Claro</> : <><IconeLua size={15} /> Escuro</>}
      </button>
      <button
        type="button"
        onClick={() => setFerramenta('selecionar')}
        style={ferramentaButtonStyle(ferramenta === 'selecionar')}
      >
        Selecionar
      </button>
      <button
        type="button"
        onClick={() => setFerramenta('pincel')}
        style={ferramentaButtonStyle(ferramenta === 'pincel')}
      >
        Pincel
      </button>
      <button
        type="button"
        onClick={() => setFerramenta('borracha')}
        style={ferramentaButtonStyle(ferramenta === 'borracha')}
      >
        Borracha
      </button>
      <button type="button" onClick={() => escolherCor('black')} style={colorButtonStyle('black')} title={nomeCor('black')} />
      <button type="button" onClick={() => escolherCor('red')} style={colorButtonStyle('red')} title={nomeCor('red')} />
      <button type="button" onClick={() => escolherCor('blue')} style={colorButtonStyle('blue')} title={nomeCor('blue')} />
      <button type="button" onClick={() => escolherCor('green')} style={colorButtonStyle('green')} title={nomeCor('green')} />
      <button
        type="button"
        onClick={() => {
          setFormaCriacao('textoSolto');
          setFerramenta(prev => (prev === 'texto' && formaCriacao === 'textoSolto' ? 'selecionar' : 'texto'));
        }}
        style={ferramentaButtonStyle(ferramenta === 'texto' && formaCriacao === 'textoSolto')}
      >
        Texto solto
      </button>
      <select
        value={formaCriacao === 'texto' || formaCriacao === 'seta' ? '' : formaCriacao}
        onChange={(e) => {
          if (!e.target.value) return;
          setFormaCriacao(e.target.value);
          setFerramenta('texto');
        }}
        style={selectFerramentaStyle}
        title="Inserir forma geométrica"
      >
        <option value="">Formas...</option>
        <option value="retangulo">Retângulo</option>
        <option value="quadrado">Quadrado</option>
        <option value="circulo">Círculo</option>
        <option value="triangulo">Triângulo</option>
        <option value="seta">Seta</option>
      </select>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
        <label style={{ fontSize: '0.85rem', color: isDark ? '#cbd5e1' : '#0f172a', whiteSpace: 'nowrap' }}>
          Texto: {tamanhoTexto}px
        </label>
        <input
          type="range"
          min="10"
          max="28"
          value={tamanhoTexto}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            setTamanhoTexto(v);
            const idEdit = editandoRef.current;
            if (idEdit) {
              const bl = blocosRef.current.find(b => b.id === idEdit);
              if (bl) {
                bl.tamanho = v;
                setBlocos([...blocosRef.current]);
              }
            }
          }}
          style={{ width: '80px', cursor: 'pointer' }}
        />
      </div>
      <button type="button" onClick={clearCanvas} style={buttonStyle}>Limpar</button>
      <button type="button" onClick={downloadFullCanvas} style={downloadButtonStyle}>Baixar PNG</button>
      <button type="button" onClick={pasteImage} style={buttonStyle}>Colar imagem</button>
      <button type="button" onClick={deleteSelectedImage} disabled={selectedImageIndex === -1} style={deleteSelectedButtonStyle}>Excluir selecionada</button>
      <button type="button" onClick={toggleFullscreen} style={buttonStyle}>
        {inFullscreen ? <><IconeSairTelaCheia size={15} /> Sair da tela cheia</> : <><IconeTelaCheia size={15} /> Tela cheia</>}
      </button>
      <div className="eraser-size-control" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
        <label style={{ fontSize: '0.85rem', color: isDark ? '#cbd5e1' : '#0f172a', whiteSpace: 'nowrap' }}>
          Tamanho: {brushSize}px
        </label>
        <input
          type="range"
          min="1"
          max="50"
          value={brushSize}
          onChange={(e) => setBrushSize(parseInt(e.target.value))}
          style={{ width: '90px', cursor: 'pointer' }}
        />
      </div>
    </>
  );

  return (
    <div ref={containerRef} className="whiteboard-root">
      {imageLoadError && (
        <div className="flash-error">
          Não foi possível carregar a imagem do quadro branco. O arquivo pode não existir ou estar corrompido.
        </div>
      )}

      {!isFullscreen && (
        <div style={externalToolbarStyle} className="whiteboard-controls">
          {renderControls(false)}
        </div>
      )}

      <div
        ref={whiteboardContainerRef}
        style={containerStyle}
        className="whiteboard-container"
      >
        <canvas
          ref={canvasRef}
          tabIndex="0"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerLeave}
          onDoubleClick={handleDoubleClick}
          style={canvasStyle}
        />

        <div
          ref={cursorPincelRef}
          className="cursor-pincel"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            pointerEvents: 'none',
            borderRadius: '50%',
            border: `1px solid ${isDark ? '#e2e8f0' : '#334155'}`,
            background: ferramenta === 'borracha' ? 'transparent' : `${getEffectiveColor(color, darkMode)}33`,
            display: 'none',
            zIndex: 998,
            boxSizing: 'border-box',
          }}
        />

        {blocoEmEdicao && (() => {
          const ehRedonda = blocoEmEdicao.forma === 'circulo' || blocoEmEdicao.forma === 'triangulo';
          const larguraCampo = ehRedonda ? larguraAcomodada(blocoEmEdicao) : blocoEmEdicao.w;
          const esquerda = ehRedonda
            ? blocoEmEdicao.x + (blocoEmEdicao.w - larguraCampo) / 2
            : blocoEmEdicao.x;
          return (
            <textarea
              ref={textareaRef}
              value={rascunhoTexto}
              onChange={(e) => atualizarTextoBloco(e.target.value)}
              onBlur={fecharEdicao}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === 'Escape') fecharEdicao();
              }}
              autoFocus
              style={{
                position: 'absolute',
                left: esquerda,
                top: blocoEmEdicao.y,
                width: larguraCampo,
                minHeight: '40px',
                boxSizing: 'border-box',
                fontFamily: 'sans-serif',
                fontSize: `${blocoEmEdicao.tamanho}px`,
                lineHeight: `${Math.round(blocoEmEdicao.tamanho * 1.3)}px`,
                padding: '6px',
                border: `2px solid ${isDark ? '#90caf9' : '#1e3a8a'}`,
                borderRadius: '4px',
                outline: 'none',
                resize: 'none',
                overflow: 'hidden',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                textAlign: ehRedonda ? 'center' : 'left',
                background: isDark ? '#1a1a2e' : '#ffffff',
                color: getEffectiveColor(blocoEmEdicao.cor, darkMode),
                zIndex: 1001,
              }}
            />
          );
        })()}

        {isFullscreen && (
          <>
            <button
              style={toggleButtonStyle}
              onClick={toggleToolbar}
              title={toolbarVisible ? 'Esconder ferramentas' : 'Mostrar ferramentas'}
            >
              {toolbarVisible ? <IconeChevronEsquerda size={16} /> : <IconeChevronDireita size={16} />}
            </button>

            <div style={internalToolbarStyle} className="whiteboard-controls">
              {renderControls(true)}
            </div>

            {!toolbarVisible && (
              <div
                style={{
                  position: 'absolute',
                  top: '10px',
                  right: '60px',
                  zIndex: 999,
                  color: isDark ? '#cbd5e1' : '#64748b',
                  fontSize: '0.8rem',
                  background: isDark ? 'rgba(26,26,46,0.8)' : 'rgba(255,255,255,0.8)',
                  padding: '4px 12px',
                  borderRadius: '12px',
                  border: isDark ? '1px solid #444466' : '1px solid #cbd5e1',
                  pointerEvents: 'none',
                }}
              >
                Ferramentas ocultas
              </div>
            )}
          </>
        )}
      </div>

      {!isFullscreen && (
        <div className="whiteboard-instructions">
          <small>
            Pincel desenha, Borracha apaga e Selecionar move os itens. Caixa de texto e Formas criam ao clicar; duplo clique edita e o canto redimensiona. Delete remove o selecionado; Ctrl+Z desfaz; Ctrl+V cola imagem.
          </small>
        </div>
      )}
    </div>
  );
}

export default React.memo(Whiteboard);