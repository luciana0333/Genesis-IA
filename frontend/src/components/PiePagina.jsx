import logoCajaIca from '../assets/logo-caja-ica.png';
import { VISTAS } from '../config/vistas';
import { IconoBaseDatos, IconoCandado, IconoEscudoCheck, IconoLibro, IconoPunto } from './Iconos';

/**
 * Pie de página corporativo: marca y descripción, accesos a los módulos,
 * referencias y privacidad; abajo, derechos y autoría.
 */
export function PiePagina() {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-marca">
          <span className="footer-logo"><img src={logoCajaIca} alt="CAJA ICA" width="289" height="58" /></span>
          <strong>Genesis IA</strong>
          <p>Auditoría de objetos SQL Server con las reglas del manual de nomenclatura de CAJA ICA.</p>
        </div>

        <nav className="footer-columna" aria-label="Módulos">
          <h2>Módulos</h2>
          <ul>
            {VISTAS.map((vista) => (
              <li key={vista.id}><a href={`#/${vista.ruta}`}>{vista.etiqueta}</a></li>
            ))}
          </ul>
        </nav>

        <div className="footer-columna">
          <h2>Referencia</h2>
          <ul>
            <li><IconoLibro />Manual de nomenclatura</li>
            <li><IconoBaseDatos />SQL Server · T-SQL</li>
            <li><IconoPunto />Reglas por severidad</li>
          </ul>
        </div>

        <div className="footer-columna">
          <h2>Privacidad</h2>
          <ul>
            <li><IconoCandado />Análisis 100% local</li>
            <li><IconoEscudoCheck />El código no sale de tu equipo</li>
          </ul>
        </div>
      </div>

      <div className="footer-base">
        <span>© {new Date().getFullYear()} CAJA ICA · Genesis IA</span>
        <span>Desarrollado por <strong>Angela Luciana Laura Vega</strong></span>
      </div>
    </footer>
  );
}
