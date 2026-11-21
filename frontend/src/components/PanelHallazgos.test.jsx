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
    // Todas las conversiones con el mismo título (usuaria, 20 nov.): la normal primero, el riesgo después.
    expect(titulos).toEqual(['Conversión implícita', 'Conversión implícita']);
    // La ficha del riesgo está después del encabezado; la normal, antes.
    const [fichaNormal, fichaRiesgo] = screen.getAllByRole('heading', { name: 'Conversión implícita' });
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
    expect(screen.getByText('2 casos')).toBeInTheDocument(); // cada columna es un caso (usuaria, 17 nov.)
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

describe('PanelHallazgos · «ISNULL posiblemente innecesario» como tabla', () => {
  it('desde 3 tablas: Tabla | Columnas, cada columna una vez y cada ISNULL un caso', () => {
    const hallazgo = {
      regla: 'ISNULL_VALIDAR_NULOS',
      severidad: 'bajo',
      linea: 3,
      mensaje: 'Se identificó el uso de ISNULL en las siguientes columnas: dbo.Credito: nSaldo, nMora; dbo.OpeTpo: nOrden; '
        + 'dbo.MovCap: nIdDescTrx, nMonto (a través de #M). Se recomienda validar si estas columnas permiten valores '
        + 'NULL. De no permitirlos, se puede retirar el ISNULL, ya que no sería necesario.',
      grupos: [
        { nombre: 'dbo.Credito', tipo: 'Tabla', lineas: [3, 3], etiquetas: ['nMora', 'nSaldo'], columnas: 'nSaldo, nMora' },
        { nombre: 'dbo.OpeTpo', tipo: 'Tabla', lineas: [3, 4], etiquetas: ['nOrden', 'nOrden'], columnas: 'nOrden' },
        { nombre: 'dbo.MovCap', tipo: 'Tabla', lineas: [3, 4], etiquetas: ['nIdDescTrx', 'nMonto'],
          columnas: 'nIdDescTrx, nMonto (a través de #M)' },
      ],
      lineas: [3, 3, 3, 4, 3, 4],
    };
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[hallazgo]} />);
    expect(screen.getByText('ISNULL posiblemente innecesario')).toBeInTheDocument();
    expect(screen.getByText(/^Se identificó el uso de ISNULL en las siguientes columnas:$/)).toBeInTheDocument();
    expect(screen.getByText('6 casos')).toBeInTheDocument();
    const filas = within(screen.getByRole('table')).getAllByRole('row').map((fila) => fila.textContent);
    expect(filas).toEqual([
      'TablaColumnas',
      'dbo.CreditonSaldo, nMora',
      'dbo.OpeTponOrden',
      'dbo.MovCapnIdDescTrx, nMonto (a través de #M)',
    ]);
  });
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

describe('PanelHallazgos · casos poco comunes (usuaria, 21 nov.)', () => {
  it('van en su propio recuadro, al final, con su cantidad', () => {
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[
      { regla: 'COLUMNA_SIN_NOT_NULL_NI_DEFAULT', severidad: 'alto', linea: 5, mensaje: 'La columna x acepta nulos. Definirla.' },
      { regla: 'PK_HEREDADA', severidad: 'bajo', linea: 3, pocoComun: true,
        mensaje: 'Se identificó que la clave primaria cCtaCod también es la relación con dbo.CaptacCTS (uno a uno), por '
          + 'eso es VARCHAR(18) y no autoincremental. Validar con el DBA, ya que es una excepción al estándar de clave primaria.' },
    ]} />);
    const recuadro = screen.getByRole('region', { name: 'Validar con el DBA' });
    expect(within(recuadro).getByText('Casos poco comunes')).toBeInTheDocument();
    expect(within(recuadro).getByText('1 caso')).toBeInTheDocument();
    expect(within(recuadro).getByRole('heading', { name: 'Clave primaria heredada' })).toBeInTheDocument();
    // La observación común no entra al recuadro.
    expect(within(recuadro).queryByText(/acepta nulos/)).not.toBeInTheDocument();
  });
});

describe('PanelHallazgos · más de 3 casos en tabla (usuaria, 21 nov.)', () => {
  it('el backend manda la tabla con sus títulos; la frase de «Qué hace» va en letra normal', () => {
    const fila = (nombre, columnas) => ({
      nombre, tipo: 'Sugerencia', tituloDetalle: 'Qué hace', detalleEnTexto: true, lineas: [1], columnas,
    });
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[{
      regla: 'HINT_BLOQUEO_PROHIBIDO',
      severidad: 'alto',
      linea: 1,
      mensaje: 'Se identificó el uso de las siguientes sugerencias de bloqueo: UPDLOCK (bloquea); HOLDLOCK (mantiene); '
        + 'ROWLOCK (obliga); TABLOCK (bloquea toda la tabla). Se recomienda retirarlas.',
      lineas: [1, 1, 1, 1],
      grupos: [fila('UPDLOCK', 'bloquea'), fila('HOLDLOCK', 'mantiene'), fila('ROWLOCK', 'obliga'), fila('TABLOCK', 'bloquea toda la tabla')],
    }]} />);
    const tabla = within(screen.getByRole('table'));
    expect(tabla.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Sugerencia', 'Qué hace']);
    expect(tabla.getByText('obliga')).toHaveClass('tabla-detalle-texto');
    expect(screen.getByText('Se identificó el uso de las siguientes sugerencias de bloqueo:')).toBeInTheDocument();
    expect(screen.getByText('4 casos')).toBeInTheDocument();
  });
});

describe('PanelHallazgos · «Validar documentación existente» con varios procedimientos', () => {
  it('desde 2 procedimientos: Procedimiento | Parámetros sin descripción (usuaria, 20 nov.)', () => {
    const mensaje = 'Se identificó que el diccionario no incluye la descripción de los siguientes procedimientos o de '
      + 'sus parámetros: dbo.PA_Uno: (descripción del procedimiento), @nB; dbo.PA_Dos: @cX. ';
    const queHacer = 'Se recomienda verificar si estas descripciones ya se encuentran registradas, considerando que '
      + 'se trata de una modificación de los procedimientos (ALTER PROCEDURE).';
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[{
      regla: 'VALIDAR_DOCUMENTACION_ALTER',
      severidad: 'bajo',
      linea: 2,
      mensaje: mensaje + queHacer,
      inicioQueHacer: mensaje.length,
      lineas: [2, 4, 9],
      grupos: [
        { nombre: 'dbo.PA_Uno', tipo: 'Procedimiento', lineas: [2, 4], etiquetas: ['(descripción del procedimiento)', '@nB'] },
        { nombre: 'dbo.PA_Dos', tipo: 'Procedimiento', lineas: [9], etiquetas: ['@cX'] },
      ],
    }]} />);
    const filas = within(screen.getByRole('table')).getAllByRole('row').map((fila) => fila.textContent);
    expect(filas).toEqual([
      'ProcedimientoParámetros sin descripción',
      'dbo.PA_Uno(descripción del procedimiento), @nB',
      'dbo.PA_Dos@cX',
    ]);
    expect(screen.getByText(/^Se identificó que el diccionario no incluye la descripción de los siguientes procedimientos o de sus parámetros:$/))
      .toBeInTheDocument();
    expect(screen.getByText(/considerando que se trata de una modificación de los procedimientos/)).toBeInTheDocument();
  });

  it('unida (no se incluyen / se agregan): Situación | Elementos y un caso por elemento (opción A, 20 nov.)', () => {
    const frase = 'Se identificó que el procedimiento está siendo modificado, por lo que se debe verificar si las '
      + 'descripciones ya están registradas en el diccionario.';
    const mensaje = `${frase} No se incluyen en el diccionario: @a, @b; Se agregan en el diccionario: @c. `;
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[{
      regla: 'VALIDAR_DOCUMENTACION_ALTER',
      severidad: 'bajo',
      linea: 3,
      mensaje: `${mensaje}Incluir en el diccionario las descripciones que no estén registradas.`,
      inicioQueHacer: mensaje.length,
      lineas: [3, 4, 2],
      seccion: 'objeto',
      grupos: [
        { nombre: 'No se incluyen en el diccionario', tipo: 'Situación', seccion: 'objeto', lineas: [3, 4], etiquetas: ['@a', '@b'] },
        { nombre: 'Se agregan en el diccionario', tipo: 'Situación', seccion: 'diccionario', lineas: [2], etiquetas: ['@c'] },
      ],
    }]} />);
    const filas = within(screen.getByRole('table')).getAllByRole('row').map((fila) => fila.textContent);
    expect(filas).toEqual(['SituaciónElementos', 'No se incluyen en el diccionario@a, @b', 'Se agregan en el diccionario@c']);
    expect(screen.getByText('3 casos')).toBeInTheDocument();
    // Sobre la tabla, solo la frase de la usuaria (el detalle está en la tabla).
    expect(screen.getByText(frase)).toBeInTheDocument();
  });

  it('unida con varios procedimientos: el nombre ocupa una celda para sus dos filas', () => {
    const fila = (nombre, situacion, seccion, etiquetas) => ({
      nombre, tipo: 'Procedimiento', situacion, seccion, lineas: etiquetas.map(() => 1), etiquetas,
    });
    render(<PanelHallazgos titulo="Resultados" estado="listo" textos={TEXTOS} hallazgos={[{
      regla: 'VALIDAR_DOCUMENTACION_ALTER',
      severidad: 'bajo',
      linea: 1,
      mensaje: 'Se identificó que los procedimientos están siendo modificados, por lo que se debe verificar si las '
        + 'descripciones ya están registradas en el diccionario. dbo.PA_A (no se incluyen en el diccionario): @a. '
        + 'Incluir en el diccionario las descripciones que no estén registradas.',
      lineas: [1, 1, 1],
      grupos: [
        fila('dbo.PA_A', 'No se incluyen en el diccionario', 'objeto', ['@a']),
        fila('dbo.PA_A', 'Se agregan en el diccionario', 'diccionario', ['@b']),
        fila('dbo.PA_B', 'No se incluyen en el diccionario', 'objeto', ['@c']),
      ],
    }]} />);
    const tabla = within(screen.getByRole('table'));
    expect(tabla.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Procedimiento', 'Situación', 'Elementos']);
    expect(tabla.getAllByText('dbo.PA_A')).toHaveLength(1);
    expect(tabla.getAllByRole('row').map((tr) => tr.textContent)).toEqual([
      'ProcedimientoSituaciónElementos',
      'dbo.PA_ANo se incluyen en el diccionario@a',
      'Se agregan en el diccionario@b',
      'dbo.PA_BNo se incluyen en el diccionario@c',
    ]);
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
