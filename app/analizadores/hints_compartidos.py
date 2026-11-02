# -*- coding: utf-8 -*-
"""Hints de bloqueo (compartido por Reportes y Procedimientos de negocio).

- En una tabla temporal (#T) o variable de tabla (@T) un hint de bloqueo no detiene a nadie: solo la usa la
  sesión que la creó (y TABLOCK en un INSERT a una temporal se usa a propósito para cargarla más rápido).
- SET TRANSACTION ISOLATION LEVEL SERIALIZABLE / REPEATABLE READ hace lo mismo que HOLDLOCK, pero en todas
  las consultas que siguen en el procedimiento.
"""

import re
from typing import List, Tuple

# Hints de bloqueo que se agregaron el 2 nov. (se escapaban), con lo que hace cada uno.
HINTS_BLOQUEO_NUEVOS = {
    "NOWAIT": "hace que la consulta falle de inmediato si encuentra una fila bloqueada, en lugar de esperar",
    "READCOMMITTEDLOCK": "obliga a leer con bloqueos compartidos aunque la base de datos use otro modo de lectura",
    "SNAPSHOT": "obliga a leer las filas con el aislamiento SNAPSHOT (versiones anteriores de las filas)",
}

# Tabla (con su alias) que va justo antes del paréntesis de hints: «#T t WITH (», «INTO #T WITH (».
_TABLA_ANTES_DEL_HINT = re.compile(
    r"([#@]?[\w\[\].]+)(?:\s+(?:AS\s+)?[A-Za-z_]\w*)?\s*(?:WITH\s*)?$", re.IGNORECASE,
)

_AISLAMIENTO = re.compile(
    r"\bSET\s+TRANSACTION\s+ISOLATION\s+LEVEL\s+(SERIALIZABLE|REPEATABLE\s+READ)\b", re.IGNORECASE,
)
QUE_HACE_EL_AISLAMIENTO = (
    "mantiene bloqueadas las filas leídas hasta que termina la transacción en todas las consultas que siguen "
    "en el procedimiento"
)


def hint_en_temporal(codigo: str, abre: int) -> bool:
    """El paréntesis de hints que abre en `abre` es de una tabla temporal (#T) o variable de tabla (@T)."""
    tabla = _TABLA_ANTES_DEL_HINT.search(codigo[max(0, abre - 200):abre])
    return bool(tabla) and tabla.group(1).lstrip("[").startswith(("#", "@"))


def niveles_de_aislamiento(codigo: str) -> List[Tuple[int, str]]:
    """[(posición, instrucción)] de cada SET TRANSACTION ISOLATION LEVEL SERIALIZABLE / REPEATABLE READ."""
    return [
        (m.start(), f"SET TRANSACTION ISOLATION LEVEL {' '.join(m.group(1).upper().split())}")
        for m in _AISLAMIENTO.finditer(codigo)
    ]
