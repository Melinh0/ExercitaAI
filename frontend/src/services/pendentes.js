const chave = (topico, tipo) => `exercita:pendente:${tipo}:${topico}`;

export function lerPendente(topico, tipo) {
  if (!topico) return null;
  try {
    const bruto = sessionStorage.getItem(chave(topico, tipo));
    if (!bruto) return null;
    const pacote = JSON.parse(bruto);
    return pacote && typeof pacote === 'object' && pacote.dados ? pacote : null;
  } catch (e) {
    return null;
  }
}

export function gravarPendente(topico, tipo, dados) {
  if (!topico || !dados) return;
  try {
    sessionStorage.setItem(chave(topico, tipo), JSON.stringify({ _ts: Date.now(), dados }));
  } catch (e) {}
}

export function limparPendente(topico, tipo) {
  if (!topico) return;
  try {
    sessionStorage.removeItem(chave(topico, tipo));
  } catch (e) {}
}

export function sincronizarPendente(topico, tipo, dados) {
  const semRestante = tipo === 'questoes'
    && dados
    && Array.isArray(dados.questions)
    && dados.questions.length === 0;
  if (!dados || semRestante) {
    limparPendente(topico, tipo);
    return;
  }
  gravarPendente(topico, tipo, dados);
}
