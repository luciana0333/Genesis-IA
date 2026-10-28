# -*- coding: utf-8 -*-
"""Reglas de buenas prácticas para procedimientos almacenados de reportes."""

import re
from typing import Dict, List, Optional, Set, Tuple

from app.analizadores.comentarios_prueba import es_bloque_de_prueba, nombre_del_procedimiento
from app.analizadores.drop_table_if_exists import mensaje_drop_if_exists, validaciones_antes_de_drop
from app.analizadores.openjson_collate import collates_en_openjson, mensaje_collate_openjson
from app.analizadores.sql_order_by import order_by_por_posicion
from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_reportes import REGLAS_REPORTES


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_HINTS_PROHIBIDOS = (
    r"\bOPTION\s*\([^)]*\)|\bDBCC\b|\bFORCESEEK\b|\bFORCESCAN\b|\bFORCE\s+ORDER\b|\bRECOMPILE\b|"
    r"\bNOEXPAND\b|\bINDEX\s*\(|\b(?:LOOP|HASH|MERGE)\s+JOIN\b|\bOPTIMIZE\s+FOR\b|\bMAXDOP\b|"
    r"\bFAST\s+\d+|\bUSE\s+PLAN\b|\bKEEP(?:FIXED)?\s+PLAN\b|\bQUERYTRACEON\b"
)
# Hints de bloqueo: no cambian el plan, cambian cómo se bloquean las filas
# leídas. Cada uno con lo que hace, para explicarlo en el mensaje.
_HINTS_BLOQUEO = {
    "UPDLOCK": "bloquea las filas leídas como si se fueran a actualizar y las mantiene bloqueadas hasta que "
               "termina la transacción",
    "HOLDLOCK": "mantiene bloqueadas las filas leídas hasta que termina la transacción, como el aislamiento "
                "SERIALIZABLE",
    "SERIALIZABLE": "mantiene bloqueadas las filas leídas hasta que termina la transacción",
    "REPEATABLEREAD": "mantiene bloqueadas las filas leídas hasta que termina la transacción",
    "XLOCK": "toma un bloqueo exclusivo sobre las filas leídas",
    "TABLOCKX": "toma un bloqueo exclusivo sobre toda la tabla",
    "TABLOCK": "bloquea toda la tabla en lugar de solo las filas leídas",
    "PAGLOCK": "obliga al motor a bloquear páginas completas",
    "ROWLOCK": "obliga al motor a bloquear fila por fila",
    "READPAST": "salta las filas que otro proceso tiene bloqueadas",
}
_PATRON_BLOQUEO = re.compile(r"\b(" + "|".join(_HINTS_BLOQUEO) + r")\b", re.IGNORECASE)
# Palabras que pueden ir antes de un hint de bloqueo dentro del mismo paréntesis.
_HINTS_DE_TABLA = set(_HINTS_BLOQUEO) | {
    "NOLOCK", "READUNCOMMITTED", "READCOMMITTED", "FORCESEEK", "FORCESCAN", "NOEXPAND", "NOWAIT",
}
_CATALOGOS_PROHIBIDOS = r"(?:sys|information_schema)\.(?!sp_|xp_)[A-Za-z_][\w$]*"
_PALABRAS_SQL_COMENTADAS = r"SELECT|INSERT|UPDATE|DELETE|MERGE|EXEC(?:UTE)?|DECLARE|CREATE|ALTER|DROP"
_SQL_DINAMICO = r"\b(?:sp_executesql\b|EXEC(?:UTE)?\s*(?:\(\s*)?(?:N?['\"]|@))"
# Uso de JSON o XML: justifica un VARCHAR(MAX).
_USO_JSON_XML = re.compile(
    r"\bFOR\s+(?:JSON|XML)\b|\bOPENJSON\s*\(|\bJSON_(?:VALUE|QUERY|MODIFY)\s*\(|\bISJSON\s*\(|"
    r"\bOPENXML\s*\(|\bAS\s+XML\b|\bCONVERT\s*\(\s*XML\b|\.(?:value|nodes|query|exist)\s*\(",
    re.IGNORECASE,
)


def _linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    """Hallazgo con la severidad definida en el catálogo de reglas de reportes."""
    return Hallazgo(
        linea=_linea(texto, posicion),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_REPORTES[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


def _quitar_comentarios(texto: str, vaciar_textos: bool = True) -> str:
    """
    Reemplaza por espacios los comentarios y el contenido de los textos ('...'),
    conservando las comillas, los saltos de línea y las posiciones. Se recorre
    una sola vez para que un '--' dentro de un texto no se tome como comentario
    y un 'SELECT * FROM sys.objects' escrito como texto no dispare reglas. El
    SQL dinámico (N'SELECT ...' asignado o ejecutado) sí se conserva: es código.
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
            if vaciar_textos and not _es_sql_dinamico(texto, i, texto[i + 1:j]):
                salida[i + 1:j] = [c if c == "\n" else " " for c in texto[i + 1:j]]
            i = j + 1
        else:
            i += 1
    return "".join(salida)


# Un texto es SQL dinámico si se asigna a una variable, se concatena o se pasa
# a EXEC / sp_executesql, y además contiene una consulta.
_ANTES_DE_SQL_DINAMICO = re.compile(r"(?:=|\+|\bEXEC(?:UTE)?\s*\(?|\bsp_executesql)\s*N?$", re.IGNORECASE)
_CONTENIDO_SQL = re.compile(r"\b(?:SELECT|FROM|JOIN|INSERT|UPDATE|DELETE|MERGE)\b", re.IGNORECASE)


def _es_sql_dinamico(texto: str, comilla: int, contenido: str) -> bool:
    """Indica si el texto que abre en `comilla` es código SQL dinámico (se revisa como código)."""
    return bool(_ANTES_DE_SQL_DINAMICO.search(texto[max(0, comilla - 40):comilla])
                and _CONTENIDO_SQL.search(contenido))


def _es_temporal(nombre: str) -> bool:
    limpio = nombre.strip("[]")
    return limpio.startswith("#") or limpio.startswith("@")


def _nombre_tabla(match: re.Match[str]) -> str:
    return match.group(2).strip()


def _esta_en_update(limpio: str, posicion: int) -> bool:
    """Indica si la referencia pertenece al FROM/JOIN de un UPDATE."""
    inicio_sentencia = max(
        limpio.rfind(";", 0, posicion),
        limpio.rfind("BEGIN", 0, posicion),
    ) + 1
    prefijo = limpio[inicio_sentencia:posicion]
    return bool(re.search(r"\bUPDATE\b", prefijo, re.IGNORECASE))


# Palabras que pueden seguir al nombre de una tabla y que no son un alias.
_NO_ALIAS = (
    "WITH|ON|WHERE|INNER|LEFT|RIGHT|FULL|CROSS|OUTER|JOIN|GROUP|ORDER|UNION|EXCEPT|"
    "INTERSECT|HAVING|OPTION|SET|FOR|INTO|PIVOT|UNPIVOT|APPLY|AND|OR|WHEN|THEN|ELSE|END"
)
# Tras la tabla: alias opcional (con o sin AS) y el hint WITH(NOLOCK) o (NOLOCK).
_ALIAS_Y_NOLOCK = re.compile(
    rf"(?:\s+(?:AS\s+)?(?!(?:{_NO_ALIAS})\b)[A-Za-z_][\w$#]*)?"
    r"\s*(?:WITH\s*)?\(\s*(?:NOLOCK|READUNCOMMITTED)\b",
    re.IGNORECASE,
)


def _tabla_del_alias(limpio: str, alias: str) -> str:
    """Tabla a la que apunta un alias en un FROM o JOIN (dbo.Cliente c → dbo.Cliente); si no, el alias."""
    match = re.search(
        rf"\b(?:FROM|JOIN)\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})\s+(?:AS\s+)?{re.escape(alias)}\b",
        limpio, re.IGNORECASE,
    )
    return match.group(1).strip() if match else alias


# Lo que cierra una sentencia (fuera de paréntesis): «;», GO o el inicio de otra sentencia.
_FIN_DE_SENTENCIA = re.compile(
    r"\(|\)|;|\b(?:GO|INSERT|UPDATE|DELETE|MERGE|TRUNCATE|CREATE|ALTER|DROP|DECLARE|EXEC|EXECUTE|IF|ELSE|"
    r"WHILE|BEGIN|END|RETURN|PRINT|SELECT|UNION|WITH)\b",
    re.IGNORECASE,
)


def _fin_de_sentencia(limpio: str, desde: int) -> int:
    """Dónde termina la sentencia que sigue en `desde`; sirve aunque el código no use «;»."""
    nivel = 0
    for token in _FIN_DE_SENTENCIA.finditer(limpio, desde):
        if token.group(0) == "(":
            nivel += 1
        elif token.group(0) == ")":
            nivel -= 1
            if nivel < 0:
                return token.start()
        elif nivel == 0:
            return token.start()
    return len(limpio)


def _tabla_del_alias_en(limpio: str, desde: int, alias: str) -> str:
    """Tabla del alias según el FROM/JOIN de la misma sentencia (DELETE A FROM #Saldo A → #Saldo)."""
    return _tabla_del_alias(limpio[desde:_fin_de_sentencia(limpio, desde)], alias)


def _tabla_de_la_cte(limpio: str, nombre: str) -> Optional[str]:
    """Primera tabla del FROM de la CTE (WITH CTE AS (SELECT ... FROM #Saldo) → #Saldo)."""
    definicion = re.search(rf"(?:\bWITH|,)\s*{re.escape(nombre)}\s*(?:\([^)]*\))?\s+AS\s*\(", limpio, re.IGNORECASE)
    if not definicion:
        return None
    nivel, fin = 1, len(limpio)
    for i in range(definicion.end(), len(limpio)):
        nivel += {"(": 1, ")": -1}.get(limpio[i], 0)
        if nivel == 0:
            fin = i
            break
    tabla = re.search(rf"\bFROM\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})",
                      limpio[definicion.end():fin], re.IGNORECASE)
    return tabla.group(1).strip() if tabla else None


def _nombres_cte(limpio: str) -> Set[str]:
    """Nombres definidos con WITH nombre AS (...): no son tablas físicas."""
    return {
        nombre.lower()
        for nombre in re.findall(
            r"(?:\bWITH|,)\s*([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s+AS\s*\(", limpio, re.IGNORECASE
        )
    }


def _validar_nolock(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        rf"\b(FROM|JOIN)\s+({_IDENTIFICADOR}(?:\s*\.(?:\s*\.)?\s*{_IDENTIFICADOR}){{0,2}})(?![\w$#.\]])",
        re.IGNORECASE,
    )
    ctes = _nombres_cte(limpio)
    for match in patron.finditer(limpio):
        # Función de tabla o subconsulta (nombre seguido de "(" que no es un hint).
        if re.match(r"\s*\((?!\s*(?:NOLOCK|READUNCOMMITTED)\b)", limpio[match.end():], re.IGNORECASE):
            continue
        tabla = _nombre_tabla(match)
        tiene_nolock = bool(_ALIAS_Y_NOLOCK.match(limpio, match.end()))
        if _es_temporal(tabla):
            if tiene_nolock:
                hallazgos.append(_hallazgo(
                    texto,
                    match.start(2),
                    "NOLOCK_EN_TABLA_TEMPORAL",
                    f"Se identificó que la tabla temporal {tabla} tiene WITH(NOLOCK). Se recomienda retirarlo, "
                    f"ya que la tabla temporal solo existe en la sesión del reporte y no genera bloqueos con otros procesos.",
                ))
            continue
        if (tabla.strip("[]").lower() in ctes or re.match(_CATALOGOS_PROHIBIDOS, tabla, re.IGNORECASE)
                or _esta_en_update(limpio, match.start())):
            continue
        if not tiene_nolock:
            hallazgo = _hallazgo(texto, match.start(2), "TABLA_FISICA_SIN_NOLOCK", _mensaje_sin_nolock([tabla]))
            hallazgo.elemento = tabla
            hallazgos.append(hallazgo)
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE):
        # MAXRECURSION tampoco se permite, pero va con su propio título.
        es_maxrecursion = "MAXRECURSION" in match.group(0).upper()
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "MAXRECURSION_PROHIBIDO" if es_maxrecursion else "HINT_PLAN_PROHIBIDO",
            f"Se identificó el uso de '{match.group(0)}', que le indica al motor de base de datos cómo ejecutar "
            f"la consulta. Se recomienda retirarlo, ya que no está permitido forzar al motor y es el optimizador "
            f"quien decide el mejor plan de ejecución.",
        ))
    return hallazgos


def _validar_hints_bloqueo(texto: str, sin_comentarios: str) -> List[Hallazgo]:
    """UPDLOCK, HOLDLOCK, TABLOCK...: en un reporte bloquean a los procesos que registran operaciones."""
    hallazgos = []
    for match in _PATRON_BLOQUEO.finditer(sin_comentarios):
        # Solo dentro del paréntesis de hints de una tabla: WITH (NOLOCK, UPDLOCK) o (UPDLOCK).
        abre = sin_comentarios.rfind("(", 0, match.start())
        previo = sin_comentarios[abre + 1:match.start()] if abre >= 0 else None
        if previo is None or not re.fullmatch(r"[\sA-Za-z,]*", previo):
            continue
        if any(palabra.upper() not in _HINTS_DE_TABLA for palabra in re.findall(r"[A-Za-z]+", previo)):
            continue
        grupo = 1
        hint = match.group(grupo).upper()
        if hint == "READPAST":
            accion = ("Se recomienda retirarlo y usar WITH(NOLOCK), ya que el reporte podría dejar fuera "
                      "registros sin avisar.")
        else:
            accion = ("Se recomienda retirarlo y usar WITH(NOLOCK), ya que un reporte solo consulta datos y "
                      "bloquear filas detiene a los procesos que están registrando operaciones.")
        hallazgos.append(_hallazgo(
            texto, match.start(grupo), "HINT_BLOQUEO_PROHIBIDO",
            f"Se identificó el uso de '{hint}', que {_HINTS_BLOQUEO[hint]}. {accion}",
        ))
    return hallazgos


def _validar_comentarios_codigo(texto: str) -> List[Hallazgo]:
    hallazgos = []
    patrones = [
        re.compile(rf"^\s*--\s*(?:{_PALABRAS_SQL_COMENTADAS})\b", re.IGNORECASE | re.MULTILINE),
        re.compile(rf"/\*\s*(?:{_PALABRAS_SQL_COMENTADAS})\b.*?\*/", re.IGNORECASE | re.DOTALL),
    ]
    posiciones: Set[int] = set()
    procedimiento = nombre_del_procedimiento(texto)
    for patron in patrones:
        for match in patron.finditer(texto):
            if match.start() in posiciones:
                continue
            posiciones.add(match.start())
            # Variables de prueba comentadas (--DECLARE @dFecha DATE = '...') o el EXEC de ejemplo.
            if es_bloque_de_prueba(texto, match.start(), procedimiento):
                continue
            hallazgos.append(_hallazgo(
                texto,
                match.start(),
                "CODIGO_SQL_COMENTADO",
                "Se identificó código SQL comentado dentro del procedimiento. Se recomienda eliminarlo si ya no se "
                "usa, ya que dificulta la lectura y el mantenimiento del reporte.",
            ))
    return hallazgos


def _validar_tablas_temporales(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(rf"\bCREATE\s+TABLE\s+({_IDENTIFICADOR})\s*\(", re.IGNORECASE)
    for tabla_match in patron.finditer(limpio):
        tabla = tabla_match.group(1)
        if not _es_temporal(tabla):
            continue
        inicio = tabla_match.end()
        profundidad = 0
        fin = len(limpio)
        for indice in range(inicio, len(limpio)):
            if limpio[indice] == "(":
                profundidad += 1
            elif limpio[indice] == ")":
                if profundidad == 0:
                    fin = indice
                    break
                profundidad -= 1
        bloque = limpio[inicio:fin]
        for columna in re.finditer(rf"\b({_IDENTIFICADOR})\s+({_TIPOS_TEXTO})(?:\s*\([^)]*\))?[^,]*", bloque, re.IGNORECASE):
            if not re.search(r"\bCOLLATE\s+\w+", columna.group(0), re.IGNORECASE):
                hallazgos.append(_hallazgo(
                    texto,
                    inicio + columna.start(),
                    "TEMPORAL_TEXTO_SIN_COLLATE",
                    f"Se identificó que la columna {columna.group(1)} de la tabla temporal {tabla} no tiene COLLATE. "
                    f"Se recomienda añadir el COLLATE de la empresa, ya que sin él puede fallar al compararla con "
                    f"columnas de otras tablas "
                    f"(ej.: {columna.group(1)} VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS).",
                ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    reglas = [
        (
            r"(?is)\b(?P<pos>SELECT)\b(?:(?!\b(?:SELECT|INSERT|MERGE|OUTPUT|FROM|UPDATE|DELETE)\b|;).)*?"
            r"\bINTO\s+(?P<tabla>[#\w\[\].]+)",
            "SELECT_INTO_PROHIBIDO",
            lambda m: (
                f"Se identificó el uso de SELECT INTO para crear la tabla "
                f"{'temporal ' if m.group('tabla').startswith('#') else ''}{m.group('tabla')}. Se recomienda "
                f"definir su estructura mediante CREATE TABLE e insertar los datos posteriormente con INSERT INTO."
            ),
        ),
        (
            rf"\bSELECT\s+(?:ALL\s+|DISTINCT\s+)?(?:TOP\s*(?:\(\s*[\w@]+\s*\)|\d+)\s*(?:PERCENT\s+)?(?:WITH\s+TIES\s+)?)?"
            rf"\*(?:\s+INTO\s+[#\w\[\].]+)?(?:\s+FROM\s+(?P<tabla>{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})(?P<funcion>\s*\()?)?",
            "SELECT_ESTRELLA_PROHIBIDO",
            lambda m: _mensaje_select_estrella(m.group("tabla"), bool(m.group("funcion"))),
        ),
        (
            r"(?<![\w.])(?P<alias>[A-Za-z_]\w*)\s*\.\s*\*(?=\s*(?:,|\bFROM\b))",
            "SELECT_ESTRELLA_PROHIBIDO",
            lambda m: _mensaje_select_estrella(_tabla_del_alias_en(limpio, m.start(), m.group("alias")), False, f"{m.group('alias')}.*"),
        ),
        (
            # IN (SELECT ...) es una subconsulta: puede devolver varias filas, no es un solo valor.
            r"(?P<no>\bNOT\s+)?\bIN\s*\((?!\s*(?:SELECT|WITH)\b)\s*(?P<valor>[^,()]+?)\s*\)",
            "IN_CON_UN_SOLO_VALOR",
            lambda m: (
                f"Se identificó el uso de {'NOT IN' if m.group('no') else 'IN'} para comparar un único valor. "
                f"Se recomienda utilizar el operador {'<>' if m.group('no') else '='} cuando se compara un solo "
                f"valor (ej.: WHERE {_columna_antes(limpio, m.start())} {'<>' if m.group('no') else '='} "
                f"{texto[m.start('valor'):m.end('valor')]})."
            ),
        ),
        (
            _CATALOGOS_PROHIBIDOS,
            "CATALOGO_SISTEMA_PROHIBIDO",
            lambda m: (
                f"Se identificó una consulta a tablas internas de SQL Server ({m.group(0)}). Se recomienda "
                f"consultar solo tablas del negocio, ya que en los reportes no está permitido acceder a las "
                f"tablas internas del motor."
            ),
        ),
    ]
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            # SELECT * sobre sys.objects...: ya lo marca «Catálogo de sistema prohibido».
            if regla == "SELECT_ESTRELLA_PROHIBIDO" and "tabla" in match.re.groupindex and match.group("tabla") \
                    and re.match(_CATALOGOS_PROHIBIDOS, match.group("tabla"), re.IGNORECASE):
                continue
            # Si el patrón marca con "pos" el elemento que causa el hallazgo, la línea es la suya.
            posicion = match.start("pos") if "pos" in match.re.groupindex else match.start()
            hallazgo = _hallazgo(texto, posicion, regla, mensaje(match))
            # Para agrupar: la tabla (o función) a la que se refiere.
            if regla == "SELECT_INTO_PROHIBIDO":
                hallazgo.elemento = match.group("tabla")
            elif regla == "SELECT_ESTRELLA_PROHIBIDO":
                hallazgo.elemento = _objeto_select_estrella(match, limpio)
            hallazgos.append(hallazgo)
    return hallazgos


def _columna_antes(limpio: str, posicion: int) -> str:
    """Columna que se compara con IN (c.cEstado IN (...)); nEstado si no se reconoce."""
    columna = re.search(r"([\w\[\].@]+)\s+(?:NOT\s+)?$", limpio[:posicion], re.IGNORECASE)
    if columna and columna.group(1).upper() not in {"WHERE", "AND", "OR", "ON", "WHEN", "NOT"}:
        return columna.group(1)
    return "nEstado"


def _objeto_select_estrella(match: re.Match, limpio: str) -> str:
    if "alias" in match.re.groupindex:
        return f"tabla {_tabla_del_alias_en(limpio, match.start(), match.group('alias'))}"
    if match.group("tabla"):
        return f"{'función' if match.group('funcion') else 'tabla'} {match.group('tabla')}"
    return "consulta sin tabla identificada"


def _mensaje_select_estrella(objeto: Optional[str], es_funcion: bool, forma: str = "SELECT *") -> str:
    """Texto de la usuaria: «Se identificó el uso de SELECT * sobre la tabla …»."""
    if not objeto:
        problema = (f"Se identificó el uso de {forma}, que obtiene todas las columnas de la consulta, aunque no "
                    f"todas sean necesarias.")
    elif es_funcion:
        problema = (f"Se identificó el uso de {forma} sobre la función {objeto}, que obtiene todas las columnas "
                    f"que devuelve, aunque no todas sean necesarias.")
    else:
        problema = (f"Se identificó el uso de {forma} sobre la tabla {objeto}, que obtiene todas las columnas de "
                    f"la tabla, aunque no todas sean necesarias.")
    return (f"{problema} Se recomienda especificar únicamente las columnas requeridas para evitar la lectura de "
            f"datos innecesarios y mejorar el rendimiento de la consulta.")


def _validar_modificaciones_fisicas(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        rf"\b(UPDATE|INSERT(?:\s+INTO)?|DELETE(?:\s+FROM)?|MERGE(?:\s+INTO)?|TRUNCATE\s+TABLE)\s+"
        rf"(?!(?:INTO|FROM|SET|JOIN|STATISTICS)\b)({_IDENTIFICADOR}(?:\s*\.(?:\s*\.)?\s*{_IDENTIFICADOR}){{0,2}})",
        re.IGNORECASE,
    )
    ctes = _nombres_cte(limpio)
    for match in patron.finditer(limpio):
        tabla = match.group(2).strip()
        if "." not in tabla and not _es_temporal(tabla):
            # UPDATE c ... FROM dbo.Cliente c: el objetivo es el alias de una tabla del FROM de esa sentencia.
            tabla = _tabla_del_alias_en(limpio, match.end(), tabla)
        if tabla.lower() in ctes:
            # UPDATE de una CTE: se modifica la tabla de la que sale la CTE.
            base = _tabla_de_la_cte(limpio, tabla)
            if base is None or _es_temporal(base):
                continue
            tabla = f"{base} (mediante la CTE {tabla})"
        if not _es_temporal(tabla):
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "MODIFICACION_TABLA_FISICA",
                f"Se identificó que el reporte modifica la tabla {tabla} con {' '.join(match.group(1).upper().split())}. "
                f"Se recomienda mover ese cambio a un procedimiento de negocio, ya que un reporte solo debe "
                f"consultar datos y no alterar la información.",
            ))
    return hallazgos


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (_SQL_DINAMICO, "SQL_DINAMICO_PROHIBIDO",
         "Se identificó una consulta armada como texto y ejecutada con EXEC o sp_executesql. Se recomienda "
         "escribir la consulta directamente y usar parámetros, ya que el SQL dinámico no está permitido por "
         "seguridad y expone el reporte a inyección SQL."),
        (r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", "VARBINARY_DOCUMENTO_IDENTIFICADO",
         "Se identificó el uso de VARBINARY, un tipo de dato para guardar archivos o documentos. Se recomienda "
         "no usarlo, ya que la base de datos es solo para datos transaccionales y los documentos se gestionan "
         "en una solución externa (se guarda solo su ruta)."),
    )
    hallazgos = []
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos


def _sentencia(limpio: str, posicion: int) -> str:
    """Sentencia que contiene la posición (entre ';' o GO)."""
    inicio = max(limpio.rfind(";", 0, posicion), limpio.upper().rfind("GO\n", 0, posicion)) + 1
    fin = limpio.find(";", posicion)
    return limpio[inicio:fin if fin >= 0 else len(limpio)]


def _validar_collate_openjson(texto: str, limpio: str) -> List[Hallazgo]:
    """COLLATE en las columnas del WITH de OPENJSON: sobra, toman el COLLATE de la base de datos."""
    return [
        _hallazgo(texto, posicion, "OPENJSON_COLLATE_INNECESARIO", mensaje_collate_openjson(columnas))
        for posicion, columnas in collates_en_openjson(limpio)
    ]


def _validar_drop_table_if_exists(texto: str) -> List[Hallazgo]:
    """IF OBJECT_ID('tempdb..#T') IS NOT NULL DROP TABLE #T: se escribe DROP TABLE IF EXISTS #T."""
    casos = validaciones_antes_de_drop(texto)
    if not casos:
        return []
    lineas = [_linea(texto, posicion) for posicion, _, _ in casos]
    hallazgo = _hallazgo(texto, casos[0][0], "DROP_TABLE_CON_VALIDACION", mensaje_drop_if_exists(casos))
    if len(casos) > 1:
        hallazgo.lineas = sorted(set(lineas))  # para recorrerlas con la barra «1 de N»
    return [hallazgo]


def _validar_varchar_max(texto: str, limpio: str) -> List[Hallazgo]:
    """VARCHAR(MAX) solo se permite para guardar JSON o XML, o una lista que se separa con STRING_SPLIT."""
    hallazgos = []
    for match in re.finditer(r"\bN?VARCHAR\s*\(\s*MAX\s*\)", limpio, re.IGNORECASE):
        declarado = re.search(r"(@?[A-Za-z_]\w*)\s+(?:AS\s+)?$", limpio[:match.start()])
        nombre = declarado.group(1) if declarado and declarado.group(1).upper() not in {"AS", "CAST", "CONVERT"} else None
        if nombre:
            usos = re.finditer(rf"(?<![\w@]){re.escape(nombre)}\b", limpio, re.IGNORECASE)
            es_json_xml = re.search(r"json|xml", nombre, re.IGNORECASE) or any(
                _USO_JSON_XML.search(_sentencia(limpio, uso.start())) for uso in usos
            )
            # Una lista que se separa con STRING_SPLIT (ej.: '205,307,312,...') puede ser larga: ahí se justifica.
            es_lista = re.search(rf"\bSTRING_SPLIT\s*\(\s*{re.escape(nombre)}\b", limpio, re.IGNORECASE)
        else:
            es_json_xml = _USO_JSON_XML.search(_sentencia(limpio, match.start()))
            es_lista = None
        if es_json_xml or es_lista:
            continue
        tipo = " ".join(match.group(0).upper().split()).replace("( ", "(").replace(" )", ")")
        sujeto = f"que {nombre} se declara como {tipo}" if nombre else f"el uso de {tipo}"
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARCHAR_MAX_PROHIBIDO",
            f"Se identificó {sujeto} y no guarda JSON ni XML. Se recomienda definir un tamaño fijo, ya que "
            f"{tipo} solo se permite para JSON o XML y consume más memoria (ej.: {tipo.replace('MAX', '500')}).",
        ))
    return hallazgos


def _es_creacion_de_procedimiento(limpio: str) -> bool:
    """True si el script crea el procedimiento (CREATE PROCEDURE); False si es un ALTER."""
    return bool(re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\b", limpio, re.IGNORECASE))


def _validar_control_de_flujo(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    # WHILE: solo en procedimientos nuevos; en un ALTER se respeta la lógica existente.
    if _es_creacion_de_procedimiento(limpio):
        for match in re.finditer(r"\bWHILE\b", limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(
                texto, match.start(), "WHILE_PROHIBIDO",
                "Se identificó un WHILE en un procedimiento nuevo. Se recomienda resolverlo con una sola "
                "consulta que trabaje con todos los registros a la vez, ya que el WHILE procesa uno por uno, "
                "vuelve lento el reporte y puede quedar en un bucle infinito.",
            ))
    for match in re.finditer(r"\bRAISERROR\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "RAISERROR_USAR_THROW",
            "Se identificó el uso de RAISERROR para gestionar excepciones. Se recomienda emplear THROW como "
            "alternativa moderna para el manejo de errores.",
        ))
    for match in re.finditer(r"\bWAITFOR\s+(?:DELAY|TIME)\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            "Se identificó un WAITFOR, que obliga al motor de base de datos a pausar la ejecución. Se recomienda "
            "retirarlo, ya que no está permitido forzar al motor y la pausa retrasa el reporte sin necesidad.",
        ))
    return hallazgos


_BEGIN_TRAN = re.compile(r"\bBEGIN\s+TRAN(?:SACTION)?\b", re.IGNORECASE)
_CIERRE_TRAN = re.compile(r"\b(?:COMMIT|ROLLBACK)(?:\s+(?:TRAN(?:SACTION)?|WORK))?\b", re.IGNORECASE)


def _validar_transacciones(texto: str, limpio: str) -> List[Hallazgo]:
    """Toda transacción abierta necesita su COMMIT (o ROLLBACK); si no, sus bloqueos no se liberan."""
    hallazgos = []
    inicios = list(_BEGIN_TRAN.finditer(limpio))
    cierres = len(_CIERRE_TRAN.findall(limpio))
    # Los BEGIN que sobran (los últimos) son los que quedan sin cerrar.
    for match in inicios[cierres:] if cierres < len(inicios) else []:
        hallazgos.append(_hallazgo(
            texto, match.start(), "TRANSACCION_SIN_CIERRE",
            "Se identificó un BEGIN TRANSACTION sin su COMMIT o ROLLBACK. Se recomienda cerrar la "
            "transacción con COMMIT (y ROLLBACK si ocurre un error), ya que una transacción abierta deja "
            "las tablas bloqueadas para los demás procesos.",
        ))
    return hallazgos


# Acción estándar pegada a la finalidad sin "_": SelEjecucionesDetalle, ConsultarDatos.
_ACCION_PEGADA = re.compile(
    r"(Sel|Upd|Ins|Del|Consultar|Actualizar|Insertar|Eliminar|Select|Update|Insert|Delete)([A-Z]\w*)$"
)
_ABREVIATURA_ACCION = {
    "sel": "Sel", "upd": "Upd", "ins": "Ins", "del": "Del",
    "consultar": "Sel", "select": "Sel", "actualizar": "Upd", "update": "Upd",
    "insertar": "Ins", "insert": "Ins", "eliminar": "Del", "delete": "Del",
}


_ACCIONES_ESTANDAR = {"sel", "upd", "ins", "del"}


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


def _validar_accion_del_nombre(texto: str, limpio: str) -> List[Hallazgo]:
    """
    Al crear el reporte, el nombre empieza con PA_ e indica la acción (Sel, Upd,
    Ins o Del), separada con "_". En un ALTER no se revisa: el objeto ya existe.
    """
    match = re.search(
        rf"\bCREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})",
        limpio, re.IGNORECASE,
    )
    if not match:
        return []
    nombre = match.group(1).split(".")[-1].strip().strip("[]")
    segmentos = nombre.split("_")
    hallazgos = []
    tiene_prefijo = segmentos[0].upper() == "PA"
    resto = segmentos[1:] if tiene_prefijo else segmentos
    if not tiene_prefijo:
        hallazgos.append(_hallazgo(
            texto, match.start(1), "PROCEDIMIENTO_SIN_PREFIJO_PA",
            f"Se identificó que el procedimiento {nombre} no empieza con el prefijo PA_. Se recomienda "
            f"añadirlo, ya que así se identifica que el objeto es un procedimiento almacenado "
            f"(ej.: PA_{nombre}).",
        ))
    pegada = _hallazgo_accion_pegada(texto, match.start(1), nombre, ["PA"] + resto)
    if pegada:
        hallazgos.append(pegada)
    elif not any(segmento.lower() in _ACCIONES_ESTANDAR for segmento in resto):
        # Para el ejemplo, la acción va después del primer segmento (la tabla o el módulo).
        sugerido = "_".join(["PA"] + resto[:1] + ["Sel"] + resto[1:])
        hallazgos.append(_hallazgo(
            texto, match.start(1), "PROCEDIMIENTO_SIN_ACCION",
            f"Se identificó que el nombre {nombre} no indica la acción del procedimiento (Sel, Upd, Ins o "
            f"Del). Se recomienda añadirla, ya que así se sabe qué hace el procedimiento "
            f"(ej.: {sugerido}).",
        ))
    return hallazgos


def _validar_esquema_procedimiento(texto: str, limpio: str) -> List[Hallazgo]:
    """El procedimiento del reporte indica su esquema, tanto al crearlo como al modificarlo."""
    match = re.search(
        rf"\b(CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})",
        limpio, re.IGNORECASE,
    )
    if not match or "." in match.group(2):
        return []
    nombre = match.group(2).strip("[]")
    return [_hallazgo(
        texto, match.start(2), "PROCEDIMIENTO_SIN_ESQUEMA",
        f"Se identificó que el procedimiento {nombre} no tiene declarado un esquema. Se recomienda añadir el "
        f"esquema; si es dbo, definirlo explícitamente, ya que así se evita crear o modificar un objeto "
        f"equivocado (ej.: dbo.{nombre}).",
    )]


def _validar_esquema_entre_bases(texto: str, limpio: str) -> List[Hallazgo]:
    """Base..Tabla omite el esquema: entre bases se escribe Base.Esquema.Tabla."""
    hallazgos = []
    patron = re.compile(r"(\[[^\]]+\]|[A-Za-z_][\w$#]*)\s*\.\s*\.\s*(\[[^\]]+\]|[A-Za-z_][\w$#]*)")
    for match in patron.finditer(limpio):
        base, tabla = match.group(1).strip("[]"), match.group(2).strip("[]")
        anterior = re.search(r"(\w+)\s*$", limpio[:match.start()])
        uso = "una unión con" if anterior and anterior.group(1).upper() == "JOIN" else "el uso de"
        hallazgos.append(_hallazgo(
            texto, match.start(), "ESQUEMA_OMITIDO_ENTRE_BASES",
            f"Se identificó {uso} la tabla {tabla} de la base {base}, pero el esquema se omitió "
            f"({base}..{tabla}). Se recomienda definir el esquema, ya que así se evita apuntar a una "
            f"tabla equivocada (ej.: {base}.dbo.{tabla}).",
        ))
    return hallazgos


def _validar_order_by_numerico(texto: str, limpio: str) -> List[Hallazgo]:
    """ORDER BY 1, 2: se ordena por posición de columna en vez de por su nombre."""
    hallazgos = []
    for inicio, posiciones in order_by_por_posicion(limpio):
        hallazgos.append(_hallazgo(
            texto, inicio, "ORDER_BY_NUMERICO_PROHIBIDO",
            f"Se identificó un ordenamiento por posición de columna (ORDER BY {', '.join(posiciones)}). "
            f"Se recomienda escribir el nombre de las columnas, ya que si cambia el SELECT el orden "
            f"cambiaría sin notarlo (ej.: ORDER BY cNombre).",
        ))
    return hallazgos


# Cláusulas que abren una parte de la consulta; la última antes de COLLATE
# indica si está en una condición (WHERE, ON, HAVING) o en otra parte.
_CLAUSULAS = re.compile(
    r"\b(WHERE|ON|HAVING|SELECT|FROM|JOIN|GROUP|ORDER|SET|VALUES|TABLE|DECLARE|RETURNS)\b",
    re.IGNORECASE,
)


def _sin_parentesis_cerrados(texto: str) -> str:
    """El texto con el contenido de los paréntesis ya cerrados en blanco (subconsultas, funciones)."""
    caracteres, abiertos = list(texto), []
    for indice, caracter in enumerate(texto):
        if caracter == "(":
            abiertos.append(indice)
        elif caracter == ")" and abiertos:
            inicio = abiertos.pop()
            caracteres[inicio + 1:indice] = " " * (indice - inicio - 1)
    return "".join(caracteres)


def _validar_collate_en_condiciones(texto: str, limpio: str) -> List[Hallazgo]:
    """COLLATE no se permite en las condiciones del WHERE ni del JOIN."""
    hallazgos = []
    for match in re.finditer(r"\bCOLLATE\s+\w+", limpio, re.IGNORECASE):
        # Una subconsulta ya cerrada antes del COLLATE (WHERE a IN (SELECT … FROM …) AND c COLLATE …)
        # no cambia la cláusula en la que está.
        previo = _sin_parentesis_cerrados(limpio[:match.start()])
        clausulas = _CLAUSULAS.findall(previo[previo.rfind(";") + 1:])
        ultima = clausulas[-1].upper() if clausulas else ""
        if ultima not in {"WHERE", "ON", "HAVING"}:
            continue
        donde = "del JOIN" if ultima == "ON" else f"del {ultima}"
        hallazgos.append(_hallazgo(
            texto, match.start(), "COLLATE_EN_PREDICADO",
            f"Se identificó un COLLATE en la condición {donde}. Se recomienda definir el COLLATE al crear la "
            f"tabla y no en la condición, ya que en el WHERE o en el JOIN impide usar los índices y vuelve "
            f"lenta la consulta.",
        ))
    return hallazgos


def _validar_funciones_reemplazables(texto: str, limpio: str) -> List[Hallazgo]:
    """Funciones con una alternativa nativa mejor: TRIM, STRING_AGG y STRING_SPLIT."""
    hallazgos = []
    for match in re.finditer(r"\b(?:LTRIM\s*\(\s*RTRIM|RTRIM\s*\(\s*LTRIM)\s*\(", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "LTRIM_RTRIM_PROHIBIDO",
            "Se identificó el uso de LTRIM(RTRIM(...)) para eliminar espacios al inicio y al final de una cadena. "
            "Se recomienda reemplazarlo por TRIM, que realiza la misma operación con una sola función "
            "(ej.: TRIM(cNombre)).",
        ))
    for match in re.finditer(r"\bFOR\s+XML\s+PATH\s*\(\s*(?:''|\"\")\s*\)", limpio, re.IGNORECASE):
        con_stuff = re.search(r"\bSTUFF\s*\(", _sentencia(limpio, match.start()), re.IGNORECASE)
        forma = "FOR XML PATH y STUFF" if con_stuff else "FOR XML PATH"
        inicio = limpio.rfind(";", 0, match.start()) + 1
        stuff_previos = list(re.finditer(r"\bSTUFF\s*\(", limpio[inicio:match.start()], re.IGNORECASE))
        posicion = inicio + stuff_previos[-1].start() if stuff_previos else match.start()
        hallazgos.append(_hallazgo(
            texto, posicion, "STUFF_FOR_XML_PATH_PROHIBIDO",
            f"Se identificó una concatenación de valores con {forma}. Se recomienda usar STRING_AGG, ya que "
            f"une los valores con su separador de forma más simple y legible (ej.: STRING_AGG(cNombre, ',')).",
        ))
    for match in re.finditer(r"(?:\b\w+\s*\.\s*)?\bfn_split\s*\(", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "FN_SPLIT_PROHIBIDO",
            "Se identificó el uso de la función fn_Split para dividir un texto. Se recomienda usar "
            "STRING_SPLIT, ya que es nativa de SQL Server y mejora el rendimiento "
            "(ej.: SELECT value FROM STRING_SPLIT('Juan,Pedro', ',')).",
        ))
    return hallazgos


def _validar_variables(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    declaraciones: Dict[str, int] = {}
    for match in re.finditer(r"\bDECLARE\s+(@[A-Za-z_]\w*)", limpio, re.IGNORECASE):
        if match.group(1).lower() not in {nombre.lower() for nombre in declaraciones}:
            declaraciones[match.group(1)] = match.start(1)
    for variable, posicion in declaraciones.items():
        usos = len(re.findall(rf"(?<![\w]){re.escape(variable)}\b", limpio[posicion + len(variable):], re.IGNORECASE))
        if usos == 0:
            hallazgos.append(_hallazgo(
                texto,
                posicion,
                "VARIABLE_DECLARADA_SIN_USO",
                f"Se identificó que la variable {variable} se declara pero no se usa en el procedimiento. "
                f"Se recomienda eliminarla, ya que solo ocupa espacio y dificulta la lectura del código.",
            ))
    return hallazgos


# Reglas que, repetidas, se resumen por elemento (tabla, función): «dbo.Cliente (líneas 9, 12)».
_PLANTILLAS_AGRUPADAS = {
    "SELECT_ESTRELLA_PROHIBIDO": (
        "usos de SELECT *",
        "Se recomienda especificar únicamente las columnas requeridas para evitar la lectura de datos "
        "innecesarios y mejorar el rendimiento de la consulta.",
    ),
    "SELECT_INTO_PROHIBIDO": (
        "tablas creadas con SELECT INTO",
        "Se recomienda definir su estructura mediante CREATE TABLE e insertar los datos posteriormente con "
        "INSERT INTO.",
    ),
}


def _mensaje_sin_nolock(tablas: List[str]) -> str:
    """Texto de la usuaria; con varias tablas, una sola frase: «las tablas dbo.Cliente y dbo.Agencia»."""
    if len(tablas) == 1:
        return (f"Se identificó que la tabla {tablas[0]} no utiliza WITH (NOLOCK). Se recomienda añadir WITH (NOLOCK) "
                f"para reducir la posibilidad de bloqueos durante la lectura de datos mientras otros procesos "
                f"realizan operaciones sobre la tabla.")
    lista = f"{', '.join(tablas[:-1])} y {tablas[-1]}"
    return (f"Se identificó que las tablas {lista} no utilizan WITH (NOLOCK). Se recomienda añadir WITH (NOLOCK) "
            f"para reducir la posibilidad de bloqueos durante la lectura de datos mientras otros procesos "
            f"realizan operaciones sobre las tablas.")


def _agrupar_sin_nolock(grupo: List[Hallazgo]) -> Hallazgo:
    """Todas las tablas sin NOLOCK en una sola observación; las líneas van en el encabezado."""
    ordenados = sorted(grupo, key=lambda h: h.linea)
    tablas = list({h.elemento.lower(): h.elemento for h in ordenados}.values())
    resumen = Hallazgo(
        linea=ordenados[0].linea,
        origen=ordenados[0].origen,
        severidad=ordenados[0].severidad,
        regla="TABLA_FISICA_SIN_NOLOCK",
        mensaje=_mensaje_sin_nolock(tablas),
    )
    resumen.lineas = sorted({h.linea for h in grupo})
    return resumen


def _agrupar_por_elemento(regla: str, grupo: List[Hallazgo]) -> Hallazgo:
    sustantivo, accion = _PLANTILLAS_AGRUPADAS[regla]
    lineas_por_elemento: Dict[str, List[int]] = {}
    for hallazgo in sorted(grupo, key=lambda h: h.linea):
        lineas_por_elemento.setdefault(hallazgo.elemento, []).append(hallazgo.linea)
    elementos = [
        f"{elemento} ({'línea' if len(set(lineas)) == 1 else 'líneas'} {', '.join(map(str, sorted(set(lineas))))})"
        for elemento, lineas in lineas_por_elemento.items()
    ]
    numeros = sorted({hallazgo.linea for hallazgo in grupo})
    lineas = ("la línea " if len(numeros) == 1 else "las líneas ") + ", ".join(map(str, numeros))
    resumen = Hallazgo(
        linea=numeros[0],
        origen=grupo[0].origen,
        severidad=grupo[0].severidad,
        regla=regla,
        mensaje=f"Se identificaron {len(grupo)} {sustantivo}, en {lineas}: {'; '.join(elementos)}. {accion}",
    )
    resumen.lineas = numeros  # para recorrer los casos uno a uno desde «Ver en el código»
    return resumen


def _agrupar_hallazgos_repetidos(hallazgos: List[Hallazgo]) -> List[Hallazgo]:
    """Resume observaciones repetidas de cualquier regla."""
    grupos: Dict[str, List[Hallazgo]] = {}
    orden: List[str] = []
    for hallazgo in hallazgos:
        if hallazgo.regla not in grupos:
            grupos[hallazgo.regla] = []
            orden.append(hallazgo.regla)
        grupos[hallazgo.regla].append(hallazgo)

    resumidos: List[Hallazgo] = []
    for regla in orden:
        grupo = grupos[regla]
        if len(grupo) == 1:
            resumidos.append(grupo[0])
            continue
        if regla == "TABLA_FISICA_SIN_NOLOCK":
            resumidos.append(_agrupar_sin_nolock(grupo))
            continue
        if regla in _PLANTILLAS_AGRUPADAS and all(getattr(h, "elemento", None) for h in grupo):
            resumidos.append(_agrupar_por_elemento(regla, grupo))
            continue

        numeros = sorted({hallazgo.linea for hallazgo in grupo})
        lineas = ("la línea " if len(numeros) == 1 else "las líneas ") + ", ".join(map(str, numeros))
        # Cada mensaje es "qué pasa. Qué hacer.": se listan los hechos y la acción
        # se dice una sola vez (la del primero; solo cambia el ejemplo).
        partes = [re.split(r"(?<=\.)\s+|, por lo que (?=se recomienda)", h.mensaje, maxsplit=1) for h in grupo]
        partes = [[p[0], p[1][:1].upper() + p[1][1:]] if len(p) == 2 else p for p in partes]
        if all(len(p) == 2 for p in partes):
            hechos = list(dict.fromkeys(p[0][:1].lower() + p[0][1:].rstrip(".") for p in partes))
            detalles = ["; ".join(hechos) + ".", partes[0][1]]
        else:
            detalles = list(dict.fromkeys(h.mensaje for h in grupo))
        resumen = Hallazgo(
            linea=grupo[0].linea,
            origen=grupo[0].origen,
            severidad=grupo[0].severidad,
            regla=regla,
            mensaje=(
                f"Se encontraron {len(grupo)} observaciones de este tipo, en {lineas}: "
                f"{' '.join(detalles)}"
            ),
        )
        resumen.lineas = numeros  # para recorrer los casos uno a uno desde «Ver en el código»
        resumidos.append(resumen)
    return resumidos


def verificar_reporte(texto_sql: str) -> List[Hallazgo]:
    """Aplica las reglas específicas de procedimientos almacenados de reportes."""
    limpio = _quitar_comentarios(texto_sql)
    hallazgos: List[Hallazgo] = []
    hallazgos.extend(_validar_nolock(texto_sql, limpio))
    sin_comentarios = _quitar_comentarios(texto_sql, vaciar_textos=False)
    hallazgos.extend(_validar_hints(texto_sql, sin_comentarios))
    hallazgos.extend(_validar_hints_bloqueo(texto_sql, sin_comentarios))
    hallazgos.extend(_validar_comentarios_codigo(texto_sql))
    hallazgos.extend(_validar_tablas_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_varchar_max(texto_sql, limpio))
    hallazgos.extend(_validar_drop_table_if_exists(texto_sql))
    hallazgos.extend(_validar_collate_openjson(texto_sql, limpio))
    hallazgos.extend(_validar_control_de_flujo(texto_sql, limpio))
    hallazgos.extend(_validar_transacciones(texto_sql, limpio))
    hallazgos.extend(_validar_esquema_procedimiento(texto_sql, limpio))
    hallazgos.extend(_validar_accion_del_nombre(texto_sql, limpio))
    hallazgos.extend(_validar_esquema_entre_bases(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_collate_en_condiciones(texto_sql, limpio))
    hallazgos.extend(_validar_funciones_reemplazables(texto_sql, limpio))
    hallazgos.extend(_validar_modificaciones_fisicas(texto_sql, limpio))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_REPORTES[h.regla].activo]
    return _agrupar_hallazgos_repetidos(hallazgos)