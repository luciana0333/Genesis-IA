import { useMemo, useState } from 'react';
import { SEVERIDADES, etiquetaSeveridad, nombreRegla } from '../config/reglas';
import { contarPorSeveridad, desglosarGrupo, normalizarSeveridad, ordenarHallazgos, separarMensaje } from '../utils/hallazgos';
import { EncabezadoSeccion } from './EncabezadoSeccion';
import { EstadoVacio } from './EstadoVacio';
import {
  IconoBandeja,
  IconoCopiar,
  IconoCopiado,
  IconoErrorCirculo,
  IconoEscudoAlerta,
  IconoEscudoCheck,
} from './Iconos';

/** Resalta lo que el mensaje cita entre comillas simples: 'Indicatg', 'dbo2'. */
function MensajeResaltado({ texto }) {
  const partes = texto.split(/('[^'\n]+')/g);
  return partes.map((parte, indice) =>
    /^'[^'\n]+'$/.test(parte)
      ? <mark key={indice} className="finding-token">{parte.slice(1, -1)}</mark>
      : parte,
  );
}

const VEREDICTOS = {
  critico: { titulo: 'Requiere correcciones', texto: 'Hay errores críticos que impiden aprobar el objeto.' },
  alto: { titulo: 'Requiere correcciones', texto: 'Corrija los hallazgos de severidad alta antes de pasar a producción.' },
  medio: { titulo: 'Con observaciones', texto: 'Revise las observaciones de severidad media; no bloquean, pero conviene corregirlas.' },
  bajo: { titulo: 'Observaciones menores', texto: 'Solo hay recomendaciones o puntos por validar.' },
};

function ResumenVeredicto({ conteo, total }) {
  const mayor = SEVERIDADES.find((severidad) => conteo[severidad] > 0) ?? 'bajo';
  const veredicto = VEREDICTOS[mayor];
  const Icono = mayor === 'bajo' ? IconoEscudoCheck : IconoEscudoAlerta;
  const desglose = SEVERIDADES
    .filter((severidad) => conteo[severidad] > 0)
    .map((severidad) => `${conteo[severidad]} ${etiquetaSeveridad(severidad).toLowerCase()}`)
    .join(' · ');
  return (
    <div className={`verdict sev-${mayor}`} role="status">
      <span className="verdict-icon"><Icono /></span>
      <div className="verdict-body">
        <p className="verdict-kicker">Resultado de la revisión</p>
        <p className="verdict-title">{veredicto.titulo}</p>
        <p className="verdict-text">{veredicto.texto}</p>
      </div>
      <div className="verdict-count">
        <strong>{total}</strong>
        <span>{total === 1 ? 'hallazgo' : 'hallazgos'} · {desglose}</span>
      </div>
    </div>
  );
}

function textoParaCopiar(hallazgo, mostrarLinea) {
  const severidad = etiquetaSeveridad(normalizarSeveridad(hallazgo.severidad));
  const ubicacion = mostrarLinea ? ` (línea ${hallazgo.linea || 1})` : '';
  return `[${severidad}] ${nombreRegla(hallazgo.regla)}${ubicacion}: ${hallazgo.mensaje}`;
}

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    return false;
  }
}

/** Botón que copia un texto y confirma durante un momento. */
function BotonCopiar({ texto, etiqueta, conTexto = false }) {
  const [copiado, setCopiado] = useState(false);
  const alCopiar = async () => {
    if (await copiar(texto)) {
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1600);
    }
  };
  return (
    <button
      type="button"
      className={conTexto ? 'copy-btn copy-btn--texto' : 'copy-btn'}
      onClick={alCopiar}
      aria-label={copiado ? 'Copiado' : etiqueta}
      title={copiado ? 'Copiado' : etiqueta}
    >
      {copiado ? <IconoCopiado /> : <IconoCopiar />}
      {conTexto && <span>{copiado ? 'Copiado' : etiqueta}</span>}
    </button>
  );
}

/**
 * Ficha de un hallazgo: encabezado (regla, severidad y líneas) y dos columnas,
 * "Qué se encontró" y "Qué hacer". Si el hallazgo agrupa varias ocurrencias,
 * cada una se lista por separado.
 */
function FilaHallazgo({ hallazgo, mostrarLinea }) {
  const severidad = normalizarSeveridad(hallazgo.severidad);
  const titulo = nombreRegla(hallazgo.regla);
  const mensaje = hallazgo.mensaje || 'Revisa este hallazgo.';
  const { problema, solucion } = separarMensaje(mensaje);
  const { lineas, ocurrencias } = desglosarGrupo(problema);
  const etiquetaLinea = lineas
    ? `${lineas.includes(',') ? 'Líneas' : 'Línea'} ${lineas}`
    : `Línea ${hallazgo.linea || 1}`;

  return (
    <article className={`finding sev-${severidad}`}>
      <header className="finding-head">
        <h4 className="finding-title">{titulo}</h4>
        <span className={`sev-pill sev-${severidad}`}>{etiquetaSeveridad(severidad)}</span>
        <span className="finding-head-side">
          {mostrarLinea && <span className="finding-line">{etiquetaLinea}</span>}
          <BotonCopiar texto={textoParaCopiar(hallazgo, mostrarLinea)} etiqueta="Copiar observación" />
        </span>
      </header>

      <div className={solucion ? 'finding-body' : 'finding-body finding-body--simple'}>
        <section className="finding-col">
          <p className="finding-label">Qué se encontró</p>
          {ocurrencias.length > 1 ? (
            <ul className="finding-list">
              {ocurrencias.map((texto) => <li key={texto}><MensajeResaltado texto={texto} /></li>)}
            </ul>
          ) : (
            <p className="finding-message"><MensajeResaltado texto={ocurrencias[0]} /></p>
          )}
        </section>
        {solucion && (
          <section className="finding-col finding-col--fix">
            <p className="finding-label">Qué hacer</p>
            <p className="finding-message"><MensajeResaltado texto={solucion} /></p>
          </section>
        )}
      </div>

    </article>
  );
}

function EsqueletoCarga() {
  return (
    <div className="findings-skeleton" aria-hidden="true">
      {[0, 1, 2].map((indice) => <div key={indice} className="skeleton-card" />)}
    </div>
  );
}

function FiltrosSeveridad({ conteo, total, filtro, onFiltrar }) {
  const opciones = [
    { id: 'todos', etiqueta: 'Todos', cantidad: total },
    ...SEVERIDADES.filter((severidad) => conteo[severidad] > 0).map((severidad) => ({
      id: severidad,
      etiqueta: etiquetaSeveridad(severidad),
      cantidad: conteo[severidad],
    })),
  ];
  return (
    <div className="filter-chips" role="group" aria-label="Filtrar por severidad">
      {opciones.map((opcion) => (
        <button
          key={opcion.id}
          type="button"
          className={`chip chip-${opcion.id}${filtro === opcion.id ? ' active' : ''}`}
          aria-pressed={filtro === opcion.id}
          onClick={() => onFiltrar(opcion.id)}
        >
          {opcion.id !== 'todos' && <span className="chip-dot" aria-hidden="true" />}
          {opcion.etiqueta}
          <span className="chip-count">{opcion.cantidad}</span>
        </button>
      ))}
    </div>
  );
}

/**
 * Panel de resultados de un análisis.
 *
 * estado: 'inicial' | 'cargando' | 'listo' | 'error'
 * textos: { inicial, cargando, sinHallazgos, tituloError } — mensajes por estado.
 */
export function PanelHallazgos({
  titulo,
  meta,
  estado,
  hallazgos = [],
  mensajeError,
  textos,
  mostrarLinea = true,
}) {
  const [filtroElegido, setFiltro] = useState('todos');
  const conteo = useMemo(() => contarPorSeveridad(hallazgos), [hallazgos]);
  const ordenados = useMemo(() => ordenarHallazgos(hallazgos), [hallazgos]);

  // Si el filtro elegido ya no tiene resultados (nuevo análisis), se vuelve a "Todos".
  const filtro = filtroElegido !== 'todos' && !conteo[filtroElegido] ? 'todos' : filtroElegido;
  const visibles = filtro === 'todos'
    ? ordenados
    : ordenados.filter((hallazgo) => normalizarSeveridad(hallazgo.severidad) === filtro);
  const hayHallazgos = estado === 'listo' && hallazgos.length > 0;

  let contenido;
  if (estado === 'cargando') {
    contenido = (
      <>
        <p className="loading-text">{textos.cargando}</p>
        <EsqueletoCarga />
      </>
    );
  } else if (estado === 'error') {
    contenido = (
      <EstadoVacio tono="error" icono={<IconoErrorCirculo />} titulo={textos.tituloError}>
        {mensajeError}
      </EstadoVacio>
    );
  } else if (estado === 'listo' && !hallazgos.length) {
    contenido = (
      <EstadoVacio tono="exito" icono={<IconoEscudoCheck />} titulo="Sin hallazgos">
        {textos.sinHallazgos}
      </EstadoVacio>
    );
  } else if (hayHallazgos) {
    contenido = (
      <div className="findings-list">
        {visibles.map((hallazgo, indice) => (
          <FilaHallazgo
            // El backend no envía un id; regla + línea + posición es estable por resultado.
            key={`${hallazgo.regla}-${hallazgo.linea}-${indice}`}
            hallazgo={hallazgo}
            mostrarLinea={mostrarLinea}
          />
        ))}
      </div>
    );
  } else {
    contenido = (
      <EstadoVacio icono={<IconoBandeja />} titulo="Aún no hay resultados">
        {textos.inicial}
      </EstadoVacio>
    );
  }

  const textoTodos = visibles.map((h, i) => `${i + 1}. ${textoParaCopiar(h, mostrarLinea)}`).join('\n');

  return (
    <section className="results-panel" aria-live="polite" aria-busy={estado === 'cargando'}>
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Paso 2 · Resultados"
        titulo={titulo}
        acciones={
          <>
            {meta && <span className="results-meta">{meta}</span>}
            {hayHallazgos && <BotonCopiar texto={textoTodos} etiqueta="Copiar todo" conTexto />}
          </>
        }
      />
      {hayHallazgos && <ResumenVeredicto conteo={conteo} total={hallazgos.length} />}
      {hayHallazgos && (
        <FiltrosSeveridad conteo={conteo} total={hallazgos.length} filtro={filtro} onFiltrar={setFiltro} />
      )}
      {contenido}
    </section>
  );
}
