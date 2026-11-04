import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { ValidacionWorkspace } from './ValidacionWorkspace';

function respuesta(cuerpo, estado = 200) {
  return new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } });
}

const LECTOR = { disponible: true, version: '18.0.0.0', lector: 'SQL Server 2022', dll: 'C:/SSMS/ScriptDom.dll' };

describe('ValidacionWorkspace', () => {
  afterEach(() => vi.restoreAllMocks());

  it('muestra si ScriptDom está listo y los errores de estructura con su línea', async () => {
    const usuario = userEvent.setup();
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation((ruta) => Promise.resolve(
      ruta === '/api/validacion-sql/estado'
        ? respuesta(LECTOR)
        : respuesta({
          estado: LECTOR,
          hallazgos: [{
            linea: 7, severidad: 'critico', regla: 'ERROR_SINTAXIS', origen: 'reglas_estaticas',
            mensaje: "Se identificó un error de sintaxis en la línea 7, columna 21: Sintaxis incorrecta cerca de ','. "
              + 'Corregir la estructura en esa línea o justo antes (comas, paréntesis, comillas, BEGIN/END), ya que '
              + 'SQL Server no podrá crear ni ejecutar el código con este error.',
          }],
        }),
    ));
    render(<ValidacionWorkspace />);

    expect(await screen.findByText(/ScriptDom listo · versión 18.0.0.0/)).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: /Validar código/ }));

    const titulo = await screen.findByRole('heading', { name: 'Error de sintaxis' });
    const ficha = titulo.closest('article');
    expect(ficha).toHaveTextContent('línea 7, columna 21: Sintaxis incorrecta cerca de');
    expect(ficha).toHaveTextContent('Corregir la estructura en esa línea');
    expect(within(ficha).getByRole('button', { name: /Ver en el código/ })).toBeInTheDocument();
    const [, pedido] = fetch.mock.calls.find(([ruta]) => ruta === '/api/validar-sql');
    expect(JSON.parse(pedido.body).sql).toContain('PA_Credito_Sel_Resumen');
  });

  it('avisa si la PC no tiene ScriptDom', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(respuesta({
      disponible: false, motivo: 'No se encontró ScriptDom en esta PC (viene con SQL Server Management Studio).',
    }));
    render(<ValidacionWorkspace />);

    expect(await screen.findByText(/No se encontró ScriptDom en esta PC/)).toBeInTheDocument();
  });
});

describe('Copiar consulta de validación', () => {
  afterEach(() => vi.restoreAllMocks());

  it('aparece en el ISNULL sobre una columna y copia la consulta', async () => {
    const usuario = userEvent.setup();
    const consulta = 'SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS';
    vi.spyOn(globalThis, 'fetch').mockImplementation((ruta) => Promise.resolve(
      ruta === '/api/validacion-sql/estado'
        ? respuesta(LECTOR)
        : respuesta({
          estado: LECTOR,
          hallazgos: [{
            linea: 3, severidad: 'bajo', regla: 'ISNULL_VALIDAR_NULOS', origen: 'reglas_estaticas', consulta,
            mensaje: 'Se identificó ISNULL(c.nSaldo, 0) sobre la columna nSaldo de dbo.Credito. Se recomienda validar '
              + 'si la columna acepta valores nulos con la consulta adjunta, ya que, si no los acepta, el ISNULL no es necesario.',
          }],
        }),
    ));
    const copiar = vi.fn().mockResolvedValue();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: copiar }, configurable: true });
    render(<ValidacionWorkspace />);

    await usuario.click(await screen.findByRole('button', { name: /Validar código/ }));
    await usuario.click(await screen.findByRole('button', { name: /Copiar consulta de validación/ }));

    expect(copiar).toHaveBeenCalledWith(consulta);
    expect(await screen.findByRole('button', { name: /Consulta copiada/ })).toBeInTheDocument();
  });
});
