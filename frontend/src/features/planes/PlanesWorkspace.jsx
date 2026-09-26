import { useId, useRef } from 'react';
import { IconoBarras, IconoHallazgo, IconoMemoria, IconoRejilla } from '../../components/Iconos';
import { ListaHallazgos } from '../../components/ListaHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { formatearKb } from '../../utils/hallazgos';
import { usePlanEjecucion } from './usePlanEjecucion';

function MetricasPlan({ analisis }) {
  const memoria = analisis?.memoria;
  return (
    <section className="services-grid plan-summary-grid" aria-label="Resumen del plan">
      <TarjetaMetrica
        variante="critical"
        titulo="Operadores"
        valor={analisis?.operadores?.length || 0}
        subtitulo="Nodos analizados"
        icono={<IconoRejilla />}
      />
      <TarjetaMetrica
        variante="high"
        titulo="Memoria concedida"
        valor={formatearKb(memoria?.concedidaKb)}
        subtitulo="Reserva del plan"
        icono={<IconoMemoria />}
      />
      <TarjetaMetrica
        variante="medium"
        titulo="Memoria utilizada"
        valor={formatearKb(memoria?.maximaUtilizadaKb)}
        subtitulo="Máximo utilizado"
        icono={<IconoBarras />}
      />
      <TarjetaMetrica
        variante="low"
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
  const { archivo, analisis, estado, cargando, seleccionarArchivo, limpiar, analizar } = usePlanEjecucion();

  const alLimpiar = () => {
    // El valor de un <input type="file"> solo puede reiniciarse desde el DOM.
    if (inputArchivoRef.current) inputArchivoRef.current.value = '';
    limpiar();
  };

  const mensajeVacio = analisis
    ? 'El plan terminó sin hallazgos según las reglas activas.'
    : 'Selecciona un archivo .sqlplan para iniciar el análisis.';

  return (
    <section className="plan-workspace-panel">
      <MetricasPlan analisis={analisis} />

      <section className="form-container plan-form-container">
        <div className="section-title">
          <span className="editor-kicker">SQL Server ShowPlanXML</span>
          <h2>Revisión de plan de ejecución real</h2>
          <div className="title-line" />
        </div>

        <div className="plan-upload-layout">
          <TarjetaEditor
            className="plan-upload-card"
            kicker="Entrada principal"
            etiqueta="Archivo .sqlplan"
            htmlFor={idArchivo}
            estado="Requerido"
            ayuda="Carga el plan real exportado desde SQL Server o Plan Explorer."
          >
            <input
              ref={inputArchivoRef}
              id={idArchivo}
              type="file"
              accept=".sqlplan,application/xml,text/xml"
              onChange={(evento) => seleccionarArchivo(evento.target.files?.[0])}
            />
            <span className="plan-file-name">{archivo?.name || 'Ningún archivo seleccionado'}</span>
          </TarjetaEditor>

          <TarjetaEditor
            className="plan-actions-card"
            kicker="Análisis profesional"
            etiqueta="Diagnóstico técnico"
            estado="Automático"
            requerido={false}
            ayuda="Se revisan conversiones implícitas, spills, scans, lecturas, cardinalidad y memoria concedida."
          >
            <div className="btn-group plan-btn-group">
              <button className="btn-primary" type="button" onClick={analizar} disabled={cargando}>
                Analizar plan
              </button>
              <button className="btn-secondary" type="button" onClick={alLimpiar}>Limpiar</button>
            </div>
            <p className="plan-status" role="status">{estado}</p>
          </TarjetaEditor>
        </div>

        <section className="plan-results-panel" aria-live="polite" aria-busy={cargando}>
          <div className="results-header">
            <h3>Hallazgos del plan</h3>
            <span className="finding-meta">{analisis?.archivo || ''}</span>
          </div>
          <ListaHallazgos
            hallazgos={analisis?.hallazgos}
            mensajeVacio={mensajeVacio}
            origenPorDefecto="plan_ejecucion"
          />
        </section>
      </section>
    </section>
  );
}
