import { act, render, screen, waitFor, within } from '@testing-library/react';
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

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Revisión e inspección de Diccionarios SQL');
    expect(screen.getByRole('link', { name: 'Diccionarios' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByLabelText('Tipo de revisión')).toHaveValue('procedimiento');
    expect(screen.getByLabelText('SQL del procedimiento').value).toContain('PA_Cliente_Consultar');
    expect(screen.getByText(/Aún no hay resultados/)).toBeInTheDocument();
  });

  it('no muestra ningún elemento de la capa de IA', () => {
    render(<App />);
    expect(screen.queryByText(/Ollama/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Sugerencias de mejora/i)).not.toBeInTheDocument();
  });

  it('en Tablas oculta el selector y el diccionario y muestra DBCMAICA', async () => {
    render(<App />);
    await irA('tablas');

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Validación de estructura');
    expect(screen.queryByLabelText('Tipo de revisión')).not.toBeInTheDocument();
    expect(screen.queryByText('Documentación')).not.toBeInTheDocument();
    expect(screen.getByLabelText(/DBCMAICA/)).toBeInTheDocument();
    expect(screen.getByLabelText('Nombre de la Tabla')).toBeInTheDocument();
  });

  it('al elegir "Procedimiento de reporte" en el selector navega a Reportes', async () => {
    const usuario = userEvent.setup();
    render(<App />);

    await usuario.selectOptions(screen.getByLabelText('Tipo de revisión'), 'reporte');

    await waitFor(() => expect(window.location.hash).toBe('#/reportes'));
    expect(screen.getByRole('link', { name: 'Reportes' })).toHaveAttribute('aria-current', 'page');
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
    expect(screen.getByText('Línea 3 · reglas_estaticas')).toBeInTheDocument();

    const tarjetaAltos = screen.getByText('Altos').closest('.service-card');
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

    expect(await screen.findByText('Spill hacia TempDB')).toBeInTheDocument();
    expect(screen.getByText('Análisis completado.')).toBeInTheDocument();
    const operadores = screen.getByText('Operadores').closest('.service-card');
    expect(within(operadores).getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/8[,.]?192 KB/)).toBeInTheDocument();
  });
});
