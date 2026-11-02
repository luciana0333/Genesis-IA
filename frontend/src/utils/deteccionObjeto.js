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
  return extraerNombresObjetos(sql)[0] ?? '';
}

/**
 * Nombres de todos los objetos que se crean o modifican en el SQL pegado, en
 * orden y sin repetir (un script puede traer 10 tablas o 10 procedimientos).
 */
export function extraerNombresObjetos(sql = '') {
  const todos = [...sql.replace(COMENTARIOS, ' ').matchAll(new RegExp(NOMBRE.source, 'gi'))].map(
    (coincidencia) => coincidencia[1].replace(/\s+/g, '').replace(/[[\]]/g, ''),
  );
  return [...new Set(todos)];
}

/**
 * Lo que va en el campo del nombre: el del objeto si es uno solo, o el primero
 * y cuántos más hay si son varios («DUN.PA_Solicitud_Sel_Avance y 9 más»).
 */
export function resumirNombresObjetos(nombres) {
  if (nombres.length <= 1) return nombres[0] ?? '';
  return `${nombres[0]} y ${nombres.length - 1} más`;
}
