/** Íconos SVG de la interfaz (trazo heredado del color del texto). */

function Icono({ grosor = 2, className, children }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={grosor}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const IconoLuna = (props) => (
  <Icono {...props}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></Icono>
);

export const IconoSol = (props) => (
  <Icono {...props}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </Icono>
);

export const IconoEjecutar = (props) => (
  <Icono {...props}><path d="M7 4.5v15l12-7.5-12-7.5z" /></Icono>
);

export const IconoLimpiar = (props) => (
  <Icono {...props}>
    <path d="M3 6h18M8 6V4h8v2m-9 0 1 14h8l1-14" />
  </Icono>
);

export const IconoRestaurar = (props) => (
  <Icono {...props}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
  </Icono>
);

export const IconoSubir = (props) => (
  <Icono {...props}>
    <path d="M12 16V4m0 0-5 5m5-5 5 5" />
    <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
  </Icono>
);

export const IconoArchivo = (props) => (
  <Icono {...props}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5z" />
    <path d="M14 3v5h5M9 13h6m-6 4h4" />
  </Icono>
);

export const IconoCerrar = (props) => (
  <Icono {...props}><path d="M18 6 6 18M6 6l12 12" /></Icono>
);

export const IconoEscudoCheck = (props) => (
  <Icono {...props}>
    <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3z" />
    <path d="m9 12 2 2 4-4" />
  </Icono>
);

export const IconoBandeja = (props) => (
  <Icono {...props}>
    <path d="M22 12h-6l-2 3h-4l-2-3H2" />
    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </Icono>
);

export const IconoErrorCirculo = (props) => (
  <Icono {...props}>
    <circle cx="12" cy="12" r="9" />
    <path d="M15 9l-6 6M9 9l6 6" />
  </Icono>
);

export const IconoBaseDatos = (props) => (
  <Icono {...props}>
    <ellipse cx="12" cy="5" rx="8" ry="3" />
    <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
    <path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3" />
  </Icono>
);

export const IconoAdvertencia = () => (
  <Icono grosor={2.5}>
    <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </Icono>
);

export const IconoAlerta = () => (
  <Icono grosor={2.5}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </Icono>
);

export const IconoInformacion = () => (
  <Icono grosor={2.5}><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></Icono>
);

export const IconoCheck = () => (
  <Icono grosor={2.5}><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></Icono>
);

export const IconoRejilla = () => (
  <Icono><path d="M8 4v16M16 4v16M4 8h16M4 16h16" /></Icono>
);

export const IconoMemoria = () => (
  <Icono><path d="M4 7h16v10H4zM8 4v3m8-3v3M8 17v3m8-3v3" /></Icono>
);

export const IconoBarras = () => (
  <Icono><path d="M4 19h16M6 16V9m4 7V5m4 11v-4m4 4V7" /></Icono>
);

export const IconoHallazgo = () => (
  <Icono grosor={2.5}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5m0 3h.01" />
  </Icono>
);
