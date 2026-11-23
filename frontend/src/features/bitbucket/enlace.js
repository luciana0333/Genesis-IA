/**
 * Lee un link de Bitbucket Cloud y dice qué es: pull request, rama o commit.
 *
 * Es lo que los desarrolladores pegan en el correo, por ejemplo:
 *   https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129/overview
 *   https://bitbucket.org/cajaica/objetos-base-de-datos/branch/feature/60PSO2026-adecuar-deposito-cts-cuenta
 *   https://bitbucket.org/cajaica/genn-ocr/commits/602464364d664f7377a8cb43f65d4d8248980305
 *
 * Solo interpreta el texto: no se conecta a nada. Devuelve { tipo, espacio, repositorio, referencia, enlace }
 * o { error } con un mensaje para mostrar.
 */

const HOST = /^(?:www\.)?bitbucket\.org$/i;
const HASH_COMMIT = /^[0-9a-f]{7,40}$/i;

export const ETIQUETA_TIPO = { pr: 'Pull request', rama: 'Rama', commit: 'Commit' };

function conProtocolo(texto) {
  return /^https?:\/\//i.test(texto) ? texto : `https://${texto}`;
}

export function leerEnlace(texto) {
  const limpio = (texto ?? '').trim();
  if (!limpio) return { error: 'Pega el link del pull request, la rama o el commit.' };

  let url;
  try {
    url = new URL(conProtocolo(limpio));
  } catch {
    return { error: 'El texto pegado no es un link válido.' };
  }
  if (!HOST.test(url.hostname)) {
    return { error: 'El link no es de Bitbucket: debe empezar con https://bitbucket.org/.' };
  }

  const partes = url.pathname.split('/').filter(Boolean).map((parte) => decodeURIComponent(parte));
  const [espacio, repositorio, seccion, ...resto] = partes;
  if (!espacio || !repositorio) {
    return { error: 'Falta el repositorio en el link (bitbucket.org/espacio/repositorio/…).' };
  }
  const base = { espacio, repositorio, enlace: `https://bitbucket.org/${partes.join('/')}` };

  if (seccion === 'pull-requests' && /^\d+$/.test(resto[0] ?? '')) {
    return { ...base, tipo: 'pr', referencia: resto[0] };
  }
  if (seccion === 'commits' && HASH_COMMIT.test(resto[0] ?? '')) {
    return { ...base, tipo: 'commit', referencia: resto[0].toLowerCase() };
  }
  // El nombre de una rama puede tener barras (feature/60PSO2026-…): es todo lo que sigue a /branch/.
  if (seccion === 'branch' && resto.length) {
    return { ...base, tipo: 'rama', referencia: resto.join('/') };
  }
  return { error: 'El link debe ser de un pull request, una rama o un commit del repositorio.' };
}

/** Texto corto para mostrar: «Pull request #129», «Rama feature/…», «Commit 6024643». */
export function describirReferencia({ tipo, referencia }) {
  if (tipo === 'pr') return `${ETIQUETA_TIPO.pr} #${referencia}`;
  if (tipo === 'commit') return `${ETIQUETA_TIPO.commit} ${referencia.slice(0, 7)}`;
  return `${ETIQUETA_TIPO.rama} ${referencia}`;
}
