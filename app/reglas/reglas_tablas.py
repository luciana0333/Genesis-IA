# -*- coding: utf-8 -*-
"""Reglas para validación de estructura de tablas."""

from app.reglas.reglas_base import ReglaDiccionario

REGLAS_TABLAS = {
    "TABLA_SIN_ESQUEMA": ReglaDiccionario(
        codigo="TABLA_SIN_ESQUEMA",
        nombre="Tabla sin esquema",
        severidad="alto",
        descripcion="Toda tabla nueva o alterada debe indicar explícitamente su esquema.",
        alcance="tabla",
        activo=True,
    ),
    "TABLA_CON_PALABRA_OMITIBLE": ReglaDiccionario(
        codigo="TABLA_CON_PALABRA_OMITIBLE",
        nombre="Nombre de tabla con palabra omitible",
        severidad="alto",
        descripcion="El nombre de la tabla no debe incluir palabras omitibles como de, mi o su.",
        alcance="tabla",
        activo=True,
    ),
    "COLUMNA_SIN_NOT_NULL_NI_DEFAULT": ReglaDiccionario(
        codigo="COLUMNA_SIN_NOT_NULL_NI_DEFAULT",
        nombre="Columna sin NOT NULL ni DEFAULT",
        severidad="alto",
        descripcion="Toda columna nueva debe ser NOT NULL o tener un valor DEFAULT.",
        alcance="tabla",
        activo=True,
    ),
    "COLUMNA_SIN_COLLATE": ReglaDiccionario(
        codigo="COLUMNA_SIN_COLLATE",
        nombre="Columna sin COLLATE",
        severidad="alto",
        descripcion="Las columnas nuevas deben definir COLLATE salvo que la tabla pertenezca a DBCMAICA.",
        alcance="tabla",
        activo=True,
    ),
    "COLLATE_EN_TIPO_NO_TEXTO": ReglaDiccionario(
        codigo="COLLATE_EN_TIPO_NO_TEXTO",
        nombre="COLLATE en tipo no textual",
        severidad="alto",
        descripcion="COLLATE solo debe utilizarse en columnas CHAR o VARCHAR.",
        alcance="tabla",
        activo=True,
    ),
    "COLUMNA_PREFIJO_TIPO_INVALIDO": ReglaDiccionario(
        codigo="COLUMNA_PREFIJO_TIPO_INVALIDO",
        nombre="Prefijo de columna inválido",
        severidad="alto",
        descripcion="El nombre de la columna debe iniciar con el prefijo correspondiente a su tipo de dato.",
        alcance="tabla",
        activo=True,
    ),
}
