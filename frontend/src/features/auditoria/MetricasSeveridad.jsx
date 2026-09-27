import { TarjetaMetrica } from '../../components/TarjetaMetrica';

const TARJETAS = [
  { severidad: 'critico', titulo: 'Críticos' },
  { severidad: 'alto', titulo: 'Altos' },
  { severidad: 'medio', titulo: 'Medios' },
  { severidad: 'bajo', titulo: 'Bajos' },
];

export function MetricasSeveridad({ conteo, subtitulos }) {
  return (
    <section className="metrics-grid" aria-label="Resumen por severidad">
      {TARJETAS.map(({ severidad, titulo }, indice) => (
        <TarjetaMetrica
          key={severidad}
          titulo={titulo}
          severidad={severidad}
          valor={conteo[severidad]}
          subtitulo={subtitulos[indice]}
        />
      ))}
    </section>
  );
}
