import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeKatex from 'rehype-katex';
import katex from 'katex';
import mermaid from 'mermaid';
import 'katex/dist/katex.min.css';

const mermaidConfig = {
  startOnLoad: false,
  theme: 'base',
  securityLevel: 'loose',
  flowchart: { useMaxWidth: true, htmlLabels: true },
  themeVariables: {
    background: '#ffffff',
    primaryColor: '#004a99',
    primaryBorderColor: '#003377',
    primaryTextColor: '#1f1f1f',
    lineColor: '#1f1f1f',
    secondaryColor: '#e0e0e0',
    tertiaryColor: '#f9f9f9',
  },
};

mermaid.initialize(mermaidConfig);

function Mermaid({ chart }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current && chart) {
      try {
        ref.current.innerHTML = '';
        mermaid.render('mermaid-svg', chart).then(({ svg }) => {
          ref.current.innerHTML = svg;
        });
      } catch (err) {
        console.error('Mermaid rendering error:', err);
        ref.current.innerHTML = `<pre class="error">Error rendering diagram: ${err.message}</pre>`;
      }
    }
  }, [chart]);

  return <div ref={ref} className="mermaid-container" />;
}

function CodeBlock({ inline, className, children, ...props }) {
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1] : '';

  if (!inline && lang === 'mermaid') {
    return <Mermaid chart={String(children).replace(/\n$/, '')} />;
  }

  if (inline) {
    return (
      <code className="md-code-inline" {...props}>
        {children}
      </code>
    );
  }

  return (
    <div className="md-code-block">
      <pre>
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}

function Table({ children }) {
  return (
    <div className="md-table-wrapper">
      <table className="md-table">{children}</table>
    </div>
  );
}

function Thead({ children }) {
  return <thead className="md-thead">{children}</thead>;
}

function Tbody({ children }) {
  return <tbody>{children}</tbody>;
}

function Tr({ children }) {
  return <tr className="md-tr">{children}</tr>;
}

function Th({ children, style }) {
  return (
    <th className="md-th" style={style}>
      {children}
    </th>
  );
}

function Td({ children, style }) {
  return (
    <td className="md-td" style={style}>
      {children}
    </td>
  );
}

function Blockquote({ children }) {
  return <blockquote className="md-blockquote">{children}</blockquote>;
}

function Img({ src, alt }) {
  return (
    <span className="md-img-wrapper">
      <img src={src} alt={alt || ''} className="md-img" />
      {alt && <span className="md-img-caption">{alt}</span>}
    </span>
  );
}

function fixLatex(text) {
  if (!text) return text;

  const replacements = {
    '*rightarrow*': '\\rightarrow',
    '*leftarrow*': '\\leftarrow',
    '*infty*': '\\infty',
    '*leq*': '\\leq',
    '*geq*': '\\geq',
    '*times*': '\\times',
    '*cdot*': '\\cdot',
    '*pm*': '\\pm',
    '*frac*': '\\frac',
    '*sqrt*': '\\sqrt',
    '*alpha*': '\\alpha',
    '*beta*': '\\beta',
    '*gamma*': '\\gamma',
    '*delta*': '\\delta',
    '*theta*': '\\theta',
    '*lambda*': '\\lambda',
    '*mu*': '\\mu',
    '*pi*': '\\pi',
    '*sigma*': '\\sigma',
    '*omega*': '\\omega',
  };

  for (const [key, value] of Object.entries(replacements)) {
    text = text.split(key).join(value);
  }

  return text;
}

const AMBIENTES_KATEX = {
  align: 'aligned',
  'align*': 'aligned',
  alignat: 'alignedat',
  'alignat*': 'alignedat',
  eqnarray: 'aligned',
  'eqnarray*': 'aligned',
  flalign: 'aligned',
  'flalign*': 'aligned',
  gather: 'gathered',
  'gather*': 'gathered',
  split: 'aligned',
  multline: 'gathered',
  'multline*': 'gathered',
  equation: 'gathered',
  'equation*': 'gathered',
  displaymath: 'gathered',
};

const COMANDOS_T = new Set([
  'text', 'textbf', 'textit', 'texttt', 'textrm', 'textsf', 'textsc', 'textup',
  'textnormal', 'textstyle', 'times', 'theta', 'tau', 'to', 'top', 'tag',
  'triangle', 'triangledown', 'triangleleft', 'triangleright', 'triangleq',
  'therefore', 'tan', 'tanh', 'tfrac', 'tilde', 'tt', 'thickapprox', 'thickspace',
  'thinspace', 'twoheadleftarrow', 'twoheadrightarrow', 'leftrightarrow',
]);

const COMANDOS_N = new Set([
  'nabla', 'notin', 'not', 'newcommand', 'newline', 'noindent', 'napprox', 'nmid',
  'neq', 'neg', 'nsubseteq', 'nsupseteq', 'nu', 'ni', 'nearrow', 'nwarrow',
  'ngtr', 'nleq', 'ngeq', 'nsim', 'ncong', 'nequiv', 'nleftarrow',
  'nrightarrow', 'nleftrightarrow', 'nRightarrow', 'nLeftarrow', 'nvDash', 'nVDash', 'nVdash',
]);

const COMANDOS_R = new Set([
  'rho', 'right', 'rightarrow', 'rightarrowtail', 'rightleftharpoons',
  'rightleftarrows', 'rightrightarrows', 'rightthreetimes', 'rule',
  'renewcommand', 'rm', 'Rightarrow', 'rangle',
]);

function alinharAmbientes(texto) {
  const comAliases = texto.replace(
    /\\(begin|end)\{([^}]+)\}/g,
    (m, cmd, nome) => (AMBIENTES_KATEX[nome] ? `\\${cmd}{${AMBIENTES_KATEX[nome]}}` : m)
  );
  return comAliases.replace(
    /[ \t]*\\(?:label|nonumber|notag|allowdisplaybreaks)(?:\{[^}]*\})?/g,
    ''
  );
}

function colapsarQuebrasInline(texto) {
  const blocos = texto.split(/(\$\$[\s\S]*?\$\$)/g);
  return blocos
    .map((b, i) =>
      i % 2 === 1
        ? b
        : b.replace(
            /\$([^\n$]+(?:\n(?!\n)[^\n$]+)*)\$/g,
            (m, corpo) => '$' + corpo.replace(/\n/g, ' ') + '$'
          )
    )
    .join('');
}

function latexValido(tex, exibicao = false) {
  try {
    katex.renderToString(tex, { throwOnError: true, strict: false, displayMode: exibicao });
    return true;
  } catch (erro) {
    return false;
  }
}

function envolverAmbientes(trecho) {
  return trecho.replace(/\\begin\{[^}]+\}[\s\S]*?\\end\{[^}]+\}/g, (m) => {
    const limpo = m.replace(/\n/g, ' ');
    return latexValido(limpo, true) ? '$$' + limpo + '$$' : m;
  });
}

function envolverGrupos(trecho) {
  let saida = '';
  let i = 0;
  while (i < trecho.length) {
    if (trecho[i] === '\\' && i + 1 < trecho.length && /[a-zA-Z]/.test(trecho[i + 1])) {
      const cmd = /^\\[a-zA-Z]+/.exec(trecho.slice(i));
      let j = i + (cmd ? cmd[0].length : 1);
      if (trecho[j] === '[') {
        const fimCol = trecho.indexOf(']', j);
        if (fimCol !== -1) j = fimCol + 1;
      }
      let grupos = 0;
      while (trecho[j] === '{') {
        let profundidade = 0;
        let k = j;
        for (; k < trecho.length; k += 1) {
          if (trecho[k] === '{') profundidade += 1;
          else if (trecho[k] === '}') {
            profundidade -= 1;
            if (profundidade === 0) break;
          }
        }
        if (profundidade !== 0) break;
        j = k + 1;
        grupos += 1;
      }
      if (grupos > 0) {
        const candidato = trecho.slice(i, j).replace(/\n/g, ' ');
        if (latexValido(candidato)) {
          saida += '$' + candidato + '$';
          i = j;
          continue;
        }
      }
    }
    saida += trecho[i];
    i += 1;
  }
  return saida;
}

function ehTokenMatematico(token) {
  if (!token || token.indexOf('$') !== -1) return false;
  const forma = /^[A-Za-z0-9\\_^{}()=+\-*/.,%;[\]!|&]+$/;
  if (token.indexOf('\\') !== -1) return forma.test(token);
  if (/^[0-9+\-*/=.,;:(){}[\]%|!&]+$/.test(token)) return true;
  if (/^[A-Za-z0-9]$/.test(token)) return true;
  if (!forma.test(token)) return false;
  const semPontuacao = token.replace(/[)\].,;:!?]+$/, '');
  const marcador = /[\^_]/.exec(semPontuacao);
  if (!marcador) return false;
  const cauda = semPontuacao.slice(marcador.index + 1);
  if (marcador[0] === '^') return /^\{[^{}]*\}$|^[0-9]{1,3}$|^[A-Za-z]$/.test(cauda);
  return /^\{[^{}]*\}$|^[0-9]$|^[A-Za-z]$/.test(cauda);
}

function tokenMarcado(token) {
  return token.indexOf('\\') !== -1 || /[\^_]/.test(token);
}

function tokenJuntaRun(token) {
  if (tokenMarcado(token)) return true;
  if (/^[0-9+\-*/=.,;:%|!&]+$/.test(token)) return true;
  return /^[A-Z]$/.test(token);
}

function envolverTrechosTokens(texto) {
  const pedacos = texto.split(/(\s+)/);
  const saida = [];
  let run = [];
  let pendente = '';
  const fecharRun = () => {
    if (run.length === 0) {
      run = [];
      return;
    }
    const candidato = run.join(' ');
    const marcado = run.some((t) => t.indexOf('\\') !== -1 || /[\^_]/.test(t));
    if (marcado && latexValido(candidato)) {
      saida.push('$' + candidato + '$');
    } else {
      for (const t of run) {
        if ((t.indexOf('\\') !== -1 || /[\^_]/.test(t)) && latexValido(t)) {
          saida.push('$' + t + '$');
        } else {
          saida.push(t);
        }
      }
    }
    run = [];
    if (pendente) {
      saida.push(pendente);
      pendente = '';
    }
  };
  for (const p of pedacos) {
    if (p === '') continue;
    if (/^\s+$/.test(p)) {
      if (/[\n\r]/.test(p)) {
        fecharRun();
        saida.push(p);
      } else if (run.length > 0) {
        pendente = p;
      } else {
        saida.push(p);
      }
      continue;
    }
    if (ehTokenMatematico(p)) {
      if (run.length === 0) {
        if (tokenMarcado(p)) {
          run.push(p);
        } else {
          saida.push(p);
        }
        continue;
      }
      if (!tokenJuntaRun(p)) {
        fecharRun();
        saida.push(p);
        continue;
      }
      run.push(p);
      continue;
    }
    fecharRun();
    saida.push(p);
  }
  fecharRun();
  return saida.join('');
}

function envolverTextoSuelto(parte) {
  const comTokens = envolverTrechosTokens(parte);
  const blocos = comTokens.split(/(\$[^$\n]+\$)/g);
  return blocos.map((b, i) => (i % 2 === 1 ? b : envolverGrupos(b))).join('');
}

function envolverSemMath(trecho) {
  const normalizado = trecho
    .replace(/\\\\([a-zA-Z[(])/g, '\\$1')
    .replace(/\\\(([\s\S]*?)\\\)/g, (m, c) => '$' + c.replace(/\n/g, ' ') + '$')
    .replace(/\\\[([\s\S]*?)\\\]/g, (m, c) => '$' + c.replace(/\n/g, ' ') + '$')
    .replace(/\\left/g, '')
    .replace(/\\right/g, '');

  const primeiros = normalizado.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g);
  const comAmbientes = primeiros.map((b, i) => (i % 2 === 1 ? b : envolverAmbientes(b))).join('');
  const segundos = comAmbientes.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g);
  return segundos.map((b, i) => (i % 2 === 1 ? b : envolverTextoSuelto(b))).join('');
}

function repararControles(texto) {
  if (!texto) return texto;

  const mapa = { 8: '\\b', 11: '\\v', 12: '\\f' };

  let saida = '';
  for (let i = 0; i < texto.length; i += 1) {
    const codigo = texto.charCodeAt(i);
    if (codigo in mapa && /[a-zA-Z]/.test(texto[i + 1] || '')) {
      saida += mapa[codigo];
    } else {
      saida += texto[i];
    }
  }

  saida = saida.replace(/\t([A-Za-z]+)/g, (m, cauda) =>
    COMANDOS_T.has('t' + cauda) ? '\\t' + cauda : m
  );
  saida = saida.replace(/\n([A-Za-z]+)/g, (m, cauda) =>
    COMANDOS_N.has('n' + cauda) ? '\\n' + cauda : m
  );
  saida = saida.replace(/\r([A-Za-z]+)/g, (m, cauda) =>
    COMANDOS_R.has('r' + cauda) ? '\\r' + cauda : m
  );

  return saida;
}

function envolverTrecho(parte) {
  const trechos = parte.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g);
  return trechos
    .map((trecho, i) => (i % 2 === 1 ? trecho : envolverSemMath(trecho)))
    .join('');
}

function envolverLatexSolto(text) {
  if (!text) return text;

  const partes = text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return partes
    .map((parte, i) => {
      if (i % 2 === 1) return parte;
      const reparado = repararControles(parte);
      const alinhado = alinharAmbientes(reparado);
      const semQuebras = colapsarQuebrasInline(alinhado);
      return envolverTrecho(semQuebras);
    })
    .join('');
}

function MarkdownRenderer({ content }) {
  if (!content) return null;

  const fixedContent = envolverLatexSolto(fixLatex(content));

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, remarkBreaks]}
        rehypePlugins={[[rehypeKatex, { errorColor: 'currentColor' }]]}
        components={{
          table: Table,
          thead: Thead,
          tbody: Tbody,
          tr: Tr,
          th: Th,
          td: Td,
          blockquote: Blockquote,
          code: CodeBlock,
          img: Img,
        }}
      >
        {fixedContent}
      </ReactMarkdown>
    </div>
  );
}

export default React.memo(MarkdownRenderer);