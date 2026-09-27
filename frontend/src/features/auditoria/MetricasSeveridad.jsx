import { SEVERIDADES, etiquetaSeveridad } from '../../config/reglas';

const NOMBRES = { critico: 'Críticos', alto: 'Altos', medio: 'Medios', bajo: 'Bajos' };

/**
 * Resumen del análisis: total de hallazgos, barra con la proporción de cada
 * severidad (tonos de rojo: más oscuro cuanto más grave) y el desglose.
 */
export function MetricasSeveridad({ conteo }) {
  const total = SEVERIDADES.reduce((suma, severidad) => suma + (conteo[severidad] || 0), 0);
  const descripcionBarra = SEVERIDADES
    .map((severidad) => `${conteo[severidad] || 0} ${etiquetaSeveridad(severidad).toLowerCase()}`)
    .join(', ');

  return (
    <section className="resumen" aria-label="Resumen por severidad">
      <p className="resumen-total">
        <strong>{total}</strong>
        <span>{total === 1 ? 'hallazgo en total' : 'hallazgos en total'}</span>
      </p>

      <div className="resumen-barra" role="img" aria-label={`Proporción: ${descripcionBarra}`}>
        {total > 0 && SEVERIDADES.map((severidad) => (
          conteo[severidad] > 0 && (
            <span
              key={severidad}
              className={`resumen-segmento sev-${severidad}`}
              style={{ width: `${(conteo[severidad] / total) * 100}%` }}
            />
          )
        ))}
      </div>

      <div className="resumen-grid">
        {SEVERIDADES.map((severidad) => (
          <div key={severidad} className={`resumen-item sev-${severidad}`}>
            <span className="resumen-nombre">{NOMBRES[severidad]}</span>
            <strong className="resumen-cifra">{conteo[severidad] || 0}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
