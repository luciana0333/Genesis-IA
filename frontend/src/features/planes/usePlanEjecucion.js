import { useCallback, useState } from 'react';
import { analizarPlan, esCancelacion } from '../../api/cliente';
import { useSolicitudCancelable } from '../../hooks/useSolicitudCancelable';

const EXTENSION_PLAN = '.sqlplan';

/**
 * Estado y acciones del análisis de planes de ejecución (.sqlplan).
 * `analisis` es la respuesta de /api/analizar-plan o null si no hay análisis.
 */
export function usePlanEjecucion() {
  const [archivo, setArchivo] = useState(null);
  const [analisis, setAnalisis] = useState(null);
  const [estado, setEstado] = useState('');
  const [cargando, setCargando] = useState(false);
  const { ejecutar, cancelar } = useSolicitudCancelable();

  const seleccionarArchivo = useCallback((nuevoArchivo) => {
    setArchivo(nuevoArchivo ?? null);
    setEstado('');
  }, []);

  const limpiar = useCallback(() => {
    cancelar();
    setCargando(false);
    setArchivo(null);
    setAnalisis(null);
    setEstado('');
  }, [cancelar]);

  const analizar = useCallback(async () => {
    if (!archivo) {
      setEstado('Selecciona un archivo .sqlplan.');
      return;
    }
    if (!archivo.name.toLowerCase().endsWith(EXTENSION_PLAN)) {
      setEstado('El archivo debe tener extensión .sqlplan.');
      return;
    }

    setCargando(true);
    setEstado('Analizando el plan real...');
    try {
      const datos = await ejecutar((signal) => analizarPlan(archivo, { signal }));
      setAnalisis(datos);
      setEstado('Análisis completado.');
    } catch (error) {
      if (esCancelacion(error)) return;
      setAnalisis(null);
      setEstado(error.message);
    }
    setCargando(false);
  }, [archivo, ejecutar]);

  return { archivo, analisis, estado, cargando, seleccionarArchivo, limpiar, analizar };
}
