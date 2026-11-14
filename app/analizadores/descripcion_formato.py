"""«Descripción sin formato estándar» (diccionarios de tabla, procedimiento y función; usuaria, 13 nov.).

La descripción del objeto mismo (no la de sus columnas ni la de sus parámetros) debe iniciar con la palabra de su tipo:
«Tabla…», «Procedimiento…» o «Función…». El resto lo escribe libre cada equipo. No distingue mayúsculas y acepta
«Funcion» sin tilde. Una descripción vacía no se marca aquí (tiene su propia regla).
"""

import re
from typing import Optional

# Palabra con la que debe iniciar cada objeto y cómo se reconoce (sin tilde también vale).
_PALABRA = {
    "tabla": ("Tabla", re.compile(r"^\W*tabla\b", re.IGNORECASE)),
    "procedimiento": ("Procedimiento", re.compile(r"^\W*procedimiento\b", re.IGNORECASE)),
    "funcion": ("Función", re.compile(r"^\W*funci[oó]n\b", re.IGNORECASE)),
}
# «de la tabla dbo.X», «del procedimiento dbo.X», «de la función dbo.X».
_DE_OBJETO = {"tabla": "de la tabla", "procedimiento": "del procedimiento", "funcion": "de la función"}


def descripcion_sin_formato(objeto: str, nombre: str, descripcion: str) -> Optional[str]:
    """Mensaje si la descripción no inicia con la palabra de su tipo; None si está bien o vacía.

    objeto: «tabla», «procedimiento» o «funcion». nombre: dbo.Cliente.
    """
    if not descripcion.strip():
        return None
    palabra, patron = _PALABRA[objeto]
    if patron.match(descripcion):
        return None
    # Texto de la usuaria (13 nov.).
    return (f"Se identificó que la descripción {_DE_OBJETO[objeto]} {nombre} no inicia con la palabra «{palabra}». "
            f"Se recomienda iniciar la descripción con la palabra «{palabra}», para que se pueda reconocer "
            f"rápidamente el tipo de objeto documentado y comprender con mayor facilidad la información que "
            f"contiene.")
