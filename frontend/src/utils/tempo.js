export function formatarDuracao(segundos) {
  const total = Math.max(0, Math.floor(segundos));
  if (total < 60) return `${total} s`;
  const min = Math.floor(total / 60);
  const resto = total % 60;
  return resto > 0 ? `${min} min ${resto} s` : `${min} min`;
}
