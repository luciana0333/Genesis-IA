import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { analizarObjeto, esCancelacion } from '../../api/cliente';
import { NOMBRE_OBJETO_INICIAL } from '../../config/ejemplos';
import { REVISIONES, construirSolicitud } from '../../config/revisiones';
import { useSolicitudCancelable } from '../../hooks/useSolicitudCancelable';
import { contarPorSeveridad } from '../../utils/hallazgos';

const RESULTADO_INICIAL = { estado: 'inicial', hallazgos: [], mensaje: '' };

function camposDeEjemplo(tipoRevision, base) {
  const { ejemplo } = REVISIONES[tipoRevision];
  return {
    ...base, objetoNombre: ejemplo.nombre ?? base.objetoNombre, sqlObject: ejemplo.sql,
    dictScript: ejemplo.diccionario, indicesScript: ejemplo.indices ?? '',
  };
}

/** Campos con la demo de "Ver ejemplo" (o el ejemplo, si la revisión no tiene demo). */
function camposDeDemo(tipoRevision, base) {
  const { demo, ejemplo } = REVISIONES[tipoRevision];
  const script = demo ?? ejemplo;
  return {
    ...base, objetoNombre: script.nombre ?? base.objetoNombre, sqlObject: script.sql,
    dictScript: script.diccionario, indicesScript: script.indices ?? '',
  };
}

/**
 * Estado y acciones del formulario de auditoría de una vista.
 *
 * resultado.estado: 'inicial' | 'cargando' | 'listo' | 'error'
 */
export function useAuditoria(tipoInicial, traspaso = null) {
  // Con un traspaso de Bitbucket («Abrir en …») se arranca con su código en vez del ejemplo.
  const [tipoRevision, setTipoRevision] = useState(traspaso?.tipoRevision ?? tipoInicial);
  const [campos, setCampos] = useState(() => (traspaso
    ? { objetoNombre: '', dictScript: '', indicesScript: '', esDbcmaica: false, esDelMotor: false, ...traspaso.campos }
    : camposDeEjemplo(tipoInicial, { objetoNombre: NOMBRE_OBJETO_INICIAL, esDbcmaica: false, esDelMotor: false })));
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
    setCampos({ objetoNombre: '', sqlObject: '', dictScript: '', indicesScript: '', esDbcmaica: false, esDelMotor: false });
    setResultado(RESULTADO_INICIAL);
  }, [cancelar]);

  /**
   * Revisa los campos actuales, o los indicados (p. ej. el ejemplo recién cargado).
   * `sinDiccionario`: el usuario confirmó revisar aunque no pegó el diccionario.
   */
  const revisar = useCallback(async (camposARevisar = campos, { sinDiccionario = false } = {}) => {
    // En Tablas basta con los índices: pueden ser de una tabla que ya existe.
    const soloIndices = REVISIONES[tipoRevision].indices && (camposARevisar.indicesScript ?? '').trim();
    if (!camposARevisar.sqlObject.trim() && !soloIndices) {
      setResultado({ estado: 'error', hallazgos: [], mensaje: 'Completa el SQL del objeto para iniciar la revisión.' });
      return;
    }
    // En una revisión de diccionario, el diccionario es obligatorio.
    if (REVISIONES[tipoRevision].diccionario && !camposARevisar.dictScript.trim() && !sinDiccionario) {
      setResultado({ estado: 'error', hallazgos: [], mensaje: 'Pega el código del diccionario para iniciar la revisión.' });
      return;
    }

    setResultado({ estado: 'cargando', hallazgos: [], mensaje: '' });
    try {
      const datos = await ejecutar((signal) =>
        analizarObjeto(construirSolicitud(tipoRevision, camposARevisar), { signal }),
      );
      setResultado({
        estado: 'listo',
        hallazgos: datos.hallazgos ?? [],
        mensaje: '',
        // Diccionarios: script de lo que falta documentar («Generar diccionario faltante»).
        diccionarioFaltante: datos.diccionarioFaltante ?? null,
        // Validador SQL Server, aparte de las buenas prácticas: {disponible, alcance, hallazgos} o {disponible: false, motivo}.
        validacion: datos.validacion ?? null,
      });
    } catch (error) {
      if (esCancelacion(error)) return;
      setResultado({ estado: 'error', hallazgos: [], mensaje: error.message });
    }
  }, [campos, tipoRevision, ejecutar]);

  /** Carga la demo de la revisión y la revisa enseguida ("Ver ejemplo"). */
  const revisarEjemplo = useCallback(() => {
    const ejemplo = camposDeDemo(tipoRevision, campos);
    setCampos(ejemplo);
    revisar(ejemplo);
  }, [tipoRevision, campos, revisar]);

  // El código que llegó de Bitbucket se revisa apenas se abre el módulo (una sola vez).
  // Se agenda en vez de llamarse directo: en desarrollo React monta dos veces y la primera solicitud se cancelaría.
  const traspasoRevisado = useRef(false);
  useEffect(() => {
    if (!traspaso || traspasoRevisado.current) return undefined;
    const agenda = setTimeout(() => {
      traspasoRevisado.current = true;
      revisar();
    });
    return () => clearTimeout(agenda);
  }, [traspaso, revisar]);

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
    revisarEjemplo,
  };
}
