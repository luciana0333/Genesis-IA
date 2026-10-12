import { useCallback, useState } from 'react';
import { analizarPlan, esCancelacion } from '../../api/cliente';
import { useSolicitudCancelable } from '../../hooks/useSolicitudCancelable';

const EXTENSION_PLAN = '.sqlplan';
const SIN_AVISO = { texto: '', tono: 'info' };

/**
 * Estado y acciones del análisis de planes de ejecución (.sqlplan).
 *
 * `analisis` es la respuesta de /api/analizar-plan o null si no hay análisis.
 * `aviso` es el mensaje de estado bajo los botones: { texto, tono: info | exito | error }.
 */
export function usePlanEjecucion(area, limite = null) {
  const [archivo, setArchivo] = useState(null);
  const [analisis, setAnalisis] = useState(null);
  const [aviso, setAviso] = useState(SIN_AVISO);
  const [cargando, setCargando] = useState(false);
  const { ejecutar, cancelar } = useSolicitudCancelable();

  const seleccionarArchivo = useCallback((nuevoArchivo) => {
    setArchivo(nuevoArchivo ?? null);
    setAviso(SIN_AVISO);
  }, []);

  const limpiar = useCallback(() => {
    cancelar();
    setCargando(false);
    setArchivo(null);
    setAnalisis(null);
    setAviso(SIN_AVISO);
  }, [cancelar]);

  /**
   * Analiza el archivo elegido, o el indicado (p. ej. el plan de ejemplo), con
   * las reglas del área y su límite de tiempo (o los indicados, al cambiarlos).
   */
  const analizar = useCallback(async (archivoIndicado, areaIndicada, limiteIndicado) => {
    const plan = archivoIndicado instanceof File ? archivoIndicado : archivo;
    if (!plan) {
      setAviso({ texto: 'Selecciona un archivo .sqlplan.', tono: 'error' });
      return;
    }
    if (!plan.name.toLowerCase().endsWith(EXTENSION_PLAN)) {
      setAviso({ texto: 'El archivo debe tener extensión .sqlplan.', tono: 'error' });
      return;
    }

    setCargando(true);
    setAviso({ texto: 'Analizando el plan real...', tono: 'info' });
    try {
      const datos = await ejecutar((signal) => analizarPlan(plan, {
        signal,
        area: areaIndicada ?? area,
        limite: limiteIndicado !== undefined ? limiteIndicado : limite,
      }));
      setAnalisis(datos);
      setAviso({ texto: 'Análisis completado.', tono: 'exito' });
    } catch (error) {
      if (esCancelacion(error)) return;
      setAnalisis(null);
      setAviso({ texto: error.message, tono: 'error' });
    }
    setCargando(false);
  }, [archivo, area, limite, ejecutar]);

  /** Elige el plan de ejemplo y lo analiza ("Ver ejemplo"). */
  const analizarEjemplo = useCallback((plan) => {
    setArchivo(plan);
    analizar(plan);
  }, [analizar]);

  return { archivo, analisis, aviso, cargando, seleccionarArchivo, limpiar, analizar, analizarEjemplo };
}
