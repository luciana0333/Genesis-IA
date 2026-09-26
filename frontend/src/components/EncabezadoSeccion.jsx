/**
 * Encabezado de sección: etiqueta roja en mayúsculas, título y línea de
 * acento. `acciones` se alinea a la derecha (botones, contadores).
 */
export function EncabezadoSeccion({ etiqueta, titulo, descripcion, acciones, nivel = 2 }) {
  const Titulo = `h${nivel}`;
  return (
    <header className="section-heading">
      <div className="section-heading-text">
        {etiqueta && <span className="section-eyebrow">{etiqueta}</span>}
        <Titulo className="section-title">{titulo}</Titulo>
        <span className="section-rule" aria-hidden="true" />
        {descripcion && <p className="section-description">{descripcion}</p>}
      </div>
      {acciones && <div className="section-heading-actions">{acciones}</div>}
    </header>
  );
}
