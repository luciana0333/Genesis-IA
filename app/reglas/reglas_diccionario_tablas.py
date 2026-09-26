# -*- coding: utf-8 -*-
"""
Reglas para diccionario de tablas.

Este catálogo es la fuente de verdad: el analizador de diccionario de tablas
toma de aquí la severidad de cada regla y omite las que tengan activo=False.
"""

from app.reglas.reglas_base import ReglaDiccionario

REGLAS_DICCIONARIO_TABLAS = {
    # --- Qué debe estar documentado -------------------------------------
    "TABLA_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="TABLA_SIN_DESCRIPCION",
        nombre="Tabla sin descripción",
        severidad="alto",
        descripcion="Falta la descripción de la propia tabla (la sentencia sin @level2type) o está vacía.",
        alcance="tabla",
        activo=True,
    ),
    "COLUMNA_FALTANTE": ReglaDiccionario(
        codigo="COLUMNA_FALTANTE",
        nombre="Columna sin descripción",
        severidad="alto",
        descripcion="La columna no está documentada en el diccionario. En un CREATE aplica a todas las columnas; en un ALTER, a las agregadas o modificadas.",
        alcance="tabla",
        activo=True,
    ),
    "DESCRIPCION_COLUMNA_VACIA": ReglaDiccionario(
        codigo="DESCRIPCION_COLUMNA_VACIA",
        nombre="Descripción de columna vacía",
        severidad="alto",
        descripcion="La columna está documentada pero su descripción en @value está vacía.",
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

    # --- Que todo coincida con la tabla ---------------------------------
    "ESQUEMA_NO_COINCIDE": ReglaDiccionario(
        codigo="ESQUEMA_NO_COINCIDE",
        nombre="Esquema no coincide",
        severidad="alto",
        descripcion="El esquema documentado en @level0name no coincide con el esquema real de la tabla.",
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
    "COLUMNA_NO_EXISTE": ReglaDiccionario(
        codigo="COLUMNA_NO_EXISTE",
        nombre="Columna documentada inexistente",
        severidad="alto",
        descripcion="En un CREATE TABLE, el diccionario documenta una columna que no existe en la tabla (posible error de tipeo).",
        alcance="tabla",
        activo=True,
    ),
    "TIPO_NIVEL_INCORRECTO": ReglaDiccionario(
        codigo="TIPO_NIVEL_INCORRECTO",
        nombre="Tipo de nivel incorrecto",
        severidad="alto",
        descripcion="En el diccionario de una tabla, @level0type debe ser SCHEMA y @level1type debe ser TABLE.",
        alcance="tabla",
        activo=True,
    ),

    # --- Calidad de las descripciones -----------------------------------
    "DESCRIPCION_TABLA_INADECUADA": ReglaDiccionario(
        codigo="DESCRIPCION_TABLA_INADECUADA",
        nombre="Descripción de tabla inadecuada",
        severidad="medio",
        descripcion="La descripción de la tabla es idéntica a la de una columna o describe un identificador en lugar del propósito de la tabla.",
        alcance="tabla",
        activo=True,
    ),

    # --- Que el script se pueda ejecutar --------------------------------
    "SINTAXIS_DICCIONARIO": ReglaDiccionario(
        codigo="SINTAXIS_DICCIONARIO",
        nombre="Error de sintaxis en el diccionario",
        severidad="critico",
        descripcion="La sentencia sp_addextendedproperty no se puede ejecutar: coma sobrante, falta de '=', cadena sin cerrar o parámetro inválido.",
        alcance="tabla",
        activo=True,
    ),
    "PARAMETROS_INCOMPLETOS": ReglaDiccionario(
        codigo="PARAMETROS_INCOMPLETOS",
        nombre="Parámetros incompletos",
        severidad="alto",
        descripcion="A la sentencia le faltan parámetros obligatorios (@name, @value, @level0/1 type y name) o @level2type sin @level2name.",
        alcance="tabla",
        activo=True,
    ),
    "DOCUMENTACION_DUPLICADA": ReglaDiccionario(
        codigo="DOCUMENTACION_DUPLICADA",
        nombre="Documentación duplicada",
        severidad="alto",
        descripcion="La misma tabla o columna se documenta más de una vez con sp_addextendedproperty; SQL Server rechaza la segunda.",
        alcance="tabla",
        activo=True,
    ),
    "VALOR_SIN_COMILLAS": ReglaDiccionario(
        codigo="VALOR_SIN_COMILLAS",
        nombre="Valor sin comillas",
        severidad="critico",
        descripcion=(
            "Nombres sin comillas (@level0name = dbo). Desactivada: SQL Server acepta nombres simples "
            "sin comillas; los que sí fallarían (espacios, puntos) los detecta SINTAXIS_DICCIONARIO."
        ),
        alcance="tabla",
        activo=False,
    ),
}
