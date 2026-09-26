/**
 * Contenedor con encabezado para una entrada del formulario (editor SQL,
 * carga de archivo, acciones). `requerido` controla la etiqueta de estado.
 */
export function TarjetaEditor({
  className = '',
  kicker,
  etiqueta,
  htmlFor,
  estado,
  requerido = true,
  ayuda,
  children,
}) {
  return (
    <div className={`editor-card ${className}`.trim()}>
      <div className="editor-card-heading">
        <div>
          <span className="editor-kicker">{kicker}</span>
          <label htmlFor={htmlFor}>{etiqueta}</label>
        </div>
        <span className={requerido ? 'editor-status' : 'editor-status optional'}>{estado}</span>
      </div>
      {ayuda && <p className="editor-hint">{ayuda}</p>}
      {children}
    </div>
  );
}
