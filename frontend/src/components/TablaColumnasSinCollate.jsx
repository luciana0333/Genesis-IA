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

/** ¿Esta observación se muestra como tabla (Tabla | Columnas)? Desde 3 tablas, en las reglas de arriba; o cuando el
 * backend ya decidió la tabla (más de 3 casos, con el título de su segunda columna; usuaria, 21 nov.). */
export const collateEnTabla = (hallazgo) => Boolean(hallazgo.grupos?.[0]?.tituloDetalle)
  || (Boolean(TITULO_DE_COLUMNAS[hallazgo.regla])
    && (hallazgo.grupos?.length ?? 0) >= (GRUPOS_PARA_TABLA[hallazgo.regla] ?? TABLAS_PARA_VER_EN_TABLA));

export const tituloDeColumnas = (regla) => TITULO_DE_COLUMNAS[regla] ?? 'Columnas';

const DESCRIPCION_DEL_OBJETO = /^\(descripción del (procedimiento|función|funcion)\)$/i;

/**
 * «Validar documentación existente» con varios procedimientos (usuaria, 21 nov.): Procedimiento | Parámetros, una fila
 * por procedimiento y sin la columna Situación. Cada parámetro en su cajita; el que no está en el diccionario lleva
 * la etiqueta «Falta» (antes era la fila «No se incluyen en el diccionario»).
 */
function TablaPorProcedimiento({ grupos, filaActiva }) {
  const filas = [];
  grupos.forEach((grupo, indice) => {
    let fila = filas.find((otra) => otra.nombre === grupo.nombre);
    if (!fila) {
      fila = { nombre: grupo.nombre, indices: [], faltan: [], agregan: [] };
      filas.push(fila);
    }
    fila.indices.push(indice);
    const falta = grupo.seccion === 'objeto';
    (falta ? fila.faltan : fila.agregan).push(...(grupo.etiquetas ?? []));
  });
  const cajita = (etiqueta, falta) => {
    const objeto = DESCRIPCION_DEL_OBJETO.exec(etiqueta);
    return (
      <span key={`${falta ? 'f' : 'a'}-${etiqueta}`} className={`cajita-parametro${falta ? ' falta' : ''}`}
        title={falta ? 'No se incluye en el diccionario' : 'Se agrega en el diccionario'}>
        {objeto ? <span className="cajita-parametro-objeto">Descripción del {objeto[1]}</span> : <code>{etiqueta}</code>}
        {falta && <span className="cajita-parametro-falta">Falta</span>}
      </span>
    );
  };
  return (
    <table className="tabla-tipos tabla-collate tabla-por-procedimiento">
      <thead>
        <tr>
          <th scope="col">Procedimiento</th>
          <th scope="col">Parámetros</th>
        </tr>
      </thead>
      <tbody>
        {filas.map((fila, indice) => (
          <tr
            key={fila.nombre}
            className={`tabla-tipos-fila${indice % 2 ? ' alterna' : ''}${fila.indices.includes(filaActiva) ? ' activa' : ''}`}
          >
            <td className="tabla-nombre">
              {/* Si no entra, baja de línea solo después de «.» o «_» (no a mitad de palabra). */}
              <code className="tabla-tipos-columna">
                {fila.nombre.split(/(?<=[._])/).map((parte, i) => <span key={i}>{parte}<wbr /></span>)}
              </code>
            </td>
            <td>
              <div className="cajitas-parametros">
                {fila.faltan.map((etiqueta) => cajita(etiqueta, true))}
                {fila.agregan.map((etiqueta) => cajita(etiqueta, false))}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * «COLLATE no especificado en tabla temporal» como tabla: Tabla | Columnas sin COLLATE.
 * Mismo diseño que «Misma columna con distinto tipo»; la fila que se recorre en el código se resalta.
 * «Validar documentación existente» (ALTER, usuaria 20 nov.): con un procedimiento, Situación | Elementos; con
 * varios, Procedimiento | Situación | Elementos (el procedimiento se escribe una vez para sus filas).
 */
export function TablaColumnasSinCollate({ grupos, filaActiva = null, tituloColumnas = 'Columnas sin COLLATE' }) {
  // La primera columna dice qué es cada fila («Tabla», «Procedimiento», «Situación»), según los grupos.
  const tituloFilas = grupos[0]?.tipo ?? 'Tabla';
  const porSituacion = tituloFilas === 'Situación';
  const conSituacion = grupos.some((grupo) => grupo.situacion);
  const tituloElementos = grupos[0]?.tituloDetalle
    ?? (porSituacion || conSituacion ? 'Elementos' : tituloColumnas);
  // Filas seguidas del mismo procedimiento: su nombre ocupa una sola celda.
  const filasDe = (indice) => {
    let filas = 1;
    while (grupos[indice + filas]?.nombre === grupos[indice].nombre) filas += 1;
    return filas;
  };
  if (conSituacion) return <TablaPorProcedimiento grupos={grupos} filaActiva={filaActiva} />;
  return (
    <table className={`tabla-tipos tabla-collate${conSituacion ? ' tabla-situaciones' : ''}`}>
      <thead>
        <tr>
          <th scope="col">{tituloFilas}</th>
          {conSituacion && <th scope="col">Situación</th>}
          <th scope="col">{tituloElementos}</th>
        </tr>
      </thead>
      <tbody>
        {grupos.map((grupo, indice) => {
          const primeraDelNombre = indice === 0 || grupos[indice - 1].nombre !== grupo.nombre;
          return (
            <tr
              key={`${grupo.nombre}-${grupo.situacion ?? indice}`}
              className={`tabla-tipos-fila${indice % 2 ? ' alterna' : ''}${indice === filaActiva ? ' activa' : ''}`}
            >
              {porSituacion ? (
                <td className="tabla-situacion">{grupo.nombre}</td>
              ) : (
                (!conSituacion || primeraDelNombre) && (
                  <td rowSpan={conSituacion ? filasDe(indice) : undefined} className="tabla-nombre">
                    <code className="tabla-tipos-columna">{grupo.nombre}</code>
                  </td>
                )
              )}
              {conSituacion && <td className="tabla-situacion">{grupo.situacion}</td>}
              {/* «columnas» viene cuando una columna se repite en varias líneas (ISNULL): se muestra una sola vez. */}
              <td className={grupo.detalleEnTexto ? 'tabla-detalle-texto' : 'tabla-collate-columnas'}>
                {grupo.columnas ?? (grupo.etiquetas ?? []).join(', ')}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
