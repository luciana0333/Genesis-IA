# -*- coding: utf-8 -*-
"""Reglas de buenas prácticas para procedimientos almacenados de reportes."""

import re
from typing import Dict, List, Set, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_reportes import REGLAS_REPORTES


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_HINTS_PROHIBIDOS = (
    r"\bOPTION\s*\([^)]*\)|\bDBCC\b|\bFORCESEEK\b|\bFORCESCAN\b|\bFORCE\s+ORDER\b|\bRECOMPILE\b|"
    r"\bNOEXPAND\b|\bHOLDLOCK\b|\bTABLOCKX?\b|\bUPDLOCK\b|\bXLOCK\b|\bROWLOCK\b|\bPAGLOCK\b|"
    r"\bREADPAST\b|\bINDEX\s*\(|\b(?:LOOP|HASH|MERGE)\s+JOIN\b|\bOPTIMIZE\s+FOR\b|\bMAXDOP\b|"
    r"\bFAST\s+\d+|\bUSE\s+PLAN\b|\bKEEP(?:FIXED)?\s+PLAN\b|\bQUERYTRACEON\b"
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
                    f"La tabla temporal {tabla} tiene WITH(NOLOCK). Retirar el WITH(NOLOCK) de la tabla temporal, ya que en las tablas temporales no es necesario.",
                ))
            continue
        if (tabla.strip("[]").lower() in ctes or re.match(_CATALOGOS_PROHIBIDOS, tabla, re.IGNORECASE)
                or _esta_en_update(limpio, match.start())):
            continue
        if not tiene_nolock:
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "TABLA_FISICA_SIN_NOLOCK",
                f"La tabla {tabla} no tiene WITH(NOLOCK). Añadir WITH(NOLOCK) a la tabla, ya que en los reportes "
                f"se usa para evitar bloqueos (ej.: dbo.Cliente c WITH(NOLOCK)).",
            ))
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "HINT_PLAN_PROHIBIDO",
            f"Se usa '{match.group(0)}', que le indica al motor de base de datos cómo ejecutar la consulta. "
            f"No está permitido emplear sintaxis que fuerce al motor; se debe dejar que el optimizador "
            f"decida el mejor plan.",
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
                "Hay código SQL comentado. Se recomienda eliminarlo si ya no se usa, ya que dificulta la lectura del procedimiento.",
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
                    f"La columna {columna.group(1)} de la temporal {tabla} no tiene COLLATE. Añadir COLLATE a la columna, "
                    f"ya que sin él puede fallar al compararla con otras tablas "
                    f"(ej.: {columna.group(1)} VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS).",
                ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    reglas = [
        (
            r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b",
            "SELECT_INTO_PROHIBIDO",
            "Se crea una tabla temporal con SELECT INTO. Crear primero la tabla con CREATE TABLE y luego "
            "llenarla con INSERT INTO seguido del SELECT, ya que así se controlan sus tipos de datos.",
        ),
        (r"\bSELECT\s+(?:DISTINCT\s+)?\*", "SELECT_ESTRELLA_PROHIBIDO", "Se usa SELECT *. Se recomienda escribir solo las columnas necesarias, ya que traer todas vuelve más lento el reporte (ej.: SELECT cNombre, dFecha)."),
        (r"\bIN\s*\(\s*[^,()]+\s*\)", "IN_CON_UN_SOLO_VALOR", "Se usa IN con un solo valor. Se recomienda usar el signo igual, ya que es más claro y directo (ej.: WHERE nEstado = 1)."),
        (_CATALOGOS_PROHIBIDOS, "CATALOGO_SISTEMA_PROHIBIDO", "Se consultan tablas internas de SQL Server (sys o information_schema). Consultar solo tablas del negocio, ya que en los reportes no está permitido acceder a tablas internas."),
    ]
    for patron, regla, mensaje in reglas:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            hallazgos.append(_hallazgo(texto, match.start(), regla, mensaje))
    return hallazgos


def _validar_modificaciones_fisicas(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    patron = re.compile(rf"\b(UPDATE|INSERT\s+INTO|DELETE\s+FROM|MERGE\s+INTO)\s+({_IDENTIFICADOR}(?:\s*\.(?:\s*\.)?\s*{_IDENTIFICADOR}){{0,2}})", re.IGNORECASE)
    for match in patron.finditer(limpio):
        tabla = match.group(2).strip()
        if not _es_temporal(tabla):
            hallazgos.append(_hallazgo(
                texto,
                match.start(2),
                "MODIFICACION_TABLA_FISICA",
                f"El reporte modifica la tabla {tabla}. Mover ese cambio a un procedimiento transaccional, "
                f"ya que un reporte solo debe consultar datos.",
            ))
    return hallazgos


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (_SQL_DINAMICO, "SQL_DINAMICO_PROHIBIDO", "Se ejecuta una consulta armada como texto (EXEC o sp_executesql). Escribir la consulta directamente y usar parámetros, ya que el SQL dinámico no está permitido por seguridad."),
        (r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", "VARBINARY_DOCUMENTO_IDENTIFICADO", "Se usa VARBINARY. Se recomienda evaluar si es necesario, ya que guarda archivos dentro de la base de datos; lo ideal es guardar solo la ruta del archivo."),
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
        sujeto = f"{nombre} es VARCHAR(MAX)" if nombre else "Se usa VARCHAR(MAX)"
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARCHAR_MAX_PROHIBIDO",
            f"{sujeto} y no guarda JSON ni XML. Definir un tamaño fijo (ej.: VARCHAR(500)), "
            f"ya que VARCHAR(MAX) solo se permite para JSON o XML.",
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
                "El procedimiento nuevo usa WHILE. Evaluar otras formas de resolverlo sin WHILE "
                "(por ejemplo, una sola consulta que trabaje con todos los registros), ya que procesa "
                "uno por uno, vuelve lento el reporte y puede quedar en un bucle infinito.",
            ))
    for match in re.finditer(r"\bRAISERROR\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "RAISERROR_USAR_THROW",
            "Se usa RAISERROR para mostrar errores. Se recomienda usar THROW, ya que es la forma "
            "actual de manejar errores (ej.: THROW 50001, 'No existe el cliente', 1;).",
        ))
    for match in re.finditer(r"\bWAITFOR\s+(?:DELAY|TIME)\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            "Se usa WAITFOR, que fuerza al motor de base de datos a pausar la ejecución. No está permitido "
            "emplear sintaxis que fuerce al motor; se debe retirar la pausa.",
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
            f"La tabla {base}..{tabla} no indica el esquema. Escribir base, esquema y tabla, "
            f"ya que así se evita apuntar a una tabla equivocada (ej.: {base}.dbo.{tabla}).",
        ))
    return hallazgos


# Fin de la lista de un ORDER BY: fin de sentencia, paréntesis o cláusula siguiente.
_FIN_ORDER_BY = re.compile(
    r";|\)|\b(?:OFFSET|FOR|OPTION|UNION|EXCEPT|INTERSECT|END|SELECT|INSERT|UPDATE|DELETE|RETURN|GO)\b",
    re.IGNORECASE,
)


def _validar_order_by_numerico(texto: str, limpio: str) -> List[Hallazgo]:
    """ORDER BY 1, 2: se ordena por posición de columna en vez de por su nombre."""
    hallazgos = []
    for match in re.finditer(r"\bORDER\s+BY\b", limpio, re.IGNORECASE):
        resto = limpio[match.end():]
        fin = _FIN_ORDER_BY.search(resto)
        lista = resto[:fin.start() if fin else len(resto)]
        posiciones = [
            item.strip().split()[0] for item in lista.split(",")
            if re.fullmatch(r"\s*\d+\s*(?:ASC|DESC)?\s*", item, re.IGNORECASE)
        ]
        if posiciones:
            hallazgos.append(_hallazgo(
                texto, match.start(), "ORDER_BY_NUMERICO_PROHIBIDO",
                f"Se ordena por posición de columna (ORDER BY {', '.join(posiciones)}). Se recomienda "
                f"escribir el nombre de la columna, ya que si cambia el SELECT el orden cambiaría sin "
                f"notarlo (ej.: ORDER BY cNombre).",
            ))
    return hallazgos


# Cláusulas que abren una parte de la consulta; la última antes de COLLATE
# indica si está en una condición (WHERE, ON, HAVING) o en otra parte.
_CLAUSULAS = re.compile(
    r"\b(WHERE|ON|HAVING|SELECT|FROM|JOIN|GROUP|ORDER|SET|VALUES|TABLE|DECLARE|RETURNS)\b",
    re.IGNORECASE,
)


def _validar_collate_en_condiciones(texto: str, limpio: str) -> List[Hallazgo]:
    """COLLATE no se permite en las condiciones del WHERE ni del JOIN."""
    hallazgos = []
    for match in re.finditer(r"\bCOLLATE\s+\w+", limpio, re.IGNORECASE):
        previo = limpio[:match.start()]
        clausulas = _CLAUSULAS.findall(previo[previo.rfind(";") + 1:])
        ultima = clausulas[-1].upper() if clausulas else ""
        if ultima not in {"WHERE", "ON", "HAVING"}:
            continue
        donde = "del JOIN" if ultima == "ON" else f"del {ultima}"
        hallazgos.append(_hallazgo(
            texto, match.start(), "COLLATE_EN_PREDICADO",
            f"Se usa COLLATE en la condición {donde}. Definir el COLLATE al crear la tabla y no en la "
            f"condición, ya que en el WHERE o en el JOIN impide usar los índices y vuelve lenta la consulta.",
        ))
    return hallazgos


def _validar_funciones_reemplazables(texto: str, limpio: str) -> List[Hallazgo]:
    """Funciones con una alternativa nativa mejor: TRIM, STRING_AGG y STRING_SPLIT."""
    hallazgos = []
    for match in re.finditer(r"\b(?:LTRIM\s*\(\s*RTRIM|RTRIM\s*\(\s*LTRIM)\s*\(", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "LTRIM_RTRIM_PROHIBIDO",
            "Se combinan LTRIM y RTRIM para quitar espacios. Se recomienda usar TRIM, ya que hace lo "
            "mismo en una sola función (ej.: TRIM(Calif0)).",
        ))
    for match in re.finditer(r"\bFOR\s+XML\s+PATH\s*\(\s*(?:''|\"\")\s*\)", limpio, re.IGNORECASE):
        con_stuff = re.search(r"\bSTUFF\s*\(", _sentencia(limpio, match.start()), re.IGNORECASE)
        forma = "FOR XML PATH y STUFF" if con_stuff else "FOR XML PATH"
        hallazgos.append(_hallazgo(
            texto, match.start(), "STUFF_FOR_XML_PATH_PROHIBIDO",
            f"Se concatenan valores con {forma}. Se recomienda usar STRING_AGG, ya que concatena los "
            f"valores con su separador de forma más simple (ej.: STRING_AGG(Nombre, ',')).",
        ))
    for match in re.finditer(r"(?:\b\w+\s*\.\s*)?\bfn_split\s*\(", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "FN_SPLIT_PROHIBIDO",
            "Se usa la función fn_Split para dividir un texto. Se recomienda usar STRING_SPLIT, ya que es "
            "nativa y mejora el rendimiento (ej.: SELECT value FROM STRING_SPLIT('Juan,Pedro', ',')).",
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
                f"La variable {variable} se declara pero no se usa. Se recomienda eliminarla, ya que solo ocupa espacio en el código.",
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

        numeros = sorted({hallazgo.linea for hallazgo in grupo})
        lineas = ("la línea " if len(numeros) == 1 else "las líneas ") + ", ".join(map(str, numeros))
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
                f"Se encontraron {len(grupo)} observaciones de este tipo, en {lineas}: "
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
    hallazgos.extend(_validar_esquema_entre_bases(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_collate_en_condiciones(texto_sql, limpio))
    hallazgos.extend(_validar_funciones_reemplazables(texto_sql, limpio))
    hallazgos.extend(_validar_modificaciones_fisicas(texto_sql, limpio))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_REPORTES[h.regla].activo]
    return _agrupar_hallazgos_repetidos(hallazgos)