/** Desde cuántas tablas «COLLATE no especificado en tabla temporal» se muestra como tabla (igual en el backend). */
export const TABLAS_PARA_VER_EN_TABLA = 3;

/** ¿Esta observación se muestra como tabla? Solo COLLATE de temporales y desde 3 tablas (usuaria, 8 nov.). */
export const collateEnTabla = (hallazgo) => hallazgo.regla === 'TEMPORAL_TEXTO_SIN_COLLATE'
  && (hallazgo.grupos?.length ?? 0) >= TABLAS_PARA_VER_EN_TABLA;

/**
 * «COLLATE no especificado en tabla temporal» como tabla: Tabla | Columnas sin COLLATE.
 * Mismo diseño que «Misma columna con distinto tipo»; la fila que se recorre en el código se resalta.
 */
export function TablaColumnasSinCollate({ grupos, filaActiva = null }) {
  return (
    <table className="tabla-tipos tabla-collate">
      <thead>
        <tr>
          <th scope="col">Tabla</th>
          <th scope="col">Columnas sin COLLATE</th>
        </tr>
      </thead>
      <tbody>
        {grupos.map((grupo, indice) => (
          <tr
            key={grupo.nombre}
            className={`tabla-tipos-fila${indice % 2 ? ' alterna' : ''}${indice === filaActiva ? ' activa' : ''}`}
          >
            <td><code className="tabla-tipos-columna">{grupo.nombre}</code></td>
            <td className="tabla-collate-columnas">{(grupo.etiquetas ?? []).join(', ')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
