export function Hero({ titulo, complemento, descripcion, seccion }) {
  return (
    <section className="hero">
      <span className="hero-shape hero-shape--a" aria-hidden="true" />
      <span className="hero-shape hero-shape--b" aria-hidden="true" />
      <span className="hero-shape hero-shape--c" aria-hidden="true" />
      <div className="hero-container">
        <p className="hero-eyebrow">
          <span>Auditoría inteligente</span>
          <span className="hero-eyebrow-sep" aria-hidden="true" />
          <span>{seccion}</span>
        </p>
        <h1>
          {titulo}
          {complemento && <span className="hero-complemento">{complemento}</span>}
        </h1>
        <p className="hero-descripcion">{descripcion}</p>
      </div>
    </section>
  );
}
