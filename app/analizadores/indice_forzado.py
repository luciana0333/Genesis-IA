"""Índice forzado: WITH (INDEX(IX_...)) o WITH (INDEX = IX_...) (compartido por Reportes y Negocio).

Se separa de «Hint de plan prohibido» (OPTION (RECOMPILE), LOOP JOIN...) con su propio título y su «Qué hacer»
(pedido de la usuaria, 7 nov.).
"""

import re
from typing import List, Optional, Tuple

_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_REFERENCIA = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"
_INDEX = re.compile(r"\bINDEX\s*(?:\(\s*([^)]*?)\s*\)|=\s*(\[[^\]]+\]|\w+))", re.IGNORECASE)
_TABLA_ANTES = re.compile(
    rf"\b(?:FROM|JOIN|UPDATE|INTO)\s+({_REFERENCIA})(?:\s+(?:AS\s+)?[A-Za-z_][\w$#]*)?\s*$", re.IGNORECASE,
)

# Texto de la usuaria (7 nov.), igual en Reportes y Negocio.
QUE_HACER_INDICE_FORZADO = (
    "Retirar los índices forzados y permitir que el optimizador determine el índice adecuado según las condiciones "
    "de cada consulta. Según nuestras buenas prácticas, se debe evitar el uso de indicaciones que obliguen al motor "
    "a ejecutar las consultas de una forma específica."
)


def indices_forzados(limpio: str) -> List[Tuple[int, str, str]]:
    """[(posición, índice, tabla)] de cada índice forzado como hint de tabla: WITH (INDEX(...)) o, en la forma
    antigua, «tabla (INDEX(...))». Un CREATE INDEX no es un hint."""
    resultado = []
    for match in _INDEX.finditer(limpio):
        abre = limpio.rfind("(", 0, match.start())
        # Dentro del paréntesis de hints de la tabla: antes del INDEX solo otros hints (NOLOCK, ...) y comas.
        if abre < 0 or not re.fullmatch(r"[\sA-Za-z_,]*", limpio[abre + 1:match.start()]):
            continue
        antes = limpio[max(0, abre - 300):abre]
        con_with = re.search(r"\bWITH\s*$", antes, re.IGNORECASE)
        antes_tabla = re.sub(r"\s*WITH\s*$", "", antes, flags=re.IGNORECASE)
        tabla = _TABLA_ANTES.search(antes_tabla)
        if not con_with and not tabla:
            continue
        indice = (match.group(1) or match.group(2) or "").strip()
        nombre = re.sub(r"\s*\.\s*", ".", tabla.group(1).strip()) if tabla else ""
        resultado.append((match.start(), indice, nombre))
    return resultado


def indice_forzado_agrupado(limpio: str, linea_de) -> Optional[Tuple[int, str, List[int]]]:
    """Una sola observación (opción A de la usuaria, 7 nov.): la frase una vez y, por viñeta, el índice y su tabla.

    «Se identificó que se obliga al motor a usar los siguientes índices: 'PK_X' en la tabla X; …». Con uno solo,
    en una línea. Devuelve (posición, mensaje, líneas) o None.
    """
    casos = indices_forzados(limpio)
    if not casos:
        return None

    def caso(indice: str, tabla: str) -> str:
        return f"'{indice}' en la tabla {tabla}" if tabla else f"'{indice}'"

    if len(casos) == 1:
        _, indice, tabla = casos[0]
        problema = f"Se identificó que se obliga al motor a usar el índice {caso(indice, tabla)}."
    else:
        vinetas = list(dict.fromkeys(caso(indice, tabla) for _, indice, tabla in casos))
        problema = f"Se identificó que se obliga al motor a usar los siguientes índices: {'; '.join(vinetas)}."
    lineas = sorted({linea_de(posicion) for posicion, _, _ in casos})
    return casos[0][0], f"{problema} {QUE_HACER_INDICE_FORZADO}", lineas
