import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';

const LIMITE_FILAS = 10;

function formatearNumero(valor) {
  return valor === null || valor === undefined ? '—' : Math.round(valor).toLocaleString();
}

/** Operadores ordenados de mayor a menor costo (lecturas lógicas, luego filas). */
function ordenarPorCosto(operadores) {
  return [...operadores].sort(
    (a, b) => (b.lecturasLogicas ?? -1) - (a.lecturasLogicas ?? -1)
      || (b.filasLeidas ?? b.filasReales ?? -1) - (a.filasLeidas ?? a.filasReales ?? -1),
  );
}

/** Tabla con los operadores más costosos del plan de ejecución. */
export function TablaOperadores({ operadores = [] }) {
  if (!operadores.length) return null;
  const visibles = ordenarPorCosto(operadores).slice(0, LIMITE_FILAS);

  return (
    <section className="operators">
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Detalle del plan"
        titulo="Operadores más costosos"
        acciones={
          <span className="results-meta">
            {visibles.length} de {operadores.length} · ordenados por lecturas lógicas
          </span>
        }
      />

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Nodo</th>
              <th scope="col">Operación</th>
              <th scope="col">Objeto</th>
              <th scope="col" className="num">Filas est.</th>
              <th scope="col" className="num">Filas reales</th>
              <th scope="col" className="num">Lecturas lógicas</th>
              <th scope="col">Alertas</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((operador) => (
              <tr key={operador.nodoId}>
                <td className="mono">#{operador.nodoId}</td>
                <td>
                  <span className="op-physical">{operador.operacionFisica || '—'}</span>
                  {operador.operacionLogica && operador.operacionLogica !== operador.operacionFisica && (
                    <span className="op-logical">{operador.operacionLogica}</span>
                  )}
                </td>
                <td className="mono op-object" title={operador.objeto || undefined}>{operador.objeto || '—'}</td>
                <td className="num">{formatearNumero(operador.estimacionFilas)}</td>
                <td className="num">{formatearNumero(operador.filasReales)}</td>
                <td className="num strong">{formatearNumero(operador.lecturasLogicas)}</td>
                <td>
                  <span className="tag-list">
                    {operador.tieneSpill && <span className="tag sev-alto">Spill</span>}
                    {operador.tieneConversionImplicita && <span className="tag sev-critico">Conversión</span>}
                    {!operador.tieneSpill && !operador.tieneConversionImplicita && <span className="tag-none">—</span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
