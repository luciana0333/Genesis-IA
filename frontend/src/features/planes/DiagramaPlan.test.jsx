import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { DiagramaPlan } from './DiagramaPlan';

const sentencia = (numero, texto, duracionMs, lecturas) => ({
  numero, texto, tipo: 'SELECT', codigo: texto, duracionMs, lecturas, costo: numero, nodos: [],
});

const SENTENCIAS = [
  sentencia(1, 'INSERT INTO #Reporte', 18400, 70411),
  sentencia(2, 'SELECT R.nCreditoId', 26750, 61254),
  sentencia(3, 'SELECT A.nAgenciaId', 9300, 24318),
];

const textosDeFilas = () => within(screen.getAllByRole('rowgroup')[1])
  .getAllByRole('row')
  .map((fila) => within(fila).getAllByRole('cell')[0].textContent);

describe('Grilla de sentencias del plan', () => {
  it('ordena por una columna: mayor a menor, menor a mayor y vuelve al orden del plan', async () => {
    const usuario = userEvent.setup();
    render(<DiagramaPlan sentencias={SENTENCIAS} />);
    const duracion = screen.getByTitle('Ordenar por Duration');

    await usuario.click(duracion);
    expect(textosDeFilas()).toEqual(['SELECT R.nCreditoId', 'INSERT INTO #Reporte', 'SELECT A.nAgenciaId']);
    expect(duracion.closest('th')).toHaveAttribute('aria-sort', 'descending');

    await usuario.click(duracion);
    expect(textosDeFilas()).toEqual(['SELECT A.nAgenciaId', 'INSERT INTO #Reporte', 'SELECT R.nCreditoId']);
    expect(duracion.closest('th')).toHaveAttribute('aria-sort', 'ascending');

    await usuario.click(duracion);
    expect(textosDeFilas()).toEqual(['INSERT INTO #Reporte', 'SELECT R.nCreditoId', 'SELECT A.nAgenciaId']);
    expect(duracion.closest('th')).toHaveAttribute('aria-sort', 'none');
  });

  it('la sentencia elegida sigue siendo la misma al reordenar', async () => {
    const usuario = userEvent.setup();
    render(<DiagramaPlan sentencias={SENTENCIAS} />);
    await usuario.click(screen.getByText('SELECT A.nAgenciaId', { selector: 'td' }));
    await usuario.click(screen.getByTitle('Ordenar por Reads'));
    const elegida = screen.getAllByRole('row').find((fila) => fila.classList.contains('elegida'));
    expect(within(elegida).getAllByRole('cell')[0]).toHaveTextContent('SELECT A.nAgenciaId');
  });

  it('Writes no se puede ordenar (el XML no trae ese dato)', () => {
    render(<DiagramaPlan sentencias={SENTENCIAS} />);
    expect(screen.queryByRole('button', { name: /Writes/ })).not.toBeInTheDocument();
  });
});
