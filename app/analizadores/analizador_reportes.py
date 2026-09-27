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
                    f"La tabla temporal {tabla} tiene WITH(NOLOCK), pero en una tabla temporal no sirve: solo la usa este "
                    f"procedimiento. Quite el WITH(NOLOCK) de esa tabla.",
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
                f"La tabla {tabla} se lee sin WITH(NOLOCK). Agréguelo después del nombre de la tabla o de su alias "
                f"(ej.: FROM dbo.Cliente c WITH(NOLOCK)): así el reporte no bloquea a quienes están registrando operaciones.",
            ))
    return hallazgos


def _validar_hints(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto,
            match.start(),
            "HINT_PLAN_PROHIBIDO",
            f"Se usa la instrucción '{match.group(0)}', que le impone a SQL Server cómo ejecutar la consulta. "
            f"Quítela: SQL Server elige solo la forma más rápida y, si se fuerza, el reporte puede volverse "
            f"lento cuando cambian los datos.",
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
                "Hay una sentencia SQL dentro de un comentario, es decir, código que ya no se ejecuta. Si ya no se "
                "usa, elimínela para que el procedimiento sea más fácil de leer.",
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
                    f"La columna {columna.group(1)} de la tabla temporal {tabla} es de texto y no indica su COLLATE. "
                    f"Agréguelo después del tipo (ej.: {columna.group(1)} VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS); "
                    f"sin él, puede dar error al compararla con columnas de otras tablas.",
                ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    reglas = [
        (
            r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b",
            "SELECT_INTO_PROHIBIDO",
            "Se crea una tabla temporal con SELECT ... INTO, que no está permitido. Primero cree la tabla con "
            "CREATE TABLE, indicando sus columnas, tipos y COLLATE, y luego llénela con INSERT INTO ... SELECT.",
        ),
        (r"\bSELECT\s+(?:DISTINCT\s+)?\*", "SELECT_ESTRELLA_PROHIBIDO", "Se usa SELECT *, que trae todas las columnas de la tabla, incluso las que el reporte no necesita. Escriba solo las columnas que va a usar (ej.: SELECT cNombre, dFecha)."),
        (r"\bIN\s*\(\s*[^,()]+\s*\)", "IN_CON_UN_SOLO_VALOR", "Se usa IN con un solo valor, por ejemplo IN (1). Cuando es un solo valor, use el signo igual (ej.: WHERE nEstado = 1)."),
        (_CATALOGOS_PROHIBIDOS, "CATALOGO_SISTEMA_PROHIBIDO", "El reporte consulta tablas internas de SQL Server (sys o information_schema), que no está permitido. Un reporte solo debe consultar las tablas del negocio."),
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
                f"El reporte modifica datos de la tabla {tabla} (INSERT, UPDATE o DELETE). Un reporte solo debe "
                f"consultar información: mueva ese cambio a un procedimiento transaccional.",
            ))
    return hallazgos


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    reglas = (
        (_SQL_DINAMICO, "SQL_DINAMICO_PROHIBIDO", "Se arma una consulta como texto y se ejecuta con EXEC o sp_executesql, que no está permitido: es difícil de revisar y puede abrir la puerta a ataques de inyección de SQL. Escriba la consulta directamente y use parámetros para los filtros."),
        (r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", "VARBINARY_DOCUMENTO_IDENTIFICADO", "Se usa VARBINARY, un tipo que guarda archivos (PDF, imágenes) dentro de la base de datos. Verifique que sea necesario: lo recomendado es guardar el archivo fuera de la base y registrar solo su ruta."),
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
        sujeto = f"{nombre} se declara como VARCHAR(MAX)" if nombre else "Se usa VARCHAR(MAX)"
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARCHAR_MAX_PROHIBIDO",
            f"{sujeto} y no se usa para guardar JSON ni XML. Indique un tamaño acorde al dato "
            f"(ej.: VARCHAR(500)): VARCHAR(MAX) solo se permite para JSON o XML.",
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
                "El procedimiento nuevo usa un bucle WHILE, que no está permitido: repite el mismo proceso "
                "registro por registro y, con muchos datos, el reporte se vuelve muy lento. "
                "Reemplace el bucle por una sola consulta que trabaje con todos los registros a la vez; por ejemplo, en lugar de recorrer los clientes uno por uno para sumar sus saldos, use SELECT nClienteId, SUM(nSaldo) FROM dbo.Cuenta GROUP BY nClienteId.",
            ))
    for match in re.finditer(r"\bRAISERROR\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "RAISERROR_USAR_THROW",
            "Se usa RAISERROR para mostrar errores, que es una forma antigua. Use THROW, la forma "
            "recomendada, que además conserva el detalle del error original (ej.: THROW 50001, "
            "'No existe el cliente', 1;).",
        ))
    for match in re.finditer(r"\bWAITFOR\s+(?:DELAY|TIME)\b", limpio, re.IGNORECASE):
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            "Se usa WAITFOR para hacer una pausa, lo que hace esperar al reporte sin motivo y mantiene "
            "recursos ocupados. Quite la pausa.",
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
            f"La tabla {base}..{tabla} está escrita con dos puntos seguidos, sin indicar el esquema. "
            f"Cuando consulte otra base de datos, escriba base, esquema y tabla (ej.: {base}.dbo.{tabla}).",
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
                f"La variable {variable} se declara pero nunca se usa. Elimine la declaración si no la necesita.",
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
    hallazgos.extend(_validar_modificaciones_fisicas(texto_sql, limpio))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_REPORTES[h.regla].activo]
    return _agrupar_hallazgos_repetidos(hallazgos)