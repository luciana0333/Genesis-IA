/**
 * Contrato de los archivos que llegan de Bitbucket y a qué módulo de Genesis va cada uno.
 *
 * El backend (POST /api/bitbucket/leer) devuelve:
 *   {
 *     origen:   { tipo: 'pr' | 'rama' | 'commit', espacio, repositorio, referencia, enlace, titulo?, autor? },
 *     archivos: [{
 *       id,          // único en la respuesta
 *       ruta,        // 'Tablas/89PSA2026_CREATE_TABLE_OCR.sql'
 *       estado,      // 'agregado' | 'modificado' | 'renombrado' | 'eliminado'
 *       tipo,        // ver TIPOS
 *       objeto,      // 'OCR.Documento' o null si no se reconoce
 *       contenido,   // texto del archivo en la versión del desarrollador ('' si se eliminó)
 *       pareja,      // id del objeto que documenta un diccionario o al que pertenecen unos índices
 *       dudoso,      // true: el tipo no se distingue con seguridad (¿reporte o procedimiento?) y se pregunta
 *       motivo,      // por qué se clasificó así (se muestra como ayuda)
 *     }],
 *   }
 *
 * La pantalla nunca adivina: si el backend marca un archivo como dudoso, la usuaria elige el módulo.
 */

export const MODULOS = {
  tabla: { etiqueta: 'Tablas', vista: 'tabla', ruta: 'tablas', tipoRevision: 'tabla_estructura' },
  diccionario_tabla: { etiqueta: 'Diccionarios', vista: 'diccionario', ruta: 'diccionarios', tipoRevision: 'tabla' },
  diccionario_procedimiento: {
    etiqueta: 'Diccionarios', vista: 'diccionario', ruta: 'diccionarios', tipoRevision: 'procedimiento',
  },
  diccionario_funcion: { etiqueta: 'Diccionarios', vista: 'diccionario', ruta: 'diccionarios', tipoRevision: 'funcion' },
  procedimiento: { etiqueta: 'Procedimientos', vista: 'normal', ruta: 'procedimientos', tipoRevision: 'procedimiento_normal' },
  reporte: { etiqueta: 'Reportes', vista: 'reporte', ruta: 'reportes', tipoRevision: 'reporte' },
};

/** Qué es cada tipo de archivo y en qué módulos se puede revisar (el primero es el sugerido). */
export const TIPOS = {
  tabla: { etiqueta: 'Tabla', icono: 'tabla', modulos: ['tabla'] },
  indices: { etiqueta: 'Índices', icono: 'tabla', modulos: [] },
  diccionario_tabla: { etiqueta: 'Diccionario de tabla', icono: 'libro', modulos: ['diccionario_tabla'] },
  diccionario_procedimiento: {
    etiqueta: 'Diccionario de procedimiento', icono: 'libro', modulos: ['diccionario_procedimiento'],
  },
  diccionario_funcion: { etiqueta: 'Diccionario de función', icono: 'libro', modulos: ['diccionario_funcion'] },
  procedimiento: { etiqueta: 'Procedimiento', icono: 'codigo', modulos: ['procedimiento', 'reporte'] },
  reporte: { etiqueta: 'Reporte', icono: 'codigo', modulos: ['reporte', 'procedimiento'] },
  funcion: { etiqueta: 'Función', icono: 'codigo', modulos: [] },
  esquema: { etiqueta: 'Esquema', icono: 'otro', modulos: [] },
  datos: { etiqueta: 'Script de datos', icono: 'otro', modulos: [] },
  otro: { etiqueta: 'Otro script', icono: 'otro', modulos: [] },
};

export function tipoDe(archivo) {
  return TIPOS[archivo.tipo] ?? TIPOS.otro;
}

export function nombreArchivo(ruta) {
  return ruta.split('/').pop();
}

export function carpetaArchivo(ruta) {
  const partes = ruta.split('/');
  return partes.length > 1 ? `${partes.slice(0, -1).join('/')}/` : '';
}

/**
 * Cómo queda cada archivo en la lista del paso 2:
 *   'revisar'   → tiene módulo (o la usuaria lo eligió)
 *   'confirmar' → dudoso y sin respuesta todavía
 *   'adjunto'   → índices que se revisan junto con su tabla
 *   'omitido'   → la usuaria eligió no revisarlo
 *   'sinReglas' → esquemas, datos, funciones sin diccionario y otros scripts
 *   'eliminado' → el archivo se borró en el cambio
 */
export function situacion(archivo, eleccion) {
  if (archivo.estado === 'eliminado') return 'eliminado';
  if (archivo.tipo === 'indices' && archivo.pareja) return 'adjunto';
  if (!tipoDe(archivo).modulos.length) return 'sinReglas';
  if (eleccion === 'ninguno') return 'omitido';
  if (eleccion) return 'revisar';
  return archivo.dudoso ? 'confirmar' : 'revisar';
}

/** Módulo con el que se revisa: el que eligió la usuaria o, si no hay duda, el sugerido. */
export function moduloDe(archivo, eleccion) {
  if (situacion(archivo, eleccion) !== 'revisar') return null;
  return eleccion ?? tipoDe(archivo).modulos[0];
}

/**
 * Lo que necesita el módulo para revisar el archivo, igual que si se pegara a mano:
 * { modulo, tipoRevision, campos } o { error } si falta algo (p. ej. el objeto que documenta un diccionario).
 */
export function armarRevision(archivo, modulo, archivos) {
  const destino = MODULOS[modulo];
  if (!destino) return { error: 'No tiene un módulo de revisión.' };
  const base = {
    objetoNombre: archivo.objeto ?? nombreArchivo(archivo.ruta),
    sqlObject: archivo.contenido,
    dictScript: '',
    indicesScript: '',
    esDbcmaica: false,
    esDelMotor: false,
  };

  if (modulo === 'tabla') {
    // Los CREATE INDEX de la tabla que vienen en otro archivo van en la cajita de índices.
    const indices = archivos.filter((otro) => otro.tipo === 'indices' && otro.pareja === archivo.id && otro.estado !== 'eliminado');
    return { modulo, tipoRevision: destino.tipoRevision, campos: { ...base, indicesScript: indices.map((i) => i.contenido).join('\n\n') } };
  }

  if (modulo.startsWith('diccionario_')) {
    const objeto = archivos.find((otro) => otro.id === archivo.pareja && otro.estado !== 'eliminado');
    if (!objeto) {
      return { error: 'El objeto que documenta este diccionario no viene en el cambio: se revisa pegándolo a mano en Diccionarios.' };
    }
    return {
      modulo,
      tipoRevision: destino.tipoRevision,
      campos: { ...base, objetoNombre: objeto.objeto ?? base.objetoNombre, sqlObject: objeto.contenido, dictScript: archivo.contenido },
    };
  }

  return { modulo, tipoRevision: destino.tipoRevision, campos: base };
}

/** Orden del resumen: primero los archivos con observaciones más graves. */
export function pesoGravedad(conteo) {
  if (!conteo) return 0;
  return conteo.critico * 1e6 + conteo.alto * 1e4 + conteo.medio * 1e2 + conteo.bajo;
}
