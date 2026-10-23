# Manual de instalación de Genesis (Windows)

Guía paso a paso para descargar Genesis en otra computadora y levantarlo.
Todo el análisis se hace **en tu equipo**: los procedimientos y los planes no se envían a ningún servidor.

> **Novedad:** la pantalla de Genesis ya viene **compilada** en GitHub (carpeta `frontend/dist`) y con sus
> **fuentes incluidas**. Para usar Genesis **no hace falta Node.js ni npm**: solo Git y Python. Así funciona
> también en la red de la Caja, donde `npm install` está bloqueado.

---

## 1. Programas que necesitas (una sola vez)

| Programa | Versión | Para qué | Descarga |
|---|---|---|---|
| **Git** | cualquiera reciente | Descargar y actualizar el proyecto | https://git-scm.com/download/win |
| **Python** | 3.10 o superior | El servidor que analiza y muestra la pantalla | https://www.python.org/downloads/ |

**Importante al instalar Python:** en la primera pantalla del instalador marca la casilla **«Add python.exe to PATH»**.

### Comprobar que quedaron instalados

Abre una **terminal nueva** (PowerShell o «Símbolo del sistema») y escribe uno por uno:

```
git --version
python --version
```

Cada uno debe mostrar un número de versión. Si alguno dice «no se reconoce como un comando», revisa la sección **Problemas comunes**.

> Si no tienes permisos de administrador para instalar, pídeselo a soporte (TI) indicando estos dos programas.

---

## 2. Descargar el proyecto (una sola vez)

En la terminal, ve a la carpeta donde quieras guardarlo (por ejemplo, Documentos) y clónalo:

```
cd %USERPROFILE%\Documents
git clone https://github.com/luciana0333/Genesis-IA.git
cd Genesis-IA
```

(En PowerShell, la primera línea es `cd $HOME\Documents`.)

Se descarga la rama **master**, que es la versión estable, con la pantalla ya lista.

---

## 3. Complementos opcionales de Python (una sola vez)

```
python -m pip install -r requirements.txt
```

Instala dos complementos. **Genesis funciona aunque este paso falle**:

| Complemento | Para qué | Si no se instala |
|---|---|---|
| Corrector ortográfico (`pyspellchecker`) | Revisa la ortografía de las descripciones del diccionario | No se revisa la ortografía |
| spaCy y su modelo de español (unos 50 MB) | Redacta las descripciones sugeridas de «Generar diccionario faltante» | Las sugerencias usan reglas más simples |

Si la red bloquea la descarga completa, prueba solo el corrector, que es pequeño:

```
python -m pip install pyspellchecker==0.9.0
```

---

## 4. Levantar Genesis

```
python server.py
```

Cuando aparezca **«Servidor Genesis corriendo en http://localhost:8000»**, abre el navegador en:

**http://localhost:8000**

- Para **detenerlo**: en la terminal, `Ctrl + C`.
- La terminal debe quedar **abierta** mientras lo usas.
- Si sale «AVISO: … no está instalado», es solo informativo (ver el paso 3): Genesis funciona igual.

### Prueba rápida

1. Entra a **Planes**, deja el área en **Reportes** y pulsa **«Ver ejemplo»**: deben salir sus observaciones (escribe en el Paso 1 un límite, por ejemplo 0 min 40 s, para ver la de tiempo).
2. Cambia el área a **Negocio** y pulsa **«Ver ejemplo»**: deben salir sus observaciones.
3. Pulsa **«Ejemplo de lote»**: debe salir el resumen con 3 planes (el más lento primero) y «1 archivo no se revisó».
4. Carga uno de tus planes reales (`.sqlplan`) y compáralo con Plan Explorer.

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
python server.py
```

Eso es todo: `git pull` trae también la pantalla ya compilada. Solo si cambió `requirements.txt`, repite el paso 3.

### Si ya habías intentado compilar con npm en esa computadora

Los intentos anteriores pueden haber dejado una carpeta `frontend\dist` a medio crear. Si `git pull` responde
**«untracked working tree files would be overwritten by merge»**, bórrala y vuelve a intentar:

```
rmdir /s /q frontend\dist
git pull
```

(En PowerShell: `Remove-Item -Recurse -Force frontend\dist`.) La carpeta `frontend\node_modules`, si existe, no estorba: puedes dejarla o borrarla.

---

## 7. Problemas comunes

| Síntoma | Solución |
|---|---|
| `python` no se reconoce | Reinstala Python marcando **«Add python.exe to PATH»**, o usa `py` en lugar de `python` (por ejemplo `py server.py`). Cierra y vuelve a abrir la terminal. |
| `git pull` dice «untracked working tree files would be overwritten» | Borra `frontend\dist` como indica el paso 6 y repite `git pull`. |
| `git pull` dice que tienes cambios locales | En esa computadora no se edita Genesis: descarta los cambios con `git checkout -- .` y repite `git pull`. |
| `pip` no descarga nada (red de la empresa / proxy) | Genesis funciona igual (ver el paso 3). Si quieres los complementos, pide a TI la dirección del proxy: `python -m pip install --proxy http://USUARIO:CLAVE@PROXY:PUERTO -r requirements.txt` |
| `pip` dice que no tiene permisos | Agrega `--user`: `python -m pip install --user -r requirements.txt` |
| El navegador muestra la página en blanco o sin estilos | Falta la pantalla compilada: revisa que exista `frontend\dist\index.html`. Si no está, haz `git pull`. |
| «El puerto 8000 está en uso» | Otro programa lo ocupa. Usa otro puerto: en cmd `set GENESIS_PUERTO=8080` (en PowerShell `$env:GENESIS_PUERTO="8080"`) y luego `python server.py`; abre http://localhost:8080. |
| Un `.rar` sale como «No se pudo abrir el .rar» | Ábrelo con clic derecho → **«Extraer todo»** (o con WinRAR / 7-Zip) y sube los planes o la carpeta extraída. |
| La revisión de diccionarios marca como error una palabra correcta del negocio | Agrégala a `app/reglas/vocabulario_tecnico.txt` (una por línea). |
| Genesis pide validar una sigla que sí es correcta (ej.: «sigla por validar: TPPP») | Agrégala con su significado a `app/reglas/siglas.txt` (ej.: `TPPP = Tasa Promedio Ponderada Pasiva`) y reinicia el servidor. Desde entonces se acepta en tablas, columnas y procedimientos. |
| Una descripción sugerida sale vacía («Completar») o con una abreviatura sin traducir | Agrega la abreviatura o la palabra del negocio en `app/reglas/glosario_diccionario.txt` (por ejemplo `cta = cuenta`) y reinicia el servidor. |

---

## 8. Revisar varios planes a la vez (lote)

En **Planes** puedes subir, de una sola vez:

- varios `.sqlplan` (en la ventana para elegir archivos, márcalos con Ctrl + clic o todos con Ctrl + A),
- una carpeta completa (arrástrala a la zona de archivos),
- el `.zip` o `.rar` tal como llegó en el correo (aunque traiga carpetas adentro).

Antes de pulsar **«Analizar planes»**, elige el área (**Reportes** o **Negocio**) y su **límite de tiempo**: todo el lote se revisa con las reglas y el límite de esa área. Si un correo trae planes de las dos áreas, súbelos en dos tandas.

- Genesis reconoce los planes por su contenido; los archivos que no son planes, los repetidos y los dañados se listan en **«archivos no se revisaron»** con el motivo, sin detener a los demás.
- El resumen muestra el procedimiento, el tiempo total de cada plan (en rojo si supera el límite) y sus hallazgos por severidad. **«Ver detalle»** abre el plan completo (diagrama, observaciones, «Copiar imagen»), y **Anterior / Siguiente** pasa al otro sin volver a subir nada.
- **«Copiar resumen»** copia la tabla para pegarla en Word o en el correo.
- Si subes un solo `.sqlplan`, la revisión es la de siempre.
- Límites: hasta 60 planes por lote, 25 MB por plan y 200 MB en total.
- Los `.rar` se abren con la herramienta que ya trae Windows 10/11; no hace falta instalar nada.

---

## 9. Límites de tiempo de los planes

El límite de cada área (Reportes y Negocio) se fija en el **Paso 1**, en el campo **«Límite de tiempo»** junto al área (minutos y segundos; si pones más de 59 segundos se pasan solos a minutos), **antes de analizar**; vale para un plan suelto o para todo el lote. En el detalle de cada plan, la tarjeta **«Tiempo de ejecución»** solo lo muestra. Si lo cambias con un resultado en pantalla, se vuelve a revisar solo.

Se guarda **en el navegador de esa computadora**: en una computadora nueva hay que escribirlo otra vez.

---

## 10. Solo para quien modifica Genesis (no hace falta para usarlo)

Para cambiar la pantalla se necesita además **Node.js 20 LTS** (https://nodejs.org) y una red que permita `npm install`.
Después de cada cambio en `frontend/src` hay que volver a compilar y subir también la carpeta `frontend/dist`:

```
cd frontend
npm install
npm run build
cd ..
git add frontend/dist
```

`npm run build` debe terminar con **«built in …»**. Si `npm` da error de «ejecución de scripts deshabilitada» en PowerShell, usa la terminal **«Símbolo del sistema» (cmd)** o escribe `npm.cmd`.
