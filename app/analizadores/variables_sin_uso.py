# -*- coding: utf-8 -*-
"""Variables declaradas que nunca se usan (compartido por Reportes y Procedimientos de negocio).

Regla de la usuaria (30 oct.): una variable se usa si vuelve a aparecer después de su DECLARE, aunque solo
reciba un valor. Se observa solo la que se declara y nunca más aparece:

    DECLARE @a INT = 1, @b INT = 2         <- @b se declara y nunca más aparece: se observa
    SET @n = 5                             <- @n vuelve a aparecer: ya tiene uso
    DECLARE @T TABLE (n INT)               <- variable de tabla: no se revisa en esta regla

Los comentarios y los textos entre comillas no cuentan: `limpio` es el SQL sin ellos (del mismo largo).
"""

import re
from typing import Dict, List, Tuple

_TOKEN = re.compile(r"[(),;]|@[A-Za-z_]\w*|[A-Za-z_]\w*")
# Palabras que, fuera de paréntesis, empiezan otra sentencia: ahí termina el DECLARE.
_FIN_DEL_DECLARE = {
    "SELECT", "SET", "IF", "ELSE", "WHILE", "INSERT", "UPDATE", "DELETE", "DECLARE", "BEGIN", "END", "EXEC",
    "EXECUTE", "CREATE", "DROP", "ALTER", "PRINT", "RETURN", "WITH", "MERGE", "TRUNCATE", "OPEN", "FETCH",
    "CLOSE", "DEALLOCATE", "GOTO", "RAISERROR", "THROW", "GO",
}
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


# Lo que sigue al nombre en una variable de tabla: DECLARE @T TABLE (…) o DECLARE @T AS TABLE (…).
_ES_VARIABLE_DE_TABLA = re.compile(r"\s+(?:AS\s+)?TABLE(?![\w$#])", re.IGNORECASE)


def variables_sin_uso(limpio: str) -> List[Tuple[str, int]]:
    """[(variable, posición de su declaración)] de las variables que nunca más aparecen después del DECLARE."""
    resultado = []
    for variable, posicion in declaraciones(limpio).items():
        # Solo variables comunes (DECLARE @n INT): una variable de tabla (DECLARE @T TABLE (…)) es otra cosa
        # y no se revisa aquí (pedido de la usuaria, 8 nov.).
        if _ES_VARIABLE_DE_TABLA.match(limpio, posicion + len(variable)):
            continue
        patron = re.compile(rf"(?<![\w@]){re.escape(variable)}(?!\w)", re.IGNORECASE)
        if not patron.search(limpio, posicion + len(variable)):
            resultado.append((variable, posicion))
    return resultado


def mensaje_variables_sin_uso(variables: List[str]) -> str:
    """Texto de la usuaria (31 oct.), igual en Reportes y Negocio; en singular si es una sola variable."""
    if len(variables) == 1:
        return (f"Se identificó una variable que ha sido declarada, pero no se utiliza dentro del procedimiento: "
                f"{variables[0]}. Se recomienda revisar la variable identificada y proceder con su eliminación si "
                f"no es necesaria, ya que no cumple ninguna función dentro del procedimiento.")
    lista = f"{', '.join(variables[:-1])} y {variables[-1]}"
    return (f"Se identificaron {len(variables)} variables que han sido declaradas, pero no se utilizan dentro del "
            f"procedimiento: {lista}. Se recomienda revisar las variables identificadas y proceder con su "
            f"eliminación si no son necesarias, ya que no cumplen ninguna función dentro del procedimiento.")


# «Variables de tabla declaradas sin uso» (usuaria, 8 nov.): una variable de tabla que después del DECLARE no se
# lee nunca (no aparece, o solo se llena, actualiza o borra). A diferencia de una temporal #, otro procedimiento no
# puede leerla: solo existe dentro de este.
_ESCRITURA_ANTES = re.compile(r"\b(?:INSERT(?:\s+INTO)?|UPDATE|DELETE(?:\s+FROM)?)\s*$", re.IGNORECASE)


def variables_de_tabla_sin_uso(limpio: str) -> List[Tuple[str, int]]:
    """[(variable, posición de su declaración)] de las variables de tabla que no se leen en ninguna parte."""
    from app.analizadores.temporal_sin_uso import _es_destino_de_alias

    resultado = []
    for variable, posicion in declaraciones(limpio).items():
        if not _ES_VARIABLE_DE_TABLA.match(limpio, posicion + len(variable)):
            continue
        patron = re.compile(rf"(?<![\w@]){re.escape(variable)}(?![\w$#])", re.IGNORECASE)
        leida = False
        for uso in patron.finditer(limpio, posicion + len(variable)):
            if _ESCRITURA_ANTES.search(limpio, max(0, uso.start() - 60), uso.start()):
                continue
            if _es_destino_de_alias(limpio, uso.start(), uso.end()):
                continue
            leida = True
            break
        if not leida:
            resultado.append((variable, posicion))
    return resultado


def mensaje_variables_de_tabla_sin_uso(variables: List[str]) -> str:
    """Texto de la usuaria (13 nov.); en singular si es una sola."""
    if len(variables) == 1:
        return (f"Se identificó que la variable de tipo tabla {variables[0]} está declarada en el procedimiento, pero "
                f"no se utiliza en ninguna parte del código. Se recomienda verificar si esta variable es necesaria y, "
                f"de no ser así, retirar su declaración para evitar código innecesario.")
    return (f"Se identificó que las siguientes variables de tipo tabla están declaradas en el procedimiento, pero no "
            f"se utilizan en ninguna parte del código: {'; '.join(variables)}. Se recomienda verificar si estas "
            f"variables son necesarias y, de no ser así, retirar sus declaraciones para evitar código innecesario.")
