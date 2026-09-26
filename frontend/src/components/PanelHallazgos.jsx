import { useMemo, useState } from 'react';
import { SEVERIDADES, etiquetaSeveridad, nombreRegla } from '../config/reglas';
import { contarPorSeveridad, normalizarSeveridad, ordenarHallazgos } from '../utils/hallazgos';
import { EstadoVacio } from './EstadoVacio';
import { IconoBandeja, IconoErrorCirculo, IconoEscudoCheck } from './Iconos';

function TarjetaHallazgo({ hallazgo, origenPorDefecto, mostrarLinea }) {
  const severidad = normalizarSeveridad(hallazgo.severidad);
  const titulo = nombreRegla(hallazgo.regla);
  const origen = hallazgo.origen || origenPorDefecto;
  return (
    <article className={`finding sev-${severidad}`}>
      <div className="finding-main">
        <div className="finding-top">
          <span className={`sev-badge sev-${severidad}`}>{etiquetaSeveridad(severidad)}</span>
          <h4 className="finding-title">{titulo}</h4>
        </div>
        <p className="finding-message">{hallazgo.mensaje || 'Revisa este hallazgo.'}</p>
        <div className="finding-meta">
          {hallazgo.regla && hallazgo.regla !== titulo && <code>{hallazgo.regla}</code>}
          <span>{origen}</span>
        </div>
      </div>
      {mostrarLinea && <span className="finding-line">Línea {hallazgo.linea || 1}</span>}
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
          <TarjetaHallazgo
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

  return (
    <section className="results-panel" aria-live="polite" aria-busy={estado === 'cargando'}>
      <div className="results-header">
        <div className="results-heading">
          <h3>{titulo}</h3>
          {hayHallazgos && <span className="count-pill">{hallazgos.length}</span>}
        </div>
        {meta && <span className="results-meta">{meta}</span>}
      </div>
      {hayHallazgos && (
        <FiltrosSeveridad conteo={conteo} total={hallazgos.length} filtro={filtro} onFiltrar={setFiltro} />
      )}
      {contenido}
    </section>
  );
}
