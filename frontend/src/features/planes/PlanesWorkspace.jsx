import { useId, useRef } from 'react';
import { Boton } from '../../components/Boton';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import { IconoBarras, IconoEjecutar, IconoHallazgo, IconoLimpiar, IconoMemoria, IconoRejilla } from '../../components/Iconos';
import { PanelHallazgos } from '../../components/PanelHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { formatearKb } from '../../utils/hallazgos';
import { TablaOperadores } from './TablaOperadores';
import { usePlanEjecucion } from './usePlanEjecucion';
import { useAlPedirEjemplo } from '../../hooks/useVerEjemplo';

// Plan real de prueba que se analiza con "Ver ejemplo".
const PLAN_EJEMPLO = `${import.meta.env.BASE_URL}ejemplos/plan-ejemplo.sqlplan`;
import { ZonaArchivo } from './ZonaArchivo';

const REVISIONES_PLAN = ['Conversiones implícitas', 'Spills a TempDB', 'Table Scan', 'Lecturas lógicas', 'Cardinalidad', 'Memoria concedida'];

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
  const inputArchivoRef = useRef(null);
  const { archivo, analisis, aviso, cargando, seleccionarArchivo, limpiar, analizar, analizarEjemplo } = usePlanEjecucion();

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
      const respuesta = await fetch(PLAN_EJEMPLO);
      if (!respuesta.ok) throw new Error();
      const contenido = await respuesta.blob();
      reiniciarInput();
      analizarEjemplo(new File([contenido], 'plan-ejemplo.sqlplan'));
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
          <div className="plan-layout">
            <TarjetaEditor
              className="field-card-primary"
              kicker="Entrada principal"
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
              kicker="Análisis profesional"
              etiqueta="Diagnóstico técnico"
              estado="Automático"
              requerido={false}
              ayuda="Cada operador del plan se contrasta con estas reglas:"
            >
              <ul className="check-list">
                {REVISIONES_PLAN.map((revision) => <li key={revision}>{revision}</li>)}
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
          <PanelHallazgos
            titulo="Hallazgos del plan"
            meta={analisis?.archivo}
            estado={estadoPanel}
            hallazgos={analisis?.hallazgos}
            mostrarLinea={false}
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
          {analisis && <TablaOperadores operadores={analisis.operadores} />}
        </div>
      </section>
    </section>
  );
}
