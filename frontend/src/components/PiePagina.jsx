export function PiePagina() {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-brand">
          <strong>Genesis IA</strong>
          <span>Auditoría de objetos SQL Server</span>
        </div>
        <p className="footer-note">
          Análisis estático local: el código revisado no sale de tu equipo.
        </p>
        <span className="footer-copy">© {new Date().getFullYear()} CAJA ICA</span>
      </div>
    </footer>
  );
}
