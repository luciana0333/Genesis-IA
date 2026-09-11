# -*- coding: utf-8 -*-
"""Reglas para diccionario de tablas."""

from app.reglas.reglas_base import ReglaDiccionario

REGLAS_DICCIONARIO_TABLAS = {
    "TABLA_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="TABLA_SIN_DESCRIPCION",
        nombre="Tabla sin descripción",
        severidad="medio",
        descripcion="La tabla no tiene una descripción válida a nivel TABLE en el diccionario.",
        alcance="tabla",
        activo=True,
    ),
    "NOMBRE_TABLA_NO_COINCIDE": ReglaDiccionario(
        codigo="NOMBRE_TABLA_NO_COINCIDE",
        nombre="Nombre de tabla no coincide",
        severidad="alto",
        descripcion="El nombre documentado en @level1name no coincide con el nombre real de la tabla.",
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
    "DESCRIPCION_COLUMNA_VACIA": ReglaDiccionario(
        codigo="DESCRIPCION_COLUMNA_VACIA",
        nombre="Descripción de columna vacía",
        severidad="medio",
        descripcion="La columna está documentada pero su descripción en @value está vacía.",
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
    "ALTER_SIN_DICCIONARIO": ReglaDiccionario(
        codigo="ALTER_SIN_DICCIONARIO",
        nombre="ALTER sin diccionario",
        severidad="bajo",
        descripcion="Se detecta un ALTER TABLE sin script de documentación válido del diccionario.",
        alcance="tabla",
        activo=True,
    ),
}
