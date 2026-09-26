import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { IconoAdvertencia, IconoAlerta, IconoCheck, IconoInformacion } from '../../components/Iconos';

const TARJETAS = [
  { severidad: 'critico', titulo: 'Críticos', icono: <IconoAdvertencia /> },
  { severidad: 'alto', titulo: 'Altos', icono: <IconoAlerta /> },
  { severidad: 'medio', titulo: 'Medios', icono: <IconoInformacion /> },
  { severidad: 'bajo', titulo: 'Bajos', icono: <IconoCheck /> },
];

export function MetricasSeveridad({ conteo, subtitulos }) {
  const total = Object.values(conteo).reduce((suma, valor) => suma + valor, 0);
  return (
    <section className="metrics-grid" aria-label="Resumen por severidad">
      {TARJETAS.map(({ severidad, titulo, icono }, indice) => (
        <TarjetaMetrica
          key={severidad}
          tono={severidad}
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
