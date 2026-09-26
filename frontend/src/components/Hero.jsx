import { etiquetaSeveridad } from '../config/reglas';

const PALABRAS_CLAVE = /\b(EXEC|CREATE|ALTER|TABLE|PROCEDURE|AS|BEGIN|END|SELECT|FROM|ORDER|BY|DECLARE|WHILE|BREAK|INT|VARCHAR|DATETIME|IDENTITY|NOT|NULL)\b/;
const TOKEN = /(N?'[^']*'|"[^"]*"|@\w+|<\/?[\w]+|\b(?:EXEC|CREATE|ALTER|TABLE|PROCEDURE|AS|BEGIN|END|SELECT|FROM|ORDER|BY|DECLARE|WHILE|BREAK|INT|VARCHAR|DATETIME|IDENTITY|NOT|NULL)\b|\b\d+\b)/g;

/** Resaltado de sintaxis mínimo para la vista previa decorativa. */
function LineaCodigo({ texto }) {
  return texto.split(TOKEN).map((parte, indice) => {
    if (!parte) return null;
    let clase;
    if (/^N?'/.test(parte) || /^"/.test(parte)) clase = 'tk-cadena';
    else if (parte.startsWith('@')) clase = 'tk-parametro';
    else if (parte.startsWith('<')) clase = 'tk-etiqueta';
    else if (PALABRAS_CLAVE.test(parte)) clase = 'tk-clave';
    else if (/^\d+$/.test(parte)) clase = 'tk-numero';
    return clase ? <span key={indice} className={clase}>{parte}</span> : parte;
  });
}

/** Ventana de código con hallazgos de ejemplo: ilustra la revisión. */
function VistaPrevia({ muestra }) {
  return (
    <div className="hero-visual" aria-hidden="true">
      <div className="hv-window">
        <div className="hv-bar">
          <span className="hv-dot" />
          <span className="hv-dot" />
          <span className="hv-dot" />
          <span className="hv-file">{muestra.archivo}</span>
        </div>
        <pre className="hv-code">
          {muestra.lineas.map((linea, indice) => (
            <span
              key={indice}
              className={muestra.marcadas.includes(indice) ? 'hv-line hv-line--marcada' : 'hv-line'}
            >
              <span className="hv-num">{indice + 1}</span>
              <LineaCodigo texto={linea} />
            </span>
          ))}
        </pre>
      </div>

      <div className="hv-card">
        <div className="hv-card-head">
          <span className="hv-card-count">{muestra.hallazgos.length}</span>
          <span>
            <strong>Hallazgos detectados</strong>
            <small>Revisión automática</small>
          </span>
        </div>
        {muestra.hallazgos.map((hallazgo) => (
          <div key={hallazgo.texto} className={`hv-item sev-${hallazgo.severidad}`}>
            <span className="hv-item-sev">{etiquetaSeveridad(hallazgo.severidad)}</span>
            <span className="hv-item-text">{hallazgo.texto}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Hero({ titulo, complemento, descripcion, seccion, muestra }) {
  return (
    <section className="hero">
      <span className="hero-grid" aria-hidden="true" />
      <span className="hero-shape hero-shape--a" aria-hidden="true" />
      <span className="hero-shape hero-shape--b" aria-hidden="true" />
      <span className="hero-shape hero-shape--c" aria-hidden="true" />
      <div className="hero-container">
        <div className="hero-text">
          <p className="hero-eyebrow">
            <span>Auditoría inteligente</span>
            <span className="hero-eyebrow-sep" aria-hidden="true" />
            <span>{seccion}</span>
          </p>
          <h1>
            {titulo}
            {complemento && <span className="hero-complemento">{complemento}</span>}
          </h1>
          <p className="hero-descripcion">{descripcion}</p>
        </div>
        {muestra && <VistaPrevia muestra={muestra} />}
      </div>
    </section>
  );
}
