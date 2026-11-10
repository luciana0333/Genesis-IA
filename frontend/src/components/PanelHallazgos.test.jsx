import { render, screen, within } from '@testing-library/react';
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
  mensaje: 'Se identificó una conversión implícita sobre la comparación SUBSTRING(cCtaCod, 9, 1) = 1. Se recomienda '
    + "comparar con un valor de texto ('1'), validando que el resultado no cambie, ya que un valor no numérico "
    + 'genera un error de conversión.',
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
      detalle: [
        { tipo: 'VARCHAR(3)', tablas: ['#TEMPDN', '#MOVCS'], lineas: [3, 6] },
        { tipo: 'VARCHAR(5)', tablas: ['#FIN'], lineas: [9] },
      ],
    },
    {
      nombre: 'cCalifInt', tipo: 'Columna', lineas: [4, 5], etiquetas: ['CHAR(5)', 'VARCHAR(10)'],
      detalle: [{ tipo: 'CHAR(5)', tablas: ['#A'] }, { tipo: 'VARCHAR(10)', tablas: ['@B'] }],
    },
  ],
};

describe('PanelHallazgos · «Misma columna con distinto tipo» como tabla', () => {
  it('muestra una fila por columna con su desglose y abre el detalle con «Ver tablas»', async () => {
    const usuario = userEvent.setup();
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[TIPOS]} />);
    expect(screen.getByText('2 columnas')).toBeInTheDocument();
    // La introducción va bajo el título; la lista de viñetas se reemplaza por la tabla.
    expect(screen.getByText(/^Se identificaron las siguientes columnas/)).toBeInTheDocument();
    const tabla = screen.getByRole('table');
    const filas = within(tabla).getAllByRole('row').map((fila) => fila.textContent);
    expect(filas).toEqual([
      'Nombre columnaDesglose de tipos y ocurrenciasDetalles',
      'cCodAgeVARCHAR(3) en 2 tablasvsVARCHAR(5) en #FINVer tablas',
      'cCalifIntCHAR(5) en #AvsVARCHAR(10) en @B',
    ]);
    // El tipo más usado va en gris; el que se sale, en rojo.
    expect(within(tabla).getByText('VARCHAR(3)').parentElement).not.toHaveClass('distinto');
    expect(within(tabla).getByText('VARCHAR(5)').parentElement).toHaveClass('distinto');
    // Solo la columna con un tipo en varias temporales tiene «Ver tablas».
    const botones = screen.getAllByRole('button', { name: 'Ver tablas' });
    expect(botones).toHaveLength(1);
    await usuario.click(botones[0]);
    expect(screen.getByText('Distinta longitud')).toBeInTheDocument();
    expect(screen.getByText('Tipos').nextSibling).toHaveTextContent('2');
    expect(screen.getByText('Tablas').nextSibling).toHaveTextContent('3');
    // Una fila por tipo con sus temporales (solo los nombres; para ir al código está «Ver en el código»).
    const detalle = screen.getAllByRole('table')[1];
    expect(within(detalle).getAllByRole('row').map((fila) => fila.textContent)).toEqual([
      'Tipo de datoTablas temporales',
      'VARCHAR(3)2 tablas · 67%#TEMPDN#MOVCS',
      'VARCHAR(5)1 tabla · 33%#FIN',
    ]);
    await usuario.click(screen.getByRole('button', { name: 'Ocultar tablas' }));
    expect(screen.queryByText('Distinta longitud')).not.toBeInTheDocument();
  });
});

const COLLATE = (tablas) => ({
  regla: 'TEMPORAL_TEXTO_SIN_COLLATE',
  severidad: 'medio',
  linea: 1,
  mensaje: 'Se identificaron columnas de texto sin COLLATE en las siguientes tablas temporales: '
    + `${tablas.map(([nombre, columnas]) => `${nombre}: ${columnas.join(', ')}`).join('; ')}. `
    + 'Se recomienda añadir el COLLATE correspondiente en las columnas de tipo texto de las tablas temporales.',
  grupos: tablas.map(([nombre, columnas], i) => ({ nombre, tipo: 'Tabla', lineas: columnas.map(() => i + 1), etiquetas: columnas })),
  // Como el backend: una línea por columna sin COLLATE.
  lineas: tablas.flatMap(([, columnas], i) => columnas.map(() => i + 1)),
});

describe('PanelHallazgos · «COLLATE no especificado en tabla temporal» como tabla', () => {
  it('desde 3 tablas: Tabla | Columnas sin COLLATE, con la introducción arriba', () => {
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[COLLATE([
      ['#CIERRECOVID', ['CCTACOD', 'cNombre']], ['#RRC1', ['CCTACOD', 'cReprogCov']], ['@T', ['cCod']],
    ])]} />);
    expect(screen.getByText(/^Se identificaron columnas de texto sin COLLATE en las siguientes tablas temporales:$/))
      .toBeInTheDocument();
    // Cada columna sin COLLATE es un caso: 5 columnas → «5 casos».
    expect(screen.getByText('5 casos')).toBeInTheDocument();
    const filas = within(screen.getByRole('table')).getAllByRole('row').map((fila) => fila.textContent);
    expect(filas).toEqual([
      'TablaColumnas sin COLLATE',
      '#CIERRECOVIDCCTACOD, cNombre',
      '#RRC1CCTACOD, cReprogCov',
      '@TcCod',
    ]);
  });

  it('con menos de 3 tablas sigue como texto', () => {
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[COLLATE([
      ['#A', ['cCod']], ['#B', ['cNombre']],
    ])]} />);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    // Hasta 4 casos se muestran las líneas.
    expect(screen.getByText('Líneas 1, 2')).toBeInTheDocument();
  });
});

describe('PanelHallazgos · tablas sin NOLOCK en cajitas', () => {
  const NOLOCK = (tablas) => ({
    regla: 'NOLOCK_POR_EVALUAR',
    severidad: 'bajo',
    linea: 1,
    mensaje: tablas.length >= 3
      ? `Se identificaron consultas de lectura sobre las siguientes tablas físicas sin utilizar WITH (NOLOCK): ${tablas.join('; ')}. Se recomienda evaluar agregar WITH (NOLOCK) a cada tabla física.`
      : `Se identificaron consultas de lectura sobre las tablas físicas ${tablas.join(' y ')} sin utilizar WITH (NOLOCK). Se recomienda evaluar agregar WITH (NOLOCK) a cada tabla física.`,
  });

  it('desde 3 tablas: la introducción y una cajita por tabla', () => {
    const { container } = render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS}
      hallazgos={[NOLOCK(['Parametro', 'Captaciones', 'CAPTACIONES.CAP_CTS_SUELDOS'])]} />);
    expect(screen.getByText('Se identificaron consultas de lectura sobre las siguientes tablas físicas sin utilizar WITH (NOLOCK):'))
      .toBeInTheDocument();
    const cajitas = [...container.querySelectorAll('.lista-cajitas code')].map((c) => c.textContent);
    expect(cajitas).toEqual(['Parametro', 'Captaciones', 'CAPTACIONES.CAP_CTS_SUELDOS']);
    expect(container.querySelector('.finding-list')).toBeNull();
  });

  it('con 2 tablas sigue la frase', () => {
    const { container } = render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS}
      hallazgos={[NOLOCK(['Parametro', 'OpeTpo'])]} />);
    expect(container.querySelector('.lista-cajitas')).toBeNull();
  });
});
