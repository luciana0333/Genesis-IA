/** Desde cuántas tablas «COLLATE no especificado en tabla temporal» se muestra como tabla (igual en el backend). */
export const TABLAS_PARA_VER_EN_TABLA = 3;

/** Observaciones que desde 3 tablas se muestran como tabla, con el título de su segunda columna. */
const TITULO_DE_COLUMNAS = {
  TEMPORAL_TEXTO_SIN_COLLATE: 'Columnas sin COLLATE', // usuaria, 8 nov.
  ISNULL_VALIDAR_NULOS: 'Columnas', // usuaria, 18 nov.
  VALIDAR_DOCUMENTACION_ALTER: 'Parámetros sin descripción', // diccionario con varios procedimientos (usuaria, 20 nov.)
};

/** Reglas que pasan a tabla con menos grupos (por defecto, desde 3). */
const GRUPOS_PARA_TABLA = { VALIDAR_DOCUMENTACION_ALTER: 2 };

/** ¿Esta observación se muestra como tabla (Tabla | Columnas)? Desde 3 tablas, en las reglas de arriba. */
export const collateEnTabla = (hallazgo) => Boolean(TITULO_DE_COLUMNAS[hallazgo.regla])
  && (hallazgo.grupos?.length ?? 0) >= (GRUPOS_PARA_TABLA[hallazgo.regla] ?? TABLAS_PARA_VER_EN_TABLA);

export const tituloDeColumnas = (regla) => TITULO_DE_COLUMNAS[regla] ?? 'Columnas';

/**
 * «COLLATE no especificado en tabla temporal» como tabla: Tabla | Columnas sin COLLATE.
 * Mismo diseño que «Misma columna con distinto tipo»; la fila que se recorre en el código se resalta.
 */
export function TablaColumnasSinCollate({ grupos, filaActiva = null, tituloColumnas = 'Columnas sin COLLATE' }) {
  // La primera columna dice qué es cada fila («Tabla», «Procedimiento»), según los grupos.
  const tituloFilas = grupos[0]?.tipo ?? 'Tabla';
  return (
    <table className="tabla-tipos tabla-collate">
      <thead>
        <tr>
          <th scope="col">{tituloFilas}</th>
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
