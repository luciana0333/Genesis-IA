import { useId, useRef, useState } from 'react';
import { Boton } from '../../components/Boton';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import {
  IconoBarras, IconoEjecutar, IconoHallazgo, IconoLimpiar, IconoMemoria, IconoNegocio, IconoRejilla, IconoReporte,
  IconoSeveridadMedia,
} from '../../components/Iconos';
import { PanelHallazgos } from '../../components/PanelHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { formatearKb } from '../../utils/hallazgos';
import { CapturaHallazgo } from './CapturaHallazgo';
import { DiagramaPlan } from './DiagramaPlan';
import { TiempoEjecucion } from './TiempoEjecucion';
import { TablaOperadores } from './TablaOperadores';
import { useLimitesTiempo } from './useLimitesTiempo';
import { usePlanEjecucion } from './usePlanEjecucion';
import { useAlPedirEjemplo } from '../../hooks/useVerEjemplo';

// Plan real de prueba que se analiza con "Ver ejemplo".
// Plan de prueba de cada área para «Ver ejemplo»: el de Reportes rompe todas sus reglas.
const PLANES_EJEMPLO = {
  reporte: 'plan-ejemplo-reportes.sqlplan',
  negocio: 'plan-ejemplo.sqlplan',
};
import { ZonaArchivo } from './ZonaArchivo';

// Cada área revisa sus planes con sus propias reglas (por ahora solo se elige en la interfaz).
const AREAS_PLAN = [
  { id: 'reporte', etiqueta: 'Reportes', icono: <IconoReporte /> },
  { id: 'negocio', etiqueta: 'Negocio', icono: <IconoNegocio /> },
];

// Reglas que revisa cada área (las de Reportes las definió la usuaria; Negocio aún usa las generales).
const REVISIONES_PLAN = {
  reporte: ['Conversión implícita detectada', 'Lectura residual elevada', 'Tiempo de ejecución superado'],
  negocio: ['Conversiones implícitas', 'Spills a TempDB', 'Table Scan', 'Lecturas lógicas', 'Cardinalidad', 'Memoria concedida'],
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
  const { archivo, analisis, aviso, cargando, seleccionarArchivo, limpiar, analizar, analizarEjemplo } = usePlanEjecucion(area, limites[area] ?? null);

  // Cambiar el límite vuelve a revisar el plan: la regla de tiempo depende de él.
  const alCambiarLimite = (areaLimite, valor) => {
    cambiarLimite(areaLimite, valor);
    if (analisis && archivo) analizar(archivo, areaLimite, valor);
  };

  const reiniciarInput = () => {
    // El valor de un <input type="file"> solo puede reiniciarse desde el DOM.
    if (inputArchivoRef.current) inputArchivoRef.current.value = '';
  };

  const alLimpiar = () => {
    reiniciarInput();
    limpiar();
  };

  const alQuitarArchivo = () => {
    reiniciarInput();
    seleccionarArchivo(null);
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

  const estadoPanel = cargando ? 'cargando' : analisis ? 'listo' : 'inicial';

  return (
    <section className="workspace" ref={workspaceRef}>
      <MetricasPlan analisis={analisis} />

      <section className="panel">
        <div className="panel-header">
          <EncabezadoSeccion
            etiqueta="Paso 1 · SQL Server ShowPlanXML"
            titulo="Revisión de plan de ejecución real"
            descripcion="Carga un plan real para detectar problemas de rendimiento con evidencia del motor."
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
                        if (analisis && archivo) analizar(archivo, opcion.id, limites[opcion.id] ?? null);
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
              etiqueta="Archivo .sqlplan"
              htmlFor={idArchivo}
              estado="Requerido"
              ayuda="Exporta el plan real desde SQL Server Management Studio o Plan Explorer."
            >
              <ZonaArchivo
                id={idArchivo}
                inputRef={inputArchivoRef}
                archivo={archivo}
                accept=".sqlplan,application/xml,text/xml"
                onSeleccionar={seleccionarArchivo}
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
                <Boton icono={<IconoEjecutar />} cargando={cargando} onClick={analizar}>Analizar plan</Boton>
                <Boton variante="secundario" icono={<IconoLimpiar />} onClick={alLimpiar}>Limpiar</Boton>
              </div>
              <p className={`status-line tono-${aviso.tono}`} role="status">{aviso.texto}</p>
            </TarjetaEditor>
          </div>
        </div>

        <div className="panel-footer">
          {/* El tiempo de ejecución va primero: es lo primero que se mira antes de las observaciones. */}
          {analisis?.diagrama?.length > 0 && (
            <TiempoEjecucion
              sentencias={analisis.diagrama}
              area={area}
              limiteS={limites[area] ?? null}
              onCambiarLimite={alCambiarLimite}
            />
          )}
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
                'Selecciona o arrastra tu archivo .sqlplan',
                'Presiona «Analizar plan»',
                'Revisa cada hallazgo y cómo corregirlo',
              ],
              cargando: 'Analizando el plan real...',
              sinHallazgos: 'El plan terminó sin hallazgos según las reglas activas.',
              tituloError: 'No se pudo analizar el plan',
            }}
          />
          {analisis?.diagrama?.length > 0 && <DiagramaPlan sentencias={analisis.diagrama} />}
          {analisis && <TablaOperadores operadores={analisis.operadores} />}
        </div>
      </section>
    </section>
  );
}
