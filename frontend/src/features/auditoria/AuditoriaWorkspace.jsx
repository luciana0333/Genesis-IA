import { useId } from 'react';
import { ListaHallazgos } from '../../components/ListaHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { OPCIONES_SELECTOR } from '../../config/revisiones';
import { buscarVistaDedicada } from '../../config/vistas';
import { MetricasSeveridad } from './MetricasSeveridad';
import { useAuditoria } from './useAuditoria';

function mensajeResultados(resultado, nombreRevision) {
  switch (resultado.estado) {
    case 'cargando':
      return `Analizando las reglas de ${nombreRevision}...`;
    case 'listo':
      return 'La revisión terminó sin hallazgos.';
    case 'error':
      return resultado.mensaje;
    default:
      return (
        <>Aún no hay resultados. Presiona <strong>&quot;Ejecutar revisión&quot;</strong> para analizar el objeto.</>
      );
  }
}

/**
 * Espacio de trabajo de las revisiones por reglas (Diccionarios, Tablas,
 * Reportes y Normales). Se monta una instancia por vista, así cada pestaña
 * arranca con su propio ejemplo y sin resultados de otra.
 */
export function AuditoriaWorkspace({ vista, onNavegar }) {
  const ids = useId();
  const {
    tipoRevision,
    revision,
    campos,
    resultado,
    conteo,
    actualizarCampo,
    cambiarTipo,
    limpiar,
    revisar,
  } = useAuditoria(vista.tipoRevision);

  const esSelectorVisible = vista.id === 'diccionario';
  const tieneDiccionario = Boolean(revision.diccionario);
  const cargando = resultado.estado === 'cargando';

  const alCambiarTipo = (evento) => {
    const nuevoTipo = evento.target.value;
    const vistaDedicada = buscarVistaDedicada(nuevoTipo);
    if (vistaDedicada) {
      onNavegar(vistaDedicada);
      return;
    }
    cambiarTipo(nuevoTipo);
  };

  const alEnviar = (evento) => {
    evento.preventDefault();
    revisar();
  };

  return (
    <section>
      <MetricasSeveridad conteo={conteo} subtitulos={vista.resultados.subtitulos} />

      <section className="form-container">
        <div className="section-title">
          <h2>Configuración de la Auditoría</h2>
          <div className="title-line" />
        </div>

        <form onSubmit={alEnviar} noValidate>
          <div className="control-row">
            {esSelectorVisible && (
              <div className="field-group revision-type-field">
                <label htmlFor={`${ids}-tipo`}>Tipo de revisión</label>
                <select id={`${ids}-tipo`} value={tipoRevision} onChange={alCambiarTipo}>
                  {OPCIONES_SELECTOR.map((opcion) => (
                    <option key={opcion.id} value={opcion.id}>{opcion.etiquetaSelector}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="field-group">
              <label htmlFor={`${ids}-objeto`}>{revision.etiquetaObjeto}</label>
              <input
                id={`${ids}-objeto`}
                type="text"
                value={campos.objetoNombre}
                onChange={(evento) => actualizarCampo('objetoNombre', evento.target.value)}
              />
            </div>

            {revision.permiteDbcmaica && (
              <label className="checkbox-field" htmlFor={`${ids}-dbcmaica`}>
                <input
                  id={`${ids}-dbcmaica`}
                  type="checkbox"
                  checked={campos.esDbcmaica}
                  onChange={(evento) => actualizarCampo('esDbcmaica', evento.target.checked)}
                />
                <span>La tabla pertenece a DBCMAICA y puede omitir COLLATE</span>
              </label>
            )}
          </div>

          <div className="editor-grid">
            <TarjetaEditor
              className={tieneDiccionario ? 'table-editor-card' : 'table-editor-card editor-card--completo'}
              kicker="Entrada principal"
              etiqueta={revision.sql.etiqueta}
              htmlFor={`${ids}-sql`}
              estado="Requerido"
              ayuda={revision.sql.ayuda}
            >
              <textarea
                id={`${ids}-sql`}
                rows={10}
                spellCheck={false}
                value={campos.sqlObject}
                onChange={(evento) => actualizarCampo('sqlObject', evento.target.value)}
              />
            </TarjetaEditor>

            {tieneDiccionario && (
              <TarjetaEditor
                className="dictionary-editor-card"
                kicker="Documentación"
                etiqueta={revision.diccionario.etiqueta}
                htmlFor={`${ids}-diccionario`}
                estado="Opcional"
                requerido={false}
                ayuda={
                  <>Pega aquí el script de <code>sp_addextendedproperty</code> para {revision.diccionario.objetivo}.</>
                }
              >
                <textarea
                  id={`${ids}-diccionario`}
                  rows={10}
                  spellCheck={false}
                  value={campos.dictScript}
                  onChange={(evento) => actualizarCampo('dictScript', evento.target.value)}
                />
              </TarjetaEditor>
            )}
          </div>

          <div className="btn-group">
            <button className="btn-primary" type="submit" disabled={cargando}>Ejecutar revisión</button>
            <button className="btn-secondary" type="button" onClick={limpiar}>Limpiar</button>
          </div>
        </form>

        <section className="results-panel" aria-live="polite" aria-busy={cargando}>
          <div className="results-header">
            <h3>{vista.resultados.titulo}</h3>
          </div>
          <ListaHallazgos
            hallazgos={resultado.hallazgos}
            mensajeVacio={mensajeResultados(resultado, vista.resultados.nombre)}
            origenPorDefecto="reglas_estaticas"
          />
        </section>
      </section>
    </section>
  );
}
