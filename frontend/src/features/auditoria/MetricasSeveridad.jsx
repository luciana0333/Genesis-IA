import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import {
  IconoSeveridadAlta,
  IconoSeveridadBaja,
  IconoSeveridadCritica,
  IconoSeveridadMedia,
} from '../../components/Iconos';

const TARJETAS = [
  { severidad: 'critico', titulo: 'Críticos', icono: <IconoSeveridadCritica /> },
  { severidad: 'alto', titulo: 'Altos', icono: <IconoSeveridadAlta /> },
  { severidad: 'medio', titulo: 'Medios', icono: <IconoSeveridadMedia /> },
  { severidad: 'bajo', titulo: 'Bajos', icono: <IconoSeveridadBaja /> },
];

export function MetricasSeveridad({ conteo, subtitulos }) {
  return (
    <section className="metrics-grid" aria-label="Resumen por severidad">
      {TARJETAS.map(({ severidad, titulo, icono }, indice) => (
        <TarjetaMetrica
          key={severidad}
          titulo={titulo}
          icono={icono}
          valor={conteo[severidad]}
          subtitulo={subtitulos[indice]}
        />
      ))}
    </section>
  );
}
