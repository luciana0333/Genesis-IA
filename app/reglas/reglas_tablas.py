# -*- coding: utf-8 -*-
"""
Reglas de estructura de tablas, según el manual de nomenclatura de base de
datos de CAJA ICA.

Este catálogo es la fuente de verdad: el analizador de tablas toma de aquí la
severidad de cada regla y omite las que tengan activo=False.

- CREATE TABLE (tabla nueva): se aplican todas las reglas.
- ALTER TABLE: solo se revisan las columnas nuevas (nombre, prefijo, COLLATE)
  y, si aceptan NULL, se pide evaluar un valor por defecto.
"""

from app.reglas.reglas_base import ReglaDiccionario


def _regla(codigo, nombre, severidad, descripcion):
    return ReglaDiccionario(
        codigo=codigo,
        nombre=nombre,
        severidad=severidad,
        descripcion=descripcion,
        alcance="tabla",
        activo=True,
    )


REGLAS_TABLAS = {
    # --- Tabla (solo CREATE) --------------------------------------------
    "TABLA_SIN_ESQUEMA": _regla(
        "TABLA_SIN_ESQUEMA", "Tabla sin esquema", "alto",
        "Toda tabla nueva debe indicar explícitamente su esquema (ej.: dbo.Persona).",
    ),
    "TABLA_NOMBRE_NO_PASCALCASE": _regla(
        "TABLA_NOMBRE_NO_PASCALCASE", "Nombre de tabla fuera del estándar", "alto",
        "El nombre de la tabla va en PascalCase: cada palabra con mayúscula inicial y el resto en "
        "minúscula, sin guiones bajos ni espacios (ej.: Persona, CuentasPorPagar).",
    ),
    "TABLA_CON_PALABRA_OMITIBLE": _regla(
        "TABLA_CON_PALABRA_OMITIBLE", "Nombre de tabla con palabra omitible", "alto",
        "El nombre de la tabla no debe incluir palabras de enlace como de, mi o su.",
    ),

    # --- Clave primaria (solo CREATE) -----------------------------------
    "PK_FALTANTE": _regla(
        "PK_FALTANTE", "Tabla sin clave primaria", "alto",
        "Toda tabla nueva debe tener un índice clúster identidad llamado nNombreTablaId.",
    ),
    "PK_COMPUESTA": _regla(
        "PK_COMPUESTA", "Clave primaria compuesta", "alto",
        "La clave primaria debe ser una sola columna identidad (nNombreTablaId).",
    ),
    "PK_NO_CLUSTER": _regla(
        "PK_NO_CLUSTER", "Clave primaria no clúster", "alto",
        "La clave primaria debe ser el índice clúster de la tabla (no NONCLUSTERED).",
    ),
    "PK_NOMBRE_INVALIDO": _regla(
        "PK_NOMBRE_INVALIDO", "Nombre de clave primaria inválido", "alto",
        "La columna de la clave primaria debe llamarse n + NombreTabla + Id (ej.: nPersonaId).",
    ),
    "PK_SIN_IDENTITY": _regla(
        "PK_SIN_IDENTITY", "Clave primaria sin IDENTITY", "alto",
        "La clave primaria debe ser una identidad de la tabla (IDENTITY).",
    ),
    "PK_NO_NUMERICA": _regla(
        "PK_NO_NUMERICA", "Clave primaria no numérica", "medio",
        "De preferencia, la clave primaria debe ser numérica (INT o BIGINT).",
    ),

    # --- Columnas (CREATE y columnas nuevas de un ALTER) ----------------
    "COLUMNA_PREFIJO_TIPO_INVALIDO": _regla(
        "COLUMNA_PREFIJO_TIPO_INVALIDO", "Prefijo de columna inválido", "alto",
        "La primera letra en minúscula indica el tipo de dato: c texto, n número, b bit, d fecha.",
    ),
    "COLUMNA_NOMBRE_NO_PASCALCASE": _regla(
        "COLUMNA_NOMBRE_NO_PASCALCASE", "Nombre de columna fuera del estándar", "alto",
        "Después del prefijo, el nombre de la columna va en PascalCase, sin guiones bajos "
        "(ej.: cPersonaNombre, dPersonaFechaNacimiento).",
    ),
    "COLUMNA_VARBINARY_PROHIBIDA": _regla(
        "COLUMNA_VARBINARY_PROHIBIDA", "Columna VARBINARY prohibida", "alto",
        "No se permiten columnas VARBINARY: guardar archivos en la base de datos la infla, "
        "degrada el rendimiento y los respaldos. Guarde el archivo fuera y registre su ruta.",
    ),
    "COLUMNA_SIN_COLLATE": _regla(
        "COLUMNA_SIN_COLLATE", "Columna sin COLLATE", "alto",
        "Las columnas de texto deben definir COLLATE, salvo en tablas de DBCMAICA.",
    ),
    "COLLATE_EN_TIPO_NO_TEXTO": _regla(
        "COLLATE_EN_TIPO_NO_TEXTO", "COLLATE en tipo no textual", "alto",
        "COLLATE solo corresponde a columnas CHAR, VARCHAR, NCHAR o NVARCHAR.",
    ),
    "COLUMNA_SIN_NOT_NULL_NI_DEFAULT": _regla(
        "COLUMNA_SIN_NOT_NULL_NI_DEFAULT", "Columna sin NOT NULL ni DEFAULT", "alto",
        "Solo CREATE: toda columna debe ser NOT NULL o tener un valor DEFAULT.",
    ),
    "COLUMNA_NULL_EN_ALTER": _regla(
        "COLUMNA_NULL_EN_ALTER", "Evaluar valor por defecto", "bajo",
        "Solo ALTER: la columna nueva acepta NULL. No se exige NOT NULL porque la tabla ya tiene "
        "registros, pero conviene evaluar un valor DEFAULT.",
    ),
}
