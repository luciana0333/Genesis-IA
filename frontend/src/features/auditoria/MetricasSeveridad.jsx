import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { IconoAdvertencia, IconoAlerta, IconoCheck, IconoInformacion } from '../../components/Iconos';

const TARJETAS = [
  { severidad: 'critico', variante: 'critical', titulo: 'Críticos', icono: <IconoAdvertencia /> },
  { severidad: 'alto', variante: 'high', titulo: 'Altos', icono: <IconoAlerta /> },
  { severidad: 'medio', variante: 'medium', titulo: 'Medios', icono: <IconoInformacion /> },
  { severidad: 'bajo', variante: 'low', titulo: 'Bajos', icono: <IconoCheck /> },
];

export function MetricasSeveridad({ conteo, subtitulos }) {
  return (
    <section className="services-grid" aria-label="Resumen por severidad">
      {TARJETAS.map(({ severidad, ...tarjeta }, indice) => (
        <TarjetaMetrica
          key={severidad}
          {...tarjeta}
          valor={conteo[severidad]}
          subtitulo={subtitulos[indice]}
        />
      ))}
    </section>
  );
}
