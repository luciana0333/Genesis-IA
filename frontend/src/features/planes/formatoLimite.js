/** Partes de un límite en segundos: { minutos, segundos } (los segundos pueden tener decimales). */
export function partesLimite(totalS) {
  if (totalS == null) return { minutos: null, segundos: null };
  const minutos = Math.floor(totalS / 60);
  const segundos = Math.round((totalS - minutos * 60) * 100) / 100;
  return { minutos, segundos };
}

/** 45 s · 1 min · 1 min 30 s */
export function formatearLimite(totalS) {
  if (totalS == null) return '';
  const { minutos, segundos } = partesLimite(totalS);
  if (!minutos) return `${segundos} s`;
  return segundos ? `${minutos} min ${segundos} s` : `${minutos} min`;
}
