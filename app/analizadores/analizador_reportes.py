# -*- coding: utf-8 -*-
"""Reglas de buenas practicas para procedimientos almacenados de reportes."""

import re
from typing import Dict, List, Set, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_HINTS_PROHIBIDOS = (
    r"FORCESEEK|FORCESCAN|RECOMPILE|HOLDLOCK|NOEXPAND|INDEX\s*\(|"
    r"LOOP\s+JOIN|HASH\s+JOIN|MERGE\s+JOIN|OPTIMIZE\s+FOR|MAXDOP\s*\(|FAST\s+\d+"
)
_CATALOGOS_PROHIBIDOS = r"(?:sys|information_schema)\.[A-Za-z_][\w$]*"
_PALABRAS_SQL_COMENTADAS = r"SELECT|INSERT|UPDATE|DELETE|MERGE|EXEC(?:UTE)?|DECLARE|CREATE|ALTER|DROP"


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
                    f"La tabla temporal {tabla} no debe usar WITH(NOLOCK).",
                ))
            continue
        if _esta_en_update(limpio, match.start()):
            continue
        if not re.match(r"\s+WITH\s*\(\s*NOLOCK\s*\)", limpio[match.end():], re.IGNORECASE):
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "TABLA_FISICA_SIN_NOLOCK",
                f"La tabla física {tabla} debe utilizar WITH(NOLOCK) en este reporte.",
            ))
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "HINT_PLAN_PROHIBIDO",
            f"El comando o hint '{match.group(0)}' fuerza el plan del motor y no debe usarse en un reporte.",
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
                "Se encontro una sentencia SQL comentada. Elimine codigo comentado que no aporte al reporte.",
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
                    f"La columna {columna.group(1)} de la tabla temporal {tabla} debe tener COLLATE.",
                ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    reglas = [
        (
            r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b",
            "SELECT_INTO_PROHIBIDO",
            "No se permite SELECT INTO; declare la tabla temporal y luego use INSERT INTO.",
        ),
        (r"\bSELECT\s+(?:DISTINCT\s+)?\*", "SELECT_ESTRELLA_PROHIBIDO", "No se permite SELECT *; indique explícitamente las columnas requeridas."),
        (r"\bIN\s*\(\s*[^,()]+\s*\)", "IN_CON_UN_SOLO_VALOR", "No use IN con un único valor; utilice el operador =."),
        (_CATALOGOS_PROHIBIDOS, "CATALOGO_SISTEMA_PROHIBIDO", "Los reportes no deben consultar sys.objects ni catálogos del sistema."),
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
                f"Un procedimiento de reporte no debe modificar la tabla física {tabla}.",
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
                f"La variable {variable} fue declarada pero no se utiliza en el reporte.",
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
        detalles = []
        for hallazgo in grupo:
            if hallazgo.mensaje not in detalles:
                detalles.append(hallazgo.mensaje)
        resumidos.append(Hallazgo(
            linea=grupo[0].linea,
            origen=grupo[0].origen,
            severidad=grupo[0].severidad,
            regla=regla,
            mensaje=(
                f"Se identificaron {len(grupo)} observaciones de la regla {regla}. "
                f"Revise las líneas {lineas}. "
                f"Detalles: {' | '.join(detalles)}"
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
    hallazgos.extend(_validar_modificaciones_fisicas(texto_sql, limpio))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    return _agrupar_hallazgos_repetidos(hallazgos)