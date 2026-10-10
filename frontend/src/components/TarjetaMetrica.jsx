/**
 * Celda del resumen superior: ícono en un círculo del color de su tono, título,
 * cifra y detalle. Se agrupan dentro de un panel único (.metrics-grid).
 * `tono`: critico | alto | medio | bajo (por defecto, el rojo de marca).
 */
export function TarjetaMetrica({ titulo, valor, subtitulo, icono, tono = 'alto' }) {
  return (
    <div className={`metric-card tono-${tono}`}>
      <span className="metric-icon">{icono}</span>
      <div className="metric-body">
        <span className="metric-title">{titulo}</span>
        <strong className="metric-value">{valor}</strong>
        <span className="metric-sub">{subtitulo}</span>
      </div>
    </div>
  );
}
