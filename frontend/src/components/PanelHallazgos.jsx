import { useMemo, useState } from 'react';
import { SEVERIDADES, etiquetaSeveridad, nombreRegla } from '../config/reglas';
import { contarPorSeveridad, normalizarSeveridad, ordenarHallazgos } from '../utils/hallazgos';
import { EstadoVacio } from './EstadoVacio';
import {
  IconoBandeja,
  IconoCopiar,
  IconoCopiado,
  IconoErrorCirculo,
  IconoEscudoCheck,
  IconoSeveridadAlta,
  IconoSeveridadBaja,
  IconoSeveridadCritica,
  IconoSeveridadMedia,
} from './Iconos';

const ICONOS_SEVERIDAD = {
  critico: IconoSeveridadCritica,
  alto: IconoSeveridadAlta,
  medio: IconoSeveridadMedia,
  bajo: IconoSeveridadBaja,
};

const ORIGENES = {
  diccionario: 'Diccionario',
  reglas_estaticas: 'Reglas estáticas',
  plan_ejecucion: 'Plan de ejecución',
};

/** Resalta lo que el mensaje cita entre comillas simples: 'Indicatg', 'dbo2'. */
function MensajeResaltado({ texto }) {
  const partes = texto.split(/('[^'\n]+')/g);
  return partes.map((parte, indice) =>
    /^'[^'\n]+'$/.test(parte)
      ? <mark key={indice} className="finding-token">{parte.slice(1, -1)}</mark>
      : parte,
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

function FilaHallazgo({ hallazgo, origenPorDefecto, mostrarLinea }) {
  const severidad = normalizarSeveridad(hallazgo.severidad);
  const Icono = ICONOS_SEVERIDAD[severidad] ?? IconoSeveridadMedia;
  const titulo = nombreRegla(hallazgo.regla);
  const origen = hallazgo.origen || origenPorDefecto;
  const mensaje = hallazgo.mensaje || 'Revisa este hallazgo.';
  return (
    <article className={`finding sev-${severidad}`}>
      <span className="finding-icon"><Icono /></span>
      <div className="finding-content">
        <div className="finding-head">
          <h4 className="finding-title">{titulo}</h4>
          <span className={`sev-pill sev-${severidad}`}>{etiquetaSeveridad(severidad)}</span>
        </div>
        <p className="finding-message"><MensajeResaltado texto={mensaje} /></p>
        <div className="finding-meta">
          {mostrarLinea && <span>Línea {hallazgo.linea || 1}</span>}
          <span>{ORIGENES[origen] ?? origen}</span>
          {hallazgo.regla && hallazgo.regla !== titulo && <code>{hallazgo.regla}</code>}
        </div>
      </div>
      <BotonCopiar texto={textoParaCopiar(hallazgo, mostrarLinea)} etiqueta="Copiar observación" />
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
  origenPorDefecto,
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
            origenPorDefecto={origenPorDefecto}
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
      <div className="results-header">
        <div className="results-heading">
          <h3>{titulo}</h3>
          {hayHallazgos && <span className="count-pill">{hallazgos.length}</span>}
        </div>
        <div className="results-actions">
          {meta && <span className="results-meta">{meta}</span>}
          {hayHallazgos && <BotonCopiar texto={textoTodos} etiqueta="Copiar todo" conTexto />}
        </div>
      </div>
      {hayHallazgos && (
        <FiltrosSeveridad conteo={conteo} total={hallazgos.length} filtro={filtro} onFiltrar={setFiltro} />
      )}
      {contenido}
    </section>
  );
}
