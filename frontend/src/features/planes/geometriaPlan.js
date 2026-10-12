/*
 * Geometría del diagrama del plan (compartida por el diagrama y la captura):
 * tamaños, ícono de cada operador, posiciones y tono del costo.
 */
import {
  ArrowDownAZ, ArrowUpToLine, Box, Calculator, Combine, FileOutput, Filter, Hash, KeyRound, Layers, ListMinus,
  ListPlus, Network, PencilLine, Repeat, ScanLine, Search, Sigma, Split, Table2,
} from 'lucide-react';

export const COLUMNA = 168;
export const FILA = 148;
export const MARGEN = 28;
export const ICONO = 40;
export const MAX_TEXTO = 24;

const ICONOS = [
  [/^(select|insert|update|delete|merge)$/i, FileOutput],
  [/seek/i, Search],
  [/scan/i, ScanLine],
  [/lookup/i, KeyRound],
  [/nested loops/i, Repeat],
  [/hash match/i, Hash],
  [/merge join/i, Combine],
  [/sort/i, ArrowDownAZ],
  [/aggregate/i, Sigma],
  [/compute scalar/i, Calculator],
  [/filter/i, Filter],
  [/spool/i, Layers],
  [/parallelism/i, Split],
  [/top/i, ArrowUpToLine],
  [/insert/i, ListPlus],
  [/delete/i, ListMinus],
  [/update/i, PencilLine],
  [/concatenation|sequence/i, Network],
  [/constant/i, Box],
];

export function iconoDe(fisica) {
  return ICONOS.find(([patron]) => patron.test(fisica))?.[1] ?? Table2;
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
      y: MARGEN + fila * FILA + 52,
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

