/**
 * Recortes de la imagen de un hallazgo del plan: la misma conversión implícita en varias consultas se muestra
 * una sola vez, con todas sus consultas en la etiqueta («Consultas 16 y 17»; usuaria, 25 nov.).
 */

// Máximo de conversiones distintas que se muestran de entrada; el resto, con «Ver N más».
export const MAXIMO_CONVERSIONES = 3;

/** La conversión sin los alias («#MovimientoDetalle.[nMovImporte] as [D].[nMovImporte]» → sin « as [D]…»). */
export function claveConversion(textos) {
  return textos
    .map((texto) => texto.replace(/\s+as\s+\[[^\]]*\](?:\.\[[^\]]*\])*/gi, '').replace(/\s+/g, ' ').trim())
    .sort()
    .join(' | ');
}

// Reglas cuya imagen muestra la misma tabla una sola vez, aunque se lea en varias consultas (usuaria, 25 nov.:
// Producto en las consultas 38 y 119 de PA_CuentasOrden_Proc_EstadisticoCapitalMensual).
const REGLAS_POR_TABLA = new Set(['LECTURA_COMPLETA_TABLA', 'LECTURA_RESIDUAL_ELEVADA']);

/**
 * casos: [{ sentencia, nodo }] en el orden del hallazgo.
 * Devuelve [{ sentencia, nodo, consultas }]: los casos con conversión resaltada (nodo.resaltar) se juntan por
 * conversión; en las reglas por tabla, por tabla e índice; los demás quedan como están, cada uno con su consulta.
 */
export function agruparCasos(casos, regla) {
  const grupos = [];
  const porClave = new Map();
  for (const caso of casos) {
    const numero = caso.sentencia.numero;
    const resaltar = caso.nodo.resaltar ?? [];
    let clave = null;
    if (resaltar.length) clave = claveConversion(resaltar);
    else if (REGLAS_POR_TABLA.has(regla) && caso.nodo.objeto) {
      clave = `${caso.nodo.fisica}|${caso.nodo.objeto}|${caso.nodo.indice ?? ''}`.toUpperCase();
    }
    if (clave === null) {
      grupos.push({ ...caso, consultas: [numero] });
      continue;
    }
    const existente = porClave.get(clave);
    if (existente) {
      if (!existente.consultas.includes(numero)) existente.consultas.push(numero);
      continue;
    }
    const grupo = { ...caso, consultas: [numero] };
    porClave.set(clave, grupo);
    grupos.push(grupo);
  }
  return grupos;
}

/** «Consulta 12» / «Consultas 16 y 17» / «Consultas 3, 8 y 9». */
export function etiquetaConsultas(consultas) {
  if (consultas.length === 1) return `Consulta ${consultas[0]}`;
  return `Consultas ${consultas.slice(0, -1).join(', ')} y ${consultas[consultas.length - 1]}`;
}
