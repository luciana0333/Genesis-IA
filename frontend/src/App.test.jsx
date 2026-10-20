import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import App from './App';

function mockRespuesta(cuerpo, estado = 200) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } }),
  );
}

async function irA(ruta) {
  await act(async () => {
    window.location.hash = `/${ruta}`;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

describe('App', () => {
  it('inicia en Diccionarios con el ejemplo de procedimiento', () => {
    render(<App />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Auditoría de diccionarios SQL');
    const menu = screen.getByRole('navigation', { name: 'Tipos de revisión' });
    expect(within(menu).getByRole('link', { name: 'Diccionarios' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByLabelText('Tipo de revisión')).toHaveValue('procedimiento');
    expect(screen.getByLabelText('SQL del procedimiento').value).toContain('PA_Cliente_Sel_PorId');
    expect(screen.getByText('Listo para iniciar la revisión')).toBeInTheDocument();
  });

  it('«Ver» del resumen por severidad baja hasta los resultados', async () => {
    const usuario = userEvent.setup();
    const desplazar = vi.fn();
    Element.prototype.scrollIntoView = desplazar;
    render(<App />);

    const resumen = screen.getByRole('region', { name: 'Resumen por severidad' });
    await usuario.click(within(resumen).getAllByRole('button', { name: /Ver/ })[0]);
    await usuario.click(within(resumen).getByRole('button', { name: 'Ver hallazgos' }));

    expect(desplazar).toHaveBeenCalledTimes(2);
    expect(desplazar.mock.contexts[0]).toHaveClass('panel-footer');
    delete Element.prototype.scrollIntoView;
  });

  it('no muestra ningún elemento de la capa de IA', () => {
    render(<App />);
    expect(screen.queryByText(/Ollama/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Sugerencias de mejora/i)).not.toBeInTheDocument();
  });

  it('en Tablas separa los hallazgos de la tabla y de los índices en pestañas', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({
      hallazgos: [
        { linea: 1, severidad: 'alto', regla: 'PK_FALTANTE', mensaje: 'Sin PK. Se recomienda añadirla.' },
        { linea: 3, severidad: 'critico', regla: 'INDICE_COLUMNA_NO_INDEXABLE', seccion: 'indices', mensaje: 'No indexable. Se recomienda quitarla.' },
        { linea: 2, severidad: 'alto', regla: 'INDICE_SIN_ESQUEMA', seccion: 'indices', mensaje: 'Sin esquema. Se recomienda añadirlo.' },
      ],
    });
    render(<App />);
    await irA('tablas');
    await usuario.click(screen.getByRole('button', { name: /Ejecutar revisión/ }));

    const pestanas = await screen.findByRole('tablist', { name: 'Origen de los hallazgos' });
    expect(within(pestanas).getByRole('tab', { name: /Tabla\s*1/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Tabla sin clave primaria')).toBeInTheDocument();
    expect(screen.queryByText('Columna no válida en índice')).not.toBeInTheDocument();

    await usuario.click(within(pestanas).getByRole('tab', { name: /Índices\s*2/ }));
    expect(screen.getByText('Columna no válida en índice')).toBeInTheDocument();
    expect(screen.getByText('Índices · Línea 2')).toBeInTheDocument();
    expect(screen.queryByText('Tabla sin clave primaria')).not.toBeInTheDocument();
  });

  it('en Tablas oculta el selector y el diccionario y muestra DBCMAICA', async () => {
    render(<App />);
    await irA('tablas');

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Auditoría de tablas SQL');
    expect(screen.queryByLabelText('Tipo de revisión')).not.toBeInTheDocument();
    expect(screen.queryByText('Documentación')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/DBCMAICA/)).toBeInTheDocument();
    expect(screen.getByLabelText('Nombre de la tabla')).toBeInTheDocument();
  });

  it('en Tablas elegir la base DBCMAICA se envía en la revisión', async () => {
    const usuario = userEvent.setup();
    const fetchMock = mockRespuesta({ hallazgos: [] });
    render(<App />);
    await irA('tablas');

    expect(screen.getByRole('radio', { name: 'Otra base de datos' })).toBeChecked();
    await usuario.click(screen.getByRole('radio', { name: 'DBCMAICA' }));
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    const cuerpo = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(cuerpo).toMatchObject({ esDbcmaica: true });
  });

  it('en Diccionarios solo ofrece diccionario de procedimiento y de tabla', async () => {
    const usuario = userEvent.setup();
    render(<App />);
    const selector = screen.getByLabelText('Tipo de revisión');

    const opciones = within(selector).getAllByRole('option').map((opcion) => opcion.textContent);
    expect(opciones).toEqual(['Diccionario de procedimiento', 'Diccionario de tabla']);

    await usuario.selectOptions(selector, 'tabla');
    expect(screen.getByLabelText('SQL de la tabla (CREATE / ALTER)').value).toContain('CREATE TABLE');
    expect(screen.getByText('Código del diccionario de tabla')).toBeInTheDocument();
    expect(screen.getByLabelText('Código del diccionario de tabla').value).toContain("@level2name=N'cCodPersona'");
  });

  it('Diccionarios: muestra el código de cada observación y «Ver en el código» marca su línea', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({
      hallazgos: [
        { linea: 2, origen: 'diccionario', severidad: 'medio', regla: 'DESCRIPCION_VACIA', mensaje: 'Descripción vacía. Completarla.', seccion: 'diccionario' },
        { linea: 1, origen: 'diccionario', severidad: 'alto', regla: 'PROCEDIMIENTO_SIN_DESCRIPCION', mensaje: 'Falta la descripción. Añadirla.', seccion: 'general' },
      ],
    });
    render(<App />);
    const diccionario = screen.getByLabelText('Código del diccionario de procedimiento');
    const segundaLinea = diccionario.value.split('\n')[1];

    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    // Solo la observación con línea propia trae su fragmento; la general, no.
    const botones = await screen.findAllByRole('button', { name: 'Ver en el código' });
    expect(botones).toHaveLength(1);
    const ficha = botones[0].closest('.finding');
    expect(within(ficha).getByText('Código del diccionario de procedimiento')).toBeInTheDocument();
    expect(ficha.querySelector('.fragmento-linea.marcada').textContent).toContain(segundaLinea.trim().slice(0, 20));

    await usuario.click(botones[0]);
    const marcadas = diccionario.closest('.code-editor').querySelectorAll('.code-gutter span.marcada');
    expect([...marcadas].map((linea) => linea.textContent)).toEqual(['2']);
    expect(document.activeElement).toBe(diccionario);
  });

  it('ejecuta la revisión, envía el payload correcto y pinta los hallazgos', async () => {
    const usuario = userEvent.setup();
    const fetchMock = mockRespuesta({
      hallazgos: [
        { linea: 3, origen: 'reglas_estaticas', severidad: 'alto', regla: 'SELECT_ESTRELLA_PROHIBIDO', mensaje: 'No use SELECT *.' },
        { linea: 7, origen: 'reglas_estaticas', severidad: 'bajo', regla: 'REGLA_NUEVA', mensaje: 'Detalle.' },
      ],
    });
    render(<App />);
    await irA('tablas');

    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    const cuerpo = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(cuerpo).toMatchObject({ tipoRevision: 'tabla_estructura', modoRevision: 'tabla_estructura', esDbcmaica: false });

    const lista = await screen.findByText('Uso de SELECT *');
    expect(lista).toBeInTheDocument();
    expect(screen.getByText('REGLA_NUEVA')).toBeInTheDocument();
    expect(screen.getByText('Línea 3')).toBeInTheDocument();

    const tarjetaAltos = screen.getByText('Altos').closest('.resumen-tarjeta');
    expect(within(tarjetaAltos).getByText('1')).toBeInTheDocument();
  });

  it('muestra el error del backend en el panel de resultados', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({ error: 'Debes completar el SQL del objeto.' }, 400);
    render(<App />);

    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    expect(await screen.findByText('Debes completar el SQL del objeto.')).toBeInTheDocument();
  });

  it('valida el SQL vacío sin llamar al servidor', async () => {
    const usuario = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    render(<App />);

    await usuario.click(screen.getByRole('button', { name: 'Limpiar' }));
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    expect(screen.getByText('Completa el SQL del objeto para iniciar la revisión.')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('filtra los hallazgos por severidad y los ordena por gravedad', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({
      hallazgos: [
        { linea: 9, severidad: 'bajo', regla: 'VARBINARY_DOCUMENTO_IDENTIFICADO', mensaje: 'b' },
        { linea: 2, severidad: 'critico', regla: 'TABLE_SCAN', mensaje: 'c' },
        { linea: 4, severidad: 'alto', regla: 'SELECT_ESTRELLA_PROHIBIDO', mensaje: 'a' },
      ],
    });
    render(<App />);
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));
    await screen.findByRole('heading', { name: 'Table Scan' });

    const titulos = () => screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent);
    expect(titulos()).toEqual(['Table Scan', 'Uso de SELECT *', 'VARBINARY identificado']);

    await usuario.click(screen.getByRole('button', { name: /^Alto/ }));
    expect(titulos()).toEqual(['Uso de SELECT *']);

    await usuario.click(screen.getByRole('button', { name: /^Todos/ }));
    expect(titulos()).toHaveLength(3);
  });

  it('restaura el script de ejemplo después de limpiar', async () => {
    const usuario = userEvent.setup();
    render(<App />);

    await usuario.click(screen.getByRole('button', { name: 'Limpiar' }));
    expect(screen.getByLabelText('SQL del procedimiento')).toHaveValue('');

    await usuario.click(screen.getByRole('button', { name: 'Restaurar ejemplo' }));
    expect(screen.getByLabelText('SQL del procedimiento').value).toContain('PA_Cliente_Sel_PorId');
  });

  it('en Diccionarios detecta una tabla pegada y aplica el diccionario de tabla', async () => {
    const usuario = userEvent.setup();
    const fetchMock = mockRespuesta({ hallazgos: [] });
    render(<App />);
    const selector = screen.getByLabelText('Tipo de revisión');
    expect(selector).toHaveValue('procedimiento');

    const editorSql = screen.getByLabelText('SQL del procedimiento');
    await usuario.clear(editorSql);
    await usuario.type(editorSql, 'CREATE TABLE dbo.TB_Estado (nEstadoId INT)');

    expect(selector).toHaveValue('tabla');
    expect(screen.getByLabelText('SQL de la tabla (CREATE / ALTER)')).toHaveValue('CREATE TABLE dbo.TB_Estado (nEstadoId INT)');

    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).tipoRevision).toBe('tabla');
  });

  it('en Diccionarios el diccionario es obligatorio', async () => {
    const usuario = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    render(<App />);

    expect(screen.queryByText('Opcional')).not.toBeInTheDocument();
    await usuario.clear(screen.getByLabelText('Código del diccionario de procedimiento'));
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    const aviso = screen.getByRole('alertdialog', { name: 'Falta el diccionario' });
    expect(aviso).toHaveTextContent('Se ha intentado revisar el procedimiento');
    expect(fetchMock).not.toHaveBeenCalled();

    // «Añadir diccionario» cierra la ventana y lleva al cuadro del diccionario.
    await usuario.click(within(aviso).getByRole('button', { name: /Añadir diccionario/ }));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Código del diccionario de procedimiento')).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('en Diccionarios permite revisar sin diccionario si se confirma', async () => {
    const usuario = userEvent.setup();
    const fetchMock = mockRespuesta({ hallazgos: [] });
    render(<App />);

    await usuario.clear(screen.getByLabelText('Código del diccionario de procedimiento'));
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));
    await usuario.click(screen.getByRole('button', { name: 'Revisar sin diccionario' }));

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).dictScript).toBe('');
  });

  it('ofrece el script del diccionario faltante una sola vez y lo copia', async () => {
    const usuario = userEvent.setup();
    const script = "-- Diccionario faltante\n\nEXEC sys.sp_addextendedproperty\n    @name = N'MS_Description', @value = N'';\nGO\n";
    mockRespuesta({
      hallazgos: [
        { linea: 1, severidad: 'alto', regla: 'PROCEDIMIENTO_SIN_DESCRIPCION', mensaje: 'Falta. Añadirla.' },
        { linea: 2, severidad: 'alto', regla: 'PARAMETRO_FALTANTE', mensaje: 'Falta. Añadirlo.' },
      ],
      diccionarioFaltante: { script, elementos: ['procedimiento PA_X', '@nId'] },
    });
    render(<App />);
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    const botones = await screen.findAllByRole('button', { name: 'Generar diccionario faltante' });
    expect(botones).toHaveLength(1);
    await usuario.click(botones[0]);

    const generador = screen.getByRole('region', { name: 'Diccionario faltante' });
    expect(generador).toHaveTextContent('Generado para procedimiento PA_X y @nId.');
    expect(generador).toHaveTextContent('Por completar');
    const editor = within(generador).getByLabelText('Diccionario faltante');
    expect(editor).toHaveValue(script);

    // Se completa la descripción ahí mismo y se copia el script ya completo.
    const completo = script.replace("N''", "N'Consulta un cliente'");
    await usuario.clear(editor);
    await usuario.click(editor);
    await usuario.paste(completo);
    expect(generador).toHaveTextContent('Completo');
    await usuario.click(within(generador).getByRole('button', { name: /Copiar script/ }));
    expect(await navigator.clipboard.readText()).toBe(completo);
    expect(within(generador).getByRole('button', { name: /Copiado/ })).toBeInTheDocument();
  });

  it('una observación que junta varias líneas las muestra en el encabezado', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({
      hallazgos: [{
        linea: 6, lineas: [6, 7], severidad: 'alto', regla: 'TABLA_FISICA_SIN_NOLOCK',
        mensaje: 'Se identificó que las tablas dbo.Cliente y dbo.Agencia no utilizan WITH (NOLOCK). Se recomienda añadir WITH (NOLOCK).',
      }],
    });
    render(<App />);
    await irA('reportes');
    await usuario.click(screen.getByRole('button', { name: /Ejecutar revisión/ }));

    const ficha = (await screen.findByText('Tabla física sin WITH (NOLOCK)')).closest('article');
    expect(within(ficha).getByText('Líneas 6, 7')).toBeInTheDocument();
    expect(within(ficha).queryByRole('list')).not.toBeInTheDocument();
  });

  it('la ventana de diccionario faltante se cierra con Escape', async () => {
    const usuario = userEvent.setup();
    render(<App />);

    await usuario.clear(screen.getByLabelText('Código del diccionario de procedimiento'));
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));
    await usuario.keyboard('{Escape}');
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('resalta lo citado en el mensaje y copia todas las observaciones', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({
      hallazgos: [
        { linea: 2, origen: 'diccionario', severidad: 'medio', regla: 'ERROR_ORTOGRAFICO', mensaje: "Palabra mal escrita: 'Indicatg' (¿quiso decir 'Indicar'?)." },
      ],
    });
    render(<App />);
    await usuario.click(screen.getByRole('button', { name: 'Ejecutar revisión' }));

    expect(await screen.findByText('Indicatg')).toHaveClass('finding-token');

    await usuario.click(screen.getByRole('button', { name: 'Copiar todo' }));
    const copiado = await navigator.clipboard.readText();
    expect(copiado).toBe("1. [Medio] Palabra mal escrita en la descripción (línea 2): Palabra mal escrita: 'Indicatg' (¿quiso decir 'Indicar'?).");
  });

  it('alterna y recuerda el tema oscuro', async () => {
    const usuario = userEvent.setup();
    render(<App />);

    await usuario.click(screen.getByRole('button', { name: 'Cambiar tema' }));

    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(localStorage.getItem('genesis-ia:tema')).toBe('dark');
  });
});

describe('Planes', () => {
  it('deja fuera los archivos que no son planes ni comprimidos', async () => {
    const usuario = userEvent.setup({ applyAccept: false });
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    render(<App />);
    await irA('planes');

    await usuario.upload(screen.getByLabelText('Planes de ejecución'), new File(['hola'], 'nota.txt', { type: 'text/plain' }));
    expect(screen.getByText(/Se dejaron fuera 1 archivo: solo se aceptan/)).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Analizar plan' }));

    expect(screen.getByText('Selecciona un plan .sqlplan, varios planes o un .zip / .rar.')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('revisa varios planes por lote y abre el detalle de cada uno', async () => {
    const usuario = userEvent.setup();
    const analisis = (archivo, regla) => ({
      archivo,
      resumen: { critico: 0, alto: 1, medio: 0, bajo: 0 },
      hallazgos: [{ linea: 1, origen: 'plan_ejecucion', severidad: 'alto', regla, mensaje: 'Detalle.' }],
      operadores: [{ nodoId: '1' }],
      memoria: null,
      diagrama: [],
    });
    const fetchMock = mockRespuesta({
      area: 'reporte',
      limite: 2,
      planes: [
        { id: 0, archivo: 'rapido.sqlplan', ruta: 'Planes.zip › rapido.sqlplan', procedimiento: 'dbo.PA_Rapido', duracionMs: 300, superaLimite: false, resumen: { critico: 0, alto: 1, medio: 0, bajo: 0 }, totalHallazgos: 1, analisis: analisis('rapido.sqlplan', 'SPILL_TEMPDB') },
        { id: 1, archivo: 'lento.sqlplan', ruta: 'Planes.zip › lento.sqlplan', procedimiento: 'dbo.PA_Lento', duracionMs: 5400, superaLimite: true, resumen: { critico: 0, alto: 1, medio: 0, bajo: 0 }, totalHallazgos: 1, analisis: analisis('lento.sqlplan', 'TABLE_SCAN') },
        { id: 2, archivo: 'roto.sqlplan', ruta: 'roto.sqlplan', procedimiento: 'roto', error: 'El plan está incompleto o dañado y no se pudo leer.' },
      ],
      ignorados: [{ ruta: 'Planes.zip › leeme.txt', motivo: 'No es un plan de ejecución (ShowPlanXML).' }],
      totales: { planes: 2, conError: 1, superanLimite: 1, hallazgos: 2, sinHallazgos: 0, porSeveridad: { critico: 0, alto: 2, medio: 0, bajo: 0 } },
    });
    render(<App />);
    await irA('planes');

    await usuario.upload(screen.getByLabelText('Planes de ejecución'), [
      new File(['<x/>'], 'uno.sqlplan'), new File(['<y/>'], 'dos.sqlplan'),
    ]);
    await usuario.click(screen.getByRole('button', { name: 'Analizar planes' }));

    expect(await screen.findByRole('heading', { name: 'Planes del lote' })).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][0]).toBe('/api/analizar-planes');
    expect(fetchMock.mock.calls[0][1].body.getAll('planes')).toHaveLength(2);
    const filas = screen.getAllByRole('row').slice(1);
    // El más lento primero; el dañado al final.
    expect(within(filas[0]).getByText('dbo.PA_Lento')).toBeInTheDocument();
    expect(within(filas[0]).getByText('Supera el límite')).toBeInTheDocument();
    expect(within(filas[2]).getByText('El plan está incompleto o dañado y no se pudo leer.')).toBeInTheDocument();
    expect(screen.getByText('1 archivo no se revisó')).toBeInTheDocument();
    const superan = screen.getByText('Superan el límite').closest('.metric-card');
    expect(within(superan).getByText('1')).toBeInTheDocument();

    await usuario.click(within(filas[0]).getByRole('button', { name: 'Ver detalle' }));
    expect(await screen.findByRole('heading', { name: 'Table Scan' })).toBeInTheDocument();
    expect(screen.getByText('Plan 1 de 2')).toBeInTheDocument();

    await usuario.click(screen.getByRole('button', { name: 'Siguiente' }));
    expect(await screen.findByRole('heading', { name: 'Spill hacia TempDB' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();

    await usuario.click(screen.getByRole('button', { name: 'Volver al resumen' }));
    expect(screen.getByRole('heading', { name: 'Planes del lote' })).toBeInTheDocument();
  });

  it('fija el límite de tiempo en el Paso 1 y lo envía con el análisis', async () => {
    const usuario = userEvent.setup();
    const fetchMock = mockRespuesta({
      archivo: 'prueba.sqlplan',
      resumen: { critico: 0, alto: 0, medio: 0, bajo: 0 },
      hallazgos: [],
      operadores: [],
      memoria: null,
      diagrama: [{ numero: 1, duracionMs: 5000, cpuMs: 100, nodos: [] }],
    });
    render(<App />);
    await irA('planes');

    // 1 min 30 s = 90 s (los segundos de más se pasan a minutos: 0 min 90 s también vale).
    await usuario.type(screen.getByLabelText('Minutos del límite de Reportes'), '1');
    await usuario.type(screen.getByLabelText('Segundos del límite de Reportes'), '30{Enter}');
    await usuario.upload(screen.getByLabelText('Planes de ejecución'), new File(['<x/>'], 'prueba.sqlplan'));
    await usuario.click(screen.getByRole('button', { name: 'Analizar plan' }));

    expect(await screen.findByText('Análisis completado.')).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][1].body.get('limite')).toBe('90');
    // En el detalle, el límite solo se muestra.
    const tarjeta = screen.getByRole('region', { name: 'Tiempo de ejecución' });
    expect(within(tarjeta).getByText('1 min 30 s')).toBeInTheDocument();
    expect(within(tarjeta).queryByRole('textbox')).not.toBeInTheDocument();
    expect(within(tarjeta).queryByRole('button')).not.toBeInTheDocument();
  });

  it('analiza un plan y muestra métricas y hallazgos', async () => {
    const usuario = userEvent.setup();
    mockRespuesta({
      archivo: 'prueba.sqlplan',
      resumen: { critico: 0, alto: 1, medio: 0, bajo: 0 },
      hallazgos: [{ linea: 1, origen: 'plan_ejecucion', severidad: 'alto', regla: 'SPILL_TEMPDB', mensaje: 'Spill.' }],
      operadores: [{ nodoId: '1' }, { nodoId: '2' }],
      memoria: { solicitadaKb: 4096, concedidaKb: 8192, maximaUtilizadaKb: 1024 },
    });
    render(<App />);
    await irA('planes');

    await usuario.upload(screen.getByLabelText('Planes de ejecución'), new File(['<x/>'], 'prueba.sqlplan'));
    await usuario.click(screen.getByRole('button', { name: 'Analizar plan' }));

    expect(await screen.findByRole('heading', { name: 'Spill hacia TempDB' })).toBeInTheDocument();
    expect(screen.getByText('Análisis completado.')).toBeInTheDocument();
    const operadores = screen.getByText('Operadores').closest('.metric-card');
    expect(within(operadores).getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/8[,.]?192 KB/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Operadores más costosos' })).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(3);
  });
});
