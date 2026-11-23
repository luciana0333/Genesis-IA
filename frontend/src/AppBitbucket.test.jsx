import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import App from './App';

function respuesta(cuerpo) {
  return new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

async function irA(ruta) {
  await act(async () => {
    window.location.hash = `/${ruta}`;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

describe('Bitbucket dentro de la aplicación', () => {
  afterEach(async () => {
    vi.restoreAllMocks();
    await irA('');
  });

  it('«Abrir en Reportes» abre el módulo de siempre con el código pegado y revisado, y la lista sigue al volver', async () => {
    const usuario = userEvent.setup();
    Element.prototype.scrollIntoView = vi.fn();
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve(respuesta({
      hallazgos: [{ linea: 4, severidad: 'alto', regla: 'SELECT_ESTRELLA', origen: 'reglas_estaticas', mensaje: 'Se identificó SELECT *.' }],
    })));
    render(<App />);

    await irA('bitbucket');
    expect(screen.queryByRole('heading', { name: /Auditoría de diccionarios/ })).not.toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Ver ejemplo' }));
    await usuario.click(screen.getByRole('button', { name: 'Procedimiento', pressed: false }));
    await usuario.click(screen.getByRole('button', { name: /Revisar 6 archivos/ }));
    await screen.findByText('Requiere corrección');

    const fila = screen.getAllByRole('listitem').find((li) => li.textContent.includes('PA_GDD_Cliente_Sel_Resumen'));
    fetch.mockClear();
    await usuario.click(within(fila).getByRole('button', { name: /Abrir en Reportes/ }));
    await act(async () => window.dispatchEvent(new HashChangeEvent('hashchange')));

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Auditoría de reportes SQL');
    expect(screen.getByLabelText('SQL del procedimiento de reporte').value).toContain('PA_GDD_Cliente_Sel_Resumen');
    // Se revisa solo, una vez, con las reglas de reportes.
    expect(await screen.findByText(/Se identificó SELECT \*/)).toBeInTheDocument();
    const pedidos = fetch.mock.calls.filter(([ruta]) => ruta === '/api/analizar');
    expect(pedidos).toHaveLength(1);
    expect(JSON.parse(pedidos[0][1].body)).toMatchObject({ tipoRevision: 'reporte' });

    await irA('bitbucket');
    expect(screen.getByRole('heading', { name: 'Detalle por archivo' })).toBeInTheDocument();
  });
});
