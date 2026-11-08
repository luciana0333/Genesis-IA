"""«Uso de CREATE OR ALTER» (compartido por Reportes y Negocio; texto de la usuaria, 8 nov.)."""

import re
from typing import Optional, Tuple

_CREATE_OR_ALTER = re.compile(r"\bCREATE\s+OR\s+ALTER\s+PROC(?:EDURE)?\b", re.IGNORECASE)

MENSAJE_CREATE_OR_ALTER = (
    "Se identificó el uso de CREATE OR ALTER en la definición del procedimiento. Se recomienda verificar si el "
    "procedimiento ya existe. Si existe, utilizar ALTER PROCEDURE; de lo contrario, utilizar CREATE PROCEDURE. "
    "Evitar el uso de CREATE OR ALTER."
)


def create_or_alter(limpio: str) -> Optional[Tuple[int, str]]:
    """(posición, mensaje) si el procedimiento se define con CREATE OR ALTER; `limpio` es el texto sin comentarios."""
    match = _CREATE_OR_ALTER.search(limpio)
    return (match.start(), MENSAJE_CREATE_OR_ALTER) if match else None
