const COMENTARIOS = /--[^\r\n]*|\/\*[\s\S]*?\*\//g;
const OBJETO = /\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(TABLE|PROC(?:EDURE)?)\b/i;

/**
 * Tipo de diccionario que corresponde al SQL pegado: 'tabla',
 * 'procedimiento' o null si todavía no se reconoce el objeto.
 * Replica app/analizadores/deteccion_objeto.py del backend.
 */
export function detectarTipoDiccionario(sql = '') {
  const coincidencia = sql.replace(COMENTARIOS, ' ').match(OBJETO);
  if (!coincidencia) return null;
  return coincidencia[1].toUpperCase() === 'TABLE' ? 'tabla' : 'procedimiento';
}
