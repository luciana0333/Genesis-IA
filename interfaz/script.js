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
  const navNormales = document.getElementById('navNormales');
  const navPlanes = document.getElementById('navPlanes');
  const planFile = document.getElementById('planFile');
  const btnAnalizarPlan = document.getElementById('btnAnalizarPlan');
  const btnLimpiarPlan = document.getElementById('btnLimpiarPlan');
  const planFileName = document.getElementById('planFileName');
  const planStatus = document.getElementById('planStatus');
  const heroTitle = document.getElementById('heroTitle');
  const heroDescription = document.getElementById('heroDescription');

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
  const sqlNormal = `ALTER PROCEDURE dbo.PA_Cliente_Actualizar
    @nClienteId INT,
    @cNombre VARCHAR(100)
AS
BEGIN
    UPDATE dbo.Cliente
    SET cNombre = @cNombre
    WHERE nClienteId = @nClienteId;
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
    const esVistaNormales = document.body.classList.contains('normal-workspace');
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

    if (esVistaNormales) {
      sqlLabel.textContent = 'SQL del procedimiento normal';
      sqlHint.textContent = 'Pega aquí el CREATE o ALTER PROCEDURE para aplicar las reglas generales.';
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

  function actualizarHero(vista) {
    const encabezados = {
      diccionario: {
        titulo: 'Revisión e inspección de Diccionarios SQL',
        descripcion: 'Valida la estructura, consistencia y estándares de documentación de tus bases de datos SQL Server en tiempo real.'
      },
      tabla: {
        titulo: 'Revisión e inspección de Tablas SQL',
        descripcion: 'Valida la estructura, nomenclatura, tipos de datos, nulabilidad y reglas de diseño de tus tablas SQL Server.'
      },
      reporte: {
        titulo: 'Revisión e inspección de Reportes SQL',
        descripcion: 'Revisa procedimientos de reportes para detectar prácticas inseguras, lecturas innecesarias y consultas que dificultan su mantenimiento.'
      },
      normal: {
        titulo: 'Revisión e inspección de Procedimientos SQL',
        descripcion: 'Valida procedimientos almacenados normales frente a reglas de control de flujo, consultas y buenas prácticas de desarrollo.'
      },
      planes: {
        titulo: 'Revisión e inspección de Planes de ejecución SQL',
        descripcion: 'Analiza planes reales de SQL Server para detectar conversiones implícitas, spills, scans, lecturas elevadas y problemas de memoria.'
      }
    };
    const encabezado = encabezados[vista] || encabezados.diccionario;
    heroTitle.textContent = encabezado.titulo;
    heroDescription.textContent = encabezado.descripcion;
  }

  function cambiarVista(vista) {
    const esPlan = vista === 'planes';
    const esTabla = vista === 'tabla';
    const esReporte = vista === 'reporte';
    const esNormal = vista === 'normal';
    tipoRevision.value = esTabla ? 'tabla' : esReporte ? 'reporte' : esNormal ? 'procedimiento_normal' : 'procedimiento';
    sqlObject.value = esTabla ? sqlTabla : esReporte ? sqlReporte : esNormal ? sqlNormal : sqlProcedimiento;
    document.getElementById('dictScript').value = esTabla || esReporte ? '' : diccionarioProcedimiento;
    navDiccionarios.classList.toggle('active', vista === 'diccionario');
    navTablas.classList.toggle('active', esTabla);
    navReportes.classList.toggle('active', esReporte);
    navNormales.classList.toggle('active', esNormal);
    navPlanes.classList.toggle('active', esPlan);
    document.body.classList.toggle('table-workspace', esTabla);
    document.body.classList.toggle('report-workspace', esReporte);
    document.body.classList.toggle('normal-workspace', esNormal);
    document.body.classList.toggle('plan-workspace', esPlan);
    actualizarHero(vista);
    if (esPlan) {
      return;
    }
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

  navNormales.addEventListener('click', (event) => {
    event.preventDefault();
    cambiarVista('normal');
  });

  navPlanes.addEventListener('click', (event) => {
    event.preventDefault();
    cambiarVista('planes');
  });

  // Cambiar Label según selección
  tipoRevision.addEventListener('change', (e) => {
    const esTabla = e.target.value === 'tabla';
    const esReporte = e.target.value === 'reporte';
    const esNormal = e.target.value === 'procedimiento_normal';
    document.body.classList.toggle('report-workspace', esReporte);
    document.body.classList.toggle('normal-workspace', esNormal);
    labelObjeto.textContent = esTabla ? 'Nombre de la Tabla' : 'Nombre del Procedimiento';
    if (!document.body.classList.contains('table-workspace')) {
      sqlObject.value = esTabla ? sqlTabla : esReporte ? sqlReporte : esNormal ? sqlNormal : sqlProcedimiento;
      document.getElementById('dictScript').value = esTabla || esReporte || esNormal ? '' : diccionarioProcedimiento;
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

  planFile.addEventListener('change', () => {
    planFileName.textContent = planFile.files[0]?.name || 'Ningún archivo seleccionado';
    planStatus.textContent = '';
  });

  btnLimpiarPlan.addEventListener('click', () => {
    planFile.value = '';
    planFileName.textContent = 'Ningún archivo seleccionado';
    planStatus.textContent = '';
    renderizarPlanResultados(null);
  });

  btnAnalizarPlan.addEventListener('click', async () => {
    const archivo = planFile.files[0];
    if (!archivo) {
      planStatus.textContent = 'Selecciona un archivo .sqlplan.';
      return;
    }
    if (!archivo.name.toLowerCase().endsWith('.sqlplan')) {
      planStatus.textContent = 'El archivo debe tener extensión .sqlplan.';
      return;
    }

    const formulario = new FormData();
    formulario.append('plan', archivo);
    btnAnalizarPlan.disabled = true;
    planStatus.textContent = 'Analizando el plan real...';
    try {
      const response = await fetch('/api/analizar-plan', { method: 'POST', body: formulario });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'No se pudo analizar el plan.');
      }
      renderizarPlanResultados(data);
      planStatus.textContent = 'Análisis completado.';
    } catch (error) {
      renderizarPlanResultados(null);
      planStatus.textContent = error.message || 'No se pudo conectar con el servidor.';
    } finally {
      btnAnalizarPlan.disabled = false;
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
  VARIABLE_DECLARADA_SIN_USO: 'Variable declarada sin uso',
  CONVERSION_IMPLICITA: 'Conversión implícita',
  SPILL_TEMPDB: 'Spill hacia TempDB',
  TABLE_SCAN: 'Table Scan',
  LECTURAS_LOGICAS_ELEVADAS: 'Lecturas lógicas elevadas',
  SOBREESTIMACION_FILAS: 'Desviación de cardinalidad',
  MEMORIA_CONCEDIDA_SOBREDIMENSIONADA: 'Memoria concedida sobredimensionada',
  VARBINARY_DOCUMENTO_IDENTIFICADO: 'VARBINARY para documento identificado'
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

function renderizarPlanResultados(data) {
  const resultsList = document.getElementById('planResultsList');
  const emptyState = document.getElementById('planEmptyState');
  const resumen = data?.resumen || { critico: 0, alto: 0, medio: 0, bajo: 0 };
  const memoria = data?.memoria;

  document.getElementById('planOperatorCount').textContent = data?.operadores?.length || 0;
  document.getElementById('planGrantedMemory').textContent = memoria?.concedidaKb
    ? `${Math.round(memoria.concedidaKb).toLocaleString()} KB`
    : '--';
  document.getElementById('planUsedMemory').textContent = memoria?.maximaUtilizadaKb
    ? `${Math.round(memoria.maximaUtilizadaKb).toLocaleString()} KB`
    : '--';
  document.getElementById('planFindingCount').textContent = data?.hallazgos?.length || 0;
  document.getElementById('planResultFile').textContent = data?.archivo || '';
  resultsList.innerHTML = '';

  if (!data) {
    emptyState.style.display = 'block';
    emptyState.textContent = 'Selecciona un archivo .sqlplan para iniciar el análisis.';
    return;
  }
  if (!data.hallazgos?.length) {
    emptyState.style.display = 'block';
    emptyState.textContent = 'El plan terminó sin hallazgos según las reglas activas.';
    return;
  }

  emptyState.style.display = 'none';
  data.hallazgos.forEach((item) => {
    const sev = item.severidad.toLowerCase();
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
    title.textContent = nombresReglas[item.regla] || item.regla;
    titleWrap.append(badge, title);
    const meta = document.createElement('span');
    meta.className = 'finding-meta';
    meta.textContent = `${item.origen || 'plan_ejecucion'} · Línea ${item.linea || 1}`;
    header.append(titleWrap, meta);
    const body = document.createElement('p');
    body.className = 'finding-body';
    body.textContent = item.mensaje;
    card.append(header, body);
    resultsList.appendChild(card);
  });

  actualizarContadores(resumen.critico, resumen.alto, resumen.medio, resumen.bajo);
}