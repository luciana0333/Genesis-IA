# -*- coding: utf-8 -*-
"""Lectura de las columnas de cada ORDER BY (compartida por Reportes y Procedimientos de negocio).

La lista se separa solo por las comas de su propio nivel: las comas dentro de una función
(SUBSTRING(cMovNro, 1, 14), CONVERT(...)) no separan columnas, así que sus números no se
confunden con un orden por posición. La lista termina en un «)» sin abrir (el OVER(...) de
ROW_NUMBER), en «;» o en la siguiente cláusula o sentencia.
"""

import re
from typing import List, Tuple

_ORDER_BY = re.compile(r"\bORDER\s+BY\b", re.IGNORECASE)
_FIN = re.compile(
    r"\b(?:OFFSET|FOR|OPTION|UNION|EXCEPT|INTERSECT|END|SELECT|INSERT|UPDATE|DELETE|RETURN|GO|"
    r"ROWS|RANGE|FROM|WHERE|SET|IF|ELSE|BEGIN|DECLARE|EXEC|EXECUTE|WITH)\b",
    re.IGNORECASE,
)
_POSICION = re.compile(r"\s*(\d+)\s*(?:ASC|DESC)?\s*", re.IGNORECASE)


def _columnas(resto: str) -> List[str]:
    """Columnas de la lista que empieza en `resto`, separadas por las comas de primer nivel."""
    columnas, actual, nivel, i = [], [], 0, 0
    while i < len(resto):
        caracter = resto[i]
        if caracter == "(":
            nivel += 1
        elif caracter == ")":
            if nivel == 0:
                break
            nivel -= 1
        elif nivel == 0:
            if caracter == ";":
                break
            if caracter == ",":
                columnas.append("".join(actual))
                actual = []
                i += 1
                continue
            fin = _FIN.match(resto, i)
            if fin and (i == 0 or not (resto[i - 1].isalnum() or resto[i - 1] in "_@#.")):
                break
        actual.append(caracter)
        i += 1
    columnas.append("".join(actual))
    return columnas


def order_by_por_posicion(limpio: str) -> List[Tuple[int, List[str]]]:
    """
    [(posición del ORDER BY, números de columna)] de cada ORDER BY que ordena por la posición
    de la columna (ORDER BY 1, 2 DESC). `limpio`: el código sin comentarios ni textos.
    """
    resultado = []
    for match in _ORDER_BY.finditer(limpio):
        posiciones = [m.group(1) for m in map(_POSICION.fullmatch, _columnas(limpio[match.end():])) if m]
        if posiciones:
            resultado.append((match.start(), posiciones))
    return resultado
