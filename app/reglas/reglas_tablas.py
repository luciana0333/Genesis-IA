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
    "CREATE_SIN_PARENTESIS": _regla(
        "CREATE_SIN_PARENTESIS", "Columnas sin paréntesis", "critico",
        "En un CREATE TABLE las columnas van entre paréntesis; sin ellos SQL Server no puede crear la tabla.",
    ),
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
    "COLUMNA_NOMBRE_CON_NUMERO": _regla(
        "COLUMNA_NOMBRE_CON_NUMERO", "Nombre de columna con números", "alto",
        "El nombre de una columna nueva no puede contener números (ej.: cNombre89).",
    ),
    "COLUMNA_VARBINARY_PROHIBIDA": _regla(
        "COLUMNA_VARBINARY_PROHIBIDA", "Columna para documentos prohibida", "alto",
        "No se permiten columnas VARBINARY ni IMAGE: la base de datos es solo para datos "
        "transaccionales; los documentos van en una solución externa y se registra su ruta.",
    ),
    "COLUMNA_TIPO_LEGACY": _regla(
        "COLUMNA_TIPO_LEGACY", "Tipo de dato legacy", "alto",
        "No se permiten tipos legacy (TEXT, NTEXT, REAL): usar VARCHAR(MAX), NVARCHAR(MAX) o DECIMAL.",
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

    # --- Índices (segunda cajita: CREATE INDEX de la tabla) --------------
    "INDICE_SINTAXIS_INVALIDA": _regla(
        "INDICE_SINTAXIS_INVALIDA", "Índice mal escrito", "critico",
        "El CREATE INDEX debe tener nombre, tabla (ON Esquema.Tabla) y columnas entre paréntesis.",
    ),
    "INDICE_PREFIJO_INVALIDO": _regla(
        "INDICE_PREFIJO_INVALIDO", "Prefijo de índice inválido", "alto",
        "El prefijo indica el tipo: IX clúster, IXN nonclustered, IXU unique clúster, IXUN unique nonclustered.",
    ),
    "INDICE_NOMBRE_NO_ESTANDAR": _regla(
        "INDICE_NOMBRE_NO_ESTANDAR", "Nombre de índice fuera del estándar", "alto",
        "Formato: <Prefijo>_<Tabla>_<Campos indexados>_INC<nn> (nn = columnas incluidas con dos dígitos, "
        "ej.: INC02; solo si hay INCLUDE).",
    ),
    "INDICE_SIN_ESQUEMA": _regla(
        "INDICE_SIN_ESQUEMA", "Índice sin esquema", "alto",
        "El índice se crea sobre Esquema.Tabla (ej.: ON dbo.Cliente).",
    ),
    "INDICE_TABLA_EXISTENTE": _regla(
        "INDICE_TABLA_EXISTENTE", "Índice sobre tabla existente", "medio",
        "Si el índice es de una tabla que ya existe (no se crea en el script), se valida si de verdad lo "
        "necesita: consultas que lo usarán e índices que ya tiene.",
    ),
    "INDICE_COLUMNA_NO_EXISTE": _regla(
        "INDICE_COLUMNA_NO_EXISTE", "Columna del índice inexistente", "critico",
        "Las columnas del índice (y de su INCLUDE) deben existir en la tabla.",
    ),
    "INDICE_COLUMNA_REPETIDA": _regla(
        "INDICE_COLUMNA_REPETIDA", "Columna repetida en el índice", "critico",
        "Una columna no puede repetirse en la clave del índice ni estar a la vez en la clave y en el INCLUDE.",
    ),
    "INDICE_COLUMNA_NO_INDEXABLE": _regla(
        "INDICE_COLUMNA_NO_INDEXABLE", "Columna no indexable", "critico",
        "Una columna VARCHAR(MAX), NVARCHAR(MAX), VARBINARY(MAX), TEXT, IMAGE o XML no puede ser clave de un índice.",
    ),
    "INDICE_CLUSTERED_CON_PK": _regla(
        "INDICE_CLUSTERED_CON_PK", "Índice clúster con PK clúster", "medio",
        "La clave primaria identidad siempre es el índice clúster: los demás índices se definen NONCLUSTERED.",
    ),
    "INDICE_IDENTIFICA_POR_DESCRIPCION": _regla(
        "INDICE_IDENTIFICA_POR_DESCRIPCION", "Descripción usada como identificador", "alto",
        "Una columna de texto descriptivo no identifica registros: un índice UNIQUE o CLUSTERED no la usa "
        "como clave; la tabla se identifica por su clave primaria identidad (nNombreTablaId).",
    ),
    "INDICE_COLUMNA_DESCRIPTIVA": _regla(
        "INDICE_COLUMNA_DESCRIPTIVA", "Columna descriptiva en el índice", "medio",
        "Se evita indexar texto descriptivo (descripción, dirección, observación, opinión, comentario...), "
        "con o sin prefijo: se indexan "
        "columnas que sirven para buscar o filtrar (códigos, fechas, estados).",
    ),
    "INDICE_DUPLICADO": _regla(
        "INDICE_DUPLICADO", "Índice duplicado", "medio",
        "No debe haber dos índices con las mismas columnas clave (ni uno igual a la clave primaria).",
    ),
}
