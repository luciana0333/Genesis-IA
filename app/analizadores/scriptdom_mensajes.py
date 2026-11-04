# -*- coding: utf-8 -*-
"""Mensajes y severidad de lo que encuentra el revisor de ScriptDom (scriptdom_revisor.cs).

Cada tipo devuelve (qué se encontró, qué hacer), con el estilo de la usuaria: en crítico y alto la acción va
en infinitivo; en medio y bajo, «Se recomienda …, ya que …». Si hay varios casos del mismo tipo se juntan
en una sola observación con todas sus líneas.

Lo que hace fallar el script o da un resultado equivocado se comprobó en SQL Server (error al lado).
"""

import difflib
from typing import Callable, Dict, List, Optional, Tuple

from app.modelos.hallazgo import Severidad

Partes = Tuple[str, str]

# Tipos de SQL Server, para reconocer uno mal escrito (VARCHR, DATTIME) sin confundirlo con un tipo propio.
_TIPOS_SQL = [
    "BIGINT", "BINARY", "BIT", "CHAR", "DATE", "DATETIME", "DATETIME2", "DATETIMEOFFSET", "DECIMAL", "FLOAT",
    "IMAGE", "INT", "MONEY", "NCHAR", "NTEXT", "NUMERIC", "NVARCHAR", "REAL", "SMALLDATETIME", "SMALLINT",
    "SMALLMONEY", "TEXT", "TIME", "TINYINT", "UNIQUEIDENTIFIER", "VARBINARY", "VARCHAR", "XML",
]
_TIPOS_VALIDOS = {"SYSNAME", "HIERARCHYID", "GEOGRAPHY", "GEOMETRY", "SQL_VARIANT", "TIMESTAMP", "ROWVERSION"}


def _cantidad(numero: int, singular: str, plural: str) -> str:
    return f"{numero} {singular if numero == 1 else plural}"


def _lineas(lineas: List[int]) -> str:
    lineas = sorted(set(int(linea) for linea in lineas))
    if len(lineas) == 1:
        return f"línea {lineas[0]}"
    return f"líneas {', '.join(map(str, lineas[:-1]))} y {lineas[-1]}"


# --- 1 · Haría fallar el script (crítico) --------------------------------------------------------------
def _insert(h: Dict) -> Partes:
    columnas, valores = int(h["columnas"]), int(h["valores"])
    es_select = h.get("origen") == "SELECT"
    if es_select:
        error = 121 if valores > columnas else 120
        envia = f"su SELECT devuelve {_cantidad(valores, 'columna', 'columnas')}"
    else:
        error = 110 if valores > columnas else 109
        envia = f"envía {_cantidad(valores, 'valor', 'valores')}"
    tabla = f" {h['tabla']}" if h.get("tabla") else ""
    return (f"Se identificó un INSERT INTO{tabla} que indica {_cantidad(columnas, 'columna', 'columnas')}, pero {envia}.",
            f"Igualar la cantidad de {'columnas del INSERT y del SELECT' if es_select else 'columnas y de valores'}, "
            f"ya que SQL Server no ejecutará el INSERT (error {error}).")


def _columna_repetida(h: Dict) -> Partes:
    return (f"Se identificó que la columna {h['columna']} se define dos veces en la tabla {h['tabla']} "
            f"({_lineas([h['primera'], h['linea']])}).",
            "Retirar la columna repetida, ya que SQL Server no podrá crear la tabla (error 2705).")


def _temporal_dos_veces(h: Dict) -> Partes:
    return (f"Se identificó que la tabla temporal {h['tabla']} se crea dos veces en el mismo bloque "
            f"({_lineas([h['primera'], h['linea']])}).",
            "Usar un nombre distinto para cada una, ya que SQL Server no permite crear dos veces la misma temporal "
            "en un procedimiento, aunque se elimine antes o esté en un IF / ELSE (error 2714).")


def _dos_pk(h: Dict) -> Partes:
    return (f"Se identificó que la tabla {h['tabla']} define {h['cantidad']} PRIMARY KEY.",
            "Dejar una sola, ya que una tabla solo puede tener una clave primaria y SQL Server no podrá crearla "
            "(error 8110).")


def _dos_identity(h: Dict) -> Partes:
    return (f"Se identificó que la tabla {h['tabla']} define {h['cantidad']} columnas IDENTITY.",
            "Dejar una sola, ya que una tabla solo puede tener una columna IDENTITY y SQL Server no podrá crearla "
            "(error 2744).")


def _alias(h: Dict) -> Partes:
    if h.get("esAlias"):
        return (f"Se identificó que el alias {h['nombre']} se usa dos veces en el mismo FROM.",
                "Usar un alias distinto para cada tabla, ya que SQL Server no ejecutará la consulta (error 1011).")
    return (f"Se identificó que {h['nombre']} aparece dos veces en el mismo FROM con el mismo nombre.",
            "Asignar un alias distinto a cada una, ya que SQL Server no ejecutará la consulta (error 1013).")


def _punto_y_coma(h: Dict) -> Partes:
    instruccion = h["instruccion"]
    return (f"Se identificó que la instrucción anterior al {instruccion} (línea {h['anterior']}) no termina en «;».",
            f"Agregar «;» al final de esa instrucción, ya que SQL Server necesita el «;» antes de un {instruccion} y "
            f"no ejecutará el código sin él (error {319 if instruccion == 'WITH' else 102}).")


def _throw_alias(h: Dict) -> Partes:
    return ("Se identificó un THROW justo después de un SELECT sin «;», por lo que SQL Server lo toma como el nombre "
            "de una columna del SELECT y el error nunca se relanza.",
            "Agregar «;» al final del SELECT, ya que, sin él, el error se pierde en silencio y el procedimiento "
            "continúa como si no hubiera fallado.")


def _no_declarada(h: Dict) -> Partes:
    return (f"Se identificó que la variable {h['variable']} se usa sin estar declarada (o antes de su DECLARE).",
            "Declararla con DECLARE antes de usarla, ya que SQL Server no ejecutará el código (error 137).")


def _dos_veces(h: Dict) -> Partes:
    return (f"Se identificó que {h['variable']} se declara dos veces ({_lineas([h['primera'], h['linea']])}).",
            "Dejar una sola declaración o usar otro nombre, ya que SQL Server no ejecutará el código (error 134).")


def _union(h: Dict) -> Partes:
    return (f"Se identificó un {h['operacion']} cuyo primer SELECT devuelve {_cantidad(int(h['primera']), 'columna', 'columnas')} "
            f"y el siguiente {_cantidad(int(h['segunda']), 'columna', 'columnas')}.",
            "Igualar la cantidad de columnas de cada SELECT, ya que SQL Server no ejecutará la consulta (error 205).")


def _tipo_desconocido(h: Dict) -> Optional[Partes]:
    tipo = str(h["tipoDato"]).upper()
    if tipo in _TIPOS_VALIDOS:
        return None
    parecido = difflib.get_close_matches(tipo, _TIPOS_SQL, n=1, cutoff=0.75)
    if not parecido:
        return None  # puede ser un tipo propio de la base
    return (f"Se identificó el tipo de dato {h['tipoDato']}, que SQL Server no reconoce (¿quiso decir {parecido[0]}?).",
            f"Corregir el nombre del tipo (ej.: {parecido[0]}), ya que SQL Server no ejecutará el código (error 2715).")


def _tamano(h: Dict) -> Partes:
    return (f"Se identificó el tipo {h['valor']}, fuera del tamaño permitido para {h['tipoDato']} ({h['limite']}).",
            f"Corregir el tamaño, ya que SQL Server no ejecutará el código (error {h['error']}).")


def _cte_columnas(h: Dict) -> Partes:
    return (f"Se identificó que la CTE {h['cte']} indica {_cantidad(int(h['columnas']), 'columna', 'columnas')}, pero su "
            f"consulta devuelve {_cantidad(int(h['consulta']), 'columna', 'columnas')}.",
            "Igualar la cantidad de columnas, ya que SQL Server no ejecutará la consulta (error 8159).")


def _cte_nombre(h: Dict) -> Partes:
    return (f"Se identificó que la CTE {h['cte']} se define dos veces en el mismo WITH.",
            "Usar un nombre distinto para cada CTE, ya que SQL Server no ejecutará la consulta (error 239).")


def _break(h: Dict) -> Partes:
    return (f"Se identificó un {h['instruccion']} fuera de un WHILE.",
            f"Retirarlo o ubicarlo dentro del WHILE, ya que {h['instruccion']} solo funciona dentro de un bucle y "
            f"SQL Server no ejecutará el código (error 135).")


def _goto(h: Dict) -> Partes:
    return (f"Se identificó un GOTO {h['etiqueta']}, pero la etiqueta {h['etiqueta']}: no existe en el bloque.",
            "Crear la etiqueta o corregir su nombre, ya que SQL Server no ejecutará el código (error 133).")


def _orden_subconsulta(h: Dict) -> Partes:
    return ("Se identificó un ORDER BY dentro de una subconsulta, tabla derivada, CTE o vista, sin TOP.",
            "Retirar el ORDER BY (o agregar TOP si se necesita), ya que ahí no ordena el resultado final y SQL Server "
            "no ejecutará la consulta (error 1033).")


def _agregado_where(h: Dict) -> Partes:
    return ("Se identificó una función de agregado (SUM, COUNT, MAX…) en el WHERE.",
            "Moverla a un HAVING o a una subconsulta, ya que SQL Server no la permite en el WHERE (error 147).")


# --- 2 · Errores silenciosos (alto) --------------------------------------------------------------------
def _varchar_sin_tamano(h: Dict) -> Partes:
    donde = "en un CAST o CONVERT" if h.get("contexto") == "conversion" else "al declarar"
    return (f"Se identificó {h['tipoDato']} sin tamaño {donde}, por lo que SQL Server lo toma como "
            f"{h['tipoDato']}({h['largo']}).",
            f"Indicar el tamaño (ej.: {h['tipoDato']}(100)), ya que, sin él, SQL Server corta el texto a "
            f"{_cantidad(int(h['largo']), 'carácter', 'caracteres')} sin avisar.")


def _con_null(h: Dict) -> Partes:
    return (f"Se identificó la comparación {h['comparacion']}, que nunca es verdadera.",
            f"Usar {'IS NOT NULL' if h.get('negada') else 'IS NULL'}, ya que en SQL Server una comparación con NULL "
            f"usando = o <> no devuelve verdadero ni falso.")


def _isnull_trunca(h: Dict) -> Partes:
    return (f"Se identificó ISNULL({h['variable']}, '{h['texto']}'), donde {h['variable']} admite "
            f"{_cantidad(int(h['largo']), 'carácter', 'caracteres')}, por lo que devuelve '{h['queda']}'.",
            "Usar COALESCE o ampliar el tamaño de la variable, ya que ISNULL corta el texto al tamaño de la primera "
            "expresión sin avisar.")


def _texto_largo(h: Dict) -> Partes:
    return (f"Se identificó que a {h['variable']}, de {_cantidad(int(h['largo']), 'carácter', 'caracteres')}, se le "
            f"asigna '{h['texto']}', por lo que queda '{h['queda']}'.",
            "Ampliar el tamaño de la variable, ya que SQL Server corta el texto sin avisar.")


def _varias_filas(h: Dict) -> Partes:
    return (f"Se identificó SELECT {h['variable']} = … FROM sin WHERE, TOP ni agregado.",
            f"Se recomienda filtrar a una sola fila (WHERE por la clave o TOP 1 con ORDER BY), ya que si la tabla "
            f"tiene varias filas {h['variable']} queda con el valor de cualquiera de ellas.")


def _not_in(h: Dict) -> Partes:
    return (f"Se identificó {h['expresion']} NOT IN (SELECT …).",
            "Se recomienda usar NOT EXISTS, ya que si la subconsulta devuelve un solo NULL, NOT IN no trae ninguna "
            "fila.")


def _top(h: Dict) -> Partes:
    return (f"Se identificó un {h['top']} sin ORDER BY.",
            "Se recomienda agregar un ORDER BY, ya que sin él SQL Server puede devolver una fila distinta en cada "
            "ejecución.")


def _between(h: Dict) -> Partes:
    return (f"Se identificó {h['expresion']} BETWEEN … AND {h['hasta']}, donde {h['expresion']} guarda fecha y hora.",
            f"Usar {h['expresion']} >= fecha inicial AND {h['expresion']} < día siguiente a la fecha final, ya que "
            f"BETWEEN deja fuera todo el último día después de las 00:00.")


def _rowcount(h: Dict) -> Partes:
    return (f"Se identificó que {h['variable']} se lee justo después de otra instrucción (línea {h['anterior']}) y "
            f"no después del INSERT, UPDATE o DELETE.",
            f"Guardar {h['variable']} en una variable inmediatamente después de la instrucción que interesa, ya que "
            f"cada instrucción, incluso un SET, lo reemplaza.")


def _identity(h: Dict) -> Partes:
    return ("Se identificó el uso de @@IDENTITY.",
            "Se recomienda usar SCOPE_IDENTITY(), ya que @@IDENTITY puede devolver el id generado por un trigger en "
            "otra tabla.")


_VALOR_INICIAL = {"varchar": "''", "nvarchar": "N''", "char": "''", "nchar": "N''", "bit": "0", "date": "GETDATE()",
                  "datetime": "GETDATE()", "datetime2": "GETDATE()", "smalldatetime": "GETDATE()"}


def _sin_valor(h: Dict) -> Partes:
    familia = str(h.get("familia") or "").lower()
    inicial = _VALOR_INICIAL.get(familia, "0")
    return (f"Se identificó que {h['variable']} se lee antes de recibir un valor, por lo que vale NULL.",
            f"Se recomienda asignarle un valor inicial (ej.: SET {h['variable']} = {inicial}) o confirmar que el NULL "
            f"es intencional, ya que una operación con NULL (+ 1, concatenación, comparación) también da NULL.")


def _output_sin_valor(h: Dict) -> Partes:
    return (f"Se identificó que el parámetro OUTPUT {h['variable']} nunca recibe un valor.",
            "Asignarle el valor que debe devolver, ya que el procedimiento siempre lo devolverá en NULL.")


def _division(h: Dict) -> Partes:
    return (f"Se identificó la división {h['expresion']} sin proteger el divisor.",
            f"Se recomienda usar NULLIF({h['divisor']}, 0), ya que si el divisor es 0 el procedimiento falla con "
            f"error de división entre cero.")


def _rollback(h: Dict) -> Partes:
    return ("Se identificó un ROLLBACK en el CATCH sin validar que haya una transacción abierta.",
            "Usar IF @@TRANCOUNT > 0 ROLLBACK, ya que si el error ocurrió antes del BEGIN TRAN el ROLLBACK falla "
            "(error 3903) y oculta el error original.")


def _transaccion_sin_try(h: Dict) -> Partes:
    return ("Se identificó un BEGIN TRANSACTION fuera de un BEGIN TRY y sin SET XACT_ABORT ON.",
            "Ubicar la transacción dentro de BEGIN TRY … BEGIN CATCH con su ROLLBACK, ya que si una instrucción "
            "falla la transacción puede quedar abierta y bloquear las tablas.")


def _inalcanzable(h: Dict) -> Partes:
    return (f"Se identificó código después del RETURN de la línea {h['retorno']}.",
            "Se recomienda retirarlo o revisar la lógica, ya que ese código nunca se ejecuta.")


# --- 3 · Rendimiento -----------------------------------------------------------------------------------
def _apply(h: Dict) -> Partes:
    return (f"Se identificaron {h['cantidad']} subconsultas a {h['tabla']} con la misma condición en el SELECT.",
            f"Se recomienda evaluar unirlas en un {h['apply']}, ya que la tabla se leería una sola vez por fila en "
            f"lugar de {h['cantidad']} (ej.: {h['ejemplo']}).")


_SUGERENCIA_FUNCION = {
    "YEAR": "comparar con un rango de fechas (ej.: dFecha >= '20260101' AND dFecha < '20270101')",
    "MONTH": "comparar con un rango de fechas",
    "DAY": "comparar con un rango de fechas",
    "DATEPART": "comparar con un rango de fechas",
    "EOMONTH": "comparar con un rango de fechas",
    "CONVERT": "comparar la columna tal cual con un rango (ej.: dFecha >= @dDia AND dFecha < DATEADD(DAY, 1, @dDia))",
    "CAST": "comparar la columna tal cual con un rango (ej.: dFecha >= @dDia AND dFecha < DATEADD(DAY, 1, @dDia))",
    "ISNULL": "comparar la columna directamente (ej.: cCodigo = 'X'), ya que un NULL tampoco sería igual al valor",
    "UPPER": "comparar la columna directamente, ya que el COLLATE de la empresa no distingue mayúsculas",
    "LOWER": "comparar la columna directamente, ya que el COLLATE de la empresa no distingue mayúsculas",
    "RTRIM": "comparar la columna directamente, ya que el = ya ignora los espacios del final",
}


def _funcion_columna(h: Dict) -> Partes:
    if h.get("ejemplo"):  # ISNULL: la condición reescrita sin perder las filas con NULL
        sugerencia = f"reescribir la condición sin la función (ej.: {h['ejemplo']})"
    else:
        sugerencia = _SUGERENCIA_FUNCION.get(h["funcion"], "aplicar la función al otro lado de la comparación")
    return (f"Se identificó {h['expresion']} en una condición, aplicando {h['funcion']} sobre la columna {h['columna']}.",
            f"Se recomienda {sugerencia}, ya que una función sobre la columna impide usar su índice.")


def _like(h: Dict) -> Partes:
    return (f"Se identificó {h['columna']} LIKE '{h['patron']}', con el comodín al inicio.",
            "Se recomienda evaluar si la búsqueda puede hacerse con el comodín solo al final, ya que con el comodín al "
            "inicio no se aprovechan los índices y se recorre toda la tabla.")


def _count(h: Dict) -> Partes:
    return (f"Se identificó {h['comparacion']} para saber si hay registros.",
            f"Se recomienda usar {h['propuesta']} (SELECT 1 FROM …), ya que EXISTS se detiene en el primer registro "
            f"y COUNT(*) los cuenta todos.")


def _funcion_escalar(h: Dict) -> Partes:
    return (f"Se identificó la función {h['funcion']} dentro de una consulta.",
            "Se recomienda evaluar reemplazarla por un JOIN o un APPLY, ya que una función escalar propia se ejecuta "
            "una vez por cada fila.")


def _conversion(h: Dict) -> Partes:
    return (f"Se identificó la comparación de la columna de texto {h['columna']} con {h['otro']} ({h['tipoDato']}).",
            "Se recomienda comparar con un valor del mismo tipo (ej.: entre comillas o como VARCHAR), ya que SQL "
            "Server convierte la columna en cada fila y no puede usar su índice.")


def _or(h: Dict) -> Partes:
    return (f"Se identificó un OR entre las columnas {h['primera']} y {h['segunda']} en el WHERE.",
            "Se recomienda evaluar separarlo en dos consultas con UNION ALL, ya que un OR entre columnas distintas "
            "suele impedir el uso de los índices.")


def _union_sin_all(h: Dict) -> Partes:
    return ("Se identificó un UNION sin ALL.",
            "Se recomienda usar UNION ALL si no puede haber filas repetidas entre las consultas, ya que UNION ordena "
            "y compara todo el resultado para quitar duplicados.")


def _distinct(h: Dict) -> Partes:
    return ("Se identificó un SELECT DISTINCT con JOIN.",
            "Se recomienda revisar las condiciones del JOIN, ya que el DISTINCT puede estar ocultando filas repetidas "
            "por una condición incompleta y obliga a ordenar todo el resultado.")


def _orden_insert(h: Dict) -> Partes:
    tabla = f" a {h['tabla']}" if h.get("tabla") else ""
    return (f"Se identificó un ORDER BY en un INSERT … SELECT{tabla}.",
            "Se recomienda retirarlo, ya que no deja la tabla ordenada (una tabla no tiene orden) y solo agrega "
            "trabajo.")


# --- ISNULL sobre columnas: validar si la columna acepta NULL -----------------------------------------
def _de_la_columna(h: Dict) -> str:
    if h.get("temporal"):
        return (f"sobre la columna {h['columnaTemporal']} de {h['temporal']}, que se llena desde "
                f"{h['tabla']}.{h['columna']}")
    return f"sobre la columna {h['columna']} de {h['tabla']}"


def _isnull_validar(h: Dict) -> Partes:
    return (f"Se identificó {h['expresion']} {_de_la_columna(h)}.",
            "Se recomienda validar si la columna acepta valores nulos con la consulta adjunta, ya que, si no los "
            "acepta, el ISNULL no es necesario.")


def _isnull_condicion(h: Dict) -> Partes:
    reescrita = f" (si los acepta, se puede reescribir sin la función: {h['ejemplo']})" if h.get("ejemplo") else ""
    return (f"Se identificó {h['expresion']} en una condición, {_de_la_columna(h)}.",
            f"Se recomienda validar si la columna acepta valores nulos con la consulta adjunta, ya que, si no los "
            f"acepta, el ISNULL no es necesario y en una condición impide usar el índice{reescrita}.")


def _isnull_not_null(h: Dict) -> Partes:
    indice = " y en una condición impide usar el índice" if h.get("contexto") == "condicion" else ""
    return (f"Se identificó {h['expresion']} sobre la columna {h['columna']} de {h['tabla']}, que se define NOT NULL "
            f"(línea {h['definicion']}).",
            f"Se recomienda retirar el ISNULL, ya que la columna no acepta valores nulos{indice}.")


def consulta_de_nulos(hechos: List[Dict]) -> Optional[str]:
    """
    Consulta lista para copiar: si cada columna acepta NULL, según la definición de su tabla física. Una sola
    consulta con todas las columnas; las tablas de otra base (DBCMACICA.dbo.T) se consultan en esa base.
    """
    por_base: Dict[str, Dict[Tuple[str, str], List[str]]] = {}
    for hecho in hechos:
        partes = [p.strip("[]") for p in str(hecho["tabla"]).split(".")]
        base, esquema, tabla = ([""] * (3 - len(partes)) + partes)[-3:]
        columnas = por_base.setdefault(base, {}).setdefault((esquema, tabla), [])
        if hecho["columna"] not in columnas:
            columnas.append(hecho["columna"])
    if not por_base:
        return None
    consultas = []
    for base, tablas in por_base.items():
        condiciones = []
        for (esquema, tabla), columnas in tablas.items():
            filtro = f"TABLE_SCHEMA = '{esquema}' AND " if esquema else ""
            lista = ", ".join(f"'{c}'" for c in columnas)
            condiciones.append(f"({filtro}TABLE_NAME = '{tabla}' AND COLUMN_NAME IN ({lista}))")
        origen = f"{base}.INFORMATION_SCHEMA.COLUMNS" if base else "INFORMATION_SCHEMA.COLUMNS"
        consultas.append(
            f"SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, IS_NULLABLE\nFROM {origen}\nWHERE "
            + "\n   OR ".join(condiciones)
        )
    return "-- IS_NULLABLE = NO: la columna no acepta NULL y el ISNULL no es necesario\n" \
        + "\nUNION ALL\n".join(consultas) + "\nORDER BY TABLE_NAME, COLUMN_NAME;"


# --- 4 · Seguridad (alto) ------------------------------------------------------------------------------
def _inyeccion(h: Dict) -> Partes:
    return (f"Se identificó SQL dinámico armado concatenando el parámetro {h['variable']}.",
            f"Usar sp_executesql con parámetros (ej.: … WHERE cCodigo = @p', N'@p VARCHAR(20)', @p = {h['variable']}), "
            f"ya que concatenar un parámetro permite la inyección de SQL.")


def _xp_cmdshell(h: Dict) -> Partes:
    return ("Se identificó el uso de xp_cmdshell.",
            "Retirarlo, ya que ejecuta comandos del sistema operativo desde la base de datos y es un riesgo de "
            "seguridad.")


def _credencial(h: Dict) -> Partes:
    return ("Se identificó un usuario o una contraseña escritos en el código.",
            "Retirarlos y usar la autenticación integrada o una credencial del servidor, ya que el código queda en "
            "repositorios y respaldos donde cualquiera puede leerlos.")


# --- 6 · Mantenibilidad (bajo) -------------------------------------------------------------------------
def _anidamiento(h: Dict) -> Partes:
    return (f"Se identificaron {h['niveles']} niveles de IF / WHILE uno dentro de otro.",
            "Se recomienda simplificar la lógica (condiciones combinadas, salidas tempranas con RETURN o "
            "procedimientos separados), ya que tantos niveles dificultan leer y mantener el código.")


def _bloque(h: Dict) -> Partes:
    return (f"Se identificó la misma instrucción {h['instruccion']} repetida en las {_lineas(h['lineas'])}.",
            "Se recomienda escribirla una sola vez (en una tabla temporal, una CTE o un procedimiento), ya que "
            "repetida hay que corregirla en cada lugar.")


def _parametro_sin_uso(h: Dict) -> Partes:
    return (f"Se identificó que el parámetro {h['variable']} no se usa.",
            "Se recomienda retirarlo o revisar si falta usarlo, ya que confunde a quien llama al procedimiento.")


def _case_sin_else(h: Dict) -> Partes:
    return ("Se identificó un CASE sin ELSE.",
            "Se recomienda agregar un ELSE, ya que si ningún WHEN se cumple el resultado es NULL.")


def _largo(h: Dict) -> Partes:
    return (f"Se identificó un procedimiento de {h['lineas']} líneas.",
            "Se recomienda dividirlo en procedimientos más pequeños, ya que uno tan largo es difícil de revisar y de "
            "mantener.")


# tipo -> (severidad, mensaje)
MENSAJES: Dict[str, Tuple[Severidad, Callable[[Dict], Optional[Partes]]]] = {
    "INSERT_COLUMNAS_NO_COINCIDEN": (Severidad.CRITICO, _insert),
    "COLUMNA_REPETIDA_EN_TABLA": (Severidad.CRITICO, _columna_repetida),
    "TEMPORAL_CREADA_DOS_VECES": (Severidad.CRITICO, _temporal_dos_veces),
    "DOS_PRIMARY_KEY": (Severidad.CRITICO, _dos_pk),
    "DOS_IDENTITY": (Severidad.CRITICO, _dos_identity),
    "ALIAS_REPETIDO_EN_FROM": (Severidad.CRITICO, _alias),
    "PUNTO_Y_COMA_FALTANTE": (Severidad.CRITICO, _punto_y_coma),
    "THROW_TOMADO_COMO_ALIAS": (Severidad.CRITICO, _throw_alias),
    "VARIABLE_NO_DECLARADA": (Severidad.CRITICO, _no_declarada),
    "VARIABLE_DECLARADA_DOS_VECES": (Severidad.CRITICO, _dos_veces),
    "UNION_COLUMNAS_DISTINTAS": (Severidad.CRITICO, _union),
    "TIPO_DESCONOCIDO": (Severidad.CRITICO, _tipo_desconocido),
    "TAMANO_FUERA_DE_RANGO": (Severidad.CRITICO, _tamano),
    "CTE_COLUMNAS_DISTINTAS": (Severidad.CRITICO, _cte_columnas),
    "CTE_NOMBRE_REPETIDO": (Severidad.CRITICO, _cte_nombre),
    "BREAK_FUERA_DE_WHILE": (Severidad.CRITICO, _break),
    "GOTO_SIN_ETIQUETA": (Severidad.CRITICO, _goto),
    "ORDER_BY_EN_SUBCONSULTA": (Severidad.CRITICO, _orden_subconsulta),
    "AGREGADO_EN_WHERE": (Severidad.CRITICO, _agregado_where),
    "VARCHAR_SIN_TAMANO": (Severidad.ALTO, _varchar_sin_tamano),
    "COMPARACION_CON_NULL": (Severidad.ALTO, _con_null),
    "ISNULL_TRUNCA": (Severidad.ALTO, _isnull_trunca),
    "TEXTO_MAS_LARGO_QUE_VARIABLE": (Severidad.ALTO, _texto_largo),
    "BETWEEN_FECHA_SIN_HORA": (Severidad.ALTO, _between),
    "ROWCOUNT_DESPUES_DE_OTRA": (Severidad.ALTO, _rowcount),
    "PARAMETRO_OUTPUT_SIN_VALOR": (Severidad.ALTO, _output_sin_valor),
    "ROLLBACK_SIN_VALIDAR": (Severidad.ALTO, _rollback),
    "TRANSACCION_SIN_TRY": (Severidad.ALTO, _transaccion_sin_try),
    "SQL_DINAMICO_CONCATENA_PARAMETRO": (Severidad.ALTO, _inyeccion),
    "XP_CMDSHELL": (Severidad.ALTO, _xp_cmdshell),
    "CREDENCIAL_EN_CODIGO": (Severidad.ALTO, _credencial),
    "ASIGNACION_VARIAS_FILAS": (Severidad.MEDIO, _varias_filas),
    "VARIABLE_SIN_VALOR": (Severidad.MEDIO, _sin_valor),
    "NOT_IN_SUBCONSULTA": (Severidad.MEDIO, _not_in),
    "TOP_SIN_ORDER_BY": (Severidad.MEDIO, _top),
    "USO_ARROBA_IDENTITY": (Severidad.MEDIO, _identity),
    "DIVISION_SIN_NULLIF": (Severidad.MEDIO, _division),
    "CODIGO_INALCANZABLE": (Severidad.MEDIO, _inalcanzable),
    "SUBCONSULTAS_A_APPLY": (Severidad.MEDIO, _apply),
    "FUNCION_SOBRE_COLUMNA": (Severidad.MEDIO, _funcion_columna),
    "COUNT_EN_LUGAR_DE_EXISTS": (Severidad.MEDIO, _count),
    "ISNULL_EN_CONDICION": (Severidad.MEDIO, _isnull_condicion),
    "ISNULL_EN_COLUMNA_NOT_NULL": (Severidad.MEDIO, _isnull_not_null),
    "ISNULL_VALIDAR_NULOS": (Severidad.BAJO, _isnull_validar),
    "FUNCION_ESCALAR_POR_FILA": (Severidad.MEDIO, _funcion_escalar),
    "CONVERSION_PREVISIBLE": (Severidad.MEDIO, _conversion),
    "LIKE_COMODIN_INICIO": (Severidad.BAJO, _like),
    "OR_ENTRE_COLUMNAS": (Severidad.BAJO, _or),
    "UNION_SIN_ALL": (Severidad.BAJO, _union_sin_all),
    "DISTINCT_CON_JOIN": (Severidad.BAJO, _distinct),
    "ORDER_BY_EN_INSERT": (Severidad.BAJO, _orden_insert),
    "ANIDAMIENTO_EXCESIVO": (Severidad.BAJO, _anidamiento),
    "BLOQUE_REPETIDO": (Severidad.BAJO, _bloque),
    "PARAMETRO_SIN_USO": (Severidad.BAJO, _parametro_sin_uso),
    "CASE_SIN_ELSE": (Severidad.BAJO, _case_sin_else),
    "PROCEDIMIENTO_MUY_LARGO": (Severidad.BAJO, _largo),
}


def partes_del_hecho(hecho: Dict) -> Optional[Partes]:
    entrada = MENSAJES.get(hecho.get("tipo"))
    return entrada[1](hecho) if entrada else None


def mensaje_hecho(hecho: Dict) -> Optional[str]:
    """Mensaje de un solo caso: «qué se encontró. Qué hacer.»."""
    partes = partes_del_hecho(hecho)
    return f"{partes[0]} {partes[1]}" if partes else None


def severidad(tipo: str) -> Severidad:
    return MENSAJES[tipo][0]


def mensaje_agrupado(hechos: List[Dict]) -> Optional[str]:
    """Varios casos del mismo tipo en una observación: cada caso y el «Qué hacer» una sola vez."""
    con_mensaje = [(h, p) for h, p in ((h, partes_del_hecho(h)) for h in hechos) if p]
    if not con_mensaje:
        return None
    if len(con_mensaje) == 1:
        return " ".join(con_mensaje[0][1])
    casos = list(dict.fromkeys(p[0][:1].lower() + p[0][1:].rstrip(".") for _, p in con_mensaje))
    # Líneas separadas por comas: así la pantalla las muestra como lista y las recorre con «1 de N».
    lineas = sorted({int(h["linea"]) for h, _ in con_mensaje})
    donde = f"la línea {lineas[0]}" if len(lineas) == 1 else f"las líneas {', '.join(map(str, lineas))}"
    return f"Se identificaron {len(con_mensaje)} casos, en {donde}: {'; '.join(casos)}. {con_mensaje[0][1][1]}"
