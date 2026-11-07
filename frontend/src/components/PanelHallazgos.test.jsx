import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

const TIPOS = {
  regla: 'TIPO_DISTINTO_ENTRE_TEMPORALES',
  severidad: 'medio',
  linea: 3,
  mensaje: 'Se identificaron las siguientes columnas con diferentes tipos de datos o longitudes entre las tablas '
    + "temporales: 'cCodAge': VARCHAR(3) en 2 tablas temporales y VARCHAR(5) en #FIN; "
    + "'cCalifInt': CHAR(5) en #A y VARCHAR(10) en @B. Se recomienda validar los tipos de datos.",
  grupos: [
    {
      nombre: 'cCodAge', tipo: 'Columna', lineas: [3, 9], etiquetas: ['VARCHAR(3)', 'VARCHAR(5)'],
      detalle: [{ tipo: 'VARCHAR(3)', tablas: ['#TEMPDN', '#MOVCS'] }, { tipo: 'VARCHAR(5)', tablas: ['#FIN'] }],
    },
    {
      nombre: 'cCalifInt', tipo: 'Columna', lineas: [4, 5], etiquetas: ['CHAR(5)', 'VARCHAR(10)'],
      detalle: [{ tipo: 'CHAR(5)', tablas: ['#A'] }, { tipo: 'VARCHAR(10)', tablas: ['@B'] }],
    },
  ],
};

describe('PanelHallazgos · «Ver tablas» de «Misma columna con distinto tipo»', () => {
  it('despliega la tablita Tipo | Tablas temporales y cuenta las columnas en el encabezado', async () => {
    const usuario = userEvent.setup();
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[TIPOS]} />);
    expect(screen.getByText('2 columnas')).toBeInTheDocument();
    // Solo la columna con un tipo en varias temporales tiene botón: en la otra los nombres ya están en la viñeta.
    const botones = screen.getAllByRole('button', { name: 'Ver tablas' });
    expect(botones).toHaveLength(1);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    await usuario.click(botones[0]);
    const filas = screen.getAllByRole('row').map((fila) => fila.textContent);
    expect(filas).toEqual([
      'Tipo de datoTablas temporales',
      'VARCHAR(3)2 tablas · 67%#TEMPDN#MOVCS',
      'VARCHAR(5)1 tabla · 33%#FIN',
    ]);
    // Cabecera: la columna, el tipo de diferencia (VARCHAR con distinto tamaño) y los indicadores.
    expect(screen.getByText('Distinta longitud')).toBeInTheDocument();
    expect(screen.getByText('Tipos').nextSibling).toHaveTextContent('2');
    expect(screen.getByText('Tablas').nextSibling).toHaveTextContent('3');
    await usuario.click(screen.getByRole('button', { name: 'Ocultar tablas' }));
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
