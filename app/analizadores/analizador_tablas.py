# -*- coding: utf-8 -*-
"""Valida reglas estructurales para sentencias CREATE y ALTER TABLE."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad


_IDENTIFICADOR = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#@]*)"
_PALABRAS_NO_COLUMNA = {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY"}
_PREFIJOS_TIPO = (
    ("c", r"(?:N?VARCHAR|N?CHAR)\b"),
    ("n", r"(?:BIGINT|SMALLINT|TINYINT|INT|MONEY|DECIMAL|NUMERIC)\b"),
    ("b", r"BIT\b"),
    ("d", r"(?:DATE|DATETIME|DATETIME2|SMALLDATETIME)\b"),
)
_PALABRAS_OMITIBLES_TABLA = {"de", "del", "la", "el", "los", "las", "mi", "mis", "su", "sus"}


@dataclass
class ColumnaNueva:
    nombre: str
    definicion: str
    posicion: int


def _limpiar_identificador(valor: str) -> str:
    return valor[1:-1] if valor.startswith("[") and valor.endswith("]") else valor


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _palabras_nombre_tabla(nombre: str) -> List[str]:
    """Separa nombres PascalCase para revisar palabras omitibles."""
    return [parte.lower() for parte in re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", nombre)]


def _prefijo_esperado(definicion: str) -> Optional[str]:
    for prefijo, patron_tipo in _PREFIJOS_TIPO:
        if re.search(rf"^\s*{patron_tipo}", definicion, re.IGNORECASE):
            return prefijo
    return None


def _es_tipo_texto(definicion: str) -> bool:
    return bool(re.search(r"^\s*(?:N?VARCHAR|N?CHAR)\b", definicion, re.IGNORECASE))


def extraer_objeto_tabla(texto_sql: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Devuelve (base_de_datos, esquema, tabla) del nombre de la tabla."""
    patron = re.compile(
        rf"\b(?:CREATE|ALTER)\s+TABLE\s+((?:{_IDENTIFICADOR}\.){{0,2}}{_IDENTIFICADOR})",
        re.IGNORECASE,
    )
    coincidencia = patron.search(texto_sql)
    if not coincidencia:
        return None, None, None

    partes = [_limpiar_identificador(p) for p in coincidencia.group(1).split(".")]
    if len(partes) == 3:
        return partes[0], partes[1], partes[2]
    if len(partes) == 2:
        return None, partes[0], partes[1]
    return None, None, partes[0]


def extraer_tipo_sentencia(texto_sql: str) -> str:
    if re.search(r"\bALTER\s+TABLE\b", texto_sql, re.IGNORECASE):
        return "ALTER"
    if re.search(r"\bCREATE\s+TABLE\b", texto_sql, re.IGNORECASE):
        return "CREATE"
    return "DESCONOCIDO"


def _separar_por_comas(contenido: str) -> List[Tuple[str, int]]:
    segmentos = []
    inicio = 0
    profundidad = 0
    for indice, caracter in enumerate(contenido):
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad = max(0, profundidad - 1)
        elif caracter == "," and profundidad == 0:
            segmentos.append((contenido[inicio:indice], inicio))
            inicio = indice + 1
    segmentos.append((contenido[inicio:], inicio))
    return segmentos


def _extraer_bloque_columnas(texto_sql: str) -> Tuple[str, int]:
    inicio = re.search(r"\b(?:CREATE|ALTER)\s+TABLE\b.*?\(", texto_sql, re.IGNORECASE | re.DOTALL)
    if not inicio:
        return "", 0

    inicio_parentesis = inicio.end() - 1
    profundidad = 0
    for indice in range(inicio_parentesis + 1, len(texto_sql)):
        if texto_sql[indice] == "(":
            profundidad += 1
        elif texto_sql[indice] == ")":
            if profundidad == 0:
                return texto_sql[inicio_parentesis + 1:indice], inicio_parentesis + 1
            profundidad -= 1
    return texto_sql[inicio_parentesis + 1:], inicio_parentesis + 1


def _columnas_create(texto_sql: str) -> List[ColumnaNueva]:
    contenido, desplazamiento = _extraer_bloque_columnas(texto_sql)
    columnas = []
    for segmento, posicion in _separar_por_comas(contenido):
        coincidencia = re.match(rf"\s*({_IDENTIFICADOR})(.*)", segmento, re.IGNORECASE | re.DOTALL)
        if not coincidencia:
            continue
        nombre = _limpiar_identificador(coincidencia.group(1))
        if nombre.upper() in _PALABRAS_NO_COLUMNA:
            continue
        columnas.append(ColumnaNueva(nombre, coincidencia.group(2), desplazamiento + posicion + coincidencia.start(1)))
    return columnas


def _columnas_alter(texto_sql: str) -> List[ColumnaNueva]:
    coincidencia_add = re.search(r"\bADD\s+(?!CONSTRAINT\b)", texto_sql, re.IGNORECASE)
    if not coincidencia_add:
        return []

    inicio = coincidencia_add.end()
    contenido = texto_sql[inicio:]
    if contenido.lstrip().startswith("("):
        desplazamiento = inicio + len(contenido) - len(contenido.lstrip()) + 1
        contenido = contenido.lstrip()[1:]
    else:
        desplazamiento = inicio

    contenido = re.sub(r"\s*\)\s*;?\s*$", "", contenido, flags=re.DOTALL)
    columnas = []
    for segmento, posicion in _separar_por_comas(contenido):
        coincidencia_columna = re.match(rf"\s*({_IDENTIFICADOR})(.*)", segmento, re.IGNORECASE | re.DOTALL)
        if not coincidencia_columna:
            continue
        columnas.append(ColumnaNueva(
            _limpiar_identificador(coincidencia_columna.group(1)),
            coincidencia_columna.group(2),
            desplazamiento + posicion + coincidencia_columna.start(1),
        ))
    return columnas


def extraer_columnas_nuevas(texto_sql: str) -> List[ColumnaNueva]:
    tipo = extraer_tipo_sentencia(texto_sql)
    return _columnas_create(texto_sql) if tipo == "CREATE" else _columnas_alter(texto_sql)


def verificar_tabla(texto_sql: str, es_dbcmaica: bool = False) -> List[Hallazgo]:
    """Valida esquema, nulabilidad/default y COLLATE de columnas nuevas."""
    hallazgos: List[Hallazgo] = []
    base, esquema, tabla = extraer_objeto_tabla(texto_sql)
    if tabla is None or extraer_tipo_sentencia(texto_sql) == "DESCONOCIDO":
        return hallazgos

    referencia = f"{esquema}.{tabla}" if esquema else tabla
    if not esquema:
        hallazgos.append(Hallazgo(
            linea=1,
            origen=OrigenAnalisis.REGLAS_ESTATICAS,
            severidad=Severidad.ALTO,
            regla="TABLA_SIN_ESQUEMA",
            mensaje=f"La tabla {referencia} debe indicar explícitamente su esquema.",
        ))

    palabras_tabla = _palabras_nombre_tabla(tabla)
    palabras_omitibles = sorted(set(palabras_tabla) & _PALABRAS_OMITIBLES_TABLA)
    if palabras_omitibles:
        hallazgos.append(Hallazgo(
            linea=1,
            origen=OrigenAnalisis.REGLAS_ESTATICAS,
            severidad=Severidad.ALTO,
            regla="TABLA_CON_PALABRA_OMITIBLE",
            mensaje=(
                f"El nombre de la tabla {tabla} contiene la palabra "
                f"'{palabras_omitibles[0]}', que debe omitirse según la nomenclatura."
            ),
        ))

    pertenece_a_dbcmaica = es_dbcmaica or (base or "").upper() == "DBCMAICA"
    for columna in extraer_columnas_nuevas(texto_sql):
        definicion = columna.definicion
        prefijo_esperado = _prefijo_esperado(definicion)
        if prefijo_esperado and not columna.nombre.startswith(prefijo_esperado):
            hallazgos.append(Hallazgo(
                linea=_numero_linea(texto_sql, columna.posicion),
                origen=OrigenAnalisis.REGLAS_ESTATICAS,
                severidad=Severidad.ALTO,
                regla="COLUMNA_PREFIJO_TIPO_INVALIDO",
                mensaje=(
                    f"La columna {columna.nombre} de {referencia} debe iniciar "
                    f"con '{prefijo_esperado}' porque su tipo de dato es "
                    f"{definicion.strip().split()[0]}."
                ),
            ))
        if not re.search(r"\bNOT\s+NULL\b|\bDEFAULT\b", definicion, re.IGNORECASE):
            hallazgos.append(Hallazgo(
                linea=_numero_linea(texto_sql, columna.posicion),
                origen=OrigenAnalisis.REGLAS_ESTATICAS,
                severidad=Severidad.ALTO,
                regla="COLUMNA_SIN_NOT_NULL_NI_DEFAULT",
                mensaje=f"La columna {columna.nombre} de {referencia} debe tener NOT NULL o un valor DEFAULT.",
            ))
        if (
            _es_tipo_texto(definicion)
            and not pertenece_a_dbcmaica
            and not re.search(r"\bCOLLATE\s+\w+", definicion, re.IGNORECASE)
        ):
            hallazgos.append(Hallazgo(
                linea=_numero_linea(texto_sql, columna.posicion),
                origen=OrigenAnalisis.REGLAS_ESTATICAS,
                severidad=Severidad.ALTO,
                regla="COLUMNA_SIN_COLLATE",
                mensaje=f"La columna {columna.nombre} de {referencia} debe definir COLLATE porque la tabla no pertenece a DBCMAICA.",
            ))
        if not _es_tipo_texto(definicion) and re.search(r"\bCOLLATE\s+\w+", definicion, re.IGNORECASE):
            hallazgos.append(Hallazgo(
                linea=_numero_linea(texto_sql, columna.posicion),
                origen=OrigenAnalisis.REGLAS_ESTATICAS,
                severidad=Severidad.ALTO,
                regla="COLLATE_EN_TIPO_NO_TEXTO",
                mensaje=(
                    f"La columna {columna.nombre} de {referencia} tiene COLLATE, "
                    "pero COLLATE solo debe usarse en columnas CHAR o VARCHAR."
                ),
            ))
    return hallazgos