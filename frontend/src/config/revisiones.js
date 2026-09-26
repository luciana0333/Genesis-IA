/**
 * Tipos de revisión que entiende el endpoint POST /api/analizar.
 *
 * Cada tipo define cómo se presenta el formulario (qué campos se muestran,
 * etiquetas y ayudas) y con qué scripts de ejemplo se precarga. El valor de
 * `id` es exactamente el `tipoRevision` que espera el backend.
 */

import {
  DICCIONARIO_PROCEDIMIENTO,
  SQL_NORMAL,
  SQL_PROCEDIMIENTO,
  SQL_REPORTE,
  SQL_TABLA,
} from './ejemplos';

const NOMBRE_TABLA = 'Nombre de la Tabla';
const NOMBRE_PROCEDIMIENTO = 'Nombre del Procedimiento';

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
    ejemplo: { sql: SQL_TABLA, diccionario: '' },
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
    ejemplo: { sql: SQL_PROCEDIMIENTO, diccionario: DICCIONARIO_PROCEDIMIENTO },
  },
  reporte: {
    id: 'reporte',
    etiquetaSelector: 'Procedimiento de reporte',
    etiquetaObjeto: NOMBRE_PROCEDIMIENTO,
    sql: {
      etiqueta: 'SQL del procedimiento de reporte',
      ayuda: 'Pega aquí el CREATE o ALTER PROCEDURE completo para aplicar las reglas de reportes.',
    },
    diccionario: null,
    ejemplo: { sql: SQL_REPORTE, diccionario: '' },
  },
  procedimiento_normal: {
    id: 'procedimiento_normal',
    etiquetaSelector: 'Procedimiento normal',
    etiquetaObjeto: NOMBRE_PROCEDIMIENTO,
    sql: {
      etiqueta: 'SQL del procedimiento normal',
      ayuda: 'Pega aquí el CREATE o ALTER PROCEDURE para aplicar las reglas generales.',
    },
    diccionario: null,
    ejemplo: { sql: SQL_NORMAL, diccionario: '' },
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
    ejemplo: { sql: SQL_TABLA, diccionario: '' },
  },
};

/** Opciones del selector "Tipo de revisión" de la vista Diccionarios. */
export const OPCIONES_SELECTOR = ['tabla', 'procedimiento', 'reporte', 'procedimiento_normal']
  .map((id) => REVISIONES[id]);

/** Construye el cuerpo que espera POST /api/analizar. */
export function construirSolicitud(tipoRevision, campos) {
  return {
    tipoRevision,
    modoRevision: tipoRevision === 'tabla_estructura' ? 'tabla_estructura' : 'diccionario',
    objetoNombre: campos.objetoNombre,
    sqlObject: campos.sqlObject,
    dictScript: campos.dictScript,
    esDbcmaica: campos.esDbcmaica,
  };
}
