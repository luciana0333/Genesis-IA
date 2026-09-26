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
