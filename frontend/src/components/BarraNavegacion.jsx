import logoCajaIca from '../assets/logo-caja-ica.png';
import { VISTAS } from '../config/vistas';
import { IconoLuna, IconoSol } from './Iconos';

export function BarraNavegacion({ vistaActiva, tema, onAlternarTema }) {
  const esOscuro = tema === 'dark';
  return (
    <header className="navbar">
      <div className="navbar-container">
        <a className="brand" href="#/diccionarios" aria-label="CAJA ICA · Inicio">
          <img className="brand-logo" src={logoCajaIca} alt="CAJA ICA" width="289" height="58" />
          <span className="brand-divider" aria-hidden="true" />
          <span className="brand-product">Auditor SQL</span>
        </a>

        <nav className="nav-tabs" aria-label="Tipos de revisión">
          {VISTAS.map((vista) => {
            const activa = vista.id === vistaActiva.id;
            return (
              <a
                key={vista.id}
                href={`#/${vista.ruta}`}
                className={activa ? 'nav-tab active' : 'nav-tab'}
                aria-current={activa ? 'page' : undefined}
              >
                {vista.etiqueta}
              </a>
            );
          })}
        </nav>

        <div className="nav-actions">
          <button
            className="icon-btn"
            type="button"
            aria-label="Cambiar tema"
            title={esOscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
            onClick={onAlternarTema}
          >
            {esOscuro ? <IconoSol /> : <IconoLuna />}
          </button>
          <button className="cta-btn" type="button">Acceso Portal</button>
        </div>
      </div>
    </header>
  );
}
