document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.getElementById('themeToggle');
  const btnEjecutar = document.getElementById('btnEjecutar');
  const btnLimpiar = document.getElementById('btnLimpiar');
  const tipoRevision = document.getElementById('tipoRevision');
  const labelObjeto = document.getElementById('labelObjeto');

  // Alternar Modo Oscuro
  themeToggle.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
  });

  // Cambiar Label según selección
  tipoRevision.addEventListener('change', (e) => {
    labelObjeto.textContent = e.target.value === 'tabla' ? 'Nombre de la Tabla' : 'Nombre del Procedimiento';
  });

  // Evento de Limpieza
  btnLimpiar.addEventListener('click', () => {
    document.getElementById('objetoNombre').value = '';
    document.getElementById('sqlObject').value = '';
    document.getElementById('dictScript').value = '';
    renderizarResultados([]);
  });

  btnEjecutar.addEventListener('click', async () => {
    const payload = {
      tipoRevision: tipoRevision.value,
      objetoNombre: document.getElementById('objetoNombre').value,
      sqlObject: document.getElementById('sqlObject').value,
      dictScript: document.getElementById('dictScript').value
    };

    if (!payload.sqlObject.trim() || !payload.dictScript.trim()) {
      renderizarEstado('Completa el SQL del objeto y el diccionario para iniciar la revisión.');
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
});

const nombresReglas = {
  ESQUEMA_NO_COINCIDE: 'Esquema no coincide',
  NOMBRE_NO_COINCIDE: 'Nombre no coincide',
  NOMBRE_TABLA_NO_COINCIDE: 'Nombre de tabla no coincide',
  PARAMETRO_SIN_DESCRIPCION: 'Parámetro sin descripción',
  COLUMNA_SIN_DESCRIPCION: 'Columna sin descripción',
  TABLA_SIN_DESCRIPCION: 'Tabla sin descripción',
  DESCRIPCION_VACIA: 'Descripción vacía',
  DESCRIPCION_COLUMNA_VACIA: 'Descripción de columna vacía',
  ALTER_SIN_DICCIONARIO: 'ALTER sin diccionario',
  VALOR_SIN_COMILLAS: 'Valor sin comillas'
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