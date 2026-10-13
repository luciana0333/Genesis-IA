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
// Reglas cuya imagen es solo el cuadrito del operador, sin recuadro ni el resto del plan.
const REGLAS_COMPACTAS = new Set(['TABLE_SCAN_DETECTADO']);
const POR_FILA_COMPACTA = 4;
const ALTO_COMPACTO = 124; // del costo a la última línea del operador, sin la fila de abajo
const MAXIMO_COMPACTOS = 8;
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
const MAX_LINEAS_CODIGO = 8;

// Tipo de advertencia (del XML) que corresponde a cada regla: solo esa se resalta en su imagen.
const TIPOS_POR_REGLA = {
  CONVERSION_IMPLICITA_DETECTADA: ['conversion'],
  SPILL_TEMPDB_DETECTADO: ['spill'],
  MEMORIA_SOBREESTIMADA: ['memoria'],
};

function contenidoRecuadro(nodo, regla, sentencia) {
  // En la regla de tiempo el recuadro muestra el bloque y sus tiempos, no las advertencias.
  if (regla === 'TIEMPO_EJECUCION_SUPERADO') {
    const ms = (valor) => (valor == null ? '' : `${Math.round(valor).toLocaleString('en-US')} ms`);
    const lineas = (sentencia?.codigo ?? '').split('\n').filter((linea) => linea.trim());
    const codigo = lineas.slice(0, MAX_LINEAS_CODIGO).map((linea) => ({ texto: linea, resaltados: [] }));
    if (lineas.length > MAX_LINEAS_CODIGO) codigo.push({ texto: '…', resaltados: [] });
    return [
      {
        titulo: 'QueryTimeStats:',
        items: [
          { texto: `Elapsed Time: ${ms(sentencia?.duracionMs)}`, resaltados: [ms(sentencia?.duracionMs)] },
          { texto: `CPU Time: ${ms(sentencia?.cpuMs)}`, resaltados: [] },
        ],
      },
      { titulo: 'Statement:', items: codigo },
    ];
  }
  // Todas las advertencias del XML se muestran, pero solo se resalta la de la regla de la observación.
  const propias = TIPOS_POR_REGLA[regla];
  const items = nodo.advertencias.map((a) => (!propias || propias.includes(a.tipo) ? a : { ...a, resaltados: [] }));
  const grupos = items.length ? [{ titulo: 'Warnings:', items }] : [];
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
function recuadro(nodo, regla, sentencia) {
  const x = 0;
  const y = 0;
  const anchoTexto = ANCHO_RECUADRO - RELLENO * 2;
  const filas = [];
  for (const grupo of contenidoRecuadro(nodo, regla, sentencia)) {
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
function bloque(sentencia, nodo, posiciones, ancho, y, regla, x = 0) {
  const compacto = REGLAS_COMPACTAS.has(regla);
  const anchoRecorte = compacto ? COLUMNA : ANCHO_RECORTE;
  const objetivo = posiciones.get(nodo.id);
  const maximo = Math.max(...sentencia.nodos.map((n) => n.costoPct), 0);
  const filasDe = (n) => n.filasReales ?? n.filasEstimadas;
  const filasMaximas = Math.max(...sentencia.nodos.map((n) => filasDe(n) ?? 0), 1);
  const recorteX = compacto
    ? objetivo.x - COLUMNA / 2
    : Math.max(0, Math.min(objetivo.x - COLUMNA * 1.5, ancho - ANCHO_RECORTE));
  const altoRecorte = compacto ? ALTO_COMPACTO : ALTO_RECORTE;
  const recorteY = objetivo.y - (compacto ? 48 : 58);

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
          soloMarcado
          onEntrar={() => {}}
          onSalir={() => {}}
        />
      ))}
    </g>,
  );

  // El recuadro sale a la derecha del operador; si no entra en el recorte, a su izquierda.
  const xOperador = objetivo.x - recorteX;
  // Sin advertencias en el XML no hay recuadro: solo el operador marcado.
  const conRecuadro = !compacto && contenidoRecuadro(nodo, regla, sentencia).length > 0;
  const { marcado: contenidoRecuadroSvg, ancho: anchoRecuadro, alto } = conRecuadro
    ? recuadro(nodo, regla, sentencia)
    : { marcado: '', ancho: 0, alto: 0 };
  // A la derecha del operador (la imagen se ensancha un poco si hace falta); a su
  // izquierda solo si ahí entra completo, para no tapar el operador ni su costo.
  const aLaDerecha = xOperador + 30;
  const aLaIzquierda = xOperador - 30 - anchoRecuadro;
  const xRecuadro = aLaDerecha + anchoRecuadro <= ANCHO_RECORTE + 160 || aLaIzquierda < 4 ? aLaDerecha : aLaIzquierda;
  const marcadoRecuadro = conRecuadro ? `<g transform="translate(${xRecuadro} ${y + 4})">${contenidoRecuadroSvg}</g>` : '';
  const yDiagrama = y + Math.max(alto - 40, 0);
  const anchoBloque = compacto ? anchoRecorte : Math.max(ANCHO_RECORTE, xRecuadro + anchoRecuadro + 8);
  const marcado = `
    <svg x="${x}" y="${yDiagrama}" width="${anchoRecorte}" height="${altoRecorte}"
         viewBox="${recorteX} ${recorteY} ${anchoRecorte} ${altoRecorte}">${diagrama}</svg>
    <rect x="${x + 0.5}" y="${yDiagrama + 0.5}" width="${anchoBloque - 1}" height="${altoRecorte - 1}" fill="none" stroke="#c9d3dc"/>
    ${marcadoRecuadro}`;
  return { marcado, alto: yDiagrama - y + altoRecorte, ancho: anchoBloque };
}

/**
 * Arma la imagen PNG de los operadores de un hallazgo (hasta 4, uno debajo de otro).
 * grupos: [{ sentencia, nodoIds }], uno por consulta; si son varias, cada recorte lleva su etiqueta.
 * Devuelve { blob, url, ancho }.
 */
export async function crearCapturaPlan({ grupos, archivo, regla }) {
  const casos = grupos
    .flatMap(({ sentencia, nodoIds }) => nodoIds
      .map((id) => sentencia.nodos.find((n) => n.id === id))
      .filter(Boolean)
      .map((nodo) => ({ sentencia, nodo })))
    .slice(0, REGLAS_COMPACTAS.has(regla) ? MAXIMO_COMPACTOS : MAXIMO_NODOS);
  if (!casos.length) throw new Error('No se encontró el operador en el diagrama.');
  const compacto = REGLAS_COMPACTAS.has(regla);

  const variasConsultas = new Set(casos.map((c) => c.sentencia.numero)).size > 1;
  const geometrias = new Map();
  let y = ALTO_PESTANA + 8;
  let anchoTotal = compacto ? 0 : ANCHO_RECORTE;
  const etiquetaAlto = variasConsultas ? 20 : 0;
  const bloques = casos.map(({ sentencia, nodo }, indice) => {
    if (!geometrias.has(sentencia.numero)) geometrias.set(sentencia.numero, calcularPosiciones(sentencia.nodos));
    const { posiciones, ancho } = geometrias.get(sentencia.numero);
    // Compacto: cuadritos en filas de 4; si no, recortes uno debajo de otro.
    const x = compacto ? (indice % POR_FILA_COMPACTA) * (COLUMNA + SEPARACION) : 0;
    const yBloque = compacto
      ? ALTO_PESTANA + 8 + Math.floor(indice / POR_FILA_COMPACTA) * (ALTO_COMPACTO + etiquetaAlto + SEPARACION)
      : y;
    const etiqueta = variasConsultas
      ? `<text x="${x + 2}" y="${yBloque + 12}" font-size="${TAMANO}" font-weight="700" fill="#4a4a55">Consulta ${sentencia.numero}</text>`
      : '';
    const resultado = bloque(sentencia, nodo, posiciones, ancho, yBloque + etiquetaAlto, regla, x);
    if (compacto) {
      y = Math.max(y, yBloque + etiquetaAlto + resultado.alto + SEPARACION);
      anchoTotal = Math.max(anchoTotal, x + resultado.ancho);
    } else {
      y += etiquetaAlto + resultado.alto + SEPARACION;
      anchoTotal = Math.max(anchoTotal, resultado.ancho);
    }
    return etiqueta + resultado.marcado;
  });
  const altoTotal = y - SEPARACION + 8;
  const consultas = [...new Set(casos.map((c) => c.sentencia.numero))];
  const pestana = `${archivo || 'plan.sqlplan'} · ${consultas.length > 1 ? 'Consultas' : 'Consulta'} ${consultas.join(', ')}`;
  // La imagen nunca es más angosta que su pestaña (un solo cuadrito compacto es estrecho).
  anchoTotal = Math.max(anchoTotal, medir(pestana, true) + 44);

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
  // ancho: tamaño real en pantalla (la imagen se genera al doble para que se vea nítida al pegarla).
  return { blob, url: URL.createObjectURL(blob), ancho: anchoTotal };
}
