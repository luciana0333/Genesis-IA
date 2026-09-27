/**
 * Celda del resumen superior: nombre, cifra y detalle. Se agrupan dentro de
 * un panel único (.metrics-grid).
 */
export function TarjetaMetrica({ titulo, valor, subtitulo }) {
  return (
    <div className="metric-card">
      <span className="metric-title">{titulo}</span>
      <strong className="metric-value">{valor}</strong>
      <span className="metric-sub">{subtitulo}</span>
    </div>
  );
}
