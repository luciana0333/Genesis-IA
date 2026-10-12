/*
 * Pestañas «Parameters» y «Missing Indexes» de Plan Explorer: lo que el XML
 * trae en ParameterList y en MissingIndexes, tal cual, sin agregar nada.
 */

/** Parámetros de la consulta con su valor al compilar y al ejecutar (como la pestaña Parameters). */
export function ParametrosPlan({ parametros = [] }) {
  if (!parametros.length) {
    return <p className="plan-vacio">El XML de esta sentencia no trae parámetros (ParameterList).</p>;
  }
  return (
    <div className="table-scroll">
      <table className="plan-sentencias plan-tabla">
        <thead>
          <tr>
            <th scope="col">Parameter</th>
            <th scope="col">Data Type</th>
            <th scope="col">Compiled Value</th>
            <th scope="col">Runtime Value</th>
          </tr>
        </thead>
        <tbody>
          {parametros.map((parametro) => {
            // Valores distintos al compilar y al ejecutar: posible «parameter sniffing».
            const distintos = parametro.valorCompilado != null && parametro.valorEjecucion != null
              && parametro.valorCompilado !== parametro.valorEjecucion;
            return (
              <tr key={parametro.nombre}>
                <td>{parametro.nombre}</td>
                <td>{parametro.tipo}</td>
                <td className={distintos ? 'desviada' : undefined}>{parametro.valorCompilado ?? ''}</td>
                <td className={distintos ? 'desviada' : undefined}>{parametro.valorEjecucion ?? ''}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Índices faltantes que sugiere SQL Server, con su CREATE INDEX como en SSMS. */
export function IndicesFaltantes({ indices = [] }) {
  if (!indices.length) {
    return <p className="plan-vacio">El XML de esta sentencia no trae índices faltantes (MissingIndexes).</p>;
  }
  return (
    <div className="plan-indices">
      {indices.map((indice) => (
        <article key={indice.sentencia} className="plan-indice">
          <table className="plan-sentencias plan-tabla">
            <tbody>
              <tr><th scope="row">Impact</th><td>{indice.impacto != null ? `${indice.impacto.toFixed(2)}%` : ''}</td></tr>
              <tr><th scope="row">Table</th><td>{[indice.base, indice.tabla].filter(Boolean).join('.')}</td></tr>
              <tr><th scope="row">Equality Columns</th><td>{indice.igualdad.join(', ')}</td></tr>
              <tr><th scope="row">Inequality Columns</th><td>{indice.desigualdad.join(', ')}</td></tr>
              <tr><th scope="row">Include Columns</th><td>{indice.incluidas.join(', ')}</td></tr>
            </tbody>
          </table>
          <pre className="plan-indice-sentencia">
            {`/*\nMissing Index Details\nThe Query Processor estimates that implementing the following index could improve the query cost by ${indice.impacto != null ? indice.impacto.toFixed(4) : '?'}%.\n*/\n${indice.sentencia}`}
          </pre>
        </article>
      ))}
    </div>
  );
}
