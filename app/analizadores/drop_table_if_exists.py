# -*- coding: utf-8 -*-
"""Validación antes de DROP TABLE de una temporal (compartido por Reportes y Procedimientos de negocio).

    IF OBJECT_ID('tempdb..#temporal') IS NOT NULL
        DROP TABLE #temporal;

o con IF EXISTS (SELECT ... FROM tempdb..sysobjects ...) DROP TABLE #temporal: desde SQL Server 2016 se
escribe en una sola instrucción, DROP TABLE IF EXISTS #temporal, que no genera error si la tabla no existe.
"""

import re
from typing import List, Tuple

_SIN_COMENTARIOS = re.compile(r"--[^\n]*|/\*[\s\S]*?\*/")
_IF_OBJECT_ID = re.compile(r"\bIF\s+OBJECT_ID\s*\(", re.IGNORECASE)
_IF_EXISTS = re.compile(r"\bIF\s+(?:NOT\s+)?EXISTS\s*\(", re.IGNORECASE)
_DROP = re.compile(r"\s*(?:BEGIN\s+)?DROP\s+TABLE\s+(#[\w#$]+)", re.IGNORECASE)
_NO_NULO = re.compile(r"\s*IS\s+NOT\s+NULL", re.IGNORECASE)


def _cierre(texto: str, apertura: int) -> int:
    """Posición del paréntesis que cierra el que abre en `apertura` (respeta textos entre comillas)."""
    nivel, en_texto = 0, False
    for i in range(apertura, len(texto)):
        caracter = texto[i]
        if caracter == "'":
            en_texto = not en_texto
        elif en_texto:
            continue
        elif caracter == "(":
            nivel += 1
        elif caracter == ")":
            nivel -= 1
            if nivel == 0:
                return i
    return -1


def validaciones_antes_de_drop(texto: str) -> List[Tuple[int, str, str]]:
    """
    [(posición, tabla temporal, forma)] de cada IF OBJECT_ID(...) IS NOT NULL / IF EXISTS (... tempdb ...)
    seguido de DROP TABLE #temporal. `forma`: «OBJECT_ID» o «EXISTS».
    """
    codigo = _SIN_COMENTARIOS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto or "")
    encontradas = []
    for patron, forma in ((_IF_OBJECT_ID, "OBJECT_ID"), (_IF_EXISTS, "EXISTS")):
        for inicio in patron.finditer(codigo):
            cierre = _cierre(codigo, inicio.end() - 1)
            if cierre < 0:
                continue
            contenido = codigo[inicio.end():cierre]
            despues = cierre + 1
            if forma == "OBJECT_ID":
                if "#" not in contenido:
                    continue  # solo tablas temporales
                no_nulo = _NO_NULO.match(codigo, despues)
                if not no_nulo:
                    continue
                despues = no_nulo.end()
            elif "TEMPDB" not in contenido.upper() or inicio.group(0).upper().replace(" ", "").startswith("IFNOT"):
                continue
            drop = _DROP.match(codigo, despues)
            if drop:
                encontradas.append((inicio.start(), drop.group(1), forma))
    return sorted(encontradas)


# EXEC de un procedimiento que elimina temporales (PA_NET_EliminaTablaTemporal, PA_EliminaTemporal...):
# nombre con «Elimina...Temporal» o «Drop...Temp», y sus argumentos hasta el fin de la línea o el «;».
_EXEC_ELIMINA_TEMPORAL = re.compile(
    r"\bEXEC(?:UTE)?\s+(?P<proc>(?:\[?\w+\]?\s*\.\s*){0,2}\[?\w*(?:Elimina\w*Temp|Drop\w*Temp)\w*\]?)"
    r"(?P<args>[^;\n]*)",
    re.IGNORECASE,
)
_TEMPORAL_EN_TEXTO = re.compile(r"'[^']*?(#[\w#$]+)[^']*'")


def eliminaciones_con_procedimiento(texto: str) -> List[Tuple[int, str, str]]:
    """
    [(posición, procedimiento, tabla temporal)] de cada EXEC a un procedimiento que elimina una tabla
    temporal que se le pasa como texto ('TEMPDB.dbo.#TempXml'). Sin la tabla en el texto (por ejemplo,
    en una variable) no se marca: no se sabe si es una temporal.
    """
    codigo = _SIN_COMENTARIOS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto or "")
    encontradas = []
    for llamada in _EXEC_ELIMINA_TEMPORAL.finditer(codigo):
        procedimiento = re.sub(r"[\s\[\]]", "", llamada.group("proc"))
        for tabla in _TEMPORAL_EN_TEXTO.finditer(llamada.group("args")):
            encontradas.append((llamada.start(), procedimiento, tabla.group(1)))
    return encontradas


def mensaje_eliminacion_con_procedimiento(casos: List[Tuple[int, str, str]]) -> str:
    """Una sola observación con todas las tablas; el «Qué hacer» es el texto de la usuaria."""
    procedimientos = list(dict.fromkeys(procedimiento for _, procedimiento, _ in casos))
    tablas = list(dict.fromkeys(tabla for _, _, tabla in casos))
    uso = (f"del procedimiento {procedimientos[0]}" if len(procedimientos) == 1
           else f"de los procedimientos {_enumerar(procedimientos)}")
    sobre = (f"la tabla temporal {tablas[0]}" if len(tablas) == 1
             else f"las tablas temporales {_enumerar(tablas)}")
    return (f"Se identificó el uso {uso} para eliminar {sobre}. Se recomienda evitar el uso de procedimientos "
            f"almacenados para la eliminación de tablas temporales y optar por el uso de DROP TABLE IF EXISTS.")


def _enumerar(partes: List[str]) -> str:
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} y {partes[-1]}"


def mensaje_drop_if_exists(casos: List[Tuple[int, str, str]]) -> str:
    """Texto de la usuaria: una sola observación con todas las tablas."""
    tablas = list(dict.fromkeys(tabla for _, tabla, _ in casos))
    formas = list(dict.fromkeys(f"IF {forma}" for _, _, forma in casos))
    uso = " e ".join(formas)  # «IF OBJECT_ID», «IF EXISTS» o «IF OBJECT_ID e IF EXISTS»
    sobre = f"la tabla {tablas[0]}" if len(tablas) == 1 else f"las tablas {_enumerar(tablas)}"
    return (f"Se identificó el uso de {uso} sobre {sobre}. Se recomienda utilizar DROP TABLE IF EXISTS en lugar de "
            f"{uso}, ya que esta instrucción verifica si la tabla existe y la elimina en un solo paso, simplificando "
            f"el código y evitando errores si la tabla no existe.")
