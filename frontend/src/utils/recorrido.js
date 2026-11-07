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
  for (let numero = 0; numero < grupos.length; numero += 1) {
    const { nombre, lineas, tipo = 'Tabla' } = grupos[numero];
    if (restante < lineas.length) {
      return {
        numero: numero + 1, total: grupos.length, nombre, tipo, vez: restante + 1, veces: lineas.length, vineta: numero,
      };
    }
    restante -= lineas.length;
  }
  return null;
}

/** Encabezado de la observación con varias viñetas: «11 columnas», «2 tablas»; con una sola, null. */
export function etiquetaDeGrupos(grupos) {
  if (!grupos || grupos.length < 2) return null;
  const tipo = (grupos[0].tipo ?? 'Tabla').toLowerCase();
  return `${grupos.length} ${tipo}s`;
}
