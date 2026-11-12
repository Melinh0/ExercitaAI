const carregarImagem = (blob) => new Promise((resolve, reject) => {
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.onload = () => {
    URL.revokeObjectURL(url);
    resolve(img);
  };
  img.onerror = () => {
    URL.revokeObjectURL(url);
    reject(new Error('imagem inválida'));
  };
  img.src = url;
});

export const converterImagemEmPng = async (blob) => {
  const img = await carregarImagem(blob);
  const largura = img.naturalWidth || img.width;
  const altura = img.naturalHeight || img.height;
  if (!largura || !altura) throw new Error('dimensões inválidas');
  const canvas = document.createElement('canvas');
  canvas.width = largura;
  canvas.height = altura;
  canvas.getContext('2d').drawImage(img, 0, 0);
  const convertido = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!convertido) throw new Error('falha na conversão');
  return convertido;
};

const extensaoDaImagem = (tipo) => {
  const parte = (tipo || '').split('/')[1] || '';
  return parte.split('+')[0].toLowerCase();
};

const obterTextoDoItem = (clipboardData, tipo) => {
  const itens = clipboardData?.items ? Array.from(clipboardData.items) : [];
  const item = itens.find(i => i.type === tipo);
  if (!item) return Promise.resolve(null);
  return new Promise((resolve) => item.getAsString(resolve));
};

const decodificarEntidades = (texto) => (texto || '')
  .replace(/&amp;/g, '&')
  .replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'");

const extrairSrcHtml = (html) => {
  const match = /<img[^>]*\ssrc\s*=\s*["']([^"']+)["']/i.exec(html || '');
  return match ? decodificarEntidades(match[1]) : null;
};

const baixarImagem = async (src) => {
  const resposta = await fetch(src);
  if (!resposta.ok) throw new Error('falha ao baixar a imagem');
  return resposta.blob();
};

export const obterTextoPlano = (clipboardData) =>
  obterTextoDoItem(clipboardData, 'text/plain');

export const coletarImagensColadas = async (
  clipboardData,
  extensoesPermitidas,
  opcoes = {}
) => {
  const { usarHtml = true } = opcoes;
  const itens = clipboardData?.items ? Array.from(clipboardData.items) : [];
  const candidatos = [];

  for (const item of itens) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile();
      if (blob) candidatos.push(blob);
    }
  }

  let houveConteudoDeImagem = candidatos.some(c => !!c);

  if (candidatos.length === 0 && usarHtml) {
    const html = await obterTextoDoItem(clipboardData, 'text/html');
    const src = extrairSrcHtml(html);
    if (src) {
      houveConteudoDeImagem = true;
      try {
        candidatos.push(await baixarImagem(src));
      } catch (err) {
        candidatos.push(null);
      }
    }
  }

  const arquivos = [];

  for (let i = 0; i < candidatos.length; i++) {
    const blob = candidatos[i];
    if (!blob) continue;
    const extensao = extensaoDaImagem(blob.type);
    const permitida = extensoesPermitidas.includes(extensao);
    let conteudo = blob;
    let extensaoFinal = extensao || 'png';
    if (!permitida) {
      conteudo = await converterImagemEmPng(blob).catch(() => null);
      if (!conteudo) continue;
      extensaoFinal = 'png';
    }
    const nome = `paste_image_${Date.now()}_${i + 1}.${extensaoFinal}`;
    arquivos.push(new File([conteudo], nome, {
      type: conteudo.type || `image/${extensaoFinal}`
    }));
  }

  return { arquivos, encontrouImagem: houveConteudoDeImagem };
};
