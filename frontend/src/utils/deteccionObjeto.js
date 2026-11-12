// Comentarios y textos ('...'): lo que haya adentro (un CREATE en SQL dinámico, un comentario) no cuenta.
const COMENTARIOS_Y_TEXTOS = /'(?:[^']|'')*'|--[^\r\n]*|\/\*[\s\S]*?\*\//g;
const OBJETO = /\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(TABLE|PROC(?:EDURE)?|FUNCTION)\s+(?![#@])/i;

/** TABLE → 'tabla', FUNCTION → 'funcion', PROC/PROCEDURE → 'procedimiento'. */
const tipoDe = (palabra) => {
  const objeto = palabra.toUpperCase();
  if (objeto === 'TABLE') return 'tabla';
  return objeto === 'FUNCTION' ? 'funcion' : 'procedimiento';
};

const sinComentariosNiTextos = (sql) => sql.replace(COMENTARIOS_Y_TEXTOS, ' ');

/**
 * Tipo de diccionario que corresponde al SQL pegado: 'tabla', 'procedimiento',
 * 'funcion' o null si todavía no se reconoce el objeto.
 * Replica app/analizadores/deteccion_objeto.py del backend.
 */
export function detectarTipoDiccionario(sql = '') {
  const coincidencia = sinComentariosNiTextos(sql).match(OBJETO);
  if (!coincidencia) return null;
  return tipoDe(coincidencia[1]);
}

const PARTE = String.raw`(?:\[[^\]]+\]|[\w#@$]+)`;
const NOMBRE = new RegExp(
  String.raw`\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(TABLE|PROC(?:EDURE)?|FUNCTION)\s+(${PARTE}(?:\s*\.\s*${PARTE}){0,2})`,
  'gi',
);

/**
 * Nombre del objeto que se crea o modifica en el SQL pegado, tal como está
 * escrito y sin corchetes (dbo.PA_Cliente_Sel_Reporte), o '' si aún no hay uno.
 */
export function extraerNombreObjeto(sql = '') {
  return extraerNombresObjetos(sql)[0] ?? '';
}

/**
 * Nombres de los objetos que se crean o modifican en el SQL pegado, en orden y
 * sin repetir (un script puede traer 10 tablas o 10 procedimientos). Solo los
 * del mismo tipo que el primero: las tablas que un procedimiento crea adentro no
 * son otros objetos. Las temporales (#T) y las variables de tabla (@T) nunca cuentan.
 */
export function extraerNombresObjetos(sql = '') {
  const objetos = [...sinComentariosNiTextos(sql).matchAll(NOMBRE)]
    .map((coincidencia) => ({
      tipo: tipoDe(coincidencia[1]),
      nombre: coincidencia[2].replace(/\s+/g, '').replace(/[[\]]/g, ''),
    }))
    .filter(({ nombre }) => !/^[#@]/.test(nombre.split('.').pop()));
  if (!objetos.length) return [];
  const tipo = objetos[0].tipo;
  return [...new Set(objetos.filter((objeto) => objeto.tipo === tipo).map((objeto) => objeto.nombre))];
}

/**
 * Lo que va en el campo del nombre: el del objeto si es uno solo, o el primero
 * y cuántos más hay si son varios («DUN.PA_Solicitud_Sel_Avance y 9 más»).
 */
export function resumirNombresObjetos(nombres) {
  if (nombres.length <= 1) return nombres[0] ?? '';
  return `${nombres[0]} y ${nombres.length - 1} más`;
}
