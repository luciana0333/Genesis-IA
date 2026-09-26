import { vi } from 'vitest';
import { ErrorApi, analizarObjeto } from './cliente';

function respuestaJson(cuerpo, estado = 200) {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('analizarObjeto', () => {
  it('envía la solicitud como JSON y devuelve los datos', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(respuestaJson({ hallazgos: [] }));

    await expect(analizarObjeto({ sqlObject: 'SELECT 1' })).resolves.toEqual({ hallazgos: [] });
    const [ruta, opciones] = fetchMock.mock.calls[0];
    expect(ruta).toBe('/api/analizar');
    expect(JSON.parse(opciones.body)).toEqual({ sqlObject: 'SELECT 1' });
  });

  it('usa el mensaje de error del backend', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(respuestaJson({ error: 'JSON inválido' }, 400));

    await expect(analizarObjeto({})).rejects.toMatchObject({ name: 'ErrorApi', message: 'JSON inválido', estado: 400 });
  });

  it('traduce un fallo de red a un mensaje legible', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await analizarObjeto({}).catch((e) => e);
    expect(error).toBeInstanceOf(ErrorApi);
    expect(error.message).toBe('No se pudo conectar con el servidor.');
  });

  it('propaga las cancelaciones sin convertirlas', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new DOMException('Abortado', 'AbortError'));

    await expect(analizarObjeto({})).rejects.toMatchObject({ name: 'AbortError' });
  });
});
