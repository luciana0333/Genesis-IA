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
    expect(screen.getByRole('link', { name: 'Diccionarios' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByLabelText('Tipo de revisión')).toHaveValue('procedimiento');
    expect(screen.getByLabelText('SQL del procedimiento').value).toContain('PA_Cliente_Consultar');
    expect(screen.getByText('Presiona "Ejecutar revisión" para analizar el objeto.')).toBeInTheDocument();
  });

  it('no muestra ningún elemento de la capa de IA', () => {
    render(<App />);
    expect(screen.queryByText(/Ollama/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Sugerencias de mejora/i)).not.toBeInTheDocument();
  });

  it('en Tablas oculta el selector y el diccionario y muestra DBCMAICA', async () => {
    render(<App />);
    await irA('tablas');

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Auditoría de tablas SQL');
    expect(screen.getByText('Validación de estructura')).toBeInTheDocument();
    expect(screen.queryByLabelText('Tipo de revisión')).not.toBeInTheDocument();
    expect(screen.queryByText('Documentación')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/DBCMAICA/)).toBeInTheDocument();
    expect(screen.getByLabelText('Nombre de la tabla')).toBeInTheDocument();
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

    const lista = await screen.findByText('SELECT estrella prohibido');
    expect(lista).toBeInTheDocument();
    expect(screen.getByText('REGLA_NUEVA')).toBeInTheDocument();
    expect(screen.getByText('Línea 3')).toBeInTheDocument();

    const tarjetaAltos = screen.getByText('Altos').closest('.metric-card');
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
    expect(titulos()).toEqual(['Table Scan', 'SELECT estrella prohibido', 'VARBINARY para documento identificado']);

    await usuario.click(screen.getByRole('button', { name: /^Alto/ }));
    expect(titulos()).toEqual(['SELECT estrella prohibido']);

    await usuario.click(screen.getByRole('button', { name: /^Todos/ }));
    expect(titulos()).toHaveLength(3);
  });

  it('restaura el script de ejemplo después de limpiar', async () => {
    const usuario = userEvent.setup();
    render(<App />);

    await usuario.click(screen.getByRole('button', { name: 'Limpiar' }));
    expect(screen.getByLabelText('SQL del procedimiento')).toHaveValue('');

    await usuario.click(screen.getByRole('button', { name: 'Restaurar ejemplo' }));
    expect(screen.getByLabelText('SQL del procedimiento').value).toContain('PA_Cliente_Consultar');
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

    expect(screen.getByText('Pega el código del diccionario para iniciar la revisión.')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
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
    expect(screen.getByText('Diccionario')).toBeInTheDocument();

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
  it('rechaza archivos sin extensión .sqlplan', async () => {
    const usuario = userEvent.setup({ applyAccept: false });
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    render(<App />);
    await irA('planes');

    await usuario.upload(screen.getByLabelText('Archivo .sqlplan'), new File(['<x/>'], 'plan.xml', { type: 'text/xml' }));
    await usuario.click(screen.getByRole('button', { name: 'Analizar plan' }));

    expect(screen.getByText('El archivo debe tener extensión .sqlplan.')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
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

    await usuario.upload(screen.getByLabelText('Archivo .sqlplan'), new File(['<x/>'], 'prueba.sqlplan'));
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
