import {
  IconoSeveridadAlta,
  IconoSeveridadBaja,
  IconoSeveridadCritica,
  IconoSeveridadMedia,
} from '../../components/Iconos';

const TARJETAS = [
  {
    severidad: 'critico', titulo: 'Críticos', plural: 'críticos', singular: 'crítico',
    descripcion: 'Impiden ejecutar el script o rompen el estándar.', icono: <IconoSeveridadCritica />,
  },
  {
    severidad: 'alto', titulo: 'Altos', plural: 'altos', singular: 'alto',
    descripcion: 'Incumplen las reglas del manual de nomenclatura.', icono: <IconoSeveridadAlta />,
  },
  {
    severidad: 'medio', titulo: 'Medios', plural: 'medios', singular: 'medio',
    descripcion: 'Conviene corregirlos o validarlos antes de pasar.', icono: <IconoSeveridadMedia />,
  },
  {
    severidad: 'bajo', titulo: 'Bajos', plural: 'bajos', singular: 'bajo',
    descripcion: 'Sugerencias para mejorar la calidad del código.', icono: <IconoSeveridadBaja />,
  },
];

/**
 * Resumen por severidad en su propia sección, debajo del encabezado: etiqueta,
 * título y cuatro tarjetas sobre un fondo de cubos isométricos. «Ver» lleva a
 * la lista de hallazgos (más abajo), que es donde se muestran en detalle.
 */
export function MetricasSeveridad({ conteo, subtitulos, onVerHallazgos }) {
  return (
    <section className="resumen-severidad" aria-label="Resumen por severidad">
      <div className="resumen-severidad-contenido">
        <p className="resumen-severidad-etiqueta">Resumen de la revisión</p>
        <h2 className="resumen-severidad-titulo">Hallazgos por severidad</h2>

        <div className="resumen-severidad-tarjetas">
          {TARJETAS.map(({ severidad, titulo, plural, singular, descripcion, icono }, indice) => {
            const valor = conteo[severidad];
            return (
              <article key={severidad} className={`resumen-tarjeta sev-${severidad}`}>
                <span className="resumen-tarjeta-insignia">
                  {icono}
                  <span>{titulo}</span>
                </span>
                <p className="resumen-tarjeta-cifra">
                  <strong className="metric-value">{valor}</strong>
                  <span>{valor === 1 ? `hallazgo ${singular}` : `hallazgos ${plural}`}</span>
                </p>
                <p className="resumen-tarjeta-descripcion">{descripcion}</p>
                <footer className="resumen-tarjeta-pie">
                  <span className="resumen-tarjeta-categoria">
                    <i aria-hidden="true" />
                    {subtitulos[indice]}
                  </span>
                  <button type="button" className="resumen-tarjeta-ver" onClick={onVerHallazgos}>
                    Ver <span aria-hidden="true">→</span>
                  </button>
                </footer>
              </article>
            );
          })}
        </div>

        <button type="button" className="resumen-severidad-boton" onClick={onVerHallazgos}>
          Ver hallazgos
        </button>
      </div>
    </section>
  );
}
