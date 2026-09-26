/**
 * Íconos de la interfaz (librería Lucide).
 *
 * Toda la app importa los íconos desde aquí, con nombres del dominio. Así el
 * trazo y el tamaño son uniformes y cambiar de librería solo toca este archivo.
 */
import {
  Check,
  CircleAlert,
  CircleX,
  CloudUpload,
  Copy,
  Database,
  Eraser,
  FileCode2,
  Gauge,
  Inbox,
  Info,
  ListChecks,
  MemoryStick,
  Moon,
  OctagonAlert,
  Play,
  RotateCcw,
  ShieldCheck,
  Sun,
  TriangleAlert,
  Workflow,
  X,
} from 'lucide-react';

const TRAZO = 1.75;

function crearIcono(Componente) {
  function Icono({ className }) {
    return <Componente className={className} strokeWidth={TRAZO} aria-hidden="true" focusable="false" />;
  }
  Icono.displayName = `Icono(${Componente.displayName ?? 'Lucide'})`;
  return Icono;
}

// Navegación y acciones
export const IconoLuna = crearIcono(Moon);
export const IconoSol = crearIcono(Sun);
export const IconoEjecutar = crearIcono(Play);
export const IconoLimpiar = crearIcono(Eraser);
export const IconoRestaurar = crearIcono(RotateCcw);
export const IconoSubir = crearIcono(CloudUpload);
export const IconoArchivo = crearIcono(FileCode2);
export const IconoCerrar = crearIcono(X);
export const IconoBaseDatos = crearIcono(Database);
export const IconoCopiar = crearIcono(Copy);
export const IconoCopiado = crearIcono(Check);

// Estados
export const IconoEscudoCheck = crearIcono(ShieldCheck);
export const IconoBandeja = crearIcono(Inbox);
export const IconoErrorCirculo = crearIcono(CircleX);

// Severidades
export const IconoSeveridadCritica = crearIcono(OctagonAlert);
export const IconoSeveridadAlta = crearIcono(TriangleAlert);
export const IconoSeveridadMedia = crearIcono(CircleAlert);
export const IconoSeveridadBaja = crearIcono(Info);

// Métricas del plan de ejecución
export const IconoRejilla = crearIcono(Workflow);
export const IconoMemoria = crearIcono(MemoryStick);
export const IconoBarras = crearIcono(Gauge);
export const IconoHallazgo = crearIcono(ListChecks);
