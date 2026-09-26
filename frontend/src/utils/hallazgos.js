import { SEVERIDADES } from '../config/reglas';

/** Normaliza la severidad que llega del backend ("ALTO", "alto"...). */
export function normalizarSeveridad(severidad) {
  return String(severidad ?? '').toLowerCase();
}

/** Cuenta los hallazgos por severidad: { critico, alto, medio, bajo }. */
export function contarPorSeveridad(hallazgos = []) {
  const conteo = Object.fromEntries(SEVERIDADES.map((severidad) => [severidad, 0]));
  for (const hallazgo of hallazgos) {
    const severidad = normalizarSeveridad(hallazgo.severidad);
    if (severidad in conteo) conteo[severidad] += 1;
  }
  return conteo;
}

/** Formatea kilobytes para las tarjetas del plan: 8192 -> "8,192 KB". */
export function formatearKb(valor) {
  return valor ? `${Math.round(valor).toLocaleString()} KB` : '--';
}
