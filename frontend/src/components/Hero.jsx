/**
 * Encabezado de cada pestaña: etiqueta, título y descripción sobre la foto
 * de fondo. Al montarse, un destello de luz cruza el encabezado una vez.
 */
export function Hero({ titulo, complemento, descripcion }) {
  return (
    <section className="hero">
      <div className="hero-container">
        <p className="hero-eyebrow">{complemento ?? 'Auditoría inteligente'}</p>
        <h1>{titulo}</h1>
        <p className="hero-descripcion">{descripcion}</p>
      </div>
    </section>
  );
}
