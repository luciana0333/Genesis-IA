# -*- coding: utf-8 -*-
"""Variables declaradas que nunca se usan (compartido por Reportes y Procedimientos de negocio).

Regla de la usuaria (30 oct.): una variable se usa si vuelve a aparecer después de su DECLARE, aunque solo
reciba un valor. Se observa solo la que se declara y nunca más aparece:

    DECLARE @a INT = 1, @b INT = 2         <- @b se declara y nunca más aparece: se observa
    SET @n = 5                             <- @n vuelve a aparecer: ya tiene uso

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


def variables_sin_uso(limpio: str) -> List[Tuple[str, int]]:
    """[(variable, posición de su declaración)] de las variables que nunca más aparecen después del DECLARE."""
    resultado = []
    for variable, posicion in declaraciones(limpio).items():
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
