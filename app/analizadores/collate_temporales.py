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
from typing import Callable, Dict, List, Optional, Tuple

_IDENTIFICADOR = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)"
_TIPOS_TEXTO = r"(?:N?VARCHAR|N?CHAR|TEXT|NTEXT)\b"
_TABLA = re.compile(
    r"\b(?:CREATE\s+TABLE\s+(#[A-Za-z_][\w$#]*)|DECLARE\s+(@[A-Za-z_]\w*)\s+(?:AS\s+)?TABLE)\s*\(",
    re.IGNORECASE,
)
_COLLATE = re.compile(r"\bCOLLATE\s+\w+", re.IGNORECASE)

# Texto de la usuaria (7 nov.), igual en Negocio y Reportes.
ACCION_COLLATE_TEMPORAL = (
    "Se recomienda añadir el COLLATE correspondiente en las columnas de tipo texto de las tablas temporales. "
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


def columnas_sin_collate_por_tabla(limpio: str) -> List[Tuple[str, str, List[Tuple[int, str]]]]:
    """Por cada #T o @T con columnas de texto sin COLLATE: (tipo de tabla, tabla, [(posición, columna)])."""
    resultado = []
    for match in _TABLA.finditer(limpio):
        tabla = match.group(1) or match.group(2)
        tipo_tabla = "la tabla temporal" if match.group(1) else "la variable de tabla"
        apertura = match.end() - 1
        columnas = []
        for definicion, desplazamiento in _por_comas(_contenido(limpio, apertura)):
            columna = re.match(rf"\s*({_IDENTIFICADOR})\s+{_TIPOS_TEXTO}", definicion, re.IGNORECASE)
            if not columna or _COLLATE.search(definicion):
                continue
            columnas.append((apertura + 1 + desplazamiento + columna.start(1), columna.group(1)))
        if columnas:
            resultado.append((tipo_tabla, tabla, columnas))
    return resultado


def hecho_por_tabla(tipo_tabla: str, tabla: str, columnas: List[str]) -> str:
    """El mismo mensaje, agrupado por tabla: «Las columnas de texto A, B y C de la tabla temporal #T no definen
    COLLATE» (con una sola columna, el texto de siempre)."""
    if len(columnas) == 1:
        return f"La columna de texto {columnas[0]} de {tipo_tabla} {tabla} no define COLLATE"
    lista = f"{', '.join(columnas[:-1])} y {columnas[-1]}"
    return f"Las columnas de texto {lista} de {tipo_tabla} {tabla} no definen COLLATE"


def collate_agrupado(limpio: str, linea_de: Callable[[int], int]) -> Optional[Tuple[int, str, List[Dict], List[int]]]:
    """Una sola observación (Negocio y Reportes) con una viñeta por tabla y todas sus columnas sin COLLATE.

    Devuelve (posición, mensaje, grupos, líneas) o None. «grupos» permite a «Ver en el código» recorrer tabla
    por tabla, columna por columna. `linea_de` convierte una posición en su número de línea.
    """
    por_tabla = columnas_sin_collate_por_tabla(limpio)
    if not por_tabla:
        return None
    hechos = [hecho_por_tabla(tipo, tabla, [c for _, c in columnas]) for tipo, tabla, columnas in por_tabla]
    if len(hechos) == 1:
        mensaje = f"{hechos[0]}. {ACCION_COLLATE_TEMPORAL}"
    else:
        primeras = sorted({linea_de(columnas[0][0]) for _, _, columnas in por_tabla})
        donde = ("la línea " if len(primeras) == 1 else "las líneas ") + ", ".join(map(str, primeras))
        detalle = "; ".join(h[:1].lower() + h[1:] for h in hechos)
        mensaje = f"Se encontraron {len(hechos)} observaciones de este tipo, en {donde}: {detalle}. {ACCION_COLLATE_TEMPORAL}"
    grupos = [
        {"nombre": tabla, "tipo": "Tabla",
         "lineas": [linea_de(posicion) for posicion, _ in columnas],
         "etiquetas": [columna for _, columna in columnas]}
        for _, tabla, columnas in por_tabla
    ]
    return por_tabla[0][2][0][0], mensaje, grupos, [n for grupo in grupos for n in grupo["lineas"]]
