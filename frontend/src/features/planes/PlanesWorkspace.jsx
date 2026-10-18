import { useId, useRef, useState } from 'react';
import { Boton } from '../../components/Boton';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import {
  IconoBarras, IconoComprimido, IconoEjecutar, IconoHallazgo, IconoLimpiar, IconoMemoria, IconoNegocio, IconoRejilla, IconoReporte,
  IconoSeveridadMedia,
} from '../../components/Iconos';
import { PanelHallazgos } from '../../components/PanelHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { formatearKb } from '../../utils/hallazgos';
import { CapturaHallazgo } from './CapturaHallazgo';
import { DiagramaPlan } from './DiagramaPlan';
import { MetricasLote, NavegacionLote, ResumenLote } from './ResumenLote';
import { ORDEN_INICIAL } from './ordenLote';
import { TiempoEjecucion } from './TiempoEjecucion';
import { TablaOperadores } from './TablaOperadores';
import { useLimitesTiempo } from './useLimitesTiempo';
import { EXTENSIONES_ACEPTADAS, esLote, usePlanEjecucion } from './usePlanEjecucion';
import { useAlPedirEjemplo } from '../../hooks/useVerEjemplo';

// Plan real de prueba que se analiza con "Ver ejemplo".
// Plan de prueba de cada área para «Ver ejemplo»: cada uno rompe todas las reglas de su área.
const PLANES_EJEMPLO = {
  reporte: 'plan-ejemplo-reportes.sqlplan',
  negocio: 'plan-ejemplo-negocio.sqlplan',
};
// Lote de ejemplo («Ejemplo de lote»): varios planes en carpetas dentro de un .zip.
const LOTE_EJEMPLO = 'lote-ejemplo.zip';
import { ZonaArchivo } from './ZonaArchivo';

// Cada área revisa sus planes con sus propias reglas (por ahora solo se elige en la interfaz).
const AREAS_PLAN = [
  { id: 'reporte', etiqueta: 'Reportes', icono: <IconoReporte /> },
  { id: 'negocio', etiqueta: 'Negocio', icono: <IconoNegocio /> },
];

// Reglas que revisa cada área (las definió la usuaria).
const REVISIONES_PLAN = {
  reporte: ['Conversión implícita detectada', 'Lectura residual elevada', 'Tiempo de ejecución superado'],
  negocio: ['Table Scan detectado', 'Conversión implícita detectada', 'Lectura residual elevada', 'Spill a TempDB', 'Sobreestimación de memoria', 'Tiempo de ejecución superado'],
};

function MetricasPlan({ analisis }) {
  const memoria = analisis?.memoria;
  const uso = memoria?.concedidaKb && memoria?.maximaUtilizadaKb
    ? Math.min(memoria.maximaUtilizadaKb / memoria.concedidaKb, 1)
    : undefined;
  return (
    <section className="metrics-grid" aria-label="Resumen del plan">
      <TarjetaMetrica
        titulo="Operadores"
        valor={analisis?.operadores?.length || 0}
        subtitulo="Nodos analizados"
        icono={<IconoRejilla />}
      />
      <TarjetaMetrica
        titulo="Memoria concedida"
        valor={formatearKb(memoria?.concedidaKb)}
        subtitulo="Reserva del plan"
        icono={<IconoMemoria />}
      />
      <TarjetaMetrica
        titulo="Memoria utilizada"
        valor={formatearKb(memoria?.maximaUtilizadaKb)}
        subtitulo={uso === undefined ? 'Máximo utilizado' : `Máximo utilizado · ${Math.round(uso * 100)}% de lo concedido`}
        icono={<IconoBarras />}
      />
      <TarjetaMetrica
        titulo="Hallazgos"
        valor={analisis?.hallazgos?.length || 0}
        subtitulo="Observaciones del plan"
        icono={<IconoHallazgo />}
      />
    </section>
  );
}

export function PlanesWorkspace() {
  const idArchivo = useId();
  const idArea = useId();
  const [area, setArea] = useState('reporte');
  const { limites, cambiarLimite } = useLimitesTiempo();
  const inputArchivoRef = useRef(null);
  const {
    archivos, analisis, lote, planElegido, elegirPlan, aviso, cargando,
    seleccionarArchivos, quitarArchivo, limpiar, analizar, analizarEjemplo,
  } = usePlanEjecucion(area, limites[area] ?? null);
  const [ordenLote, setOrdenLote] = useState(ORDEN_INICIAL);
  const hayResultado = Boolean(analisis || lote);
  const enResumenLote = Boolean(lote) && planElegido === null;

  // Cambiar el límite vuelve a revisar el plan (o el lote): la regla de tiempo depende de él.
  const alCambiarLimite = (areaLimite, valor) => {
    cambiarLimite(areaLimite, valor);
    if (hayResultado && archivos.length) analizar(archivos, areaLimite, valor);
  };

  const verPlan = (id) => {
    elegirPlan(id);
    workspaceRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  };

  const reiniciarInput = () => {
    // El valor de un <input type="file"> solo puede reiniciarse desde el DOM.
    if (inputArchivoRef.current) inputArchivoRef.current.value = '';
  };

  const alLimpiar = () => {
    reiniciarInput();
    limpiar();
  };

  const alQuitarArchivo = (indice) => {
    reiniciarInput();
    quitarArchivo(indice);
  };

  // "Ver ejemplo" del encabezado: solo responde cuando Planes está visible.
  const workspaceRef = useRef(null);
  useAlPedirEjemplo(async () => {
    if (!workspaceRef.current?.offsetParent) return;
    try {
      const nombre = PLANES_EJEMPLO[area] ?? PLANES_EJEMPLO.negocio;
      const respuesta = await fetch(`${import.meta.env.BASE_URL}ejemplos/${nombre}`);
      if (!respuesta.ok) throw new Error();
      const contenido = await respuesta.blob();
      reiniciarInput();
      analizarEjemplo(new File([contenido], nombre));
    } catch {
      // Sin ejemplo disponible: el usuario puede cargar su propio plan.
    }
  });

  // Ejemplo de lote: los planes de ejemplo de ambas áreas, comprimidos en un .zip.
  const verEjemploLote = async () => {
    try {
      const respuesta = await fetch(`${import.meta.env.BASE_URL}ejemplos/${LOTE_EJEMPLO}`);
      if (!respuesta.ok) throw new Error();
      const contenido = await respuesta.blob();
      reiniciarInput();
      analizarEjemplo([new File([contenido], LOTE_EJEMPLO)]);
    } catch {
      // Sin ejemplo disponible: el usuario puede cargar sus propios planes.
    }
  };

  const estadoPanel = cargando ? 'cargando' : analisis ? 'listo' : 'inicial';
  const variosArchivos = esLote(archivos);

  return (
    <section className="workspace" ref={workspaceRef}>
      {enResumenLote ? <MetricasLote lote={lote} /> : <MetricasPlan analisis={analisis} />}

      <section className="panel">
        <div className="panel-header">
          <EncabezadoSeccion
            etiqueta="Paso 1 · SQL Server ShowPlanXML"
            titulo="Revisión de plan de ejecución real"
            descripcion="Carga un plan real, o todos los del lote, para detectar problemas de rendimiento con evidencia del motor."
          />
        </div>

        <div className="panel-body">
          <div className="control-row control-row--area">
            <div className="field-group">
              <span className="field-label" id={idArea}>Área del plan de ejecución</span>
              <div className="selector-base" role="radiogroup" aria-labelledby={idArea}>
                {AREAS_PLAN.map((opcion) => (
                  <label key={opcion.id} className={area === opcion.id ? 'activa' : undefined}>
                    <input
                      type="radio"
                      name={idArea}
                      checked={area === opcion.id}
                      onChange={() => {
                        setArea(opcion.id);
                        // Con un plan ya analizado, se vuelve a revisar con las reglas de la nueva área.
                        if (hayResultado && archivos.length) analizar(archivos, opcion.id, limites[opcion.id] ?? null);
                      }}
                    />
                    {opcion.icono}
                    {opcion.etiqueta}
                  </label>
                ))}
              </div>
              <p className="nota-base nota-base--campo">
                <IconoSeveridadMedia />
                Cada área revisa su plan con sus propias reglas.
              </p>
            </div>
          </div>

          <div className="plan-layout">
            <TarjetaEditor
              className="field-card-primary"
              numero={1}
              etiqueta="Planes de ejecución"
              htmlFor={idArchivo}
              estado="Requerido"
              ayuda="Sube un plan .sqlplan, varios a la vez, una carpeta o el .zip / .rar del correo. Todos se revisan con las reglas del área elegida."
            >
              <ZonaArchivo
                id={idArchivo}
                inputRef={inputArchivoRef}
                archivos={archivos}
                accept={EXTENSIONES_ACEPTADAS.join(',')}
                multiple
                pista="Planes .sqlplan o comprimidos .zip / .rar · máximo 25 MB por plan"
                onSeleccionar={seleccionarArchivos}
                onQuitar={alQuitarArchivo}
              />
            </TarjetaEditor>

            <TarjetaEditor
              className="field-card-secondary"
              etiqueta="Diagnóstico técnico"
              estado="Automático"
              requerido={false}
              ayuda="Cada operador del plan se contrasta con estas reglas:"
            >
              <ul className="check-list">
                {(REVISIONES_PLAN[area] ?? REVISIONES_PLAN.negocio).map((revision) => <li key={revision}>{revision}</li>)}
              </ul>
              <div className="btn-group plan-actions">
                <Boton icono={<IconoEjecutar />} cargando={cargando} onClick={() => analizar()}>
                  {variosArchivos ? 'Analizar planes' : 'Analizar plan'}
                </Boton>
                <Boton variante="secundario" icono={<IconoLimpiar />} onClick={alLimpiar}>Limpiar</Boton>
                <Boton variante="fantasma" icono={<IconoComprimido />} onClick={verEjemploLote} disabled={cargando}>
                  Ejemplo de lote
                </Boton>
              </div>
              <p className={`status-line tono-${aviso.tono}`} role="status">{aviso.texto}</p>
            </TarjetaEditor>
          </div>
        </div>

        <div className="panel-footer">
          {enResumenLote && (
            <ResumenLote lote={lote} orden={ordenLote} onOrdenar={setOrdenLote} onVerPlan={verPlan} />
          )}
          {lote && !enResumenLote && (
            <NavegacionLote
              lote={lote}
              orden={ordenLote}
              planElegido={planElegido}
              onVerPlan={verPlan}
              onVolver={() => elegirPlan(null)}
            />
          )}
          {/* El tiempo de ejecución va primero: es lo primero que se mira antes de las observaciones. */}
          {analisis?.diagrama?.length > 0 && (
            <section className="tiempo-seccion">
              <EncabezadoSeccion
                nivel={3}
                etiqueta="Rendimiento"
                titulo="Tiempo de ejecución"
              />
              <TiempoEjecucion
                sentencias={analisis.diagrama}
                area={area}
                limiteS={limites[area] ?? null}
                onCambiarLimite={alCambiarLimite}
              />
            </section>
          )}
          {!enResumenLote && (
            <PanelHallazgos
              titulo="Hallazgos del plan"
              meta={analisis?.archivo}
              estado={estadoPanel}
              hallazgos={analisis?.hallazgos}
              mostrarLinea={false}
              accionesHallazgo={(hallazgo) => (
                <CapturaHallazgo hallazgo={hallazgo} sentencias={analisis?.diagrama} archivo={analisis?.archivo} />
              )}
              textos={{
                inicialTitulo: 'Listo para analizar tu plan',
                pasos: [
                  'Selecciona o arrastra tu plan .sqlplan, varios planes o un .zip / .rar',
                  'Presiona «Analizar plan»',
                  'Revisa cada hallazgo y cómo corregirlo',
                ],
                cargando: 'Analizando el plan real...',
                sinHallazgos: 'El plan terminó sin hallazgos según las reglas activas.',
                tituloError: 'No se pudo analizar el plan',
              }}
            />
          )}
          {analisis?.diagrama?.length > 0 && <DiagramaPlan sentencias={analisis.diagrama} />}
          {analisis && <TablaOperadores operadores={analisis.operadores} />}
        </div>
      </section>
    </section>
  );
}
