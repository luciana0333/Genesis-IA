import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
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

/**
 * Detalle del operador como el tooltip de SSMS: mismos nombres y datos del XML.
 * Flota sobre la página (no se corta en el borde del diagrama) y, si es largo, tiene su propia
 * barra; no se cierra mientras el mouse esté encima, para poder leerlo completo.
 */
function DetalleNodo({ nodo, posicion, onEntrar, onSalir }) {
  // Todos los datos del operador tal cual el XML, con los nombres y el orden de SQL Server.
  // (La raíz de la consulta no tiene: usa los datos de siempre.)
  const filas = nodo.propiedades?.length ? nodo.propiedades : [
    ['Estimated Operator Cost', nodo.padre === null ? '' : `${nodo.costoPct.toFixed(1)}%`],
    ['Estimated Number of Rows', formatearFilas(nodo.filasEstimadas)],
    ['Actual Number of Rows', formatearFilas(nodo.filasReales)],
    ['Actual Number of Rows Read', formatearFilas(nodo.filasLeidas)],
    ['Number of Executions', formatearFilas(nodo.ejecuciones)],
    ['Actual Logical Reads', formatearFilas(nodo.lecturas)],
    ['Actual Physical Reads', formatearFilas(nodo.lecturasFisicas)],
    // Tiempo real del operador (plan real); como en SSMS, incluye a los operadores que lo alimentan.
    ['Actual Elapsed Time (ms)', formatearFilas(nodo.duracionMs)],
    ['Actual Elapsed CPU Time (ms)', formatearFilas(nodo.cpuMs)],
  ].filter(([, valor]) => valor);
  return createPortal(
    <div
      className="plan-detalle-flotante"
      style={posicion}
      role="tooltip"
      onMouseEnter={onEntrar}
      onMouseLeave={onSalir}
    >
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
          <p className="plan-detalle-objeto">{predicado.texto}</p>
        </div>
      ))}
    </div>,
    document.body,
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

  // El detalle se cierra con una pequeña espera: así da tiempo de pasar el mouse del operador al recuadro.
  const cierre = useRef(null);
  const mantener = () => clearTimeout(cierre.current);
  const cerrar = () => {
    clearTimeout(cierre.current);
    cierre.current = setTimeout(() => setEnfocado(null), 180);
  };
  useEffect(() => () => clearTimeout(cierre.current), []);
  // Si la página o el diagrama se desplazan, el recuadro ya no está junto a su operador: se cierra.
  // (Bajar dentro del propio recuadro no lo cierra.)
  useEffect(() => {
    if (!enfocado) return undefined;
    const alDesplazar = (evento) => {
      if (!(evento.target instanceof Element && evento.target.closest('.plan-detalle-flotante'))) setEnfocado(null);
    };
    window.addEventListener('scroll', alDesplazar, true);
    return () => window.removeEventListener('scroll', alDesplazar, true);
  }, [enfocado]);

  const alEntrar = (nodo, evento) => {
    mantener();
    const caja = evento.currentTarget.getBoundingClientRect();
    const margen = 8;
    // A la derecha del operador; si no entra en la pantalla, a su izquierda.
    const anchoDetalle = Math.min(ANCHO_DETALLE, window.innerWidth - margen * 2);
    let left = caja.right + margen;
    if (left + anchoDetalle > window.innerWidth - margen) {
      left = Math.max(caja.left - anchoDetalle - margen, margen);
    }
    // Hacia abajo desde el operador o, si arriba hay más espacio, hacia arriba; lo que no entra se baja
    // con la barra del propio recuadro.
    const espacioAbajo = window.innerHeight - caja.top - margen;
    const espacioArriba = caja.bottom - margen;
    const posicion = espacioAbajo >= 360 || espacioAbajo >= espacioArriba
      ? { left, top: caja.top, maxHeight: espacioAbajo }
      : { left, bottom: window.innerHeight - caja.bottom, maxHeight: espacioArriba };
    setEnfocado({ nodo, posicion: { ...posicion, width: anchoDetalle } });
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
              onSalir={cerrar}
            />
          ))}
        </svg>
        {enfocado && (
          <DetalleNodo nodo={enfocado.nodo} posicion={enfocado.posicion} onEntrar={mantener} onSalir={cerrar} />
        )}
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

/*
 * Paneles ajustables como en Plan Explorer: la grilla de sentencias, el Text Data y el diagrama
 * comparten un alto fijo y se reparten el espacio arrastrando las barras que los separan
 * (doble clic en una barra: medidas iniciales). Las medidas se recuerdan en este navegador.
 */
const ALTOS_INICIALES = { grilla: 150, texto: 130 };
const ALTO_MINIMO = 44;
const ALTO_MINIMO_DIAGRAMA = 160;
const ALTO_TOTAL = 760; // grilla + Text Data + diagrama, como la ventana de Plan Explorer
const CLAVE_ALTOS = 'genesis.planes.paneles';

function leerAltos() {
  try {
    const guardados = JSON.parse(localStorage.getItem(CLAVE_ALTOS) || 'null');
    if (guardados && Number.isFinite(guardados.grilla) && Number.isFinite(guardados.texto)) return guardados;
  } catch {
    // Sin almacenamiento (ventana privada, bloqueado): se usan las medidas iniciales.
  }
  return ALTOS_INICIALES;
}

function guardarAltos(altos) {
  try {
    localStorage.setItem(CLAVE_ALTOS, JSON.stringify(altos));
  } catch {
    // Sin almacenamiento: las medidas valen solo mientras la página esté abierta.
  }
}

/** Barra entre dos paneles: al arrastrarla cambia el alto del panel de arriba. */
function Divisor({ etiqueta, alto, minimo, maximo, onCambiar, onReiniciar }) {
  const alPresionar = (evento) => {
    evento.preventDefault();
    const barra = evento.currentTarget;
    barra.setPointerCapture?.(evento.pointerId);
    barra.classList.add('arrastrando');
    const inicioY = evento.clientY;
    const mover = (ev) => onCambiar(Math.round(Math.min(Math.max(alto + ev.clientY - inicioY, minimo), maximo)));
    const soltar = () => {
      barra.classList.remove('arrastrando');
      barra.removeEventListener('pointermove', mover);
      barra.removeEventListener('pointerup', soltar);
      barra.removeEventListener('pointercancel', soltar);
    };
    barra.addEventListener('pointermove', mover);
    barra.addEventListener('pointerup', soltar);
    barra.addEventListener('pointercancel', soltar);
  };
  // Con el teclado: flechas arriba y abajo de 20 en 20 píxeles.
  const alTeclear = (evento) => {
    const paso = { ArrowUp: -20, ArrowDown: 20 }[evento.key];
    if (!paso) return;
    evento.preventDefault();
    onCambiar(Math.min(Math.max(alto + paso, minimo), maximo));
  };
  return (
    <div
      className="plan-divisor"
      role="separator"
      aria-orientation="horizontal"
      aria-label={etiqueta}
      aria-valuenow={alto}
      aria-valuemin={minimo}
      aria-valuemax={maximo}
      tabIndex={0}
      title="Arrastra para ajustar · doble clic: medidas iniciales"
      onPointerDown={alPresionar}
      onDoubleClick={onReiniciar}
      onKeyDown={alTeclear}
    />
  );
}

/** Panel «Text Data» de Plan Explorer: el código de la sentencia tal cual viene en el XML, coloreado. */
function TextoSentencia({ codigo, alto }) {
  if (!codigo) return null;
  return (
    <div className="plan-panel" style={{ height: alto }}>
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
  const [altos, setAltos] = useState(leerAltos);
  const cambiarAlto = (panel) => (valor) => setAltos((actuales) => {
    const nuevos = { ...actuales, [panel]: valor };
    guardarAltos(nuevos);
    return nuevos;
  });
  const reiniciarAltos = () => {
    setAltos(ALTOS_INICIALES);
    guardarAltos(ALTOS_INICIALES);
  };
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
  // El diagrama se queda con lo que dejan la grilla y el Text Data (al menos ALTO_MINIMO_DIAGRAMA).
  const conTexto = Boolean(sentencia.codigo);
  const libre = ALTO_TOTAL - ALTO_MINIMO_DIAGRAMA - 60;
  const maximoGrilla = Math.max(ALTO_MINIMO, libre - (conTexto ? altos.texto : 0));
  const maximoTexto = Math.max(ALTO_MINIMO, libre - altos.grilla);

  return (
    <section className="plan-diagrama-seccion">
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Detalle del plan"
        titulo="Diagrama del plan"
        acciones={<span className="results-meta">Pasa el mouse sobre un operador para ver su detalle</span>}
      />
      <div className="plan-paneles" style={{ height: ALTO_TOTAL }}>
        <div className="table-scroll plan-grilla" style={{ height: Math.min(altos.grilla, maximoGrilla) }}>
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
        <Divisor
          etiqueta="Alto de la grilla de sentencias"
          alto={Math.min(altos.grilla, maximoGrilla)}
          minimo={ALTO_MINIMO}
          maximo={maximoGrilla}
          onCambiar={cambiarAlto('grilla')}
          onReiniciar={reiniciarAltos}
        />
        <TextoSentencia codigo={sentencia.codigo} alto={Math.min(altos.texto, maximoTexto)} />
        {conTexto && (
          <Divisor
            etiqueta="Alto del Text Data"
            alto={Math.min(altos.texto, maximoTexto)}
            minimo={ALTO_MINIMO}
            maximo={maximoTexto}
            onCambiar={cambiarAlto('texto')}
            onReiniciar={reiniciarAltos}
          />
        )}
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
      </div>
    </section>
  );
}
