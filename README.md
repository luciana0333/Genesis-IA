# Genesis

Auditor de objetos SQL Server: revisa diccionarios (`sp_addextendedproperty`),
estructura de tablas, procedimientos de reportes, procedimientos normales y
planes de ejecución reales (`.sqlplan`) mediante reglas estáticas.

## Estructura

```
app/        Analizadores y reglas (Python, sin dependencias externas)
frontend/   Interfaz web (React + Vite) — ver frontend/README.md
pruebas/    Pruebas unitarias de los analizadores
recursos/   Archivos de ejemplo (planes de ejecución)
server.py   Servidor HTTP: API + interfaz compilada
```

## Puesta en marcha

> Paso a paso para instalarlo en otra computadora (Windows): ver [MANUAL_INSTALACION.md](MANUAL_INSTALACION.md).

Requisitos: Python 3.10+ y Node.js 20+.

```bash
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python server.py
```

`python server.py` se reinicia solo cuando cambia un archivo `.py` del backend
(`server.py` o `app/`), así que basta con recargar la página. Para correrlo sin
recarga automática: `python server.py --sin-recarga`. El puerto se puede cambiar
con la variable `GENESIS_PUERTO` (por defecto, 8000).

`requirements.txt` instala `pyspellchecker`, que revisa la ortografía de las
descripciones del diccionario. Si el corrector marca como error una palabra
correcta del negocio, agréguela a `app/reglas/vocabulario_tecnico.txt`.

Abrir http://localhost:8000.

### Desarrollo de la interfaz

Con `python server.py` corriendo, en otra terminal:

```bash
npm --prefix frontend run dev
```

Abrir http://localhost:5173 (recarga en caliente; `/api` se redirige al puerto 8000).

## API

| Método | Ruta                 | Descripción                                        |
|--------|----------------------|----------------------------------------------------|
| GET    | `/api/health`        | Estado del servidor                                |
| POST   | `/api/analizar`      | Revisa un objeto SQL (JSON)                        |
| POST   | `/api/analizar-plan` | Analiza un plan `.sqlplan` (multipart, máx. 25 MB) |

## Pruebas

```bash
python -m unittest pruebas.tablas.test_analizador_tablas
npm --prefix frontend test
```
