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
  const total = Object.values(conteo).reduce((suma, valor) => suma + valor, 0);
  return (
    <section className="metrics-grid" aria-label="Resumen por severidad">
      {TARJETAS.map(({ severidad, titulo, icono }, indice) => (
        <TarjetaMetrica
          key={severidad}
          titulo={titulo}
          icono={icono}
          valor={conteo[severidad]}
          subtitulo={subtitulos[indice]}
          proporcion={total ? conteo[severidad] / total : 0}
        />
      ))}
    </section>
  );
}
