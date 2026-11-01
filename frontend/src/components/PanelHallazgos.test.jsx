import { render, screen } from '@testing-library/react';
import { PanelHallazgos } from './PanelHallazgos';

const TEXTOS = { cargando: '', sinHallazgos: '', tituloError: '', inicialTitulo: '', pasos: [] };

const NORMAL = {
  regla: 'CONVERSION_IMPLICITA_DETECTADA',
  severidad: 'alto',
  linea: 1,
  mensaje: 'Se ha identificado una conversión implícita en el operador SELECT. Se recomienda revisar la alerta.',
};

const RIESGO = {
  regla: 'CONVERSION_TEXTO_A_NUMERO',
  severidad: 'medio',
  linea: 1,
  complementario: true,
  mensaje: "Se identificó una comparación en la que un texto se convierte implícitamente a número: "
    + "«SUBSTRING(cCtaCod, 9, 1) = 1» → «SUBSTRING(cCtaCod, 9, 1) = '1'» (consulta 2). Se recomienda comparar "
    + 'con un valor de texto, como se indica, ya que si el dato no es numérico la consulta generará un error de '
    + 'conversión.',
};

describe('PanelHallazgos · riesgos identificados por Genesis', () => {
  it('van aparte, debajo de las demás observaciones, con su encabezado', () => {
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[RIESGO, NORMAL]} mostrarLinea={false} />);
    const encabezado = screen.getByRole('heading', { name: 'Riesgos identificados por Genesis' });
    expect(screen.getByText('Análisis complementario')).toBeInTheDocument();
    const titulos = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent);
    expect(titulos).toEqual(['Conversión implícita detectada', 'Conversión de texto a número']);
    // La ficha del riesgo está después del encabezado; la normal, antes.
    const fichaRiesgo = screen.getByRole('heading', { name: 'Conversión de texto a número' });
    const fichaNormal = screen.getByRole('heading', { name: 'Conversión implícita detectada' });
    expect(encabezado.compareDocumentPosition(fichaRiesgo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(encabezado.compareDocumentPosition(fichaNormal) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
  });

  it('sin riesgos de Genesis no aparece la sección', () => {
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[NORMAL]} mostrarLinea={false} />);
    expect(screen.queryByText('Riesgos identificados por Genesis')).not.toBeInTheDocument();
  });
});
