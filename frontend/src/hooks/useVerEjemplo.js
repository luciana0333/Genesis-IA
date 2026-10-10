import { useEffect, useRef } from 'react';

const EVENTO_VER_EJEMPLO = 'genesis:ver-ejemplo';

/** Pide a la vista visible que cargue su ejemplo y lo analice (botón "Ver ejemplo" del encabezado). */
export function pedirEjemplo() {
  window.dispatchEvent(new Event(EVENTO_VER_EJEMPLO));
}

/** Ejecuta `alPedir` cada vez que el encabezado pide ver el ejemplo. */
export function useAlPedirEjemplo(alPedir) {
  const ultimo = useRef(alPedir);
  useEffect(() => {
    ultimo.current = alPedir;
  });

  useEffect(() => {
    const manejar = () => ultimo.current();
    window.addEventListener(EVENTO_VER_EJEMPLO, manejar);
    return () => window.removeEventListener(EVENTO_VER_EJEMPLO, manejar);
  }, []);
}
