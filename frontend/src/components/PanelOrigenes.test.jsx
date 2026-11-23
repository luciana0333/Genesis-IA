import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PanelHallazgos } from './PanelHallazgos';

const TEXTOS = { cargando: '', sinHallazgos: '', tituloError: '', inicialTitulo: '', pasos: [] };

const PRACTICA = {
  regla: 'TRANSACCION_SIN_COMMIT', severidad: 'alto', linea: 7,
  mensaje: 'Se detectó una transacción abierta con BEGIN TRANSACTION pero ningún COMMIT. Se recomienda confirmarla.',
};
const SUGERENCIA = {
  regla: 'TOP_SIN_ORDER_BY', severidad: 'medio', linea: 31,
  mensaje: 'Se identificó un TOP 1 sin ORDER BY. Se recomienda añadir un ORDER BY.',
};
const SINTAXIS = {
  regla: 'ERROR_SINTAXIS', severidad: 'critico', linea: 10,
  mensaje: "Se identificó un error de sintaxis en la línea 10, columna 25: Sintaxis incorrecta cerca de ','. Corregir la estructura.",
};

function panel(props) {
  return <PanelHallazgos titulo="Hallazgos del procedimiento" estado="listo" textos={TEXTOS} hallazgos={[PRACTICA]} {...props} />;
}

const titulosFichas = () => screen.queryAllByRole('heading', { level: 4 }).map((h) => h.textContent);

describe('PanelHallazgos · pestañas «Buenas prácticas» y «Validador SQL Server»', () => {
  it('sin validador el panel es el de siempre (sin pestañas ni aviso)', () => {
    render(panel({}));
    expect(screen.queryByRole('tablist', { name: 'Origen de las observaciones' })).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(titulosFichas()).toEqual(['Transacción sin COMMIT']);
    expect(document.querySelector('.tablero-lateral')).not.toHaveClass('origen-validador');
  });

  it('con validador separa cada origen, con su cantidad y su color en la columna', async () => {
    const usuario = userEvent.setup();
    render(panel({ validacion: { disponible: true, alcance: 'completo', hallazgos: [SUGERENCIA] } }));

    const pestanas = within(screen.getByRole('tablist', { name: 'Origen de las observaciones' })).getAllByRole('tab');
    expect(pestanas.map((p) => p.textContent)).toEqual([
      'Buenas prácticasEstándares y reglas de CAJA ICA1', 'Validador SQL ServerLector oficial de SQL Server1',
    ]);
    // Empieza en buenas prácticas: solo sus fichas, columna roja.
    expect(pestanas[0]).toHaveAttribute('aria-selected', 'true');
    expect(titulosFichas()).toEqual(['Transacción sin COMMIT']);
    expect(document.querySelector('.tablero-lateral')).not.toHaveClass('origen-validador');

    await usuario.click(pestanas[1]);
    expect(titulosFichas()).toEqual(['TOP sin ORDER BY']);
    expect(document.querySelector('.tablero-lateral')).toHaveClass('origen-validador');
    expect(screen.queryByText(/solo lo que haría fallar el script/)).not.toBeInTheDocument();
  });

  it('lo que impide ejecutar se avisa arriba en cualquier pestaña y lleva al validador', async () => {
    const usuario = userEvent.setup();
    render(panel({ validacion: { disponible: true, alcance: 'completo', hallazgos: [SINTAXIS, SUGERENCIA] } }));

    const aviso = screen.getByRole('alert');
    expect(aviso).toHaveTextContent('Impide ejecutar');
    expect(aviso).toHaveTextContent('Error de sintaxis (línea 10)');
    expect(titulosFichas()).toEqual(['Transacción sin COMMIT']);
    await usuario.click(within(aviso).getByRole('button', { name: 'Ver en el Validador SQL Server' }));
    expect(titulosFichas()).toEqual(['Error de sintaxis', 'TOP sin ORDER BY']);
    // Ya en el validador, el aviso sigue pero sin el botón.
    expect(within(screen.getByRole('alert')).queryByRole('button')).not.toBeInTheDocument();
  });

  it('cuenta los errores que impiden ejecutar', () => {
    render(panel({ validacion: { disponible: true, alcance: 'completo', hallazgos: [SINTAXIS, { ...SINTAXIS, linea: 20 }, { ...SINTAXIS, linea: 30 }] } }));
    expect(screen.getByRole('alert')).toHaveTextContent('Error de sintaxis (línea 10) y 2 errores más.');
  });

  it('sin observaciones del validador lo dice, y en Tablas y Diccionarios explica el alcance', async () => {
    const usuario = userEvent.setup();
    render(panel({ validacion: { disponible: true, alcance: 'estructura', hallazgos: [] } }));
    await usuario.click(screen.getByRole('tab', { name: /Validador SQL Server/ }));
    expect(screen.getByText('Sin observaciones de SQL Server')).toBeInTheDocument();
    expect(screen.getByText(/solo lo que haría fallar el script/)).toBeInTheDocument();
    expect(screen.getByText('Se revisó que el código se pueda crear y ejecutar')).toBeInTheDocument();
  });

  it('si esta PC no tiene el validador, lo dice sin afectar las buenas prácticas', async () => {
    const usuario = userEvent.setup();
    render(panel({ validacion: { disponible: false, motivo: 'No se encontró ScriptDom en esta PC.' } }));
    const pestana = screen.getByRole('tab', { name: /Validador SQL Server/ });
    expect(pestana).toHaveTextContent('—');
    expect(titulosFichas()).toEqual(['Transacción sin COMMIT']);
    await usuario.click(pestana);
    expect(screen.getByText('El Validador SQL Server no está disponible en esta PC')).toBeInTheDocument();
    expect(screen.getByText(/No se encontró ScriptDom en esta PC\. Las buenas prácticas se revisaron igual\./)).toBeInTheDocument();
  });

  it('sin buenas prácticas pero con validador, cada pestaña muestra lo suyo', async () => {
    const usuario = userEvent.setup();
    render(panel({ hallazgos: [], validacion: { disponible: true, alcance: 'completo', hallazgos: [SUGERENCIA] } }));
    expect(screen.getByText('Todo en orden')).toBeInTheDocument();
    await usuario.click(screen.getByRole('tab', { name: /Validador SQL Server/ }));
    expect(titulosFichas()).toEqual(['TOP sin ORDER BY']);
  });

  it('una revisión nueva vuelve a «Buenas prácticas»', async () => {
    const usuario = userEvent.setup();
    const validacion = { disponible: true, alcance: 'completo', hallazgos: [SUGERENCIA] };
    const { rerender } = render(panel({ validacion }));
    await usuario.click(screen.getByRole('tab', { name: /Validador SQL Server/ }));
    expect(titulosFichas()).toEqual(['TOP sin ORDER BY']);
    rerender(panel({ hallazgos: [{ ...PRACTICA }], validacion: { ...validacion } }));
    expect(screen.getByRole('tab', { name: /Buenas prácticas/ })).toHaveAttribute('aria-selected', 'true');
    expect(titulosFichas()).toEqual(['Transacción sin COMMIT']);
  });

  it('mientras revisa no muestra pestañas', () => {
    render(panel({ estado: 'cargando', validacion: { disponible: true, alcance: 'completo', hallazgos: [SUGERENCIA] } }));
    expect(screen.queryByRole('tablist', { name: 'Origen de las observaciones' })).not.toBeInTheDocument();
  });
});
