# -*- coding: utf-8 -*-
"""Reglas para diccionario de procedimientos."""

from app.reglas.reglas_base import ReglaDiccionario

REGLAS_DICCIONARIO_PROCEDIMIENTOS = {
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
        nombre="Nombre del procedimiento no coincide",
        severidad="alto",
        descripcion="El nombre documentado en @level1name no coincide con el nombre real del objeto.",
        alcance="procedimiento",
        activo=True,
    ),
    "PARAMETRO_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="PARAMETRO_SIN_DESCRIPCION",
        nombre="Parámetro sin descripción",
        severidad="medio",
        descripcion="Un parámetro declarado en el procedimiento no tiene descripción en el diccionario.",
        alcance="procedimiento",
        activo=True,
    ),
    "PARAMETRO_FALTANTE": ReglaDiccionario(
        codigo="PARAMETRO_FALTANTE",
        nombre="Parámetro no documentado",
        severidad="medio",
        descripcion="El parámetro declarado falta en el diccionario.",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="PROCEDIMIENTO_SIN_DESCRIPCION",
        nombre="Procedimiento no documentado",
        severidad="medio",
        descripcion="El procedimiento no tiene una descripción válida a nivel PROCEDURE en el diccionario.",
        alcance="procedimiento",
        activo=True,
    ),
    "DESCRIPCION_VACIA": ReglaDiccionario(
        codigo="DESCRIPCION_VACIA",
        nombre="Descripción de parámetro vacía",
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
        descripcion=(
            "Nombres sin comillas (@level0name = dbo). Desactivada: SQL Server acepta nombres simples "
            "sin comillas en sp_addextendedproperty."
        ),
        alcance="procedimiento",
        activo=False,
    ),
}
