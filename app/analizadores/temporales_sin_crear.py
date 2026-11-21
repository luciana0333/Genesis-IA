"""Tabla temporal usada sin crear (compartido por Reportes y Procedimientos de negocio).

SQL Server no revisa las tablas temporales al guardar el procedimiento, sino al ejecutarlo: si se usa #X y
nunca se crea, el ALTER PROCEDURE se guarda sin problema y el error («El nombre de objeto '#X' no es válido»)
aparece recién cuando alguien lo ejecuta (caso de la usuaria, 7 nov.: #TempPre2 en el reporte de libro caja).

Tabla temporal externa (usuaria, 13 nov.): un PA puede usar una temporal local que crea el PA que lo llama (cada
sesión tiene la suya, no se mezclan). Si su creación está documentada en el ENCABEZADO (el CREATE TABLE #X o el
SELECT … INTO #X dentro de los comentarios del encabezado, como en la sección «Pruebas»), no es un error: es
«Tabla temporal externa» (bajo). Sin esa documentación sigue siendo «Tabla temporal usada sin crear» (crítico).
Un CREATE comentado dentro del cuerpo no cuenta: suele ser código viejo.

Validar tabla temporal sin crear (usuaria, 21 nov.): sin documentación en el encabezado, lo más probable es que la
cree el procedimiento que lo llama (p. ej. los PA del motor y su #BaseHechos). Solo sigue en crítico cuando el
procedimiento crea una temporal de nombre muy parecido (casi siempre un error de escritura, como #TempPre2); el resto
es «validar» (medio), con lo que el procedimiento hace con cada una (se lee, se actualiza…).
"""

import difflib
import re
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.analizadores.encabezado import comentarios_del_encabezado

_TEMPORAL = r"\[#(?!#)[^\]]+\]|#(?!#)[A-Za-z_][\w$#]*"  # #T o [#T] (las globales ##T no se revisan)

# Dónde se crea: CREATE TABLE #T o SELECT ... INTO #T (el INTO de un INSERT no crea, usa).
_CREA = re.compile(rf"\bCREATE\s+TABLE\s+({_TEMPORAL})|(?<!INSERT)(?<!INSERT\s)\bINTO\s+({_TEMPORAL})", re.IGNORECASE)
_INSERT_INTO = re.compile(rf"\bINSERT\s+(?:INTO\s+)?({_TEMPORAL})", re.IGNORECASE)

# Dónde se usa: leer, insertar, actualizar, borrar, vaciar o indexar (DROP no cuenta: borrarla no es usarla).
_USA = re.compile(
    rf"(?<![\w@#$])(?:FROM|JOIN|UPDATE|DELETE(?:\s+FROM)?|TRUNCATE\s+TABLE|MERGE(?:\s+INTO)?|APPLY|ON)\s+({_TEMPORAL})",
    re.IGNORECASE,
)


def _clave(nombre: str) -> str:
    """#TempPre, [#TempPre] y #temppre son la misma tabla para SQL Server."""
    return nombre.strip("[]").lower()


def _creadas(limpio: str) -> Dict[str, str]:
    """{nombre en minúsculas: nombre como se escribió} de las temporales que se crean."""
    creadas: Dict[str, str] = {}
    for m in _CREA.finditer(limpio):
        nombre = m.group(1) or m.group(2)
        # «INSERT INTO #T SELECT …» con espacios variables: el INTO es del INSERT, no crea la tabla.
        if m.group(2) and re.search(r"\bINSERT\s*$", limpio[max(0, m.start() - 20):m.start()], re.IGNORECASE):
            continue
        creadas.setdefault(_clave(nombre), nombre.strip("[]"))
    return creadas


def creadas_en_el_encabezado(texto: str, limpio: str) -> Set[str]:
    """Temporales cuya creación (CREATE TABLE #X o SELECT … INTO #X) figura en los comentarios del encabezado."""
    return set(_creadas("\n".join(comentarios_del_encabezado(texto, limpio))))


def _usadas_sin_crear(limpio: str) -> Tuple[Dict[str, List[int]], Dict[str, str], Dict[str, str]]:
    """({temporal: posiciones de uso}, {temporal: nombre}, creadas) de las que se usan y no se crean en el código."""
    creadas = _creadas(limpio)
    usos: Dict[str, List[int]] = {}
    nombres: Dict[str, str] = {}
    for patron in (_USA, _INSERT_INTO):
        for m in patron.finditer(limpio):
            nombre = m.group(1).strip("[]")
            clave = _clave(nombre)
            if clave in creadas:
                continue
            usos.setdefault(clave, []).append(m.start(1))
            nombres.setdefault(clave, nombre)
    return usos, nombres, creadas


def _enumerar(nombres: List[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def temporales_externas(
    texto: str, limpio: str, linea_de: Callable[[int], int],
) -> Optional[Tuple[int, str, List[Dict], List[int]]]:
    """«Tabla temporal externa»: se usa, no se crea en el código y su creación está en el encabezado (13 nov.)."""
    usos, nombres, _ = _usadas_sin_crear(limpio)
    externas = creadas_en_el_encabezado(texto, limpio)
    orden = sorted((clave for clave in usos if clave in externas), key=lambda clave: min(usos[clave]))
    if not orden:
        return None
    tablas = [nombres[clave] for clave in orden]
    # Texto dictado por la usuaria (13 nov.); en plural con varias tablas.
    if len(tablas) == 1:
        mensaje = (f"Se identificó que la tabla temporal {tablas[0]} no se crea en este procedimiento. Según lo "
                   f"indicado en el encabezado, esta es creada por otro procedimiento que se ejecuta previamente. Se "
                   f"recomienda verificar que dicho procedimiento cree la tabla {tablas[0]} antes de ejecutar este "
                   f"procedimiento, para evitar errores al intentar utilizarla.")
    else:
        mensaje = (f"Se identificó que las tablas temporales {_enumerar(tablas)} no se crean en este procedimiento. "
                   f"Según lo indicado en el encabezado, estas son creadas por otro procedimiento que se ejecuta "
                   f"previamente. Se recomienda verificar que dicho procedimiento cree las tablas {_enumerar(tablas)} "
                   f"antes de ejecutar este procedimiento, para evitar errores al intentar utilizarlas.")
    grupos = [{"nombre": nombres[clave], "tipo": "Tabla",
               "lineas": sorted({linea_de(posicion) for posicion in usos[clave]})} for clave in orden]
    return min(usos[orden[0]]), mensaje, grupos, [n for grupo in grupos for n in grupo["lineas"]]


def _parecida(clave: str, creadas: Dict[str, str]) -> Optional[str]:
    """La temporal creada con un nombre muy parecido (#TempPre para #TempPre2), si la hay."""
    parecida = difflib.get_close_matches(clave, list(creadas), n=1, cutoff=0.75)
    return creadas[parecida[0]] if parecida else None


def _sin_crear_y_sin_documentar(limpio: str, texto: Optional[str]):
    usos, nombres, creadas = _usadas_sin_crear(limpio)
    if texto is not None:
        externas = creadas_en_el_encabezado(texto, limpio)
        usos = {clave: posiciones for clave, posiciones in usos.items() if clave not in externas}
    return usos, nombres, creadas


# Qué hace el procedimiento con la temporal, en el orden en que se dice («Se lee y se actualiza»).
_ACCIONES = ("se lee", "se inserta", "se actualiza", "se eliminan filas")


def _uso(limpio: str, posiciones: List[int]) -> str:
    """«Solo se lee», «Se lee y se actualiza»…: lo que el procedimiento hace con la temporal (opción C)."""
    from app.analizadores.temporal_sin_uso import _es_destino_de_alias

    hechas = set()
    for posicion in posiciones:
        antes = limpio[max(0, posicion - 40):posicion]
        nombre = re.match(_TEMPORAL, limpio[posicion:])
        fin = posicion + (len(nombre.group(0)) if nombre else 0)
        if re.search(r"\bINSERT\s+(?:INTO\s+)?$", antes, re.IGNORECASE):
            hechas.add("se inserta")
        elif re.search(r"\bUPDATE\s+$", antes, re.IGNORECASE) or re.search(r"\bMERGE(?:\s+INTO)?\s+$", antes, re.IGNORECASE):
            hechas.add("se actualiza")
        elif re.search(r"\b(?:DELETE(?:\s+FROM)?|TRUNCATE\s+TABLE)\s+$", antes, re.IGNORECASE):
            hechas.add("se eliminan filas")
        elif re.search(r"\bFROM\s+$", antes, re.IGNORECASE) and _es_destino_de_alias(limpio, posicion, fin):
            # «UPDATE A SET … FROM #T A» / «DELETE A FROM #T A»: la temporal es la que se modifica.
            delete = re.search(r"\bDELETE\s+\w+\s+FROM\s+$", limpio[max(0, posicion - 60):posicion], re.IGNORECASE)
            hechas.add("se eliminan filas" if delete else "se actualiza")
        else:
            hechas.add("se lee")
    orden = [accion for accion in _ACCIONES if accion in hechas]
    if orden == ["se lee"]:
        return "Solo se lee"
    texto = orden[0] if len(orden) == 1 else f"{', '.join(orden[:-1])} y {orden[-1]}"
    return texto[0].upper() + texto[1:]


# Texto de la usuaria (21 nov.): confirmar que la crea el que lo llama; 2 en el párrafo, 3 en viñetas, más en tabla.
_QUE_HACER_VALIDAR_UNA = (
    "Se recomienda confirmar que el procedimiento que lo llama la cree antes de ejecutarlo y documentarlo en el "
    "encabezado, ya que, si no existe, SQL Server detiene el procedimiento con el error «El nombre de objeto "
    "'{nombre}' no es válido»."
)
_QUE_HACER_VALIDAR_VARIAS = (
    "Se recomienda confirmar que el procedimiento que lo llama las cree antes de ejecutarlo y documentarlo en el "
    "encabezado, ya que, si no existen, SQL Server detiene el procedimiento con el error «El nombre de objeto no es "
    "válido»."
)


def temporales_por_validar(
    limpio: str, linea_de: Callable[[int], int], texto: Optional[str] = None,
) -> Optional[Tuple[int, str, List[Dict], List[int]]]:
    """«Validar tabla temporal sin crear» (medio): se usan, no se crean, no están en el encabezado y no se parecen a
    ninguna que sí se crea. Devuelve (posición, mensaje, grupos, líneas) o None."""
    usos, nombres, creadas = _sin_crear_y_sin_documentar(limpio, texto)
    orden = sorted((c for c in usos if not _parecida(c, creadas)), key=lambda clave: min(usos[clave]))
    if not orden:
        return None
    tablas = [nombres[clave] for clave in orden]
    if len(tablas) == 1:
        problema = f"Se identificó que la tabla temporal {tablas[0]} se utiliza, pero no se crea en este procedimiento."
        que_hacer = _QUE_HACER_VALIDAR_UNA.format(nombre=tablas[0])
    elif len(tablas) == 2:
        problema = (f"Se identificó que las tablas temporales {tablas[0]} y {tablas[1]} se utilizan, pero no se crean "
                    f"en este procedimiento.")
        que_hacer = _QUE_HACER_VALIDAR_VARIAS
    else:
        problema = (f"Se identificó que las siguientes tablas temporales se utilizan, pero no se crean en este "
                    f"procedimiento: {'; '.join(tablas)}.")
        que_hacer = _QUE_HACER_VALIDAR_VARIAS
    grupos = [{"nombre": nombres[clave], "tipo": "Tabla temporal",
               "lineas": sorted({linea_de(posicion) for posicion in usos[clave]})} for clave in orden]
    if len(tablas) > 3:
        # Más de 3: tabla «Tabla temporal | Uso en el procedimiento» (opción C de la usuaria).
        for grupo, clave in zip(grupos, orden):
            grupo.update({"tituloDetalle": "Uso en el procedimiento", "detalleEnTexto": True,
                          "columnas": _uso(limpio, usos[clave])})
    return min(usos[orden[0]]), f"{problema} {que_hacer}", grupos, [n for g in grupos for n in g["lineas"]]


def temporales_sin_crear(
    limpio: str, linea_de: Callable[[int], int], texto: Optional[str] = None,
) -> Optional[Tuple[int, str, List[Dict], List[int]]]:
    """Una sola observación con las temporales que se usan pero nunca se crean en el procedimiento.

    Devuelve (posición, mensaje, grupos, líneas) o None. «grupos» permite a «Ver en el código» recorrer tabla
    por tabla todas las líneas donde se usa. Con `texto` (el SQL original), las temporales documentadas en el
    encabezado no cuentan: son «Tabla temporal externa».
    """
    usos, nombres, creadas = _sin_crear_y_sin_documentar(limpio, texto)
    # Solo las que se parecen a una que sí se crea (posible error de escritura); las demás se validan aparte.
    usos = {clave: posiciones for clave, posiciones in usos.items() if _parecida(clave, creadas)}
    if not usos:
        return None
    orden = sorted(usos, key=lambda clave: min(usos[clave]))
    lineas = {clave: sorted({linea_de(posicion) for posicion in usos[clave]}) for clave in orden}

    if len(orden) == 1:
        clave = orden[0]
        nombre = nombres[clave]
        parecida = difflib.get_close_matches(clave, list(creadas), n=1, cutoff=0.75)
        ejemplo = f" (ej.: {creadas[parecida[0]]})" if parecida else ""
        mensaje = (
            f"Se identificó que la tabla temporal {nombre} se utiliza, pero no se crea "
            f"dentro del procedimiento. Crear la tabla temporal antes de usarla o corregir el nombre{ejemplo}, "
            f"salvo que la cree el procedimiento que lo llama, ya que, al ejecutarse, SQL Server detiene el "
            f"procedimiento con el error «El nombre de objeto '{nombre}' no es válido»."
        )
    else:
        # Sin las líneas en el texto: van arriba de la tarjeta y «Ver en el código» las recorre (usuaria, 21 nov.).
        detalle = "; ".join(nombres[clave] for clave in orden)
        mensaje = (
            f"Se identificaron {len(orden)} tablas temporales que se utilizan, pero no se crean dentro del "
            f"procedimiento: {detalle}. Crear cada tabla temporal antes de usarla o corregir su nombre, salvo que "
            f"la cree el procedimiento que lo llama, ya que, al ejecutarse, SQL Server detiene el procedimiento "
            f"con el error «El nombre de objeto no es válido»."
        )
    grupos = [{"nombre": nombres[clave], "tipo": "Tabla", "lineas": lineas[clave]} for clave in orden]
    return min(usos[orden[0]]), mensaje, grupos, [n for grupo in grupos for n in grupo["lineas"]]
