# -*- coding: utf-8 -*-
"""Paréntesis en el SQL (compartido por Reportes y Procedimientos de negocio)."""

import re
from typing import Optional, Tuple

_NOMBRE = re.compile(r"[\w.\[\]@#]+$")
# Palabras que no son una columna ni una función: lo que va antes del IN no se reconoce.
_NO_ES_EXPRESION = {"WHERE", "AND", "OR", "ON", "WHEN", "NOT", "HAVING", "SELECT", "SET", "IF", "WHILE", "CASE"}


def expresion_antes(texto: str, posicion: int) -> Optional[Tuple[int, str]]:
    """
    Columna o función que termina justo antes de `posicion` (la que se compara con IN, =...), con su
    inicio: «c.cEstado», «UPPER(cRhCod)», «LEFT(cRhCod, 1)». None si no se reconoce.
    """
    fin = len(texto[:posicion].rstrip())
    inicio = fin
    if fin and texto[fin - 1] == ")":
        nivel = 0
        for indice in range(fin - 1, -1, -1):
            nivel += {")": 1, "(": -1}.get(texto[indice], 0)
            if nivel == 0:
                inicio = indice
                break
        else:
            return None
    nombre = _NOMBRE.search(texto[:inicio].rstrip() if inicio < fin else texto[:inicio])
    if not nombre:
        return None
    if nombre.group(0).upper() in _NO_ES_EXPRESION:
        return None
    return nombre.start(), texto[nombre.start():fin]


def sin_parentesis_cerrados(texto: str) -> str:
    """
    El texto con los paréntesis ya cerrados (y su contenido) en blanco: subconsultas, funciones,
    VARCHAR(10). Conserva el largo, así las posiciones siguen valiendo. Sirve para saber en qué cláusula está algo sin que cuente lo de una subconsulta:

        WHERE a.n IN (SELECT n FROM B) AND a.c COLLATE …   ->   la cláusula es WHERE, no FROM
    """
    caracteres, abiertos = list(texto), []
    for indice, caracter in enumerate(texto):
        if caracter == "(":
            abiertos.append(indice)
        elif caracter == ")" and abiertos:
            inicio = abiertos.pop()
            caracteres[inicio:indice + 1] = " " * (indice - inicio + 1)
    return "".join(caracteres)
