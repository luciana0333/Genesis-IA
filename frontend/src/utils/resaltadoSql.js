/**
 * Resaltado de T-SQL para el editor: separa el texto en fragmentos con su tipo
 * (palabra clave, texto entre comillas, variable, comentario o normal). Une los
 * fragmentos y se obtiene exactamente el texto original, así el resaltado
 * queda alineado con lo que se escribe.
 */

const PALABRAS_CLAVE = new Set([
  'ADD', 'ALTER', 'AND', 'AS', 'ASC', 'BEGIN', 'BETWEEN', 'BIGINT', 'BIT', 'BY', 'CASE', 'CAST',
  'CATCH', 'CHAR', 'CLUSTERED', 'COLLATE', 'COLUMN', 'COMMIT', 'CONSTRAINT', 'CONVERT', 'CREATE',
  'CROSS', 'DATE', 'DATETIME', 'DECIMAL', 'DECLARE', 'DEFAULT', 'DELETE', 'DESC', 'DISTINCT',
  'DROP', 'ELSE', 'END', 'EXEC', 'EXECUTE', 'EXISTS', 'FOREIGN', 'FROM', 'FULL', 'FUNCTION', 'GO',
  'GROUP', 'HAVING', 'IDENTITY', 'IF', 'IN', 'INDEX', 'INNER', 'INSERT', 'INT', 'INTO', 'IS', 'JOIN',
  'KEY', 'LEFT', 'LIKE', 'MAX', 'MERGE', 'MONEY', 'NCHAR', 'NOCOUNT', 'NOLOCK', 'NONCLUSTERED',
  'NOT', 'NULL', 'NUMERIC', 'NVARCHAR', 'ON', 'OR', 'ORDER', 'OUTER', 'OUTPUT', 'PRIMARY', 'PROC',
  'PROCEDURE', 'RAISERROR', 'REFERENCES', 'RETURN', 'RIGHT', 'ROLLBACK', 'SELECT', 'SET',
  'SMALLINT', 'TABLE', 'THEN', 'THROW', 'TINYINT', 'TOP', 'TRAN', 'TRANSACTION', 'TRY', 'UNION',
  'UNIQUE', 'UPDATE', 'VALUES', 'VARBINARY', 'VARCHAR', 'VIEW', 'WAITFOR', 'WHEN', 'WHERE',
  'WHILE', 'WITH',
]);

// Comentarios, textos (N'...'), variables (@x) y palabras; el resto queda igual.
const PATRON = /(--[^\n]*|\/\*[\s\S]*?(?:\*\/|$))|(N?'(?:[^']|'')*(?:'|$))|(@@?\w+)|([A-Za-z_]\w*)/g;

export function tokenizarSql(texto) {
  const fragmentos = [];
  let ultimo = 0;
  for (const coincidencia of texto.matchAll(PATRON)) {
    const [entero, comentario, cadena, variable, palabra] = coincidencia;
    if (coincidencia.index > ultimo) fragmentos.push({ tipo: 'texto', valor: texto.slice(ultimo, coincidencia.index) });
    let tipo = 'texto';
    if (comentario) tipo = 'comentario';
    else if (cadena) tipo = 'cadena';
    else if (variable) tipo = 'variable';
    else if (palabra && PALABRAS_CLAVE.has(palabra.toUpperCase())) tipo = 'clave';
    fragmentos.push({ tipo, valor: entero });
    ultimo = coincidencia.index + entero.length;
  }
  if (ultimo < texto.length) fragmentos.push({ tipo: 'texto', valor: texto.slice(ultimo) });
  return fragmentos;
}
