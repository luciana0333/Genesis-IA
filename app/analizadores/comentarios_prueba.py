# -*- coding: utf-8 -*-
"""Bloques comentados de prueba (compartido por Reportes y Procedimientos de negocio).

Para probar el cuerpo de un procedimiento sin ejecutarlo con EXEC, se copian sus parámetros como
variables con valores de prueba y luego se dejan comentados:

    --DECLARE
    --@FECHA DATE = '20260930',
    --@AGENCIAS VARCHAR(300) = '18'

o se deja un ejemplo de ejecución: --EXEC dbo.PA_Reporte_Sel_Saldos @dFecha = '20260930'.
No es código que dejó de usarse, así que no se marca como «Código SQL comentado». Si el bloque
tiene algo más (un SELECT ... FROM, un UPDATE, el EXEC de otro procedimiento), sí se marca.
"""

import re
from typing import List, Optional, Tuple

_ID = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)"
_NOMBRE_PROCEDIMIENTO = re.compile(
    rf"\b(?:CREATE(?:\s+OR\s+ALTER)?|ALTER)\s+PROC(?:EDURE)?\s+((?:{_ID}\s*\.\s*){{0,2}}{_ID})",
    re.IGNORECASE,
)
# Palabras con las que empieza una línea de código SQL (si no, la línea es texto explicativo).
_INICIO_SQL = re.compile(
    r"(?:SELECT|INSERT|UPDATE|DELETE|MERGE|FROM|WHERE|JOIN|INNER|LEFT|RIGHT|FULL|CROSS|OUTER|ON|AND|OR|"
    r"GROUP|ORDER|HAVING|UNION|CREATE|ALTER|DROP|TRUNCATE|EXEC|EXECUTE|DECLARE|SET|IF|ELSE|BEGIN|END|"
    r"WHILE|RETURN|WITH|CASE|WHEN|THEN|INTO|VALUES|PRINT|RAISERROR|THROW|COMMIT|ROLLBACK|USE|GO)\b",
    re.IGNORECASE,
)
_VALOR = r"(?:N?'(?:[^']|'')*'|-?\d+(?:\.\d+)?|NULL|GETDATE\s*\(\s*\)|@\w+)"
_TIPO = r"\w+(?:\s*\(\s*(?:\d+|MAX)(?:\s*,\s*\d+)?\s*\))?"
# Líneas propias de un bloque de prueba.
# Una variable de prueba: @FECHA DATE = '20260930' (el valor es opcional).
_VARIABLE = rf"@\w+\s+(?:AS\s+)?{_TIPO}(?:\s*=\s*{_VALOR})?"
_LINEAS_DE_PRUEBA = [
    # «DECLARE», «DECLARE @a DATE = '...', @b INT = 1», «@a DATE = '...',», «, @b INT»
    re.compile(rf"(?:DECLARE\b\s*)?,?\s*(?:{_VARIABLE}(?:\s*,\s*{_VARIABLE})*)?\s*[,;]?", re.IGNORECASE),
    re.compile(rf"(?:SET|SELECT)\s+@\w+\s*=\s*{_VALOR}\s*[,;]?", re.IGNORECASE),
]
_USE_O_GO = re.compile(r"(?:USE\s+\w+|GO)\s*;?", re.IGNORECASE)
_EXEC = re.compile(rf"EXEC(?:UTE)?\s+(?:@\w+\s*=\s*)?((?:{_ID}\s*\.\s*){{0,2}}{_ID})", re.IGNORECASE)


def _ultima_parte(nombre: str) -> str:
    return nombre.split(".")[-1].strip().strip("[]").upper()


def nombre_del_procedimiento(texto: str) -> Optional[str]:
    m = _NOMBRE_PROCEDIMIENTO.search(texto or "")
    return _ultima_parte(m.group(1)) if m else None


def _bloque_de_guiones(texto: str, posicion: int) -> Tuple[int, int]:
    """Líneas seguidas comentadas con -- que rodean la posición: (inicio, fin)."""
    lineas = texto.split("\n")
    numero = texto.count("\n", 0, posicion)
    es_comentada = lambda i: lineas[i].lstrip().startswith("--")  # noqa: E731
    desde = numero
    while desde > 0 and es_comentada(desde - 1):
        desde -= 1
    hasta = numero
    while hasta + 1 < len(lineas) and es_comentada(hasta + 1):
        hasta += 1
    return desde, hasta


def _es_de_prueba(lineas: List[str], procedimiento: Optional[str]) -> bool:
    """Todas las líneas con código son DECLARE/variables/SET de prueba o el EXEC del mismo procedimiento."""
    hay_prueba = False
    for linea in lineas:
        linea = linea.strip().rstrip(";").strip()
        if not linea:
            continue
        # «EXEC dbo.PA_X @dFecha = '20260930', @cAgencia = '18'»: solo el del mismo procedimiento.
        ejecucion = _EXEC.match(linea)
        if ejecucion:
            if not procedimiento or _ultima_parte(ejecucion.group(1)) != procedimiento:
                return False
            hay_prueba = True
            continue
        if _USE_O_GO.fullmatch(linea):
            continue
        if any(patron.fullmatch(linea) for patron in _LINEAS_DE_PRUEBA):
            hay_prueba = True
            continue
        if _INICIO_SQL.match(linea):
            return False
        # Texto explicativo («Prueba», «Ejemplo de ejecución:»): no cambia nada.
    return hay_prueba


def es_bloque_de_prueba(texto: str, posicion: int, procedimiento: Optional[str]) -> bool:
    """¿El comentario que empieza en `posicion` (-- o /* */) es un bloque de variables de prueba?"""
    if texto.startswith("/*", posicion):
        fin = texto.find("*/", posicion)
        contenido = texto[posicion + 2:fin if fin >= 0 else len(texto)]
        return _es_de_prueba(contenido.split("\n"), procedimiento)
    desde, hasta = _bloque_de_guiones(texto, posicion)
    lineas = texto.split("\n")[desde:hasta + 1]
    return _es_de_prueba([linea.lstrip()[2:] for linea in lineas], procedimiento)
