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
export function usePlanEjecucion() {
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

  const analizar = useCallback(async () => {
    if (!archivo) {
      setAviso({ texto: 'Selecciona un archivo .sqlplan.', tono: 'error' });
      return;
    }
    if (!archivo.name.toLowerCase().endsWith(EXTENSION_PLAN)) {
      setAviso({ texto: 'El archivo debe tener extensión .sqlplan.', tono: 'error' });
      return;
    }

    setCargando(true);
    setAviso({ texto: 'Analizando el plan real...', tono: 'info' });
    try {
      const datos = await ejecutar((signal) => analizarPlan(archivo, { signal }));
      setAnalisis(datos);
      setAviso({ texto: 'Análisis completado.', tono: 'exito' });
    } catch (error) {
      if (esCancelacion(error)) return;
      setAnalisis(null);
      setAviso({ texto: error.message, tono: 'error' });
    }
    setCargando(false);
  }, [archivo, ejecutar]);

  return { archivo, analisis, aviso, cargando, seleccionarArchivo, limpiar, analizar };
}
