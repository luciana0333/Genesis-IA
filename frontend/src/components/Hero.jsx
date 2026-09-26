/**
 * Encabezado de cada pestaña: etiqueta de ubicación, título y descripción
 * sobre la foto de fondo. Un solo recurso visual (la foto con degradado,
 * zoom lento y un halo de luz) para mantenerlo limpio.
 */
export function Hero({ titulo, complemento, descripcion, seccion }) {
  return (
    <section className="hero">
      <span className="hero-media" aria-hidden="true" />
      <span className="hero-glow" aria-hidden="true" />
      <div className="hero-container">
        <p className="hero-eyebrow">
          <span>Auditoría inteligente</span>
          <span className="hero-eyebrow-sep" aria-hidden="true" />
          <span>{seccion}</span>
          {complemento && (
            <>
              <span className="hero-eyebrow-sep" aria-hidden="true" />
              <span>{complemento}</span>
            </>
          )}
        </p>
        <h1>{titulo}</h1>
        <p className="hero-descripcion">{descripcion}</p>
      </div>
    </section>
  );
}
