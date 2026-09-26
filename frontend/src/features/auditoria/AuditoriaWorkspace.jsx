import { useId } from 'react';
import { Boton } from '../../components/Boton';
import { EditorCodigo } from '../../components/EditorCodigo';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import { IconoEjecutar, IconoLimpiar, IconoRestaurar } from '../../components/Iconos';
import { PanelHallazgos } from '../../components/PanelHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { OPCIONES_SELECTOR } from '../../config/revisiones';
import { MetricasSeveridad } from './MetricasSeveridad';
import { detectarTipoDiccionario } from '../../utils/deteccionObjeto';
import { useAuditoria } from './useAuditoria';

function esAtajoEjecutar(evento) {
  return evento.key === 'Enter' && (evento.ctrlKey || evento.metaKey);
}

/**
 * Espacio de trabajo de las revisiones por reglas (Diccionarios, Tablas,
 * Reportes y Normales). Se monta una instancia por vista, así cada pestaña
 * arranca con su propio ejemplo y sin resultados de otra.
 */
export function AuditoriaWorkspace({ vista }) {
  const ids = useId();
  const {
    tipoRevision,
    revision,
    campos,
    resultado,
    conteo,
    actualizarCampo,
    cambiarTipo,
    ajustarTipo,
    restaurarEjemplo,
    limpiar,
    revisar,
  } = useAuditoria(vista.tipoRevision);

  const esSelectorVisible = vista.id === 'diccionario';

  // En Diccionarios el tipo se ajusta solo según el SQL pegado (tabla o
  // procedimiento), para que nunca se apliquen las reglas equivocadas.
  const alCambiarSql = (valor) => {
    actualizarCampo('sqlObject', valor);
    if (!esSelectorVisible) return;
    const detectado = detectarTipoDiccionario(valor);
    if (detectado && detectado !== tipoRevision) ajustarTipo(detectado);
  };
  const tieneDiccionario = Boolean(revision.diccionario);
  const cargando = resultado.estado === 'cargando';

  const alEnviar = (evento) => {
    evento.preventDefault();
    if (!cargando) revisar();
  };

  const alPresionarTecla = (evento) => {
    if (esAtajoEjecutar(evento)) evento.currentTarget.requestSubmit();
  };

  return (
    <section className="workspace">
      <MetricasSeveridad conteo={conteo} subtitulos={vista.resultados.subtitulos} />

      <section className="panel">
        <div className="panel-header">
          <EncabezadoSeccion
            etiqueta="Paso 1 · Configuración"
            titulo="Configuración de la auditoría"
            descripcion={`Pega el código del objeto y ejecuta las reglas de ${vista.resultados.nombre.toLowerCase()}.`}
          />
        </div>

        <form className="panel-body" onSubmit={alEnviar} onKeyDown={alPresionarTecla} noValidate>
          <div className="control-row">
            {esSelectorVisible && (
              <div className="field-group">
                <label className="field-label" htmlFor={`${ids}-tipo`}>Tipo de revisión</label>
                <select id={`${ids}-tipo`} value={tipoRevision} onChange={(evento) => cambiarTipo(evento.target.value)}>
                  {OPCIONES_SELECTOR.map((opcion) => (
                    <option key={opcion.id} value={opcion.id}>{opcion.etiquetaSelector}</option>
                  ))}
                </select>
                <p className="field-note">Se ajusta solo según el SQL que pegues.</p>
              </div>
            )}

            <div className="field-group">
              <label className="field-label" htmlFor={`${ids}-objeto`}>{revision.etiquetaObjeto}</label>
              <input
                id={`${ids}-objeto`}
                type="text"
                autoComplete="off"
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
              className={tieneDiccionario ? 'field-card-primary' : 'field-card-primary field-card-full'}
              kicker="Entrada principal"
              etiqueta={revision.sql.etiqueta}
              htmlFor={`${ids}-sql`}
              estado="Requerido"
              ayuda={revision.sql.ayuda}
              acciones={
                <button type="button" className="link-btn" onClick={restaurarEjemplo} title="Volver a cargar el script de ejemplo">
                  <IconoRestaurar />
                  Restaurar ejemplo
                </button>
              }
            >
              <EditorCodigo
                id={`${ids}-sql`}
                valor={campos.sqlObject}
                onCambiar={alCambiarSql}
                placeholder="CREATE PROCEDURE ..."
              />
            </TarjetaEditor>

            {tieneDiccionario && (
              <TarjetaEditor
                className="field-card-secondary"
                kicker="Documentación"
                etiqueta={revision.diccionario.etiqueta}
                htmlFor={`${ids}-diccionario`}
                estado="Requerido"
                ayuda={
                  <>Pega aquí el script de <code>sp_addextendedproperty</code> para {revision.diccionario.objetivo}.</>
                }
              >
                <EditorCodigo
                  id={`${ids}-diccionario`}
                  valor={campos.dictScript}
                  onCambiar={(valor) => actualizarCampo('dictScript', valor)}
                  placeholder="EXEC sys.sp_addextendedproperty ..."
                />
              </TarjetaEditor>
            )}
          </div>

          <div className="action-bar">
            <div className="btn-group">
              <Boton type="submit" icono={<IconoEjecutar />} cargando={cargando}>Ejecutar revisión</Boton>
              <Boton variante="secundario" icono={<IconoLimpiar />} onClick={limpiar}>Limpiar</Boton>
            </div>
            <p className="shortcut-hint"><kbd>Ctrl</kbd> + <kbd>Enter</kbd> para ejecutar</p>
          </div>
        </form>

        <div className="panel-footer">
          <PanelHallazgos
            titulo={vista.resultados.titulo}
            estado={resultado.estado}
            hallazgos={resultado.hallazgos}
            mensajeError={resultado.mensaje}
            origenPorDefecto="reglas_estaticas"
            textos={{
              inicial: 'Presiona "Ejecutar revisión" para analizar el objeto.',
              cargando: `Analizando las reglas de ${vista.resultados.nombre}...`,
              sinHallazgos: 'La revisión terminó sin hallazgos.',
              tituloError: 'No se pudo completar la revisión',
            }}
          />
        </div>
      </section>
    </section>
  );
}
