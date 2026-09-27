/**
 * Vistas (pestañas) de la aplicación.
 *
 * `ruta` es el fragmento de la URL (#/ruta), lo que permite recargar la página
 * o compartir un enlace sin perder la pestaña activa.
 */

export const VISTAS = [
  {
    id: 'diccionario',
    ruta: 'diccionarios',
    etiqueta: 'Diccionarios',
    tipoRevision: 'procedimiento',
    hero: {
      titulo: 'Auditoría de diccionarios SQL',
      descripcion: 'Valida la estructura, consistencia y estándares de documentación de tus bases de datos SQL Server en tiempo real.',
    },
    resultados: {
      titulo: 'Hallazgos del diccionario',
      nombre: 'Diccionarios',
      subtitulos: ['Errores de estructura', 'Inconsistencias de documentación', 'Faltas de documentación', 'Sugerencias menores'],
    },
  },
  {
    id: 'tabla',
    ruta: 'tablas',
    etiqueta: 'Tablas',
    tipoRevision: 'tabla_estructura',
    hero: {
      titulo: 'Auditoría de tablas SQL',
      complemento: 'Validación de estructura',
      descripcion: 'Valida la estructura, nomenclatura, tipos de datos, nulabilidad y reglas de diseño de tus tablas SQL Server.',
    },
    resultados: {
      titulo: 'Hallazgos de la tabla',
      nombre: 'Tablas',
      subtitulos: ['Errores de estructura', 'Reglas de diseño', 'Tipos y nulabilidad', 'Sugerencias menores'],
    },
  },
  {
    id: 'reporte',
    ruta: 'reportes',
    etiqueta: 'Reportes',
    tipoRevision: 'reporte',
    hero: {
      titulo: 'Auditoría de reportes SQL',
      descripcion: 'Revisa procedimientos de reportes para detectar prácticas inseguras, lecturas innecesarias y consultas que dificultan su mantenimiento.',
    },
    resultados: {
      titulo: 'Hallazgos del reporte',
      nombre: 'Reportes',
      subtitulos: ['Riesgos críticos', 'Inconsistencias de consulta', 'Buenas prácticas', 'Sugerencias menores'],
    },
  },
  {
    id: 'normal',
    ruta: 'normales',
    etiqueta: 'Normales',
    tipoRevision: 'procedimiento_normal',
    hero: {
      titulo: 'Auditoría de procedimientos SQL',
      descripcion: 'Valida procedimientos almacenados normales frente a reglas de control de flujo, consultas y buenas prácticas de desarrollo.',
    },
    resultados: {
      titulo: 'Hallazgos del procedimiento',
      nombre: 'Procedimientos',
      subtitulos: ['Riesgos críticos', 'Reglas incumplidas', 'Buenas prácticas', 'Sugerencias menores'],
    },
  },
  {
    id: 'planes',
    ruta: 'planes',
    etiqueta: 'Planes',
    esPlan: true,
    hero: {
      titulo: 'Análisis de planes de ejecución',
      descripcion: 'Analiza planes reales de SQL Server para detectar conversiones implícitas, spills, scans, lecturas elevadas y problemas de memoria.',
      puntos: [
        'Conversiones implícitas, spills y table scans',
        'Lecturas lógicas, cardinalidad y memoria',
        'Análisis local: el plan no sale de tu equipo',
      ],
      accion: 'Cargar plan',
    },
  },
];

export const VISTA_INICIAL = VISTAS[0];

export function buscarVistaPorRuta(ruta) {
  return VISTAS.find((vista) => vista.ruta === ruta) ?? VISTA_INICIAL;
}

