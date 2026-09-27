# -*- coding: utf-8 -*-
"""Reglas de buenas prácticas para procedimientos almacenados de reportes."""

import re
from typing import Dict, List, Set, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_reportes import REGLAS_REPORTES


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_HINTS_PROHIBIDOS = (
    r"FORCESEEK|FORCESCAN|RECOMPILE|HOLDLOCK|NOEXPAND|INDEX\s*\(|"
    r"LOOP\s+JOIN|HASH\s+JOIN|MERGE\s+JOIN|OPTIMIZE\s+FOR|MAXDOP\s*\(|FAST\s+\d+"
)
_CATALOGOS_PROHIBIDOS = r"(?:sys|information_schema)\.[A-Za-z_][\w$]*"
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


def _quitar_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), texto, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", lambda m: " " * len(m.group(0)), texto)


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


def _validar_nolock(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(
        rf"\b(FROM|JOIN)\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})(?!\s*\()",
        re.IGNORECASE,
    )
    for match in patron.finditer(limpio):
        tabla = _nombre_tabla(match)
        if _es_temporal(tabla):
            if re.match(r"\s*WITH\s*\(\s*NOLOCK\s*\)", limpio[match.end():], re.IGNORECASE):
                hallazgos.append(_hallazgo(
                    texto,
                    match.start(2),
                    "NOLOCK_EN_TABLA_TEMPORAL",
                    f"La tabla temporal {tabla} usa WITH(NOLOCK), que no aplica a temporales. Quite el WITH(NOLOCK).",
                ))
            continue
        if _esta_en_update(limpio, match.start()):
            continue
        if not re.match(r"\s+WITH\s*\(\s*NOLOCK\s*\)", limpio[match.end():], re.IGNORECASE):
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "TABLA_FISICA_SIN_NOLOCK",
                f"La tabla {tabla} se consulta sin WITH(NOLOCK). En un reporte agregue WITH(NOLOCK) después del nombre de la tabla para no bloquear las operaciones del sistema.",
            ))
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "HINT_PLAN_PROHIBIDO",
            f"Se usa la instrucción '{match.group(0)}', que obliga a SQL Server a seguir un plan fijo. Quítela "
            f"y deje que el motor elija el mejor plan.",
        ))
    return hallazgos


def _validar_comentarios_codigo(texto: str) -> List[Hallazgo]:
    hallazgos = []
    patrones = [
        re.compile(rf"^\s*--\s*(?:{_PALABRAS_SQL_COMENTADAS})\b", re.IGNORECASE | re.MULTILINE),
        re.compile(rf"/\*\s*(?:{_PALABRAS_SQL_COMENTADAS})\b.*?\*/", re.IGNORECASE | re.DOTALL),
    ]
    posiciones: Set[int] = set()
    for patron in patrones:
        for match in patron.finditer(texto):
            if match.start() in posiciones:
                continue
            posiciones.add(match.start())
            hallazgos.append(_hallazgo(
                texto,
                match.start(),
                "CODIGO_SQL_COMENTADO",
                "Hay código SQL comentado. Elimínelo si ya no se usa: el historial de cambios queda en el control de versiones.",
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
                    f"La columna de texto {columna.group(1)} de la tabla temporal {tabla} no define COLLATE. Agréguelo (ej.: VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS) para evitar conflictos al compararla con otras tablas.",
                ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    reglas = [
        (
            r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b",
            "SELECT_INTO_PROHIBIDO",
            "Se usa SELECT INTO, que está prohibido. Cree primero la tabla temporal con CREATE TABLE (con sus tipos y COLLATE) y luego llénela con INSERT INTO ... SELECT.",
        ),
        (r"\bSELECT\s+(?:DISTINCT\s+)?\*", "SELECT_ESTRELLA_PROHIBIDO", "Se usa SELECT *, que está prohibido. Escriba solo las columnas que el reporte necesita."),
        (r"\bIN\s*\(\s*[^,()]+\s*\)", "IN_CON_UN_SOLO_VALOR", "Se usa IN con un solo valor. Reemplácelo por el operador = (ej.: WHERE nEstado = 1)."),
        (_CATALOGOS_PROHIBIDOS, "CATALOGO_SISTEMA_PROHIBIDO", "El reporte consulta tablas del sistema (sys o information_schema), que está prohibido. Consulte solo las tablas del negocio."),
    ]
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos


def _validar_modificaciones_fisicas(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(rf"\b(UPDATE|INSERT\s+INTO|DELETE\s+FROM|MERGE\s+INTO)\s+({_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}})", re.IGNORECASE)
    for match in patron.finditer(limpio):
        tabla = match.group(2).strip()
        if not _es_temporal(tabla):
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "MODIFICACION_TABLA_FISICA",
                f"El reporte modifica la tabla {tabla}. Un reporte solo debe leer datos: mueva el INSERT, UPDATE o DELETE a un procedimiento transaccional.",
            ))
    return hallazgos


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (_SQL_DINAMICO, "SQL_DINAMICO_PROHIBIDO", "Se ejecuta SQL dinámico (EXEC o sp_executesql), que está prohibido. Escriba la consulta de forma directa, usando parámetros para los filtros."),
        (r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", "VARBINARY_DOCUMENTO_IDENTIFICADO", "Se usa VARBINARY, un tipo para guardar archivos o documentos. Confirme que es necesario: lo recomendado es guardar el archivo fuera de la base de datos y manejar solo su ruta."),
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


def _validar_varchar_max(texto: str, limpio: str) -> List[Hallazgo]:
    """VARCHAR(MAX) solo se permite para guardar JSON o XML."""
    hallazgos = []
    for match in re.finditer(r"\bN?VARCHAR\s*\(\s*MAX\s*\)", limpio, re.IGNORECASE):
        declarado = re.search(r"(@?[A-Za-z_]\w*)\s+(?:AS\s+)?$", limpio[:match.start()])
        nombre = declarado.group(1) if declarado and declarado.group(1).upper() not in {"AS", "CAST", "CONVERT"} else None
        if nombre:
            usos = re.finditer(rf"(?<![\w@]){re.escape(nombre)}\b", limpio, re.IGNORECASE)
            es_json_xml = re.search(r"json|xml", nombre, re.IGNORECASE) or any(
                _USO_JSON_XML.search(_sentencia(limpio, uso.start())) for uso in usos
            )
        else:
            es_json_xml = _USO_JSON_XML.search(_sentencia(limpio, match.start()))
        if es_json_xml:
            continue
        referencia = f"en {nombre} " if nombre else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARCHAR_MAX_PROHIBIDO",
            f"Se usa VARCHAR(MAX) {referencia}y no se identifica que guarde JSON o XML. Defina una "
            f"longitud acorde al dato (ej.: VARCHAR(500)); VARCHAR(MAX) solo se permite para JSON o XML.",
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
                "El procedimiento nuevo usa WHILE, que no se permite: procesar fila por fila es lento. "
                "Resuélvalo con una sola consulta sobre todo el conjunto (INSERT/UPDATE con JOIN).",
            ))
    for match in re.finditer(r"\bRAISERROR\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "RAISERROR_USAR_THROW",
            "Se usa RAISERROR para lanzar errores. Se recomienda THROW, que es la forma actual: "
            "conserva el número y la línea del error original (ej.: THROW 50001, 'Mensaje', 1;).",
        ))
    for match in re.finditer(r"\bWAITFOR\s+(?:DELAY|TIME)\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            "Se usa WAITFOR para pausar la ejecución, lo que retrasa el reporte y mantiene recursos "
            "ocupados sin necesidad. Quite la espera.",
        ))
    return hallazgos


def _validar_variables(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    declaraciones: Dict[str, int] = {}
    for match in re.finditer(r"\bDECLARE\s+(@[A-Za-z_]\w*)", limpio, re.IGNORECASE):
        declaraciones[match.group(1).lower()] = match.start(1)
    for variable, posicion in declaraciones.items():
        usos = len(re.findall(rf"(?<![\w]){re.escape(variable)}\b", limpio[posicion + len(variable):], re.IGNORECASE))
        if usos == 0:
            hallazgos.append(_hallazgo(
                texto,
                posicion,
                "VARIABLE_DECLARADA_SIN_USO",
                f"La variable {variable} se declara pero nunca se usa. Elimínela.",
            ))
    return hallazgos


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

        lineas = ", ".join(str(hallazgo.linea) for hallazgo in grupo)
        # Cada mensaje es "qué pasa. Qué hacer.": si todos piden lo mismo, la
        # acción se dice una sola vez al final.
        partes = [re.split(r"(?<=\.)\s+", h.mensaje, maxsplit=1) for h in grupo]
        acciones = {p[1] for p in partes if len(p) == 2}
        if len(acciones) == 1 and all(len(p) == 2 for p in partes):
            hechos = list(dict.fromkeys(p[0][:1].lower() + p[0][1:].rstrip(".") for p in partes))
            detalles = ["; ".join(hechos) + ".", acciones.pop()]
        else:
            detalles = list(dict.fromkeys(h.mensaje for h in grupo))
        resumidos.append(Hallazgo(
            linea=grupo[0].linea,
            origen=grupo[0].origen,
            severidad=grupo[0].severidad,
            regla=regla,
            mensaje=(
                f"Se encontraron {len(grupo)} observaciones de este tipo, en las líneas {lineas}: "
                f"{' '.join(detalles)}"
            ),
        ))
    return resumidos


def verificar_reporte(texto_sql: str) -> List[Hallazgo]:
    """Aplica las reglas específicas de procedimientos almacenados de reportes."""
    limpio = _quitar_comentarios(texto_sql)
    hallazgos: List[Hallazgo] = []
    hallazgos.extend(_validar_nolock(texto_sql, limpio))
    hallazgos.extend(_validar_hints(texto_sql, limpio))
    hallazgos.extend(_validar_comentarios_codigo(texto_sql))
    hallazgos.extend(_validar_tablas_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_varchar_max(texto_sql, limpio))
    hallazgos.extend(_validar_control_de_flujo(texto_sql, limpio))
    hallazgos.extend(_validar_modificaciones_fisicas(texto_sql, limpio))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_REPORTES[h.regla].activo]
    return _agrupar_hallazgos_repetidos(hallazgos)