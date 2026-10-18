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

1. Entra a **Planes**, deja el área en **Reportes** y pulsa **«Ver ejemplo»**: deben salir sus observaciones (escribe un límite, por ejemplo 40 s, para ver la de tiempo).
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
| La revisión de diccionarios marca como error una palabra correcta del negocio | Agrégala a `app/reglas/vocabulario_tecnico.txt` (una por línea). |
| Una descripción sugerida sale vacía («Completar») o con una abreviatura sin traducir | Agrega la abreviatura o la palabra del negocio en `app/reglas/glosario_diccionario.txt` (por ejemplo `cta = cuenta`) y reinicia el servidor. |

---

## 8. Límites de tiempo de los planes

El límite de cada área (Reportes y Negocio) se escribe en la tarjeta **«Tiempo de ejecución»** y se guarda **en el navegador de esa computadora**. En una computadora nueva hay que escribirlo otra vez.

---

## 9. Solo para quien modifica Genesis (no hace falta para usarlo)

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
