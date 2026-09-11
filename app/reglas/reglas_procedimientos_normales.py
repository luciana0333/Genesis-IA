# -*- coding: utf-8 -*-
"""Reglas para procedimientos almacenados normales."""

from app.reglas.reglas_base import ReglaDiccionario

REGLAS_PROCEDIMIENTOS_NORMALES = {
    "WHILE_PROHIBIDO": ReglaDiccionario(
        codigo="WHILE_PROHIBIDO",
        nombre="WHILE prohibido",
        severidad="alto",
        descripcion="No se permite el uso de bucles WHILE en procedimientos normales; use operaciones basadas en conjuntos.",
        alcance="procedimiento",
        activo=True,
    ),
    "GOTO_PROHIBIDO": ReglaDiccionario(
        codigo="GOTO_PROHIBIDO",
        nombre="GOTO prohibido",
        severidad="alto",
        descripcion="No se permite el uso de GOTO en procedimientos normales.",
        alcance="procedimiento",
        activo=True,
    ),
    "MERGE_PROHIBIDO": ReglaDiccionario(
        codigo="MERGE_PROHIBIDO",
        nombre="MERGE prohibido",
        severidad="alto",
        descripcion="No se permite la sentencia MERGE en procedimientos normales.",
        alcance="procedimiento",
        activo=True,
    ),
    "COLLATE_EN_PREDICADO": ReglaDiccionario(
        codigo="COLLATE_EN_PREDICADO",
        nombre="COLLATE en predicado",
        severidad="alto",
        descripcion="No debe usarse COLLATE dentro de condiciones WHERE o JOIN; debe definirse en la tabla temporal o columna.",
        alcance="procedimiento",
        activo=True,
    ),
    "STUFF_FOR_XML_PATH_PROHIBIDO": ReglaDiccionario(
        codigo="STUFF_FOR_XML_PATH_PROHIBIDO",
        nombre="STUFF con FOR XML PATH prohibido",
        severidad="alto",
        descripcion="Se debe reemplazar STUFF(... FOR XML PATH ...) por STRING_AGG o una alternativa equivalente.",
        alcance="procedimiento",
        activo=True,
    ),
    "FN_SPLIT_PROHIBIDO": ReglaDiccionario(
        codigo="FN_SPLIT_PROHIBIDO",
        nombre="FN_SPLIT prohibido",
        severidad="alto",
        descripcion="La función dbo.FN_SPLIT debe reemplazarse por STRING_SPLIT.",
        alcance="procedimiento",
        activo=True,
    ),
    "LTRIM_RTRIM_PROHIBIDO": ReglaDiccionario(
        codigo="LTRIM_RTRIM_PROHIBIDO",
        nombre="LTRIM(RTRIM(...)) prohibido",
        severidad="medio",
        descripcion="Se debe usar TRIM(...) en lugar de anidar LTRIM(RTRIM(...)).",
        alcance="procedimiento",
        activo=True,
    ),
    "NOLOCK_EN_TABLA_FISICA": ReglaDiccionario(
        codigo="NOLOCK_EN_TABLA_FISICA",
        nombre="NOLOCK en tabla física",
        severidad="alto",
        descripcion="La tabla física no debe usar WITH(NOLOCK) cuando forma parte del FROM de un UPDATE o un patrón equivalente.",
        alcance="procedimiento",
        activo=True,
    ),
    "ORDER_BY_NUMERICO_PROHIBIDO": ReglaDiccionario(
        codigo="ORDER_BY_NUMERICO_PROHIBIDO",
        nombre="ORDER BY numérico prohibido",
        severidad="medio",
        descripcion="No se permite ORDER BY 1, ORDER BY 2 o posiciones numéricas; debe ordenarse por columnas explícitas.",
        alcance="procedimiento",
        activo=True,
    ),
    "CAST_EN_JOIN_PROHIBIDO": ReglaDiccionario(
        codigo="CAST_EN_JOIN_PROHIBIDO",
        nombre="CAST en JOIN prohibido",
        severidad="alto",
        descripcion="No se permite realizar CAST dentro de una condición JOIN; debe realizarse antes del JOIN.",
        alcance="procedimiento",
        activo=True,
    ),
}
