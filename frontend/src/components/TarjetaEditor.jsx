/**
 * Tarjeta de una entrada del formulario: cabecera con número de paso (opcional),
 * título, ayuda corta, acciones y estado ("Requerido"); debajo, el control que
 * se pase como hijo (editor, zona de archivo, lista...).
 */
export function TarjetaEditor({
  className = '',
  numero,
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
        {numero && <span className="field-card-numero" aria-hidden="true">{numero}</span>}
        <div className="field-card-titles">
          <Etiqueta className="field-label" htmlFor={htmlFor}>{etiqueta}</Etiqueta>
          {ayuda && <p className="field-hint">{ayuda}</p>}
        </div>
        <div className="field-card-side">
          {acciones}
          {estado && <span className={requerido ? 'field-status' : 'field-status optional'}>{estado}</span>}
        </div>
      </div>
      <div className="field-card-body">{children}</div>
    </div>
  );
}
