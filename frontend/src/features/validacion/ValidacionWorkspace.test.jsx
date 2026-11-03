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
    await usuario.click(screen.getByRole('button', { name: /Validar estructura/ }));

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
