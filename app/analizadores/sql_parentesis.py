# -*- coding: utf-8 -*-
"""Paréntesis en el SQL (compartido por Reportes y Procedimientos de negocio)."""


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
