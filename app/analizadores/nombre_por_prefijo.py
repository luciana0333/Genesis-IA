"""Columnas o parámetros documentados con el prefijo de tipo equivocado (Diccionarios de tablas y procedimientos).

Caso de la usuaria (7 nov.): el diccionario documenta cFechaRegularizacion, que no existe, y la tabla tiene
dFechaRegularizacion sin documentar. Es el mismo nombre con otro prefijo (c/d): se dice que parece referirse a
la columna real, en vez de dar dos observaciones separadas. Solo se empareja cuando es seguro: mismo esquema,
mismo objeto y el nombre idéntico salvo el prefijo; lo demás queda como «no documentada» / «no existe».
"""

import re
from typing import Dict, Iterable

_PREFIJO = re.compile(r"^[a-z]{1,3}(?=[A-Z0-9_])")


def sin_prefijo(nombre: str) -> str:
    """cFechaRegularizacion -> fecharegularizacion; @nCodAge -> codage (sin corchetes ni @)."""
    limpio = nombre.strip().strip("[]").lstrip("@")
    return _PREFIJO.sub("", limpio).lower()


def emparejar_por_prefijo(documentados_inexistentes: Iterable[str], sin_documentar: Iterable[str]) -> Dict[str, str]:
    """{nombre documentado que no existe: nombre real sin documentar} cuando solo cambia el prefijo de tipo.

    Si un nombre podría emparejarse con más de uno, no se empareja (no es seguro).
    """
    faltantes = list(dict.fromkeys(sin_documentar))
    pares: Dict[str, str] = {}
    usados = set()
    for documentado in dict.fromkeys(documentados_inexistentes):
        base = sin_prefijo(documentado)
        if not base:
            continue
        candidatos = [f for f in faltantes if sin_prefijo(f) == base and f.upper() != documentado.upper()]
        if len(candidatos) == 1 and candidatos[0] not in usados:
            pares[documentado] = candidatos[0]
            usados.add(candidatos[0])
    return pares
