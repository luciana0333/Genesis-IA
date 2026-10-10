const ICONO_LUPA = <><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.5-4.5" /></>;
const ICONO_CHECK = <path d="M6 12.5l4 4 8-9" />;

/**
 * Estado del panel de resultados con ilustración: documento con un sello y,
 * al lado, un título y una lista.
 * - variante "inicio": lupa roja y pasos numerados para empezar.
 * - variante "exito": sello con check y lista de verificaciones superadas.
 */
export function EstadoInicial({ titulo, descripcion, pasos, variante = 'inicio' }) {
  const esExito = variante === 'exito';
  return (
    <div className={`estado-inicial estado-${variante}`} role="status">
      <div className="estado-inicial-ilustracion" aria-hidden="true">
        <span className="estado-inicial-doc">
          <i /><i className="marcada" /><i className="corta" /><i /><i className="marcada" /><i className="corta" />
        </span>
        <span className="estado-inicial-lupa">
          <svg viewBox="0 0 24 24">{esExito ? ICONO_CHECK : ICONO_LUPA}</svg>
        </span>
      </div>
      <div className="estado-inicial-texto">
        <p className="estado-inicial-titulo">{titulo}</p>
        {descripcion && <p className="estado-inicial-descripcion">{descripcion}</p>}
        <ol className="estado-inicial-pasos">
          {pasos.map((paso, indice) => (
            <li key={indice}>
              <span>{esExito ? <svg viewBox="0 0 24 24">{ICONO_CHECK}</svg> : indice + 1}</span>
              {paso}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
