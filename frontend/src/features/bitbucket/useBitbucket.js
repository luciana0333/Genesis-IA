import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { analizarObjeto, esCancelacion, leerBitbucket } from '../../api/cliente';
import { construirSolicitud } from '../../config/revisiones';
import { contarPorSeveridad } from '../../utils/hallazgos';
import { armarRevision, moduloDe, situacion } from './archivos';
import { ENLACE_EJEMPLO, PR_EJEMPLO } from './ejemplo';
import { leerEnlace } from './enlace';

const SIN_CONEXION_BITBUCKET = 'La conexión con Bitbucket todavía no está activa en Genesis. Mientras tanto, '
  + 'puedes probar todo el recorrido con «Ver ejemplo».';

/**
 * Estado de la pestaña Bitbucket.
 *
 * paso: 'enlace' (paso 1) → 'lista' (paso 2) → 'resultado' (paso 3)
 * lectura.estado: 'inicial' | 'leyendo' | 'error'
 * resultados[id]: { estado: 'revisando' | 'listo' | 'error', conteo, total, mensaje, revision }
 */
export function useBitbucket() {
  const [enlace, setEnlace] = useState('');
  const [lectura, setLectura] = useState({ estado: 'inicial', mensaje: '' });
  const [cambio, setCambio] = useState(null);
  const [elecciones, setElecciones] = useState({});
  const [resultados, setResultados] = useState({});
  const [paso, setPaso] = useState('enlace');
  const controlador = useRef(null);

  const cancelar = useCallback(() => {
    controlador.current?.abort();
    controlador.current = null;
  }, []);
  useEffect(() => cancelar, [cancelar]);

  const nuevoControlador = useCallback(() => {
    cancelar();
    controlador.current = new AbortController();
    return controlador.current.signal;
  }, [cancelar]);

  const cargarCambio = useCallback((datos) => {
    setCambio(datos);
    setElecciones({});
    setResultados({});
    setLectura({ estado: 'inicial', mensaje: '' });
    setPaso('lista');
  }, []);

  const leer = useCallback(async (texto = enlace) => {
    const leido = leerEnlace(texto);
    if (leido.error) {
      setLectura({ estado: 'error', mensaje: leido.error });
      return;
    }
    setLectura({ estado: 'leyendo', mensaje: '' });
    try {
      const datos = await leerBitbucket(leido.enlace, { signal: nuevoControlador() });
      cargarCambio(datos);
    } catch (error) {
      if (esCancelacion(error)) return;
      // 404: el servidor todavía no tiene la conexión con Bitbucket.
      setLectura({ estado: 'error', mensaje: error.estado === 404 ? SIN_CONEXION_BITBUCKET : error.message });
    }
  }, [enlace, nuevoControlador, cargarCambio]);

  const verEjemplo = useCallback(() => {
    cancelar();
    setEnlace(ENLACE_EJEMPLO);
    cargarCambio(PR_EJEMPLO);
  }, [cancelar, cargarCambio]);

  const elegir = useCallback((id, modulo) => {
    setElecciones((actuales) => ({ ...actuales, [id]: modulo }));
  }, []);

  const archivos = useMemo(() => cambio?.archivos ?? [], [cambio]);

  // Cada archivo con su situación (revisar, confirmar, sin reglas…) y, si se revisa, lo que se manda al módulo.
  const filas = useMemo(() => archivos.map((archivo) => {
    const eleccion = elecciones[archivo.id];
    const modulo = moduloDe(archivo, eleccion);
    return {
      archivo,
      eleccion,
      situacion: situacion(archivo, eleccion),
      modulo,
      revision: modulo ? armarRevision(archivo, modulo, archivos) : null,
    };
  }), [archivos, elecciones]);

  const cuenta = useMemo(() => {
    const total = { revisar: 0, confirmar: 0, sinReglas: 0, otros: 0 };
    for (const fila of filas) {
      if (fila.situacion === 'revisar' && !fila.revision?.error) total.revisar += 1;
      else if (fila.situacion === 'confirmar') total.confirmar += 1;
      else if (fila.situacion === 'sinReglas') total.sinReglas += 1;
      else total.otros += 1;
    }
    return total;
  }, [filas]);

  /** Revisa uno por uno los archivos (con las mismas reglas del módulo) y pasa al resumen. */
  const revisar = useCallback(async () => {
    const porRevisar = filas.filter((fila) => fila.situacion === 'revisar' && fila.revision && !fila.revision.error);
    if (!porRevisar.length || cuenta.confirmar) return;
    const signal = nuevoControlador();
    setResultados(Object.fromEntries(porRevisar.map((fila) => [fila.archivo.id, { estado: 'revisando', revision: fila.revision }])));
    setPaso('resultado');

    for (const { archivo, revision } of porRevisar) {
      try {
        const datos = await analizarObjeto(construirSolicitud(revision.tipoRevision, revision.campos), { signal });
        const conteo = contarPorSeveridad(datos.hallazgos ?? []);
        const total = Object.values(conteo).reduce((suma, valor) => suma + valor, 0);
        setResultados((actuales) => ({ ...actuales, [archivo.id]: { estado: 'listo', conteo, total, revision } }));
      } catch (error) {
        if (esCancelacion(error)) return;
        setResultados((actuales) => ({ ...actuales, [archivo.id]: { estado: 'error', mensaje: error.message, revision } }));
      }
    }
  }, [filas, cuenta.confirmar, nuevoControlador]);

  const volverALista = useCallback(() => {
    cancelar();
    setPaso('lista');
  }, [cancelar]);

  const nuevoEnlace = useCallback(() => {
    cancelar();
    setCambio(null);
    setElecciones({});
    setResultados({});
    setEnlace('');
    setLectura({ estado: 'inicial', mensaje: '' });
    setPaso('enlace');
  }, [cancelar]);

  return {
    enlace, setEnlace, lectura, cambio, filas, cuenta, resultados, paso,
    leer, verEjemplo, elegir, revisar, volverALista, nuevoEnlace,
  };
}
