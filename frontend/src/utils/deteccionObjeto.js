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

const PARTE = String.raw`(?:\[[^\]]+\]|[\w#@$]+)`;
const NOMBRE = new RegExp(
  String.raw`\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(?:TABLE|PROC(?:EDURE)?)\s+(${PARTE}(?:\s*\.\s*${PARTE}){0,2})`,
  'i',
);

/**
 * Nombre del objeto que se crea o modifica en el SQL pegado, tal como está
 * escrito y sin corchetes (dbo.PA_Cliente_Sel_Reporte), o '' si aún no hay uno.
 */
export function extraerNombreObjeto(sql = '') {
  const coincidencia = sql.replace(COMENTARIOS, ' ').match(NOMBRE);
  if (!coincidencia) return '';
  return coincidencia[1].replace(/\s+/g, '').replace(/[[\]]/g, '');
}
