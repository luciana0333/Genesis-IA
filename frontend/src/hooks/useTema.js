import { useCallback, useEffect, useState } from 'react';

const CLAVE_ALMACENAMIENTO = 'genesis-ia:tema';

function leerTemaGuardado() {
  try {
    return localStorage.getItem(CLAVE_ALMACENAMIENTO) === 'dark' ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

/**
 * Tema claro/oscuro. Se aplica como `data-theme` en <html> (así lo espera el
 * CSS) y se recuerda entre visitas.
 */
export function useTema() {
  const [tema, setTema] = useState(leerTemaGuardado);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', tema);
    try {
      localStorage.setItem(CLAVE_ALMACENAMIENTO, tema);
    } catch {
      // Almacenamiento no disponible (modo privado, políticas del navegador).
    }
  }, [tema]);

  const alternarTema = useCallback(() => {
    setTema((actual) => (actual === 'dark' ? 'light' : 'dark'));
  }, []);

  return { tema, alternarTema };
}
