/**
 * Estado inicial del panel de resultados: ilustración de un documento con lupa,
 * un título y los pasos numerados para empezar.
 */
export function EstadoInicial({ titulo, descripcion, pasos }) {
  return (
    <div className="estado-inicial" role="status">
      <div className="estado-inicial-ilustracion" aria-hidden="true">
        <span className="estado-inicial-doc">
          <i /><i className="marcada" /><i className="corta" /><i /><i className="marcada" /><i className="corta" />
        </span>
        <span className="estado-inicial-lupa">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.5-4.5" /></svg>
        </span>
      </div>
      <div className="estado-inicial-texto">
        <p className="estado-inicial-titulo">{titulo}</p>
        {descripcion && <p className="estado-inicial-descripcion">{descripcion}</p>}
        <ol className="estado-inicial-pasos">
          {pasos.map((paso, indice) => (
            <li key={indice}><span>{indice + 1}</span>{paso}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
