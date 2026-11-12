"""Código SQL comentado (compartido por Reportes y Negocio; mejora pedida por la usuaria, 8 nov.).

Además de las sentencias comentadas (--SELECT, --UPDATE, /* DELETE … */), detecta los restos de código que suelen
quedar al depurar, también a mitad de línea:

    SELECT -- TOP (10000)
    --THEN 'Apertura'
    --  Where cctacod = '108133041000273368'

Los comentarios que explican (-- 1. Hacia cuentas nuevas) no se marcan: tras las palabras de SQL que también
podrían iniciar una frase (WHERE, AND, TOP, THEN, SET...) se exige forma de código (una comparación, un número,
un texto entre comillas). Las variables de prueba y el EXEC de ejemplo no cuentan (comentarios_prueba).
"""

import re
from typing import List, Optional, Tuple

from app.analizadores.comentarios_prueba import es_bloque_de_prueba, nombre_del_procedimiento

_SENTENCIAS = r"SELECT|INSERT|UPDATE|DELETE|MERGE|EXEC(?:UTE)?|DECLARE|CREATE|ALTER|DROP|TRUNCATE|WHILE|GOTO"
_OBJETO = r"[\w.\[\]#@]+"
# Lado izquierdo de una condición: una columna (c.nEstado) o una función sobre ella (CAST(dFecha AS DATE)).
_EXPRESION = r"(?:[A-Za-z_@#][\w.\[\]]*\s*\([^()]*\)|[A-Za-z_@#][\w.\[\]]*)"
# Lado derecho: un texto, un número, una variable o una columna con su alias.
# (o una función: «--D.FECHAPROVISION = IIF(@bFiltro = 1, @dFecha, D.FECHAPROVISION) AND»; usuaria, 8 nov.).
_VALOR = r"(?:N?'[^']*'|-?\d+(?:\.\d+)?|@\w+|[A-Za-z_]\w*\s*\([^()]*\)|[A-Za-z_]\w*\.[\w\[\]]+)"

# Un comentario de línea con código: la sentencia o, para las palabras que podrían iniciar una frase, su forma de
# código (WHERE col = …, TOP (10), THEN 'x', JOIN tabla, SET @x = …).
# Una línea de encabezado «Etiqueta: valor» no es código: «-- Create date: 05-09-2012», «-- Update:», «-- Update
# date:» (plantilla de SSMS; caso de la usuaria, 11 nov.). Hasta tres palabras y los dos puntos.
_ETIQUETA = r"(?:[A-Za-zÁÉÍÓÚÑáéíóúñ]+[ \t]+){0,2}[A-Za-zÁÉÍÓÚÑáéíóúñ]+[ \t]*:(?!:)"

_CODIGO_EN_LINEA = re.compile(
    # Puede empezar con paréntesis: «--(case when CAST(…) in (select …) then …)» (caso de la usuaria, 8 nov.).
    rf"--\s*(?!{_ETIQUETA})(?:\(\s*)*(?:"
    rf"(?:{_SENTENCIAS})\b"
    rf"|CASE\s+WHEN\s+(?:(?:NOT\s+)?EXISTS\b|{_EXPRESION}\s*(?:=|<>|!=|<=|>=|<|>|\bIN\b|\bIS\b|\bLIKE\b|\bBETWEEN\b|\bNOT\b))"
    rf"|(?:WHERE|AND|OR|ON|HAVING)\s+{_OBJETO}\s*(?:=|<>|!=|<|>|\bIN\b|\bLIKE\b|\bIS\b|\bBETWEEN\b|\bNOT\b)"
    rf"|TOP\s*\(?\s*\d"
    rf"|(?:THEN|ELSE)\s+(?:'|\d|NULL\b)"
    rf"|(?:(?:INNER|CROSS)\s+|(?:LEFT|RIGHT|FULL)\s+(?:OUTER\s+)?)?JOIN\s+{_OBJETO}"
    rf"|FROM\s+{_OBJETO}"
    rf"|(?:ORDER|GROUP)\s+BY\s+[\w.\[\]@]"
    rf"|SET\s+@?[\w.]+\s*="
    rf"|UNION(?:\s+ALL)?\s*$"
    # Una condición suelta comentada: --CAST(dFecha AS DATE)='2024-01-08', --c.nEstado = 1, --A.cCta = @cCta.
    # Termina ahí (o sigue con AND/OR): «-- nEstado = 1 activo» es una explicación, no código.
    rf"|{_EXPRESION}\s*(?:=|<>|!=|<=|>=)\s*{_VALOR}\s*(?:$|(?:AND|OR)\b)"
    rf")",
    re.IGNORECASE,
)
_CODIGO_EN_BLOQUE = re.compile(rf"/\*\s*(?!{_ETIQUETA})(?:{_SENTENCIAS})\b", re.IGNORECASE)


def _comentarios(texto: str) -> List[Tuple[int, str]]:
    """[(posición, texto)] de cada comentario (-- o /* */), sin confundir un «--» dentro de un texto ('...')."""
    resultado, i, n = [], 0, len(texto)
    while i < n:
        if texto[i] == "'":
            j = i + 1
            while j < n:
                if texto[j] == "'":
                    if texto.startswith("''", j):
                        j += 2
                        continue
                    break
                j += 1
            i = j + 1
        elif texto.startswith("--", i):
            fin = texto.find("\n", i)
            fin = n if fin < 0 else fin
            resultado.append((i, texto[i:fin]))
            i = fin
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            fin = n if fin < 0 else fin + 2
            resultado.append((i, texto[i:fin]))
            i = fin
        else:
            i += 1
    return resultado


def comentarios_con_codigo(texto: str) -> List[int]:
    """Posiciones de los comentarios que contienen código SQL (sin las variables de prueba ni el EXEC de ejemplo)."""
    procedimiento = nombre_del_procedimiento(texto)
    posiciones = []
    for posicion, comentario in _comentarios(texto):
        patron = _CODIGO_EN_LINEA if comentario.startswith("--") else _CODIGO_EN_BLOQUE
        if not patron.match(comentario.rstrip()):
            continue
        if es_bloque_de_prueba(texto, posicion, procedimiento):
            continue
        posiciones.append(posicion)
    return posiciones


# Texto de la usuaria (8 nov.), igual en Reportes y Negocio.
QUE_HACER_CODIGO_COMENTADO = (
    "Retirar los comentarios innecesarios que ya no se utilizan, para mantener un código más limpio, ordenado y "
    "legible, facilitando su mantenimiento."
)


def codigo_comentado_agrupado(texto: str, linea_de) -> Optional[Tuple[int, str, List[int]]]:
    """Una sola observación con todas las líneas comentadas: (posición, mensaje, líneas) o None."""
    posiciones = comentarios_con_codigo(texto)
    if not posiciones:
        return None
    lineas = sorted({linea_de(posicion) for posicion in posiciones})
    problema = ("Se encontró una línea de código SQL comentada dentro del procedimiento." if len(lineas) == 1 else
                "Se encontraron líneas de código SQL comentadas dentro del procedimiento.")
    return posiciones[0], f"{problema} {QUE_HACER_CODIGO_COMENTADO}", lineas
