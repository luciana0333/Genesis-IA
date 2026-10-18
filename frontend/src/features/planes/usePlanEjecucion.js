import { useCallback, useState } from 'react';
import { analizarPlan, analizarPlanes, esCancelacion } from '../../api/cliente';
import { useSolicitudCancelable } from '../../hooks/useSolicitudCancelable';

const EXTENSION_PLAN = '.sqlplan';
// Lo que se puede subir: planes sueltos o comprimidos tal como llegan en el correo.
export const EXTENSIONES_ACEPTADAS = ['.sqlplan', '.xml', '.zip', '.rar'];
const MAXIMO_LOTE_MB = 200;
const SIN_AVISO = { texto: '', tono: 'info' };

const extensionDe = (archivo) => {
  const nombre = archivo.name.toLowerCase();
  return EXTENSIONES_ACEPTADAS.find((extension) => nombre.endsWith(extension));
};

/** Un solo .sqlplan se revisa como siempre; varios archivos, un .xml, .zip o .rar van por lote. */
export const esLote = (archivos) => archivos.length > 1
  || (archivos.length === 1 && extensionDe(archivos[0]) !== EXTENSION_PLAN);

const huella = (archivo) => `${archivo.rutaRelativa || archivo.name}|${archivo.size}|${archivo.lastModified}`;

/**
 * Estado y acciones del análisis de planes de ejecución.
 *
 * - Un .sqlplan: `analisis` es la respuesta de /api/analizar-plan.
 * - Lote: `lote` es la respuesta de /api/analizar-planes y `analisis` es el del
 *   plan que se está viendo en detalle (`planElegido`), o null en el resumen.
 * `aviso` es el mensaje de estado bajo los botones: { texto, tono: info | exito | error }.
 */
export function usePlanEjecucion(area, limite = null) {
  const [archivos, setArchivos] = useState([]);
  const [analisisSuelto, setAnalisisSuelto] = useState(null);
  const [lote, setLote] = useState(null);
  const [planElegido, setPlanElegido] = useState(null);
  const [aviso, setAviso] = useState(SIN_AVISO);
  const [cargando, setCargando] = useState(false);
  const { ejecutar, cancelar } = useSolicitudCancelable();

  /**
   * Nueva selección (reemplaza la anterior, como hasta ahora), sin repetir ni aceptar otros tipos.
   * Con `agregar` se suman a los ya elegidos.
   */
  const seleccionarArchivos = useCallback((nuevos, { agregar = false } = {}) => {
    const lista = Array.from(nuevos ?? []);
    const validos = lista.filter(extensionDe);
    const rechazados = lista.length - validos.length;
    setArchivos((actuales) => {
      const base = agregar ? actuales : [];
      const vistos = new Set(base.map(huella));
      return [...base, ...validos.filter((archivo) => !vistos.has(huella(archivo)) && vistos.add(huella(archivo)))];
    });
    setAviso(rechazados
      ? {
        texto: `Se dejaron fuera ${rechazados} archivo${rechazados === 1 ? '' : 's'}: solo se aceptan .sqlplan, .xml, .zip y .rar.`,
        tono: 'error',
      }
      : SIN_AVISO);
  }, []);

  const quitarArchivo = useCallback((indice) => {
    setArchivos((actuales) => actuales.filter((_, posicion) => posicion !== indice));
    setAviso(SIN_AVISO);
  }, []);

  const limpiar = useCallback(() => {
    cancelar();
    setCargando(false);
    setArchivos([]);
    setAnalisisSuelto(null);
    setLote(null);
    setPlanElegido(null);
    setAviso(SIN_AVISO);
  }, [cancelar]);

  /**
   * Analiza los archivos elegidos, o los indicados (p. ej. el plan de ejemplo), con
   * las reglas del área y su límite de tiempo (o los indicados, al cambiarlos).
   * Al volver a revisar un lote se mantiene el plan que se estaba viendo.
   */
  const analizar = useCallback(async (archivosIndicados, areaIndicada, limiteIndicado) => {
    const planes = Array.isArray(archivosIndicados) ? archivosIndicados : archivos;
    if (!planes.length) {
      setAviso({ texto: 'Selecciona un plan .sqlplan, varios planes o un .zip / .rar.', tono: 'error' });
      return;
    }
    const opciones = {
      area: areaIndicada ?? area,
      limite: limiteIndicado !== undefined ? limiteIndicado : limite,
    };

    if (!esLote(planes)) {
      setCargando(true);
      setAviso({ texto: 'Analizando el plan real...', tono: 'info' });
      try {
        const datos = await ejecutar((signal) => analizarPlan(planes[0], { signal, ...opciones }));
        setLote(null);
        setPlanElegido(null);
        setAnalisisSuelto(datos);
        setAviso({ texto: 'Análisis completado.', tono: 'exito' });
      } catch (error) {
        if (esCancelacion(error)) return;
        setAnalisisSuelto(null);
        setAviso({ texto: error.message, tono: 'error' });
      }
      setCargando(false);
      return;
    }

    const totalMb = planes.reduce((suma, archivo) => suma + archivo.size, 0) / (1024 * 1024);
    if (totalMb > MAXIMO_LOTE_MB) {
      setAviso({ texto: `Los archivos suman ${Math.round(totalMb)} MB; el máximo por lote es ${MAXIMO_LOTE_MB} MB.`, tono: 'error' });
      return;
    }
    setCargando(true);
    setAviso({ texto: 'Abriendo los archivos y analizando cada plan...', tono: 'info' });
    try {
      const datos = await ejecutar((signal) => analizarPlanes(planes, { signal, ...opciones }));
      setAnalisisSuelto(null);
      setLote(datos);
      // Si el comprimido traía un solo plan, se abre directo su detalle.
      setPlanElegido((anterior) => {
        if (anterior !== null && datos.planes.some((plan) => plan.id === anterior)) return anterior;
        return datos.planes.length === 1 && !datos.planes[0].error ? datos.planes[0].id : null;
      });
      const { planes: leidos, conError } = datos.totales;
      const partes = [`${leidos} plan${leidos === 1 ? '' : 'es'} analizado${leidos === 1 ? '' : 's'}`];
      if (conError) partes.push(`${conError} dañado${conError === 1 ? '' : 's'}`);
      if (datos.ignorados.length) partes.push(`${datos.ignorados.length} archivo${datos.ignorados.length === 1 ? '' : 's'} sin revisar`);
      setAviso({ texto: `${partes.join(' · ')}.`, tono: 'exito' });
    } catch (error) {
      if (esCancelacion(error)) return;
      setLote(null);
      setPlanElegido(null);
      setAviso({ texto: error.message, tono: 'error' });
    }
    setCargando(false);
  }, [archivos, area, limite, ejecutar]);

  /** Elige el plan de ejemplo (o el lote de ejemplo) y lo analiza ("Ver ejemplo"). */
  const analizarEjemplo = useCallback((ejemplo) => {
    const lista = Array.isArray(ejemplo) ? ejemplo : [ejemplo];
    setArchivos(lista);
    setPlanElegido(null);
    analizar(lista);
  }, [analizar]);

  const planDelLote = lote && planElegido !== null ? lote.planes.find((plan) => plan.id === planElegido) : null;
  const analisis = lote ? (planDelLote?.analisis ?? null) : analisisSuelto;

  return {
    archivos,
    analisis,
    lote,
    planElegido,
    elegirPlan: setPlanElegido,
    aviso,
    cargando,
    seleccionarArchivos,
    quitarArchivo,
    limpiar,
    analizar,
    analizarEjemplo,
  };
}
