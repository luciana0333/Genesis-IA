"""«Palabra repetida en la descripción» (diccionarios de tablas y de procedimientos; usuaria, 11 nov.).

Caso real: «…que no se encuentran en el repositorio de de RRHH.EstructuraCAPDetalle». La ortografía no lo ve porque
«de» está bien escrita: el error es que aparece dos veces seguidas. Compartido por los dos diccionarios.

Se marca la misma palabra dos veces seguidas, sin importar mayúsculas («de de», «El el»). No cuentan los números
(«1 1») ni las palabras que forman parte de un nombre con punto o guion bajo (RRHH.de.de, cod_de_de).
"""

import re
from typing import List, Tuple

# Una palabra (solo letras, con tildes y ñ), un espacio y la misma palabra. Sin pegarse a «.», «_» ni «@».
_REPETIDA = re.compile(r"(?<![\w.@#])([^\W\d_]+)\s+(\1)(?![\w.])", re.IGNORECASE)


def palabras_repetidas(descripcion: str) -> List[Tuple[str, str]]:
    """[(palabra, fragmento)] de cada repetición: («de», «…el repositorio de de RRHH…»)."""
    casos = []
    for match in _REPETIDA.finditer(descripcion):
        antes = descripcion[:match.start()].split()[-2:]
        despues = descripcion[match.end():].split()[:1]
        fragmento = " ".join(antes + [match.group(1), match.group(2)] + despues)
        if antes and len(descripcion[:match.start()].split()) > 2:
            fragmento = "…" + fragmento
        if despues and len(descripcion[match.end():].split()) > 1:
            fragmento += "…"
        casos.append((match.group(1).lower(), fragmento))
    return casos


QUE_HACER_PALABRA_REPETIDA = ("Se recomienda corregir la descripción, ya que la palabra repetida afecta la claridad "
                              "de la documentación.")


def mensaje_palabra_repetida(objeto: str, casos: List[Tuple[str, str]]) -> str:
    """objeto: «del procedimiento dbo.PA_X», «del parámetro @n», «de la columna cNombre», «de la tabla dbo.T»."""
    if len(casos) == 1:
        palabra, fragmento = casos[0]
        hecho = f"Se identificó la palabra «{palabra}» repetida en la descripción {objeto} («{fragmento}»)."
    else:
        detalle = "; ".join(f"«{fragmento}»" for _, fragmento in casos)
        hecho = f"Se identificaron palabras repetidas en la descripción {objeto} ({detalle})."
    return f"{hecho} {QUE_HACER_PALABRA_REPETIDA}"


def elemento_palabra_repetida(objeto: str, casos: List[Tuple[str, str]]) -> str:
    """Caso para la observación agrupada: «descripción del parámetro @n: «…de de…»»."""
    return f"descripción {objeto}: " + ", ".join(f"«{fragmento}»" for _, fragmento in casos)
