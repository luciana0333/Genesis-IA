# -*- coding: utf-8 -*-
"""
Glosario de siglas aprobadas.

- app/reglas/siglas.txt: glosario base, viene con Genesis (se actualiza con git pull).
- app/reglas/siglas_locales.txt: siglas aprobadas desde la pantalla en esta PC
  («Aprobar siglas»). Git no lo toca, así que no choca con las actualizaciones.

Una sigla de cualquiera de los dos se acepta en los nombres de tablas, columnas y
procedimientos; las demás se marcan como «sigla por validar».
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

_CARPETA = Path(__file__).resolve().parent.parent / "reglas"
_BASE = _CARPETA / "siglas.txt"
_LOCALES = _CARPETA / "siglas_locales.txt"

_FORMATO_SIGLA = re.compile(r"^[A-Z]{2,10}$")
MAXIMO_SIGNIFICADO = 150


def _leer(archivo: Path) -> Dict[str, str]:
    if not archivo.is_file():
        return {}
    siglas = {}
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        sigla, _, significado = linea.partition("=")
        if sigla.strip():
            siglas[sigla.strip().upper()] = significado.strip()
    return siglas


@lru_cache(maxsize=1)
def siglas_aprobadas() -> Dict[str, str]:
    """{SIGLA: significado}: el glosario base más las aprobadas en esta PC."""
    return {**_leer(_BASE), **_leer(_LOCALES)}


def es_sigla_aprobada(sigla: str) -> bool:
    return sigla.upper() in siglas_aprobadas()


def significado(sigla: str) -> Optional[str]:
    return siglas_aprobadas().get(sigla.upper()) or None


def aprobar_sigla(sigla: str, significado_sigla: str) -> str:
    """
    Guarda la sigla en el glosario de esta PC y la deja aprobada al instante.
    Devuelve la sigla normalizada. Lanza ValueError si los datos no son válidos.
    """
    sigla = (sigla or "").strip().upper()
    significado_sigla = " ".join((significado_sigla or "").split())
    if not _FORMATO_SIGLA.match(sigla):
        raise ValueError("La sigla debe tener entre 2 y 10 letras, sin espacios ni números.")
    if not significado_sigla:
        raise ValueError("Escribe el significado de la sigla.")
    if len(significado_sigla) > MAXIMO_SIGNIFICADO:
        raise ValueError(f"El significado puede tener hasta {MAXIMO_SIGNIFICADO} caracteres.")
    if "=" in significado_sigla or "#" in significado_sigla:
        raise ValueError("El significado no puede llevar los caracteres = ni #.")

    locales = _leer(_LOCALES)
    locales[sigla] = significado_sigla
    encabezado = (
        "# Siglas aprobadas desde la pantalla de Genesis en esta PC («Aprobar siglas»).\n"
        "# Se suman al glosario base (siglas.txt). Formato: SIGLA = significado\n"
    )
    cuerpo = "".join(f"{clave} = {valor}\n" for clave, valor in sorted(locales.items()))
    _LOCALES.write_text(encabezado + cuerpo, encoding="utf-8")
    siglas_aprobadas.cache_clear()
    return sigla
