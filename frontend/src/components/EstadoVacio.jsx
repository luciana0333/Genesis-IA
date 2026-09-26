/**
 * Estado sin contenido (inicial, error o éxito) con ícono, título y texto.
 * tono: neutro | error | exito
 */
export function EstadoVacio({ icono, titulo, children, tono = 'neutro' }) {
  return (
    <div className={`empty-state tono-${tono}`} role="status">
      {icono && <span className="empty-icon">{icono}</span>}
      {titulo && <p className="empty-title">{titulo}</p>}
      {children && <p className="empty-text">{children}</p>}
    </div>
  );
}
