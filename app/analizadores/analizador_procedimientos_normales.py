# -*- coding: utf-8 -*-
"""Reglas para procedimientos almacenados normales, fuera de reportes."""

import re
from typing import Dict, List, Set, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_procedimientos_normales import REGLAS_PROCEDIMIENTOS_NORMALES
from app.analizadores.analizador_tablas import _PASCAL_CASE, _a_pascal_case, _siglas_del_nombre, _texto_siglas


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_HINTS_PROHIBIDOS = (
    r"FORCESEEK|FORCESCAN|RECOMPILE|NOEXPAND|"
    r"LOOP\s+JOIN|HASH\s+JOIN|MERGE\s+JOIN|OPTIMIZE\s+FOR|MAXDOP\s*\(|FAST\s+\d+|"
    r"OPTION\s*\([^)]*\)"
)
# Hints de bloqueo: fuerzan al motor a bloquear de una forma determinada.
# Cada uno con lo que hace, para explicarlo en el mensaje.
_HINTS_BLOQUEO = {
    "UPDLOCK": "bloquea las filas leídas como si se fueran a actualizar y las mantiene bloqueadas hasta que "
               "termina la transacción",
    "HOLDLOCK": "mantiene bloqueadas las filas leídas hasta que termina la transacción, como el aislamiento "
                "SERIALIZABLE",
    "SERIALIZABLE": "mantiene bloqueadas las filas leídas hasta que termina la transacción",
    "REPEATABLEREAD": "mantiene bloqueadas las filas leídas hasta que termina la transacción",
    "XLOCK": "toma un bloqueo exclusivo sobre las filas leídas",
    "TABLOCKX": "toma un bloqueo exclusivo sobre toda la tabla",
    "TABLOCK": "bloquea toda la tabla en lugar de solo las filas usadas",
    "PAGLOCK": "obliga al motor a bloquear páginas completas",
    "ROWLOCK": "obliga al motor a bloquear fila por fila",
    "READPAST": "salta las filas que otro proceso tiene bloqueadas",
}
# Palabras que pueden ir antes de un hint de bloqueo dentro del mismo paréntesis.
_HINTS_DE_TABLA = set(_HINTS_BLOQUEO) | {
    "NOLOCK", "READUNCOMMITTED", "READCOMMITTED", "FORCESEEK", "FORCESCAN", "NOEXPAND", "NOWAIT",
}
_PALABRAS_SQL_COMENTADAS = r"SELECT|INSERT|UPDATE|DELETE|MERGE|EXEC(?:UTE)?|DECLARE|CREATE|ALTER|DROP|WHILE|GOTO"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_CATALOGO_SISTEMA = r"\bsys\s*\.\s*[A-Za-z_][\w$]*"
_SQL_DINAMICO = r"\b(?:sp_executesql\b|EXEC(?:UTE)?\s*(?:\(\s*)?(?:N?['\"]|@))"


def _linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    """Hallazgo con la severidad definida en el catálogo de procedimientos."""
    return Hallazgo(
        linea=_linea(texto, posicion),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_PROCEDIMIENTOS_NORMALES[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


# Un texto es SQL dinámico si se asigna a una variable, se concatena o se pasa
# a EXEC / sp_executesql, y además contiene una consulta: ese sí se revisa.
_ANTES_DE_SQL_DINAMICO = re.compile(r"(?:=|\+|\bEXEC(?:UTE)?\s*\(?|\bsp_executesql)\s*N?$", re.IGNORECASE)
_CONTENIDO_SQL = re.compile(r"\b(?:SELECT|FROM|JOIN|INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)


def _quitar_comentarios(texto: str) -> str:
    """
    Reemplaza por espacios los comentarios y el contenido de los textos ('...'),
    conservando las comillas, los saltos de línea y las posiciones. Así un
    mensaje como 'SELECT * FROM sys.objects' no se revisa como código. El SQL
    dinámico (N'SELECT ...' asignado o ejecutado) sí se conserva: es código.
    Se recorre una sola vez para que un '--' dentro de un texto no se tome
    como comentario. (El código comentado se revisa aparte, sobre el original.)
    """
    salida = list(texto)
    i, n = 0, len(texto)
    while i < n:
        if texto.startswith("--", i):
            fin = texto.find("\n", i)
            fin = n if fin < 0 else fin
            salida[i:fin] = " " * (fin - i)
            i = fin
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            fin = n if fin < 0 else fin + 2
            salida[i:fin] = [c if c == "\n" else " " for c in texto[i:fin]]
            i = fin
        elif texto[i] == "'":
            j = i + 1
            while j < n:
                if texto[j] == "'":
                    if texto.startswith("''", j):
                        j += 2
                        continue
                    break
                j += 1
            contenido = texto[i + 1:j]
            es_sql = (_ANTES_DE_SQL_DINAMICO.search(texto[max(0, i - 40):i])
                      and _CONTENIDO_SQL.search(contenido))
            if not es_sql:
                salida[i + 1:j] = [c if c == "\n" else " " for c in contenido]
            i = j + 1
        else:
            i += 1
    return "".join(salida)


def _quitar_solo_comentarios(texto: str) -> str:
    """Quita los comentarios pero conserva el contenido de los textos."""
    texto = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", lambda m: " " * len(m.group(0)), texto)


def _es_temporal(nombre: str) -> bool:
    """Tabla temporal (#T) o variable de tabla (@T)."""
    return nombre.strip("[]").startswith(("#", "@"))


_REFERENCIA = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"


def _limpiar_nombre(nombre: str) -> str:
    return re.sub(r"\s*\.\s*", ".", nombre.strip())


def _tabla_del_from(limpio: str, posicion: int) -> str:
    """Primera tabla del FROM de la sentencia que empieza en `posicion`."""
    fin = limpio.find(";", posicion)
    tramo = limpio[posicion:fin if fin >= 0 else len(limpio)]
    # Admite Base..Tabla (esquema omitido) para nombrar la tabla completa.
    encontrado = re.search(
        rf"\bFROM\s+({_IDENTIFICADOR}(?:\s*\.(?:\s*\.)?\s*{_IDENTIFICADOR}){{0,2}})", tramo, re.IGNORECASE,
    )
    return _limpiar_nombre(encontrado.group(1)) if encontrado else ""


def _nombre_declarado_antes(limpio: str, posicion: int) -> str:
    """Variable o columna declarada justo antes de un tipo (ej.: @doc VARBINARY)."""
    encontrado = re.search(r"(@?[A-Za-z_]\w*)\s+$", limpio[:posicion])
    if encontrado and encontrado.group(1).upper() not in {"AS", "CAST", "CONVERT", "DECLARE", "TABLE"}:
        return encontrado.group(1)
    return ""


def _validar_control_flujo(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bWHILE\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "WHILE_PROHIBIDO",
            "Se identificó el uso de un bucle WHILE en el procedimiento. Se recomienda evaluar otras alternativas "
            "que permitan procesar los registros en conjunto y evitar el uso de WHILE, ya que puede generar "
            "bucles infinitos y afectar el rendimiento del procedimiento.",
        ))
    for match in re.finditer(r"\bGOTO\b\s*(\w*)", limpio, re.IGNORECASE):
        etiqueta = f" hacia la etiqueta {match.group(1)}" if match.group(1) else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "GOTO_PROHIBIDO",
            f"Se identificó una instrucción GOTO{etiqueta}. Se recomienda validar si su uso está "
            f"justificado y, de ser posible, reemplazarla por IF/ELSE o por un bloque TRY/CATCH, ya que "
            f"GOTO salta a otra parte del código y hace difícil seguir su lógica.",
        ))
    for match in re.finditer(rf"\bMERGE\b(?:\s+(?:TOP\s*\([^)]*\)\s*)?(?:INTO\s+)?({_REFERENCIA}))?", limpio, re.IGNORECASE):
        tabla = f" sobre la tabla {_limpiar_nombre(match.group(1))}" if match.group(1) else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "MERGE_PROHIBIDO",
            f"Se detectó una sentencia MERGE{tabla}. Se recomienda validar si su uso está justificado y, "
            f"de ser posible, reemplazarla por sentencias INSERT, UPDATE y DELETE separadas, ya que MERGE "
            f"tiene errores conocidos en SQL Server y dificulta controlar cada operación.",
        ))
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    return [
        _hallazgo(
            texto,
            match.start(),
            "HINT_PLAN_PROHIBIDO",
            f"Se verificó el uso de '{match.group(0)}', que le indica al motor de base de datos cómo "
            f"ejecutar la consulta. Retirarlo, ya que no está permitido forzar al motor y es el "
            f"optimizador quien decide el mejor plan de ejecución.",
        )
        for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE)
    ]


def _validar_indice_forzado(texto: str, limpio: str) -> List[Hallazgo]:
    """WITH (INDEX(IX_...)) o WITH (INDEX = IX_...): obliga al motor a usar un índice."""
    hallazgos = []
    referencia = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"
    for match in re.finditer(r"\bINDEX\s*(?:\(\s*([^)]*?)\s*\)|=\s*(\[[^\]]+\]|\w+))", limpio, re.IGNORECASE):
        # Solo como hint de tabla: dentro del WITH (...) que sigue a la tabla.
        abre = limpio.rfind("(", 0, match.start())
        previo = limpio[max(0, abre - 40):abre] if abre >= 0 else ""
        if not re.search(r"\bWITH\s*$", previo, re.IGNORECASE):
            continue
        indice = (match.group(1) or match.group(2) or "").strip()
        antes = re.sub(r"\s*WITH\s*$", "", limpio[max(0, abre - 300):abre], flags=re.IGNORECASE)
        tabla = re.search(
            rf"\b(?:FROM|JOIN)\s+({referencia})(?:\s+(?:AS\s+)?[A-Za-z_][\w$#]*)?\s*$", antes, re.IGNORECASE,
        )
        en_tabla = f" en la tabla {_limpiar_nombre(tabla.group(1))}" if tabla else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "HINT_PLAN_PROHIBIDO",
            f"Se identificó que se obliga al motor a usar el índice {indice}{en_tabla} (WITH (INDEX)). Se "
            f"recomienda retirarlo, ya que es el optimizador quien decide qué índice usar según los datos, y "
            f"si el índice cambia o se elimina, el procedimiento dejará de funcionar.",
        ))
    return hallazgos


def _validar_hints_bloqueo(texto: str, limpio: str) -> List[Hallazgo]:
    """UPDLOCK, HOLDLOCK, TABLOCK...: fuerzan al motor a bloquear; no se permiten."""
    hallazgos = []
    for match in re.finditer(r"\b(" + "|".join(_HINTS_BLOQUEO) + r")\b", limpio, re.IGNORECASE):
        # Solo dentro del paréntesis de hints de una tabla: WITH (UPDLOCK, HOLDLOCK) o (UPDLOCK).
        abre = limpio.rfind("(", 0, match.start())
        previo = limpio[abre + 1:match.start()] if abre >= 0 else None
        if previo is None or not re.fullmatch(r"[\sA-Za-z,]*", previo):
            continue
        if any(palabra.upper() not in _HINTS_DE_TABLA for palabra in re.findall(r"[A-Za-z]+", previo)):
            continue
        hint = match.group(1).upper()
        hallazgos.append(_hallazgo(
            texto, match.start(1), "HINT_BLOQUEO_PROHIBIDO",
            f"Se detectó el uso de '{hint}', que {_HINTS_BLOQUEO[hint]}. Se recomienda retirarlo y dejar que "
            f"el motor gestione los bloqueos, ya que forzarlo no está permitido por las buenas prácticas y "
            f"detiene a los demás procesos que usan la tabla.",
        ))
    return hallazgos


# Palabras que pueden seguir al nombre de una tabla y que no son un alias.
_NO_ALIAS = (
    "WITH|ON|WHERE|INNER|LEFT|RIGHT|FULL|CROSS|OUTER|JOIN|GROUP|ORDER|UNION|EXCEPT|"
    "INTERSECT|HAVING|OPTION|SET|FOR|INTO|PIVOT|UNPIVOT|APPLY|AND|OR|WHEN|THEN|ELSE|END"
)


def _tiene_nolock_despues(texto: str, posicion: int) -> bool:
    """WITH(NOLOCK) justo después de la tabla o de su alias (no más adelante en el código)."""
    return bool(re.match(
        rf"(?:\s+(?:AS\s+)?(?!(?:{_NO_ALIAS})\b)[A-Za-z_@#][\w$#]*)?\s*(?:WITH\s*)?\(\s*NOLOCK\b",
        texto[posicion:], re.IGNORECASE,
    ))


# Palabras del nombre que indican una tabla de movimientos (pesada) o de constantes.
_PALABRAS_MOVIMIENTOS = {"mov", "movs", "movimiento", "movimientos"}
_PALABRAS_CONSTANTES = {"constante", "constantes"}


def _palabras_del_nombre(nombre: str) -> List[str]:
    """Palabras de un nombre de tabla: separa por _ y por mayúsculas (CuentaMov → cuenta, mov)."""
    tabla = nombre.split(".")[-1].strip("[]")
    return [p.lower() for parte in tabla.split("_") for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", parte)]


def _validar_nolock_tablas_pesadas(texto: str, limpio: str) -> List[Hallazgo]:
    """
    En los procedimientos de negocio el WITH(NOLOCK) es opcional, salvo al leer
    tablas de movimientos (pesadas) o de constantes: ahí se recomienda.
    No aplica a la tabla que se modifica en un UPDATE o DELETE.
    """
    hallazgos = []
    referencia = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"
    for match in re.finditer(rf"\b(FROM|JOIN)\s+({referencia})", limpio, re.IGNORECASE):
        if re.match(r"\s*\(", limpio[match.end():]):  # función de tabla, no una tabla
            continue
        tabla = _limpiar_nombre(match.group(2))
        if _es_temporal(tabla) or _tiene_nolock_despues(limpio, match.end()):
            continue
        palabras = set(_palabras_del_nombre(tabla))
        if palabras & _PALABRAS_MOVIMIENTOS:
            tipo = "de movimientos"
            porque = "de gran volumen"
        elif palabras & _PALABRAS_CONSTANTES:
            tipo = "de constantes"
            porque = "de uso frecuente"
        else:
            continue
        # La tabla que se modifica (UPDATE/DELETE ... FROM) no lleva NOLOCK.
        sentencia = _sentencia_de(limpio, match.start())
        objetivo = re.search(rf"\b(?:UPDATE|DELETE(?:\s+FROM)?)\s+({referencia})", sentencia, re.IGNORECASE)
        if objetivo:
            alias = re.match(rf"\s+(?:AS\s+)?([A-Za-z_][\w$#]*)", limpio[match.end():])
            nombre_objetivo = _limpiar_nombre(objetivo.group(1)).lower()
            if nombre_objetivo in {tabla.lower(), (alias.group(1).lower() if alias else "")}:
                continue
        hallazgos.append(_hallazgo(
            texto, match.start(2), "TABLA_PESADA_SIN_NOLOCK",
            f"Se identificó que la tabla {tipo} ({tabla}), {porque}, se consulta sin WITH(NOLOCK). Se recomienda "
            f"evaluar agregar WITH(NOLOCK) en estas tablas, ya que puede ayudar a agilizar la consulta "
            f"(ej.: {tabla} WITH(NOLOCK)).",
        ))
    return hallazgos


def _validar_update_from_nolock(texto: str, limpio: str) -> List[Hallazgo]:
    """En un UPDATE, la tabla física que se actualiza no debe llevar WITH(NOLOCK).

    La tabla actualizada es la que va después de UPDATE: su nombre, o el alias
    que se resuelve en el FROM/JOIN. Las demás tablas del JOIN pueden usarlo.
    """
    hallazgos = []
    referencia = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"
    for update in re.finditer(rf"\bUPDATE\s+(?:TOP\s*\([^)]*\)\s*)?({referencia})", limpio, re.IGNORECASE):
        objetivo = _limpiar_nombre(update.group(1))
        # La sentencia termina en ";" o donde empieza la siguiente (el SET es parte del UPDATE).
        fin = len(limpio)
        for siguiente in _INICIO_SENTENCIA.finditer(limpio, update.end()):
            if not re.match(r"\s*SET\b", limpio[siguiente.start():], re.IGNORECASE):
                fin = siguiente.start()
                break
        sentencia = limpio[update.start():fin]

        tabla, posicion_hint = None, None
        if _tiene_nolock_despues(limpio, update.end()):  # UPDATE dbo.T WITH(NOLOCK) SET ...
            tabla, posicion_hint = objetivo, update.start(1)
        else:
            # UPDATE alias ... FROM dbo.T alias WITH(NOLOCK)  |  UPDATE dbo.T ... FROM dbo.T WITH(NOLOCK)
            for origen in re.finditer(rf"\b(?:FROM|JOIN)\s+({referencia})", sentencia, re.IGNORECASE):
                nombre = _limpiar_nombre(origen.group(1))
                alias = re.match(rf"\s+(?:AS\s+)?(?!(?:{_NO_ALIAS})\b)([A-Za-z_][\w$#]*)", sentencia[origen.end():], re.IGNORECASE)
                es_objetivo = nombre.lower() == objetivo.lower() or (
                    alias is not None and alias.group(1).lower() == objetivo.lower())
                if es_objetivo and _tiene_nolock_despues(limpio, update.start() + origen.end()):
                    tabla, posicion_hint = nombre, update.start() + origen.start(1)
                    break
        if tabla and not _es_temporal(tabla):
            hallazgos.append(_hallazgo(
                texto, posicion_hint, "NOLOCK_EN_TABLA_FISICA",
                f"Se identificó el uso de WITH (NOLOCK) en la tabla {tabla}, sobre la cual se realiza una "
                f"actualización. Se recomienda retirar WITH (NOLOCK), ya que SQL Server ignora esta instrucción en "
                f"la tabla que se actualiza y su uso no es una buena práctica.",
            ))
    return hallazgos


def _validar_temporales(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        rf"\b(FROM|JOIN)\s+({_IDENTIFICADOR})(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}",
        re.IGNORECASE,
    )
    for match in patron.finditer(limpio):
        nombre = match.group(2)
        if _es_temporal(nombre) and _tiene_nolock_despues(limpio, match.end()):
            tipo_temporal = "la variable de tabla" if nombre.startswith("@") else "la tabla temporal"
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "NOLOCK_EN_TABLA_TEMPORAL",
                f"Se identificó el uso de WITH (NOLOCK) en {tipo_temporal} {nombre}. Se recomienda retirar "
                f"WITH (NOLOCK), ya que las tablas temporales son de uso exclusivo de la sesión que las crea, por "
                f"lo que no requieren esta instrucción para evitar bloqueos entre sesiones.",
            ))
    return hallazgos


def _validar_order_by_numerico(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bORDER\s+BY\s+(\d+(?:\s*,\s*\d+)*)", limpio, re.IGNORECASE):
        posiciones = ", ".join(re.findall(r"\d+", match.group(1)))
        hallazgos.append(_hallazgo(
            texto, match.start(), "ORDER_BY_NUMERICO_PROHIBIDO",
            f"Se encontró un ORDER BY por posición de columna (ORDER BY {posiciones}). Escribir "
            f"el nombre de la columna, ya que si cambia el SELECT el orden cambiaría sin notarlo "
            f"(ej.: ORDER BY cNombre).",
        ))
    return hallazgos


def _validar_cast_en_join(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        rf"\bJOIN\s+({_REFERENCIA}).*?\bON\b(?:(?!\bJOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|;).)*?\b(CAST|CONVERT)\s*\(",
        re.IGNORECASE | re.DOTALL,
    )
    for match in patron.finditer(limpio):
        tabla = _limpiar_nombre(match.group(1))
        hallazgos.append(_hallazgo(
            texto, match.start(2), "CAST_EN_JOIN_PROHIBIDO",
            f"Se identificó un {match.group(2).upper()} en la condición del JOIN con la tabla {tabla}. Se "
            f"recomienda convertir el dato antes del JOIN (en una tabla temporal o variable) o unir columnas del "
            f"mismo tipo, ya que la conversión en la condición impide usar los índices y vuelve lenta la consulta.",
        ))
    return hallazgos


# Cláusulas que indican en qué parte de la sentencia está un COLLATE.
_CLAUSULAS_COLLATE = re.compile(
    r"\b(WHERE|ON|HAVING|SELECT|FROM|JOIN|GROUP|ORDER|SET|VALUES|TABLE|DECLARE|RETURNS)\b",
    re.IGNORECASE,
)


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    # Cada SELECT seguido de INTO sin pasar por otra sentencia ni por su FROM: así se
    # detecta también justo después de BEGIN o de una sentencia sin ";".
    for match in re.finditer(
        r"(?is)\b(SELECT)\b(?:(?!\b(?:SELECT|INSERT|MERGE|OUTPUT|FROM|UPDATE|DELETE|GO)\b|;).)*?"
        r"\bINTO\b\s*([#@]?[\w\[\].]*)",
        limpio,
    ):
        destino = match.group(2).strip()
        tabla = f"la tabla {destino}" if destino else "una tabla temporal"
        hallazgos.append(_hallazgo(
            texto, match.start(1), "SELECT_INTO_PROHIBIDO",
            f"Se identificó que {tabla} se crea con SELECT INTO. Se recomienda crear primero la tabla con "
            f"CREATE TABLE, indicando sus tipos y COLLATE, y luego llenarla con INSERT INTO seguido del SELECT, "
            f"ya que así se controlan sus tipos de datos.",
        ))
    # SELECT *, SELECT DISTINCT * y SELECT TOP 10 / TOP (10) [PERCENT] [WITH TIES] *.
    patron_estrella = (
        r"\bSELECT\s+(?:ALL\s+|DISTINCT\s+)?"
        r"(?:TOP\s*(?:\(\s*[\w@]+\s*\)|\d+)\s*(?:PERCENT\s+)?(?:WITH\s+TIES\s+)?)?\*"
    )
    for match in re.finditer(patron_estrella, limpio, re.IGNORECASE):
        tabla = _tabla_del_from(limpio, match.start())
        sobre = f" sobre la tabla {tabla}" if tabla else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "SELECT_ESTRELLA_PROHIBIDO",
            f"Se identificó un SELECT *{sobre}, que trae todas sus columnas. Se recomienda escribir solo las "
            f"columnas necesarias, ya que traer columnas de más consume memoria y vuelve más lento el "
            f"procedimiento (ej.: SELECT cNombre, dFecha).",
        ))
    # SELECT c.*: todas las columnas de la tabla del alias c.
    for match in re.finditer(r"(?<![\w.@#])([A-Za-z_]\w*)\s*\.\s*\*(?=\s*(?:,|\bFROM\b))", limpio, re.IGNORECASE):
        alias = match.group(1)
        sentencia = _sentencia_de(limpio, match.start())
        origen = re.search(
            rf"\b(?:FROM|JOIN)\s+({_IDENTIFICADOR}(?:\s*\.(?:\s*\.)?\s*{_IDENTIFICADOR}){{0,2}})\s+(?:AS\s+)?{re.escape(alias)}\b",
            sentencia, re.IGNORECASE,
        )
        tabla = _limpiar_nombre(origen.group(1)) if origen else alias
        hallazgos.append(_hallazgo(
            texto, match.start(), "SELECT_ESTRELLA_PROHIBIDO",
            f"Se identificó un SELECT {alias}.* sobre la tabla {tabla}, que trae todas sus columnas. Se recomienda "
            f"escribir solo las columnas necesarias, ya que traer columnas de más consume memoria y vuelve más "
            f"lento el procedimiento (ej.: SELECT {alias}.cNombre, {alias}.dFecha).",
        ))
    for match in re.finditer(r"([\w.\[\]@#]+)\s+COLLATE\s+\w+", limpio, re.IGNORECASE):
        # La cláusula que manda es la más cercana al COLLATE (puede haber un ON antes del WHERE).
        previo = limpio[:match.start()]
        clausulas = _CLAUSULAS_COLLATE.findall(previo[previo.rfind(";") + 1:])
        ultima = clausulas[-1].upper() if clausulas else ""
        if ultima not in {"WHERE", "ON", "HAVING"}:
            continue
        clausula = "del JOIN" if ultima == "ON" else f"del {ultima}"
        hallazgos.append(_hallazgo(
            texto, match.start(1), "COLLATE_EN_PREDICADO",
            f"Se detectó un COLLATE sobre {match.group(1)} en la condición {clausula}. Definir "
            f"el COLLATE al crear la tabla temporal y no en la condición, ya que en el WHERE o en el JOIN impide "
            f"usar los índices y vuelve lenta la consulta.",
        ))
    for match in re.finditer(r"\bSTUFF\s*\([\s\S]*?\bFOR\s+XML\s+PATH\b", limpio, re.IGNORECASE):
        tabla = _tabla_del_from(limpio, match.start())
        sobre = f" sobre la tabla {tabla}" if tabla else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "STUFF_FOR_XML_PATH_PROHIBIDO",
            f"Se identificó una concatenación con STUFF y FOR XML PATH{sobre}. Emplear STRING_AGG, "
            f"ya que es la función nativa para concatenar valores y es más simple y rápida "
            f"(ej.: STRING_AGG(cNombre, ',')).",
        ))
    for match in re.finditer(r"\b(?:dbo\.)?FN_SPLIT\s*\(\s*([^,)]*)", limpio, re.IGNORECASE):
        dato = match.group(1).strip()
        sobre = f" para dividir {dato}" if dato.startswith("@") else " para dividir textos"
        hallazgos.append(_hallazgo(
            texto, match.start(), "FN_SPLIT_PROHIBIDO",
            f"Se verificó el uso de la función dbo.FN_SPLIT{sobre}. Se recomienda usar STRING_SPLIT, ya que es la "
            f"función nativa de SQL Server y mejora el rendimiento (ej.: SELECT value FROM "
            f"STRING_SPLIT(@cLista, ',')).",
        ))
    for match in re.finditer(r"\b(LTRIM\s*\(\s*RTRIM|RTRIM\s*\(\s*LTRIM)\s*\(\s*([^()]*?)\s*\)\s*\)", limpio, re.IGNORECASE):
        dato = match.group(2) or "cNombre"
        hallazgos.append(_hallazgo(
            texto, match.start(), "LTRIM_RTRIM_PROHIBIDO",
            f"Se identificó la combinación de LTRIM y RTRIM sobre {dato} para quitar espacios. Se recomienda "
            f"usar TRIM, ya que hace lo mismo en una sola función y le da más legibilidad al código "
            f"(ej.: TRIM({dato})).",
        ))
    return hallazgos


def _contenido_entre_parentesis(texto: str, apertura: int) -> str:
    """Texto dentro del paréntesis que abre en `apertura`, respetando anidados y cadenas ('(')."""
    profundidad, en_cadena = 0, False
    for indice in range(apertura, len(texto)):
        caracter = texto[indice]
        if caracter == "'":
            en_cadena = not en_cadena
        elif en_cadena:
            continue
        elif caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
            if profundidad == 0:
                return texto[apertura + 1:indice]
    return texto[apertura + 1:]


def _separar_por_comas(contenido: str) -> List[tuple]:
    """Partes separadas por comas de primer nivel (fuera de paréntesis y cadenas), con su posición."""
    partes, inicio, profundidad, en_cadena = [], 0, 0, False
    for indice, caracter in enumerate(contenido):
        if caracter == "'":
            en_cadena = not en_cadena
        elif en_cadena:
            continue
        elif caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        elif caracter == "," and profundidad == 0:
            partes.append((contenido[inicio:indice], inicio))
            inicio = indice + 1
    partes.append((contenido[inicio:], inicio))
    return partes


def _validar_tipos_entre_temporales(texto: str, limpio: str) -> List[Hallazgo]:
    """
    Una misma columna declarada en varias tablas temporales (#T) o variables de
    tabla (@T) debe tener el mismo tipo y longitud: si una es VARCHAR(40) y la
    otra VARCHAR(30), al pasar los datos de una a otra se truncan o falla.
    """
    hallazgos = []
    primeras: Dict[str, Tuple[str, str, int]] = {}
    patron = re.compile(
        r"\b(?:CREATE\s+TABLE\s+(#[A-Za-z_]\w*)|DECLARE\s+(@[A-Za-z_]\w*)\s+(?:AS\s+)?TABLE)\s*\(",
        re.IGNORECASE,
    )
    for match in patron.finditer(limpio):
        tabla = match.group(1) or match.group(2)
        apertura = match.end() - 1
        contenido = _contenido_entre_parentesis(limpio, apertura)
        for definicion, desplazamiento in _separar_por_comas(contenido):
            columna = re.match(
                rf"\s*({_IDENTIFICADOR})\s+([A-Za-z]+\s*(?:\(\s*(?:MAX|\d+)\s*(?:,\s*\d+\s*)?\))?)",
                definicion, re.IGNORECASE,
            )
            if not columna or columna.group(1).upper() in {"CONSTRAINT", "PRIMARY", "UNIQUE", "INDEX", "CHECK", "FOREIGN"}:
                continue
            nombre = columna.group(1).strip("[]")
            tipo = re.sub(r"\s+", "", columna.group(2)).upper()
            posicion = apertura + 1 + desplazamiento + columna.start(1)
            anterior = primeras.get(nombre.lower())
            if anterior is None:
                primeras[nombre.lower()] = (tabla, tipo, posicion)
                continue
            tabla_anterior, tipo_anterior, posicion_anterior = anterior
            if tipo != tipo_anterior and tabla.lower() != tabla_anterior.lower():
                hallazgos.append(_hallazgo(
                    texto, posicion, "TIPO_DISTINTO_ENTRE_TEMPORALES",
                    f"La columna {nombre} es {tipo} en {tabla}, pero {tipo_anterior} en "
                    f"{tabla_anterior} (línea {_linea(texto, posicion_anterior)}). Usar el mismo tipo "
                    f"y longitud en ambas, ya que al pasar los datos de una tabla a otra se pueden truncar o "
                    f"generar un error.",
                ))
    return hallazgos


_COLLATE_EMPRESA = "SQL_Latin1_General_CP1_CI_AS"


def _validar_collate_usado(texto: str, limpio: str) -> List[Hallazgo]:
    """
    El COLLATE de la empresa es SQL_Latin1_General_CP1_CI_AS. DATABASE_DEFAULT
    depende de cada base (alto); otro COLLATE, como Modern_Spanish, se pide validar (medio).
    """
    hallazgos = []
    for match in re.finditer(r"\bCOLLATE\s+([A-Za-z_]\w*)", limpio, re.IGNORECASE):
        collate = match.group(1)
        if collate.upper() == _COLLATE_EMPRESA.upper():
            continue
        if collate.upper() == "DATABASE_DEFAULT":
            hallazgos.append(_hallazgo(
                texto, match.start(1), "COLLATE_DATABASE_DEFAULT",
                f"Se detectó el uso de COLLATE DATABASE_DEFAULT, que toma el COLLATE de la base donde se "
                f"ejecuta. Se recomienda definir el COLLATE explícitamente con el que usa la empresa, ya que "
                f"DATABASE_DEFAULT puede cambiar entre bases y servidores, y las comparaciones fallarían "
                f"(ej.: COLLATE {_COLLATE_EMPRESA}).",
            ))
        else:
            hallazgos.append(_hallazgo(
                texto, match.start(1), "COLLATE_DISTINTO_AL_ESTANDAR",
                f"Se identificó el COLLATE {collate}, distinto al que usa la empresa ({_COLLATE_EMPRESA}). "
                f"Valide si el COLLATE es el correcto, ya que si no coincide con el de las demás "
                f"tablas las comparaciones y los JOIN pueden fallar.",
            ))
    return hallazgos


def _validar_collate_temporales(texto: str, limpio: str) -> List[Hallazgo]:
    """Toda columna de texto de una tabla temporal (#T) o variable de tabla (@T) lleva COLLATE."""
    hallazgos = []
    patron = re.compile(
        r"\b(?:CREATE\s+TABLE\s+(#[A-Za-z_]\w*)|DECLARE\s+(@[A-Za-z_]\w*)\s+(?:AS\s+)?TABLE)\s*\(",
        re.IGNORECASE,
    )
    for match in patron.finditer(limpio):
        tabla = match.group(1) or match.group(2)
        tipo_tabla = "la tabla temporal" if match.group(1) else "la variable de tabla"
        apertura = match.end() - 1
        contenido = _contenido_entre_parentesis(limpio, apertura)
        for definicion, desplazamiento in _separar_por_comas(contenido):
            columna = re.match(rf"\s*({_IDENTIFICADOR})\s+({_TIPOS_TEXTO})", definicion, re.IGNORECASE)
            if not columna or re.search(r"\bCOLLATE\s+\w+", definicion, re.IGNORECASE):
                continue
            tipo = re.match(r"\s*\S+\s+(\w+\s*(?:\([^)]*\))?)", definicion).group(1).upper().replace(" ", "")
            hallazgos.append(_hallazgo(
                texto, apertura + 1 + desplazamiento + columna.start(1), "TEMPORAL_TEXTO_SIN_COLLATE",
                f"La columna de texto {columna.group(1)} de {tipo_tabla} {tabla} no define "
                f"COLLATE. Añadir el COLLATE de la empresa, ya que sin él puede fallar al compararla "
                f"con columnas de otras tablas "
                f"(ej.: {columna.group(1)} {tipo} COLLATE SQL_Latin1_General_CP1_CI_AS).",
            ))
    return hallazgos


def _validar_comentarios(texto: str) -> List[Hallazgo]:
    patrones = (
        re.compile(rf"^\s*--\s*(?:{_PALABRAS_SQL_COMENTADAS})\b", re.IGNORECASE | re.MULTILINE),
        re.compile(rf"/\*\s*(?:{_PALABRAS_SQL_COMENTADAS})\b.*?\*/", re.IGNORECASE | re.DOTALL),
    )
    hallazgos = []
    vistos: Set[int] = set()
    for patron in patrones:
        for match in patron.finditer(texto):
            if match.start() not in vistos:
                vistos.add(match.start())
                hallazgos.append(_hallazgo(texto, match.start(), "CODIGO_SQL_COMENTADO", "Se encontró código SQL comentado, es decir, sentencias que ya no se ejecutan. Elimínelo "
                "si ya no se usa, ya que dificulta la lectura del procedimiento y el historial de "
                "cambios ya queda guardado en el control de versiones."))
    return hallazgos


def _validar_variables(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    declaraciones: Dict[str, int] = {}
    for match in re.finditer(r"\bDECLARE\s+(@[A-Za-z_]\w*)", limpio, re.IGNORECASE):
        # Se conserva el nombre tal como se escribió (@cLista, no @clista).
        if match.group(1).lower() not in {nombre.lower() for nombre in declaraciones}:
            declaraciones[match.group(1)] = match.start(1)
    for variable, posicion in declaraciones.items():
        if not re.search(rf"(?<![\w]){re.escape(variable)}\b", limpio[posicion + len(variable):], re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, posicion, "VARIABLE_DECLARADA_SIN_USO", f"La variable {variable} se declara, pero no se usa. Se recomienda eliminarla, "
                f"ya que no cumple ninguna función dentro del procedimiento."))
    return hallazgos


# Acciones estándar del manual: la palabra completa se abrevia.
_ACCIONES_ABREVIADAS = {
    "consultar": "Sel", "consulta": "Sel", "select": "Sel", "seleccionar": "Sel",
    "actualizar": "Upd", "actualiza": "Upd", "update": "Upd",
    "insertar": "Ins", "inserta": "Ins", "insert": "Ins",
    "eliminar": "Del", "elimina": "Del", "delete": "Del", "borrar": "Del",
}
# Ejemplo fijo que usa el diccionario de procedimientos (diccionario_nomenclatura.py).
_EJEMPLO_NOMBRE = "PA_Cliente_Sel_PorDocumento"
_ACCIONES_ESTANDAR = {"sel": "Sel", "upd": "Upd", "ins": "Ins", "del": "Del"}
# Otras formas de nombrar la acción que solo se usan para armar el ejemplo.
_ACCIONES_EN_SUGERENCIA = {
    "get": "Sel", "obtener": "Sel", "listar": "Sel", "buscar": "Sel",
    "set": "Upd", "modificar": "Upd", "add": "Ins", "agregar": "Ins", "registrar": "Ins",
    "remove": "Del", "quitar": "Del",
}


def _nombre_sugerido(nombre: str) -> str:
    """
    Ejemplo de nombre correcto armado con el nombre escrito:
    PA_ConsultarVentas → PA_Ventas_Sel; Cliente_Upd_Estado → PA_Cliente_Upd_Estado.
    Si no se reconoce la acción se propone Sel; si no hay tabla, se indica "Tabla".
    """
    segmentos = [x for x in nombre.split("_") if x]
    # Prefijos de otros estándares (PA_, SP_, USP_) no forman parte del nombre sugerido.
    if segmentos and segmentos[0].upper() in {"PA", "SP", "USP", "PROC"}:
        segmentos = segmentos[1:]
    palabras = [p for segmento in segmentos for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", segmento)]
    accion, resto = None, []
    for palabra in palabras:
        abreviada = (_ACCIONES_ESTANDAR.get(palabra.lower()) or _ACCIONES_ABREVIADAS.get(palabra.lower())
                     or _ACCIONES_EN_SUGERENCIA.get(palabra.lower()))
        if abreviada and accion is None:
            accion = abreviada
        else:
            resto.append(_en_pascal(palabra))
    tabla = resto[0] if resto else "Tabla"
    finalidad = "".join(resto[1:])
    return "_".join(["PA", tabla, accion or "Sel"] + ([finalidad] if finalidad else []))


def _es_pascal(parte: str) -> bool:
    """PascalCase: mayúscula inicial (Cliente, TipoCambio). Se aceptan siglas cortas (BI, IGV)."""
    return bool(re.fullmatch(r"(?:[A-Z][a-z0-9]+)+", parte)) or bool(re.fullmatch(r"[A-Z]{2,3}", parte)) \
        or parte in {"Sel", "Upd", "Ins", "Del"}


def _en_pascal(parte: str) -> str:
    """CLIENTE o cliente → Cliente; TipoCambio se respeta."""
    if parte.isupper() or parte.islower():
        return parte.capitalize()
    return parte[0].upper() + parte[1:]


# Acción estándar pegada a la finalidad sin "_": SelEjecucionesDetalle, ConsultarDatos.
_ACCION_PEGADA = re.compile(
    r"(Sel|Upd|Ins|Del|Consultar|Actualizar|Insertar|Eliminar|Select|Update|Insert|Delete)([A-Z]\w*)$"
)
_ABREVIATURA_ACCION = {
    "sel": "Sel", "upd": "Upd", "ins": "Ins", "del": "Del",
    "consultar": "Sel", "select": "Sel", "actualizar": "Upd", "update": "Upd",
    "insertar": "Ins", "insert": "Ins", "eliminar": "Del", "delete": "Del",
}


def _hallazgo_accion_pegada(texto: str, posicion: int, nombre: str, segmentos: List[str]):
    """Hallazgo si la acción va pegada a la finalidad (PA_Tabla_SelFinalidad); si no, None."""
    if len(segmentos) < 3:
        return None
    pegada = _ACCION_PEGADA.match(segmentos[2])
    if not pegada:
        return None
    accion = _ABREVIATURA_ACCION[pegada.group(1).lower()]
    sugerido = "_".join(["PA", segmentos[1], accion, pegada.group(2)] + [x for x in segmentos[3:] if x])
    return _hallazgo(
        texto, posicion, "PROCEDIMIENTO_ACCION_SIN_SEPARAR",
        f"Se identificó que en el nombre {nombre} la acción {pegada.group(1)} está pegada a la finalidad "
        f"({segmentos[2]}). Se recomienda separarla con un guion bajo, ya que el formato es "
        f"PA_Tabla_Acción_Finalidad (ej.: {sugerido}).",
    )


def _validar_nombre_procedimiento(texto: str, limpio: str) -> List[Hallazgo]:
    """Nomenclatura: Esquema.PA_Tabla_Acción_Finalidad (en un ALTER solo el esquema)."""
    match = re.search(
        rf"\b(CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+"
        rf"({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})",
        limpio, re.IGNORECASE,
    )
    if not match:
        return []
    partes = [parte.strip().strip("[]") for parte in match.group(2).split(".")]
    nombre = partes[-1]
    posicion = match.start(2)
    hallazgos = []

    if len(partes) == 1:
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_SIN_ESQUEMA",
            f"El procedimiento {nombre} no tiene declarado un esquema. Se recomienda añadir "
            f"el esquema; si es dbo, definirlo explícitamente, ya que así se evita crear o modificar un objeto "
            f"equivocado (ej.: dbo.{nombre}).",
        ))

    # En un ALTER el procedimiento ya existe: su nombre no se puede cambiar.
    if match.group(1).upper() != "CREATE":
        return hallazgos

    segmentos = nombre.split("_")
    if segmentos[0].upper() != "PA":
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_SIN_PREFIJO_PA",
            f"Se identificó que el procedimiento {nombre} no empieza con el prefijo PA_. Se recomienda usar el "
            f"formato PA_Tabla_Acción_Finalidad, ya que PA identifica a los procedimientos almacenados "
            f"(ej.: {_nombre_sugerido(nombre)}).",
        ))
        return hallazgos
    # PA_ y pa_ son equivalentes: el prefijo no distingue mayúsculas.

    if len(segmentos) < 3 or not all(segmentos[1:3]):
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            f"Se identificó que el nombre del procedimiento {nombre} no indica la tabla y la acción. Se "
            f"recomienda usar el formato PA_Tabla_Acción_Finalidad, ya que así se entiende qué hace el "
            f"procedimiento (ej.: {_nombre_sugerido(nombre)}).",
        ))
        return hallazgos

    pegada = _hallazgo_accion_pegada(texto, posicion, nombre, segmentos)
    if pegada:
        hallazgos.append(pegada)
        return hallazgos

    tabla, accion, finalidad = segmentos[1], segmentos[2], [parte for parte in segmentos[3:] if parte]
    abreviatura = _ACCIONES_ABREVIADAS.get(accion.lower())
    es_estandar = accion.lower() in {"sel", "upd", "ins", "del"}
    es_verbo = bool(re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+(?:ar|er|ir)", accion, re.IGNORECASE))

    if abreviatura and accion != abreviatura:
        sugerido = "_".join(["PA", _en_pascal(tabla), abreviatura] + [_en_pascal(x) for x in finalidad])
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
            f"La acción del procedimiento {nombre} está escrita como '{accion}'. "
            f"Usar la abreviatura del manual, {abreviatura}, ya que así se nombran las acciones "
            f"estándar (ej.: {sugerido}).",
        ))
    elif not es_estandar and not es_verbo:
        sugerido = "_".join(["PA", _en_pascal(tabla), "Sel", _en_pascal(accion)] + [_en_pascal(x) for x in finalidad])
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_SIN_ACCION",
            f"Se identificó que el nombre del procedimiento {nombre} no indica una acción: '{accion}' no es "
            f"Sel, Upd, Ins, Del ni un verbo. Se recomienda añadir la acción después de la tabla, ya que así se "
            f"entiende qué hace el procedimiento (ej.: {sugerido}).",
        ))
        accion = None  # su mayúscula ya se corrige en la sugerencia anterior

    partes = [tabla] + ([accion] if accion and not abreviatura else []) + finalidad
    fuera_de_estandar = [parte for parte in partes if not _es_pascal(parte)]
    # Una sigla pegada a otras palabras (SaldoRenovacionPF) no es un error seguro: se pide validarla.
    siglas = {parte: _siglas_del_nombre(parte, _PASCAL_CASE) for parte in fuera_de_estandar}
    con_sigla = [s for parte in fuera_de_estandar for s in siglas[parte]]
    errores = [parte for parte in fuera_de_estandar if not siglas[parte]]
    if con_sigla:
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_CON_SIGLA",
            f"Se identificó que el nombre del procedimiento {nombre} contiene "
            f"{_texto_siglas(list(dict.fromkeys(con_sigla)))}. Validar que "
            f"{'la sigla sea comprensible y esté estandarizada' if len(set(con_sigla)) == 1 else 'las siglas sean comprensibles y estén estandarizadas'}. "
            f"De ser necesario, reemplazar{'la' if len(set(con_sigla)) == 1 else 'las'} por términos descriptivos "
            f"que faciliten la comprensión del nombre del procedimiento.",
        ))
    if errores:
        # Solo se sugiere un nombre si es distinto y correcto; si no, se indica la parte sin inventar.
        casos = []
        for parte in errores:
            sugerida = _a_pascal_case(parte)
            casos.append(f"{parte} → {sugerida}" if sugerida and sugerida != parte and _es_pascal(sugerida) else parte)
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_NO_PASCALCASE",
            f"Se verificó que partes del nombre {nombre} no están en PascalCase ({', '.join(casos)}). Se "
            f"recomienda escribir cada palabra con mayúscula inicial y el resto en minúscula, ya que es el "
            f"estándar de nomenclatura.",
        ))
    return hallazgos


def _agrupar_repetidos(hallazgos: List[Hallazgo]) -> List[Hallazgo]:
    """Une los hallazgos de una misma regla en uno solo, con todas sus líneas.

    Formato: "Se encontraron N observaciones de este tipo, en las líneas 3, 8:
    hecho uno; hecho dos. Acción." La interfaz lo muestra como lista.
    """
    grupos: Dict[str, List[Hallazgo]] = {}
    for hallazgo in hallazgos:
        grupos.setdefault(hallazgo.regla, []).append(hallazgo)

    resumidos: List[Hallazgo] = []
    for regla, grupo in grupos.items():
        if len(grupo) == 1:
            resumidos.append(grupo[0])
            continue
        numeros = sorted({hallazgo.linea for hallazgo in grupo})
        lineas = ("la línea " if len(numeros) == 1 else "las líneas ") + ", ".join(map(str, numeros))
        partes = [re.split(r"(?<=[.?])\s+(?=[A-ZÁÉÍÓÚÑ¿(])", h.mensaje, maxsplit=1) for h in grupo]
        if all(len(parte) == 2 for parte in partes):
            hechos = list(dict.fromkeys(parte[0][:1].lower() + parte[0][1:].rstrip(".") for parte in partes))
            detalle = "; ".join(hechos) + ". " + partes[0][1]
        else:
            detalle = " ".join(dict.fromkeys(h.mensaje for h in grupo))
        resumidos.append(Hallazgo(
            linea=numeros[0],
            origen=grupo[0].origen,
            severidad=grupo[0].severidad,
            regla=regla,
            mensaje=f"Se encontraron {len(grupo)} observaciones de este tipo, en {lineas}: {detalle}",
        ))
    return resumidos


# Uso de JSON o XML: el único caso en que se permite VARCHAR(MAX).
_USO_JSON_XML = re.compile(
    r"\bFOR\s+(?:JSON|XML)\b|\bOPENJSON\s*\(|\bJSON_(?:VALUE|QUERY|MODIFY)\s*\(|\bISJSON\s*\(|"
    r"\bOPENXML\s*\(|\bAS\s+XML\b|\bCONVERT\s*\(\s*XML\b|\.(?:value|nodes|query|exist)\s*\(",
    re.IGNORECASE,
)


def _sentencia_de(limpio: str, posicion: int) -> str:
    inicio = limpio.rfind(";", 0, posicion) + 1
    fin = limpio.find(";", posicion)
    return limpio[inicio:fin if fin >= 0 else len(limpio)]


def _validar_varchar_max(texto: str, limpio: str) -> List[Hallazgo]:
    """VARCHAR(MAX) solo se permite para JSON, XML o datos que vienen de una tabla heredada."""
    hallazgos = []
    for match in re.finditer(r"\bN?VARCHAR\s*\(\s*MAX\s*\)", limpio, re.IGNORECASE):
        declarado = re.search(r"(@?[A-Za-z_]\w*)\s+(?:AS\s+)?$", limpio[:match.start()])
        nombre = declarado.group(1) if declarado and declarado.group(1).upper() not in {"AS", "CAST", "CONVERT"} else None
        if nombre:
            usos = re.finditer(rf"(?<![\w@]){re.escape(nombre)}\b", limpio, re.IGNORECASE)
            es_json_xml = re.search(r"json|xml", nombre, re.IGNORECASE) or any(
                _USO_JSON_XML.search(_sentencia_de(limpio, uso.start())) for uso in usos
            )
        else:
            es_json_xml = _USO_JSON_XML.search(_sentencia_de(limpio, match.start()))
        if es_json_xml:
            continue
        tipo = re.sub(r"\s+", "", match.group(0)).upper()
        sujeto = f"que {nombre} se declara como {tipo}" if nombre else f"el uso de {tipo}"
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARCHAR_MAX_PROHIBIDO",
            f"Se detectó {sujeto} y no guarda JSON ni XML. Definir una longitud acorde al "
            f"dato, salvo que provenga de una tabla heredada con {tipo}, ya que solo se justifica para JSON, "
            f"XML o tablas heredadas y reserva más memoria de la necesaria (ej.: {tipo.replace('MAX', '500')}).",
        ))
    return hallazgos


def _validar_waitfor(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bWAITFOR\s+(DELAY|TIME)\s*('[^']*')?", limpio, re.IGNORECASE):
        tipo = match.group(1).upper()
        valor = match.group(2) or ""
        espera = f" {valor}" if valor else ""
        if tipo == "DELAY" and _duracion_en_palabras(valor):
            efecto = f"que detiene la ejecución del procedimiento durante {_duracion_en_palabras(valor)}"
        elif tipo == "TIME" and valor:
            efecto = f"que detiene la ejecución del procedimiento hasta las {valor.strip(chr(39))}"
        else:
            efecto = "que detiene la ejecución del procedimiento"
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            f"Se identificó el uso de WAITFOR {tipo}{espera}, {efecto}. Se recomienda retirar esta instrucción, "
            f"ya que obligar al motor de base de datos a esperar innecesariamente retrasa la ejecución y "
            f"constituye una mala práctica.",
        ))
    return hallazgos


_NUMEROS = (
    "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis "
    "diecisiete dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro veinticinco "
    "veintiséis veintisiete veintiocho veintinueve"
).split()
_DECENAS = {3: "treinta", 4: "cuarenta", 5: "cincuenta"}


def _numero_en_palabras(numero: int, femenino: bool = False) -> str:
    if numero < 30:
        palabra = _NUMEROS[numero]
    else:
        decena, unidad = divmod(numero, 10)
        palabra = _DECENAS.get(decena, str(numero)) + (f" y {_NUMEROS[unidad]}" if unidad else "")
    if numero % 10 == 1 and numero != 11:
        palabra = palabra[:-3] + ("una" if femenino else "un")  # uno -> un / una; veintiuno -> veintiún
        palabra = palabra.replace("veintiun", "veintiún")
    return palabra


def _duracion_en_palabras(valor: str) -> str:
    """'00:00:05' -> 'cinco segundos'; '00:01:30' -> 'un minuto y treinta segundos'."""
    partes = re.fullmatch(r"'(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?(?:\.\d+)?'", valor.strip())
    if not partes:
        return ""
    horas, minutos, segundos = (int(p) if p else 0 for p in partes.groups())
    trozos = []
    for cantidad, singular, plural, femenino in (
        (horas, "hora", "horas", True), (minutos, "minuto", "minutos", False), (segundos, "segundo", "segundos", False),
    ):
        if cantidad:
            trozos.append(f"{_numero_en_palabras(cantidad, femenino)} {singular if cantidad == 1 else plural}")
    if not trozos:
        return ""
    return trozos[0] if len(trozos) == 1 else f"{', '.join(trozos[:-1])} y {trozos[-1]}"


def _validar_raiserror(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bRAISERROR\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "RAISERROR_USAR_THROW",
            "Se identificó RAISERROR para mostrar errores. Se recomienda usar THROW, ya que es la forma "
            "actual de manejar errores y conserva el detalle del error original "
            "(ej.: THROW 50001, 'No existe el cliente', 1;).",
        ))
    return hallazgos


def _validar_in_un_valor(texto: str, limpio: str) -> List[Hallazgo]:
    """IN se usa con dos o más valores; con uno solo corresponde = (o <> si es NOT IN)."""
    hallazgos = []
    patron = re.compile(r"([\w.\[\]@#]+)\s+(NOT\s+)?IN\s*\(\s*([^,()]+?)\s*\)", re.IGNORECASE)
    for match in patron.finditer(limpio):
        columna, negado = match.group(1), bool(match.group(2))
        # El valor se toma del código original: en "limpio" el contenido de los textos va en blanco.
        valor = texto[match.start(3):match.end(3)]
        if re.match(r"SELECT\b", valor, re.IGNORECASE):
            continue  # IN (SELECT ...) es una subconsulta, no una lista de valores
        operador_in = "NOT IN" if negado else "IN"
        operador = "<>" if negado else "="
        hallazgos.append(_hallazgo(
            texto, match.start(), "IN_CON_UN_SOLO_VALOR",
            f"Se identificó {columna} {operador_in} ({valor}) con un solo valor. Se recomienda usar {operador}, "
            f"ya que {operador_in} está pensado para dos o más valores y con uno solo es más claro y directo "
            f"(ej.: {columna} {operador} {valor}).",
        ))
    return hallazgos


def _validar_left_como_like(texto: str, limpio: str) -> List[Hallazgo]:
    """LEFT(col, n) = 'abc' en una condición: con LIKE 'abc%' se aprovechan los índices."""
    hallazgos = []
    columna = r"[\w.\[\]@#]+"
    valor = r"'[^']*'|@\w+"
    patrones = (
        rf"\bLEFT\s*\(\s*(?P<col>{columna})\s*,\s*(?P<n>\d+)\s*\)\s*=\s*(?P<val>{valor})",
        rf"(?P<val>{valor})\s*=\s*LEFT\s*\(\s*(?P<col>{columna})\s*,\s*(?P<n>\d+)\s*\)",
    )
    for patron in patrones:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            col, n, val = match.group("col"), match.group("n"), match.group("val")
            like = f"{col} LIKE '{val[1:-1]}%'" if val.startswith("'") else f"{col} LIKE {val} + '%'"
            hallazgos.append(_hallazgo(
                texto, match.start(), "LEFT_REEMPLAZABLE_POR_LIKE",
                f"Se encontró LEFT({col}, {n}) = {val} en una condición. Emplear LIKE, ya que "
                f"aplicar LEFT a la columna impide usar sus índices y LIKE con el comodín al final sí los "
                f"aprovecha (ej.: {like}).",
            ))
    return hallazgos


def _desarmar_replace(expresion: str):
    """REPLACE(REPLACE(x, 'a', '1'), 'b', '2') → (x, [('a', '1'), ('b', '2')]) o None."""
    pares = []
    actual = expresion.strip()
    while True:
        cabecera = re.match(r"REPLACE\s*\(", actual, re.IGNORECASE)
        if not cabecera or not actual.endswith(")"):
            break
        argumentos = [parte.strip() for parte, _ in _separar_por_comas(actual[cabecera.end():-1])]
        if len(argumentos) != 3:
            return None
        actual = argumentos[0]
        pares.insert(0, (argumentos[1], argumentos[2]))
    return actual, pares


def _validar_replace_anidado(texto: str, limpio: str) -> List[Hallazgo]:
    """Tres o más REPLACE anidados que cambian caracteres sueltos: se hace con un TRANSLATE."""
    hallazgos = []
    usados = set()
    patron = re.compile(r"\bREPLACE\s*\(\s*REPLACE\s*\(\s*REPLACE\s*\(", re.IGNORECASE)
    for match in patron.finditer(limpio):
        if any(inicio <= match.start() < fin for inicio, fin in usados):
            continue  # es parte de una cadena de REPLACE ya reportada
        apertura = limpio.index("(", match.start())
        contenido = _contenido_entre_parentesis(limpio, apertura)
        usados.add((match.start(), apertura + len(contenido) + 2))
        desarmado = _desarmar_replace(limpio[match.start():apertura + len(contenido) + 2])
        cantidad = len(desarmado[1]) if desarmado else 3
        sugerencia = ""
        if desarmado:
            base, pares = desarmado
            literales = all(re.fullmatch(r"'[^']'", buscar) and re.fullmatch(r"'[^']'", poner)
                            for buscar, poner in pares)
            if literales:
                origen = "".join(buscar[1] for buscar, _ in pares)
                destino = "".join(poner[1] for _, poner in pares)
                # Si un carácter reemplazado vuelve a reemplazarse, TRANSLATE no da el mismo resultado.
                if not set(destino) & set(origen):
                    sugerencia = f" (ej.: TRANSLATE({base}, '{origen}', '{destino}'))"
            elif all(re.fullmatch(r"'[^']'", buscar) and poner == "''" for buscar, poner in pares):
                # Todos eliminan un carácter: TRANSLATE los convierte en uno solo y un REPLACE lo quita.
                origen = "".join(buscar[1] for buscar, _ in pares)
                sugerencia = f" (ej.: REPLACE(TRANSLATE({base}, '{origen}', '{'|' * len(origen)}'), '|', ''))"
        hallazgos.append(_hallazgo(
            texto, match.start(), "REPLACE_ANIDADO_TRANSLATE",
            f"Se identificaron {cantidad} REPLACE anidados. Usar TRANSLATE, ya que cambia "
            f"varios caracteres en una sola función y le da más legibilidad al código"
            f"{sugerencia}.",
        ))
    return hallazgos


def _validar_transacciones(texto: str, limpio: str) -> List[Hallazgo]:
    """Toda transacción abierta (BEGIN TRAN) debe cerrarse con COMMIT."""
    inicios = list(re.finditer(r"\bBEGIN\s+(?:DISTRIBUTED\s+)?TRAN(?:SACTION)?\b", limpio, re.IGNORECASE))
    commits = len(re.findall(r"\bCOMMIT(?:\s+(?:TRAN(?:SACTION)?|WORK))?\b", limpio, re.IGNORECASE))
    if not inicios or commits >= len(inicios):
        return []
    if commits == 0:
        detalle = "pero ningún COMMIT"
    else:
        detalle = f"pero solo {commits} COMMIT para {len(inicios)} BEGIN TRANSACTION"
    return [_hallazgo(
        texto, inicios[commits].start(), "TRANSACCION_SIN_COMMIT",
        f"Se detectó una transacción abierta con BEGIN TRANSACTION {detalle}. Se recomienda confirmarla "
        f"con COMMIT TRANSACTION al terminar (y deshacerla con ROLLBACK en el CATCH), ya que una "
        f"transacción sin cerrar deja las tablas bloqueadas para los demás usuarios.",
    )]


def _validar_envio_correo(texto: str, limpio: str) -> List[Hallazgo]:
    """Enviar correos desde la base de datos (Database Mail) es crítico."""
    hallazgos = []
    for match in re.finditer(r"(?:\b\w+\s*\.\s*)*\bsp_send_dbmail\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "ENVIO_CORREO_DESDE_BD",
            f"Se identificó un envío de correo desde la base de datos ({_limpiar_nombre(match.group(0))}). "
            f"Se recomienda retirar el envío de correo del procedimiento y hacerlo desde la aplicación, ya que "
            f"depende de la "
            f"configuración de Database Mail, puede dejar la transacción esperando y expone información "
            f"fuera del sistema.",
        ))
    return hallazgos


def _validar_esquema_entre_bases(texto: str, limpio: str) -> List[Hallazgo]:
    """Base..Tabla omite el esquema: entre bases se escribe Base.Esquema.Tabla."""
    hallazgos = []
    patron = re.compile(r"(\[[^\]]+\]|[A-Za-z_][\w$#]*)\s*\.\s*\.\s*(\[[^\]]+\]|[A-Za-z_][\w$#]*)")
    for match in patron.finditer(limpio):
        base, tabla = match.group(1), match.group(2)
        hallazgos.append(_hallazgo(
            texto, match.start(), "ESQUEMA_OMITIDO_ENTRE_BASES",
            f"Se verificó el uso de la tabla {tabla} de la base {base}, pero el esquema se omitió "
            f"({base}..{tabla}). Defina el esquema, ya que así se evita apuntar a una tabla "
            f"equivocada (ej.: {base}.dbo.{tabla}).",
        ))
    return hallazgos


# Inicio de una nueva sentencia: separa las consultas del procedimiento.
_INICIO_SENTENCIA = re.compile(
    r";|\bGO\b|^\s*(?=(?:INSERT|UPDATE|DELETE|DECLARE|SET|IF|ELSE|END|BEGIN|RETURN|CREATE|DROP|"
    r"TRUNCATE|EXEC|EXECUTE|WHILE|MERGE|WITH)\b)",
    re.IGNORECASE | re.MULTILINE,
)
_VECES_MAXIMAS_MISMA_TABLA = 3


def _validar_tabla_repetida(texto: str, limpio: str) -> List[Hallazgo]:
    """Una misma tabla leída más de 3 veces (FROM/JOIN) dentro de una misma consulta."""
    hallazgos = []
    cortes = [m.start() for m in _INICIO_SENTENCIA.finditer(limpio)]
    # Un SELECT al inicio de línea y fuera de paréntesis también es una consulta
    # nueva (procedimientos sin ";"); dentro de paréntesis es una subconsulta.
    for match in re.finditer(r"^\s*(?=SELECT\b)", limpio, re.IGNORECASE | re.MULTILINE):
        if limpio.count("(", 0, match.start()) == limpio.count(")", 0, match.start()):
            cortes.append(match.start())
    cortes = sorted({0, len(limpio), *cortes})
    for inicio, fin in zip(cortes, cortes[1:]):
        accesos: Dict[str, List[int]] = {}
        nombres: Dict[str, str] = {}
        for match in re.finditer(rf"\b(?:FROM|JOIN)\s+({_REFERENCIA})(?![\w$#.\]])(?!\s*\()",
                                 limpio[inicio:fin], re.IGNORECASE):
            nombre = _limpiar_nombre(match.group(1))
            clave = nombre.split(".")[-1].strip("[]").lower()  # dbo.Cliente y [Cliente] son la misma
            accesos.setdefault(clave, []).append(inicio + match.start(1))
            nombres.setdefault(clave, nombre)
        for clave, posiciones in accesos.items():
            if len(posiciones) <= _VECES_MAXIMAS_MISMA_TABLA:
                continue
            lineas = ", ".join(str(n) for n in sorted({_linea(texto, pos) for pos in posiciones}))
            hallazgos.append(_hallazgo(
                texto, posiciones[0], "TABLA_REPETIDA_EN_CONSULTA",
                f"La tabla {nombres[clave]} se consulta {len(posiciones)} veces en la misma "
                f"consulta ({'líneas' if ',' in lineas else 'línea'} {lineas}). Se recomienda revisar si se puede leer una sola vez (por ejemplo, "
                f"cargándola antes en una tabla temporal o combinando las condiciones), ya que acceder "
                f"muchas veces a la misma tabla vuelve lenta la consulta.",
            ))
    return hallazgos


def _fin_de_sentencia(limpio: str, inicio: int) -> int:
    """Donde termina la sentencia que empieza en `inicio`: ';', la siguiente instrucción o un SELECT
    al inicio de línea fuera de paréntesis (el SET de un UPDATE sigue siendo parte de él)."""
    profundidad = 0
    for indice in range(inicio, len(limpio)):
        caracter = limpio[indice]
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad = max(profundidad - 1, 0)
        elif profundidad == 0 and caracter == ";":
            return indice
        elif profundidad == 0 and caracter == "\n":
            siguiente = re.match(
                r"\n\s*(INSERT|UPDATE|DELETE|DECLARE|IF|ELSE|END|BEGIN|RETURN|CREATE|DROP|TRUNCATE|EXEC|"
                r"EXECUTE|WHILE|MERGE|WITH|SELECT|GO|PRINT|THROW|RAISERROR|COMMIT|ROLLBACK)\b",
                limpio[indice:], re.IGNORECASE,
            )
            if siguiente:
                return indice
    return len(limpio)


def _a_nivel_cero(sentencia: str, patron: str) -> bool:
    """El patrón aparece fuera de paréntesis (no en una subconsulta)."""
    for match in re.finditer(patron, sentencia, re.IGNORECASE):
        if sentencia.count("(", 0, match.start()) == sentencia.count(")", 0, match.start()):
            return True
    return False


def _validar_modificacion_sin_where(texto: str, limpio: str) -> List[Hallazgo]:
    """
    UPDATE o DELETE sobre una tabla física sin WHERE: afecta toda la tabla. No se marcan las
    temporales ni las variables de tabla, ni la sentencia con JOIN (el JOIN ya limita las filas).
    """
    hallazgos = []
    ctes = {n.lower() for n in re.findall(r"(?:\bWITH|,)\s*([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s+AS\s*\(", limpio, re.IGNORECASE)}
    patron = re.compile(
        rf"\b(UPDATE|DELETE)\s+(?:TOP\s*\([^)]*\)\s*)?(?:FROM\s+)?({_REFERENCIA})", re.IGNORECASE,
    )
    for match in patron.finditer(limpio):
        accion = match.group(1).upper()
        objetivo = _limpiar_nombre(match.group(2))
        # UPDATE STATISTICS, y el UPDATE SET / DELETE de un MERGE (WHEN MATCHED THEN UPDATE SET ...).
        if objetivo.upper() in {"STATISTICS", "SET"} or re.search(r"\bTHEN\s*$", limpio[:match.start()], re.IGNORECASE):
            continue
        sentencia = limpio[match.start():_fin_de_sentencia(limpio, match.end())]
        if _a_nivel_cero(sentencia, r"\bWHERE\b") or _a_nivel_cero(sentencia, r"\bJOIN\b|\bAPPLY\b"):
            continue
        tabla = objetivo
        if "." not in objetivo and not _es_temporal(objetivo):
            # UPDATE c SET ... FROM dbo.Cliente c / DELETE c FROM dbo.Cliente c: el alias se resuelve en el FROM.
            origen = re.search(
                rf"\bFROM\s+({_REFERENCIA})\s+(?:AS\s+)?{re.escape(objetivo)}\b", sentencia, re.IGNORECASE)
            if origen:
                tabla = _limpiar_nombre(origen.group(1))
        if _es_temporal(tabla) or tabla.lower() in ctes:
            continue
        verbo, efecto = ("actualizar", "se modificarán") if accion == "UPDATE" else ("eliminar", "se eliminarán")
        hallazgos.append(_hallazgo(
            texto, match.start(), "MODIFICACION_SIN_WHERE",
            f"Se identificó un {accion} sobre la tabla {tabla} sin condición WHERE, por lo que {efecto} todos "
            f"sus registros. Se recomienda agregar la condición WHERE que limite los registros a {verbo}, ya que "
            f"sin ella el cambio afecta a toda la tabla.",
        ))
    return hallazgos


def verificar_procedimiento_normal(texto_sql: str, es_del_motor: bool = False) -> List[Hallazgo]:
    """
    Aplica exclusivamente las reglas de procedimientos normales. Si el
    procedimiento pertenece al motor de base de datos (es_del_motor), se le
    permite el SELECT * (sus tablas son enormes); el resto de reglas se aplica igual.
    """
    limpio = _quitar_comentarios(texto_sql)
    # Igual que "limpio", pero con el contenido de los textos (para los mensajes que lo muestran).
    con_textos = _quitar_solo_comentarios(texto_sql)
    hallazgos: List[Hallazgo] = []
    hallazgos.extend(_validar_nombre_procedimiento(texto_sql, limpio))
    hallazgos.extend(_validar_control_flujo(texto_sql, limpio))
    hallazgos.extend(_validar_hints(texto_sql, limpio))
    hallazgos.extend(_validar_hints_bloqueo(texto_sql, limpio))
    hallazgos.extend(_validar_indice_forzado(texto_sql, limpio))
    hallazgos.extend(_validar_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_update_from_nolock(texto_sql, limpio))
    hallazgos.extend(_validar_modificacion_sin_where(texto_sql, limpio))
    hallazgos.extend(_validar_nolock_tablas_pesadas(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_cast_en_join(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_varchar_max(texto_sql, limpio))
    hallazgos.extend(_validar_waitfor(texto_sql, con_textos))
    hallazgos.extend(_validar_raiserror(texto_sql, limpio))
    hallazgos.extend(_validar_transacciones(texto_sql, limpio))
    hallazgos.extend(_validar_envio_correo(texto_sql, limpio))
    hallazgos.extend(_validar_in_un_valor(texto_sql, limpio))
    hallazgos.extend(_validar_left_como_like(texto_sql, con_textos))
    hallazgos.extend(_validar_replace_anidado(texto_sql, con_textos))
    hallazgos.extend(_validar_esquema_entre_bases(texto_sql, limpio))
    hallazgos.extend(_validar_tabla_repetida(texto_sql, limpio))
    hallazgos.extend(_validar_collate_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_collate_usado(texto_sql, limpio))
    hallazgos.extend(_validar_tipos_entre_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_comentarios(texto_sql))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    if es_del_motor:
        hallazgos = [h for h in hallazgos if h.regla != "SELECT_ESTRELLA_PROHIBIDO"]
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_PROCEDIMIENTOS_NORMALES[h.regla].activo]
    return _agrupar_repetidos(hallazgos)


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_CATALOGO_SISTEMA, limpio, re.IGNORECASE):
        objeto = _limpiar_nombre(match.group(0))
        hallazgos.append(_hallazgo(
            texto, match.start(), "CATALOGO_SISTEMA_PROHIBIDO",
            f"Se detectó una consulta a {objeto}, una tabla interna de SQL Server. Consultar "
            f"solo las tablas del negocio, ya que un procedimiento no debe depender de las tablas internas del "
            f"motor.",
        ))
    for match in re.finditer(_SQL_DINAMICO, limpio, re.IGNORECASE):
        variable = re.search(r"@\w+", limpio[match.start():match.start() + 80])
        guardada = f" guardada en {variable.group(0)}" if variable else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "SQL_DINAMICO_PROHIBIDO",
            f"Se identificó SQL dinámico: la consulta{guardada} se arma como texto y se ejecuta con EXEC o "
            f"sp_executesql. Se recomienda escribir la consulta directamente y usar parámetros para los "
            f"filtros, ya que el SQL dinámico es difícil de revisar y puede permitir ataques de inyección de SQL.",
        ))
    hallazgos.extend(_validar_documentos_guardados(texto, limpio))
    return hallazgos


_TIPO_BINARIO = r"\b(?:VARBINARY|IMAGE)\b(?:\s*\(\s*(?:MAX|\d+)\s*\))?"
# Fin de un INSERT/UPDATE: punto y coma o el inicio de otra sentencia.
_FIN_ESCRITURA = re.compile(
    r";|\b(?:INSERT|UPDATE|DELETE|MERGE|DECLARE|RETURN|END|IF|BEGIN|COMMIT|ROLLBACK|EXEC(?:UTE)?|GO)\b",
    re.IGNORECASE,
)


def _validar_documentos_guardados(texto: str, limpio: str) -> List[Hallazgo]:
    """
    VARBINARY solo se marca cuando de verdad se guarda un documento en una tabla
    física: un INSERT/UPDATE que escribe un valor binario (variable o parámetro
    VARBINARY, CAST/CONVERT a VARBINARY, OPENROWSET SINGLE_BLOB) o una tabla
    física que agrega una columna VARBINARY. Consultarlo o declararlo no se marca.
    """
    hallazgos = []
    variables = {
        nombre.lower()
        for match in re.finditer(_TIPO_BINARIO, limpio, re.IGNORECASE)
        if (nombre := _nombre_declarado_antes(limpio, match.start())) and nombre.startswith("@")
    }
    pistas = [
        (rf"\b(?:CAST|CONVERT)\s*\((?:[^()]|\([^()]*\))*?{_TIPO_BINARIO}", "un valor convertido a VARBINARY"),
        (r"\bOPENROWSET\s*\([^)]*\bSINGLE_BLOB\b", "un archivo leído con OPENROWSET"),
    ]
    if variables:
        pistas.append((
            r"(?<![\w@])(" + "|".join(re.escape(v) for v in sorted(variables, key=len, reverse=True)) + r")\b",
            None,
        ))

    escrituras = re.finditer(
        rf"\b(INSERT(?:\s+INTO)?|UPDATE)\s+(?!(?:INTO|STATISTICS)\b)({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})",
        limpio, re.IGNORECASE,
    )
    for escritura in escrituras:
        tabla = escritura.group(2).strip()
        fin = _FIN_ESCRITURA.search(limpio, escritura.end())
        tramo_fin = fin.start() if fin else len(limpio)
        tramo = limpio[escritura.end():tramo_fin]
        if "." not in tabla and not _es_temporal(tabla):
            # UPDATE d SET ... FROM dbo.Documento d: el objetivo es la tabla del alias.
            alias = re.search(
                rf"\bFROM\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})\s+(?:AS\s+)?{re.escape(tabla)}\b",
                tramo, re.IGNORECASE,
            )
            if alias:
                tabla = alias.group(1).strip()
        if _es_temporal(tabla):
            continue
        for patron, descripcion in pistas:
            pista = re.search(patron, tramo, re.IGNORECASE)
            if not pista:
                continue
            que = descripcion or f"la variable {pista.group(1)} (VARBINARY)"
            accion = "UPDATE" if escritura.group(1).upper() == "UPDATE" else "INSERT"
            hallazgos.append(_hallazgo(
                texto, escritura.end() + pista.start(), "DOCUMENTO_GUARDADO_EN_BD",
                f"Se identificó que el procedimiento guarda un documento en la base de datos: {que} se "
                f"escribe en la tabla {tabla} con {accion}. Se recomienda guardar el documento en la solución "
                f"externa y registrar solo su ruta, ya que la base de datos es solo para datos transaccionales.",
            ))
            break

    # Una tabla física que agrega una columna para documentos.
    for match in re.finditer(
        rf"\b(CREATE\s+TABLE|ALTER\s+TABLE)\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})", limpio, re.IGNORECASE,
    ):
        tabla = match.group(2).strip()
        if _es_temporal(tabla):
            continue
        fin = re.search(r";|\bGO\b|\b(?:CREATE|ALTER|INSERT|UPDATE|DELETE|SELECT|DECLARE)\b", limpio[match.end():], re.IGNORECASE)
        tramo = limpio[match.end():match.end() + (fin.start() if fin else len(limpio))]
        columna = re.search(rf"({_IDENTIFICADOR})\s+{_TIPO_BINARIO}", tramo, re.IGNORECASE)
        if columna:
            hallazgos.append(_hallazgo(
                texto, match.end() + columna.start(), "DOCUMENTO_GUARDADO_EN_BD",
                f"Se identificó que la tabla {tabla} tendrá la columna {columna.group(1)} de tipo VARBINARY para "
                f"guardar documentos. Se recomienda guardar el documento en la solución externa y registrar solo "
                f"su ruta, ya que la base de datos es solo para datos transaccionales.",
            ))
    return hallazgos
