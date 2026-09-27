/**
 * Celda del resumen superior: nombre (con un punto del color de la severidad,
 * si la tiene), cifra y detalle. Se agrupan dentro de un panel único
 * (.metrics-grid).
 */
export function TarjetaMetrica({ titulo, valor, subtitulo, severidad }) {
  return (
    <div className={severidad ? `metric-card sev-${severidad}` : 'metric-card'}>
      <span className="metric-title">
        {severidad && <span className="metric-dot" aria-hidden="true" />}
        {titulo}
      </span>
      <strong className="metric-value">{valor}</strong>
      <span className="metric-sub">{subtitulo}</span>
    </div>
  );
}
