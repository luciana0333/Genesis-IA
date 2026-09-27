/**
 * Celda del resumen superior: ícono de línea, título en mayúsculas, cifra y
 * detalle. Se agrupan dentro de un panel único (.metrics-grid).
 */
export function TarjetaMetrica({ titulo, valor, subtitulo, icono }) {
  return (
    <div className="metric-card">
      <span className="metric-icon">{icono}</span>
      <div className="metric-body">
        <span className="metric-title">{titulo}</span>
        <strong className="metric-value">{valor}</strong>
        <span className="metric-sub">{subtitulo}</span>
      </div>
    </div>
  );
}
