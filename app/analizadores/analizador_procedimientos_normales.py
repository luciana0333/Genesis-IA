# -*- coding: utf-8 -*-
"""Reglas para procedimientos almacenados normales, fuera de reportes."""

import re
from typing import Dict, List, Set

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_HINTS_PROHIBIDOS = (
    r"FORCESEEK|FORCESCAN|RECOMPILE|NOEXPAND|HOLDLOCK|INDEX\s*\(|"
    r"LOOP\s+JOIN|HASH\s+JOIN|MERGE\s+JOIN|OPTIMIZE\s+FOR|MAXDOP\s*\(|FAST\s+\d+|"
    r"OPTION\s*\([^)]*\)"
)
_PALABRAS_SQL_COMENTADAS = r"SELECT|INSERT|UPDATE|DELETE|MERGE|EXEC(?:UTE)?|DECLARE|CREATE|ALTER|DROP|WHILE|GOTO"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_CATALOGO_SISTEMA = r"\bsys\s*\.\s*[A-Za-z_][\w$]*"
_SQL_DINAMICO = r"\b(?:sp_executesql\b|EXEC(?:UTE)?\s*(?:\(\s*)?(?:N?['\"]|@))"


def _linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    return Hallazgo(
        linea=_linea(texto, posicion),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad.ALTO,
        regla=regla,
        mensaje=mensaje,
    )


def _quitar_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), texto, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", lambda m: " " * len(m.group(0)), texto)


def _es_temporal(nombre: str) -> bool:
    return nombre.strip("[]").startswith("#")


def _validar_control_flujo(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for patron, regla, mensaje in (
        (r"\bWHILE\b", "WHILE_PROHIBIDO", "El procedimiento usa un bucle WHILE, que no está permitido: repite el mismo proceso registro por registro y, con muchos datos, se vuelve muy lento. Reemplace el bucle por una sola consulta que trabaje con todos los registros a la vez; por ejemplo, en lugar de recorrer los clientes uno por uno para sumar sus saldos, use SELECT nClienteId, SUM(nSaldo) FROM dbo.Cuenta GROUP BY nClienteId."),
        (r"\bGOTO\b", "GOTO_PROHIBIDO", "Se usa GOTO, que está prohibido porque vuelve difícil de seguir el código. Use IF/ELSE o TRY/CATCH."),
        (r"\bMERGE\b", "MERGE_PROHIBIDO", "Se usa MERGE, que está prohibido. Reemplácelo por sentencias INSERT, UPDATE y DELETE separadas."),
    ):
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    return [
        _hallazgo(
            texto,
            match.start(),
            "HINT_PLAN_PROHIBIDO",
            f"Se usa la instrucción '{match.group(0)}', que obliga a SQL Server a seguir un plan fijo. Quítela "
            f"y deje que el motor elija el mejor plan.",
        )
        for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE)
    ]


def _tiene_nolock_despues(texto: str, posicion: int) -> bool:
    restante = texto[posicion:]
    return bool(re.search(r"(?:\s+AS\s+)?(?:[A-Za-z_@#][\w$#]*\s+)?WITH\s*\(\s*NOLOCK\s*\)", restante, re.IGNORECASE))


def _validar_update_from_nolock(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        rf"\bFROM\s+({_IDENTIFICADOR})(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}",
        re.IGNORECASE,
    )
    for match in patron.finditer(limpio):
        inicio_sentencia = max(limpio.rfind(";", 0, match.start()), limpio.rfind("BEGIN", 0, match.start())) + 1
        prefijo = limpio[inicio_sentencia:match.start()]
        if not re.search(r"\bUPDATE\b", prefijo, re.IGNORECASE):
            continue
        nombre = match.group(1)
        if _tiene_nolock_despues(limpio, match.end()):
            hallazgos.append(_hallazgo(
                texto,
                match.start(1),
                "NOLOCK_EN_TABLA_FISICA",
                f"La tabla {nombre} usa WITH(NOLOCK) dentro de un UPDATE. Quítelo: al modificar datos no se deben leer datos sin confirmar.",
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
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "NOLOCK_EN_TABLA_TEMPORAL",
                f"La tabla temporal {nombre} usa WITH(NOLOCK), que no aplica a temporales. Quite el WITH(NOLOCK).",
            ))
    return hallazgos


def _validar_order_by_numerico(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bORDER\s+BY\s+\d+(?:\s*,\s*\d+)*", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "ORDER_BY_NUMERICO_PROHIBIDO",
            "Se ordena por número de columna (ORDER BY 1, 2...). Escriba el nombre de la columna: si cambia el SELECT, el orden no se altera por error.",
        ))
    return hallazgos


def _validar_cast_en_join(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        r"\bJOIN\b.*?\bON\b(?:(?!\bJOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|;).)*CAST\s*\(",
        re.IGNORECASE | re.DOTALL,
    )
    for match in patron.finditer(limpio):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "CAST_EN_JOIN_PROHIBIDO",
            "Se usa CAST dentro de la condición del JOIN, lo que impide usar los índices. Convierta el dato antes (en una temporal o variable) o use columnas del mismo tipo.",
        ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b", "SELECT_INTO_PROHIBIDO", "Se usa SELECT INTO, que está prohibido. Cree primero la tabla temporal con CREATE TABLE (con sus tipos y COLLATE) y luego llénela con INSERT INTO ... SELECT."),
        (r"\bSELECT\s+(?:DISTINCT\s+)?\*", "SELECT_ESTRELLA_PROHIBIDO", "Se usa SELECT *, que está prohibido. Escriba solo las columnas que necesita."),
        (r"\b(?:WHERE|ON)\b[^;\n]*(?:COLLATE\s+\w+)", "COLLATE_EN_PREDICADO", "Se usa COLLATE en el WHERE o JOIN, lo que impide usar los índices. Defina el COLLATE en las columnas de la tabla temporal."),
        (r"\bSTUFF\s*\([\s\S]*?\bFOR\s+XML\s+PATH\b", "STUFF_FOR_XML_PATH_PROHIBIDO", "Se concatena con STUFF y FOR XML PATH. Use STRING_AGG, que es más simple y rápido."),
        (r"\b(?:dbo\.)?FN_SPLIT\s*\(", "FN_SPLIT_PROHIBIDO", "Se usa dbo.FN_SPLIT para separar textos. Use la función nativa STRING_SPLIT."),
        (r"\bLTRIM\s*\([\s\S]*?\bRTRIM\s*\(", "LTRIM_RTRIM_PROHIBIDO", "Se usa LTRIM(RTRIM(...)) para quitar espacios. Use TRIM(...), que hace lo mismo en una sola función."),
    )
    hallazgos = []
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos


def _validar_collate_temporales(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(r"\bCREATE\s+TABLE\s+(#[A-Za-z_]\w*)\s*\((.*?)\)", re.IGNORECASE | re.DOTALL)
    for match in patron.finditer(limpio):
        tabla = match.group(1)
        bloque = match.group(2)
        for columna in re.finditer(rf"\b({_IDENTIFICADOR})\s+({_TIPOS_TEXTO})(?:\s*\([^)]*\))?[^,]*", bloque, re.IGNORECASE):
            if not re.search(r"\bCOLLATE\s+\w+", columna.group(0), re.IGNORECASE):
                hallazgos.append(_hallazgo(
                    texto,
                    match.start(2) + columna.start(),
                    "TEMPORAL_TEXTO_SIN_COLLATE",
                    f"La columna de texto {columna.group(1)} de la tabla temporal {tabla} no define COLLATE. Agréguelo (ej.: VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS) para evitar conflictos al compararla con otras tablas.",
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
                hallazgos.append(_hallazgo(texto, match.start(), "CODIGO_SQL_COMENTADO", "Hay código SQL comentado. Elimínelo si ya no se usa: el historial de cambios queda en el control de versiones."))
    return hallazgos


def _validar_variables(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    declaraciones: Dict[str, int] = {}
    for match in re.finditer(r"\bDECLARE\s+(@[A-Za-z_]\w*)", limpio, re.IGNORECASE):
        declaraciones[match.group(1).lower()] = match.start(1)
    for variable, posicion in declaraciones.items():
        if not re.search(rf"(?<![\w]){re.escape(variable)}\b", limpio[posicion + len(variable):], re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, posicion, "VARIABLE_DECLARADA_SIN_USO", f"La variable {variable} se declara pero nunca se usa. Elimínela."))
    return hallazgos


def verificar_procedimiento_normal(texto_sql: str) -> List[Hallazgo]:
    """Aplica exclusivamente las reglas de procedimientos normales."""
    limpio = _quitar_comentarios(texto_sql)
    hallazgos: List[Hallazgo] = []
    hallazgos.extend(_validar_control_flujo(texto_sql, limpio))
    hallazgos.extend(_validar_hints(texto_sql, limpio))
    hallazgos.extend(_validar_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_update_from_nolock(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_cast_en_join(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_collate_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_comentarios(texto_sql))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    return hallazgos


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (_CATALOGO_SISTEMA, "CATALOGO_SISTEMA_PROHIBIDO", "Se consultan tablas del sistema (sys), que está prohibido. Consulte solo las tablas del negocio."),
        (_SQL_DINAMICO, "SQL_DINAMICO_PROHIBIDO", "Se ejecuta SQL dinámico (EXEC o sp_executesql), que está prohibido. Escriba la consulta de forma directa, usando parámetros para los filtros."),
        (r"\bN?VARCHAR\s*\(\s*MAX\s*\)", "VARCHAR_MAX_PROHIBIDO", "Se usa VARCHAR(MAX), que está prohibido: reserva memoria de más y vuelve lentas las consultas. Defina una longitud acorde al dato (ej.: VARCHAR(500))."),
        (r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", "VARBINARY_DOCUMENTO_IDENTIFICADO", "Se usa VARBINARY, un tipo para guardar archivos o documentos. Confirme que es necesario: lo recomendado es guardar el archivo fuera de la base de datos y manejar solo su ruta."),
    )
    hallazgos = []
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos