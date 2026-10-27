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


def _validacion(tabla: str, forma: str) -> str:
    if forma == "OBJECT_ID":
        return f"IF OBJECT_ID('tempdb..{tabla}') IS NOT NULL"
    return "IF EXISTS (SELECT … FROM tempdb…)"


def mensaje_drop_if_exists(casos: List[Tuple[int, str, str]], lineas: List[int]) -> str:
    """Texto aprobado por la usuaria (uno o varios casos)."""
    motivo = ("ya que elimina la tabla si existe en una sola instrucción y no genera error si la tabla no está "
              "creada.")
    if len(casos) == 1:
        _, tabla, forma = casos[0]
        return (f"Se identificó la validación {_validacion(tabla, forma)} para eliminar la tabla temporal {tabla}. "
                f"Se recomienda reemplazarla por DROP TABLE IF EXISTS {tabla}, {motivo}")
    donde = ("la línea " if len(set(lineas)) == 1 else "las líneas ") + ", ".join(map(str, sorted(set(lineas))))
    detalle = "; ".join(f"{_validacion(tabla, forma)} para la tabla temporal {tabla}" for _, tabla, forma in casos)
    return (f"Se identificaron {len(casos)} validaciones antes de eliminar tablas temporales, en {donde}: {detalle}. "
            f"Se recomienda reemplazarlas por DROP TABLE IF EXISTS (ej.: DROP TABLE IF EXISTS {casos[0][1]}), {motivo}")
