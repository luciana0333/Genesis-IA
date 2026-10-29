import { calcularPosiciones, FILA } from './geometriaPlan';

// IF ... OR EXISTS: Concatenation con una rama larga (hasta el Key Lookup) y otra corta (el Scan).
const NODOS = [
  { id: 'raiz', padre: null },
  { id: 'concat', padre: 'raiz' },
  { id: 'filtro', padre: 'concat' },
  { id: 'loops', padre: 'filtro' },
  { id: 'seek', padre: 'loops' },
  { id: 'lookup', padre: 'loops' },
  { id: 'scan', padre: 'concat' },
];

describe('calcularPosiciones', () => {
  it('una rama corta sube a la fila libre de sus columnas (no baja por una rama larga de más a la derecha)', () => {
    const { posiciones } = calcularPosiciones(NODOS);
    const fila = (id) => (posiciones.get(id).y - posiciones.get('raiz').y) / FILA;
    expect(fila('concat')).toBe(0);
    expect(fila('lookup')).toBe(1);
    expect(fila('scan')).toBe(1);  // antes quedaba en la fila 2, debajo del Key Lookup
    expect(posiciones.get('scan').x).not.toBe(posiciones.get('lookup').x);
  });

  it('nunca pone dos operadores en el mismo lugar', () => {
    const { posiciones } = calcularPosiciones(NODOS);
    const lugares = [...posiciones.values()].map((p) => `${p.x},${p.y}`);
    expect(new Set(lugares).size).toBe(lugares.length);
  });
});
