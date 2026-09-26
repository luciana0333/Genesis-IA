import { BarraNavegacion } from './components/BarraNavegacion';
import { Hero } from './components/Hero';
import { AuditoriaWorkspace } from './features/auditoria/AuditoriaWorkspace';
import { PlanesWorkspace } from './features/planes/PlanesWorkspace';
import { useTema } from './hooks/useTema';
import { useVistaActiva } from './hooks/useVistaActiva';

export default function App() {
  const { alternarTema } = useTema();
  const { vista, navegar } = useVistaActiva();

  return (
    <>
      <BarraNavegacion vistaActiva={vista} onAlternarTema={alternarTema} />
      <Hero {...vista.hero} />

      <main className="main-wrapper">
        {/* Planes se mantiene montado para conservar el archivo y el análisis al cambiar de pestaña. */}
        <div hidden={!vista.esPlan}>
          <PlanesWorkspace />
        </div>

        {!vista.esPlan && (
          // La key reinicia el formulario y los resultados al cambiar de pestaña.
          <AuditoriaWorkspace key={vista.id} vista={vista} onNavegar={navegar} />
        )}
      </main>
    </>
  );
}
