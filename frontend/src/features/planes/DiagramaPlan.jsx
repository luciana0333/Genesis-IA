import { useMemo, useRef, useState } from 'react';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import {
  ICONO, MAX_TEXTO, calcularPosiciones, formatearFilas, recortar, simboloDe, tonoCosto,
} from './geometriaPlan';
import { DefinicionesIconos } from './IconosPlan';

/*
 * Diagrama del plan al estilo de SQL Sentry Plan Explorer: el resultado a la
 * izquierda y los datos fluyendo de derecha a izquierda; costo de cada operador
 * arriba (naranja y rojo para los más caros), filas sobre cada flecha (más
 * gruesa cuantas más filas) y, debajo, operación, tabla e índice. Los operadores
 * con advertencias se resaltan en amarillo con su triángulo.
 */

export function Flecha({ desde, hasta, filas, filasMaximas }) {
  // Más gruesa cuantas más filas pasan, como en Plan Explorer.
  const grosor = 1.5 + 4.5 * (Math.log10((filas ?? 0) + 1) / Math.log10(filasMaximas + 1 || 10));
  const inicio = desde.x - ICONO / 2 - 8;
  const fin = hasta.x + ICONO / 2 + 6;
  const punta = 4 + grosor * 0.6;
  // Enlaces en ángulo: las ramas inferiores suben en diagonal hacia su padre.
  const puntos = desde.y === hasta.y
    ? `${inicio},${desde.y} ${fin + punta * 1.6},${hasta.y}`
    : `${inicio},${desde.y} ${fin + 34},${desde.y} ${fin + 20},${hasta.y} ${fin + punta * 1.6},${hasta.y}`;
  return (
    <g className="plan-flecha">
      <polyline points={puntos} fill="none" strokeWidth={grosor} strokeLinejoin="round" />
      <polygon points={`${fin},${hasta.y} ${fin + punta * 1.8},${hasta.y - punta} ${fin + punta * 1.8},${hasta.y + punta}`} />
      {filas !== null && filas !== undefined && (
        <text x={inicio - 4} y={desde.y - grosor / 2 - 4} textAnchor="end" className="plan-filas">
          {formatearFilas(filas)}
        </text>
      )}
    </g>
  );
}

const ANCHO_LETRA = 6.3; // ancho aproximado de un carácter a 11.5 px (Segoe UI)

export function Nodo({ nodo, posicion, maximo, activo, marcado = false, onEntrar, onSalir }) {
  const tono = tonoCosto(nodo.costoPct, maximo);
  const conAdvertencia = nodo.advertencias.length > 0;
  const nombre = nodo.padre === null ? nodo.fisica.toUpperCase() : nodo.fisica;
  const lineas = [
    nodo.logica && nodo.logica !== nodo.fisica ? `(${nodo.logica})` : null,
    nodo.objeto || null,
    nodo.indice || null,
  ].filter(Boolean);
  const costo = `${nodo.costoPct.toFixed(1)}%`;
  const anchoNombre = Math.min(nombre.length, MAX_TEXTO) * ANCHO_LETRA + 10;
  const anchoPastilla = costo.length * 7 + 14;
  const { x, y } = posicion;
  const mitad = ICONO / 2;

  return (
    <g
      className={`plan-nodo${activo ? ' activo' : ''}`}
      onMouseEnter={(evento) => onEntrar(nodo, evento)}
      onMouseLeave={onSalir}
      tabIndex={0}
      onFocus={(evento) => onEntrar(nodo, evento)}
      onBlur={onSalir}
    >
      {tono === 'normal' ? (
        <text x={x} y={y - mitad - 8} textAnchor="middle" className="plan-costo">{costo}</text>
      ) : (
        <g className={`plan-costo-pastilla ${tono}`}>
          <rect x={x - anchoPastilla / 2} y={y - mitad - 22} width={anchoPastilla} height={17} rx={8.5} />
          <text x={x} y={y - mitad - 9.5} textAnchor="middle">{costo}</text>
        </g>
      )}
      <rect x={x - mitad - 3} y={y - mitad - 3} width={ICONO + 6} height={ICONO + 6} className="plan-icono-fondo" />
      <use href={`#${simboloDe(nodo.fisica)}`} x={x - mitad} y={y - mitad} width={ICONO} height={ICONO} />
      {conAdvertencia && (
        <g className="plan-alerta">
          <polygon points={`${x - mitad + 2},${y + mitad - 13} ${x - mitad + 9},${y + mitad} ${x - mitad - 5},${y + mitad}`} />
          <text x={x - mitad + 2} y={y + mitad - 1.5} textAnchor="middle">!</text>
        </g>
      )}
      {(conAdvertencia || marcado) && (
        <rect x={x - anchoNombre / 2} y={y + mitad + 5} width={anchoNombre} height={16} rx={2} className="plan-resaltado" />
      )}
      <text x={x} y={y + mitad + 17} textAnchor="middle" className="plan-nombre">
        {recortar(nombre)}
        <title>{nombre}</title>
      </text>
      {lineas.map((linea, indice) => (
        <text key={linea} x={x} y={y + mitad + 32 + indice * 14} textAnchor="middle" className="plan-detalle">
          {recortar(linea)}
          <title>{linea}</title>
        </text>
      ))}
    </g>
  );
}

/** Texto con las partes importantes resaltadas en amarillo (como en las capturas del informe). */
export function TextoResaltado({ texto, resaltados }) {
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
          <p className="plan-detalle-alertas-titulo">Warnings:</p>
          {nodo.advertencias.map((advertencia) => (
            <p key={advertencia.texto}><TextoResaltado texto={advertencia.texto} resaltados={advertencia.resaltados} /></p>
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

const ANCHO_DETALLE = 480;
const ZOOM_MINIMO = 0.25;
const ZOOM_MAXIMO = 1.5;
const PASO_ZOOM = 0.1;

/** Diagrama de una sentencia del plan con zoom y detalle al pasar el mouse. */
function Diagrama({ sentencia }) {
  const [zoom, setZoom] = useState(0.8);
  const [enfocado, setEnfocado] = useState(null);
  const { posiciones, ancho, alto } = useMemo(() => calcularPosiciones(sentencia.nodos), [sentencia]);
  const maximo = Math.max(...sentencia.nodos.map((nodo) => nodo.costoPct), 0);
  const filasDe = (nodo) => nodo.filasReales ?? nodo.filasEstimadas;
  const filasMaximas = Math.max(...sentencia.nodos.map((nodo) => filasDe(nodo) ?? 0), 1);
  const lienzoRef = useRef(null);
  const cambiarZoom = (valor) => setZoom(Math.round(Math.min(Math.max(valor, ZOOM_MINIMO), ZOOM_MAXIMO) * 100) / 100);
  // «Ajustar»: el plan completo a lo ancho del recuadro.
  const ajustar = () => cambiarZoom(((lienzoRef.current?.clientWidth ?? ancho) - 24) / ancho);

  const alEntrar = (nodo, evento) => {
    const lienzo = evento.currentTarget.ownerSVGElement.parentElement;
    const caja = evento.currentTarget.getBoundingClientRect();
    const base = lienzo.getBoundingClientRect();
    // A la derecha del operador; si no entra en el recuadro visible, a su izquierda.
    const anchoDetalle = Math.min(ANCHO_DETALLE, lienzo.clientWidth - 16);
    let left = caja.right - base.left + lienzo.scrollLeft + 8;
    if (left + anchoDetalle > lienzo.scrollLeft + lienzo.clientWidth) {
      left = Math.max(caja.left - base.left + lienzo.scrollLeft - anchoDetalle - 8, lienzo.scrollLeft + 8);
    }
    setEnfocado({ nodo, posicion: { left, top: caja.top - base.top + lienzo.scrollTop } });
  };

  return (
    <div className="plan-diagrama">
      <div className="plan-zoom" role="group" aria-label="Zoom del diagrama">
        <span className="plan-zoom-etiqueta">Zoom</span>
        <button type="button" onClick={() => cambiarZoom(zoom - PASO_ZOOM)} aria-label="Alejar">−</button>
        <span className="plan-zoom-valor">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => cambiarZoom(zoom + PASO_ZOOM)} aria-label="Acercar">+</button>
        <button type="button" className="plan-zoom-texto" onClick={ajustar}>Ajustar</button>
        <button type="button" className="plan-zoom-texto" onClick={() => cambiarZoom(1)}>100%</button>
      </div>
      <div className="plan-lienzo" ref={lienzoRef}>
        <svg
          width={ancho * zoom}
          height={alto * zoom}
          viewBox={`0 0 ${ancho} ${alto}`}
          role="img"
          aria-label={`Diagrama del plan de la consulta ${sentencia.numero}`}
        >
          <DefinicionesIconos />
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
