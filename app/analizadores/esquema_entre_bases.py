"""Base..Tabla omite el esquema (compartido por Reportes y Negocio; texto de la usuaria, 7 nov.)."""

import re
from typing import List, Tuple

_BASE_SIN_ESQUEMA = re.compile(r"(\[[^\]]+\]|[A-Za-z_][\w$#]*)\s*\.\s*\.\s*(\[[^\]]+\]|[A-Za-z_][\w$#]*)")

# Texto de la usuaria (7 nov.), igual en Reportes y Negocio.
QUE_HACER_ESQUEMA_ENTRE_BASES = (
    "Indicar el esquema correspondiente de las tablas utilizadas en la consulta, evitando el uso del esquema "
    "predeterminado, para identificar correctamente su procedencia y facilitar futuras modificaciones."
)


def esquemas_omitidos(limpio: str) -> List[Tuple[int, str]]:
    """[(posición, mensaje)] de cada Base..Tabla: entre bases se escribe Base.Esquema.Tabla."""
    resultado = []
    for match in _BASE_SIN_ESQUEMA.finditer(limpio):
        base, tabla = match.group(1).strip("[]"), match.group(2).strip("[]")
        resultado.append((
            match.start(),
            f"Se verificó el uso de la tabla {tabla} de la base de datos {base} sin indicar el esquema "
            f"correspondiente ({base}..{tabla}). {QUE_HACER_ESQUEMA_ENTRE_BASES}",
        ))
    return resultado
