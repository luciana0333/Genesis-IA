# -*- coding: utf-8 -*-
"""Reglas para procedimientos almacenados normales, fuera de reportes."""

import re
from typing import Dict, List, Set, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_procedimientos_normales import REGLAS_PROCEDIMIENTOS_NORMALES


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_HINTS_PROHIBIDOS = (
    r"FORCESEEK|FORCESCAN|RECOMPILE|NOEXPAND|INDEX\s*\(|"
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


def _quitar_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), texto, flags=re.DOTALL)
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
    encontrado = re.search(rf"\bFROM\s+({_REFERENCIA})", tramo, re.IGNORECASE)
    return _limpiar_nombre(encontrado.group(1)) if encontrado else ""


def _nombre_declarado_antes(limpio: str, posicion: int) -> str:
    """Variable o columna declarada justo antes de un tipo (ej.: @doc VARBINARY)."""
    encontrado = re.search(r"(@?[A-Za-z_]\w*)\s+$", limpio[:posicion])
    if encontrado and encontrado.group(1).upper() not in {"AS", "CAST", "CONVERT", "DECLARE", "TABLE"}:
        return encontrado.group(1)
    return ""


def _validar_control_flujo(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bWHILE\b\s*([^\n]*)", limpio, re.IGNORECASE):
        condicion = re.split(r"\bBEGIN\b", match.group(1), flags=re.IGNORECASE)[0].strip()[:60]
        cual = f" (WHILE {condicion})" if condicion else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "WHILE_PROHIBIDO",
            f"Se identificó un bucle WHILE{cual} en el procedimiento. Se recomienda resolverlo con una sola "
            f"consulta que trabaje con todos los registros a la vez, ya que el WHILE procesa los registros uno "
            f"por uno, vuelve lento el procedimiento y puede quedar en un bucle infinito.",
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
            f"Se identificó una sentencia MERGE{tabla}. Se recomienda validar si su uso está justificado y, "
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
            f"Se identificó el uso de '{match.group(0)}', que le indica al motor de base de datos cómo "
            f"ejecutar la consulta. Se recomienda retirarlo, ya que no está permitido forzar al motor y es el "
            f"optimizador quien decide el mejor plan de ejecución.",
        )
        for match in re.finditer(_HINTS_PROHIBIDOS, limpio, re.IGNORECASE)
    ]


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
            f"Se identificó el uso de '{hint}', que {_HINTS_BLOQUEO[hint]}. Se recomienda retirarlo y dejar que "
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
            porque = "que es pesada"
        elif palabras & _PALABRAS_CONSTANTES:
            tipo = "de constantes"
            porque = "que se consulta en casi todos los procesos"
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
            f"Se identificó que la tabla {tipo} {tabla}, {porque}, se lee sin WITH(NOLOCK). Se recomienda "
            f"añadirlo, ya que leer estas tablas sin NOLOCK genera bloqueos y esperas para los procesos que "
            f"registran operaciones (ej.: {tabla} WITH(NOLOCK)).",
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
                f"Se identificó que la tabla {tabla}, que es la que se actualiza en el UPDATE, usa WITH(NOLOCK). "
                f"Se recomienda retirar el WITH(NOLOCK) de esa tabla, ya que al modificar datos no se deben leer "
                f"datos que aún no están confirmados.",
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
                f"Se identificó que {'la variable de tabla' if nombre.startswith('@') else 'la tabla temporal'} "
                f"{nombre} usa WITH(NOLOCK). Se recomienda retirarlo, ya que la tabla temporal solo la usa este "
                f"procedimiento y no genera bloqueos con otros procesos.",
            ))
    return hallazgos


def _validar_order_by_numerico(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bORDER\s+BY\s+(\d+(?:\s*,\s*\d+)*)", limpio, re.IGNORECASE):
        posiciones = ", ".join(re.findall(r"\d+", match.group(1)))
        hallazgos.append(_hallazgo(
            texto, match.start(), "ORDER_BY_NUMERICO_PROHIBIDO",
            f"Se identificó un ORDER BY por posición de columna (ORDER BY {posiciones}). Se recomienda escribir "
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
    for match in re.finditer(r"(?is)(?:^|;|\bGO\b)\s*(SELECT)\b(?:(?!;|\bGO\b).)*?\bINTO\b\s*([#@]?[\w\[\].]*)", limpio):
        destino = match.group(2).strip()
        tabla = f"la tabla {destino}" if destino else "una tabla temporal"
        hallazgos.append(_hallazgo(
            texto, match.start(1), "SELECT_INTO_PROHIBIDO",
            f"Se identificó que {tabla} se crea con SELECT INTO. Se recomienda crear primero la tabla con "
            f"CREATE TABLE, indicando sus tipos y COLLATE, y luego llenarla con INSERT INTO seguido del SELECT, "
            f"ya que así se controlan sus tipos de datos.",
        ))
    for match in re.finditer(r"\bSELECT\s+(?:DISTINCT\s+)?\*", limpio, re.IGNORECASE):
        tabla = _tabla_del_from(limpio, match.start())
        sobre = f" sobre la tabla {tabla}" if tabla else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "SELECT_ESTRELLA_PROHIBIDO",
            f"Se identificó un SELECT *{sobre}, que trae todas sus columnas. Se recomienda escribir solo las "
            f"columnas necesarias, ya que traer columnas de más consume memoria y vuelve más lento el "
            f"procedimiento (ej.: SELECT cNombre, dFecha).",
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
            f"Se identificó un COLLATE sobre {match.group(1)} en la condición {clausula}. Se recomienda definir "
            f"el COLLATE al crear la tabla temporal y no en la condición, ya que en el WHERE o en el JOIN impide "
            f"usar los índices y vuelve lenta la consulta.",
        ))
    for match in re.finditer(r"\bSTUFF\s*\([\s\S]*?\bFOR\s+XML\s+PATH\b", limpio, re.IGNORECASE):
        tabla = _tabla_del_from(limpio, match.start())
        sobre = f" sobre la tabla {tabla}" if tabla else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "STUFF_FOR_XML_PATH_PROHIBIDO",
            f"Se identificó una concatenación con STUFF y FOR XML PATH{sobre}. Se recomienda usar STRING_AGG, "
            f"ya que es la función nativa para concatenar valores y es más simple y rápida "
            f"(ej.: STRING_AGG(cNombre, ',')).",
        ))
    for match in re.finditer(r"\b(?:dbo\.)?FN_SPLIT\s*\(\s*([^,)]*)", limpio, re.IGNORECASE):
        dato = match.group(1).strip()
        sobre = f" para dividir {dato}" if dato.startswith("@") else " para dividir textos"
        hallazgos.append(_hallazgo(
            texto, match.start(), "FN_SPLIT_PROHIBIDO",
            f"Se identificó la función dbo.FN_SPLIT{sobre}. Se recomienda usar STRING_SPLIT, ya que es la "
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
                    f"Se identificó que la columna {nombre} es {tipo} en {tabla}, pero {tipo_anterior} en "
                    f"{tabla_anterior} (línea {_linea(texto, posicion_anterior)}). Se recomienda usar el mismo tipo "
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
                f"Se identificó el uso de COLLATE DATABASE_DEFAULT, que toma el COLLATE de la base donde se "
                f"ejecuta. Se recomienda definir el COLLATE explícitamente con el que usa la empresa, ya que "
                f"DATABASE_DEFAULT puede cambiar entre bases y servidores, y las comparaciones fallarían "
                f"(ej.: COLLATE {_COLLATE_EMPRESA}).",
            ))
        else:
            hallazgos.append(_hallazgo(
                texto, match.start(1), "COLLATE_DISTINTO_AL_ESTANDAR",
                f"Se identificó el COLLATE {collate}, distinto al que usa la empresa ({_COLLATE_EMPRESA}). Se "
                f"recomienda validar si el COLLATE es el correcto, ya que si no coincide con el de las demás "
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
                f"Se identificó que la columna de texto {columna.group(1)} de {tipo_tabla} {tabla} no define "
                f"COLLATE. Se recomienda añadir el COLLATE de la empresa, ya que sin él puede fallar al compararla "
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
                hallazgos.append(_hallazgo(texto, match.start(), "CODIGO_SQL_COMENTADO", "Se identificó código SQL comentado, es decir, sentencias que ya no se ejecutan. Se recomienda "
                "eliminarlo si ya no se usa, ya que dificulta la lectura del procedimiento y el historial de "
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
            hallazgos.append(_hallazgo(texto, posicion, "VARIABLE_DECLARADA_SIN_USO", f"Se identificó la variable {variable}, que es declarada pero no usada. Se recomienda su "
                f"eliminación, ya que no es usada dentro del procedimiento."))
    return hallazgos


# Acciones estándar del manual: la palabra completa se abrevia.
_ACCIONES_ABREVIADAS = {
    "consultar": "Sel", "consulta": "Sel", "select": "Sel", "seleccionar": "Sel",
    "actualizar": "Upd", "actualiza": "Upd", "update": "Upd",
    "insertar": "Ins", "inserta": "Ins", "insert": "Ins",
    "eliminar": "Del", "elimina": "Del", "delete": "Del", "borrar": "Del",
}
_EJEMPLO_NOMBRE = "PA_Cliente_Sel_PorDocumento"


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
            f"Se identificó que el procedimiento {nombre} no tiene declarado un esquema. Se recomienda añadir "
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
            f"(ej.: {_EJEMPLO_NOMBRE}).",
        ))
        return hallazgos
    # PA_ y pa_ son equivalentes: el prefijo no distingue mayúsculas.

    if len(segmentos) < 3 or not all(segmentos[1:3]):
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            f"Se identificó que el nombre del procedimiento {nombre} no indica la tabla y la acción. Se "
            f"recomienda usar el formato PA_Tabla_Acción_Finalidad, ya que así se entiende qué hace el "
            f"procedimiento (ej.: {_EJEMPLO_NOMBRE}).",
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
            f"Se identificó que la acción del procedimiento {nombre} está escrita como '{accion}'. Se "
            f"recomienda usar la abreviatura del manual, {abreviatura}, ya que así se nombran las acciones "
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
    if fuera_de_estandar:
        corregidas = ", ".join(f"{parte} → {_en_pascal(parte)}" for parte in fuera_de_estandar)
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_NO_PASCALCASE",
            f"Se identificó que partes del nombre {nombre} no están en PascalCase ({corregidas}). Se "
            f"recomienda escribir cada palabra con mayúscula inicial y el resto en minúscula, ya que es el "
            f"estándar de nomenclatura.",
        ))
    return hallazgos

    if len(segmentos) < 3 or not all(segmentos[1:3]):
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            f"Se identificó que el nombre del procedimiento {nombre} no indica la tabla y la acción. Se "
            f"recomienda usar el formato PA_Tabla_Acción_Finalidad, ya que así se entiende qué hace el "
            f"procedimiento (ej.: {_EJEMPLO_NOMBRE}).",
        ))
        return hallazgos

    accion = segmentos[2]
    abreviatura = _ACCIONES_ABREVIADAS.get(accion.lower())
    if abreviatura and accion != abreviatura:
        sugerido = "_".join(segmentos[:2] + [abreviatura] + segmentos[3:])
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
            f"Se identificó que la acción del procedimiento {nombre} está escrita como '{accion}'. Se "
            f"recomienda usar la abreviatura del manual, {abreviatura}, ya que así se nombran las acciones "
            f"estándar (ej.: {sugerido}).",
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
            f"Se identificó {sujeto} y no guarda JSON ni XML. Se recomienda definir una longitud acorde al "
            f"dato, salvo que provenga de una tabla heredada con {tipo}, ya que solo se justifica para JSON, "
            f"XML o tablas heredadas y reserva más memoria de la necesaria (ej.: {tipo.replace('MAX', '500')}).",
        ))
    return hallazgos


def _validar_waitfor(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bWAITFOR\s+(DELAY|TIME)\s*('[^']*')?", limpio, re.IGNORECASE):
        espera = f" {match.group(2)}" if match.group(2) else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            f"Se identificó una pausa con WAITFOR {match.group(1).upper()}{espera}, que fuerza al motor de "
            f"base de datos a detener la ejecución. Se recomienda retirarla, ya que no está permitido forzar al "
            f"motor y deja el procedimiento esperando sin motivo.",
        ))
    return hallazgos


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
        columna, negado, valor = match.group(1), bool(match.group(2)), match.group(3)
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
                f"Se identificó LEFT({col}, {n}) = {val} en una condición. Se recomienda usar LIKE, ya que "
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
            f"Se identificaron {cantidad} REPLACE anidados. Se recomienda usar TRANSLATE, ya que cambia "
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
        f"Se identificó una transacción abierta con BEGIN TRANSACTION {detalle}. Se recomienda confirmarla "
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
            f"Se identificó el uso de la tabla {tabla} de la base {base}, pero el esquema se omitió "
            f"({base}..{tabla}). Se recomienda definir el esquema, ya que así se evita apuntar a una tabla "
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
                f"Se identificó que la tabla {nombres[clave]} se consulta {len(posiciones)} veces en la misma "
                f"consulta (líneas {lineas}). Se recomienda revisar si se puede leer una sola vez (por ejemplo, "
                f"cargándola antes en una tabla temporal o combinando las condiciones), ya que acceder "
                f"muchas veces a la misma tabla vuelve lenta la consulta.",
            ))
    return hallazgos


def verificar_procedimiento_normal(texto_sql: str) -> List[Hallazgo]:
    """Aplica exclusivamente las reglas de procedimientos normales."""
    limpio = _quitar_comentarios(texto_sql)
    hallazgos: List[Hallazgo] = []
    hallazgos.extend(_validar_nombre_procedimiento(texto_sql, limpio))
    hallazgos.extend(_validar_control_flujo(texto_sql, limpio))
    hallazgos.extend(_validar_hints(texto_sql, limpio))
    hallazgos.extend(_validar_hints_bloqueo(texto_sql, limpio))
    hallazgos.extend(_validar_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_update_from_nolock(texto_sql, limpio))
    hallazgos.extend(_validar_nolock_tablas_pesadas(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_cast_en_join(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_varchar_max(texto_sql, limpio))
    hallazgos.extend(_validar_waitfor(texto_sql, limpio))
    hallazgos.extend(_validar_raiserror(texto_sql, limpio))
    hallazgos.extend(_validar_transacciones(texto_sql, limpio))
    hallazgos.extend(_validar_envio_correo(texto_sql, limpio))
    hallazgos.extend(_validar_in_un_valor(texto_sql, limpio))
    hallazgos.extend(_validar_left_como_like(texto_sql, limpio))
    hallazgos.extend(_validar_replace_anidado(texto_sql, limpio))
    hallazgos.extend(_validar_esquema_entre_bases(texto_sql, limpio))
    hallazgos.extend(_validar_tabla_repetida(texto_sql, limpio))
    hallazgos.extend(_validar_collate_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_collate_usado(texto_sql, limpio))
    hallazgos.extend(_validar_tipos_entre_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_comentarios(texto_sql))
    hallazgos.extend(_validar_variables(texto_sql, limpio))
    # Las reglas desactivadas en el catálogo no se reportan.
    hallazgos = [h for h in hallazgos if REGLAS_PROCEDIMIENTOS_NORMALES[h.regla].activo]
    return _agrupar_repetidos(hallazgos)


def _validar_sintaxis_prohibida(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(_CATALOGO_SISTEMA, limpio, re.IGNORECASE):
        objeto = _limpiar_nombre(match.group(0))
        hallazgos.append(_hallazgo(
            texto, match.start(), "CATALOGO_SISTEMA_PROHIBIDO",
            f"Se identificó una consulta a {objeto}, una tabla interna de SQL Server. Se recomienda consultar "
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
