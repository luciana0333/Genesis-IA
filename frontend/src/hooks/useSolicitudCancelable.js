import { useCallback, useEffect, useRef } from 'react';

/**
 * Ejecuta solicitudes asíncronas cancelando la anterior si sigue en curso y
 * cancelando la pendiente al desmontar el componente. Evita que la respuesta
 * de una revisión vieja pise el estado de una vista nueva.
 */
export function useSolicitudCancelable() {
  const controladorRef = useRef(null);

  const cancelar = useCallback(() => {
    controladorRef.current?.abort();
    controladorRef.current = null;
  }, []);

  const ejecutar = useCallback((tarea) => {
    cancelar();
    const controlador = new AbortController();
    controladorRef.current = controlador;
    return tarea(controlador.signal);
  }, [cancelar]);

  useEffect(() => cancelar, [cancelar]);

  return { ejecutar, cancelar };
}
