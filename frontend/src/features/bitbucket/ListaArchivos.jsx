import { useId } from 'react';
import {
  IconoAdjunto, IconoArchivos, IconoCodigo, IconoEliminado, IconoFlecha, IconoLibro, IconoMenos, IconoPregunta, IconoPunto,
  IconoTabla,
} from '../../components/Iconos';
import { MODULOS, carpetaArchivo, nombreArchivo, tipoDe } from './archivos';
import { describirReferencia } from './enlace';

const ICONOS = { tabla: IconoTabla, libro: IconoLibro, codigo: IconoCodigo, otro: IconoArchivos };

function IconoTipo({ archivo }) {
  const Icono = ICONOS[tipoDe(archivo).icono] ?? IconoArchivos;
  return <span className="bb-icono-tipo"><Icono /></span>;
}

/** Selector «Se revisa en»: los módulos posibles del tipo de archivo, o no revisarlo. */
function SelectorModulo({ fila, onElegir }) {
  const { archivo, modulo } = fila;
  const id = useId();
  const opciones = tipoDe(archivo).modulos;
  return (
    <>
      <label htmlFor={id} className="bb-rotulo">Se revisa en</label>
      <select
        id={id}
        className="bb-selector"
        value={modulo ?? 'ninguno'}
        onChange={(evento) => onElegir(archivo.id, evento.target.value)}
      >
        {opciones.map((opcion) => <option key={opcion} value={opcion}>{MODULOS[opcion].etiqueta}</option>)}
        <option value="ninguno">No revisar</option>
      </select>
    </>
  );
}

/** Pregunta cuando el tipo no se distingue con seguridad: la usuaria elige y Genesis no adivina. */
function PreguntaModulo({ fila, onElegir }) {
  const { archivo, eleccion } = fila;
  return (
    <>
      <span className="bb-rotulo">¿Cómo lo reviso?</span>
      <div className="bb-segmentos" role="group" aria-label={`Cómo revisar ${nombreArchivo(archivo.ruta)}`}>
        {tipoDe(archivo).modulos.map((opcion) => (
          <button
            key={opcion}
            type="button"
            className={eleccion === opcion ? 'bb-segmento activo' : 'bb-segmento'}
            aria-pressed={eleccion === opcion}
            onClick={() => onElegir(archivo.id, opcion)}
          >
            {MODULOS[opcion].etiqueta === 'Procedimientos' ? 'Procedimiento' : 'Reporte'}
          </button>
        ))}
      </div>
    </>
  );
}

function TarjetaArchivo({ fila, numero, onElegir }) {
  const { archivo, situacion, revision } = fila;
  const duda = archivo.dudoso;
  const clases = ['bb-tarjeta'];
  if (situacion === 'confirmar') clases.push('bb-tarjeta-duda');
  if (situacion === 'omitido') clases.push('bb-tarjeta-omitida');
  return (
    <article className={clases.join(' ')}>
      <span className={situacion === 'confirmar' ? 'bb-numero bb-numero-alerta' : 'bb-numero'}>
        {situacion === 'confirmar' ? 'Requiere tu respuesta' : String(numero).padStart(2, '0')}
      </span>
      <div className="bb-tarjeta-cabecera">
        <IconoTipo archivo={archivo} />
        <div className="bb-tarjeta-nombres">
          <p className="bb-archivo">{nombreArchivo(archivo.ruta)}</p>
          <p className="bb-archivo-detalle">
            {!duda && <em>{tipoDe(archivo).etiqueta}</em>}
            {!duda && carpetaArchivo(archivo.ruta) && ' · '}
            {carpetaArchivo(archivo.ruta)}
            {archivo.estado === 'modificado' && ' · modificado'}
          </p>
          {archivo.motivo && <p className="bb-archivo-motivo">{archivo.motivo}</p>}
        </div>
      </div>
      {revision?.error && <p className="bb-tarjeta-aviso">{revision.error}</p>}
      <div className="bb-tarjeta-pie">
        {duda && situacion !== 'omitido'
          ? <PreguntaModulo fila={fila} onElegir={onElegir} />
          : <SelectorModulo fila={fila} onElegir={onElegir} />}
      </div>
    </article>
  );
}

function Aparte({ icono: Icono, titulo, filas, detalle }) {
  if (!filas.length) return null;
  return (
    <p className="bb-aparte">
      <Icono />
      <span>
        <b>{titulo}:</b>{' '}
        {filas.map((fila, indice) => (
          <span key={fila.archivo.id}>
            {indice > 0 && ' · '}
            {nombreArchivo(fila.archivo.ruta)}
            {detalle && ` (${detalle(fila)})`}
          </span>
        ))}
      </span>
    </p>
  );
}

/** Paso 2: qué es cada archivo y dónde se revisa. */
export function ListaArchivos({ cambio, filas, cuenta, onElegir, onRevisar }) {
  const visibles = filas.filter((fila) => ['revisar', 'confirmar', 'omitido'].includes(fila.situacion));
  const adjuntos = filas.filter((fila) => fila.situacion === 'adjunto');
  const sinReglas = filas.filter((fila) => fila.situacion === 'sinReglas');
  const eliminados = filas.filter((fila) => fila.situacion === 'eliminado');
  const { origen } = cambio;
  const detalleOrigen = [origen.repositorio, origen.autor].filter(Boolean).join(' · ');
  const nombrePorId = Object.fromEntries(filas.map((fila) => [fila.archivo.id, nombreArchivo(fila.archivo.ruta)]));

  return (
    <section className="bb-seccion" aria-labelledby="bb-lista-titulo">
      <header className="bb-seccion-cabecera">
        <p className="bb-etiqueta">{describirReferencia(origen)}</p>
        <h2 id="bb-lista-titulo" className="bb-seccion-titulo">Archivos encontrados</h2>
        <p className="bb-seccion-detalle">{origen.titulo ? `${origen.titulo} · ${detalleOrigen}` : detalleOrigen}</p>
      </header>

      <div className="bb-franja">
        <div className="bb-franja-celda activa"><IconoArchivos /><span><small>Archivos .sql</small><strong>{filas.length}</strong></span></div>
        <div className="bb-franja-celda"><IconoPunto /><span><small>Para revisar</small><strong>{cuenta.revisar}</strong></span></div>
        <div className="bb-franja-celda"><IconoPregunta /><span><small>Por confirmar</small><strong>{cuenta.confirmar}</strong></span></div>
        <div className="bb-franja-celda"><IconoMenos /><span><small>Sin reglas</small><strong>{cuenta.sinReglas}</strong></span></div>
      </div>

      <div className="bb-seccion-cuerpo">
        <div className="bb-grilla">
          {visibles.map((fila, indice) => (
            <TarjetaArchivo key={fila.archivo.id} fila={fila} numero={indice + 1} onElegir={onElegir} />
          ))}
        </div>

        <div className="bb-apartes">
          <Aparte
            icono={IconoAdjunto}
            titulo="Se revisan junto con su tabla"
            filas={adjuntos}
            detalle={(fila) => `con ${nombrePorId[fila.archivo.pareja] ?? 'su tabla'}`}
          />
          <Aparte icono={IconoMenos} titulo="Sin reglas de revisión" filas={sinReglas} detalle={(fila) => tipoDe(fila.archivo).etiqueta.toLowerCase()} />
          <Aparte icono={IconoEliminado} titulo="Eliminados en el cambio" filas={eliminados} />
        </div>

        <div className="bb-cierre">
          {cuenta.confirmar > 0 && (
            <p className="bb-cierre-aviso">
              {cuenta.confirmar === 1 ? 'Falta responder 1 archivo.' : `Faltan responder ${cuenta.confirmar} archivos.`}
            </p>
          )}
          <button type="button" className="bb-boton" onClick={onRevisar} disabled={!cuenta.revisar || cuenta.confirmar > 0}>
            {cuenta.revisar === 1 ? 'Revisar 1 archivo' : `Revisar ${cuenta.revisar} archivos`}
            <IconoFlecha />
          </button>
        </div>
      </div>
    </section>
  );
}
