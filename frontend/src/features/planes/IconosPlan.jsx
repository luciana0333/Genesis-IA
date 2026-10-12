/*
 * Íconos de los operadores del plan, dibujados en el estilo de SQL Sentry Plan
 * Explorer (azul grisáceo, relleno claro y barra superior). Se definen una vez
 * como <symbol> dentro del SVG y cada nodo los usa con <use href="#op-...">.
 * Son propios: imitan la forma y los tonos, no copian los de SolarWinds ni SSMS.
 */

const T = '#5b7a93'; // trazo
const B = '#7d98ae'; // barra superior
const F = '#f7fafc'; // relleno claro
const M = '#c9d8e4'; // relleno medio
const A = '#4f6f88'; // flechas y acentos
const W = { strokeWidth: 1.3 };

/** Hoja con barra superior: base de muchos operadores. */
function Hoja({ x = 6, y = 4, ancho = 20, alto = 24 }) {
  return (
    <>
      <rect x={x} y={y} width={ancho} height={alto} fill={F} stroke={T} {...W} />
      <rect x={x} y={y} width={ancho} height={5} fill={B} />
    </>
  );
}

/** Árbol de un índice (raíz y tres hojas); con corchetes si es clúster. */
function Arbol({ cluster = false, resaltar = null }) {
  return (
    <>
      {cluster && <path d="M5 7H3v16h2M27 7h2v16h-2" fill="none" stroke={T} strokeWidth={1.5} />}
      <rect x={13} y={3} width={6} height={5} fill={M} stroke={T} strokeWidth={1.1} />
      <path d="M16 8v2.5M9 10.5h14M9 10.5V13M16 10.5V13M23 10.5V13" stroke={T} strokeWidth={1.1} />
      {[6, 13, 20].map((x) => (
        <rect key={x} x={x} y={13} width={6} height={5} fill={x === resaltar ? '#ffd76a' : F} stroke={T} strokeWidth={1.1} />
      ))}
    </>
  );
}

/** Rejilla de tabla con encabezado. */
function Tabla({ x = 4, y = 5, ancho = 24, alto = 16 }) {
  return (
    <>
      <rect x={x} y={y} width={ancho} height={alto} fill={F} stroke={T} {...W} />
      <rect x={x} y={y} width={ancho} height={4} fill={B} />
      <path
        d={`M${x} ${y + 8}h${ancho}M${x} ${y + 12}h${ancho}M${x + ancho / 3} ${y + 4}v${alto - 4}M${x + (2 * ancho) / 3} ${y + 4}v${alto - 4}`}
        stroke={M}
      />
    </>
  );
}

const FlechaDerecha = ({ y = 26, desde = 9, hasta = 23 }) => (
  <>
    <path d={`M${desde} ${y}H${hasta}`} stroke={A} strokeWidth={2.2} />
    <path d={`M${hasta - 1} ${y - 3.5}l5 3.5-5 3.5z`} fill={A} />
  </>
);
const FlechaAbajo = ({ x = 23, desde = 18, hasta = 26 }) => (
  <>
    <path d={`M${x} ${desde}V${hasta}`} stroke={A} strokeWidth={2.2} />
    <path d={`M${x - 3.5} ${hasta - 1}l3.5 5 3.5-5z`} fill={A} />
  </>
);
const FlechaArriba = ({ x = 16, desde = 30, hasta = 20 }) => (
  <>
    <path d={`M${x} ${desde}V${hasta}`} stroke={A} strokeWidth={2.2} />
    <path d={`M${x - 3.5} ${hasta + 1}l3.5-5 3.5 5z`} fill={A} />
  </>
);
const Lineas = ({ x = 9.5, y = 13, ancho = 13, n = 3 }) => (
  <path d={Array.from({ length: n }, (_, i) => `M${x} ${y + i * 4}h${ancho}`).join('')} stroke={T} strokeWidth={1.2} />
);

const SIMBOLOS = {
  // Sentencias
  'raiz-select': <><Hoja /><path d="M9.5 14h13M9.5 18h13M9.5 22h9" stroke={T} strokeWidth={1.2} strokeDasharray="1.4 1.2" /></>,
  'raiz-dml': (
    <>
      <Hoja x={10} ancho={18} />
      <path d="M13 14h12M13 18h12M13 22h8" stroke={T} strokeWidth={1.2} strokeDasharray="1.4 1.2" />
      <path d="M2 17h8" stroke={A} strokeWidth={2.4} />
      <path d="M8 13.5l4 3.5-4 3.5z" fill={A} />
    </>
  ),
  // Lecturas
  'table-scan': <><Tabla /><FlechaDerecha /></>,
  'index-scan': <><Arbol /><path d="M9 18v8h13" fill="none" stroke={A} strokeWidth={2.2} /><path d="M21 22.5l5 3.5-5 3.5z" fill={A} /></>,
  'clustered-index-scan': <><Arbol cluster /><path d="M9 18v8h13" fill="none" stroke={A} strokeWidth={2.2} /><path d="M21 22.5l5 3.5-5 3.5z" fill={A} /></>,
  'index-seek': <><Arbol resaltar={20} /><FlechaAbajo x={23} desde={19} hasta={25} /></>,
  'clustered-index-seek': <><Arbol cluster resaltar={20} /><FlechaAbajo x={23} desde={19} hasta={25} /></>,
  'key-lookup': (
    <>
      <Arbol cluster />
      <circle cx={11} cy={25} r={3} fill="#ffd76a" stroke={A} strokeWidth={1.3} />
      <path d="M14 25h11M22 25v3M25 25v3" stroke={A} strokeWidth={1.6} />
    </>
  ),
  'rid-lookup': (
    <>
      <Tabla y={3} alto={14} />
      <circle cx={11} cy={25} r={3} fill="#ffd76a" stroke={A} strokeWidth={1.3} />
      <path d="M14 25h11M22 25v3M25 25v3" stroke={A} strokeWidth={1.6} />
    </>
  ),
  'constant-scan': <><Hoja /><text x={16} y={23} textAnchor="middle" fontSize={11} fontWeight={700} fill={A} fontFamily="Segoe UI, Arial">C</text></>,
  // Combinaciones
  'nested-loops': (
    <>
      <rect x={4} y={5} width={13} height={9} fill={F} stroke={T} {...W} />
      <rect x={4} y={5} width={13} height={3} fill={B} />
      <rect x={4} y={18} width={13} height={9} fill={F} stroke={T} {...W} />
      <rect x={4} y={18} width={13} height={3} fill={B} />
      <path d="M21 9.5h5v13h-5" fill="none" stroke={A} strokeWidth={2} />
      <path d="M22 19l-4 3.5 4 3.5z" fill={A} />
    </>
  ),
  'hash-match': (
    <>
      <rect x={3} y={8} width={11} height={14} fill={F} stroke={T} strokeWidth={1.2} />
      <rect x={3} y={8} width={11} height={3} fill={B} />
      <path d="M5 14.5h7M5 18h7" stroke={T} />
      <rect x={18} y={8} width={11} height={14} fill={F} stroke={T} strokeWidth={1.2} />
      <rect x={18} y={8} width={11} height={3} fill={B} />
      <path d="M20 14.5h7M20 18h7" stroke={T} />
      <path d="M14 15h4" stroke={A} strokeWidth={2} />
      <path d="M8.5 22v5h15v-5" fill="none" stroke={A} strokeWidth={1.6} />
    </>
  ),
  'merge-join': (
    <>
      <Hoja />
      <path d="M10 12l6 6 6-6" fill="none" stroke={T} strokeWidth={1.6} />
      <FlechaAbajo x={16} desde={18} hasta={23} />
    </>
  ),
  concatenation: (
    <>
      <rect x={3} y={4} width={11} height={11} fill={F} stroke={T} strokeWidth={1.2} />
      <rect x={3} y={17} width={11} height={11} fill={F} stroke={T} strokeWidth={1.2} />
      <path d="M14 9.5h5v13h-5M19 16h4" fill="none" stroke={A} strokeWidth={1.8} />
      <rect x={23} y={11} width={7} height={10} fill={M} stroke={T} strokeWidth={1.2} />
    </>
  ),
  // Transformaciones
  sort: (
    <>
      <Hoja x={5} ancho={22} />
      <text x={8.5} y={17} fontSize={7} fontWeight={700} fill={A} fontFamily="Segoe UI, Arial">A</text>
      <text x={8.5} y={25} fontSize={7} fontWeight={700} fill={A} fontFamily="Segoe UI, Arial">Z</text>
      <Lineas x={14} y={13} ancho={5} n={4} />
      <FlechaAbajo x={22.5} desde={12} hasta={21} />
    </>
  ),
  'compute-scalar': (
    <>
      <Hoja />
      <g fill={M} stroke={T} strokeWidth={0.8}>
        {[12, 17, 22].flatMap((y) => [9, 14, 19].map((x) => <rect key={`${x}-${y}`} x={x} y={y} width={4} height={3} />))}
      </g>
    </>
  ),
  'stream-aggregate': <><Hoja /><text x={16} y={24} textAnchor="middle" fontSize={13} fontWeight={700} fill={A} fontFamily="Segoe UI, Arial">Σ</text></>,
  filter: (
    <>
      <Hoja x={4} y={6} ancho={24} alto={20} />
      <path d="M9 13h14l-5 5.5v5.5l-4-2v-3.5z" fill={M} stroke={T} strokeWidth={1.2} strokeLinejoin="round" />
    </>
  ),
  top: <><Hoja /><path d="M10 13h12" stroke={A} strokeWidth={2} /><FlechaArriba x={16} desde={25} hasta={17} /></>,
  spool: <><Hoja /><Lineas x={10} y={13} ancho={12} n={3} /><path d="M10 25h12" stroke={A} strokeWidth={2.4} /></>,
  parallelism: (
    <>
      <Hoja />
      <path d="M10 22l6-7 6 7" fill="none" stroke={A} strokeWidth={2} />
      <path d="M16 15v-3" stroke={A} strokeWidth={2} />
    </>
  ),
  segment: <><Hoja /><path d="M9.5 14h13M9.5 19.5h13" stroke={A} strokeWidth={1.8} /><Lineas x={9.5} y={23.5} ancho={9} n={1} /></>,
  assert: <><Hoja /><text x={16} y={25} textAnchor="middle" fontSize={13} fontWeight={700} fill={A} fontFamily="Segoe UI, Arial">!</text></>,
  sequence: <><Hoja x={7} y={9} ancho={19} alto={19} /><path d="M12 3h12v4" fill="none" stroke={T} strokeWidth={1.2} /><path d="M16.5 14v10M11.5 19h10" stroke={A} strokeWidth={2.2} /></>,
  // Escrituras
  'clustered-index-insert': <><Arbol cluster /><FlechaArriba x={16} desde={30} hasta={20} /></>,
  'index-insert': <><Arbol /><FlechaArriba x={16} desde={30} hasta={20} /></>,
  'table-insert': <><Tabla /><path d="M16 24v6M13 27h6" stroke={A} strokeWidth={2.2} /></>,
  generico: <><Hoja /><Lineas /></>,
};

/** <defs> con todos los íconos; va dentro de cada SVG que dibuja el plan. */
export function DefinicionesIconos() {
  return (
    <defs>
      {Object.entries(SIMBOLOS).map(([id, contenido]) => (
        <symbol key={id} id={`op-${id}`} viewBox="0 0 32 32">{contenido}</symbol>
      ))}
    </defs>
  );
}
