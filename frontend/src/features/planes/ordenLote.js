/** Orden y formato del resumen de un lote de planes. */

/** 850 ms · 2.35 s · 1 min 12 s */
export function formatearDuracion(ms) {
  if (ms === null || ms === undefined) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const segundos = ms / 1000;
  if (segundos < 60) return `${segundos.toFixed(2)} s`;
  return `${Math.floor(segundos / 60)} min ${Math.round(segundos % 60)} s`;
}

// Columnas que ordenan el resumen. El 1.er clic ordena de mayor a menor.
const COLUMNAS_ORDEN = {
  procedimiento: (plan) => plan.procedimiento?.toLowerCase() ?? '',
  duracion: (plan) => plan.duracionMs,
  hallazgos: (plan) => (plan.resumen
    ? plan.resumen.critico * 1e9 + plan.resumen.alto * 1e6 + plan.resumen.medio * 1e3 + plan.resumen.bajo
    : null),
};
export const ORDEN_INICIAL = { columna: 'duracion', direccion: 'desc' };

/** Planes en el orden del resumen (los dañados siempre al final). La navegación sigue este orden. */
export function ordenarPlanes(planes, orden) {
  const valor = COLUMNAS_ORDEN[orden.columna];
  const signo = orden.direccion === 'desc' ? -1 : 1;
  return [...planes].sort((a, b) => {
    if (Boolean(a.error) !== Boolean(b.error)) return a.error ? 1 : -1;
    const va = valor(a);
    const vb = valor(b);
    const vacioA = va === null || va === undefined;
    const vacioB = vb === null || vb === undefined;
    if (vacioA || vacioB) return vacioA === vacioB ? a.id - b.id : vacioA ? 1 : -1;
    if (va === vb) return a.id - b.id;
    return (va > vb ? 1 : -1) * signo;
  });
}
