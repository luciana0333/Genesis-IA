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

/** Ordena por gravedad (crítico primero) y luego por número de línea. */
export function ordenarHallazgos(hallazgos = []) {
  const peso = (hallazgo) => {
    const indice = SEVERIDADES.indexOf(normalizarSeveridad(hallazgo.severidad));
    return indice === -1 ? SEVERIDADES.length : indice;
  };
  return [...hallazgos].sort((a, b) => peso(a) - peso(b) || (a.linea ?? 0) - (b.linea ?? 0));
}

/** Formatea kilobytes para las tarjetas del plan: 8192 -> "8,192 KB". */
export function formatearKb(valor) {
  return valor ? `${Math.round(valor).toLocaleString()} KB` : '--';
}

/**
 * Los mensajes siguen el formato "qué pasa. Qué hacer.": se separa la primera
 * oración (el problema) del resto (la corrección) para mostrarlos por separado.
 */
export function separarMensaje(texto) {
  const corte = texto.search(/(?<=[.?])\s+(?=[A-ZÁÉÍÓÚÑ¿(])/);
  if (corte < 0) return { problema: texto, solucion: '' };
  return { problema: texto.slice(0, corte), solucion: texto.slice(corte).trim() };
}

/**
 * Un hallazgo agrupado llega como "Se encontraron N observaciones de este
 * tipo, en las líneas 3, 8: hecho uno; hecho dos." Devuelve las líneas y cada
 * ocurrencia por separado para mostrarlas como lista.
 */
export function desglosarGrupo(problema) {
  const grupo = problema.match(/^Se encontraron \d+ observaciones de este tipo, en (?:la línea|las líneas) ([\d, ]+): ([\s\S]+)$/);
  if (!grupo) return { lineas: null, ocurrencias: [problema] };
  const ocurrencias = grupo[2]
    .replace(/\.$/, '')
    .split(/;\s+/)
    .map((texto) => texto.charAt(0).toUpperCase() + texto.slice(1));
  return { lineas: grupo[1].trim(), ocurrencias };
}
