import { useId, useState } from 'react';
import { aprobarSigla } from '../../api/cliente';
import { IconoCopiado, IconoLibro, IconoRestaurar } from '../../components/Iconos';

/**
 * «Aprobar siglas»: se despliega dentro de la observación de «sigla por validar».
 * Cada sigla se aprueba con su significado y se guarda en el glosario de esta PC;
 * desde la siguiente revisión deja de marcarse.
 */
export function AprobarSiglas({ siglas, onActualizar }) {
  const id = useId();
  const [abierto, setAbierto] = useState(false);
  const [filas, setFilas] = useState(() => Object.fromEntries(
    siglas.map((sigla) => [sigla, { texto: '', estado: 'pendiente', error: '' }]),
  ));
  const VACIA = { texto: '', estado: 'pendiente', error: '' };
  // Al actualizar la revisión puede aparecer una sigla nueva: empieza vacía.
  const filaDe = (sigla) => filas[sigla] ?? VACIA;
  const aprobadas = siglas.filter((sigla) => filaDe(sigla).estado === 'aprobada').length;

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
            <div>
              <p className="aprobar-siglas-etiqueta">Glosario de siglas</p>
              <p className="aprobar-siglas-titulo">Aprobar siglas</p>
              <p className="aprobar-siglas-ayuda">
                Se guardan en el glosario de esta PC y dejan de marcarse en las próximas revisiones.
              </p>
            </div>
            <span className="aprobar-siglas-contador" aria-live="polite">
              <strong>{aprobadas}</strong> de {siglas.length} aprobada{siglas.length === 1 ? '' : 's'}
            </span>
          </header>

          <ul className="aprobar-siglas-lista">
            {siglas.map((sigla) => {
              const fila = filaDe(sigla);
              const campo = `${id}-${sigla}`;
              if (fila.estado === 'aprobada') {
                return (
                  <li key={sigla} className="aprobar-siglas-fila aprobada">
                    <span className="aprobar-siglas-sigla">{sigla}</span>
                    <span className="aprobar-siglas-significado">{fila.texto}</span>
                    <span className="aprobar-siglas-estado"><IconoCopiado />Aprobada</span>
                  </li>
                );
              }
              return (
                <li key={sigla} className="aprobar-siglas-fila">
                  <label className="aprobar-siglas-sigla" htmlFor={campo}>{sigla}</label>
                  <div className="aprobar-siglas-campo">
                    <input
                      id={campo}
                      type="text"
                      value={fila.texto}
                      maxLength={150}
                      placeholder={`¿Qué significa ${sigla}?`}
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
            <p>¿No sabes qué significa? Déjala sin aprobar: seguirá como «por validar».</p>
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
