import { etiquetaSeveridad, nombreRegla } from '../config/reglas';
import { normalizarSeveridad } from '../utils/hallazgos';

function TarjetaHallazgo({ hallazgo, origenPorDefecto }) {
  const severidad = normalizarSeveridad(hallazgo.severidad);
  return (
    <article className={`finding-card ${severidad}`}>
      <div className="finding-header">
        <div className="finding-title-wrap">
          <span className={`finding-badge ${severidad}`}>{etiquetaSeveridad(severidad)}</span>
          <h4 className="finding-title">{nombreRegla(hallazgo.regla)}</h4>
        </div>
        <span className="finding-meta">
          Línea {hallazgo.linea || 1} · {hallazgo.origen || origenPorDefecto}
        </span>
      </div>
      <p className="finding-body">{hallazgo.mensaje || 'Revisa este hallazgo.'}</p>
    </article>
  );
}

/**
 * Lista de hallazgos o, si no hay ninguno, el recuadro de estado vacío con
 * el mensaje recibido (puede incluir marcado, por eso es un nodo React).
 */
export function ListaHallazgos({ hallazgos, mensajeVacio, origenPorDefecto }) {
  if (!hallazgos?.length) {
    return <div className="empty-state" role="status">{mensajeVacio}</div>;
  }
  return (
    <div className="results-list">
      {hallazgos.map((hallazgo, indice) => (
        <TarjetaHallazgo
          // El backend no envía un id; regla + línea + posición es estable por resultado.
          key={`${hallazgo.regla}-${hallazgo.linea}-${indice}`}
          hallazgo={hallazgo}
          origenPorDefecto={origenPorDefecto}
        />
      ))}
    </div>
  );
}
