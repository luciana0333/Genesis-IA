/**
 * Botón del sistema de diseño.
 * variante: primario | secundario | fantasma. `cargando` muestra un spinner y
 * deshabilita el botón mientras dura la operación. `atajo` muestra las teclas
 * del atajo dentro del botón (ej. ['Ctrl', 'Enter']).
 */
export function Boton({ variante = 'primario', icono, cargando = false, atajo, children, className = '', ...props }) {
  return (
    <button
      type="button"
      {...props}
      className={`btn btn-${variante} ${className}`.trim()}
      disabled={cargando || props.disabled}
      aria-busy={cargando || undefined}
    >
      {cargando ? <span className="spinner" aria-hidden="true" /> : icono}
      <span>{children}</span>
      {atajo && (
        <span className="btn-atajo" aria-hidden="true">
          {atajo.map((tecla) => <kbd key={tecla}>{tecla}</kbd>)}
        </span>
      )}
    </button>
  );
}
