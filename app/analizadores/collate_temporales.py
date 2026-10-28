# -*- coding: utf-8 -*-
"""Columna de texto sin COLLATE en tabla temporal (compartido por Reportes y Procedimientos de negocio).

Toda columna de texto de una tabla temporal (#T) o de una variable de tabla (@T) debe declarar el
COLLATE de la empresa:

    DECLARE @Control TABLE (
        cControl VARCHAR(100),                                        <- se observa
        cNivel CHAR(1) COLLATE SQL_Latin1_General_CP1_CI_AS           <- correcto
    )
"""

import re
from typing import List, Tuple

_IDENTIFICADOR = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_TABLA = re.compile(
    r"\b(?:CREATE\s+TABLE\s+(#[A-Za-z_][\w$#]*)|DECLARE\s+(@[A-Za-z_]\w*)\s+(?:AS\s+)?TABLE)\s*\(",
    re.IGNORECASE,
)
_COLLATE = re.compile(r"\bCOLLATE\s+\w+", re.IGNORECASE)

ACCION_COLLATE_TEMPORAL = (
    "Se recomienda añadir el COLLATE establecido en las columnas de tipo texto de las tablas temporales. "
    "Por favor, revisar y aplicarlo donde corresponda."
)


def _contenido(texto: str, apertura: int) -> str:
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


def _por_comas(contenido: str) -> List[Tuple[str, int]]:
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


def columnas_sin_collate(limpio: str) -> List[Tuple[int, str]]:
    """(posición de la columna, mensaje) de cada columna de texto de #T o @T sin COLLATE."""
    resultado = []
    for match in _TABLA.finditer(limpio):
        tabla = match.group(1) or match.group(2)
        tipo_tabla = "la tabla temporal" if match.group(1) else "la variable de tabla"
        apertura = match.end() - 1
        for definicion, desplazamiento in _por_comas(_contenido(limpio, apertura)):
            columna = re.match(rf"\s*({_IDENTIFICADOR})\s+{_TIPOS_TEXTO}", definicion, re.IGNORECASE)
            if not columna or _COLLATE.search(definicion):
                continue
            resultado.append((
                apertura + 1 + desplazamiento + columna.start(1),
                f"La columna de texto {columna.group(1)} de {tipo_tabla} {tabla} no define COLLATE. "
                f"{ACCION_COLLATE_TEMPORAL}",
            ))
    return resultado
