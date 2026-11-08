"""«Dependencia con la base de datos BI» (compartido por Negocio y Reportes; texto de la usuaria).

BI es de Inteligencia Comercial y no es productiva: si un día borran o cambian una tabla, el procedimiento que la
usa falla. Se observa en Negocio y, desde el 8 nov., también en Reportes, con el mismo texto.
"""

import re
from typing import Callable, List, Optional, Tuple

# Objeto de la base BI: BI.dbo.Objeto, [BI].[dbo].[Objeto], BI..Objeto o Servidor.BI.dbo.Objeto.
# Necesita dos puntos: «bi.cColumna» es un alias con su columna, no la base BI.
_OBJETO_DE_BI = re.compile(
    r"(?<![\w$#@.\]])(?:(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)\s*\.\s*)?(?:\[BI\]|BI)\s*\.\s*"
    r"(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)?\s*\.\s*(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)",
    re.IGNORECASE,
)
_USE_BI = re.compile(r"\bUSE\s+\[?BI\]?(?![\w$#])", re.IGNORECASE)

# Texto de la usuaria.
ACCION_DEPENDENCIA_BI = (
    "Se recomienda evitar dependencias con la base de datos BI, ya que no se considera una base de datos "
    "productiva. Ante una eventual indisponibilidad de dicha base, los procedimientos que dependan de ella "
    "podrían verse afectados en su ejecución."
)


def dependencia_bi(texto: str, limpio: str, linea_de: Callable[[int], int]) -> Optional[Tuple[int, str, List[int]]]:
    """Una observación con todos los objetos de BI: (posición, mensaje, líneas) o None."""
    usos = [(m.start(), re.sub(r"\s+", "", texto[m.start():m.end()])) for m in _OBJETO_DE_BI.finditer(limpio)]
    usos += [(m.start(), "USE BI") for m in _USE_BI.finditer(limpio)]
    if not usos:
        return None
    usos.sort()
    objetos = list(dict.fromkeys(nombre for _, nombre in usos))
    if len(objetos) == 1:
        mensaje = f"Se identificó una dependencia con la base de datos BI ({objetos[0]}). {ACCION_DEPENDENCIA_BI}"
    else:
        mensaje = (f"Se identificaron {len(objetos)} dependencias con la base de datos BI: {'; '.join(objetos)}. "
                   f"{ACCION_DEPENDENCIA_BI}")
    return usos[0][0], mensaje, sorted({linea_de(posicion) for posicion, _ in usos})
