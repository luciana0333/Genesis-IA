import { renderToStaticMarkup } from 'react-dom/server';
import { Flecha, Nodo } from './DiagramaPlan';
import { COLUMNA, calcularPosiciones, filasDesviadas } from './geometriaPlan';
import { DefinicionesIconos } from './IconosPlan';

/*
 * Captura de un hallazgo del plan, como la que se pega en el informe: un recorte
 * del diagrama alrededor del operador (enmarcado en verde) con el recuadro de
 * advertencias encima y los valores importantes resaltados en amarillo, igual
 * que el tooltip de SSMS / Plan Explorer. Se dibuja como SVG y se pasa a PNG.
 */

const FUENTE = '"Segoe UI", Tahoma, Arial, sans-serif';
const TAMANO = 12;
const ALTO_LINEA = 17;
const ANCHO_RECUADRO = 560;
const RELLENO = 10;
const ANCHO_RECORTE = COLUMNA * 5;
const ALTO_RECORTE = 150;
const ALTO_PESTANA = 26;
const SEPARACION = 18;
const MAXIMO_NODOS = 4;
const ESCALA = 2;

// Los mismos colores del diagrama (tema claro): la imagen no lee el CSS de la página.
const ESTILOS = `
  text { font-family: ${FUENTE}; }
  .plan-flecha polyline { stroke: #8fa2b2; }
  .plan-flecha polygon { fill: #8fa2b2; }
  .plan-filas { fill: #555555; font-size: 10.5px; }
  .plan-filas.desviada { fill: #c8102e; }
  .plan-costo { fill: #222222; font-size: 12px; font-weight: 700; }
  .plan-costo-pastilla rect { fill: #f58220; }
  .plan-costo-pastilla.alto rect { fill: #c8102e; }
  .plan-costo-pastilla text { fill: #ffffff; font-size: 11.5px; font-weight: 600; }
  .plan-icono-fondo { fill: #ffffff; }
  .plan-nodo.activo .plan-icono-fondo { stroke: #36c23a; stroke-width: 2.5; }
  .plan-alerta polygon { fill: #ffd200; stroke: #9c7a00; stroke-width: 1; }
  .plan-alerta text { fill: #3d2b00; font-size: 10px; font-weight: 800; }
  .plan-resaltado { fill: #ffef7a; }
  .plan-nombre { fill: #222222; font-size: 11.5px; }
  .plan-detalle { fill: #444444; font-size: 11px; }
`;

let contexto;
function medir(texto, negrita = false) {
  contexto ??= document.createElement('canvas').getContext('2d');
  contexto.font = `${negrita ? '700 ' : ''}${TAMANO}px ${FUENTE}`;
  return contexto.measureText(texto).width;
}

function escapar(texto) {
  return String(texto).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Parte un texto en trozos normales y resaltados, y los acomoda en líneas del ancho dado. */
function acomodar(texto, resaltados, ancho) {
  const partes = resaltados.filter(Boolean);
  const patron = partes.length
    ? new RegExp(`(${partes.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`)
    : null;
  const trozos = (patron ? texto.split(patron) : [texto])
    .filter(Boolean)
    .flatMap((trozo) => {
      const resaltado = partes.includes(trozo);
      return trozo.split(/(?<= )/).map((palabra) => ({ texto: palabra, resaltado }));
    });

  const lineas = [[]];
  let usado = 0;
  for (const trozo of trozos) {
    let { texto: resto } = trozo;
    while (resto) {
      const espacio = ancho - usado;
      let pedazo = resto;
      // Una «palabra» más larga que la línea (p. ej. una expresión sin espacios) se corta por caracteres.
      while (medir(pedazo) > ancho && pedazo.length > 1) pedazo = pedazo.slice(0, -1);
      if (medir(pedazo) > espacio && usado > 0) {
        lineas.push([]);
        usado = 0;
        continue;
      }
      lineas.at(-1).push({ texto: pedazo, resaltado: trozo.resaltado, x: usado });
      usado += medir(pedazo);
      resto = resto.slice(pedazo.length);
    }
  }
  return lineas;
}

/** Contenido del recuadro: solo las advertencias que trae el XML del plan. */
function contenidoRecuadro(nodo, regla) {
  const grupos = nodo.advertencias.length ? [{ titulo: 'Warnings:', items: nodo.advertencias }] : [];
  // Lectura residual: con el mismo aviso que muestra Plan Explorer (datos del XML: ActualRowsRead y ActualRows).
  if (regla === 'LECTURA_RESIDUAL_ELEVADA' && nodo.filasLeidas != null) {
    const leidas = Math.round(nodo.filasLeidas).toLocaleString('en-US');
    const devueltas = Math.round(nodo.filasReales ?? 0).toLocaleString('en-US');
    const filtro = (nodo.predicados ?? []).find((p) => p.nombre === 'Predicate');
    grupos.push({
      titulo: grupos.length ? null : 'Warnings:',
      items: [
        {
          texto: `Operation caused residual I/O. The actual number of rows read was ${leidas}, but the number of rows returned was ${devueltas}.`,
          resaltados: [leidas, devueltas],
        },
        ...(filtro ? [{ texto: `Predicate: ${filtro.texto}`, resaltados: [] }] : []),
      ],
    });
  }
  return grupos;
}

/** Recuadro de advertencias en SVG, dibujado desde (0, 0); devuelve su marcado, ancho y alto. */
function recuadro(nodo, regla) {
  const x = 0;
  const y = 0;
  const anchoTexto = ANCHO_RECUADRO - RELLENO * 2;
  const filas = [];
  for (const grupo of contenidoRecuadro(nodo, regla)) {
    if (grupo.titulo) filas.push({ tipo: 'grupo', texto: grupo.titulo });
    for (const item of grupo.items) {
      for (const linea of acomodar(item.texto, item.resaltados ?? [], anchoTexto)) filas.push({ tipo: 'linea', linea });
    }
  }
  const alto = RELLENO * 2 + filas.length * ALTO_LINEA;
  // Tan ancho como su línea más larga: un recuadro corto tapa menos el diagrama.
  const anchoLinea = (fila) => (fila.tipo === 'linea'
    ? Math.max(0, ...fila.linea.map((trozo) => trozo.x + medir(trozo.texto.trimEnd())))
    : medir(fila.texto, true));
  const ancho = Math.min(ANCHO_RECUADRO, Math.ceil(Math.max(...filas.map(anchoLinea))) + RELLENO * 2);
  let marcado = `<rect x="${x}" y="${y}" width="${ancho}" height="${alto}" fill="#f4f7fa" stroke="#8fa3b5"/>`;
  filas.forEach((fila, indice) => {
    const base = y + RELLENO + indice * ALTO_LINEA + 12;
    if (fila.tipo === 'grupo') {
      marcado += `<text x="${x + RELLENO}" y="${base}" font-size="${TAMANO}" font-weight="700" fill="#c4000c">${escapar(fila.texto)}</text>`;
    } else {
      fila.linea.forEach((trozo, posicion) => {
        const tx = x + RELLENO + trozo.x;
        if (trozo.resaltado && trozo.texto.trim()) {
          // Si la palabra siguiente también va resaltada, el amarillo cubre el espacio entre ambas.
          const sigue = fila.linea[posicion + 1]?.resaltado;
          const ancho = medir(sigue ? trozo.texto : trozo.texto.trimEnd());
          marcado += `<rect x="${tx}" y="${base - 12}" width="${ancho}" height="16" fill="#fff27a"/>`;
        }
        marcado += `<text x="${tx}" y="${base}" font-size="${TAMANO}" fill="#1d1d24" xml:space="preserve">${escapar(trozo.texto)}</text>`;
      });
    }
  });
  return { marcado, ancho, alto };
}

/** Recorte del diagrama alrededor de un operador, con el recuadro encima. */
function bloque(sentencia, nodo, posiciones, ancho, y, regla) {
  const objetivo = posiciones.get(nodo.id);
  const maximo = Math.max(...sentencia.nodos.map((n) => n.costoPct), 0);
  const filasDe = (n) => n.filasReales ?? n.filasEstimadas;
  const filasMaximas = Math.max(...sentencia.nodos.map((n) => filasDe(n) ?? 0), 1);
  const recorteX = Math.max(0, Math.min(objetivo.x - COLUMNA * 1.5, ancho - ANCHO_RECORTE));
  const recorteY = objetivo.y - 58;

  const diagrama = renderToStaticMarkup(
    <g>
      <DefinicionesIconos />
      {sentencia.nodos.filter((n) => n.padre !== null).map((n) => (
        <Flecha key={`f-${n.id}`} desde={posiciones.get(n.id)} hasta={posiciones.get(n.padre)} filas={filasDe(n)} filasMaximas={filasMaximas} desviada={filasDesviadas(n)} />
      ))}
      {sentencia.nodos.map((n) => (
        <Nodo
          key={n.id}
          nodo={n}
          posicion={posiciones.get(n.id)}
          maximo={maximo}
          activo={n.id === nodo.id}
          marcado={n.id === nodo.id}
          onEntrar={() => {}}
          onSalir={() => {}}
        />
      ))}
    </g>,
  );

  // El recuadro sale a la derecha del operador; si no entra en el recorte, a su izquierda.
  const xOperador = objetivo.x - recorteX;
  // Sin advertencias en el XML no hay recuadro: solo el operador marcado.
  const conRecuadro = contenidoRecuadro(nodo, regla).length > 0;
  const { marcado: contenidoRecuadroSvg, ancho: anchoRecuadro, alto } = conRecuadro
    ? recuadro(nodo, regla)
    : { marcado: '', ancho: 0, alto: 0 };
  // A la derecha del operador (la imagen se ensancha un poco si hace falta); a su
  // izquierda solo si ahí entra completo, para no tapar el operador ni su costo.
  const aLaDerecha = xOperador + 30;
  const aLaIzquierda = xOperador - 30 - anchoRecuadro;
  const xRecuadro = aLaDerecha + anchoRecuadro <= ANCHO_RECORTE + 160 || aLaIzquierda < 4 ? aLaDerecha : aLaIzquierda;
  const marcadoRecuadro = conRecuadro ? `<g transform="translate(${xRecuadro} ${y + 4})">${contenidoRecuadroSvg}</g>` : '';
  const yDiagrama = y + Math.max(alto - 40, 0);
  const anchoBloque = Math.max(ANCHO_RECORTE, xRecuadro + anchoRecuadro + 8);
  const marcado = `
    <svg x="0" y="${yDiagrama}" width="${ANCHO_RECORTE}" height="${ALTO_RECORTE}"
         viewBox="${recorteX} ${recorteY} ${ANCHO_RECORTE} ${ALTO_RECORTE}">${diagrama}</svg>
    <rect x="0.5" y="${yDiagrama + 0.5}" width="${anchoBloque - 1}" height="${ALTO_RECORTE - 1}" fill="none" stroke="#c9d3dc"/>
    ${marcadoRecuadro}`;
  return { marcado, alto: yDiagrama - y + ALTO_RECORTE, ancho: anchoBloque };
}

/**
 * Arma la imagen PNG de los operadores de un hallazgo (hasta 4, uno debajo de otro).
 * Devuelve { blob, url }.
 */
export async function crearCapturaPlan({ sentencia, nodoIds, archivo, regla }) {
  const { posiciones, ancho } = calcularPosiciones(sentencia.nodos);
  const nodos = nodoIds
    .map((id) => sentencia.nodos.find((n) => n.id === id))
    .filter(Boolean)
    .slice(0, MAXIMO_NODOS);
  if (!nodos.length) throw new Error('No se encontró el operador en el diagrama.');

  let y = ALTO_PESTANA + 8;
  let anchoTotal = ANCHO_RECORTE;
  const bloques = nodos.map((nodo) => {
    const resultado = bloque(sentencia, nodo, posiciones, ancho, y, regla);
    y += resultado.alto + SEPARACION;
    anchoTotal = Math.max(anchoTotal, resultado.ancho);
    return resultado.marcado;
  });
  const altoTotal = y - SEPARACION + 8;
  const pestana = `${archivo || 'plan.sqlplan'} · Consulta ${sentencia.numero}`;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${anchoTotal * ESCALA}" height="${altoTotal * ESCALA}"
      viewBox="0 0 ${anchoTotal} ${altoTotal}">
    <style>${ESTILOS}</style>
    <rect width="100%" height="100%" fill="#ffffff"/>
    <rect x="0" y="0" width="${Math.min(medir(pestana, true) + 44, anchoTotal)}" height="${ALTO_PESTANA}" fill="#2d2d30"/>
    <rect x="12" y="8" width="10" height="10" fill="none" stroke="#d4d4d4" stroke-width="1.4"/>
    <text x="30" y="17.5" font-size="${TAMANO}" font-weight="700" fill="#ffffff">${escapar(pestana)}</text>
    ${bloques.join('')}
  </svg>`;

  const imagen = new Image();
  imagen.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  await imagen.decode();
  const lienzo = document.createElement('canvas');
  lienzo.width = anchoTotal * ESCALA;
  lienzo.height = altoTotal * ESCALA;
  lienzo.getContext('2d').drawImage(imagen, 0, 0);
  const blob = await new Promise((resolver, rechazar) => {
    lienzo.toBlob((resultado) => (resultado ? resolver(resultado) : rechazar(new Error('No se pudo crear la imagen.'))), 'image/png');
  });
  return { blob, url: URL.createObjectURL(blob) };
}
