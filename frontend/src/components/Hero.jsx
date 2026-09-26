export function Hero({ titulo, complemento, descripcion }) {
  return (
    <section className="hero-banner">
      <div className="hero-container">
        <div className="hero-text">
          <span className="badge-tag">Auditoría Inteligente</span>
          <h1>
            {titulo}
            {complemento && <span className="hero-complemento">{complemento}</span>}
          </h1>
          <p>{descripcion}</p>
        </div>
      </div>
    </section>
  );
}
