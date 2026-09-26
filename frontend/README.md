# Genesis-IA · Frontend

Interfaz web del auditor SQL, construida con **React 19 + Vite**.
Consume la API del backend Python (`server.py`).

## Requisitos

- Node.js 20 o superior
- Backend corriendo en `http://127.0.0.1:8000` (`python server.py` desde la raíz)

## Comandos

```bash
npm install        # instalar dependencias (solo la primera vez)
npm run dev        # servidor de desarrollo en http://localhost:5173
npm test           # pruebas (Vitest + Testing Library)
npm run lint       # análisis estático (ESLint)
npm run build      # compilación de producción en dist/
```

En desarrollo, Vite redirige `/api/*` al backend. Para usar otro host:
`GENESIS_API_URL=http://host:puerto npm run dev`.

## Estructura

```
src/
├── api/            Cliente HTTP (manejo de errores y cancelación)
├── config/         Datos de la interfaz: vistas, tipos de revisión, reglas, ejemplos
├── hooks/          Hooks reutilizables (tema, vista activa, solicitudes cancelables)
├── components/     Componentes de presentación compartidos
├── features/
│   ├── auditoria/  Revisiones por reglas (Diccionarios, Tablas, Reportes, Normales)
│   └── planes/     Análisis de planes de ejecución (.sqlplan)
├── utils/          Funciones puras (conteo por severidad, formatos)
└── styles/         CSS del diseño, separado por sección
```

### Decisiones

- **Configuración antes que condicionales.** Agregar una pestaña o un tipo de
  revisión se hace en `config/vistas.js` y `config/revisiones.js`, sin tocar
  los componentes.
- **Navegación por hash** (`#/tablas`, `#/planes`): la pestaña sobrevive a una
  recarga y se puede compartir el enlace, sin depender de un router ni de
  configurar el servidor.
- **Solicitudes cancelables.** Al cambiar de pestaña o limpiar, la solicitud en
  curso se cancela para que su respuesta no pise el estado nuevo.
- **Sin HTML inyectado.** Todo el contenido que llega del backend se pinta como
  texto (React escapa por defecto).
- **Mismo CSS del diseño original**, solo reorganizado por archivos; los
  nombres de clase se mantuvieron para que el aspecto sea idéntico.
