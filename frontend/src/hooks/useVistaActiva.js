import { useEffect, useState } from 'react';
import { buscarVistaPorRuta } from '../config/vistas';

function rutaDesdeHash() {
  return window.location.hash.replace(/^#\/?/, '');
}

/**
 * Vista activa sincronizada con el hash de la URL (#/tablas, #/planes...).
 * No se usa un router completo porque la aplicación es de una sola página
 * con pestañas; el hash basta y funciona sin configurar el servidor.
 */
export function useVistaActiva() {
  const [vista, setVista] = useState(() => buscarVistaPorRuta(rutaDesdeHash()));

  useEffect(() => {
    const sincronizar = () => setVista(buscarVistaPorRuta(rutaDesdeHash()));
    window.addEventListener('hashchange', sincronizar);
    return () => window.removeEventListener('hashchange', sincronizar);
  }, []);

  return { vista };
}
