# -*- coding: utf-8 -*-
"""Variables declaradas que nunca se usan (compartido por Reportes y Procedimientos de negocio).

Una variable se usa cuando se LEE al menos una vez. Si solo se declara o solo recibe valores, no se usa:

    DECLARE @a INT = 1, @b INT = 2         <- @b se declara en el mismo DECLARE y nunca se lee
    SET @n = 5                             <- @n solo recibe un valor
    SELECT @dMax = MAX(dFecha) FROM …      <- @dMax solo recibe un valor
    INSERT INTO @T (nId) VALUES (1)        <- @T solo recibe filas; nunca se consulta

`limpio` es el SQL sin comentarios ni textos entre comillas (del mismo largo que el original).
"""

import re
from typing import Dict, List, Tuple

_VARIABLE = re.compile(r"@[A-Za-z_]\w*")
_TOKEN = re.compile(r"[(),;]|@[A-Za-z_]\w*|[A-Za-z_]\w*")
# Palabras que, fuera de paréntesis, empiezan otra sentencia: ahí termina el DECLARE.
_FIN_DEL_DECLARE = {
    "SELECT", "SET", "IF", "ELSE", "WHILE", "INSERT", "UPDATE", "DELETE", "DECLARE", "BEGIN", "END", "EXEC",
    "EXECUTE", "CREATE", "DROP", "ALTER", "PRINT", "RETURN", "WITH", "MERGE", "TRUNCATE", "OPEN", "FETCH",
    "CLOSE", "DEALLOCATE", "GOTO", "RAISERROR", "THROW", "GO",
}
# Antes de una variable que RECIBE un valor (seguida de «=», «+=»…): SET @x =, SELECT @x =, SELECT TOP 1 @x =,
# «, @x =» en la lista del SELECT o del UPDATE … SET, y EXEC @x = dbo.PA_….
_ANTES_DE_ASIGNACION = re.compile(
    r"(?:\bSET|\bSELECT(?:\s+DISTINCT)?(?:\s+TOP\s*\(?\s*\d+\s*\)?)?|,|\bEXEC(?:UTE)?)\s*$", re.IGNORECASE
)
_ASIGNACION = re.compile(r"\s*[-+*/%&|^]?=(?!=)")
# Antes de una tabla (o variable) que RECIBE filas: INSERT [INTO] @T, UPDATE @T, DELETE [FROM] @T,
# OUTPUT … INTO @T y FETCH … INTO @a, @b.
_ANTES_DE_ESCRITURA = re.compile(
    r"(?:\bINSERT(?:\s+INTO)?|\bUPDATE|\bDELETE(?:\s+FROM)?|\bINTO(?:\s+@[A-Za-z_]\w*\s*,)*)\s*$", re.IGNORECASE
)


def declaraciones(limpio: str) -> Dict[str, int]:
    """{variable: posición} de cada variable declarada (también varias en un DECLARE: @a INT, @b INT)."""
    encontradas: Dict[str, int] = {}
    vistas = set()
    for declare in re.finditer(r"\bDECLARE\b", limpio, re.IGNORECASE):
        profundidad, casos, espera_nombre = 0, 0, True
        for token in _TOKEN.finditer(limpio, declare.end()):
            valor = token.group(0)
            palabra = valor.upper()
            if valor == "(":
                profundidad += 1
            elif valor == ")":
                profundidad -= 1
                if profundidad < 0:
                    break
            elif profundidad > 0:
                continue
            elif valor == ";":
                break
            elif valor == ",":
                espera_nombre = True
            elif valor.startswith("@"):
                if espera_nombre and valor.lower() not in vistas:
                    vistas.add(valor.lower())
                    encontradas[valor] = token.start()
                espera_nombre = False
            elif palabra == "CASE":
                casos += 1
            elif palabra == "END" and casos:
                casos -= 1
            elif palabra in _FIN_DEL_DECLARE:
                break
            else:
                espera_nombre = False
    return encontradas


def _se_lee(limpio: str, inicio: int, fin: int) -> bool:
    """True si la variable que está en limpio[inicio:fin] se lee ahí (no solo recibe un valor o filas)."""
    previo = limpio[max(0, inicio - 200):inicio]
    if _ASIGNACION.match(limpio, fin) and _ANTES_DE_ASIGNACION.search(previo):
        return False
    return not _ANTES_DE_ESCRITURA.search(previo)


def variables_sin_uso(limpio: str, asignar_es_usar: bool = False) -> List[Tuple[str, int]]:
    """[(variable, posición de su declaración)] de las variables que nunca se leen.

    asignar_es_usar (Procedimientos de negocio, regla de la usuaria): la variable se usa si vuelve a aparecer
    después de su DECLARE, aunque solo reciba un valor (SET @x = …, SELECT @x = …); se observa solo la que se
    declara y nunca más aparece.
    """
    resultado = []
    for variable, posicion in declaraciones(limpio).items():
        patron = re.compile(rf"(?<![\w@]){re.escape(variable)}(?!\w)", re.IGNORECASE)
        lecturas = (
            m for m in patron.finditer(limpio, posicion + len(variable))
            if asignar_es_usar or _se_lee(limpio, m.start(), m.end())
        )
        if next(lecturas, None) is None:
            resultado.append((variable, posicion))
    return resultado
