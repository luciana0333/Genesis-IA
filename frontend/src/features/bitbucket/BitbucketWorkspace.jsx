import { useEffect, useRef } from 'react';
import { ListaArchivos } from './ListaArchivos';
import { PortadaBitbucket } from './PortadaBitbucket';
import { ResultadoBitbucket } from './ResultadoBitbucket';
import { useBitbucket } from './useBitbucket';

/**
 * Pestaña Bitbucket: pegar el link (paso 1), confirmar qué es cada archivo (paso 2) y ver el resultado por archivo
 * (paso 3). La revisión es la misma de los módulos; «Abrir en …» lleva al módulo de siempre con el código pegado.
 * Se mantiene montada (oculta) al cambiar de pestaña, para que la lista siga ahí al volver.
 */
export function BitbucketWorkspace() {
  const bitbucket = useBitbucket();
  const { paso, cambio } = bitbucket;
  const pasoRef = useRef(null);

  // Al pasar a la lista o al resultado, se baja hasta ese paso.
  useEffect(() => {
    if (paso !== 'enlace') pasoRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, [paso, cambio]);

  return (
    <div className="bb">
      <PortadaBitbucket
        enlace={bitbucket.enlace}
        onCambiarEnlace={bitbucket.setEnlace}
        lectura={bitbucket.lectura}
        onLeer={() => bitbucket.leer()}
        onVerEjemplo={bitbucket.verEjemplo}
      />
      <div className="bb-pasos" ref={pasoRef}>
        {paso === 'lista' && cambio && (
          <ListaArchivos
            cambio={cambio}
            filas={bitbucket.filas}
            cuenta={bitbucket.cuenta}
            onElegir={bitbucket.elegir}
            onRevisar={bitbucket.revisar}
          />
        )}
        {paso === 'resultado' && cambio && (
          <ResultadoBitbucket
            cambio={cambio}
            filas={bitbucket.filas}
            resultados={bitbucket.resultados}
            onVolver={bitbucket.volverALista}
            onNuevoEnlace={bitbucket.nuevoEnlace}
          />
        )}
      </div>
    </div>
  );
}
