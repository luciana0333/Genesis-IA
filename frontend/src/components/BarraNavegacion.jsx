import { VISTAS } from '../config/vistas';
import { IconoLuna } from './Iconos';

export function BarraNavegacion({ vistaActiva, onAlternarTema }) {
  return (
    <header className="navbar-full">
      <div className="navbar-container">
        <div className="brand">
          <div className="brand-logo">
            <span className="logo-circle" />
            <span className="logo-text">CAJA ICA</span>
          </div>
        </div>

        <nav className="nav-menu" aria-label="Tipos de revisión">
          {VISTAS.map((vista) => {
            const activa = vista.id === vistaActiva.id;
            return (
              <a
                key={vista.id}
                href={`#/${vista.ruta}`}
                className={activa ? 'active' : undefined}
                aria-current={activa ? 'page' : undefined}
              >
                {vista.etiqueta}
              </a>
            );
          })}
        </nav>

        <div className="nav-actions">
          <button
            className="theme-btn"
            type="button"
            aria-label="Cambiar tema"
            title="Cambiar tema"
            onClick={onAlternarTema}
          >
            <IconoLuna className="theme-svg" />
          </button>
          <button className="cta-btn" type="button">Acceso Portal</button>
        </div>
      </div>
    </header>
  );
}
