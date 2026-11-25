import { useState } from 'react';

/** Desde cuántas tablas «COLLATE no especificado en tabla temporal» se muestra como tabla (igual en el backend). */
export const TABLAS_PARA_VER_EN_TABLA = 3;

/** Observaciones que desde 3 tablas se muestran como tabla, con el título de su segunda columna. */
const TITULO_DE_COLUMNAS = {
  TEMPORAL_TEXTO_SIN_COLLATE: 'Columnas sin COLLATE', // usuaria, 8 nov.
  ISNULL_VALIDAR_NULOS: 'Columnas', // usuaria, 18 nov.
  VALIDAR_DOCUMENTACION_ALTER: 'Parámetros sin descripción', // diccionario con varios procedimientos (usuaria, 20 nov.)
  DOCUMENTACION_EXISTENTE_EN_ALTER: 'Parámetros', // solo descripciones agregadas, varios procedimientos (23 nov.)
};

/** Reglas que pasan a tabla con menos grupos (por defecto, desde 3). */
const GRUPOS_PARA_TABLA = { VALIDAR_DOCUMENTACION_ALTER: 2, DOCUMENTACION_EXISTENTE_EN_ALTER: 2 };

/** ¿Esta observación se muestra como tabla (Tabla | Columnas)? Desde 3 tablas, en las reglas de arriba; o cuando el
 * backend ya decidió la tabla (más de 3 casos, con el título de su segunda columna; usuaria, 21 nov.). */
export const collateEnTabla = (hallazgo) => Boolean(hallazgo.grupos?.[0]?.tituloDetalle)
  || (Boolean(TITULO_DE_COLUMNAS[hallazgo.regla])
    && (hallazgo.grupos?.length ?? 0) >= (GRUPOS_PARA_TABLA[hallazgo.regla] ?? TABLAS_PARA_VER_EN_TABLA));

export const tituloDeColumnas = (regla) => TITULO_DE_COLUMNAS[regla] ?? 'Columnas';

const DESCRIPCION_DEL_OBJETO = /^\(descripción del (procedimiento|función|funcion)\)$/i;

/** Cuántos parámetros se ven antes de «+N más» (idea A3, usuaria, 24 nov.: «que solo muestre 3 parámetros»). La cajita
 * «Procedimiento» (descripción del objeto) no cuenta: se ve siempre. */
const PARAMETROS_VISIBLES = 3;

function cajita(etiqueta, falta, neutra = false) {
  const objeto = DESCRIPCION_DEL_OBJETO.exec(etiqueta);
  return (
    <span key={`${falta ? 'f' : 'a'}-${etiqueta}`} className={`cajita-parametro${falta ? ' falta' : ''}`}
      title={neutra ? etiqueta
        : `${objeto ? `Descripción del ${objeto[1]}: ` : ''}${falta ? 'no se incluye en el diccionario' : 'se agrega en el diccionario'}`}>
      {/* Corto para que la fila entre en un renglón (A3, 24 nov.); el texto completo va en el título. */}
      {objeto
        ? <span className="cajita-parametro-objeto">{objeto[1] === 'procedimiento' ? 'Procedimiento' : 'Función'}</span>
        : <code>{etiqueta}</code>}
      {falta && <span className="cajita-parametro-falta">Falta</span>}
    </span>
  );
}

/**
 * Los elementos de un procedimiento: la cajita «Procedimiento» y los que faltan primero (nunca quedan escondidos detrás
 * de «+N más»), luego los parámetros que se agregan. Se ven 3 parámetros y «+N más» despliega el resto («Ver menos» los
 * vuelve a juntar); si solo quedaría uno escondido, se ven todos.
 */
function CajitasDeLaFila({ faltan, agregan, neutras = false }) {
  const [abierta, setAbierta] = useState(false);
  const todas = [...faltan.map((etiqueta) => [etiqueta, true]), ...agregan.map((etiqueta) => [etiqueta, false])];
  const esObjeto = ([etiqueta]) => DESCRIPCION_DEL_OBJETO.test(etiqueta);
  const objetos = todas.filter(esObjeto);
  const parametros = todas.filter((cajita) => !esObjeto(cajita));
  const cantidadFaltan = parametros.filter(([, falta]) => falta).length;
  const resumir = parametros.length > PARAMETROS_VISIBLES + 1;
  const visibles = [
    ...objetos,
    ...(resumir && !abierta ? parametros.slice(0, Math.max(PARAMETROS_VISIBLES, cantidadFaltan)) : parametros),
  ];
  const ocultas = todas.length - visibles.length;
  return (
    <div className="cajitas-parametros">
      {visibles.map(([etiqueta, falta]) => cajita(etiqueta, falta, neutras))}
      {resumir && (
        <button type="button" className="cajitas-mas" aria-expanded={abierta} onClick={() => setAbierta(!abierta)}>
          {abierta ? 'Ver menos' : `+${ocultas} más`}
        </button>
      )}
    </div>
  );
}

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
              {/* El nombre completo, en una línea (usuaria, 24 nov.). */}
              <span className="tabla-procedimiento-nombre">{fila.nombre}</span>
            </td>
            <td>
              <CajitasDeLaFila faltan={fila.faltan} agregan={fila.agregan} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Tablas con más de 3 casos (usuaria, 25 nov.): Tabla | Columnas con el mismo diseño A3 de Diccionarios (blanco con
 * sombra suave, el nombre completo en una línea, cada columna en su cajita y «+N más»).
 */
function TablaConCajitas({ grupos, filaActiva, tituloFilas, tituloElementos }) {
  // Si todas las tablas son del mismo esquema, se dice una vez en el encabezado («Tabla · Conciliacion») y cada fila
  // lleva solo el nombre: así las columnas tienen espacio y las cajitas no se apilan.
  const esquemas = new Set(grupos.map((grupo) => (grupo.nombre.includes('.') ? grupo.nombre.split('.')[0] : null)));
  const esquema = esquemas.size === 1 ? [...esquemas][0] : null;
  const nombreDe = (nombre) => (esquema ? nombre.slice(esquema.length + 1) : nombre);
  return (
    <table className="tabla-tipos tabla-collate tabla-por-procedimiento">
      <thead>
        <tr>
          <th scope="col">{esquema ? `${tituloFilas} · ${esquema}` : tituloFilas}</th>
          <th scope="col">{tituloElementos}</th>
        </tr>
      </thead>
      <tbody>
        {grupos.map((grupo, indice) => (
          <tr key={grupo.nombre} className={`tabla-tipos-fila${indice % 2 ? ' alterna' : ''}${indice === filaActiva ? ' activa' : ''}`}>
            <td className="tabla-nombre">
              <span className="tabla-procedimiento-nombre" title={grupo.nombre}>{nombreDe(grupo.nombre)}</span>
            </td>
            <td><CajitasDeLaFila faltan={[]} agregan={grupo.etiquetas ?? []} neutras /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Índices por renombrar (usuaria, 25 nov.): los nombres son largos y en dos columnas el sugerido quedaba cortado; cada
 * fila lleva el nombre actual y, debajo, el sugerido.
 */
function TablaRenombrar({ grupos, filaActiva, encabezado }) {
  return (
    <table className="tabla-tipos tabla-collate tabla-por-procedimiento tabla-renombrar">
      <thead>
        <tr><th scope="col">{encabezado}</th></tr>
      </thead>
      <tbody>
        {grupos.map((grupo, indice) => (
          <tr key={`${grupo.nombre}-${indice}`} className={`tabla-tipos-fila${indice === filaActiva ? ' activa' : ''}`}>
            <td>
              <code className="renombrar-actual">{grupo.nombre}</code>
              {/* «7 columnas: a, b, c» (INCLUDE): cada columna en su cajita, que bajan de línea sin cortarse. */}
              {/^\d+ columnas: /.test(grupo.columnas ?? '') ? (
                <span className="renombrar-sugerido renombrar-columnas">
                  <span aria-hidden="true">→</span> {grupo.columnas.split(': ')[0]}:
                  <span className="cajitas-parametros">
                    {grupo.columnas.split(': ').slice(1).join(': ').split(', ').map((columna) => (
                      <span key={columna} className="cajita-parametro"><code>{columna}</code></span>
                    ))}
                  </span>
                </span>
              ) : (
                <span className="renombrar-sugerido"><span aria-hidden="true">→</span> <code>{grupo.columnas}</code></span>
              )}
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
  // Índices: el nombre y debajo lo que corresponde (el sugerido o las columnas del INCLUDE; usuaria, 25 nov.).
  const ENCABEZADO_APILADO = {
    'Nombre sugerido': `${tituloFilas} actual → nombre sugerido`,
    'Columnas en el INCLUDE': `${tituloFilas} → columnas en el INCLUDE`,
  };
  if (ENCABEZADO_APILADO[tituloElementos]) {
    return <TablaRenombrar grupos={grupos} filaActiva={filaActiva} encabezado={ENCABEZADO_APILADO[tituloElementos]} />;
  }
  if (grupos.every((grupo) => grupo.enCajitas)) {
    return <TablaConCajitas grupos={grupos} filaActiva={filaActiva} tituloFilas={tituloFilas} tituloElementos={tituloElementos} />;
  }
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
