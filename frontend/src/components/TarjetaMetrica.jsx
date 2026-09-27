/**
 * Tarjeta de indicador: nombre arriba con su ícono a la derecha (en una
 * pastilla del color de la severidad, si la tiene), cifra grande y detalle.
 */
export function TarjetaMetrica({ titulo, valor, subtitulo, icono, severidad }) {
  return (
    <div className={severidad ? `metric-card sev-${severidad}` : 'metric-card'}>
      <div className="metric-head">
        <span className="metric-title">{titulo}</span>
        <span className="metric-icon">{icono}</span>
      </div>
      <strong className="metric-value">{valor}</strong>
      <span className="metric-sub">{subtitulo}</span>
    </div>
  );
}
