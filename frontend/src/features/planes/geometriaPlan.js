/*
 * Geometría del diagrama del plan (compartida por el diagrama y la captura):
 * tamaños, ícono de cada operador, posiciones y tono del costo.
 */
export const COLUMNA = 160;
export const FILA = 122;
export const MARGEN = 28;
export const ICONO = 32;
export const MAX_TEXTO = 24;

// Ícono de cada operador (ver IconosPlan.jsx), según su operación física.
const SIMBOLOS = [
  [/^select$/i, 'raiz-select'],
  [/^(insert|update|delete|merge)$/i, 'raiz-dml'],
  [/^clustered index (insert|update|delete|merge)$/i, 'clustered-index-insert'],
  [/^index (insert|update|delete)$/i, 'index-insert'],
  [/^table (insert|update|delete|merge)$/i, 'table-insert'],
  [/clustered index scan/i, 'clustered-index-scan'],
  [/clustered index seek/i, 'clustered-index-seek'],
  [/index scan/i, 'index-scan'],
  [/index seek/i, 'index-seek'],
  [/table scan/i, 'table-scan'],
  [/key lookup/i, 'key-lookup'],
  [/rid lookup/i, 'rid-lookup'],
  [/constant scan/i, 'constant-scan'],
  [/nested loops/i, 'nested-loops'],
  [/hash match/i, 'hash-match'],
  [/merge join|adaptive join/i, 'merge-join'],
  [/concatenation/i, 'concatenation'],
  [/sort/i, 'sort'],
  [/compute scalar/i, 'compute-scalar'],
  [/aggregate/i, 'stream-aggregate'],
  [/filter/i, 'filter'],
  [/^top|top n sort/i, 'top'],
  [/spool/i, 'spool'],
  [/parallelism/i, 'parallelism'],
  [/segment|sequence project|window/i, 'segment'],
  [/assert/i, 'assert'],
  [/^sequence$/i, 'sequence'],
];

export function simboloDe(fisica) {
  return `op-${SIMBOLOS.find(([patron]) => patron.test(fisica))?.[1] ?? 'generico'}`;
}

export function recortar(texto) {
  return texto.length > MAX_TEXTO ? `${texto.slice(0, MAX_TEXTO - 1)}…` : texto;
}

export function formatearFilas(valor) {
  return valor === null || valor === undefined ? '' : Math.round(valor).toLocaleString('en-US');
}

/** Posición de cada nodo: el primer hijo en la misma fila, los demás debajo (como SSMS). */
export function calcularPosiciones(nodos) {
  const hijos = new Map(nodos.map((nodo) => [nodo.id, []]));
  for (const nodo of nodos) if (nodo.padre !== null) hijos.get(nodo.padre)?.push(nodo);
  const posiciones = new Map();
  let siguienteFila = 0;
  const ubicar = (nodo, columna) => {
    const propios = hijos.get(nodo.id) ?? [];
    let fila;
    if (!propios.length) {
      fila = siguienteFila;
      siguienteFila += 1;
    } else {
      propios.forEach((hijo, indice) => {
        const filaHijo = ubicar(hijo, columna + 1);
        if (indice === 0) fila = filaHijo;
      });
    }
    posiciones.set(nodo.id, {
      x: MARGEN + columna * COLUMNA + COLUMNA / 2,
      y: MARGEN + fila * FILA + 40,
    });
    return fila;
  };
  const raiz = nodos.find((nodo) => nodo.padre === null);
  if (raiz) ubicar(raiz, 0);
  const columnas = Math.max(...[...posiciones.values()].map((p) => p.x), 0);
  return { posiciones, ancho: columnas + COLUMNA / 2 + MARGEN, alto: MARGEN * 2 + siguienteFila * FILA };
}

/** Rojo para los operadores más caros, naranja para los que pesan al menos la mitad del mayor. */
export function tonoCosto(costo, maximo) {
  if (maximo >= 5 && costo >= maximo * 0.9) return 'alto';
  if (costo >= 1 && costo >= maximo * 0.5) return 'medio';
  return 'normal';
}


/**
 * Filas reales muy distintas de las estimadas (10 veces o más, en cualquier
 * sentido): Plan Explorer pinta en rojo el número de filas de esa flecha.
 */
export function filasDesviadas(nodo) {
  const { filasReales: reales, filasEstimadas: estimadas } = nodo;
  if (reales == null || estimadas == null) return false;
  const mayor = Math.max(reales, estimadas);
  const menor = Math.max(Math.min(reales, estimadas), 1);
  return mayor >= 100 && mayor / menor >= 10;
}
