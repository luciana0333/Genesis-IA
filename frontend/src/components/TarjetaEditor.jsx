/**
 * Bloque del formulario con encabezado (kicker, etiqueta, estado y acciones
 * opcionales), texto de ayuda y el control que se pase como hijo.
 */
export function TarjetaEditor({
  className = '',
  kicker,
  etiqueta,
  htmlFor,
  estado,
  requerido = true,
  ayuda,
  acciones,
  children,
}) {
  const Etiqueta = htmlFor ? 'label' : 'span';
  return (
    <div className={`field-card ${className}`.trim()}>
      <div className="field-card-heading">
        <div className="field-card-titles">
          <span className="field-kicker">{kicker}</span>
          <Etiqueta className="field-label" htmlFor={htmlFor}>{etiqueta}</Etiqueta>
        </div>
        <div className="field-card-side">
          {acciones}
          {estado && <span className={requerido ? 'field-status' : 'field-status optional'}>{estado}</span>}
        </div>
      </div>
      {ayuda && <p className="field-hint">{ayuda}</p>}
      {children}
    </div>
  );
}
