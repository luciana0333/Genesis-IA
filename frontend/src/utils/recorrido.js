/**
 * Observación cuyas viñetas traen cada una sus líneas (ej.: «Misma tabla en varios JOIN»):
 * [{ nombre: 'TempDNCalculado', lineas: [345, 379] }, ...]. Para la posición `indice` del
 * recorrido (que va viñeta por viñeta), dice en cuál se está y qué vez es:
 * { numero: 1, total: 4, nombre: 'TempDNCalculado', vez: 2, veces: 2, vineta: 0 }.
 */
export function grupoDelRecorrido(grupos, indice) {
  if (!grupos?.length) return null;
  let restante = indice;
  for (let numero = 0; numero < grupos.length; numero += 1) {
    const { nombre, lineas } = grupos[numero];
    if (restante < lineas.length) {
      return { numero: numero + 1, total: grupos.length, nombre, vez: restante + 1, veces: lineas.length, vineta: numero };
    }
    restante -= lineas.length;
  }
  return null;
}
