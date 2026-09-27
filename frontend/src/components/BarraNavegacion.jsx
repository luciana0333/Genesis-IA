import logoCajaIca from '../assets/logo-caja-ica.png';
import { VISTAS } from '../config/vistas';
import { IconoBaseDatos, IconoLuna, IconoSol } from './Iconos';

function BarraSuperior({ tema, onAlternarTema }) {
  const esOscuro = tema === 'dark';
  return (
    <div className="topbar">
      <div className="topbar-container">
        <span className="topbar-item">
          <IconoBaseDatos />
          Auditoría de objetos SQL Server
        </span>
        <button
          type="button"
          className="topbar-action"
          onClick={onAlternarTema}
          aria-label="Cambiar tema"
          title={esOscuro ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
        >
          {esOscuro ? <IconoSol /> : <IconoLuna />}
          {esOscuro ? 'Tema claro' : 'Tema oscuro'}
        </button>
      </div>
    </div>
  );
}

export function BarraNavegacion({ vistaActiva, tema, onAlternarTema }) {
  return (
    <>
      <BarraSuperior tema={tema} onAlternarTema={onAlternarTema} />
      <header className="navbar">
        <div className="navbar-container">
          <a className="brand" href="#/diccionarios" aria-label="CAJA ICA · Inicio">
            <img className="brand-logo" src={logoCajaIca} alt="CAJA ICA" width="289" height="58" />
            <span className="brand-divider" aria-hidden="true" />
            <span className="brand-product">Genesis IA</span>
          </a>

          <nav className="nav-links" aria-label="Tipos de revisión">
            {VISTAS.map((vista) => {
              const activa = vista.id === vistaActiva.id;
              return (
                <a
                  key={vista.id}
                  href={`#/${vista.ruta}`}
                  className={activa ? 'nav-link active' : 'nav-link'}
                  aria-current={activa ? 'page' : undefined}
                >
                  {vista.etiqueta}
                </a>
              );
            })}
          </nav>

          <button className="cta-btn" type="button">Acceso Portal</button>
        </div>
      </header>
    </>
  );
}
