/**
 * Botón del sistema de diseño.
 * variante: primario | secundario | fantasma. `cargando` muestra un spinner y
 * deshabilita el botón mientras dura la operación.
 */
export function Boton({ variante = 'primario', icono, cargando = false, children, className = '', ...props }) {
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
    </button>
  );
}
