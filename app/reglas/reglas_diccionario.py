# -*- coding: utf-8 -*-
"""Consolidado de reglas por categoría.

Este archivo mantiene compatibilidad con imports existentes, pero la
organización real está separada por tipo de validación.
"""

from __future__ import annotations

from typing import Dict, List

from app.reglas.reglas_base import ReglaDiccionario
from app.reglas.reglas_diccionario_procedimientos import REGLAS_DICCIONARIO_PROCEDIMIENTOS
from app.reglas.reglas_diccionario_tablas import REGLAS_DICCIONARIO_TABLAS
from app.reglas.reglas_procedimientos_normales import REGLAS_PROCEDIMIENTOS_NORMALES
from app.reglas.reglas_reportes import REGLAS_REPORTES
from app.reglas.reglas_tablas import REGLAS_TABLAS

REGLAS_DICCIONARIO: Dict[str, ReglaDiccionario] = {
    **REGLAS_DICCIONARIO_PROCEDIMIENTOS,
    **REGLAS_DICCIONARIO_TABLAS,
    **REGLAS_TABLAS,
    **REGLAS_REPORTES,
    **REGLAS_PROCEDIMIENTOS_NORMALES,
}


def listar_reglas() -> List[ReglaDiccionario]:
    """Devuelve todas las reglas definidas."""
    return list(REGLAS_DICCIONARIO.values())


def obtener_regla(codigo: str) -> ReglaDiccionario:
    """Obtiene una regla por su codigo."""
    return REGLAS_DICCIONARIO[codigo]


def reglas_activas() -> List[ReglaDiccionario]:
    """Devuelve solo las reglas activas."""
    return [regla for regla in REGLAS_DICCIONARIO.values() if regla.activo]


if __name__ == "__main__":
    for regla in listar_reglas():
        print(f"{regla.codigo} | {regla.severidad} | {regla.nombre}")
