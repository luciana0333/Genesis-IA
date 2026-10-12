import { useCallback, useState } from 'react';
import { LIMITES_TIEMPO_PLAN } from '../../config/planes';

const CLAVE_LIMITES = 'genesis.limitesTiempoPlan';

function leerLimites() {
  try {
    return { ...LIMITES_TIEMPO_PLAN, ...JSON.parse(localStorage.getItem(CLAVE_LIMITES) ?? '{}') };
  } catch {
    return { ...LIMITES_TIEMPO_PLAN };
  }
}

/**
 * Límite de tiempo (segundos) de cada área, guardado en este navegador.
 * Lo usan la tarjeta del velocímetro y la regla «Tiempo de ejecución superado».
 */
export function useLimitesTiempo() {
  const [limites, setLimites] = useState(leerLimites);

  const cambiarLimite = useCallback((area, valor) => {
    setLimites((actuales) => {
      const nuevos = { ...actuales, [area]: valor };
      try {
        localStorage.setItem(CLAVE_LIMITES, JSON.stringify(nuevos));
      } catch {
        // Sin almacenamiento (modo privado): el límite vale solo mientras la página esté abierta.
      }
      return nuevos;
    });
  }, []);

  return { limites, cambiarLimite };
}
