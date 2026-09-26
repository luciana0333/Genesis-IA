/**
 * Catálogo de presentación de reglas y severidades.
 * El backend envía códigos (ej. "TABLE_SCAN"); aquí se traducen a texto legible.
 */

/** Orden canónico de severidades, de mayor a menor gravedad. */
export const SEVERIDADES = ['critico', 'alto', 'medio', 'bajo'];

export const ETIQUETAS_SEVERIDAD = {
  critico: 'Crítico',
  alto: 'Alto',
  medio: 'Medio',
  bajo: 'Bajo',
};

export const NOMBRES_REGLAS = {
  ESQUEMA_NO_COINCIDE: 'Esquema no coincide',
  NOMBRE_NO_COINCIDE: 'Nombre no coincide',
  NOMBRE_TABLA_NO_COINCIDE: 'Nombre de tabla no coincide',
  PARAMETRO_SIN_DESCRIPCION: 'Parámetro sin descripción',
  PARAMETRO_FALTANTE: 'Parámetro faltante',
  COLUMNA_FALTANTE: 'Columna no documentada',
  TABLA_SIN_DESCRIPCION: 'Tabla no documentada',
  DESCRIPCION_VACIA: 'Descripción vacía',
  DESCRIPCION_COLUMNA_VACIA: 'Descripción de columna vacía',
  ALTER_SIN_DICCIONARIO: 'ALTER sin diccionario',
  VALOR_SIN_COMILLAS: 'Valor sin comillas',
  TABLA_SIN_ESQUEMA: 'Tabla sin esquema',
  COLUMNA_SIN_NOT_NULL_NI_DEFAULT: 'Columna sin NOT NULL ni DEFAULT',
  COLUMNA_SIN_COLLATE: 'Columna sin COLLATE',
  COLUMNA_PREFIJO_TIPO_INVALIDO: 'Prefijo de columna inválido',
  TABLA_CON_PALABRA_OMITIBLE: 'Nombre de tabla con palabra omitible',
  COLLATE_EN_TIPO_NO_TEXTO: 'COLLATE en tipo no textual',
  TABLA_FISICA_SIN_NOLOCK: 'Tabla física sin NOLOCK',
  NOLOCK_EN_TABLA_TEMPORAL: 'NOLOCK en tabla temporal',
  HINT_PLAN_PROHIBIDO: 'Hint de plan prohibido',
  CODIGO_SQL_COMENTADO: 'Código SQL comentado',
  TEMPORAL_TEXTO_SIN_COLLATE: 'Texto temporal sin COLLATE',
  SELECT_INTO_PROHIBIDO: 'SELECT INTO prohibido',
  SELECT_ESTRELLA_PROHIBIDO: 'SELECT estrella prohibido',
  IN_CON_UN_SOLO_VALOR: 'IN con un solo valor',
  CATALOGO_SISTEMA_PROHIBIDO: 'Catálogo de sistema prohibido',
  MODIFICACION_TABLA_FISICA: 'Modificación de tabla física',
  VARIABLE_DECLARADA_SIN_USO: 'Variable declarada sin uso',
  PROCEDIMIENTO_SIN_DESCRIPCION: 'Procedimiento sin descripción',
  WHILE_PROHIBIDO: 'WHILE prohibido',
  GOTO_PROHIBIDO: 'GOTO prohibido',
  MERGE_PROHIBIDO: 'MERGE prohibido',
  COLLATE_EN_PREDICADO: 'COLLATE en predicado',
  STUFF_FOR_XML_PATH_PROHIBIDO: 'STUFF con FOR XML PATH prohibido',
  FN_SPLIT_PROHIBIDO: 'FN_SPLIT prohibido',
  LTRIM_RTRIM_PROHIBIDO: 'LTRIM(RTRIM(...)) prohibido',
  NOLOCK_EN_TABLA_FISICA: 'NOLOCK en tabla física',
  ORDER_BY_NUMERICO_PROHIBIDO: 'ORDER BY numérico prohibido',
  CAST_EN_JOIN_PROHIBIDO: 'CAST en JOIN prohibido',
  SQL_DINAMICO_PROHIBIDO: 'SQL dinámico prohibido',
  VARCHAR_MAX_PROHIBIDO: 'VARCHAR(MAX) prohibido',
  SINTAXIS_DICCIONARIO: 'Error de sintaxis en el diccionario',
  PARAMETROS_INCOMPLETOS: 'Parámetros incompletos',
  TIPO_NIVEL_INCORRECTO: 'Tipo de nivel incorrecto',
  COLUMNA_NO_EXISTE: 'Columna documentada inexistente',
  DOCUMENTACION_DUPLICADA: 'Documentación duplicada',
  DESCRIPCION_TABLA_INADECUADA: 'Descripción de tabla inadecuada',
  CONVERSION_IMPLICITA: 'Conversión implícita',
  SPILL_TEMPDB: 'Spill hacia TempDB',
  TABLE_SCAN: 'Table Scan',
  LECTURAS_LOGICAS_ELEVADAS: 'Lecturas lógicas elevadas',
  SOBREESTIMACION_FILAS: 'Desviación de cardinalidad',
  MEMORIA_CONCEDIDA_SOBREDIMENSIONADA: 'Memoria concedida sobredimensionada',
  VARBINARY_DOCUMENTO_IDENTIFICADO: 'VARBINARY para documento identificado',
};

export function nombreRegla(codigo) {
  return NOMBRES_REGLAS[codigo] || codigo || 'Hallazgo de auditoría';
}

export function etiquetaSeveridad(severidad) {
  return ETIQUETAS_SEVERIDAD[severidad] || severidad;
}
