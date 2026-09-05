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
    "TABLA_SIN_ESQUEMA": ReglaDiccionario(
        codigo="TABLA_SIN_ESQUEMA",
        nombre="Tabla sin esquema",
        severidad="alto",
        descripcion="Toda tabla nueva o alterada debe indicar explícitamente su esquema.",
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
    "COLUMNA_PREFIJO_TIPO_INVALIDO": ReglaDiccionario(
        codigo="COLUMNA_PREFIJO_TIPO_INVALIDO",
        nombre="Prefijo de columna inválido",
        severidad="alto",
        descripcion="El nombre de la columna debe iniciar con el prefijo correspondiente a su tipo de dato.",
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
    "COLLATE_EN_TIPO_NO_TEXTO": ReglaDiccionario(
        codigo="COLLATE_EN_TIPO_NO_TEXTO",
        nombre="COLLATE en tipo no textual",
        severidad="alto",
        descripcion="COLLATE solo debe utilizarse en columnas CHAR o VARCHAR.",
        alcance="tabla",
        activo=True,
    ),
    "TABLA_FISICA_SIN_NOLOCK": ReglaDiccionario(
        codigo="TABLA_FISICA_SIN_NOLOCK",
        nombre="Tabla física sin NOLOCK",
        severidad="alto",
        descripcion="Las tablas físicas consultadas por un reporte deben usar WITH(NOLOCK).",
        alcance="reporte",
        activo=True,
    ),
    "NOLOCK_EN_TABLA_TEMPORAL": ReglaDiccionario(
        codigo="NOLOCK_EN_TABLA_TEMPORAL",
        nombre="NOLOCK en tabla temporal",
        severidad="alto",
        descripcion="Las tablas temporales no deben utilizar WITH(NOLOCK).",
        alcance="reporte",
        activo=True,
    ),
    "HINT_PLAN_PROHIBIDO": ReglaDiccionario(
        codigo="HINT_PLAN_PROHIBIDO",
        nombre="Hint de plan prohibido",
        severidad="alto",
        descripcion="No se deben forzar planes o decisiones del optimizador en reportes.",
        alcance="reporte",
        activo=True,
    ),
    "CODIGO_SQL_COMENTADO": ReglaDiccionario(
        codigo="CODIGO_SQL_COMENTADO",
        nombre="Código SQL comentado",
        severidad="medio",
        descripcion="El reporte no debe conservar sentencias SQL comentadas que no aporten.",
        alcance="reporte",
        activo=True,
    ),
    "TEMPORAL_TEXTO_SIN_COLLATE": ReglaDiccionario(
        codigo="TEMPORAL_TEXTO_SIN_COLLATE",
        nombre="Texto temporal sin COLLATE",
        severidad="alto",
        descripcion="Las columnas de texto de tablas temporales deben declarar COLLATE.",
        alcance="reporte",
        activo=True,
    ),
    "SELECT_INTO_PROHIBIDO": ReglaDiccionario(
        codigo="SELECT_INTO_PROHIBIDO",
        nombre="SELECT INTO prohibido",
        severidad="alto",
        descripcion="Se debe declarar la tabla temporal y luego insertar sus datos.",
        alcance="reporte",
        activo=True,
    ),
    "SELECT_ESTRELLA_PROHIBIDO": ReglaDiccionario(
        codigo="SELECT_ESTRELLA_PROHIBIDO",
        nombre="SELECT estrella prohibido",
        severidad="medio",
        descripcion="Las consultas deben indicar sus columnas explícitamente.",
        alcance="reporte",
        activo=True,
    ),
    "IN_CON_UN_SOLO_VALOR": ReglaDiccionario(
        codigo="IN_CON_UN_SOLO_VALOR",
        nombre="IN con un solo valor",
        severidad="medio",
        descripcion="Use igualdad cuando IN contiene un único valor.",
        alcance="reporte",
        activo=True,
    ),
    "CATALOGO_SISTEMA_PROHIBIDO": ReglaDiccionario(
        codigo="CATALOGO_SISTEMA_PROHIBIDO",
        nombre="Catálogo de sistema prohibido",
        severidad="alto",
        descripcion="Un procedimiento de reporte no debe consultar catálogos del sistema.",
        alcance="reporte",
        activo=True,
    ),
    "MODIFICACION_TABLA_FISICA": ReglaDiccionario(
        codigo="MODIFICACION_TABLA_FISICA",
        nombre="Modificación de tabla física",
        severidad="critico",
        descripcion="Los reportes solo consultan y no modifican tablas físicas.",
        alcance="reporte",
        activo=True,
    ),
    "VARIABLE_DECLARADA_SIN_USO": ReglaDiccionario(
        codigo="VARIABLE_DECLARADA_SIN_USO",
        nombre="Variable declarada sin uso",
        severidad="medio",
        descripcion="Toda variable declarada debe utilizarse en la lógica del reporte.",
        alcance="reporte",
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
