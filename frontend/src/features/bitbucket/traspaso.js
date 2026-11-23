/**
 * «Abrir en …»: lleva un archivo de Bitbucket al módulo de siempre, con el código ya pegado.
 *
 * La pestaña Bitbucket deja el traspaso y cambia la URL (#/procedimientos); el módulo, al montarse, lo toma
 * una sola vez, carga los campos y revisa. Así el módulo no cambia en nada: recibe lo mismo que si se pegara.
 */
import { MODULOS } from './archivos';

let pendiente = null;

export function abrirEnModulo(revision) {
  const destino = MODULOS[revision.modulo];
  pendiente = { vista: destino.vista, tipoRevision: revision.tipoRevision, campos: revision.campos };
  window.location.hash = `#/${destino.ruta}`;
}

/** El traspaso para esta vista (y se borra), o null si no hay. */
export function tomarTraspaso(vistaId) {
  if (!pendiente || pendiente.vista !== vistaId) return null;
  const traspaso = pendiente;
  pendiente = null;
  return traspaso;
}
