import { useCallback, useMemo, useState } from 'react';
import { analizarObjeto, esCancelacion } from '../../api/cliente';
import { NOMBRE_OBJETO_INICIAL } from '../../config/ejemplos';
import { REVISIONES, construirSolicitud } from '../../config/revisiones';
import { useSolicitudCancelable } from '../../hooks/useSolicitudCancelable';
import { contarPorSeveridad } from '../../utils/hallazgos';

const RESULTADO_INICIAL = { estado: 'inicial', hallazgos: [], mensaje: '' };

function camposDeEjemplo(tipoRevision, base) {
  const { ejemplo } = REVISIONES[tipoRevision];
  return { ...base, sqlObject: ejemplo.sql, dictScript: ejemplo.diccionario };
}

/**
 * Estado y acciones del formulario de auditoría de una vista.
 *
 * resultado.estado: 'inicial' | 'cargando' | 'listo' | 'error'
 */
export function useAuditoria(tipoInicial) {
  const [tipoRevision, setTipoRevision] = useState(tipoInicial);
  const [campos, setCampos] = useState(() =>
    camposDeEjemplo(tipoInicial, { objetoNombre: NOMBRE_OBJETO_INICIAL, esDbcmaica: false }),
  );
  const [resultado, setResultado] = useState(RESULTADO_INICIAL);
  const { ejecutar, cancelar } = useSolicitudCancelable();

  const actualizarCampo = useCallback((nombre, valor) => {
    setCampos((actuales) => ({ ...actuales, [nombre]: valor }));
  }, []);

  const cambiarTipo = useCallback((nuevoTipo) => {
    setTipoRevision(nuevoTipo);
    setCampos((actuales) => camposDeEjemplo(nuevoTipo, actuales));
  }, []);

  /** Ajusta el tipo sin tocar lo escrito (detección automática del SQL). */
  const ajustarTipo = useCallback((nuevoTipo) => {
    setTipoRevision(nuevoTipo);
  }, []);

  const restaurarEjemplo = useCallback(() => {
    setCampos((actuales) => camposDeEjemplo(tipoRevision, actuales));
  }, [tipoRevision]);

  const limpiar = useCallback(() => {
    cancelar();
    setCampos({ objetoNombre: '', sqlObject: '', dictScript: '', esDbcmaica: false });
    setResultado(RESULTADO_INICIAL);
  }, [cancelar]);

  const revisar = useCallback(async () => {
    if (!campos.sqlObject.trim()) {
      setResultado({ estado: 'error', hallazgos: [], mensaje: 'Completa el SQL del objeto para iniciar la revisión.' });
      return;
    }
    // En una revisión de diccionario, el diccionario es obligatorio.
    if (REVISIONES[tipoRevision].diccionario && !campos.dictScript.trim()) {
      setResultado({ estado: 'error', hallazgos: [], mensaje: 'Pega el código del diccionario para iniciar la revisión.' });
      return;
    }

    setResultado({ estado: 'cargando', hallazgos: [], mensaje: '' });
    try {
      const datos = await ejecutar((signal) =>
        analizarObjeto(construirSolicitud(tipoRevision, campos), { signal }),
      );
      setResultado({ estado: 'listo', hallazgos: datos.hallazgos ?? [], mensaje: '' });
    } catch (error) {
      if (esCancelacion(error)) return;
      setResultado({ estado: 'error', hallazgos: [], mensaje: error.message });
    }
  }, [campos, tipoRevision, ejecutar]);

  const conteo = useMemo(() => contarPorSeveridad(resultado.hallazgos), [resultado.hallazgos]);

  return {
    tipoRevision,
    revision: REVISIONES[tipoRevision],
    campos,
    resultado,
    conteo,
    actualizarCampo,
    cambiarTipo,
    ajustarTipo,
    restaurarEjemplo,
    limpiar,
    revisar,
  };
}
