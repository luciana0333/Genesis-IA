import { useId } from 'react';
import { IconoCandado, IconoCapas, IconoCargando, IconoEnlace, IconoErrorCirculo, IconoFlecha, IconoPunto } from '../../components/Iconos';

/**
 * Paso 1: portada minimalista (opción A aprobada el 22 nov.) con el campo del link.
 * Fondo: la foto del centro de datos bajo un velo de color, para que se insinúe sin competir con el texto.
 */
export function PortadaBitbucket({ enlace, onCambiarEnlace, lectura, onLeer, onVerEjemplo }) {
  const id = useId();
  const leyendo = lectura.estado === 'leyendo';
  const alEnviar = (evento) => {
    evento.preventDefault();
    if (!leyendo) onLeer();
  };

  return (
    <section className="bb-portada" aria-labelledby={`${id}-titulo`}>
      <span className="bb-portada-fondo" aria-hidden="true" />
      <div className="bb-portada-contenido">
        <span className="bb-portada-hilo" aria-hidden="true" />
        <p className="bb-etiqueta bb-etiqueta-centrada">Revisión desde Bitbucket</p>
        <h1 id={`${id}-titulo`} className="bb-portada-titulo">
          Un link. <strong>Todos los objetos revisados.</strong>
        </h1>
        <p className="bb-portada-texto">
          Pega el pull request, la rama o el commit. Genesis identifica cada objeto y lo revisa con las reglas de su
          módulo.
        </p>

        <form className="bb-buscador" onSubmit={alEnviar} noValidate>
          <label htmlFor={`${id}-enlace`} className="sr-only">Link de Bitbucket</label>
          <IconoEnlace className="bb-buscador-icono" />
          <input
            id={`${id}-enlace`}
            className="bb-buscador-campo"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck="false"
            placeholder="https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129"
            value={enlace}
            onChange={(evento) => onCambiarEnlace(evento.target.value)}
            aria-invalid={lectura.estado === 'error'}
            aria-describedby={lectura.estado === 'error' ? `${id}-error` : undefined}
          />
          <button type="submit" className="bb-boton" disabled={leyendo}>
            {leyendo ? <><IconoCargando className="bb-girando" />Leyendo…</> : <>Leer archivos<IconoFlecha /></>}
          </button>
        </form>

        {lectura.estado === 'error' && (
          <p id={`${id}-error`} className="bb-portada-error" role="alert">
            <IconoErrorCirculo />
            <span>{lectura.mensaje}</span>
          </p>
        )}

        <ul className="bb-portada-notas">
          <li><IconoCandado />Solo lectura</li>
          <li><IconoCapas />Pull request, rama o commit</li>
          <li><IconoPunto />Las reglas de siempre</li>
        </ul>
        <button type="button" className="bb-enlace-ejemplo" onClick={onVerEjemplo}>Ver ejemplo</button>
      </div>
    </section>
  );
}
