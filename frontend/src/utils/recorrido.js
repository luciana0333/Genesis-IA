/**
 * Observación cuyas viñetas traen cada una sus líneas (ej.: «Múltiples JOIN sobre la misma tabla»):
 * [{ nombre: 'TempDNCalculado', lineas: [345, 379], tipo: 'Tabla' }, ...]. Para la posición `indice` del
 * recorrido (que va viñeta por viñeta), dice en cuál se está y qué vez es:
 * { numero: 1, total: 4, nombre: 'TempDNCalculado', tipo: 'Tabla', vez: 2, veces: 2, vineta: 0 }.
 * `tipo` es lo que la barra dice de cada viñeta («Tabla», «Columna»); si no viene, «Tabla».
 */
export function grupoDelRecorrido(grupos, indice) {
  if (!grupos?.length) return null;
  let restante = indice;
  // «Procedimiento 1 de 3»: un mismo nombre en dos grupos (ALTER: lo que falta y lo que se agrega) es una sola fila
  // de la tabla, así que se cuenta una vez (usuaria, 21 nov.).
  const nombres = [...new Set(grupos.map((grupo) => grupo.nombre))];
  for (let numero = 0; numero < grupos.length; numero += 1) {
    const { nombre, lineas, tipo = 'Tabla', etiquetas } = grupos[numero];
    if (restante < lineas.length) {
      return {
        numero: nombres.indexOf(nombre) + 1, total: nombres.length, nombre, tipo, vez: restante + 1, veces: lineas.length, vineta: numero,
        // Qué es cada parada, si la observación lo dice (ej.: el tipo de dato, «VARCHAR(5)»).
        etiqueta: etiquetas?.[restante] ?? null,
      };
    }
    restante -= lineas.length;
  }
  return null;
}

/**
 * Encabezado de la observación con varias viñetas: «11 casos», «2 casos» (cada tabla o columna es un caso; usuaria,
 * 17 nov.); con una sola, null.
 */
export function etiquetaDeGrupos(grupos) {
  if (!grupos || grupos.length < 2) return null;
  // Filas por situación (ALTER: «no se incluyen» / «se agregan»): cada elemento es un caso.
  if (grupos.some((grupo) => grupo.seccion)) return `${grupos.reduce((total, grupo) => total + grupo.lineas.length, 0)} casos`;
  return `${grupos.length} casos`;
}
