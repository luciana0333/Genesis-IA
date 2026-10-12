/**
 * Límite de tiempo de ejecución de un plan, en segundos, por área.
 * Se compara con la suma de la duración (Duration) de todas sus consultas.
 * null = el área aún no tiene límite definido: la tarjeta muestra el tiempo sin compararlo.
 */
export const LIMITES_TIEMPO_PLAN = {
  reporte: null,
  negocio: null,
};

export const NOMBRES_AREA_PLAN = {
  reporte: 'Reportes',
  negocio: 'Negocio',
};
