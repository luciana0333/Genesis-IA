# -*- coding: utf-8 -*-
"""
Detecta qué tipo de objeto contiene un script SQL (tabla o procedimiento).

Se usa en la revisión de diccionarios para aplicar siempre las reglas
correctas, sin depender de que el usuario elija bien el tipo en la interfaz.
"""

import re
from typing import Optional

_COMENTARIOS = re.compile(r"--[^\r\n]*|/\*.*?\*/", re.DOTALL)
_OBJETO = re.compile(
    r"\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(TABLE|PROC(?:EDURE)?)\b",
    re.IGNORECASE,
)


def detectar_objeto(texto_sql: str) -> Optional[str]:
    """Devuelve 'tabla', 'procedimiento' o None si no reconoce el objeto."""
    coincidencia = _OBJETO.search(_COMENTARIOS.sub(" ", texto_sql or ""))
    if not coincidencia:
        return None
    return "tabla" if coincidencia.group(1).upper() == "TABLE" else "procedimiento"
