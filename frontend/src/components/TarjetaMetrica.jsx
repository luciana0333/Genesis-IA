/**
 * Tarjeta de métrica del encabezado (conteos y valores resumidos).
 * `variante` define el acento visual: critical | high | medium | low.
 */
export function TarjetaMetrica({ variante, titulo, valor, subtitulo, icono }) {
  return (
    <div className={`service-card ${variante}`}>
      <div className="card-header">
        <span className="card-title">{titulo}</span>
        <div className="card-icon-wrap">{icono}</div>
      </div>
      <strong>{valor}</strong>
      <span className="card-sub">{subtitulo}</span>
    </div>
  );
}
