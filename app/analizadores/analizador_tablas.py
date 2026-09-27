# -*- coding: utf-8 -*-
"""
Valida la estructura de CREATE TABLE y ALTER TABLE según el manual de
nomenclatura de base de datos de CAJA ICA.

CREATE TABLE (tabla nueva): esquema, nombre en PascalCase sin palabras de
enlace, clave primaria (índice clúster identidad nNombreTablaId) y todas las
columnas (prefijo del tipo + PascalCase, COLLATE, NOT NULL o DEFAULT).

ALTER TABLE: solo las columnas nuevas (ADD): prefijo, nombre y COLLATE; si
aceptan NULL se pide evaluar un valor por defecto, porque la tabla ya tiene
registros y no se puede exigir NOT NULL.

La severidad de cada regla sale del catálogo app/reglas/reglas_tablas.py.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_tablas import REGLAS_TABLAS


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#@]*)"
_COMENTARIOS = re.compile(r"--[^\r\n]*|/\*.*?\*/", re.DOTALL)
_PALABRAS_NO_COLUMNA = {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY", "PERIOD"}
_PREFIJOS_TIPO = (
    ("c", r"(?:N?VARCHAR|N?CHAR)\b"),
    ("n", r"(?:BIGINT|SMALLINT|TINYINT|INT|MONEY|SMALLMONEY|DECIMAL|NUMERIC)\b"),
    ("b", r"BIT\b"),
    ("d", r"(?:DATETIME2|DATETIME|SMALLDATETIME|DATE)\b"),
)
_TIPOS_NUMERICOS = r"(?:BIGINT|SMALLINT|TINYINT|INT|DECIMAL|NUMERIC)\b"
_PALABRAS_OMITIBLES_TABLA = {"de", "del", "la", "el", "los", "las", "mi", "mis", "su", "sus"}

# Manual: cada palabra con mayúscula inicial y el resto en minúscula.
_PASCAL_CASE = re.compile(r"^(?:[A-Z][a-z0-9]+)+$")
# Columnas: prefijo del tipo en minúscula + PascalCase (cPersonaNombre).
_NOMBRE_COLUMNA = re.compile(r"^[a-z](?:[A-Z][a-z0-9]+)+$")


@dataclass
class ColumnaNueva:
    nombre: str
    definicion: str
    posicion: int


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def _limpiar_identificador(valor: str) -> str:
    return valor[1:-1] if valor.startswith("[") and valor.endswith("]") else valor


def _sin_comentarios(texto: str) -> str:
    """Reemplaza comentarios por espacios conservando posiciones y saltos de línea."""
    return _COMENTARIOS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto or "")


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    """Hallazgo con la severidad definida en el catálogo de reglas."""
    return Hallazgo(
        linea=_numero_linea(texto, posicion) if posicion >= 0 else 1,
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_TABLAS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )


def _palabras_nombre_tabla(nombre: str) -> List[str]:
    """Separa nombres PascalCase para revisar palabras omitibles."""
    return [parte.lower() for parte in re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", nombre)]


def _prefijo_esperado(definicion: str) -> Optional[str]:
    for prefijo, patron_tipo in _PREFIJOS_TIPO:
        if re.search(rf"^\s*{patron_tipo}", definicion, re.IGNORECASE):
            return prefijo
    return None


def _tipo_de_dato(definicion: str) -> str:
    coincidencia = re.match(r"\s*([A-Za-z0-9_]+)", definicion)
    return coincidencia.group(1).upper() if coincidencia else "?"


def _es_tipo_texto(definicion: str) -> bool:
    return bool(re.search(r"^\s*(?:N?VARCHAR|N?CHAR)\b", definicion, re.IGNORECASE))


def _separar_por_comas(contenido: str) -> List[Tuple[str, int]]:
    """Divide por comas de primer nivel (respeta paréntesis y cadenas)."""
    segmentos, inicio, profundidad, en_cadena = [], 0, 0, False
    for indice, caracter in enumerate(contenido):
        if caracter == "'":
            en_cadena = not en_cadena
        elif not en_cadena:
            if caracter == "(":
                profundidad += 1
            elif caracter == ")":
                profundidad = max(0, profundidad - 1)
            elif caracter == "," and profundidad == 0:
                segmentos.append((contenido[inicio:indice], inicio))
                inicio = indice + 1
    segmentos.append((contenido[inicio:], inicio))
    return segmentos


def _columna_desde_segmento(segmento: str, posicion: int) -> Optional[ColumnaNueva]:
    coincidencia = re.match(rf"\s*({_IDENTIFICADOR})(.*)", segmento, re.DOTALL)
    if not coincidencia:
        return None
    nombre = _limpiar_identificador(coincidencia.group(1))
    if nombre.upper() in _PALABRAS_NO_COLUMNA:
        return None
    return ColumnaNueva(nombre, coincidencia.group(2), posicion + coincidencia.start(1))


# ---------------------------------------------------------------------------
# EXTRACCIÓN
# ---------------------------------------------------------------------------

def extraer_objeto_tabla(texto_sql: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Devuelve (base_de_datos, esquema, tabla); prioriza el CREATE TABLE."""
    texto = _sin_comentarios(texto_sql)
    for verbo in ("CREATE", "ALTER"):
        coincidencia = re.search(
            rf"\b{verbo}\s+TABLE\s+((?:{_IDENTIFICADOR}\s*\.\s*){{0,2}}{_IDENTIFICADOR})",
            texto,
            re.IGNORECASE,
        )
        if coincidencia:
            partes = [_limpiar_identificador(p.strip()) for p in coincidencia.group(1).split(".")]
            if len(partes) == 3:
                return partes[0], partes[1], partes[2]
            if len(partes) == 2:
                return None, partes[0], partes[1]
            return None, None, partes[0]
    return None, None, None


def extraer_tipo_sentencia(texto_sql: str) -> str:
    """CREATE si el script crea la tabla (aunque luego tenga ALTER TABLE)."""
    texto = _sin_comentarios(texto_sql)
    if re.search(r"\bCREATE\s+TABLE\b", texto, re.IGNORECASE):
        return "CREATE"
    if re.search(r"\bALTER\s+TABLE\b", texto, re.IGNORECASE):
        return "ALTER"
    return "DESCONOCIDO"


def _segmentos_create(texto: str) -> List[Tuple[str, int]]:
    """Definiciones (columnas y restricciones) entre los paréntesis del CREATE TABLE."""
    inicio = re.search(
        rf"\bCREATE\s+TABLE\s+(?:{_IDENTIFICADOR}\s*\.\s*){{0,2}}{_IDENTIFICADOR}\s*\(",
        texto,
        re.IGNORECASE,
    )
    if not inicio:
        return []
    apertura = inicio.end()
    profundidad, cierre = 0, len(texto)
    for indice in range(apertura, len(texto)):
        if texto[indice] == "(":
            profundidad += 1
        elif texto[indice] == ")":
            if profundidad == 0:
                cierre = indice
                break
            profundidad -= 1
    return [(segmento, apertura + posicion) for segmento, posicion in _separar_por_comas(texto[apertura:cierre])]


def _columnas_create(texto: str) -> List[ColumnaNueva]:
    columnas = (_columna_desde_segmento(s, p) for s, p in _segmentos_create(texto))
    return [c for c in columnas if c]


def _columnas_alter(texto: str) -> List[ColumnaNueva]:
    """Columnas agregadas con ADD en cada ALTER TABLE (admite varias por ADD)."""
    columnas = []
    sentencias = re.finditer(
        r"\bALTER\s+TABLE\b(.*?)(?=;|\bGO\b|\bALTER\s+TABLE\b|\bCREATE\b|\Z)",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    for sentencia in sentencias:
        cuerpo, base = sentencia.group(1), sentencia.start(1)
        if re.search(r"\bALTER\s+COLUMN\b", cuerpo, re.IGNORECASE):
            continue
        agregar = re.search(r"\bADD\b(?:\s+COLUMN\b)?", cuerpo, re.IGNORECASE)
        if not agregar:
            continue
        resto = cuerpo[agregar.end():]
        desplazamiento = base + agregar.end()
        # ALTER TABLE t ADD ( ... ) con paréntesis envolvente.
        recortado = resto.lstrip()
        if recortado.startswith("(") and recortado.rstrip().endswith(")"):
            desplazamiento += len(resto) - len(recortado) + 1
            resto = recortado.rstrip()[1:-1]
        for segmento, posicion in _separar_por_comas(resto):
            columna = _columna_desde_segmento(segmento, desplazamiento + posicion)
            if columna:
                columnas.append(columna)
    return columnas


def extraer_columnas_nuevas(texto_sql: str) -> List[ColumnaNueva]:
    """Columnas del CREATE TABLE o, en un ALTER, las columnas agregadas."""
    texto = _sin_comentarios(texto_sql)
    return _columnas_create(texto) if extraer_tipo_sentencia(texto) == "CREATE" else _columnas_alter(texto)


def _clave_primaria(texto: str, columnas: List[ColumnaNueva]) -> Tuple[List[str], bool, int]:
    """
    Devuelve (columnas de la PK, es_cluster, posición). Reconoce la PK en la
    columna (nId INT PRIMARY KEY), como restricción del CREATE o agregada
    con ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY en el mismo script.
    """
    for columna in columnas:
        if re.search(r"\bPRIMARY\s+KEY\b", columna.definicion, re.IGNORECASE):
            no_cluster = re.search(r"\bPRIMARY\s+KEY\s+NONCLUSTERED\b", columna.definicion, re.IGNORECASE)
            return [columna.nombre], not no_cluster, columna.posicion
    restriccion = re.search(
        r"\bPRIMARY\s+KEY\s*(CLUSTERED|NONCLUSTERED)?\s*\(([^)]*)\)",
        texto,
        re.IGNORECASE,
    )
    if restriccion:
        nombres = [
            _limpiar_identificador(re.sub(r"\s+(?:ASC|DESC)\s*$", "", n.strip(), flags=re.IGNORECASE))
            for n in restriccion.group(2).split(",") if n.strip()
        ]
        es_cluster = (restriccion.group(1) or "CLUSTERED").upper() == "CLUSTERED"
        return nombres, es_cluster, restriccion.start()
    return [], False, -1


# ---------------------------------------------------------------------------
# VALIDACIONES
# ---------------------------------------------------------------------------

def _validar_tabla(texto: str, esquema: Optional[str], tabla: str, referencia: str) -> List[Hallazgo]:
    hallazgos = []
    if not esquema:
        hallazgos.append(_hallazgo(
            texto, -1, "TABLA_SIN_ESQUEMA",
            f"La tabla {tabla} no indica su esquema. Escríbala como esquema.tabla (ej.: dbo.{tabla}).",
        ))
    if not _PASCAL_CASE.match(tabla):
        hallazgos.append(_hallazgo(
            texto, -1, "TABLA_NOMBRE_NO_PASCALCASE",
            f"El nombre de la tabla {tabla} no sigue el estándar: debe ir en PascalCase, cada palabra "
            f"con mayúscula inicial y sin guiones bajos ni espacios (ej.: Persona, CuentasPorPagar).",
        ))
    omitibles = sorted(set(_palabras_nombre_tabla(tabla)) & _PALABRAS_OMITIBLES_TABLA)
    if omitibles:
        hallazgos.append(_hallazgo(
            texto, -1, "TABLA_CON_PALABRA_OMITIBLE",
            f"El nombre de la tabla {tabla} contiene la palabra '{omitibles[0]}', que debe omitirse "
            f"según la nomenclatura.",
        ))
    return hallazgos


def _validar_clave_primaria(
    texto: str, tabla: str, referencia: str, columnas: List[ColumnaNueva]
) -> List[Hallazgo]:
    nombre_esperado = f"n{tabla}Id"
    pk, es_cluster, posicion = _clave_primaria(texto, columnas)
    if not pk:
        return [_hallazgo(
            texto, -1, "PK_FALTANTE",
            f"La tabla {referencia} no tiene clave primaria. Defina un índice clúster identidad "
            f"llamado {nombre_esperado}.",
        )]

    hallazgos = []
    if len(pk) > 1:
        hallazgos.append(_hallazgo(
            texto, posicion, "PK_COMPUESTA",
            f"La clave primaria de {referencia} usa varias columnas ({', '.join(pk)}). Debe ser una "
            f"sola columna identidad llamada {nombre_esperado}.",
        ))
    if not es_cluster:
        hallazgos.append(_hallazgo(
            texto, posicion, "PK_NO_CLUSTER",
            f"La clave primaria de {referencia} está definida como NONCLUSTERED. Debe ser el índice "
            f"clúster de la tabla.",
        ))
    if len(pk) > 1:
        return hallazgos

    nombre_pk = pk[0]
    # Si el nombre de la tabla no sigue el estándar, ese error ya se reporta y
    # el nombre esperado de la PK no tendría sentido (nTB_EstadoId).
    if _PASCAL_CASE.match(tabla) and nombre_pk != nombre_esperado:
        hallazgos.append(_hallazgo(
            texto, posicion, "PK_NOMBRE_INVALIDO",
            f"La clave primaria {nombre_pk} debe llamarse {nombre_esperado} (n + nombre de la tabla + Id).",
        ))
    columna_pk = next((c for c in columnas if c.nombre.upper() == nombre_pk.upper()), None)
    if columna_pk:
        if not re.search(r"\bIDENTITY\b", columna_pk.definicion, re.IGNORECASE):
            hallazgos.append(_hallazgo(
                texto, columna_pk.posicion, "PK_SIN_IDENTITY",
                f"La clave primaria {nombre_pk} no es IDENTITY. Debe ser una identidad de la tabla "
                f"(ej.: INT IDENTITY(1,1) NOT NULL).",
            ))
        if not re.search(rf"^\s*{_TIPOS_NUMERICOS}", columna_pk.definicion, re.IGNORECASE):
            hallazgos.append(_hallazgo(
                texto, columna_pk.posicion, "PK_NO_NUMERICA",
                f"La clave primaria {nombre_pk} es {_tipo_de_dato(columna_pk.definicion)}. De preferencia "
                f"debe ser numérica (INT o BIGINT).",
            ))
    return hallazgos


def _validar_columna(
    texto: str, columna: ColumnaNueva, referencia: str, es_dbcmaica: bool
) -> List[Hallazgo]:
    hallazgos = []
    definicion = columna.definicion
    prefijo = _prefijo_esperado(definicion)

    if prefijo and not columna.nombre.startswith(prefijo):
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_PREFIJO_TIPO_INVALIDO",
            f"La columna {columna.nombre} de {referencia} debe iniciar con '{prefijo}' porque su tipo "
            f"de dato es {_tipo_de_dato(definicion)}.",
        ))
    elif not _NOMBRE_COLUMNA.match(columna.nombre):
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_NOMBRE_NO_PASCALCASE",
            f"El nombre de la columna {columna.nombre} no sigue el estándar: después del prefijo debe ir "
            f"en PascalCase, sin guiones bajos (ej.: cPersonaNombre, dPersonaFechaNacimiento).",
        ))

    tiene_collate = re.search(r"\bCOLLATE\s+\w+", definicion, re.IGNORECASE)
    if _es_tipo_texto(definicion) and not es_dbcmaica and not tiene_collate:
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLUMNA_SIN_COLLATE",
            f"La columna {columna.nombre} de {referencia} debe definir COLLATE porque la tabla no "
            f"pertenece a DBCMAICA.",
        ))
    if not _es_tipo_texto(definicion) and tiene_collate:
        hallazgos.append(_hallazgo(
            texto, columna.posicion, "COLLATE_EN_TIPO_NO_TEXTO",
            f"La columna {columna.nombre} de {referencia} tiene COLLATE, pero COLLATE solo corresponde "
            f"a columnas de texto (CHAR o VARCHAR).",
        ))
    return hallazgos


def _tiene_not_null_o_default(definicion: str) -> bool:
    return bool(re.search(r"\bNOT\s+NULL\b|\bDEFAULT\b", definicion, re.IGNORECASE))


# ---------------------------------------------------------------------------
# ORQUESTADOR
# ---------------------------------------------------------------------------

def verificar_tabla(texto_sql: str, es_dbcmaica: bool = False) -> List[Hallazgo]:
    """Valida un CREATE TABLE o ALTER TABLE según el manual de nomenclatura."""
    texto = _sin_comentarios(texto_sql)
    base, esquema, tabla = extraer_objeto_tabla(texto)
    tipo = extraer_tipo_sentencia(texto)
    if tabla is None or tipo == "DESCONOCIDO":
        return []

    referencia = f"{esquema}.{tabla}" if esquema else tabla
    pertenece_a_dbcmaica = es_dbcmaica or (base or "").upper() == "DBCMAICA"
    hallazgos: List[Hallazgo] = []

    if tipo == "CREATE":
        columnas = _columnas_create(texto)
        hallazgos += _validar_tabla(texto, esquema, tabla, referencia)
        hallazgos += _validar_clave_primaria(texto, tabla, referencia, columnas)
        for columna in columnas:
            hallazgos += _validar_columna(texto, columna, referencia, pertenece_a_dbcmaica)
            # La PK y las columnas IDENTITY ya son NOT NULL implícitamente.
            implicita = re.search(r"\bPRIMARY\s+KEY\b|\bIDENTITY\b", columna.definicion, re.IGNORECASE)
            if not implicita and not _tiene_not_null_o_default(columna.definicion):
                hallazgos.append(_hallazgo(
                    texto, columna.posicion, "COLUMNA_SIN_NOT_NULL_NI_DEFAULT",
                    f"La columna {columna.nombre} de {referencia} debe ser NOT NULL o tener un valor DEFAULT.",
                ))
    else:
        for columna in _columnas_alter(texto):
            hallazgos += _validar_columna(texto, columna, referencia, pertenece_a_dbcmaica)
            if not _tiene_not_null_o_default(columna.definicion):
                hallazgos.append(_hallazgo(
                    texto, columna.posicion, "COLUMNA_NULL_EN_ALTER",
                    f"La columna {columna.nombre} se agrega permitiendo NULL. ¿Evaluó definir un valor por "
                    f"defecto (DEFAULT)? No se exige NOT NULL porque la tabla ya tiene registros.",
                ))

    # Las reglas desactivadas en el catálogo no se reportan.
    return [h for h in hallazgos if REGLAS_TABLAS[h.regla].activo]
