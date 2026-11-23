import { BarraNavegacion } from './components/BarraNavegacion';
import { Hero } from './components/Hero';
import { PiePagina } from './components/PiePagina';
import { AuditoriaWorkspace } from './features/auditoria/AuditoriaWorkspace';
import { BitbucketWorkspace } from './features/bitbucket/BitbucketWorkspace';
import { PlanesWorkspace } from './features/planes/PlanesWorkspace';
import { ValidacionWorkspace } from './features/validacion/ValidacionWorkspace';
import { useTema } from './hooks/useTema';
import { useVistaActiva } from './hooks/useVistaActiva';

export default function App() {
  const { tema, alternarTema } = useTema();
  const { vista } = useVistaActiva();
  const esModulo = !vista.esPlan && !vista.esValidacion && !vista.esBitbucket;

  return (
    <>
      <BarraNavegacion vistaActiva={vista} tema={tema} onAlternarTema={alternarTema} />

      {/* Bitbucket tiene su propia portada; se mantiene montada para conservar la lista al ir a un módulo y volver. */}
      <div hidden={!vista.esBitbucket}>
        <BitbucketWorkspace />
      </div>

      {!vista.esBitbucket && <Hero key={vista.id} {...vista.hero} />}

      <main className="main-wrapper" hidden={vista.esBitbucket}>
        {/* Planes se mantiene montado para conservar el archivo y el análisis al cambiar de pestaña. */}
        <div hidden={!vista.esPlan}>
          <PlanesWorkspace />
        </div>

        {vista.esValidacion && <ValidacionWorkspace />}

        {esModulo && (
          // La key reinicia el formulario y los resultados al cambiar de pestaña.
          <AuditoriaWorkspace key={vista.id} vista={vista} />
        )}
      </main>

      <PiePagina />
    </>
  );
}
