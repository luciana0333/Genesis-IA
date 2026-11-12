"""«Palabra repetida en la descripción» (diccionarios de tablas y de procedimientos; usuaria, 11 nov.).

Caso real: «…que no se encuentran en el repositorio de de RRHH.EstructuraCAPDetalle». La ortografía no lo ve porque
«de» está bien escrita: el error es que aparece dos veces seguidas. Compartido por los dos diccionarios.

Se marca la misma palabra dos veces seguidas, sin importar mayúsculas («de de», «El el»). No cuentan los números
(«1 1») ni las palabras que forman parte de un nombre con punto o guion bajo (RRHH.de.de, cod_de_de).
Todas las del diccionario van en UNA sola observación, con texto directo (usuaria, 11 nov.).
"""

import re
from typing import List, Optional, Tuple

# Una palabra (solo letras, con tildes y ñ), un espacio y la misma palabra. Sin pegarse a «.», «_» ni «@».
_REPETIDA = re.compile(r"(?<![\w.@#])([^\W\d_]+)\s+(\1)(?![\w.])", re.IGNORECASE)


def palabras_repetidas(descripcion: str) -> List[str]:
    """Cada repetición tal como está escrita: ["de de", "El el"]."""
    return [f"{match.group(1)} {match.group(2)}" for match in _REPETIDA.finditer(descripcion)]


def _enumerar(elementos: List[str]) -> str:
    return elementos[0] if len(elementos) == 1 else f"{', '.join(elementos[:-1])} y {elementos[-1]}"


def palabra_repetida_agrupada(
    descripciones: List[Tuple[int, str]],
) -> Optional[Tuple[int, str, List[int]]]:
    """descripciones: [(línea del @value, texto)]. Devuelve (primera línea, mensaje, líneas) o None."""
    repetidas: List[str] = []
    lineas: List[int] = []
    for linea, texto in descripciones:
        encontradas = palabras_repetidas(texto)
        if encontradas:
            lineas.append(linea)
        for repetida in encontradas:
            if repetida.lower() not in (r.lower() for r in repetidas):
                repetidas.append(repetida)
    if not repetidas:
        return None
    lineas = sorted(set(lineas))
    comillas = [f"«{r}»" for r in repetidas]
    # Texto de la usuaria (11 nov.): directo, sin el nombre del objeto ni el fragmento.
    if len(repetidas) == 1 and len(lineas) == 1:
        mensaje = (f"Se identificó la palabra repetida {comillas[0]} en la descripción del diccionario. "
                   f"Se recomienda corregir la descripción eliminando la palabra repetida, ya que genera redundancia.")
    else:
        donde = "la descripción" if len(lineas) == 1 else "las descripciones"
        mensaje = (f"Se identificaron palabras repetidas en {donde} del diccionario: {_enumerar(comillas)}. "
                   f"Se recomienda corregir {donde} eliminando las palabras repetidas, ya que generan redundancia.")
    return lineas[0], mensaje, lineas
