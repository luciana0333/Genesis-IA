# Manual de instalación de Genesis (Windows)

Guía paso a paso para descargar Genesis en otra computadora y levantarlo.
Todo el análisis se hace **en tu equipo**: los procedimientos y los planes no se envían a ningún servidor.

---

## 1. Programas que necesitas (una sola vez)

| Programa | Versión | Para qué | Descarga |
|---|---|---|---|
| **Git** | cualquiera reciente | Descargar el proyecto (`git clone`) | https://git-scm.com/download/win |
| **Python** | 3.10 o superior | El servidor que analiza (backend) | https://www.python.org/downloads/ |
| **Node.js** | 20 LTS o superior | Compilar la pantalla (frontend) | https://nodejs.org (elige la versión **LTS**) |

**Importante al instalar Python:** en la primera pantalla del instalador marca la casilla **«Add python.exe to PATH»**.

### Comprobar que quedaron instalados

Abre una **terminal nueva** (PowerShell o «Símbolo del sistema») y escribe uno por uno:

```
git --version
python --version
node --version
npm --version
```

Cada uno debe mostrar un número de versión. Si alguno dice «no se reconoce como un comando», revisa la sección **Problemas comunes**.

> Si no tienes permisos de administrador para instalar, pídeselo a soporte (TI) indicando estos tres programas.

---

## 2. Descargar el proyecto

En la terminal, ve a la carpeta donde quieras guardarlo (por ejemplo, Documentos) y clónalo:

```
cd %USERPROFILE%\Documents
git clone https://github.com/luciana0333/Genesis-IA.git
cd Genesis-IA
```

(En PowerShell, la primera línea es `cd $HOME\Documents`.)

Se descarga la rama **master**, que es la versión estable.

---

## 3. Instalar lo que necesita el proyecto (una sola vez)

Dentro de la carpeta `Genesis-IA`, ejecuta en orden:

```
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

- `pip install` instala el corrector ortográfico que usa la revisión de diccionarios.
- `npm install` (dentro de `frontend`) descarga las librerías de la pantalla; tarda unos minutos la primera vez. Si al final sugiere `npm audit fix`, puedes ignorarlo.
- `npm run build` compila la pantalla; al final debe decir **«built in …»**.
- `cd ..` vuelve a la carpeta principal `Genesis-IA`.

---

## 4. Levantar Genesis

```
python server.py
```

Cuando aparezca que el servidor está escuchando, abre el navegador en:

**http://localhost:8000**

- Para **detenerlo**: en la terminal, `Ctrl + C`.
- La terminal debe quedar **abierta** mientras lo usas.

### Prueba rápida

1. Entra a **Planes**, deja el área en **Reportes** y pulsa **«Ver ejemplo»**: deben salir 3 observaciones (escribe un límite, por ejemplo 40 s, para ver la de tiempo).
2. Cambia el área a **Negocio** y pulsa **«Ver ejemplo»**: deben salir sus observaciones.
3. Carga uno de tus planes reales (`.sqlplan`) y compáralo con Plan Explorer.

---

## 5. Uso diario

Cada vez que quieras usarlo:

```
cd %USERPROFILE%\Documents\Genesis-IA
python server.py
```

y abre http://localhost:8000.

---

## 6. Actualizar a una versión nueva

Cuando haya cambios nuevos en GitHub:

```
cd %USERPROFILE%\Documents\Genesis-IA
git pull
python -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
python server.py
```

(Repetir `install` y `build` siempre es seguro: si no cambió nada, terminan rápido.)

---

## 7. Problemas comunes

| Síntoma | Solución |
|---|---|
| `python` no se reconoce | Reinstala Python marcando **«Add python.exe to PATH»**, o usa `py` en lugar de `python` (por ejemplo `py server.py`). Cierra y vuelve a abrir la terminal. |
| `npm install` dice «Could not read package.json» | Estás en la carpeta equivocada: entra primero a `frontend` (`cd frontend`). |
| `npm` da error de «ejecución de scripts deshabilitada» en PowerShell | Usa la terminal **«Símbolo del sistema» (cmd)** en lugar de PowerShell, o escribe `npm.cmd` en lugar de `npm`. |
| `pip` o `npm` no descargan nada (red de la empresa / proxy) | Pide a TI la dirección del proxy y configúrala: `python -m pip install --proxy http://USUARIO:CLAVE@PROXY:PUERTO -r requirements.txt` y `npm config set proxy http://PROXY:PUERTO` + `npm config set https-proxy http://PROXY:PUERTO`. |
| `pip` dice que no tiene permisos | Agrega `--user`: `python -m pip install --user -r requirements.txt` |
| El navegador muestra la página pero sin estilos o en blanco | Falta compilar la pantalla: `cd frontend`, `npm run build`, `cd ..` y recarga. |
| «El puerto 8000 está en uso» | Otro programa lo ocupa. Usa otro puerto: en cmd `set GENESIS_PUERTO=8080` (en PowerShell `$env:GENESIS_PUERTO="8080"`) y luego `python server.py`; abre http://localhost:8080. |
| La revisión de diccionarios marca como error una palabra correcta del negocio | Agrégala a `app/reglas/vocabulario_tecnico.txt` (una por línea). |

---

## 8. Límites de tiempo de los planes

El límite de cada área (Reportes y Negocio) se escribe en la tarjeta **«Tiempo de ejecución»** y se guarda **en el navegador de esa computadora**. En una computadora nueva hay que escribirlo otra vez.
