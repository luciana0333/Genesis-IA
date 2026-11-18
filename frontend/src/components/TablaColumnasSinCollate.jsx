/** Desde cuántas tablas «COLLATE no especificado en tabla temporal» se muestra como tabla (igual en el backend). */
export const TABLAS_PARA_VER_EN_TABLA = 3;

/** Observaciones que desde 3 tablas se muestran como tabla, con el título de su segunda columna. */
const TITULO_DE_COLUMNAS = {
  TEMPORAL_TEXTO_SIN_COLLATE: 'Columnas sin COLLATE', // usuaria, 8 nov.
  ISNULL_VALIDAR_NULOS: 'Columnas', // usuaria, 18 nov.
};

/** ¿Esta observación se muestra como tabla (Tabla | Columnas)? Desde 3 tablas, en las reglas de arriba. */
export const collateEnTabla = (hallazgo) => Boolean(TITULO_DE_COLUMNAS[hallazgo.regla])
  && (hallazgo.grupos?.length ?? 0) >= TABLAS_PARA_VER_EN_TABLA;

export const tituloDeColumnas = (regla) => TITULO_DE_COLUMNAS[regla] ?? 'Columnas';

/**
 * «COLLATE no especificado en tabla temporal» como tabla: Tabla | Columnas sin COLLATE.
 * Mismo diseño que «Misma columna con distinto tipo»; la fila que se recorre en el código se resalta.
 */
export function TablaColumnasSinCollate({ grupos, filaActiva = null, tituloColumnas = 'Columnas sin COLLATE' }) {
  return (
    <table className="tabla-tipos tabla-collate">
      <thead>
        <tr>
          <th scope="col">Tabla</th>
          <th scope="col">{tituloColumnas}</th>
        </tr>
      </thead>
      <tbody>
        {grupos.map((grupo, indice) => (
          <tr
            key={grupo.nombre}
            className={`tabla-tipos-fila${indice % 2 ? ' alterna' : ''}${indice === filaActiva ? ' activa' : ''}`}
          >
            <td><code className="tabla-tipos-columna">{grupo.nombre}</code></td>
            {/* «columnas» viene cuando una columna se repite en varias líneas (ISNULL): se muestra una sola vez. */}
            <td className="tabla-collate-columnas">{grupo.columnas ?? (grupo.etiquetas ?? []).join(', ')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
