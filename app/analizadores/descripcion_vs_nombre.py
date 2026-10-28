# -*- coding: utf-8 -*-
"""La descripción habla de un dato distinto al que indica el nombre.

    @nCodMonedaTotal  ->  'Monto total expresado en la moneda…'   (el nombre dice código; la descripción, monto)

Solo se observa cuando los dos lados son claros: el nombre empieza con Cod/Monto/Fecha (o termina en Id)
y la descripción empieza con Código/Identificador, Monto/Importe/Saldo o Fecha.
"""

import re
from typing import Optional, Tuple

from app.analizadores.ortografia import normalizar

# Qué dato es, según la primera palabra de la descripción (sin tildes, en minúscula).
_POR_DESCRIPCION = {
    "codigo": "un código", "identificador": "un código", "id": "un código",
    "monto": "un monto", "importe": "un monto", "saldo": "un monto",
    "fecha": "una fecha",
}
# Qué dato es, según la primera parte del nombre (después del prefijo n, c, d…).
_POR_NOMBRE = {
    "cod": "un código", "codigo": "un código", "id": "un código",
    "monto": "un monto", "importe": "un monto", "saldo": "un monto",
    "fecha": "una fecha",
}
_INICIO = re.compile(r"^\s*(?:indica\s+)?(?:el|la|los|las)?\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)", re.IGNORECASE)


def _segun_nombre(nombre: str) -> Optional[str]:
    partes = re.findall(r"[A-Z][a-z0-9]*", nombre.lstrip("@#"))
    if not partes:
        return None
    dato = _POR_NOMBRE.get(partes[0].lower())
    if dato:
        return dato
    return "un código" if partes[-1] == "Id" else None


def contradice(nombre: str, descripcion: str) -> Optional[Tuple[str, str]]:
    """(lo que dice la descripción, lo que indica el nombre) si no coinciden; si no, None."""
    inicio = _INICIO.match(descripcion or "")
    if not inicio:
        return None
    segun_descripcion = _POR_DESCRIPCION.get(normalizar(inicio.group(1)))
    segun_nombre = _segun_nombre(nombre)
    if segun_descripcion and segun_nombre and segun_descripcion != segun_nombre:
        return segun_descripcion, segun_nombre
    return None
