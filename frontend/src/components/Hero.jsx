import fotoEncabezado from '../assets/profesional-laptop.webp';
import { pedirEjemplo } from '../hooks/useVerEjemplo';
import { IconoBajar, IconoPunto } from './Iconos';

const PUNTOS_POR_DEFECTO = [
  'Reglas del manual de nomenclatura de CAJA ICA',
  'Cada hallazgo indica cómo corregirlo',
  'Análisis local: el código no sale de tu equipo',
];

/** Lleva al formulario visible y pone el cursor en el primer editor. */
function irAlFormulario() {
  const panel = [...document.querySelectorAll('.main-wrapper .panel')].find((p) => p.offsetParent !== null);
  if (!panel) return;
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  panel.querySelector('textarea, input[type="file"]')?.focus({ preventScroll: true });
}

/** Lleva al formulario y carga ahí el ejemplo ya analizado. */
function verEjemplo() {
  irAlFormulario();
  pedirEjemplo();
}

/**
 * Encabezado de cada pestaña: a la izquierda el título, los puntos clave y la
 * acción principal; a la derecha el profesional con su laptop sobre la foto
 * financiera fundida en rojo.
 */
export function Hero({ titulo, descripcion, puntos = PUNTOS_POR_DEFECTO, accion = 'Comenzar revisión' }) {
  return (
    <section className="hero">
      <span className="hero-foto-fondo" aria-hidden="true" />
      <div className="hero-container">
        <div className="hero-texto">
          <h1>{titulo}</h1>
          <p className="hero-descripcion">{descripcion}</p>
          <ul className="hero-puntos">
            {puntos.map((punto) => (
              <li key={punto}><IconoPunto />{punto}</li>
            ))}
          </ul>
          <div className="hero-acciones">
            <button type="button" className="hero-accion" onClick={irAlFormulario}>
              {accion}
              <IconoBajar />
            </button>
            <button type="button" className="hero-accion-secundaria" onClick={verEjemplo}>
              Ver ejemplo
            </button>
          </div>
        </div>

        <figure className="hero-figura" aria-hidden="true">
          <img className="hero-foto" src={fotoEncabezado} alt="" />
        </figure>
      </div>
    </section>
  );
}
