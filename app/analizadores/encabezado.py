"""«Encabezado del procedimiento» (compartido por Reportes y Negocio; pedido de la usuaria, 8 nov.).

Todo procedimiento lleva al inicio su encabezado de documentación (antes del CREATE/ALTER, o justo después del
AS o del BEGIN):

    /*****************************************************************
    Nombre del PA  | Logistica.PA_Provision_Sel_OrdenesSicmac
    Descripción    | Procedimiento que lista las ordenes del sicmac
    Autor          | LMPE
    Fecha          | 04/08/2025
    ------------------------------------------------------------------
    Control de Cambios
    Fecha    | Autor    | Descripción
    ------------------------------------------------------------------
    exec LOGISTICA.PA_Provision_Sel_OrdenesSicmac @cOpeCod=N'702401'
    *****************************************************************/

Una sola regla: sin encabezado, o con datos que faltan (se nombran solo los que faltan). Se aceptan los nombres
que usa cada equipo (PROPÓSITO, CREADO POR, FECHA CREACIÓN, HISTORIAL DE CAMBIOS...).
"""

import re
from typing import List, Optional, Tuple

_PROCEDIMIENTO = re.compile(r"\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\b", re.IGNORECASE)
_COMENTARIO = re.compile(r"/\*[\s\S]*?(?:\*/|$)|--[^\n]*")

# Cada dato con su etiqueta y un valor en la misma línea («Autor | LMPE» o «Autor: LMPE»). La fila de títulos de
# «Control de Cambios» (Fecha | Autor | Descripción) no cuenta como valor: tras la etiqueta viene otra etiqueta.
_DESCRIPCION = r"(?:Descripci[oó]n|Prop[oó]sito|Objetivo)"
_AUTOR = r"(?:Autor|Creado\s+por|Elaborado\s+por|Desarrollado\s+por|Responsable)"
_ETIQUETAS = rf"(?:Nombre|{_DESCRIPCION}|{_AUTOR}|Fecha|Motivo)\b"
_EXEC = r"\bEXEC(?:UTE)?\s+[\w\[]"
_DATOS = (
    # El nombre puede ir en su propia línea o en el EXEC de ejemplo, que lo nombra.
    ("el nombre del procedimiento",
     re.compile(rf"\bNombre\b[^|:\n]*[|:]\s*(?!{_ETIQUETAS})[\w\[]|{_EXEC}", re.IGNORECASE)),
    ("la descripción", re.compile(rf"\b{_DESCRIPCION}\b[^|:\n]*[|:]\s*(?!{_ETIQUETAS})\w", re.IGNORECASE)),
    ("el autor", re.compile(rf"\b{_AUTOR}\b[^|:\n]*[|:]\s*(?!{_ETIQUETAS})\w", re.IGNORECASE)),
    ("la fecha", re.compile(r"\bFecha\b[^|:\n]*[|:]\s*[^|\n]*\d", re.IGNORECASE)),
    # El título («Control de Cambios», «Historial de cambios») o, sin título, la fila de títulos de la tabla de
    # cambios en una línea: «Fecha  Autor  Descripción» (o Responsable / Motivo).
    ("el control de cambios",
     re.compile(r"\b(?:Control|Historial)\s+de\s+(?:cambios|modificaciones)\b"
                r"|\bFecha\b[^\n]*\b(?:Autor|Responsable|Usuario)\b[^\n]*\b(?:Descripci[oó]n|Motivo|Detalle)\b",
                re.IGNORECASE)),
    ("el ejemplo de ejecución (EXEC)", re.compile(_EXEC, re.IGNORECASE)),
)

# Texto de la usuaria (8 nov.).
QUE_HACER_SIN_ENCABEZADO = (
    "Se recomienda agregar al inicio el encabezado con el nombre del procedimiento, la descripción, el autor, la "
    "fecha, el control de cambios y un ejemplo de ejecución."
)
QUE_HACER_ENCABEZADO_INCOMPLETO = (
    "Se recomienda completar los datos del encabezado, ya que permiten identificar su propósito y facilitan su "
    "mantenimiento."
)


def _inicio_del_cuerpo(limpio: str, desde: int) -> int:
    """Posición de la primera instrucción del cuerpo: tras el AS (fuera de paréntesis) y, si lo hay, el BEGIN."""
    profundidad = 0
    for match in re.finditer(r"[()]|\bAS\b", limpio[desde:], re.IGNORECASE):
        token = match.group(0)
        if token == "(":
            profundidad += 1
        elif token == ")":
            profundidad -= 1
        elif profundidad == 0:
            fin = desde + match.end()
            begin = re.match(r"\s*BEGIN\b", limpio[fin:], re.IGNORECASE)
            if begin:
                fin += begin.end()
            siguiente = re.search(r"\S", limpio[fin:])
            return fin + siguiente.start() if siguiente else len(limpio)
    return len(limpio)


def _enumerar(datos: List[str]) -> str:
    return datos[0] if len(datos) == 1 else f"{', '.join(datos[:-1])} ni {datos[-1]}"


def encabezado_observado(texto: str, limpio: str) -> Optional[Tuple[int, str]]:
    """(posición, mensaje) si el procedimiento no tiene encabezado o le faltan datos; None si está completo.

    `limpio` es el texto sin comentarios con las mismas posiciones. Solo se revisan procedimientos.
    """
    procedimiento = _PROCEDIMIENTO.search(limpio)
    if not procedimiento:
        return None
    zona = texto[:_inicio_del_cuerpo(limpio, procedimiento.end())]
    comentarios = list(_COMENTARIO.finditer(zona))
    encabezado = "\n".join(c.group(0) for c in comentarios)
    if not re.search(r"\w", encabezado):
        return procedimiento.start(), (
            f"Se identificó que el procedimiento no cuenta con un encabezado de documentación. "
            f"{QUE_HACER_SIN_ENCABEZADO}"
        )
    faltan = [dato for dato, patron in _DATOS if not patron.search(encabezado)]
    if not faltan:
        return None
    return comentarios[0].start(), (
        f"Se identificó que el encabezado del procedimiento no indica {_enumerar(faltan)}. "
        f"{QUE_HACER_ENCABEZADO_INCOMPLETO}"
    )
