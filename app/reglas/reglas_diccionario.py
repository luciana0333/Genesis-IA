# -*- coding: utf-8 -*-
"""
reglas_diccionario.py
--------------------
Define la catalogacion centralizada de reglas para el analisis del
(diccionario) de procedimientos y tablas.

Objetivo:
- separar la definicion de la regla del codigo que la ejecuta
- mantener un catalogo claro y reutilizable por la UI y reportes
- facilitar la extension futura a tablas, plan de ejecucion y IA
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ReglaDiccionario:
    codigo: str
    nombre: str
    severidad: str
    descripcion: str
    alcance: str
    activo: bool = True


REGLAS_DICCIONARIO: Dict[str, ReglaDiccionario] = {
    "ESQUEMA_NO_COINCIDE": ReglaDiccionario(
        codigo="ESQUEMA_NO_COINCIDE",
        nombre="Esquema no coincide",
        severidad="alto",
        descripcion="El esquema documentado en @level0name no coincide con el esquema real del objeto.",
        alcance="procedimiento",
        activo=True,
    ),
    "NOMBRE_NO_COINCIDE": ReglaDiccionario(
        codigo="NOMBRE_NO_COINCIDE",
        nombre="Nombre no coincide",
        severidad="alto",
        descripcion="El nombre documentado en @level1name no coincide con el nombre real del objeto.",
        alcance="procedimiento",
        activo=True,
    ),
    "PARAMETRO_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="PARAMETRO_SIN_DESCRIPCION",
        nombre="Parámetro sin descripción",
        severidad="medio",
        descripcion="Un parámetro declarado en el procedimient o no tiene descripción en el diccionario.",
        alcance="procedimiento",
        activo=True,
    ),
    "PARAMETRO_FALTANTE": ReglaDiccionario(
        codigo="PARAMETRO_FALTANTE",
        nombre="Parámetro faltante",
        severidad="medio",
        descripcion="El parámetro declarado falta en el diccionario.",
        alcance="procedimiento",
        activo=True,
    ),
    "DESCRIPCION_VACIA": ReglaDiccionario(
        codigo="DESCRIPCION_VACIA",
        nombre="Descripción vacía",
        severidad="medio",
        descripcion="La descripción del parámetro o atributo existe pero está vacía.",
        alcance="procedimiento",
        activo=True,
    ),
    "ALTER_SIN_DICCIONARIO": ReglaDiccionario(
        codigo="ALTER_SIN_DICCIONARIO",
        nombre="ALTER sin diccionario",
        severidad="bajo",
        descripcion="Se detecta un ALTER sin script de documentación válido del diccionario.",
        alcance="procedimiento",
        activo=True,
    ),
    "VALOR_SIN_COMILLAS": ReglaDiccionario(
        codigo="VALOR_SIN_COMILLAS",
        nombre="Valor sin comillas",
        severidad="critico",
        descripcion="Un valor de extended property no está bien formado o tiene formato inválido.",
        alcance="procedimiento",
        activo=True,
    ),
    "TABLA_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="TABLA_SIN_DESCRIPCION",
        nombre="Tabla sin descripción",
        severidad="medio",
        descripcion="La tabla no tiene una descripción válida a nivel TABLE en el diccionario.",
        alcance="tabla",
        activo=True,
    ),
    "COLUMNA_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="COLUMNA_SIN_DESCRIPCION",
        nombre="Columna sin descripción",
        severidad="medio",
        descripcion="La columna declarada no tiene descripción en el diccionario.",
        alcance="tabla",
        activo=True,
    ),
    "COLUMNA_FALTANTE": ReglaDiccionario(
        codigo="COLUMNA_FALTANTE",
        nombre="Columna faltante",
        severidad="medio",
        descripcion="La columna declarada falta en el diccionario.",
        alcance="tabla",
        activo=True,
    ),
}


def listar_reglas() -> List[ReglaDiccionario]:
    """Devuelve todas las reglas definidas para el diccionario."""
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
