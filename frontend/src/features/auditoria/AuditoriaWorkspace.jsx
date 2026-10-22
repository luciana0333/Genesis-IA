import { useCallback, useId, useRef, useState } from 'react';
import { Boton } from '../../components/Boton';
import { EditorCodigo } from '../../components/EditorCodigo';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import {
  IconoAgregar, IconoBaseDatos, IconoCerrar, IconoEjecutar, IconoGlobo, IconoLimpiar, IconoMotor, IconoNegocio,
  IconoRestaurar, IconoSeveridadMedia,
} from '../../components/Iconos';
import { PanelHallazgos } from '../../components/PanelHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { OPCIONES_SELECTOR } from '../../config/revisiones';
import { AvisoFaltaDiccionario } from './AvisoFaltaDiccionario';
import { BarraRecorrido, VerEnCodigo } from './VerEnCodigo';
import { nombreRegla } from '../../config/reglas';
import { GeneradorDiccionario } from './GeneradorDiccionario';
import { MetricasSeveridad } from './MetricasSeveridad';
import { detectarTipoDiccionario, extraerNombreObjeto } from '../../utils/deteccionObjeto';
import { useAuditoria } from './useAuditoria';
import { useAlPedirEjemplo } from '../../hooks/useVerEjemplo';

// Observaciones de «falta documentar»: la primera presente ofrece el script del diccionario faltante.
const REGLAS_DICCIONARIO_FALTANTE = [
  'TABLA_SIN_DESCRIPCION',
  'PROCEDIMIENTO_SIN_DESCRIPCION',
  'COLUMNA_FALTANTE',
  'PARAMETRO_FALTANTE',
];

function esAtajoEjecutar(evento) {
  return evento.key === 'Enter' && (evento.ctrlKey || evento.metaKey);
}

/**
 * Espacio de trabajo de las revisiones por reglas (Diccionarios, Tablas,
 * Reportes y Procedimientos). Se monta una instancia por vista, así cada pestaña
 * arranca con su propio ejemplo y sin resultados de otra.
 */
export function AuditoriaWorkspace({ vista }) {
  const ids = useId();
  // «Ver» del resumen por severidad baja hasta los resultados.
  const resultadosRef = useRef(null);
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
    revisarEjemplo,
  } = useAuditoria(vista.tipoRevision);

  // "Ver ejemplo" del encabezado: carga el ejemplo y lo revisa.
  useAlPedirEjemplo(revisarEjemplo);

  const esSelectorVisible = vista.id === 'diccionario';

  // En Diccionarios el tipo se ajusta solo según el SQL pegado (tabla o
  // procedimiento), para que nunca se apliquen las reglas equivocadas.
  const alCambiarSql = (valor) => {
    actualizarCampo('sqlObject', valor);
    // El nombre se completa con el del CREATE/ALTER pegado, salvo que el
    // usuario lo haya escrito a mano (distinto del que traía el SQL anterior).
    const nombreSql = extraerNombreObjeto(valor);
    const nombreAnterior = extraerNombreObjeto(campos.sqlObject);
    const nombreEsAutomatico = !campos.objetoNombre.trim() || campos.objetoNombre === nombreAnterior;
    if (nombreSql && nombreEsAutomatico && nombreSql !== campos.objetoNombre) actualizarCampo('objetoNombre', nombreSql);
    if (!esSelectorVisible) return;
    const detectado = detectarTipoDiccionario(valor);
    if (detectado && detectado !== tipoRevision) ajustarTipo(detectado);
  };
  const tieneDiccionario = Boolean(revision.diccionario);
  const tieneIndices = Boolean(revision.indices);
  // La cajita de índices está plegada: se abre con «Agregar índices» o si ya trae código.
  const [indicesAbiertos, setIndicesAbiertos] = useState(false);
  const mostrarIndices = tieneIndices && (indicesAbiertos || Boolean((campos.indicesScript ?? '').trim()));
  const quitarIndices = () => {
    actualizarCampo('indicesScript', '');
    setIndicesAbiertos(false);
  };
  const contarLineas = (texto = '') => (texto.trim() ? texto.split('\n').length : 0);
  const lineasSql = contarLineas(campos.sqlObject);
  const lineasDiccionario = tieneDiccionario ? contarLineas(campos.dictScript) : 0;
  const lineasIndices = tieneIndices ? contarLineas(campos.indicesScript) : 0;
  const hayCodigo = lineasSql > 0 || lineasIndices > 0;
  const lineasSegunda = tieneDiccionario ? lineasDiccionario : lineasIndices;
  const resumenLineas = lineasSql && lineasSegunda ? `${lineasSql} + ${lineasSegunda} líneas` : `${lineasSql || lineasSegunda} líneas`;
  const cargando = resultado.estado === 'cargando';
  // Ventana «Falta el diccionario»: se pegó el objeto pero no su documentación.
  const [avisoDiccionario, setAvisoDiccionario] = useState(false);

  const alEnviar = (evento) => {
    evento.preventDefault();
    if (cargando) return;
    if (tieneDiccionario && campos.sqlObject.trim() && !campos.dictScript.trim()) {
      setAvisoDiccionario(true);
      return;
    }
    revisar();
  };

  const cerrarAviso = useCallback(() => setAvisoDiccionario(false), []);

  // El script del diccionario faltante se ofrece una sola vez, en la primera observación de «falta documentar».
  const faltante = resultado.diccionarioFaltante;
  const reglaConScript = faltante
    && REGLAS_DICCIONARIO_FALTANTE.find((regla) => resultado.hallazgos.some((hallazgo) => hallazgo.regla === regla));
  // «Ver en el código» (Diccionarios, Tablas y procedimientos): cajita y líneas marcadas en rojo.
  // La marca vale solo para el resultado en el que se pidió (una revisión nueva la quita).
  const [marcaPedida, setMarca] = useState(null);
  const marca = marcaPedida?.resultado === resultado ? marcaPedida : null;
  // Cajita de la línea de cada observación: sin sección es el código principal; «general» no apunta a una línea.
  const CAJITAS = { objeto: 'objeto', diccionario: 'diccionario', indices: 'indices' };
  const verEnCodigo = (seccion, lineas, recorrido = null) => {
    // La clave cambia en cada clic, para volver a llevar a la línea aunque sea la misma.
    setMarca((anterior) => ({ seccion, lineas, resultado, recorrido, indice: 0, clave: (anterior?.clave ?? 0) + 1 }));
  };
  // Recorrer una a una las líneas de la observación (barra flotante «4 de 20 ‹ ›»).
  const irALinea = (paso) => {
    setMarca((anterior) => anterior && ({
      ...anterior,
      indice: (anterior.indice + paso + anterior.lineas.length) % anterior.lineas.length,
      clave: anterior.clave + 1,
    }));
  };
  const botonVerEnCodigo = (hallazgo) => {
    const seccion = hallazgo.seccion ? CAJITAS[hallazgo.seccion] : 'objeto';
    if (!seccion || !hallazgo.linea) return null;
    const lineas = hallazgo.lineas?.length ? hallazgo.lineas : [hallazgo.linea];
    // Con varias líneas, la barra «1 de N ‹ ›» permite ir de un error al otro.
    const recorrido = lineas.length > 1 ? nombreRegla(hallazgo.regla) : null;
    return <VerEnCodigo onVer={() => verEnCodigo(seccion, lineas, recorrido)} />;
  };
  const marcadasEn = (seccion) => (marca?.seccion === seccion ? marca.lineas : []);
  const enfocarEn = (seccion) => (
    marca?.seccion === seccion ? { linea: marca.lineas[marca.indice], clave: marca.clave } : null
  );
  const accionesHallazgo = (hallazgo) => (
    <>
      {botonVerEnCodigo(hallazgo)}
      {reglaConScript && hallazgo.regla === reglaConScript && <GeneradorDiccionario faltante={faltante} />}
    </>
  );
  const anadirDiccionario = () => {
    setAvisoDiccionario(false);
    const editor = document.getElementById(`${ids}-diccionario`);
    editor?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    editor?.focus();
  };
  const revisarSinDiccionario = () => {
    setAvisoDiccionario(false);
    revisar(campos, { sinDiccionario: true });
  };

  const alPresionarTecla = (evento) => {
    if (esAtajoEjecutar(evento)) evento.currentTarget.requestSubmit();
  };

  return (
    <section className="workspace">
      <MetricasSeveridad
        conteo={conteo}
        subtitulos={vista.resultados.subtitulos}
        onVerHallazgos={() => resultadosRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
      />

      <section className="panel">
        <div className="panel-header">
          <EncabezadoSeccion
            etiqueta="Paso 1 · Configuración"
            titulo="Configuración de la auditoría"
            descripcion={`Pega el código del objeto y ejecuta las reglas de ${vista.resultados.nombre.toLowerCase()}.`}
          />
        </div>

        <form className="panel-body" onSubmit={alEnviar} onKeyDown={alPresionarTecla} noValidate>
          <div className={revision.permiteDbcmaica || revision.permiteMotor ? 'control-row control-row--base' : 'control-row'}>
            {esSelectorVisible && (
              <div className="field-group">
                <label className="field-label" htmlFor={`${ids}-tipo`}>Tipo de revisión</label>
                <select className="campo-icono campo-icono-tipo" id={`${ids}-tipo`} value={tipoRevision} onChange={(evento) => cambiarTipo(evento.target.value)}>
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
                className="campo-icono campo-icono-nombre"
                type="text"
                autoComplete="off"
                value={campos.objetoNombre}
                onChange={(evento) => actualizarCampo('objetoNombre', evento.target.value)}
              />
            </div>

            {revision.permiteDbcmaica && (
              <div className="field-group">
                <span className="field-label" id={`${ids}-base`}>Base de datos</span>
                <div className="selector-base" role="radiogroup" aria-labelledby={`${ids}-base`}>
                  {[
                    { valor: false, etiqueta: 'Otra base de datos', icono: <IconoGlobo /> },
                    { valor: true, etiqueta: 'DBCMAICA', icono: <IconoBaseDatos /> },
                  ].map((opcion) => (
                    <label key={opcion.etiqueta} className={campos.esDbcmaica === opcion.valor ? 'activa' : undefined}>
                      <input
                        type="radio"
                        name={`${ids}-base`}
                        checked={campos.esDbcmaica === opcion.valor}
                        onChange={() => actualizarCampo('esDbcmaica', opcion.valor)}
                      />
                      {opcion.icono}
                      {opcion.etiqueta}
                    </label>
                  ))}
                </div>
              </div>
            )}

            {revision.permiteDbcmaica && (
              <p className="nota-base">
                <IconoSeveridadMedia />
                En DBCMAICA las columnas de texto pueden omitir COLLATE.
              </p>
            )}

            {revision.permiteMotor && (
              <div className="field-group">
                <span className="field-label" id={`${ids}-motor`}>Tipo de procedimiento</span>
                <div className="selector-base" role="radiogroup" aria-labelledby={`${ids}-motor`}>
                  {[
                    { valor: false, etiqueta: 'De negocio', icono: <IconoNegocio /> },
                    { valor: true, etiqueta: 'Del motor', icono: <IconoMotor /> },
                  ].map((opcion) => (
                    <label key={opcion.etiqueta} className={Boolean(campos.esDelMotor) === opcion.valor ? 'activa' : undefined}>
                      <input
                        type="radio"
                        name={`${ids}-motor`}
                        checked={Boolean(campos.esDelMotor) === opcion.valor}
                        onChange={() => actualizarCampo('esDelMotor', opcion.valor)}
                      />
                      {opcion.icono}
                      {opcion.etiqueta}
                    </label>
                  ))}
                </div>
                <p className="nota-base nota-base--campo">
                  <IconoSeveridadMedia />
                  Los procedimientos del motor de base de datos pueden usar SELECT *.
                </p>
              </div>
            )}
          </div>

          <div className="editor-grid">
            <TarjetaEditor
              className={tieneDiccionario ? 'field-card-primary' : 'field-card-primary field-card-full'}
              numero={1}
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
                onCambiar={(valor) => {
                  setMarca(null);
                  alCambiarSql(valor);
                }}
                marcadas={marcadasEn('objeto')}
                enfocar={enfocarEn('objeto')}
                placeholder="CREATE PROCEDURE ..."
              />
            </TarjetaEditor>

            {tieneDiccionario && (
              <TarjetaEditor
                className="field-card-secondary"
                numero={2}
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
                  onCambiar={(valor) => {
                    setMarca(null);
                    actualizarCampo('dictScript', valor);
                  }}
                  marcadas={marcadasEn('diccionario')}
                  enfocar={enfocarEn('diccionario')}
                  placeholder="EXEC sys.sp_addextendedproperty ..."
                />
              </TarjetaEditor>
            )}

            {tieneIndices && !mostrarIndices && (
              <button type="button" className="agregar-indices" onClick={() => setIndicesAbiertos(true)}>
                <span className="agregar-indices-icono" aria-hidden="true"><IconoAgregar /></span>
                Agregar índices de la tabla
              </button>
            )}

            {mostrarIndices && (
              <TarjetaEditor
                className="field-card-full field-card-indices"
                numero={2}
                etiqueta={revision.indices.etiqueta}
                htmlFor={`${ids}-indices`}
                estado="Opcional"
                requerido={false}
                ayuda={revision.indices.ayuda}
                acciones={
                  <button type="button" className="link-btn" onClick={quitarIndices} title="Quitar los índices de la revisión">
                    <IconoCerrar />
                    Quitar
                  </button>
                }
              >
                <EditorCodigo
                  id={`${ids}-indices`}
                  valor={campos.indicesScript ?? ''}
                  onCambiar={(valor) => {
                    setMarca(null);
                    actualizarCampo('indicesScript', valor);
                  }}
                  marcadas={marcadasEn('indices')}
                  enfocar={enfocarEn('indices')}
                  filas={5}
                  placeholder="CREATE NONCLUSTERED INDEX ..."
                />
              </TarjetaEditor>
            )}
          </div>

          <div className="action-bar">
            <div className="btn-group">
              <Boton type="submit" icono={<IconoEjecutar />} cargando={cargando} atajo={['Ctrl', 'Enter']}>
                Ejecutar revisión
              </Boton>
              <Boton variante="secundario" icono={<IconoLimpiar />} onClick={limpiar}>Limpiar</Boton>
            </div>
            <p className={`estado-revision${hayCodigo ? ' listo' : ''}`} role="status">
              <i aria-hidden="true" />
              {hayCodigo ? `Listo para revisar · ${resumenLineas}` : 'Pega el código para iniciar la revisión'}
            </p>
          </div>
        </form>

        {marca?.recorrido && (
          <BarraRecorrido
            titulo={marca.recorrido}
            linea={marca.lineas[marca.indice]}
            posicion={marca.indice + 1}
            total={marca.lineas.length}
            onAnterior={() => irALinea(-1)}
            onSiguiente={() => irALinea(1)}
            onCerrar={() => setMarca(null)}
          />
        )}

        {avisoDiccionario && (
          <AvisoFaltaDiccionario
            objeto={tipoRevision}
            nombre={campos.objetoNombre.trim()}
            onAnadir={anadirDiccionario}
            onRevisarSinDiccionario={revisarSinDiccionario}
            onCerrar={cerrarAviso}
          />
        )}

        <div className="panel-footer" ref={resultadosRef}>
          <PanelHallazgos
            titulo={vista.resultados.titulo}
            estado={resultado.estado}
            hallazgos={resultado.hallazgos}
            mensajeError={resultado.mensaje}
            accionesHallazgo={accionesHallazgo}
            textos={{
              inicialTitulo: 'Listo para iniciar la revisión',
              pasos: [
                'Pega el código del objeto en el editor',
                <>Presiona «Ejecutar revisión» o <kbd>Ctrl</kbd> + <kbd>Enter</kbd></>,
                'Revisa cada hallazgo y cómo corregirlo',
              ],
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
