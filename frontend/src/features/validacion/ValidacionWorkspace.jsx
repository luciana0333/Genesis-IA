import { useEffect, useId, useRef, useState } from 'react';
import { estadoValidacionSql, esCancelacion, validarSql } from '../../api/cliente';
import { Boton } from '../../components/Boton';
import { EditorCodigo } from '../../components/EditorCodigo';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import {
  IconoBaseDatos, IconoEjecutar, IconoErrorCirculo, IconoEscudoCheck, IconoLimpiar, IconoRestaurar,
} from '../../components/Iconos';
import { PanelHallazgos } from '../../components/PanelHallazgos';
import { TarjetaEditor } from '../../components/TarjetaEditor';
import { useAlPedirEjemplo } from '../../hooks/useVerEjemplo';
import { nombreRegla } from '../../config/reglas';
import { BarraRecorrido, VerEnCodigo } from '../auditoria/VerEnCodigo';

// Ejemplo con los errores de estructura más comunes (coma de más, paréntesis sin cerrar, BEGIN sin END).
export const EJEMPLO_VALIDACION = `CREATE PROCEDURE dbo.PA_Credito_Sel_Resumen
    @pcCtaCod VARCHAR(18)
AS
BEGIN
    SET NOCOUNT ON

    SELECT c.cCtaCod,, c.nSaldo
    FROM dbo.Credito c WITH (NOLOCK)
    WHERE c.cCtaCod = @pcCtaCod

    IF EXISTS (SELECT 1 FROM dbo.CreditoCuota q WITH (NOLOCK) WHERE (q.cCtaCod = @pcCtaCod)
    BEGIN
        SELECT 'Tiene cuotas' AS cMensaje
    END
`;

const RESULTADO_INICIAL = { estado: 'inicial', hallazgos: [], mensaje: '' };

const esAtajoEjecutar = (evento) => (evento.ctrlKey || evento.metaKey) && evento.key === 'Enter';

/**
 * Validación SQL Server: el código se lee con ScriptDom, el lector oficial de T-SQL (el mismo de SSMS).
 * Etapa 1: solo errores de estructura (comas, paréntesis, comillas, BEGIN/END). Si la PC no tiene
 * ScriptDom (viene con SSMS), se avisa y las demás pestañas siguen igual.
 */
export function ValidacionWorkspace() {
  const ids = useId();
  const resultadosRef = useRef(null);
  const [sql, setSql] = useState(EJEMPLO_VALIDACION);
  const [lector, setLector] = useState({ cargando: true });
  const [resultado, setResultado] = useState(RESULTADO_INICIAL);
  const [marcaPedida, setMarca] = useState(null);
  const pedidoRef = useRef(null);

  useEffect(() => {
    const control = new AbortController();
    estadoValidacionSql({ signal: control.signal })
      .then((estado) => setLector(estado))
      .catch((error) => {
        if (!esCancelacion(error)) setLector({ disponible: false, motivo: error.message });
      });
    return () => control.abort();
  }, []);

  const validar = async (codigo = sql) => {
    pedidoRef.current?.abort();
    const control = new AbortController();
    pedidoRef.current = control;
    setResultado({ estado: 'cargando', hallazgos: [], mensaje: '' });
    try {
      const datos = await validarSql(codigo, { signal: control.signal });
      if (datos.estado) setLector(datos.estado);
      setResultado({ estado: 'listo', hallazgos: datos.hallazgos ?? [], mensaje: '' });
    } catch (error) {
      if (esCancelacion(error)) return;
      setResultado({ estado: 'error', hallazgos: [], mensaje: error.message });
    }
  };

  useAlPedirEjemplo(() => {
    setSql(EJEMPLO_VALIDACION);
    setMarca(null);
    validar(EJEMPLO_VALIDACION);
    resultadosRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  });

  const alEnviar = (evento) => {
    evento.preventDefault();
    if (resultado.estado === 'cargando' || !sql.trim()) return;
    validar();
  };

  // «Ver en el código»: la marca vale solo para el resultado en el que se pidió.
  const marca = marcaPedida?.resultado === resultado ? marcaPedida : null;
  // Una observación que junta varios casos recorre sus líneas con la barra «1 de N».
  const verEnCodigo = (hallazgo) => {
    const lineas = hallazgo.lineas?.length ? hallazgo.lineas : [hallazgo.linea];
    setMarca((anterior) => ({
      lineas, indice: 0, resultado, titulo: nombreRegla(hallazgo.regla), clave: (anterior?.clave ?? 0) + 1,
    }));
  };
  const irALinea = (paso) => {
    setMarca((anterior) => anterior && ({
      ...anterior,
      indice: (anterior.indice + paso + anterior.lineas.length) % anterior.lineas.length,
      clave: anterior.clave + 1,
    }));
  };

  const lineas = sql.trim() ? sql.split('\n').length : 0;
  const cargando = resultado.estado === 'cargando';

  return (
    <section className="workspace">
      <section className="panel">
        <div className="panel-header">
          <EncabezadoSeccion
            etiqueta="Paso 1 · Código"
            titulo="Validación con el lector oficial de SQL Server"
            descripcion="Pega el código y Genesis lo lee como SQL Server 2022, igual que SSMS al ejecutarlo."
          />
        </div>

        <form
          className="panel-body"
          onSubmit={alEnviar}
          onKeyDown={(evento) => { if (esAtajoEjecutar(evento)) evento.currentTarget.requestSubmit(); }}
          noValidate
        >
          <EstadoLector lector={lector} />

          <div className="editor-grid">
            <TarjetaEditor
              className="field-card-primary field-card-full"
              numero={1}
              etiqueta="Código SQL"
              htmlFor={`${ids}-sql`}
              estado="Requerido"
              ayuda="Pega aquí un procedimiento, una tabla o cualquier script de SQL Server (con o sin GO)."
              acciones={
                <button type="button" className="link-btn" onClick={() => { setSql(EJEMPLO_VALIDACION); setMarca(null); }}>
                  <IconoRestaurar />
                  Restaurar ejemplo
                </button>
              }
            >
              <EditorCodigo
                id={`${ids}-sql`}
                valor={sql}
                onCambiar={(valor) => { setMarca(null); setSql(valor); }}
                marcadas={marca?.lineas ?? []}
                enfocar={marca ? { linea: marca.lineas[marca.indice], clave: marca.clave } : null}
                placeholder="CREATE PROCEDURE ..."
              />
            </TarjetaEditor>
          </div>

          <div className="action-bar">
            <div className="btn-group">
              <Boton type="submit" icono={<IconoEjecutar />} cargando={cargando} atajo={['Ctrl', 'Enter']}>
                Validar código
              </Boton>
              <Boton variante="secundario" icono={<IconoLimpiar />} onClick={() => { setSql(''); setMarca(null); setResultado(RESULTADO_INICIAL); }}>
                Limpiar
              </Boton>
            </div>
            <p className={`estado-revision${lineas ? ' listo' : ''}`} role="status">
              <i aria-hidden="true" />
              {lineas ? `Listo para validar · ${lineas} líneas` : 'Pega el código para iniciar la validación'}
            </p>
          </div>
        </form>

        {marca && marca.lineas.length > 1 && (
          <BarraRecorrido
            titulo={marca.titulo}
            linea={marca.lineas[marca.indice]}
            posicion={marca.indice + 1}
            total={marca.lineas.length}
            onAnterior={() => irALinea(-1)}
            onSiguiente={() => irALinea(1)}
            onCerrar={() => setMarca(null)}
          />
        )}

        <div className="panel-footer" ref={resultadosRef}>
          <PanelHallazgos
            titulo="Resultados de la validación"
            estado={resultado.estado}
            hallazgos={resultado.hallazgos}
            mensajeError={resultado.mensaje}
            accionesHallazgo={(hallazgo) => <VerEnCodigo onVer={() => verEnCodigo(hallazgo)} />}
            textos={{
              inicialTitulo: 'Listo para validar el código',
              pasos: [
                'Pega el código en el editor',
                <>Presiona «Validar estructura» o <kbd>Ctrl</kbd> + <kbd>Enter</kbd></>,
                'Revisa cada observación en la línea que indica',
              ],
              cargando: 'Leyendo el código como SQL Server...',
              sinHallazgos: 'La validación terminó sin observaciones.',
              tituloError: 'No se pudo validar el código',
            }}
          />
        </div>
      </section>
    </section>
  );
}

/** Estado del lector: si esta PC tiene ScriptDom y con qué versión de SQL Server lee. */
function EstadoLector({ lector }) {
  if (lector.cargando) {
    return <div className="estado-lector"><span className="estado-lector-chip">Buscando ScriptDom en esta PC...</span></div>;
  }
  return (
    <div className="estado-lector">
      {lector.disponible ? (
        <span className="estado-lector-chip ok" title={lector.dll}>
          <IconoEscudoCheck />
          ScriptDom listo{lector.version ? ` · versión ${lector.version}` : ''}
        </span>
      ) : (
        <span className="estado-lector-chip error">
          <IconoErrorCirculo />
          {lector.motivo || 'ScriptDom no está disponible en esta PC.'}
        </span>
      )}
      <span className="estado-lector-chip"><IconoBaseDatos />Lee como SQL Server 2022</span>
    </div>
  );
}
