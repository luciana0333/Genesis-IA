# -*- coding: utf-8 -*-
"""Reglas para diccionario de procedimientos."""

from app.reglas.reglas_base import ReglaDiccionario

REGLAS_DICCIONARIO_PROCEDIMIENTOS = {
    "PROCEDIMIENTO_DUPLICADO": ReglaDiccionario(
        codigo="PROCEDIMIENTO_DUPLICADO",
        nombre="Procedimiento duplicado en el script",
        severidad="critico",
        descripcion="El mismo procedimiento se crea dos veces (dos CREATE PROCEDURE); SQL Server falla en el segundo (error 2714).",
        alcance="procedimiento",
        activo=True,
    ),
    "OBJETO_SIN_ESQUEMA": ReglaDiccionario(
        codigo="OBJETO_SIN_ESQUEMA",
        nombre="Procedimiento sin esquema",
        severidad="alto",
        descripcion="El procedimiento indica su esquema en el CREATE o ALTER (ej.: dbo.PA_Cliente_Sel_PorId).",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_SIN_PREFIJO_PA": ReglaDiccionario(
        codigo="PROCEDIMIENTO_SIN_PREFIJO_PA",
        nombre="Nombre sin prefijo PA_",
        severidad="alto",
        descripcion="Al crear el procedimiento, su nombre empieza con PA_ (PA_Tabla_Acción_Finalidad).",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_NOMBRE_INCOMPLETO": ReglaDiccionario(
        codigo="PROCEDIMIENTO_NOMBRE_INCOMPLETO",
        nombre="Nombre de procedimiento incompleto",
        severidad="alto",
        descripcion="Al crear el procedimiento, su nombre indica la tabla y la acción.",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_ACCION_SIN_SEPARAR": ReglaDiccionario(
        codigo="PROCEDIMIENTO_ACCION_SIN_SEPARAR",
        nombre="Acción sin separar",
        severidad="alto",
        descripcion="La acción va separada de la finalidad con guion bajo (PA_Registro_Sel_Ejecuciones).",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_ACCION_NO_ABREVIADA": ReglaDiccionario(
        codigo="PROCEDIMIENTO_ACCION_NO_ABREVIADA",
        nombre="Acción sin abreviar",
        severidad="alto",
        descripcion="Las acciones estándar usan la abreviatura del manual: Sel, Upd, Ins, Del.",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_SIN_ACCION": ReglaDiccionario(
        codigo="PROCEDIMIENTO_SIN_ACCION",
        nombre="Nombre sin acción",
        severidad="alto",
        descripcion="Después de la tabla va la acción: Sel, Upd, Ins, Del o un verbo (personalizado).",
        alcance="procedimiento",
        activo=True,
    ),
    "PARAMETRO_NO_EXISTE": ReglaDiccionario(
        codigo="PARAMETRO_NO_EXISTE",
        nombre="Parámetro documentado que no existe",
        severidad="alto",
        descripcion="Se documenta un parámetro que el procedimiento no declara (mal escrito o eliminado).",
        alcance="procedimiento",
        activo=True,
    ),
    "PARAMETROS_INCOMPLETOS": ReglaDiccionario(
        codigo="PARAMETROS_INCOMPLETOS",
        nombre="Sentencia incompleta",
        severidad="alto",
        descripcion="A la sentencia sp_addextendedproperty le faltan datos obligatorios (@name, @value, niveles).",
        alcance="procedimiento",
        activo=True,
    ),
    "SINTAXIS_DICCIONARIO": ReglaDiccionario(
        codigo="SINTAXIS_DICCIONARIO",
        nombre="Error de sintaxis en el diccionario",
        severidad="critico",
        descripcion="El script del diccionario tiene errores de escritura y SQL Server no lo podría ejecutar.",
        alcance="procedimiento",
        activo=True,
    ),
    "NOMBRE_PROPIEDAD_INCORRECTO": ReglaDiccionario(
        codigo="NOMBRE_PROPIEDAD_INCORRECTO",
        nombre="Nombre de propiedad mal escrito",
        severidad="alto",
        descripcion=(
            "El nombre de la propiedad parece MS_Description pero está mal escrito (MS_Descripcion, "
            "Descripcion...): la descripción no se reconoce como la del diccionario."
        ),
        alcance="procedimiento",
        activo=True,
    ),
    "DOCUMENTACION_DUPLICADA": ReglaDiccionario(
        codigo="DOCUMENTACION_DUPLICADA",
        nombre="Documentación duplicada",
        severidad="alto",
        descripcion="El mismo procedimiento o parámetro se documenta más de una vez con sp_addextendedproperty; SQL Server rechaza la segunda.",
        alcance="procedimiento",
        activo=True,
    ),
    "ESQUEMA_NO_COINCIDE": ReglaDiccionario(
        codigo="ESQUEMA_NO_COINCIDE",
        nombre="Esquema no coincide",
        severidad="alto",
        descripcion="El esquema documentado en @level0name no coincide con el esquema real del objeto.",
        alcance="procedimiento",
        activo=True,
    ),
    "NOMBRE_VACIO": ReglaDiccionario(
        codigo="NOMBRE_VACIO",
        nombre="Nombre vacío en el diccionario",
        severidad="alto",
        descripcion="@level0name, @level1name o @level2name no pueden ir vacíos (N''): deben indicar el "
                    "esquema, el procedimiento o el parámetro documentado.",
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
        severidad="alto",
        descripcion="El parámetro declarado falta en el diccionario. Solo CREATE PROCEDURE (en ALTER se pide validar).",
        alcance="procedimiento",
        activo=True,
    ),
    "PROCEDIMIENTO_SIN_DESCRIPCION": ReglaDiccionario(
        codigo="PROCEDIMIENTO_SIN_DESCRIPCION",
        nombre="Procedimiento no documentado",
        severidad="alto",
        descripcion="El procedimiento no tiene una descripción válida a nivel PROCEDURE en el diccionario. Alto en CREATE PROCEDURE; medio en ALTER.",
        alcance="procedimiento",
        activo=True,
    ),
    "DESCRIPCION_VACIA": ReglaDiccionario(
        codigo="DESCRIPCION_VACIA",
        nombre="Descripción de parámetro vacía",
        severidad="medio",
        descripcion="El parámetro figura en el diccionario, pero no cuenta con una descripción.",
        alcance="procedimiento",
        activo=True,
    ),
    "DESCRIPCION_PROCEDIMIENTO_VACIA": ReglaDiccionario(
        codigo="DESCRIPCION_PROCEDIMIENTO_VACIA",
        nombre="Procedimiento sin descripción",
        severidad="medio",
        descripcion="El diccionario del procedimiento está documentado, pero su descripción está vacía.",
        alcance="procedimiento",
        activo=True,
    ),
    "ERROR_ORTOGRAFICO": ReglaDiccionario(
        codigo="ERROR_ORTOGRAFICO",
        nombre="Palabra mal escrita en la descripción",
        severidad="medio",
        descripcion=(
            "La descripción del procedimiento o de un parámetro tiene palabras mal escritas. "
            "No exige tildes. Vocabulario del equipo: app/reglas/vocabulario_tecnico.txt."
        ),
        alcance="procedimiento",
        activo=True,
    ),
    "VALIDAR_DOCUMENTACION_ALTER": ReglaDiccionario(
        codigo="VALIDAR_DOCUMENTACION_ALTER",
        nombre="Validar documentación existente",
        severidad="bajo",
        descripcion=(
            "En un ALTER PROCEDURE, al diccionario le falta la descripción del procedimiento o de un "
            "parámetro. No es error: el objeto ya existía y puede estar documentado de antes; validar."
        ),
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
