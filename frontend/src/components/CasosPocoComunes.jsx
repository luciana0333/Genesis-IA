/**
 * «Casos poco comunes» (usuaria, 21 nov.; diseño B): diseños fuera del estándar que pueden estar justificados
 * (p. ej. una clave primaria heredada de su tabla padre). Van en su propio recuadro, debajo de las demás
 * observaciones, para validarlos con el DBA. Cada caso es una ficha con sus acciones (Ver en el código, Copiar).
 */
export function CasosPocoComunes({ cantidad, children }) {
  return (
    <section className="poco-comun" aria-labelledby="poco-comun-titulo">
      <header className="poco-comun-cabecera">
        <div className="poco-comun-textos">
          <span className="section-eyebrow">Casos poco comunes</span>
          <h3 id="poco-comun-titulo" className="poco-comun-titulo">Validar con el DBA</h3>
          <p className="poco-comun-descripcion">Diseños fuera del estándar que pueden estar justificados.</p>
        </div>
        <span className="poco-comun-cantidad">{cantidad === 1 ? '1 caso' : `${cantidad} casos`}</span>
      </header>
      <div className="poco-comun-lista">{children}</div>
    </section>
  );
}
