import { useMemo, useRef, useState } from 'react';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import { tokenizarSql } from '../../utils/resaltadoSql';
import {
  ICONO, MAX_TEXTO, calcularPosiciones, filasDesviadas, formatearFilas, recortar, simboloDe, tonoCosto,
} from './geometriaPlan';
import { DefinicionesIconos } from './IconosPlan';
import { IndicesFaltantes, ParametrosPlan } from './PestanasPlan';

/*
 * Diagrama del plan al estilo de SQL Sentry Plan Explorer: el resultado a la
 * izquierda y los datos fluyendo de derecha a izquierda; costo de cada operador
 * arriba (naranja y rojo para los más caros), filas sobre cada flecha (más
 * gruesa cuantas más filas) y, debajo, operación, tabla e índice. Los operadores
 * con advertencias se resaltan en amarillo con su triángulo.
 */

export function Flecha({ desde, hasta, filas, filasMaximas, desviada = false }) {
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
        <text x={inicio - 4} y={desde.y - grosor / 2 - 4} textAnchor="end" className={desviada ? 'plan-filas desviada' : 'plan-filas'}>
          {formatearFilas(filas)}
        </text>
      )}
    </g>
  );
}

const ANCHO_LETRA = 6.3; // ancho aproximado de un carácter a 11.5 px (Segoe UI)

export function Nodo({ nodo, posicion, maximo, activo, marcado = false, soloMarcado = false, onEntrar, onSalir }) {
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
      {/* En la imagen de una observación (soloMarcado) solo se resalta su operador. */}
      {(marcado || (conAdvertencia && !soloMarcado)) && (
        <rect x={x - anchoNombre / 2} y={y + mitad + 5} width={anchoNombre} height={16} rx={8} className="plan-resaltado" />
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

const MAX_PREDICADO = 420; // el recuadro no se desplaza: los textos muy largos se acortan

/** Detalle del operador como el tooltip de SSMS: mismos nombres y datos del XML. */
function DetalleNodo({ nodo, posicion }) {
  const filas = [
    ['Estimated Operator Cost', nodo.padre === null ? '' : `${nodo.costoPct.toFixed(1)}%`],
    ['Estimated Number of Rows', formatearFilas(nodo.filasEstimadas)],
    ['Actual Number of Rows', formatearFilas(nodo.filasReales)],
    ['Actual Number of Rows Read', formatearFilas(nodo.filasLeidas)],
    ['Number of Executions', formatearFilas(nodo.ejecuciones)],
    ['Actual Logical Reads', formatearFilas(nodo.lecturas)],
  ].filter(([, valor]) => valor);
  return (
    <div className="plan-detalle-flotante" style={{ left: posicion.left, top: posicion.top }} role="tooltip">
      <p className="plan-detalle-titulo">
        {nodo.padre === null ? nodo.fisica.toUpperCase() : nodo.fisica}
        {nodo.logica && nodo.logica !== nodo.fisica && <span> ({nodo.logica})</span>}
      </p>
      {nodo.advertencias.length > 0 && (
        <div className="plan-detalle-alertas">
          <p className="plan-detalle-alertas-titulo">Warnings:</p>
          {nodo.advertencias.map((advertencia) => (
            <p key={advertencia.texto}><TextoResaltado texto={advertencia.texto} resaltados={advertencia.resaltados} /></p>
          ))}
        </div>
      )}
      {filas.length > 0 && (
        <dl>
          {filas.map(([etiqueta, valor]) => (
            <div key={etiqueta}><dt>{etiqueta}</dt><dd>{valor}</dd></div>
          ))}
        </dl>
      )}
      {(nodo.objeto || nodo.indice) && (
        <div className="plan-detalle-bloque">
          <p className="plan-detalle-subtitulo">Object</p>
          <p className="plan-detalle-objeto">{nodo.objetoCompleto || [nodo.objeto, nodo.indice].filter(Boolean).join('.')}</p>
        </div>
      )}
      {(nodo.predicados ?? []).map((predicado) => (
        <div key={predicado.nombre} className="plan-detalle-bloque">
          <p className="plan-detalle-subtitulo">{predicado.nombre}</p>
          <p className="plan-detalle-objeto">
            {predicado.texto.length > MAX_PREDICADO ? `${predicado.texto.slice(0, MAX_PREDICADO - 1)}…` : predicado.texto}
          </p>
        </div>
      ))}
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
              desviada={filasDesviadas(nodo)}
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

function formatearNumero(valor) {
  return valor === null || valor === undefined ? '' : Math.round(valor).toLocaleString('en-US');
}

function porcentaje(valor, total) {
  return total ? `${((valor / total) * 100).toFixed(1)}%` : '';
}

// Columnas de la grilla de sentencias de Plan Explorer, con sus mismos nombres.
// `orden`: el número por el que se ordena la columna al hacer clic en su encabezado.
const udfDuracion = (s) => s.udfDuracionMs ?? (s.duracionMs != null ? 0 : null);
const udfCpu = (s) => s.udfCpuMs ?? (s.cpuMs != null ? 0 : null);
const COLUMNAS_SENTENCIAS = [
  { titulo: 'Est Cost %', valor: (s, t) => porcentaje(s.costo, t.costo), orden: (s) => s.costo },
  { titulo: 'Compile Time', valor: (s) => formatearNumero(s.compilacionMs), orden: (s) => s.compilacionMs },
  { titulo: 'Duration', valor: (s) => formatearNumero(s.duracionMs), orden: (s) => s.duracionMs },
  // Sin funciones en la consulta el XML no trae los tiempos de UDF: Plan Explorer muestra 0.
  { titulo: 'UDF Duration', valor: (s) => formatearNumero(udfDuracion(s)), orden: udfDuracion },
  { titulo: 'CPU', valor: (s) => formatearNumero(s.cpuMs), orden: (s) => s.cpuMs },
  { titulo: 'UDF CPU', valor: (s) => formatearNumero(udfCpu(s)), orden: udfCpu },
  { titulo: 'Est CPU Cost %', valor: (s, t) => porcentaje(s.costoCpu, t.costoCpu), orden: (s) => s.costoCpu },
  { titulo: 'Reads', valor: (s) => formatearNumero(s.lecturas), orden: (s) => s.lecturas },
  { titulo: 'Writes', valor: () => '' },
  { titulo: 'Est IO Cost %', valor: (s, t) => porcentaje(s.costoIo, t.costoIo), orden: (s) => s.costoIo },
  { titulo: 'Est Rows', valor: (s) => formatearNumero(s.filasEstimadas), filas: true, orden: (s) => s.filasEstimadas },
  { titulo: 'Actual Rows', valor: (s) => formatearNumero(s.filasReales), filas: true, orden: (s) => s.filasReales },
];
const COLUMNA_SENTENCIA = { titulo: 'Statement', orden: (s) => (s.texto || s.tipo || '').toLowerCase() };

/**
 * Ordena las sentencias por la columna elegida. Los valores vacíos van siempre al final.
 * direccion: 'desc' (de mayor a menor) o 'asc'; sin columna se deja el orden del plan.
 */
function ordenarSentencias(sentencias, columna, direccion) {
  if (!columna) return sentencias;
  const signo = direccion === 'asc' ? 1 : -1;
  return [...sentencias].sort((a, b) => {
    const va = columna.orden(a);
    const vb = columna.orden(b);
    const vacioA = va === null || va === undefined || va === '';
    const vacioB = vb === null || vb === undefined || vb === '';
    if (vacioA || vacioB) return vacioA === vacioB ? a.numero - b.numero : vacioA ? 1 : -1;
    if (va === vb) return a.numero - b.numero;
    return (va > vb ? 1 : -1) * signo;
  });
}

/** Encabezado que ordena: 1.er clic de mayor a menor, 2.º de menor a mayor, 3.º el orden del plan. */
function EncabezadoOrdenable({ columna, orden, onOrdenar, className }) {
  if (!columna.orden) return <th scope="col" className={className}>{columna.titulo}</th>;
  const activa = orden.titulo === columna.titulo;
  const sentido = activa ? (orden.direccion === 'desc' ? 'descending' : 'ascending') : 'none';
  return (
    <th scope="col" className={className} aria-sort={sentido}>
      <button
        type="button"
        className={activa ? 'plan-orden activa' : 'plan-orden'}
        onClick={() => onOrdenar(columna)}
        title={`Ordenar por ${columna.titulo}`}
      >
        {columna.titulo}
        <span className="plan-orden-flecha" aria-hidden="true">
          {activa ? (orden.direccion === 'desc' ? '▼' : '▲') : '↕'}
        </span>
      </button>
    </th>
  );
}

/** Panel «Text Data» de Plan Explorer: el código de la sentencia tal cual viene en el XML, coloreado. */
function TextoSentencia({ codigo }) {
  if (!codigo) return null;
  return (
    <div className="plan-panel">
      <p className="plan-panel-titulo">Text Data</p>
      <pre className="plan-texto">
        {tokenizarSql(codigo).map((fragmento, indice) => (
          fragmento.tipo === 'texto'
            ? fragmento.valor
            : <span key={indice} className={`tok-${fragmento.tipo}`}>{fragmento.valor}</span>
        ))}
      </pre>
    </div>
  );
}

/** Sentencias del plan (como la grilla de Plan Explorer) y el diagrama de la elegida. */
export function DiagramaPlan({ sentencias = [] }) {
  const [elegida, setElegida] = useState(null);
  const [pestana, setPestana] = useState('diagrama');
  const [orden, setOrden] = useState({ titulo: null, direccion: null });
  if (!sentencias.length) return null;
  // La sentencia elegida se recuerda por su número: al reordenar sigue siendo la misma.
  const sentencia = sentencias.find((s) => s.numero === elegida) ?? sentencias[0];
  const columnaOrden = [COLUMNA_SENTENCIA, ...COLUMNAS_SENTENCIAS].find((c) => c.titulo === orden.titulo);
  const ordenadas = ordenarSentencias(sentencias, columnaOrden, orden.direccion);
  const alOrdenar = (columna) => setOrden((actual) => {
    if (actual.titulo !== columna.titulo) return { titulo: columna.titulo, direccion: 'desc' };
    if (actual.direccion === 'desc') return { titulo: columna.titulo, direccion: 'asc' };
    return { titulo: null, direccion: null };
  });
  const totales = ['costo', 'costoCpu', 'costoIo'].reduce(
    (suma, campo) => ({ ...suma, [campo]: sentencias.reduce((t, s) => t + (s[campo] || 0), 0) }),
    {},
  );

  return (
    <section className="plan-diagrama-seccion">
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Detalle del plan"
        titulo="Diagrama del plan"
        acciones={<span className="results-meta">Pasa el mouse sobre un operador para ver su detalle</span>}
      />
      <div className="table-scroll plan-grilla">
        <table className="plan-sentencias">
          <thead>
            <tr>
              <EncabezadoOrdenable columna={COLUMNA_SENTENCIA} orden={orden} onOrdenar={alOrdenar} />
              {COLUMNAS_SENTENCIAS.map((columna) => (
                <EncabezadoOrdenable key={columna.titulo} columna={columna} orden={orden} onOrdenar={alOrdenar} className="num" />
              ))}
            </tr>
          </thead>
          <tbody>
            {ordenadas.map((item) => {
              // Como Plan Explorer: filas estimadas y reales en naranja si se alejan mucho.
              const desviada = filasDesviadas(item);
              return (
                <tr
                  key={item.numero}
                  className={item === sentencia ? 'elegida' : undefined}
                  onClick={() => setElegida(item.numero)}
                >
                  <td className="plan-sentencia-texto" title={item.texto}>{item.texto || item.tipo}</td>
                  {COLUMNAS_SENTENCIAS.map((columna) => (
                    <td key={columna.titulo} className={columna.filas && desviada ? 'num desviada' : 'num'}>
                      {columna.valor(item, totales)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <TextoSentencia codigo={sentencia.codigo} />
      <div className="plan-vista">
        {pestana === 'diagrama' && <Diagrama key={sentencia.numero} sentencia={sentencia} />}
        {pestana === 'parametros' && <ParametrosPlan parametros={sentencia.parametros} />}
        {pestana === 'indices' && <IndicesFaltantes indices={sentencia.indicesFaltantes} />}
      </div>
      {/* Pestañas al pie, como Plan Explorer; entre paréntesis, cuántos datos trae el XML. */}
      <div className="plan-pestanas" role="tablist" aria-label="Vistas del plan">
        {[
          { id: 'diagrama', etiqueta: 'Plan Diagram' },
          { id: 'parametros', etiqueta: 'Parameters', cantidad: sentencia.parametros?.length ?? 0 },
          { id: 'indices', etiqueta: 'Missing Indexes', cantidad: sentencia.indicesFaltantes?.length ?? 0 },
        ].map((opcion) => (
          <button
            key={opcion.id}
            type="button"
            role="tab"
            aria-selected={pestana === opcion.id}
            className={pestana === opcion.id ? 'plan-pestana activa' : 'plan-pestana'}
            onClick={() => setPestana(opcion.id)}
          >
            {opcion.etiqueta}
            {opcion.cantidad > 0 && <span className="plan-pestana-cantidad">{opcion.cantidad}</span>}
          </button>
        ))}
      </div>
    </section>
  );
}
