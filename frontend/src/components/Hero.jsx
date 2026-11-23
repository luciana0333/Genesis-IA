import fotoEncabezado from '../assets/profesional-laptop.webp';
import { pedirEjemplo } from '../hooks/useVerEjemplo';
import { IconoBuscar, IconoCodigo, IconoCorregir, IconoFlecha, IconoSubir } from './Iconos';

const ICONOS = { codigo: IconoCodigo, subir: IconoSubir, buscar: IconoBuscar, corregir: IconoCorregir };

/** Pasos de las pestañas de revisión: solo el primero cambia según lo que se pega en cada una. */
function pasosDeRevision(pega) {
  return [
    { titulo: 'Pega', texto: pega, icono: 'codigo' },
    { titulo: 'Revisa', texto: 'Reglas de la Caja y del Validador SQL Server.', icono: 'buscar' },
    { titulo: 'Corrige', texto: 'Cada hallazgo dice qué hacer.', icono: 'corregir' },
  ];
}

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
 * Encabezado de cada pestaña (boceto 2 de la usuaria, 22 nov., sin la etiqueta enmarcada): panel rojo con corte
 * diagonal, título y descripción de la pestaña (sin cambios), acciones y, montadas sobre el borde inferior, tres tarjetas con
 * los pasos (pega o carga, revisa, corrige). A la derecha, el profesional con su laptop.
 */
export function Hero({
  titulo,
  descripcion,
  pega = 'El código del objeto.',
  pasos = pasosDeRevision(pega),
  accion = 'Comenzar revisión',
}) {
  return (
    <>
      <section className="hero hero--pasos">
        <span className="hero-foto-fondo" aria-hidden="true" />
        <span className="hero-panel" aria-hidden="true" />
        <div className="hero-container">
          <div className="hero-texto">
            <h1>{titulo}</h1>
            <p className="hero-descripcion">{descripcion}</p>
            <div className="hero-acciones">
              <button type="button" className="hero-accion" onClick={irAlFormulario}>
                {accion}
                <IconoFlecha />
              </button>
              <button type="button" className="hero-accion-enlace" onClick={verEjemplo}>
                <span>Ver ejemplo</span>
                <IconoFlecha />
              </button>
            </div>
          </div>

          <figure className="hero-figura" aria-hidden="true">
            <img className="hero-foto" src={fotoEncabezado} alt="" />
          </figure>
        </div>
      </section>

      <div className="hero-pasos-banda">
        <ol className="hero-pasos" aria-label="Cómo funciona">
          {pasos.map(({ titulo: tituloPaso, texto, icono }, indice) => {
            const Icono = ICONOS[icono] ?? IconoCodigo;
            return (
              <li key={tituloPaso} className="hero-paso">
                <span className="hero-paso-numero" aria-hidden="true">{String(indice + 1).padStart(2, '0')}</span>
                <Icono className="hero-paso-icono" />
                <strong className="hero-paso-titulo">{tituloPaso}</strong>
                <span className="hero-paso-texto">{texto}</span>
              </li>
            );
          })}
        </ol>
      </div>
    </>
  );
}
