# -*- coding: utf-8 -*-
"""Reglas para procedimientos almacenados normales, fuera de reportes."""

import re
from typing import Dict, List, Set

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_procedimientos_normales import REGLAS_PROCEDIMIENTOS_NORMALES


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
    """Hallazgo con la severidad definida en el catálogo de procedimientos."""
    return Hallazgo(
        linea=_linea(texto, posicion),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_PROCEDIMIENTOS_NORMALES[regla].severidad),
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
        (r"\bWHILE\b", "WHILE_PROHIBIDO", "Se identificó un bucle WHILE en el procedimiento. Evaluar otras formas de resolverlo sin WHILE (por ejemplo, una sola consulta que trabaje con todos los registros), ya que procesa los registros uno por uno, vuelve lento el procedimiento y puede quedar en un bucle infinito."),
        (r"\bGOTO\b", "GOTO_PROHIBIDO", "Se identificó una instrucción GOTO, que salta a otra parte del código y hace difícil seguir su lógica. Reemplazarla por estructuras IF/ELSE o por un bloque TRY/CATCH, ya que así el flujo del procedimiento queda claro y fácil de mantener."),
        (r"\bMERGE\b", "MERGE_PROHIBIDO", "Se identificó una sentencia MERGE, que inserta, actualiza y elimina en una sola instrucción. Reemplazarla por sentencias INSERT, UPDATE y DELETE separadas, ya que MERGE tiene errores conocidos en SQL Server y dificulta controlar cada operación."),
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
            f"Se identificó la instrucción '{match.group(0)}', que le indica al motor de base de datos cómo "
            f"ejecutar la consulta. Retirar la instrucción, ya que no está permitido forzar al motor y se debe "
            f"dejar que el optimizador decida el mejor plan.",
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
                f"La tabla {nombre} usa WITH(NOLOCK) dentro de un UPDATE. Retirar el WITH(NOLOCK) de esa tabla, "
                f"ya que al modificar datos no se deben leer datos que aún no están confirmados.",
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
                f"La tabla temporal {nombre} usa WITH(NOLOCK). Retirar el WITH(NOLOCK), ya que en las tablas "
                f"temporales no es necesario: solo las usa este procedimiento.",
            ))
    return hallazgos


def _validar_order_by_numerico(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bORDER\s+BY\s+\d+(?:\s*,\s*\d+)*", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "ORDER_BY_NUMERICO_PROHIBIDO",
            "Se identificó un ORDER BY por posición de columna (por ejemplo, ORDER BY 1). Se recomienda "
            "escribir el nombre de la columna, ya que si cambia el SELECT el orden cambiaría sin notarlo "
            "(ej.: ORDER BY cNombre).",
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
            "Se identificó un CAST dentro de la condición del JOIN. Convertir el dato antes del JOIN (en una "
            "tabla temporal o variable) o unir columnas del mismo tipo, ya que el CAST en la condición impide "
            "usar los índices y vuelve lenta la consulta.",
        ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b", "SELECT_INTO_PROHIBIDO", "Se identificó una tabla temporal creada con SELECT INTO. Crear primero la tabla con CREATE TABLE, indicando sus tipos y COLLATE, y luego llenarla con INSERT INTO seguido del SELECT, ya que así se controlan sus tipos de datos."),
        (r"\bSELECT\s+(?:DISTINCT\s+)?\*", "SELECT_ESTRELLA_PROHIBIDO", "Se identificó un SELECT *, que trae todas las columnas de la tabla. Se recomienda escribir solo las columnas necesarias, ya que traer columnas de más consume memoria y vuelve más lento el procedimiento (ej.: SELECT cNombre, dFecha)."),
        (r"\b(?:WHERE|ON)\b[^;\n]*(?:COLLATE\s+\w+)", "COLLATE_EN_PREDICADO", "Se identificó COLLATE en una condición del WHERE o del JOIN. Definir el COLLATE al crear la tabla temporal y no en la condición, ya que en el WHERE o en el JOIN impide usar los índices y vuelve lenta la consulta."),
        (r"\bSTUFF\s*\([\s\S]*?\bFOR\s+XML\s+PATH\b", "STUFF_FOR_XML_PATH_PROHIBIDO", "Se identificó una concatenación con STUFF y FOR XML PATH. Reemplazarla por STRING_AGG, ya que es la función nativa para concatenar valores y es más simple y rápida (ej.: STRING_AGG(cNombre, ','))."),
        (r"\b(?:dbo\.)?FN_SPLIT\s*\(", "FN_SPLIT_PROHIBIDO", "Se identificó la función dbo.FN_SPLIT para dividir textos. Reemplazarla por STRING_SPLIT, ya que es la función nativa de SQL Server y mejora el rendimiento (ej.: SELECT value FROM STRING_SPLIT('Juan,Pedro', ','))."),
        (r"\bLTRIM\s*\([\s\S]*?\bRTRIM\s*\(", "LTRIM_RTRIM_PROHIBIDO", "Se identificó la combinación de LTRIM y RTRIM para quitar espacios. Se recomienda usar TRIM, ya que hace lo mismo en una sola función (ej.: TRIM(cNombre))."),
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
                    f"La columna de texto {columna.group(1)} de la tabla temporal {tabla} no define COLLATE. Añadir "
                    f"COLLATE a la columna, ya que sin él puede fallar al compararla con columnas de otras tablas "
                    f"(ej.: {columna.group(1)} VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS).",
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
                hallazgos.append(_hallazgo(texto, match.start(), "CODIGO_SQL_COMENTADO", "Se identificó código SQL comentado, es decir, sentencias que ya no se ejecutan. Se recomienda "
                "eliminarlo si ya no se usa, ya que dificulta la lectura del procedimiento y el historial de "
                "cambios queda en el control de versiones."))
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
            hallazgos.append(_hallazgo(texto, posicion, "VARIABLE_DECLARADA_SIN_USO", f"La variable {variable} se declara pero no se usa en ninguna parte del procedimiento. Se recomienda "
                f"eliminar su declaración, ya que solo ocupa espacio y confunde a quien lee el código."))
    return hallazgos


# Acciones estándar del manual: la palabra completa se abrevia.
_ACCIONES_ABREVIADAS = {
    "consultar": "Sel", "consulta": "Sel", "select": "Sel", "seleccionar": "Sel",
    "actualizar": "Upd", "actualiza": "Upd", "update": "Upd",
    "insertar": "Ins", "inserta": "Ins", "insert": "Ins",
    "eliminar": "Del", "elimina": "Del", "delete": "Del", "borrar": "Del",
}
_EJEMPLO_NOMBRE = "PA_Cliente_Sel_PorDocumento"


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
            f"El procedimiento {nombre} no indica su esquema. Anteponer el esquema al nombre, ya que "
            f"así se evita crear o modificar un objeto equivocado (ej.: dbo.{nombre}).",
        ))

    # En un ALTER el procedimiento ya existe: su nombre no se puede cambiar.
    if match.group(1).upper() != "CREATE":
        return hallazgos

    segmentos = nombre.split("_")
    if segmentos[0] != "PA":
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_SIN_PREFIJO_PA",
            f"El nombre del procedimiento {nombre} no empieza con PA_. Usar el formato "
            f"PA_Tabla_Acción_Finalidad, ya que PA identifica a los procedimientos almacenados "
            f"(ej.: {_EJEMPLO_NOMBRE}).",
        ))
        return hallazgos

    if len(segmentos) < 3 or not all(segmentos[1:3]):
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            f"El nombre del procedimiento {nombre} no indica la tabla y la acción. Usar el formato "
            f"PA_Tabla_Acción_Finalidad, ya que así se entiende qué hace el procedimiento "
            f"(ej.: {_EJEMPLO_NOMBRE}).",
        ))
        return hallazgos

    accion = segmentos[2]
    abreviatura = _ACCIONES_ABREVIADAS.get(accion.lower())
    if abreviatura and accion != abreviatura:
        sugerido = "_".join(segmentos[:2] + [abreviatura] + segmentos[3:])
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
            f"La acción del procedimiento {nombre} está escrita como '{accion}'. Usar la abreviatura "
            f"del manual, {abreviatura}, ya que así se nombran las acciones estándar (ej.: {sugerido}).",
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
    """VARCHAR(MAX) solo se permite para guardar JSON o XML."""
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
        donde = f" en {nombre}" if nombre else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARCHAR_MAX_PROHIBIDO",
            f"Se identificó un tipo de dato VARCHAR(MAX){donde} que no guarda JSON ni XML. Se recomienda "
            f"definir una longitud acorde al dato (ej.: VARCHAR(500)), ya que VARCHAR(MAX) reserva más "
            f"memoria de la necesaria y vuelve lentas las consultas.",
        ))
    return hallazgos


def verificar_procedimiento_normal(texto_sql: str) -> List[Hallazgo]:
    """Aplica exclusivamente las reglas de procedimientos normales."""
    limpio = _quitar_comentarios(texto_sql)
    hallazgos: List[Hallazgo] = []
    hallazgos.extend(_validar_nombre_procedimiento(texto_sql, limpio))
    hallazgos.extend(_validar_control_flujo(texto_sql, limpio))
    hallazgos.extend(_validar_hints(texto_sql, limpio))
    hallazgos.extend(_validar_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_update_from_nolock(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_cast_en_join(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_varchar_max(texto_sql, limpio))
    hallazgos.extend(_validar_collate_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_comentarios(texto_sql))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_PROCEDIMIENTOS_NORMALES[h.regla].activo]
    return _agrupar_repetidos(hallazgos)


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (_CATALOGO_SISTEMA, "CATALOGO_SISTEMA_PROHIBIDO", "Se identificó una consulta a tablas internas de SQL Server (sys). Consultar solo las tablas del negocio, ya que un procedimiento no debe depender de las tablas internas del motor."),
        (_SQL_DINAMICO, "SQL_DINAMICO_PROHIBIDO", "Se identificó una consulta armada como texto y ejecutada con EXEC o sp_executesql (SQL dinámico). Escribir la consulta directamente y usar parámetros para los filtros, ya que el SQL dinámico es difícil de revisar y puede permitir ataques de inyección de SQL."),
        (r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", "VARBINARY_DOCUMENTO_IDENTIFICADO", "Se identificó un tipo de dato VARBINARY, que guarda archivos dentro de la base de datos. Se recomienda evaluar si es necesario, ya que lo ideal es guardar el archivo fuera de la base de datos y registrar solo su ruta."),
    )
    hallazgos = []
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos