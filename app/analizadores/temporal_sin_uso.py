"""«Tabla temporal llena y sin uso» (compartido por Reportes y Negocio; pedido de la usuaria, 8 nov.).

Una temporal que el procedimiento crea y llena, pero que no se lee en ninguna parte: sus consultas se ejecutan y su
resultado se descarta. Es la pareja de «Tabla temporal usada sin crear» (temporales_sin_crear.py).

Cuenta como uso cualquier lectura: SELECT final, FROM/JOIN, subconsulta, EXISTS, IN (SELECT …), MERGE … USING, o como
origen de un INSERT/UPDATE hacia otra tabla. No cuenta: crearla, llenarla (INSERT, SELECT INTO), borrarle filas,
actualizarla, TRUNCATE, índices, ALTER ni DROP.

Para no marcar de más (usuaria: «solo la que no se usa»):
- Una temporal que solo sirve para llenar otra sí se usa (no se sigue la cadena).
- Si después de crearla hay un EXEC a otro procedimiento, ese procedimiento puede leerla: no se marca.
- Si aparece dentro de un texto (SQL dinámico), puede leerse ahí: no se marca.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple

_NOMBRE = r"#[A-Za-z_][\w$#]*"
_CREA = re.compile(rf"\bCREATE\s+TABLE\s+({_NOMBRE})", re.IGNORECASE)
_SELECT_INTO = re.compile(rf"\bINTO\s+({_NOMBRE})", re.IGNORECASE)
# EXEC a otro procedimiento (no sp_executesql con texto, que es SQL dinámico y se revisa aparte).
_EXEC_PROCEDIMIENTO = re.compile(r"\bEXEC(?:UTE)?\s+(?!sp_executesql\b)(?:@\w+\s*=\s*)?[\[\]\w.]+", re.IGNORECASE)

# Lo que va justo antes del nombre cuando no es una lectura (la temporal es el destino o se administra).
_ANTES_NO_LECTURA = re.compile(
    r"(?:\bCREATE\s+TABLE|\bINSERT(?:\s+INTO)?|\bINTO|\bDELETE(?:\s+FROM)?|\bUPDATE|\bTRUNCATE\s+TABLE"
    r"|\bALTER\s+TABLE|\bINDEX\s+[\[\]\w]+\s+ON)\s*$",
    re.IGNORECASE,
)
# DROP TABLE [IF EXISTS] #A, #B, … (la lista puede ser larga: se toma completa).
_DROP = re.compile(rf"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?{_NOMBRE}(?:\s*,\s*{_NOMBRE})*", re.IGNORECASE)
# UPDATE A SET … FROM #T A / DELETE A FROM #T A: #T es el destino del alias A.
_UPDATE_DELETE_ALIAS = re.compile(r"\b(?:UPDATE|DELETE)\s+([A-Za-z_]\w*)\s+(?:SET|FROM)\b", re.IGNORECASE)
_FIN_DE_SENTENCIA = re.compile(r"\b(?:INSERT|CREATE|DROP|TRUNCATE|UPDATE|DELETE|MERGE)\b|;", re.IGNORECASE)

QUE_HACER_TEMPORAL_SIN_USO = (
    "Se recomienda retirar la tabla temporal y las consultas que la llenan, ya que consumen tiempo de "
    "procesamiento y recursos sin aportar al resultado del procedimiento."
)


def _textos(texto: str) -> List[str]:
    """El contenido de cada texto entre comillas ('…'), sin confundir comillas de comentarios."""
    resultado, i, n = [], 0, len(texto)
    while i < n:
        if texto.startswith("--", i):
            fin = texto.find("\n", i)
            i = n if fin < 0 else fin
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = n if fin < 0 else fin + 2
        elif texto[i] == "'":
            j = i + 1
            while j < n:
                if texto[j] == "'":
                    if texto.startswith("''", j):
                        j += 2
                        continue
                    break
                j += 1
            resultado.append(texto[i + 1:j])
            i = j + 1
        else:
            i += 1
    return resultado


def _es_destino_de_alias(limpio: str, posicion: int, fin: int) -> bool:
    """¿#T está en «UPDATE A SET … FROM #T A» o «DELETE A FROM #T A» como la tabla del alias A?"""
    alias = re.match(r"\s+(?:AS\s+)?([A-Za-z_]\w*)", limpio[fin:], re.IGNORECASE)
    if not alias:
        return False
    for sentencia in reversed(list(_UPDATE_DELETE_ALIAS.finditer(limpio, 0, posicion))):
        # La sentencia UPDATE/DELETE debe seguir abierta: sin otra sentencia entre ella y #T.
        if _FIN_DE_SENTENCIA.search(limpio, sentencia.end(), posicion):
            return False
        return sentencia.group(1).lower() == alias.group(1).lower()
    return False


def temporales_sin_uso(texto: str, limpio: str) -> List[Tuple[str, int]]:
    """[(#tabla, posición de su creación)] de las temporales que se crean y se llenan, pero no se leen.

    `limpio` es el texto sin comentarios y con los textos vacíos (mismas posiciones).
    """
    creadas: Dict[str, Tuple[str, int]] = {}
    for patron in (_CREA, _SELECT_INTO):
        for match in patron.finditer(limpio):
            clave = match.group(1).lower()
            if clave not in creadas or match.start(1) < creadas[clave][1]:
                creadas[clave] = (match.group(1), match.start(1))
    drops = [(m.start(), m.end()) for m in _DROP.finditer(limpio)]
    resultado = []
    for clave, (nombre, creada_en) in creadas.items():
        llenada = leida = False
        for uso in re.finditer(rf"(?<![\w$#@]){re.escape(nombre)}(?![\w$#])", limpio, re.IGNORECASE):
            if any(inicio <= uso.start() < fin for inicio, fin in drops):
                continue  # DROP TABLE: no es una lectura
            antes = limpio[max(0, uso.start() - 300):uso.start()]
            destino = _ANTES_NO_LECTURA.search(antes)
            if destino:
                if re.search(r"\b(?:INSERT|INTO)\b", destino.group(0), re.IGNORECASE):
                    llenada = True
                continue
            if _es_destino_de_alias(limpio, uso.start(), uso.end()):
                continue
            leida = True
            break
        if leida or not llenada:
            continue
        # Un procedimiento llamado después, o SQL dinámico, pueden leerla.
        if _EXEC_PROCEDIMIENTO.search(limpio, creada_en):
            continue
        if any(re.search(rf"(?<![\w$#@]){re.escape(nombre)}(?![\w$#])", cadena, re.IGNORECASE)
               for cadena in _textos(texto)):
            continue
        resultado.append((nombre, creada_en))
    return sorted(resultado, key=lambda caso: caso[1])


def temporal_sin_uso_agrupado(
    texto: str, limpio: str, linea_de: Callable[[int], int],
) -> Optional[Tuple[int, str, List[int]]]:
    """Una sola observación con todas: (posición, mensaje, líneas) o None. Texto de la usuaria (8 nov.)."""
    casos = temporales_sin_uso(texto, limpio)
    if not casos:
        return None
    if len(casos) == 1:
        problema = (f"Se identificó que la tabla temporal {casos[0][0]} se crea y se llena, pero no se utiliza en "
                    f"ninguna consulta posterior.")
    else:
        problema = (f"Se identificaron las siguientes tablas temporales que se llenan, pero no se utilizan en ninguna "
                    f"consulta posterior: {'; '.join(nombre for nombre, _ in casos)}.")
    return casos[0][1], f"{problema} {QUE_HACER_TEMPORAL_SIN_USO}", [linea_de(posicion) for _, posicion in casos]
