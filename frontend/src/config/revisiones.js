/**
 * Tipos de revisión que entiende el endpoint POST /api/analizar.
 *
 * Cada tipo define cómo se presenta el formulario (qué campos se muestran,
 * etiquetas y ayudas), con qué scripts de ejemplo se precarga y, si la tiene,
 * qué demo con errores se analiza con "Ver ejemplo". El valor de
 * `id` es exactamente el `tipoRevision` que espera el backend.
 */

import {
  DEMO_NORMAL,
  DEMO_REPORTE,
  DEMO_INDICES,
  DEMO_TABLA,
  DICCIONARIO_PROCEDIMIENTO,
  DICCIONARIO_TABLA,
  INDICES_TABLA,
  SQL_NORMAL,
  SQL_PROCEDIMIENTO,
  SQL_REPORTE,
  SQL_TABLA,
} from './ejemplos';

const NOMBRE_TABLA = 'Nombre de la tabla';
const NOMBRE_PROCEDIMIENTO = 'Nombre del procedimiento';

export const REVISIONES = {
  tabla: {
    id: 'tabla',
    etiquetaSelector: 'Diccionario de tabla',
    etiquetaObjeto: NOMBRE_TABLA,
    sql: {
      etiqueta: 'SQL de la tabla (CREATE / ALTER)',
      ayuda: 'Pega aquí el código CREATE TABLE o ALTER TABLE.',
    },
    diccionario: {
      etiqueta: 'Código del diccionario de tabla',
      objetivo: 'la tabla y sus columnas',
    },
    ejemplo: { sql: SQL_TABLA, diccionario: DICCIONARIO_TABLA, nombre: 'CLICKTOPAY.Cliente' },
  },
  procedimiento: {
    id: 'procedimiento',
    etiquetaSelector: 'Diccionario de procedimiento',
    etiquetaObjeto: NOMBRE_PROCEDIMIENTO,
    sql: {
      etiqueta: 'SQL del procedimiento',
      ayuda: 'Pega aquí el código del procedimiento almacenado.',
    },
    diccionario: {
      etiqueta: 'Código del diccionario de procedimiento',
      objetivo: 'el procedimiento y sus parámetros',
    },
    ejemplo: { sql: SQL_PROCEDIMIENTO, diccionario: DICCIONARIO_PROCEDIMIENTO, nombre: 'CLICKTOPAY.PA_Cliente_Sel_PorId' },
  },
  reporte: {
    id: 'reporte',
    etiquetaObjeto: NOMBRE_PROCEDIMIENTO,
    sql: {
      etiqueta: 'SQL del procedimiento de reporte',
      ayuda: 'Pega aquí el CREATE o ALTER PROCEDURE completo para aplicar las reglas de reportes.',
    },
    diccionario: null,
    ejemplo: { sql: SQL_REPORTE, diccionario: '', nombre: 'dbo.PA_BI_Sel_Reporte' },
    demo: { sql: DEMO_REPORTE, diccionario: '', nombre: 'dbo.PA_Cliente_Sel_Resumen' },
  },
  procedimiento_normal: {
    id: 'procedimiento_normal',
    etiquetaObjeto: NOMBRE_PROCEDIMIENTO,
    sql: {
      etiqueta: 'SQL del procedimiento normal',
      ayuda: 'Pega aquí el CREATE o ALTER PROCEDURE para aplicar las reglas generales.',
    },
    diccionario: null,
    ejemplo: { sql: SQL_NORMAL, diccionario: '', nombre: 'dbo.PA_Cliente_Actualizar' },
    demo: { sql: DEMO_NORMAL, diccionario: '', nombre: 'dbo.PA_Cliente_Upd_Estado' },
  },
  tabla_estructura: {
    id: 'tabla_estructura',
    etiquetaObjeto: NOMBRE_TABLA,
    permiteDbcmaica: true,
    sql: {
      etiqueta: 'Script de tabla (CREATE / ALTER)',
      ayuda: 'Pega aquí el script completo de CREATE TABLE o ALTER TABLE.',
    },
    diccionario: null,
    // Segunda cajita, opcional: los CREATE INDEX que acompañan al script de la tabla.
    indices: {
      etiqueta: 'Índices de la tabla',
      ayuda: 'Pega aquí los CREATE INDEX de la tabla, si el script los trae.',
    },
    ejemplo: { sql: SQL_TABLA, diccionario: '', indices: INDICES_TABLA, nombre: 'CLICKTOPAY.Cliente' },
    demo: { sql: DEMO_TABLA, diccionario: '', indices: DEMO_INDICES, nombre: 'TB_cliente_datos' },
  },
};

/**
 * Opciones del selector "Tipo de revisión" de la vista Diccionarios: solo se
 * revisan diccionarios de procedimientos y de tablas. Reportes y
 * procedimientos normales tienen su propia pestaña.
 */
export const OPCIONES_SELECTOR = ['procedimiento', 'tabla'].map((id) => REVISIONES[id]);

/** Construye el cuerpo que espera POST /api/analizar. */
export function construirSolicitud(tipoRevision, campos) {
  return {
    tipoRevision,
    modoRevision: tipoRevision === 'tabla_estructura' ? 'tabla_estructura' : 'diccionario',
    objetoNombre: campos.objetoNombre,
    sqlObject: campos.sqlObject,
    dictScript: campos.dictScript,
    indicesScript: campos.indicesScript ?? '',
    esDbcmaica: campos.esDbcmaica,
  };
}
