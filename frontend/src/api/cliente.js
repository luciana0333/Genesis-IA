/**
 * Cliente HTTP de la API de Genesis.
 *
 * Centraliza el manejo de errores: cualquier fallo (red, JSON inválido o
 * respuesta no exitosa) se convierte en un ErrorApi con un mensaje apto para
 * mostrar al usuario. Las cancelaciones (AbortController) se propagan tal cual
 * para que el llamador pueda ignorarlas.
 */

const MENSAJE_SIN_CONEXION = 'No se pudo conectar con el servidor.';

export class ErrorApi extends Error {
  constructor(mensaje, estado = 0) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.estado = estado;
  }
}

export function esCancelacion(error) {
  return error?.name === 'AbortError';
}

async function solicitar(ruta, opciones, mensajeFallo) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, opciones);
  } catch (error) {
    if (esCancelacion(error)) throw error;
    throw new ErrorApi(MENSAJE_SIN_CONEXION);
  }

  let datos = null;
  try {
    datos = await respuesta.json();
  } catch (error) {
    if (esCancelacion(error)) throw error;
    // Respuesta sin JSON válido: se reporta con el mensaje genérico.
  }

  if (!respuesta.ok || datos === null) {
    throw new ErrorApi(datos?.error || mensajeFallo, respuesta.status);
  }
  return datos;
}

/** POST /api/siglas — aprueba una sigla y la guarda en el glosario de esta PC. */
export function aprobarSigla(sigla, significado) {
  return solicitar(
    '/api/siglas',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sigla, significado }),
    },
    'No se pudo aprobar la sigla.',
  );
}

/** POST /api/analizar — revisa un objeto SQL con las reglas estáticas. */
export function analizarObjeto(solicitud, { signal } = {}) {
  return solicitar(
    '/api/analizar',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(solicitud),
      signal,
    },
    'No se pudo completar la revisión.',
  );
}

/** POST /api/analizar-plan — analiza un archivo .sqlplan (multipart). */
export function analizarPlan(archivo, { signal, area, limite } = {}) {
  const formulario = new FormData();
  formulario.append('plan', archivo);
  // Área del plan (reporte | negocio): cada una tiene sus propias reglas.
  if (area) formulario.append('area', area);
  // Límite de tiempo del área en segundos (regla «Tiempo de ejecución superado»).
  if (limite != null) formulario.append('limite', String(limite));
  return solicitar(
    '/api/analizar-plan',
    { method: 'POST', body: formulario, signal },
    'No se pudo analizar el plan.',
  );
}

/**
 * POST /api/analizar-planes — revisión por lote: varios .sqlplan, .zip o .rar
 * (multipart). Cada plan vuelve con su análisis completo, igual que uno suelto.
 */
export function analizarPlanes(archivos, { signal, area, limite } = {}) {
  const formulario = new FormData();
  // La ruta dentro de una carpeta arrastrada se conserva para ubicar cada plan.
  archivos.forEach((archivo) => formulario.append('planes', archivo, archivo.rutaRelativa || archivo.name));
  if (area) formulario.append('area', area);
  if (limite != null) formulario.append('limite', String(limite));
  return solicitar(
    '/api/analizar-planes',
    { method: 'POST', body: formulario, signal },
    'No se pudieron analizar los planes.',
  );
}
