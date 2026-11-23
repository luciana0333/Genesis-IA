import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { BitbucketWorkspace } from './BitbucketWorkspace';
import { tomarTraspaso } from './traspaso';

function respuesta(cuerpo, estado = 200) {
  return new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } });
}

// Cada revisión devuelve observaciones según el tipo, para comprobar el total y el orden por gravedad.
function revisionSimulada(ruta, pedido) {
  if (ruta === '/api/bitbucket/leer') return Promise.resolve(new Response('', { status: 404 }));
  const { tipoRevision } = JSON.parse(pedido.body);
  const hallazgos = tipoRevision === 'tabla_estructura'
    ? [{ severidad: 'critico', regla: 'X' }, { severidad: 'alto', regla: 'Y' }]
    : [{ severidad: 'bajo', regla: 'Z' }];
  return Promise.resolve(respuesta({ hallazgos }));
}

describe('BitbucketWorkspace', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.location.hash = '';
  });

  it('avisa si el link no es de Bitbucket, sin llamar al servidor', async () => {
    const usuario = userEvent.setup();
    const fetch = vi.spyOn(globalThis, 'fetch');
    render(<BitbucketWorkspace />);

    await usuario.type(screen.getByLabelText('Link de Bitbucket'), 'https://github.com/cajaica/repo/pull/1');
    await usuario.click(screen.getByRole('button', { name: /Leer archivos/ }));

    expect(screen.getByRole('alert')).toHaveTextContent('no es de Bitbucket');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('mientras el servidor no tenga la conexión, lo dice y ofrece el ejemplo', async () => {
    const usuario = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockImplementation(revisionSimulada);
    render(<BitbucketWorkspace />);

    await usuario.type(screen.getByLabelText('Link de Bitbucket'), 'https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129');
    await usuario.click(screen.getByRole('button', { name: /Leer archivos/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('todavía no está activa');
  });

  it('recorrido completo con el ejemplo: confirmar, revisar, resumen ordenado y abrir en el módulo', async () => {
    const usuario = userEvent.setup();
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(revisionSimulada);
    render(<BitbucketWorkspace />);

    await usuario.click(screen.getByRole('button', { name: 'Ver ejemplo' }));
    expect(screen.getByRole('heading', { name: 'Archivos encontrados' })).toBeInTheDocument();

    // Hay un archivo dudoso: no se puede revisar hasta responder.
    const revisar = screen.getByRole('button', { name: /Revisar 5 archivos/ });
    expect(revisar).toBeDisabled();
    expect(screen.getByText('Falta responder 1 archivo.')).toBeInTheDocument();
    await usuario.click(screen.getByRole('button', { name: 'Reporte', pressed: false }));
    await usuario.click(screen.getByRole('button', { name: /Revisar 6 archivos/ }));

    // 2 tablas (crítica + alta) y 4 archivos con una baja.
    expect(await screen.findByText('Requiere corrección')).toBeInTheDocument();
    expect(document.querySelector('.bb-total')).toHaveTextContent('8');
    const filas = screen.getAllByRole('listitem').filter((li) => li.classList.contains('bb-fila'));
    expect(filas).toHaveLength(6);
    expect(filas[0]).toHaveTextContent('Tabla');
    expect(fetch.mock.calls.filter(([ruta]) => ruta === '/api/analizar')).toHaveLength(6);

    // El diccionario se mandó con su tabla, y el dudoso como reporte.
    const pedidos = fetch.mock.calls.filter(([ruta]) => ruta === '/api/analizar').map(([, p]) => JSON.parse(p.body));
    expect(pedidos.find((p) => p.tipoRevision === 'tabla')).toMatchObject({ sqlObject: expect.stringContaining('CREATE TABLE CLICKTOPAY.Cliente') });
    expect(pedidos.find((p) => p.tipoRevision === 'reporte' && p.sqlObject.includes('PA_Cliente_Sel_PorId'))).toBeTruthy();
    // Los índices de TB_cliente_datos van en la cajita de índices de su tabla.
    expect(pedidos.find((p) => p.tipoRevision === 'tabla_estructura' && p.sqlObject.includes('TB_cliente_datos')).indicesScript)
      .toContain('CREATE INDEX idx_cliente');

    const filaReporte = filas.find((li) => li.textContent.includes('PA_GDD_Cliente_Sel_Resumen'));
    await usuario.click(within(filaReporte).getByRole('button', { name: /Abrir en Reportes/ }));
    expect(window.location.hash).toBe('#/reportes');
    const traspaso = tomarTraspaso('reporte');
    expect(traspaso).toMatchObject({ tipoRevision: 'reporte', campos: { objetoNombre: 'dbo.PA_GDD_Cliente_Sel_Resumen' } });
    expect(tomarTraspaso('reporte')).toBeNull();
    // Recorre los tres pasos: con la PC cargada puede pasar de los 5 s por defecto.
  }, 20000);
});
