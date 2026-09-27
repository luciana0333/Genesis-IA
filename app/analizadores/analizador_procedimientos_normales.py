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
            f"Se identificó un bucle WHILE{cual} en el procedimiento. Evaluar otras formas de resolverlo "
            f"sin WHILE (por ejemplo, una sola consulta que trabaje con todos los registros), ya que procesa "
            f"los registros uno por uno, vuelve lento el procedimiento y puede quedar en un bucle infinito.",
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
            texto, match.start(), "CAST_EN_JOIN_PROHIBIDO",
            f"Se identificó un {match.group(2).upper()} en la condición del JOIN con la tabla {tabla}. Convertir el dato antes del "
            f"JOIN (en una tabla temporal o variable) o unir columnas del mismo tipo, ya que el CAST en la "
            f"condición impide usar los índices y vuelve lenta la consulta.",
        ))
    return hallazgos


def _validar_sentencias(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"(?is)(?:^|;|\bGO\b)\s*SELECT\b(?:(?!;|\bGO\b).)*?\bINTO\b\s*([#@]?[\w\[\].]*)", limpio):
        destino = match.group(1).strip()
        tabla = f"la tabla {destino}" if destino else "una tabla temporal"
        hallazgos.append(_hallazgo(
            texto, match.start(), "SELECT_INTO_PROHIBIDO",
            f"Se identificó que {tabla} se crea con SELECT INTO. Crear primero la tabla con CREATE TABLE, "
            f"indicando sus tipos y COLLATE, y luego llenarla con INSERT INTO seguido del SELECT, ya que así "
            f"se controlan sus tipos de datos.",
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
    for match in re.finditer(r"\b(WHERE|ON)\b[^;\n]*?([\w.\[\]@#]+)\s+COLLATE\s+\w+", limpio, re.IGNORECASE):
        # La cláusula que manda es la más cercana al COLLATE (puede haber un ON antes del WHERE).
        ultima = re.findall(r"\b(WHERE|ON)\b", match.group(0), re.IGNORECASE)[-1]
        clausula = "del JOIN" if ultima.upper() == "ON" else "del WHERE"
        hallazgos.append(_hallazgo(
            texto, match.start(), "COLLATE_EN_PREDICADO",
            f"Se identificó COLLATE sobre {match.group(2)} en la condición {clausula}. Definir el COLLATE al "
            f"crear la tabla temporal y no en la condición, ya que en el WHERE o en el JOIN impide usar los "
            f"índices y vuelve lenta la consulta.",
        ))
    for match in re.finditer(r"\bSTUFF\s*\([\s\S]*?\bFOR\s+XML\s+PATH\b", limpio, re.IGNORECASE):
        tabla = _tabla_del_from(limpio, match.start())
        sobre = f" sobre la tabla {tabla}" if tabla else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "STUFF_FOR_XML_PATH_PROHIBIDO",
            f"Se identificó una concatenación con STUFF y FOR XML PATH{sobre}. Reemplazarla por STRING_AGG, "
            f"ya que es la función nativa para concatenar valores y es más simple y rápida "
            f"(ej.: STRING_AGG(cNombre, ',')).",
        ))
    for match in re.finditer(r"\b(?:dbo\.)?FN_SPLIT\s*\(\s*([^,)]*)", limpio, re.IGNORECASE):
        dato = match.group(1).strip()
        sobre = f" para dividir {dato}" if dato.startswith("@") else " para dividir textos"
        hallazgos.append(_hallazgo(
            texto, match.start(), "FN_SPLIT_PROHIBIDO",
            f"Se identificó la función dbo.FN_SPLIT{sobre}. Reemplazarla por STRING_SPLIT, ya que es la "
            f"función nativa de SQL Server y mejora el rendimiento (ej.: SELECT value FROM "
            f"STRING_SPLIT(@cLista, ',')).",
        ))
    for match in re.finditer(r"\b(LTRIM\s*\(\s*RTRIM|RTRIM\s*\(\s*LTRIM)\s*\(\s*([^()]*?)\s*\)\s*\)", limpio, re.IGNORECASE):
        dato = match.group(2) or "cNombre"
        hallazgos.append(_hallazgo(
            texto, match.start(), "LTRIM_RTRIM_PROHIBIDO",
            f"Se identificó la combinación de LTRIM y RTRIM sobre {dato} para quitar espacios. Se recomienda "
            f"usar TRIM, ya que hace lo mismo en una sola función (ej.: TRIM({dato})).",
        ))
    return hallazgos


def _contenido_entre_parentesis(texto: str, apertura: int) -> str:
    """Texto dentro del paréntesis que abre en `apertura`, respetando los anidados."""
    profundidad = 0
    for indice in range(apertura, len(texto)):
        if texto[indice] == "(":
            profundidad += 1
        elif texto[indice] == ")":
            profundidad -= 1
            if profundidad == 0:
                return texto[apertura + 1:indice]
    return texto[apertura + 1:]


def _separar_por_comas(contenido: str) -> List[tuple]:
    """Partes separadas por comas de primer nivel, con su posición."""
    partes, inicio, profundidad = [], 0, 0
    for indice, caracter in enumerate(contenido):
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        elif caracter == "," and profundidad == 0:
            partes.append((contenido[inicio:indice], inicio))
            inicio = indice + 1
    partes.append((contenido[inicio:], inicio))
    return partes


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
                f"La columna de texto {columna.group(1)} de {tipo_tabla} {tabla} no define COLLATE. Añadir "
                f"COLLATE a la columna, ya que sin él puede fallar al compararla con columnas de otras tablas "
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


def _es_pascal(parte: str) -> bool:
    """PascalCase: mayúscula inicial (Cliente, TipoCambio). Se aceptan siglas cortas (BI, IGV)."""
    return bool(re.fullmatch(r"(?:[A-Z][a-z0-9]+)+", parte)) or bool(re.fullmatch(r"[A-Z]{2,3}", parte)) \
        or parte in {"Sel", "Upd", "Ins", "Del"}


def _en_pascal(parte: str) -> str:
    """CLIENTE o cliente → Cliente; TipoCambio se respeta."""
    if parte.isupper() or parte.islower():
        return parte.capitalize()
    return parte[0].upper() + parte[1:]


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
    if segmentos[0].upper() != "PA":
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_SIN_PREFIJO_PA",
            f"El nombre del procedimiento {nombre} no empieza con PA_. Usar el formato "
            f"PA_Tabla_Acción_Finalidad, ya que PA identifica a los procedimientos almacenados "
            f"(ej.: {_EJEMPLO_NOMBRE}).",
        ))
        return hallazgos
    # PA_ y pa_ son equivalentes: el prefijo no distingue mayúsculas.

    if len(segmentos) < 3 or not all(segmentos[1:3]):
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            f"El nombre del procedimiento {nombre} no indica la tabla y la acción. Usar el formato "
            f"PA_Tabla_Acción_Finalidad, ya que así se entiende qué hace el procedimiento "
            f"(ej.: {_EJEMPLO_NOMBRE}).",
        ))
        return hallazgos

    tabla, accion, finalidad = segmentos[1], segmentos[2], [parte for parte in segmentos[3:] if parte]
    abreviatura = _ACCIONES_ABREVIADAS.get(accion.lower())
    es_estandar = accion.lower() in {"sel", "upd", "ins", "del"}
    es_verbo = bool(re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]+(?:ar|er|ir)", accion, re.IGNORECASE))

    if abreviatura and accion != abreviatura:
        sugerido = "_".join(["PA", _en_pascal(tabla), abreviatura] + [_en_pascal(x) for x in finalidad])
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
            f"La acción del procedimiento {nombre} está escrita como '{accion}'. Usar la abreviatura "
            f"del manual, {abreviatura}, ya que así se nombran las acciones estándar (ej.: {sugerido}).",
        ))
    elif not es_estandar and not es_verbo:
        sugerido = "_".join(["PA", _en_pascal(tabla), "Sel", _en_pascal(accion)] + [_en_pascal(x) for x in finalidad])
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_SIN_ACCION",
            f"El nombre del procedimiento {nombre} no indica una acción: '{accion}' no es Sel, Upd, Ins, "
            f"Del ni un verbo. Añadir la acción después de la tabla, ya que así se entiende qué hace el "
            f"procedimiento (ej.: {sugerido}).",
        ))
        accion = None  # su mayúscula ya se corrige en la sugerencia anterior

    partes = [tabla] + ([accion] if accion and not abreviatura else []) + finalidad
    fuera_de_estandar = [parte for parte in partes if not _es_pascal(parte)]
    if fuera_de_estandar:
        corregidas = ", ".join(f"{parte} → {_en_pascal(parte)}" for parte in fuera_de_estandar)
        hallazgos.append(_hallazgo(
            texto, posicion, "PROCEDIMIENTO_NOMBRE_NO_PASCALCASE",
            f"Partes del nombre {nombre} no están en PascalCase ({corregidas}). Escribir cada palabra "
            f"con mayúscula inicial y el resto en minúscula, ya que es el estándar de nomenclatura.",
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


def _validar_waitfor(texto: str, limpio: str) -> List[Hallazgo]:
    hallazgos = []
    for match in re.finditer(r"\bWAITFOR\s+(DELAY|TIME)\s*('[^']*')?", limpio, re.IGNORECASE):
        espera = f" {match.group(2)}" if match.group(2) else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "WAITFOR_DELAY_PROHIBIDO",
            f"Se identificó una pausa con WAITFOR {match.group(1).upper()}{espera}, que fuerza al motor de "
            f"base de datos a detener la ejecución. Retirar la pausa, ya que no está permitido emplear "
            f"sintaxis que fuerce al motor y deja el procedimiento esperando sin motivo.",
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
            f"La tabla {base}..{tabla} no indica el esquema. Escribir base, esquema y tabla, ya que así se "
            f"evita apuntar a una tabla equivocada (ej.: {base}.dbo.{tabla}).",
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
    cortes = [0] + [m.start() for m in _INICIO_SENTENCIA.finditer(limpio)] + [len(limpio)]
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
                f"La tabla {nombres[clave]} se consulta {len(posiciones)} veces en la misma consulta "
                f"(líneas {lineas}). Se recomienda revisar si se puede leer una sola vez (por ejemplo, "
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
    hallazgos.extend(_validar_temporales(texto_sql, limpio))
    hallazgos.extend(_validar_update_from_nolock(texto_sql, limpio))
    hallazgos.extend(_validar_order_by_numerico(texto_sql, limpio))
    hallazgos.extend(_validar_cast_en_join(texto_sql, limpio))
    hallazgos.extend(_validar_sentencias(texto_sql, limpio))
    hallazgos.extend(_validar_sintaxis_prohibida(texto_sql, limpio))
    hallazgos.extend(_validar_varchar_max(texto_sql, limpio))
    hallazgos.extend(_validar_waitfor(texto_sql, limpio))
    hallazgos.extend(_validar_esquema_entre_bases(texto_sql, limpio))
    hallazgos.extend(_validar_tabla_repetida(texto_sql, limpio))
    hallazgos.extend(_validar_collate_temporales(texto_sql, limpio))
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
            f"Se identificó una consulta a {objeto}, una tabla interna de SQL Server. Consultar solo las "
            f"tablas del negocio, ya que un procedimiento no debe depender de las tablas internas del motor.",
        ))
    for match in re.finditer(_SQL_DINAMICO, limpio, re.IGNORECASE):
        variable = re.search(r"@\w+", limpio[match.start():match.start() + 80])
        guardada = f" guardada en {variable.group(0)}" if variable else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "SQL_DINAMICO_PROHIBIDO",
            f"Se identificó SQL dinámico: la consulta{guardada} se arma como texto y se ejecuta con EXEC o "
            f"sp_executesql. Escribir la consulta directamente y usar parámetros para los filtros, ya que el "
            f"SQL dinámico es difícil de revisar y puede permitir ataques de inyección de SQL.",
        ))
    for match in re.finditer(r"\bVARBINARY(?:\s*\(\s*(?:MAX|\d+)\s*\))?", limpio, re.IGNORECASE):
        nombre = _nombre_declarado_antes(limpio, match.start())
        en = f" en {nombre}" if nombre else ""
        hallazgos.append(_hallazgo(
            texto, match.start(), "VARBINARY_DOCUMENTO_IDENTIFICADO",
            f"Se identificó un tipo de dato VARBINARY{en}, que guarda archivos dentro de la base de datos. Se "
            f"recomienda evaluar si es necesario, ya que lo ideal es guardar el archivo fuera de la base de "
            f"datos y registrar solo su ruta.",
        ))
    return hallazgos
