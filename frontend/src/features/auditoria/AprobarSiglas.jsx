import { useId, useState } from 'react';
import { aprobarSigla } from '../../api/cliente';
import { IconoCopiado, IconoLibro, IconoRestaurar, IconoSeveridadMedia } from '../../components/Iconos';

const VACIA = { texto: '', estado: 'pendiente', error: '' };

/** «En 2 tablas · 12 columnas · 1 procedimiento» */
function textoUso(uso) {
  if (!uso) return null;
  const partes = [
    [uso.tabla, 'tabla', 'tablas'],
    [uso.columna, 'columna', 'columnas'],
    [uso.procedimiento, 'procedimiento', 'procedimientos'],
  ].filter(([cantidad]) => cantidad > 0).map(([cantidad, uno, varios]) => `${cantidad} ${cantidad === 1 ? uno : varios}`);
  return partes.length ? `En ${partes.join(' · ')}` : null;
}

/**
 * «Aprobar siglas»: se despliega dentro de la observación de «sigla por validar».
 * Cada sigla se aprueba con su significado y se guarda en el glosario de esta PC;
 * desde la siguiente revisión deja de marcarse.
 * `usos`: dónde aparece cada sigla en toda la revisión ({ TPPP: { tabla: 2, columna: 12 } }).
 */
export function AprobarSiglas({ siglas, usos = {}, onActualizar }) {
  const id = useId();
  const [abierto, setAbierto] = useState(false);
  const [filas, setFilas] = useState({});
  // Al actualizar la revisión puede aparecer una sigla nueva: empieza vacía.
  const filaDe = (sigla) => filas[sigla] ?? VACIA;
  const aprobadas = siglas.filter((sigla) => filaDe(sigla).estado === 'aprobada').length;
  const avance = siglas.length ? Math.round((aprobadas / siglas.length) * 100) : 0;

  const cambiar = (sigla, cambios) => setFilas((actuales) => ({
    ...actuales,
    [sigla]: { ...(actuales[sigla] ?? VACIA), ...cambios },
  }));

  const aprobar = async (sigla) => {
    const significado = filaDe(sigla).texto.trim();
    if (!significado) {
      cambiar(sigla, { error: 'Escribe el significado para aprobarla.' });
      return;
    }
    cambiar(sigla, { estado: 'guardando', error: '' });
    try {
      const datos = await aprobarSigla(sigla, significado);
      cambiar(sigla, { estado: 'aprobada', texto: datos.significado || significado });
    } catch (error) {
      cambiar(sigla, { estado: 'pendiente', error: error.message });
    }
  };

  return (
    <>
      <button
        type="button"
        className={abierto ? 'aprobar-siglas-boton activo' : 'aprobar-siglas-boton'}
        aria-expanded={abierto}
        aria-controls={`${id}-panel`}
        onClick={() => setAbierto((valor) => !valor)}
      >
        <IconoLibro />
        {abierto ? 'Ocultar siglas' : `Aprobar sigla${siglas.length === 1 ? '' : 's'}`}
      </button>

      {abierto && (
        <section className="aprobar-siglas" id={`${id}-panel`} aria-label="Aprobar siglas">
          <header className="aprobar-siglas-cabecera">
            <span className="aprobar-siglas-icono" aria-hidden="true"><IconoLibro /></span>
            <div className="aprobar-siglas-textos">
              <p className="aprobar-siglas-etiqueta">Glosario de siglas</p>
              <p className="aprobar-siglas-titulo">Aprobar siglas</p>
              <p className="aprobar-siglas-ayuda">
                Se guardan en el glosario de esta PC y dejan de marcarse en las próximas revisiones.
              </p>
            </div>
            <div className="aprobar-siglas-avance" aria-live="polite">
              <span className="aprobar-siglas-avance-texto">
                <span>Avance</span>
                <strong>{aprobadas} de {siglas.length}</strong>
              </span>
              <span className="aprobar-siglas-barra" role="progressbar" aria-valuemin={0} aria-valuemax={siglas.length} aria-valuenow={aprobadas} aria-label="Siglas aprobadas">
                <i style={{ width: `${avance}%` }} />
              </span>
            </div>
          </header>

          <ul className="aprobar-siglas-lista">
            {siglas.map((sigla) => {
              const fila = filaDe(sigla);
              const campo = `${id}-${sigla}`;
              const uso = textoUso(usos[sigla]);
              const cabecera = (
                <div className="aprobar-siglas-nombre">
                  <label className="aprobar-siglas-sigla" htmlFor={fila.estado === 'aprobada' ? undefined : campo}>{sigla}</label>
                  {uso && <span className="aprobar-siglas-uso">{uso}</span>}
                </div>
              );
              if (fila.estado === 'aprobada') {
                return (
                  <li key={sigla} className="aprobar-siglas-fila aprobada">
                    {cabecera}
                    <span className="aprobar-siglas-significado">
                      <span className="aprobar-siglas-check" aria-hidden="true"><IconoCopiado /></span>
                      {fila.texto}
                    </span>
                    <span className="aprobar-siglas-estado">Aprobada</span>
                  </li>
                );
              }
              return (
                <li key={sigla} className="aprobar-siglas-fila">
                  {cabecera}
                  <div className="aprobar-siglas-campo">
                    <input
                      id={campo}
                      type="text"
                      value={fila.texto}
                      maxLength={150}
                      placeholder={`Significado de ${sigla}`}
                      aria-invalid={Boolean(fila.error)}
                      disabled={fila.estado === 'guardando'}
                      onChange={(evento) => cambiar(sigla, { texto: evento.target.value, error: '' })}
                      onKeyDown={(evento) => { if (evento.key === 'Enter') aprobar(sigla); }}
                    />
                    {fila.error && <span className="aprobar-siglas-error" role="alert">{fila.error}</span>}
                  </div>
                  <button
                    type="button"
                    className="aprobar-siglas-aprobar"
                    disabled={fila.estado === 'guardando'}
                    onClick={() => aprobar(sigla)}
                  >
                    {fila.estado === 'guardando' ? <span className="spinner" aria-hidden="true" /> : <IconoCopiado />}
                    Aprobar
                  </button>
                </li>
              );
            })}
          </ul>

          <footer className="aprobar-siglas-pie">
            <p>
              <IconoSeveridadMedia />
              Si no sabes su significado, déjala pendiente: seguirá como «por validar».
            </p>
            {aprobadas > 0 && (
              <button type="button" className="aprobar-siglas-actualizar" onClick={onActualizar}>
                <IconoRestaurar />
                Actualizar revisión
              </button>
            )}
          </footer>
        </section>
      )}
    </>
  );
}
