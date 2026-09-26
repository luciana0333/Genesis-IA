export function Hero({ titulo, complemento, descripcion, seccion }) {
  return (
    <section className="hero">
      <div className="hero-container">
        <div className="hero-text">
          <p className="hero-breadcrumb">
            <span className="hero-badge">Auditoría Inteligente</span>
            <span className="hero-breadcrumb-sep" aria-hidden="true">/</span>
            <span>{seccion}</span>
          </p>
          <h1>
            {titulo}
            {complemento && <span className="hero-complemento">{complemento}</span>}
          </h1>
          <p className="hero-descripcion">{descripcion}</p>
        </div>
      </div>
    </section>
  );
}
