# -*- coding: utf-8 -*-
"""
Glosario de siglas aprobadas (app/reglas/siglas.txt).

Una sigla del glosario se acepta en los nombres de tablas, columnas y procedimientos;
las demás se marcan como «sigla por validar».
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

_ARCHIVO = Path(__file__).resolve().parent.parent / "reglas" / "siglas.txt"


@lru_cache(maxsize=1)
def siglas_aprobadas() -> Dict[str, str]:
    """{SIGLA: significado} leído del glosario (vacío si el archivo no existe)."""
    if not _ARCHIVO.is_file():
        return {}
    siglas = {}
    for linea in _ARCHIVO.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        sigla, _, significado = linea.partition("=")
        if sigla.strip():
            siglas[sigla.strip().upper()] = significado.strip()
    return siglas


def es_sigla_aprobada(sigla: str) -> bool:
    return sigla.upper() in siglas_aprobadas()


def significado(sigla: str) -> Optional[str]:
    return siglas_aprobadas().get(sigla.upper()) or None
