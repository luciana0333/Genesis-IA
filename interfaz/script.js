document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.getElementById('themeToggle');
  const btnEjecutar = document.getElementById('btnEjecutar');
  const btnLimpiar = document.getElementById('btnLimpiar');
  const tipoRevision = document.getElementById('tipoRevision');
  const labelObjeto = document.getElementById('labelObjeto');
  const sqlObject = document.getElementById('sqlObject');
  const sqlHint = document.getElementById('sqlHint');
  const sqlLabel = document.getElementById('sqlLabel');
  const dictLabel = document.getElementById('dictLabel');
  const dictHint = document.querySelector('#dictionaryEditorCard .editor-hint');
  const tablaFields = document.querySelectorAll('.table-only-field');
  const navDiccionarios = document.getElementById('navDiccionarios');
  const navTablas = document.getElementById('navTablas');
  const navReportes = document.getElementById('navReportes');

  const sqlProcedimiento = `CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Consultar
    @nClienteId INT
AS
BEGIN
    SELECT nClienteId, cCodPersona, cCorreoElectronico
    FROM CLICKTOPAY.Cliente
    WHERE nClienteId = @nClienteId;
END;`;
  const sqlTabla = `CREATE TABLE CLICKTOPAY.Cliente (
    nClienteId INT PRIMARY KEY IDENTITY(1,1) NOT NULL COLLATE Latin1_General_CI_AS,
    cCodPersona VARCHAR(20) NOT NULL COLLATE Latin1_General_CI_AS,
    cCorreoElectronico VARCHAR(64) NOT NULL COLLATE Latin1_General_CI_AS
);`;
  const sqlReporte = `ALTER PROCEDURE dbo.PA_BI_Reporte
AS
BEGIN
    SELECT cCodigo, cNombre
    FROM dbo.Cliente WITH(NOLOCK);
END;`;
  const diccionarioProcedimiento = `EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Consulta la informacion del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Consultar'
GO`;
  const diccionarioTabla = `EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla que almacena la informacion del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'TABLE', @level1name=N'CLIENTE'
GO`;

  function actualizarFormulario() {
    const esTabla = tipoRevision.value === 'tabla';
    const esVistaTablas = document.body.classList.contains('table-workspace');
    const esVistaReportes = document.body.classList.contains('report-workspace');
    tablaFields.forEach((field) => {
      field.style.display = esVistaTablas ? 'flex' : 'none';
    });
    if (esVistaTablas) {
      sqlLabel.textContent = 'Script de tabla (CREATE / ALTER)';
      dictLabel.textContent = 'Código del diccionario de tabla';
      dictHint.innerHTML = 'Pega aquí el script de <code>sp_addextendedproperty</code> para la tabla y sus columnas.';
      sqlHint.textContent = 'Pega aquí el script completo de CREATE TABLE o ALTER TABLE.';
      return;
    }

    if (esVistaReportes) {
      sqlLabel.textContent = 'SQL del procedimiento de reporte';
      sqlHint.textContent = 'Pega aquí el CREATE o ALTER PROCEDURE completo para aplicar las reglas de reportes.';
      return;
    }

    sqlLabel.textContent = esTabla ? 'SQL de la tabla (CREATE / ALTER)' : 'SQL del procedimiento';
    dictLabel.textContent = esTabla
      ? 'Código del diccionario de tabla'
      : 'Código del diccionario de procedimiento';
    dictHint.innerHTML = esTabla
      ? 'Pega aquí el script de <code>sp_addextendedproperty</code> para la tabla y sus columnas.'
      : 'Pega aquí el script de <code>sp_addextendedproperty</code> para el procedimiento y sus parámetros.';
    sqlHint.textContent = esTabla
      ? 'Pega aquí el código CREATE TABLE o ALTER TABLE.'
      : 'Pega aquí el código del procedimiento almacenado.';
  }

  function cambiarVista(vista) {
    const esTabla = vista === 'tabla';
    const esReporte = vista === 'reporte';
    tipoRevision.value = esTabla ? 'tabla' : esReporte ? 'reporte' : 'procedimiento';
    sqlObject.value = esTabla ? sqlTabla : esReporte ? sqlReporte : sqlProcedimiento;
    document.getElementById('dictScript').value = esTabla || esReporte ? '' : diccionarioProcedimiento;
    navDiccionarios.classList.toggle('active', !esTabla && !esReporte);
    navTablas.classList.toggle('active', esTabla);
    navReportes.classList.toggle('active', esReporte);
    document.body.classList.toggle('table-workspace', esTabla);
    document.body.classList.toggle('report-workspace', esReporte);
    labelObjeto.textContent = esTabla ? 'Nombre de la Tabla' : 'Nombre del Procedimiento';
    actualizarFormulario();
  }

  // Alternar Modo Oscuro
  themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
  });

  navDiccionarios.addEventListener('click', (event) => {
    event.preventDefault();
    cambiarVista('diccionario');
  });

  navTablas.addEventListener('click', (event) => {
    event.preventDefault();
    cambiarVista('tabla');
  });

  navReportes.addEventListener('click', (event) => {
    event.preventDefault();
    cambiarVista('reporte');
  });

  // Cambiar Label según selección
  tipoRevision.addEventListener('change', (e) => {
    const esTabla = e.target.value === 'tabla';
    const esReporte = e.target.value === 'reporte';
    document.body.classList.toggle('report-workspace', esReporte);
    labelObjeto.textContent = esTabla ? 'Nombre de la Tabla' : 'Nombre del Procedimiento';
    if (!document.body.classList.contains('table-workspace')) {
      sqlObject.value = esTabla ? sqlTabla : esReporte ? sqlReporte : sqlProcedimiento;
      document.getElementById('dictScript').value = esTabla || esReporte ? '' : diccionarioProcedimiento;
    }
    actualizarFormulario();
  });

  // Evento de Limpieza
  btnLimpiar.addEventListener('click', () => {
    document.getElementById('objetoNombre').value = '';
    document.getElementById('sqlObject').value = '';
    document.getElementById('dictScript').value = '';
    document.getElementById('esDbcmaica').checked = false;
    renderizarResultados([]);
  });

  btnEjecutar.addEventListener('click', async () => {
    const payload = {
      tipoRevision: document.body.classList.contains('table-workspace')
        ? 'tabla_estructura'
        : tipoRevision.value,
      objetoNombre: document.getElementById('objetoNombre').value,
      sqlObject: document.getElementById('sqlObject').value,
      dictScript: document.getElementById('dictScript').value,
      esDbcmaica: document.getElementById('esDbcmaica').checked,
      modoRevision: document.body.classList.contains('table-workspace')
        ? 'tabla_estructura'
        : 'diccionario'
    };

    if (!payload.sqlObject.trim()) {
      renderizarEstado('Completa el SQL del objeto para iniciar la revisión.');
      return;
    }

    btnEjecutar.disabled = true;
    renderizarEstado('Analizando las reglas del diccionario...');

    try {
      const response = await fetch('/api/analizar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'No se pudo completar la revisión.');
      }

      renderizarResultados(data.hallazgos || []);
    } catch (error) {
      renderizarEstado(error.message || 'No se pudo conectar con el servidor.');
      actualizarContadores(0, 0, 0, 0);
    } finally {
      btnEjecutar.disabled = false;
    }
  });

  cambiarVista('diccionario');
});

const nombresReglas = {
  ESQUEMA_NO_COINCIDE: 'Esquema no coincide',
  NOMBRE_NO_COINCIDE: 'Nombre no coincide',
  NOMBRE_TABLA_NO_COINCIDE: 'Nombre de tabla no coincide',
  PARAMETRO_SIN_DESCRIPCION: 'Parámetro sin descripción',
  PARAMETRO_FALTANTE: 'Parámetro faltante',
  COLUMNA_SIN_DESCRIPCION: 'Columna sin descripción',
  COLUMNA_FALTANTE: 'Columna faltante',
  TABLA_SIN_DESCRIPCION: 'Tabla sin descripción',
  DESCRIPCION_VACIA: 'Descripción vacía',
  DESCRIPCION_COLUMNA_VACIA: 'Descripción de columna vacía',
  ALTER_SIN_DICCIONARIO: 'ALTER sin diccionario',
  VALOR_SIN_COMILLAS: 'Valor sin comillas',
  TABLA_SIN_ESQUEMA: 'Tabla sin esquema',
  COLUMNA_SIN_NOT_NULL_NI_DEFAULT: 'Columna sin NOT NULL ni DEFAULT',
  COLUMNA_SIN_COLLATE: 'Columna sin COLLATE',
  COLUMNA_PREFIJO_TIPO_INVALIDO: 'Prefijo de columna inválido',
  TABLA_CON_PALABRA_OMITIBLE: 'Nombre de tabla con palabra omitible',
  COLLATE_EN_TIPO_NO_TEXTO: 'COLLATE en tipo no textual',
  TABLA_FISICA_SIN_NOLOCK: 'Tabla física sin NOLOCK',
  NOLOCK_EN_TABLA_TEMPORAL: 'NOLOCK en tabla temporal',
  HINT_PLAN_PROHIBIDO: 'Hint de plan prohibido',
  CODIGO_SQL_COMENTADO: 'Código SQL comentado',
  TEMPORAL_TEXTO_SIN_COLLATE: 'Texto temporal sin COLLATE',
  SELECT_INTO_PROHIBIDO: 'SELECT INTO prohibido',
  SELECT_ESTRELLA_PROHIBIDO: 'SELECT estrella prohibido',
  IN_CON_UN_SOLO_VALOR: 'IN con un solo valor',
  CATALOGO_SISTEMA_PROHIBIDO: 'Catálogo de sistema prohibido',
  MODIFICACION_TABLA_FISICA: 'Modificación de tabla física',
  VARIABLE_DECLARADA_SIN_USO: 'Variable declarada sin uso'
};

const etiquetasSeveridad = {
  critico: 'Crítico',
  alto: 'Alto',
  medio: 'Medio',
  bajo: 'Bajo'
};

function renderizarResultados(lista) {
  const resultsList = document.getElementById('resultsList');
  const emptyState = document.getElementById('emptyState');

  let countCritico = 0, countAlto = 0, countMedio = 0, countBajo = 0;

  resultsList.innerHTML = '';

  if (!lista || lista.length === 0) {
    renderizarEstado('La revisión terminó sin hallazgos.');
    actualizarContadores(0, 0, 0, 0);
    return;
  }

  emptyState.style.display = 'none';

  lista.forEach((item) => {
    const sev = item.severidad.toLowerCase();

    if (sev === 'critico') countCritico++;
    if (sev === 'alto') countAlto++;
    if (sev === 'medio') countMedio++;
    if (sev === 'bajo') countBajo++;

    const card = document.createElement('div');
    card.className = `finding-card ${sev}`;

    const header = document.createElement('div');
    header.className = 'finding-header';
    const titleWrap = document.createElement('div');
    titleWrap.className = 'finding-title-wrap';
    const badge = document.createElement('span');
    badge.className = `finding-badge ${sev}`;
    badge.textContent = etiquetasSeveridad[sev] || sev;
    const title = document.createElement('h4');
    title.className = 'finding-title';
    title.textContent = nombresReglas[item.regla] || item.regla || 'Hallazgo de auditoría';
    titleWrap.append(badge, title);

    const meta = document.createElement('span');
    meta.className = 'finding-meta';
    meta.textContent = `Línea ${item.linea || 1} · ${item.origen || 'diccionario'}`;
    header.append(titleWrap, meta);

    const body = document.createElement('p');
    body.className = 'finding-body';
    body.textContent = item.mensaje || item.descripcion || 'Revisa este hallazgo.';
    card.append(header, body);

    resultsList.appendChild(card);
  });

  actualizarContadores(countCritico, countAlto, countMedio, countBajo);
}

function actualizarContadores(c, a, m, b) {
  document.getElementById('countCritico').textContent = c;
  document.getElementById('countAlto').textContent = a;
  document.getElementById('countMedio').textContent = m;
  document.getElementById('countBajo').textContent = b;
}

function renderizarEstado(mensaje) {
  const emptyState = document.getElementById('emptyState');
  document.getElementById('resultsList').innerHTML = '';
  emptyState.style.display = 'block';
  emptyState.textContent = mensaje;
}