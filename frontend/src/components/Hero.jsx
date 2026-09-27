import fotoAnalista from '../assets/analista-recorte.webp';
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

/**
 * Encabezado de cada pestaña: a la izquierda el título, los puntos clave y la
 * acción principal; a la derecha el analista recortado.
 */
export function Hero({ titulo, complemento, descripcion, puntos = PUNTOS_POR_DEFECTO, accion = 'Comenzar revisión' }) {
  return (
    <section className="hero">
      <span className="hero-media" aria-hidden="true" />
      <div className="hero-container">
        <div className="hero-texto">
          <p className="hero-eyebrow">{complemento ?? 'Auditoría inteligente'}</p>
          <h1>{titulo}</h1>
          <p className="hero-descripcion">{descripcion}</p>
          <ul className="hero-puntos">
            {puntos.map((punto) => (
              <li key={punto}><IconoPunto />{punto}</li>
            ))}
          </ul>
          <button type="button" className="hero-accion" onClick={irAlFormulario}>
            {accion}
            <IconoBajar />
          </button>
        </div>

        <figure className="hero-figura" aria-hidden="true">
          <img className="hero-foto" src={fotoAnalista} alt="" />
        </figure>
      </div>
    </section>
  );
}
