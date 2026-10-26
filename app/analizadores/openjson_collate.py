# -*- coding: utf-8 -*-
"""COLLATE innecesario en el WITH de OPENJSON (compartido por Reportes y Procedimientos de negocio).

Las columnas que se definen en OPENJSON(...) WITH (...) toman por defecto el COLLATE de la base de
datos, así que indicarlo sobra:

    FROM OPENJSON(@cJson)
    WITH (
        nTasaId INT,
        cSustento VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS   <- se observa
    )
"""

import re
from typing import List, Tuple

_OPENJSON = re.compile(r"\bOPENJSON\s*\(", re.IGNORECASE)
_WITH = re.compile(r"\s*WITH\s*\(", re.IGNORECASE)
_COLLATE = re.compile(r"\bCOLLATE\s+\w+", re.IGNORECASE)


def _cierre(texto: str, apertura: int) -> int:
    """Posición del paréntesis que cierra el que abre en `apertura` (o el final del texto)."""
    nivel = 0
    for i in range(apertura, len(texto)):
        if texto[i] == "(":
            nivel += 1
        elif texto[i] == ")":
            nivel -= 1
            if nivel == 0:
                return i
    return len(texto)


def _columnas(contenido: str, desplazamiento: int) -> List[Tuple[str, int, int]]:
    """(texto, inicio, fin) de cada columna del WITH, separadas por las comas de primer nivel."""
    columnas, inicio, nivel = [], 0, 0
    for i, caracter in enumerate(contenido + ","):
        if caracter == "(":
            nivel += 1
        elif caracter == ")":
            nivel -= 1
        elif caracter == "," and nivel == 0:
            columnas.append((contenido[inicio:i], desplazamiento + inicio, desplazamiento + i))
            inicio = i + 1
    return columnas


def bloques_with_openjson(limpio: str) -> List[Tuple[int, int]]:
    """(inicio, fin) del contenido de cada WITH (...) que acompaña a un OPENJSON."""
    bloques = []
    for openjson in _OPENJSON.finditer(limpio):
        fin_openjson = _cierre(limpio, openjson.end() - 1)
        con_with = _WITH.match(limpio, fin_openjson + 1)
        if con_with:
            apertura = con_with.end() - 1
            bloques.append((apertura + 1, _cierre(limpio, apertura)))
    return bloques


def collates_en_openjson(limpio: str) -> List[Tuple[int, List[str]]]:
    """
    [(posición del primer COLLATE, columnas con COLLATE)] por cada bloque WITH de OPENJSON que tenga
    columnas con COLLATE. `limpio`: el código sin comentarios ni textos (con las mismas posiciones).
    """
    resultado = []
    for inicio, fin in bloques_with_openjson(limpio):
        columnas, primera = [], None
        for texto, desde, _ in _columnas(limpio[inicio:fin], inicio):
            collate = _COLLATE.search(texto)
            nombre = re.match(r"\s*(\[[^\]]+\]|[A-Za-z_@#][\w$#]*)", texto)
            if collate and nombre:
                columnas.append(nombre.group(1).strip("[]"))
                primera = desde + collate.start() if primera is None else primera
        if columnas:
            resultado.append((primera, columnas))
    return resultado


def dentro_de_openjson(limpio: str, posicion: int) -> bool:
    """¿La posición cae dentro del WITH (...) de un OPENJSON?"""
    return any(inicio <= posicion < fin for inicio, fin in bloques_with_openjson(limpio))


def mensaje_collate_openjson(columnas: List[str]) -> str:
    """Texto aprobado por la usuaria."""
    if len(columnas) == 1:
        donde = f"en la columna {columnas[0]}"
    else:
        donde = f"en las columnas {', '.join(columnas[:-1])} y {columnas[-1]}"
    return (f"Se identificó el uso de COLLATE {donde} del bloque OPENJSON. Se recomienda retirarlo, ya que las "
            f"columnas definidas en el WITH de OPENJSON toman por defecto el COLLATE de la base de datos y no es "
            f"necesario indicarlo.")
