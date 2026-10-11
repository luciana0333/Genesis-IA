import { useMemo, useState } from 'react';
import {
  ArrowDownAZ, ArrowUpToLine, Box, Calculator, Combine, FileOutput, Filter, Hash, KeyRound, Layers, ListMinus,
  ListPlus, Network, PencilLine, Repeat, ScanLine, Search, Sigma, Split, Table2,
} from 'lucide-react';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';

/*
 * Diagrama del plan al estilo de SQL Sentry Plan Explorer: el resultado a la
 * izquierda y los datos fluyendo de derecha a izquierda; costo de cada operador
 * arriba (naranja y rojo para los más caros), filas sobre cada flecha (más
 * gruesa cuantas más filas) y, debajo, operación, tabla e índice. Los operadores
 * con advertencias se resaltan en amarillo con su triángulo.
 */

const COLUMNA = 168;
const FILA = 148;
const MARGEN = 28;
const ICONO = 40;
const MAX_TEXTO = 24;

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

function iconoDe(fisica) {
  return ICONOS.find(([patron]) => patron.test(fisica))?.[1] ?? Table2;
}

function recortar(texto) {
  return texto.length > MAX_TEXTO ? `${texto.slice(0, MAX_TEXTO - 1)}…` : texto;
}

function formatearFilas(valor) {
  return valor === null || valor === undefined ? '' : Math.round(valor).toLocaleString('en-US');
}

/** Posición de cada nodo: el primer hijo en la misma fila, los demás debajo (como SSMS). */
function calcularPosiciones(nodos) {
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
function tonoCosto(costo, maximo) {
  if (maximo >= 5 && costo >= maximo * 0.9) return 'alto';
  if (costo >= 1 && costo >= maximo * 0.5) return 'medio';
  return 'normal';
}

function Flecha({ desde, hasta, filas, filasMaximas }) {
  const grosor = 1.5 + 7 * (Math.log10((filas ?? 0) + 1) / Math.log10(filasMaximas + 1 || 10));
  const inicio = desde.x - ICONO / 2 - 10;
  const fin = hasta.x + ICONO / 2 + 10;
  const tronco = fin + 18;
  const puntos = desde.y === hasta.y
    ? `${inicio},${desde.y} ${fin + 9},${hasta.y}`
    : `${inicio},${desde.y} ${tronco},${desde.y} ${tronco},${hasta.y} ${fin + 9},${hasta.y}`;
  const punta = Math.max(grosor * 1.4, 7);
  return (
    <g className="plan-flecha">
      <polyline points={puntos} fill="none" strokeWidth={grosor} strokeLinejoin="round" />
      <polygon points={`${fin},${hasta.y} ${fin + 11},${hasta.y - punta} ${fin + 11},${hasta.y + punta}`} />
      {filas !== null && filas !== undefined && (
        <text x={inicio - 6} y={desde.y - grosor / 2 - 6} textAnchor="end" className="plan-filas">
          {formatearFilas(filas)}
        </text>
      )}
    </g>
  );
}

function Nodo({ nodo, posicion, maximo, activo, onEntrar, onSalir }) {
  const Icono = iconoDe(nodo.fisica);
  const tono = tonoCosto(nodo.costoPct, maximo);
  const conAdvertencia = nodo.advertencias.length > 0;
  const nombre = nodo.padre === null ? nodo.fisica.toUpperCase() : nodo.fisica;
  const lineas = [
    nodo.logica && nodo.logica !== nodo.fisica ? `(${nodo.logica})` : null,
    nodo.objeto || null,
    nodo.indice || null,
  ].filter(Boolean);
  const anchoNombre = Math.min(nombre.length, MAX_TEXTO) * 6.9 + 14;
  const { x, y } = posicion;

  return (
    <g
      className={`plan-nodo${activo ? ' activo' : ''}`}
      onMouseEnter={(evento) => onEntrar(nodo, evento)}
      onMouseLeave={onSalir}
      tabIndex={0}
      onFocus={(evento) => onEntrar(nodo, evento)}
      onBlur={onSalir}
    >
      {nodo.padre !== null && (
        tono === 'normal' ? (
          <text x={x} y={y - ICONO / 2 - 12} textAnchor="middle" className="plan-costo">{nodo.costoPct.toFixed(1)}%</text>
        ) : (
          <g className={`plan-costo-pastilla ${tono}`}>
            <rect x={x - 27} y={y - ICONO / 2 - 29} width={54} height={21} rx={10.5} />
            <text x={x} y={y - ICONO / 2 - 14} textAnchor="middle">{nodo.costoPct.toFixed(1)}%</text>
          </g>
        )
      )}
      <rect x={x - ICONO / 2 - 4} y={y - ICONO / 2 - 4} width={ICONO + 8} height={ICONO + 8} className="plan-icono-fondo" />
      <Icono x={x - ICONO / 2} y={y - ICONO / 2} width={ICONO} height={ICONO} strokeWidth={1.4} className="plan-icono" />
      {conAdvertencia && (
        <g className="plan-alerta">
          <polygon points={`${x + 16},${y - 28} ${x + 29},${y - 6} ${x + 3},${y - 6}`} />
          <text x={x + 16} y={y - 9} textAnchor="middle">!</text>
        </g>
      )}
      {conAdvertencia && (
        <rect x={x - anchoNombre / 2} y={y + ICONO / 2 + 6} width={anchoNombre} height={21} rx={10.5} className="plan-resaltado" />
      )}
      <text x={x} y={y + ICONO / 2 + 21} textAnchor="middle" className="plan-nombre">
        {recortar(nombre)}
        <title>{nombre}</title>
      </text>
      {lineas.map((linea, indice) => (
        <text key={linea} x={x} y={y + ICONO / 2 + 40 + indice * 16} textAnchor="middle" className="plan-detalle">
          {recortar(linea)}
          <title>{linea}</title>
        </text>
      ))}
    </g>
  );
}

/** Texto con las partes importantes resaltadas en amarillo (como en las capturas del informe). */
function TextoResaltado({ texto, resaltados }) {
  const partes = resaltados.filter(Boolean);
  if (!partes.length) return texto;
  const patron = new RegExp(`(${partes.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`);
  return texto.split(patron).map((trozo, indice) => (
    partes.includes(trozo) ? <mark key={indice}>{trozo}</mark> : trozo
  ));
}

function DetalleNodo({ nodo, posicion }) {
  const filas = [
    ['Costo del operador', `${nodo.costoPct.toFixed(1)}%`],
    ['Filas estimadas', formatearFilas(nodo.filasEstimadas)],
    ['Filas reales', formatearFilas(nodo.filasReales)],
    ['Ejecuciones', formatearFilas(nodo.ejecuciones)],
    ['Lecturas lógicas', formatearFilas(nodo.lecturas)],
  ].filter(([, valor]) => valor && !(nodo.padre === null && valor === '0.0%'));
  return (
    <div className="plan-detalle-flotante" style={{ left: posicion.left, top: posicion.top }} role="tooltip">
      <p className="plan-detalle-titulo">
        {nodo.padre === null ? nodo.fisica.toUpperCase() : nodo.fisica}
        {nodo.logica && nodo.logica !== nodo.fisica && <span> ({nodo.logica})</span>}
      </p>
      {(nodo.objeto || nodo.indice) && <p className="plan-detalle-objeto">{[nodo.objeto, nodo.indice].filter(Boolean).join('.')}</p>}
      {nodo.advertencias.length > 0 && (
        <div className="plan-detalle-alertas">
          <p className="plan-detalle-alertas-titulo">Advertencias:</p>
          {nodo.advertencias.map((advertencia) => (
            <p key={advertencia.texto}><TextoResaltado texto={advertencia.texto} resaltados={advertencia.resaltados} /></p>
          ))}
        </div>
      )}
      {nodo.conversiones?.length > 0 && (
        <div className="plan-detalle-conversiones">
          <p className="plan-detalle-alertas-titulo">Conversiones implícitas:</p>
          {nodo.conversiones.map((expresion) => (
            <p key={expresion} className="mono"><TextoResaltado texto={expresion} resaltados={['CONVERT_IMPLICIT']} /></p>
          ))}
        </div>
      )}
      <dl>
        {filas.map(([etiqueta, valor]) => (
          <div key={etiqueta}><dt>{etiqueta}</dt><dd>{valor}</dd></div>
        ))}
      </dl>
    </div>
  );
}

const ZOOMS = [0.5, 0.65, 0.8, 1, 1.2];

/** Diagrama de una sentencia del plan con zoom y detalle al pasar el mouse. */
function Diagrama({ sentencia }) {
  const [zoom, setZoom] = useState(0.8);
  const [enfocado, setEnfocado] = useState(null);
  const { posiciones, ancho, alto } = useMemo(() => calcularPosiciones(sentencia.nodos), [sentencia]);
  const maximo = Math.max(...sentencia.nodos.map((nodo) => nodo.costoPct), 0);
  const filasDe = (nodo) => nodo.filasReales ?? nodo.filasEstimadas;
  const filasMaximas = Math.max(...sentencia.nodos.map((nodo) => filasDe(nodo) ?? 0), 1);
  const indiceZoom = ZOOMS.indexOf(zoom);

  const alEntrar = (nodo, evento) => {
    const lienzo = evento.currentTarget.ownerSVGElement.parentElement;
    const caja = evento.currentTarget.getBoundingClientRect();
    const base = lienzo.getBoundingClientRect();
    setEnfocado({
      nodo,
      posicion: { left: caja.right - base.left + lienzo.scrollLeft + 8, top: caja.top - base.top + lienzo.scrollTop },
    });
  };

  return (
    <div className="plan-diagrama">
      <div className="plan-zoom" role="group" aria-label="Zoom del diagrama">
        <button type="button" onClick={() => setZoom(ZOOMS[Math.max(indiceZoom - 1, 0)])} aria-label="Alejar">−</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom(ZOOMS[Math.min(indiceZoom + 1, ZOOMS.length - 1)])} aria-label="Acercar">+</button>
      </div>
      <div className="plan-lienzo">
        <svg
          width={ancho * zoom}
          height={alto * zoom}
          viewBox={`0 0 ${ancho} ${alto}`}
          role="img"
          aria-label={`Diagrama del plan de la consulta ${sentencia.numero}`}
        >
          {sentencia.nodos.filter((nodo) => nodo.padre !== null).map((nodo) => (
            <Flecha
              key={`flecha-${nodo.id}`}
              desde={posiciones.get(nodo.id)}
              hasta={posiciones.get(nodo.padre)}
              filas={filasDe(nodo)}
              filasMaximas={filasMaximas}
            />
          ))}
          {sentencia.nodos.map((nodo) => (
            <Nodo
              key={nodo.id}
              nodo={nodo}
              posicion={posiciones.get(nodo.id)}
              maximo={maximo}
              activo={enfocado?.nodo.id === nodo.id}
              onEntrar={alEntrar}
              onSalir={() => setEnfocado(null)}
            />
          ))}
        </svg>
        {enfocado && <DetalleNodo nodo={enfocado.nodo} posicion={enfocado.posicion} />}
      </div>
    </div>
  );
}

function formatearMs(valor) {
  return valor === null || valor === undefined ? '—' : Math.round(valor).toLocaleString('en-US');
}

/** Sentencias del plan (como la grilla de Plan Explorer) y el diagrama de la elegida. */
export function DiagramaPlan({ sentencias = [] }) {
  const [elegida, setElegida] = useState(0);
  if (!sentencias.length) return null;
  const sentencia = sentencias[Math.min(elegida, sentencias.length - 1)];
  const costoTotal = sentencias.reduce((suma, s) => suma + (s.costo || 0), 0);

  return (
    <section className="plan-diagrama-seccion">
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Detalle del plan"
        titulo="Diagrama del plan"
        acciones={<span className="results-meta">Pasa el mouse sobre un operador para ver su detalle</span>}
      />
      <div className="table-scroll">
        <table className="data-table plan-sentencias">
          <thead>
            <tr>
              <th scope="col">Sentencia</th>
              <th scope="col" className="num">Costo est. %</th>
              <th scope="col" className="num">Duración (ms)</th>
              <th scope="col" className="num">CPU (ms)</th>
            </tr>
          </thead>
          <tbody>
            {sentencias.map((item, indice) => (
              <tr
                key={item.numero}
                className={item === sentencia ? 'elegida' : undefined}
                onClick={() => setElegida(indice)}
              >
                <td className="mono plan-sentencia-texto" title={item.texto}>{item.texto || item.tipo}</td>
                <td className="num">{costoTotal ? ((item.costo / costoTotal) * 100).toFixed(1) : '—'}%</td>
                <td className="num">{formatearMs(item.duracionMs)}</td>
                <td className="num">{formatearMs(item.cpuMs)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Diagrama key={sentencia.numero} sentencia={sentencia} />
    </section>
  );
}
