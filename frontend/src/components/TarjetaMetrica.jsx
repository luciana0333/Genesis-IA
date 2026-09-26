/**
 * Tarjeta de métrica del resumen superior.
 *
 * `tono` define el color de acento: critico | alto | medio | bajo | marca.
 * `proporcion` (0 a 1, opcional) dibuja una barra con el peso de la métrica
 * sobre el total.
 */
export function TarjetaMetrica({ tono = 'marca', titulo, valor, subtitulo, icono, proporcion }) {
  const conBarra = typeof proporcion === 'number';
  return (
    <div className={`metric-card tono-${tono}`}>
      <div className="metric-header">
        <span className="metric-title">{titulo}</span>
        <span className="metric-icon">{icono}</span>
      </div>
      <strong className="metric-value">{valor}</strong>
      <span className="metric-sub">{subtitulo}</span>
      {conBarra && (
        <span className="metric-bar" aria-hidden="true">
          <span className="metric-bar-fill" style={{ width: `${Math.round(proporcion * 100)}%` }} />
        </span>
      )}
    </div>
  );
}
