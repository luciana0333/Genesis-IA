# -*- coding: utf-8 -*-
"""Mensajes y severidad de lo que encuentra el revisor de ScriptDom (scriptdom_revisor.cs).

Cada tipo devuelve (qué se encontró, qué hacer), con el estilo de la usuaria: en crítico y alto la acción va
en infinitivo; en medio y bajo, «Se recomienda …, ya que …». Si hay varios casos del mismo tipo se juntan
en una sola observación con todas sus líneas.

Lo que hace fallar el script o da un resultado equivocado se comprobó en SQL Server (error al lado).
"""

import difflib
from collections import Counter
import re
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
    return (f"Se identificó que la columna {h['columna']} se define dos veces en la tabla {h['tabla']}.",
            "Retirar la columna repetida, ya que SQL Server no podrá crear la tabla (error 2705).")


def _temporal_dos_veces(h: Dict) -> Partes:
    return (f"Se identificó que la tabla temporal {h['tabla']} se crea dos veces en el mismo bloque.",
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
    # Texto aprobado por la usuaria (9 nov.): la línea donde se escribe el «;» (donde termina la instrucción anterior) y
    # cómo queda («END;»); probado en SQL Server: el «;» dentro del bloque (ROLLBACK TRANSACTION;) no basta.
    instruccion = h["instruccion"]
    fin = h.get("fin", h["anterior"])
    termina = (h.get("termina") or "").strip()
    # Texto dictado por la usuaria (10 nov.) para el bloque END; sin la línea del THROW (la tarjeta ya la muestra).
    error = 319 if instruccion == "WITH" else 102
    if termina.upper() == "END":
        return (f"Se identificó la ausencia de «;» al finalizar el bloque END, antes de la instrucción {instruccion}.",
                f"Se recomienda agregar el punto y coma (;) al finalizar el bloque (END;), para evitar el error de "
                f"sintaxis {error} durante la ejecución del procedimiento.")
    # Otra instrucción (PRINT, SELECT, SET…): el mismo texto, con la línea donde termina (sin «(OFF;)» ni «(1;)»,
    # que no aclaran).
    return (f"Se identificó la ausencia de «;» al finalizar la instrucción anterior a {instruccion}.",
            f"Se recomienda agregar el punto y coma (;) al finalizar esa instrucción, para evitar el error de sintaxis "
            f"{error} durante la ejecución del procedimiento.")


def _throw_transaccion(h: Dict) -> Partes:
    return (f"Se identificó un THROW después de un {h['instruccion']} sin «;», por lo que SQL Server lo toma como el "
            f"nombre de la transacción y el error nunca se relanza.",
            # Probado en SQL Server (9 nov.): ROLLBACK busca una transacción llamada THROW (error 6401); COMMIT ignora
            # el nombre, confirma y sigue sin error.
            f"Agregar «;» al final del {h['instruccion']}, ya que sin él "
            + ("falla al ejecutarse (error 6401) y el error original se pierde." if h["instruccion"].startswith("ROLLBACK")
               else "el error original se pierde y el código continúa como si no hubiera fallado."))


def _throw_alias(h: Dict) -> Partes:
    return ("Se identificó un THROW justo después de un SELECT sin «;», por lo que SQL Server lo toma como el nombre "
            "de una columna del SELECT y el error nunca se relanza.",
            "Agregar «;» al final del SELECT, ya que, sin él, el error se pierde en silencio y el procedimiento "
            "continúa como si no hubiera fallado.")


def _no_declarada(h: Dict) -> Partes:
    return (f"Se identificó que la variable {h['variable']} se usa sin estar declarada (o antes de su DECLARE).",
            "Declararla con DECLARE antes de usarla, ya que SQL Server no ejecutará el código (error 137).")


def _dos_veces(h: Dict) -> Partes:
    return (f"Se identificó que {h['variable']} se declara dos veces.",
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


# Formatos de fecha de CONVERT cuyo resultado nunca pasa de 30 caracteres, con su largo máximo. Medido en SQL Server
# (18 nov.) con DATETIME, DATETIME2(7), DATETIMEOFFSET(7), DATE, TIME(7) y SMALLDATETIME. Los demás (9, 13, 21, 25,
# 109, 113, 121, 130, 131) llegan a 34-37 con DATETIME2 o DATETIMEOFFSET y sí se cortan: siguen en VARCHAR_SIN_TAMANO.
# Los formatos 0-3 y 126 también sirven para números: tampoco se toman como fecha.
LARGO_POR_FORMATO_DE_FECHA = {
    4: 8, 5: 8, 6: 9, 7: 10, 8: 15, 10: 8, 11: 8, 12: 6, 14: 23, 20: 26, 22: 27, 23: 10, 24: 15,
    100: 26, 101: 10, 102: 10, 103: 10, 104: 10, 105: 10, 106: 11, 107: 12, 108: 15, 110: 10, 111: 10, 112: 8,
    114: 23, 120: 26, 127: 28,
}


def es_formato_de_fecha_corto(estilo) -> bool:
    try:
        return int(estilo) in LARGO_POR_FORMATO_DE_FECHA
    except (TypeError, ValueError):
        return False


def _varchar_sin_tamano_fecha(h: Dict) -> Partes:
    # Texto de la usuaria (18 nov.).
    estilo = int(h["estilo"])
    return (f"Se identificó un caso de CONVERT({h['tipoDato']}, ..., {estilo}) sin especificar el tamaño del tipo de dato.",
            f"Se recomienda especificar el tamaño de {h['tipoDato']} según el formato de fecha utilizado, por ejemplo, "
            f"{h['tipoDato']}({LARGO_POR_FORMATO_DE_FECHA[estilo]}) para el formato {estilo}, a fin de definir "
            f"explícitamente la longitud del resultado.")


def mensaje_varchar_sin_tamano_fecha(hechos: List[Dict]) -> str:
    """Todos los casos en una frase, sin repetir cada uno (usuaria, 18 nov.: «no redundar»)."""
    if len(hechos) == 1:
        return " ".join(_varchar_sin_tamano_fecha(hechos[0]))
    formas = list(dict.fromkeys(f"CONVERT({h['tipoDato']}, ..., {int(h['estilo'])})" for h in hechos))
    formas_texto = formas[0] if len(formas) == 1 else f"{', '.join(formas[:-1])} y {formas[-1]}"
    return (f"Se identificaron {len(hechos)} casos de {formas_texto} sin especificar el tamaño del tipo de dato. "
            f"{_varchar_sin_tamano_fecha(hechos[0])[1]}")


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
    # Texto de la usuaria (18 nov.), con la columna en lugar de «(SELECT ...)», que no se entendía (usuaria, 22 nov.).
    return (f"Se identificó el uso de NOT IN sobre {h['expresion']} para excluir registros mediante una subconsulta.",
            "Se recomienda evaluar su reemplazo por NOT EXISTS, ya que si la subconsulta devuelve valores NULL, la "
            "comparación con NOT IN puede generar resultados inesperados.")


def _top(h: Dict) -> Partes:
    return (f"Se identificó un {h['top']} sin ORDER BY.",
            "Se recomienda agregar un ORDER BY, ya que sin él SQL Server puede devolver una fila distinta en cada "
            "ejecución.")


def _between(h: Dict) -> Partes:
    return (f"Se identificó {h['expresion']} BETWEEN … AND {h['hasta']}, donde {h['expresion']} guarda fecha y hora.",
            f"Usar {h['expresion']} >= fecha inicial AND {h['expresion']} < día siguiente a la fecha final, ya que "
            f"BETWEEN deja fuera todo el último día después de las 00:00.")


def _rowcount(h: Dict) -> Partes:
    return (f"Se identificó que {h['variable']} se lee justo después de otra instrucción y no después del INSERT, "
            f"UPDATE o DELETE.",
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
    return ("Se identificó código después de un RETURN.",
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
    "ISNULL": "comparar la columna directamente (ej.: cCodigo = 'X'), ya que un NULL tampoco sería igual al valor",
    "UPPER": "comparar la columna directamente, ya que el COLLATE de la empresa no distingue mayúsculas",
    "LOWER": "comparar la columna directamente, ya que el COLLATE de la empresa no distingue mayúsculas",
    "RTRIM": "comparar la columna directamente, ya que el = ya ignora los espacios del final",
}


_FUNCIONES_DE_FECHA = {"YEAR", "MONTH", "DAY", "DATEPART", "EOMONTH"}


def _funcion_columna(h: Dict) -> Partes:
    return partes_funcion_columna([h])


def partes_funcion_columna(hechos: List[Dict]) -> Partes:
    """«Filtro que no aprovecha el índice» (usuaria, 18 nov.: entendible, sin redundar y sin exagerar). No se afirma que
    recorra toda la tabla: si otra condición ya busca por un índice (cPersCod = @c), la función no cuesta; Genesis no
    conoce los índices. Cada expresión una vez, con «(2 veces)» si se repite."""
    veces = Counter(h["expresion"] for h in hechos)
    expresiones = [f"{e} ({n} veces)" if n > 1 else e for e, n in veces.items()]
    funciones = {h["funcion"] for h in hechos}
    ejemplos = {h.get("ejemplo") or None for h in hechos}  # ISNULL: la condición reescrita
    motivo = "ya que una función sobre la columna impide que SQL Server use su índice para buscar."
    if len(hechos) == 1:
        h = hechos[0]
        problema = f"Se identificó un filtro que aplica una función sobre la columna {h['columna']}: {h['expresion']}."
        general = "dejar la columna sin función en el filtro y aplicar el cálculo al otro lado de la comparación"
    else:
        problema = (f"Se identificaron {len(hechos)} filtros que aplican una función sobre la columna: "
                    f"{_enumerar(expresiones)}.")
        general = "dejar las columnas sin función en los filtros y aplicar el cálculo al otro lado de la comparación"
    # Un ejemplo concreto solo si todos los casos son de la misma función (YEAR → rango de fechas, ISNULL → reescrita).
    if len(ejemplos) == 1 and None not in ejemplos:
        sugerencia = f"reescribir la condición sin la función (ej.: {ejemplos.pop()})"
    elif len(funciones) == 1 and next(iter(funciones)) in _SUGERENCIA_FUNCION:
        sugerencia = _SUGERENCIA_FUNCION[next(iter(funciones))]
    elif funciones <= _FUNCIONES_DE_FECHA:
        # MONTH y YEAR sobre la misma fecha (18 nov., PA real): las dos se resuelven con un rango de fechas.
        sugerencia = _SUGERENCIA_FUNCION["YEAR"]
    else:
        sugerencia = general
    if " ya que " in sugerencia:  # UPPER, RTRIM, ISNULL ya traen su motivo: se suma el del índice, sin repetir «ya que»
        return problema, f"Se recomienda {sugerencia} y la función impide que SQL Server use su índice para buscar."
    return problema, f"Se recomienda {sugerencia}, {motivo}"


def _like(h: Dict) -> Partes:
    return (f"Se identificó {h['columna']} LIKE '{h['patron']}', con el comodín al inicio.",
            "Se recomienda evaluar si la búsqueda puede hacerse con el comodín solo al final, ya que con el comodín al "
            "inicio no se aprovechan los índices y se recorre toda la tabla.")


def _count(h: Dict) -> Partes:
    return (f"Se identificó {h['comparacion']} para saber si hay registros.",
            f"Se recomienda usar {h['propuesta']} (SELECT 1 FROM …), ya que EXISTS se detiene en el primer registro "
            f"y COUNT(*) los cuenta todos.")


def _funcion_escalar(h: Dict) -> Partes:
    return (f"Se identificó la función {h['funcion']} dentro de {h.get('contexto', 'una consulta')}.",
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
    return partes_orden_insert([h])


def partes_orden_insert(hechos: List[Dict]) -> Partes:
    """Texto de la usuaria (18 nov.). Comprobado en SQL Server: sin IDENTITY el ORDER BY se ignora (mismo plan, sin
    ordenamiento); con IDENTITY se ordena y define la numeración. Por eso no se dice que «agrega trabajo» y, si el
    destino es una tabla física, se pide validar antes si tiene IDENTITY."""
    tablas = list(dict.fromkeys(h.get("tabla") or "" for h in hechos))
    nombradas = [t for t in tablas if t]
    fisicas = [t for t in nombradas if not t.startswith(("#", "@"))]
    # Temporal que no se crea en el script (la crea quien llama): no se sabe si tiene IDENTITY (22 nov.).
    sin_definir = list(dict.fromkeys(h["tabla"] for h in hechos
                                     if (h.get("tabla") or "").startswith(("#", "@")) and h.get("definida") is False))
    if len(hechos) == 1:
        donde = f" en la tabla {nombradas[0]}" if nombradas else ""
        problema = f"Se identificó un ORDER BY al insertar datos con SELECT{donde}."
    else:
        donde = (f" en la tabla {nombradas[0]}" if len(nombradas) == 1 else
                 f" en las tablas {_enumerar(nombradas)}" if nombradas else "")
        problema = f"Se identificaron {len(hechos)} casos de ORDER BY al insertar datos con SELECT{donde}."
    que_hacer = "Se recomienda retirar el ORDER BY, ya que la tabla no conserva ese orden al consultarla."
    if fisicas and not sin_definir:
        cual, tenga = ("la tabla física", "tenga") if len(fisicas) == 1 else ("las tablas físicas", "tengan")
        que_hacer += (f" En el caso de {cual}, validar previamente que no {tenga} una columna IDENTITY, ya que en ese "
                      "caso el ORDER BY define la numeración de los registros.")
    elif sin_definir:
        validar = [t for t in nombradas if t in fisicas or t in sin_definir]  # en el orden del texto
        cual, tenga = (f"la tabla {validar[0]}, cuya definición", "tenga") if len(validar) == 1 else \
            (f"las tablas {_enumerar(validar)}, cuya definición", "tengan")
        que_hacer += (f" En el caso de {cual} no está en el procedimiento, validar previamente que no {tenga} una "
                      "columna IDENTITY, ya que en ese caso el ORDER BY define la numeración de los registros.")
    return problema, que_hacer


# --- ISNULL sobre columnas: validar si la columna acepta NULL -----------------------------------------
def _de_la_columna(h: Dict) -> str:
    if h.get("temporal"):
        return (f"sobre la columna {h['columnaTemporal']} de {h['temporal']}, que se llena desde "
                f"{h['tabla']}.{h['columna']}")
    return f"sobre la columna {h['columna']} de {h['tabla']}"


# Desde cuántas tablas «ISNULL posiblemente innecesario» se muestra como tabla (Tabla | Columnas), igual que
# «COLLATE no especificado» (usuaria, 18 nov.). Mismo número en frontend/src/components/TablaColumnasSinCollate.jsx.
TABLAS_PARA_VER_EN_TABLA = 3


def _por_donde(h: Dict) -> str:
    """La temporal por la que llega la columna: «#M», «#R.nSaldoActual» si allí se llama distinto, o «» si es directa."""
    if not h.get("temporal"):
        return ""
    if str(h.get("columnaTemporal", "")).lower() == str(h["columna"]).lower():
        return h["temporal"]
    return f"{h['temporal']}.{h['columnaTemporal']}"


def _enumerar(elementos: List[str]) -> str:
    return elementos[0] if len(elementos) == 1 else f"{', '.join(elementos[:-1])} y {elementos[-1]}"


def _columnas_por_tabla(hechos: List[Dict]) -> List[Tuple[str, List[Tuple[str, str]], List[Dict]]]:
    """[(tabla física, [(columna, por dónde llega)] sin repetir, hechos de esa tabla)] en el orden en que aparecen."""
    tablas: Dict[str, Tuple[str, Dict[Tuple[str, str], None], List[Dict]]] = {}
    for h in hechos:
        tabla, columnas, suyos = tablas.setdefault(h["tabla"].lower(), (h["tabla"], {}, []))
        columnas[(h["columna"], _por_donde(h))] = None
        suyos.append(h)
    return [(tabla, list(columnas), suyos) for tabla, columnas, suyos in tablas.values()]


def _columnas_de_una_tabla(columnas: List[Tuple[str, str]], separador=_enumerar) -> str:
    """«nIdDescTrx, nMonto (a través de #M)»: si todas llegan por la misma temporal, se dice una sola vez."""
    caminos = {por for _, por in columnas}
    if len(caminos) == 1:
        por = caminos.pop()
        return separador([c for c, _ in columnas]) + (f" (a través de {por})" if por else "")
    return separador([c + (f" (a través de {por})" if por else "") for c, por in columnas])


def _isnull_validar(h: Dict) -> Partes:
    return mensaje_isnull_validar_partes([h])


def mensaje_isnull_validar_partes(hechos: List[Dict]) -> Partes:
    """Texto de la usuaria (18 nov.): cada columna una sola vez, aunque el ISNULL se repita en varias líneas.
    Desde 3 tablas, «las siguientes columnas: tabla: columnas; …», que la pantalla muestra como tabla."""
    por_tabla = _columnas_por_tabla(hechos)
    varias = len(por_tabla) > 1 or len(por_tabla[0][1]) > 1
    que_hacer = ("Se recomienda validar si estas columnas permiten valores NULL. De no permitirlos, se puede retirar "
                 "el ISNULL, ya que no sería necesario." if varias else
                 "Se recomienda validar si esta columna permite valores NULL. De no permitirlos, se puede retirar el "
                 "ISNULL, ya que no sería necesario.")
    if len(por_tabla) >= TABLAS_PARA_VER_EN_TABLA:
        detalle = "; ".join(f"{tabla}: {_columnas_de_una_tabla(columnas, ', '.join)}" for tabla, columnas, _ in por_tabla)
        return f"Se identificó el uso de ISNULL en las siguientes columnas: {detalle}.", que_hacer
    partes = []
    for tabla, columnas, _ in por_tabla:
        caminos = {por for _, por in columnas}
        if len(caminos) == 1:
            # «NIDDESCTRX de DBO.MOVCAP (a través de #MovimientosBase)», «nSaldo y nMora de dbo.Credito».
            por = caminos.pop()
            partes.append(f"{_enumerar([c for c, _ in columnas])} de {tabla}" + (f" (a través de {por})" if por else ""))
        else:
            # Columnas de la misma tabla que llegan por caminos distintos: cada una con el suyo.
            partes.append(f"{_columnas_de_una_tabla(columnas)} de {tabla}")
    sujeto = "la columna" if not varias else "las columnas"
    return f"Se identificó el uso de ISNULL en {sujeto} {_enumerar(partes)}.", que_hacer


def grupos_isnull_validar(hechos: List[Dict]) -> Optional[List[Dict]]:
    """Desde 3 tablas: una fila por tabla (Tabla | Columnas) y sus líneas, para «Ver en el código»."""
    por_tabla = _columnas_por_tabla(hechos)
    if len(por_tabla) < TABLAS_PARA_VER_EN_TABLA:
        return None
    grupos = []
    for tabla, columnas, suyos in por_tabla:
        paradas = sorted({(int(h["linea"]), h["columna"]) for h in suyos})
        grupos.append({"nombre": tabla, "tipo": "Tabla", "lineas": [linea for linea, _ in paradas],
                       "etiquetas": [columna for _, columna in paradas],
                       "columnas": _columnas_de_una_tabla(columnas, ", ".join)})
    return grupos


def _isnull_condicion(h: Dict) -> Partes:
    reescrita = f" (si los acepta, se puede reescribir sin la función: {h['ejemplo']})" if h.get("ejemplo") else ""
    return (f"Se identificó {h['expresion']} en una condición, {_de_la_columna(h)}.",
            f"Se recomienda validar si la columna acepta valores nulos con la consulta adjunta, ya que, si no los "
            f"acepta, el ISNULL no es necesario y en una condición impide usar el índice{reescrita}.")


def _isnull_not_null(h: Dict) -> Partes:
    indice = " y en una condición impide usar el índice" if h.get("contexto") == "condicion" else ""
    return (f"Se identificó {h['expresion']} sobre la columna {h['columna']} de {h['tabla']}, que se define NOT "
            f"NULL.",
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
    return partes_anidamiento([h])


def partes_anidamiento(hechos: List[Dict]) -> Partes:
    """Varios lugares: cuántos y hasta cuántos niveles, sin «N casos: …; …» (usuaria, 22 nov.)."""
    que_hacer = ("Se recomienda simplificar la lógica (condiciones combinadas, salidas tempranas con RETURN o "
                 "procedimientos separados), ya que tantos niveles dificultan leer y mantener el código.")
    if len(hechos) == 1:
        return f"Se identificaron {hechos[0]['niveles']} niveles de IF / WHILE uno dentro de otro.", que_hacer
    maximo = max(int(h["niveles"]) for h in hechos)
    return (f"Se identificaron {len(hechos)} lugares con IF / WHILE uno dentro de otro (hasta {maximo} niveles).",
            que_hacer)


def _bloque(h: Dict) -> Partes:
    return partes_bloque([h])


def partes_bloque(hechos: List[Dict]) -> Partes:
    """Varias instrucciones repetidas en una sola frase, sin el formato antiguo «N casos: …; …» (usuaria, 22 nov.,
    caso real FluGenSol_InsPropuesta_SP: 4 INSERT y 2 UPDATE repetidos). Las líneas van arriba, en la tarjeta."""
    if len(hechos) == 1:
        return (f"Se identificó la misma instrucción {hechos[0]['instruccion']} repetida en varias partes del código.",
                "Se recomienda escribirla una sola vez (en una tabla temporal, una CTE o un procedimiento), ya que "
                "repetida hay que corregirla en cada lugar.")
    por_tipo: Dict[str, int] = {}
    for h in hechos:
        por_tipo[h["instruccion"]] = por_tipo.get(h["instruccion"], 0) + 1
    if len(por_tipo) == 1:
        problema = (f"Se identificaron {len(hechos)} instrucciones {next(iter(por_tipo))} repetidas en varias partes "
                    "del código.")
    else:
        detalle = _enumerar([f"{n} {tipo}" for tipo, n in por_tipo.items()])
        problema = f"Se identificaron {len(hechos)} instrucciones repetidas en varias partes del código: {detalle}."
    return (problema, "Se recomienda escribir cada una una sola vez (en una tabla temporal, una CTE o un "
                      "procedimiento), ya que repetidas hay que corregirlas en cada lugar.")


def _parametro_sin_uso(h: Dict) -> Partes:
    return (f"Se identificó que el parámetro {h['variable']} no se usa.",
            "Se recomienda retirarlo o revisar si falta usarlo, ya que confunde a quien llama al procedimiento.")


def _case_sin_else(h: Dict) -> Partes:
    return ("Se identificó un CASE sin ELSE.",
            "Se recomienda agregar un ELSE, ya que si ningún WHEN se cumple el resultado es NULL.")


# tipo -> (severidad, mensaje)
MENSAJES: Dict[str, Tuple[Severidad, Callable[[Dict], Optional[Partes]]]] = {
    "INSERT_COLUMNAS_NO_COINCIDEN": (Severidad.CRITICO, _insert),
    "COLUMNA_REPETIDA_EN_TABLA": (Severidad.CRITICO, _columna_repetida),
    "TEMPORAL_CREADA_DOS_VECES": (Severidad.CRITICO, _temporal_dos_veces),
    "DOS_PRIMARY_KEY": (Severidad.CRITICO, _dos_pk),
    "DOS_IDENTITY": (Severidad.CRITICO, _dos_identity),
    "ALIAS_REPETIDO_EN_FROM": (Severidad.CRITICO, _alias),
    "PUNTO_Y_COMA_FALTANTE": (Severidad.CRITICO, _punto_y_coma),
    "PUNTO_Y_COMA_ANTES_DE_WITH": (Severidad.CRITICO, _punto_y_coma),
    "THROW_TOMADO_COMO_ALIAS": (Severidad.CRITICO, _throw_alias),
    "THROW_TOMADO_COMO_TRANSACCION": (Severidad.CRITICO, _throw_transaccion),
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
    "VARCHAR_SIN_TAMANO_FECHA": (Severidad.BAJO, _varchar_sin_tamano_fecha),
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
    "FUNCION_SOBRE_COLUMNA": (Severidad.BAJO, _funcion_columna),  # depende de los índices (18 nov.)
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
    # «Procedimiento muy largo» se retiró: no es necesario (usuaria, 22 nov.). ScriptDom lo sigue informando, pero sin
    # mensaje no se muestra.
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
    if con_mensaje[0][0].get("tipo") == "FUNCION_SOBRE_COLUMNA":
        return " ".join(partes_funcion_columna([h for h, _ in con_mensaje]))
    if con_mensaje[0][0].get("tipo") == "ORDER_BY_EN_INSERT":
        return " ".join(partes_orden_insert([h for h, _ in con_mensaje]))
    if con_mensaje[0][0].get("tipo") == "BLOQUE_REPETIDO":
        return " ".join(partes_bloque([h for h, _ in con_mensaje]))
    if con_mensaje[0][0].get("tipo") == "ANIDAMIENTO_EXCESIVO":
        return " ".join(partes_anidamiento([h for h, _ in con_mensaje]))
    # Sin redundar (usuaria, 18 nov., modelo «Se identificaron 2 casos de CASE sin ELSE.»): lo común se dice una vez
    # y las líneas van arriba, en la tarjeta (hallazgo.lineas), no en el texto.
    total = len(con_mensaje)
    que_hacer = con_mensaje[0][1][1]
    restos = list(dict.fromkeys(_sin_se_identifico(p[0]) for _, p in con_mensaje))
    if len(restos) == 1 and restos[0] is not None:
        return f"Se identificaron {total} {_casos_de(restos[0])}. {que_hacer}"
    # Lo distinto en medio de la frase (la variable, la columna…): la frase en plural y solo lo que cambia.
    plural = _PLURALES.get(con_mensaje[0][0].get("tipo"))
    if plural:
        frase, elemento, mismo = plural
        elementos = list(dict.fromkeys(elemento(h) for h, _ in con_mensaje))
        if len(elementos) > 1 and (not mismo or len({str(h.get(mismo)) for h, _ in con_mensaje}) == 1):
            que_hacer = _QUE_HACER_EN_PLURAL.get(con_mensaje[0][0].get("tipo"), que_hacer)
            return f"Se identificaron {len(elementos)} {frase}: {_enumerar(elementos)}. {que_hacer}"
        if len(elementos) == 1 and not mismo:
            # Mismo elemento con detalles distintos (p. ej. dos grupos de subconsultas a la misma tabla): la frase en
            # plural con el total, nunca «N casos: …; …» (22 nov.).
            que_hacer = _QUE_HACER_EN_PLURAL.get(con_mensaje[0][0].get("tipo"), que_hacer)
            return f"Se identificaron {total} {frase}: {elementos[0]}. {que_hacer}"
    if all(resto is not None for resto in restos):
        # Solo cambia el final (ORDER BY … a #A / a #B): «2 casos de ORDER BY … a #A y #B».
        comun, finales = _comun_al_inicio(restos)
        if comun:
            return f"Se identificaron {total} {_casos_de(comun)} {_enumerar(finales)}. {que_hacer}"
    # Otros casos distintos: una viñeta por caso, sin repetir «Se identificó».
    casos = list(dict.fromkeys(_mayuscula(_sin_se_identifico(p[0]) or p[0].rstrip(".")) for _, p in con_mensaje))
    return f"Se identificaron {total} casos: {'; '.join(casos)}. {que_hacer}"


# Observaciones que se repiten con algo distinto en medio (una variable, una columna): la frase en plural y la lista
# de lo que cambia (usuaria, 18 nov.: sin redundar). (frase, qué se lista de cada caso, dato que debe ser igual en
# todos para que el «Qué hacer» del primero sirva para todos, o None).
_PLURALES: Dict[str, Tuple[str, Callable[[Dict], str], Optional[str]]] = {
    "VARIABLE_NO_DECLARADA": ("variables que se usan sin estar declaradas (o antes de su DECLARE)",
                              lambda h: h["variable"], None),
    "PARAMETRO_SIN_USO": ("parámetros que no se usan", lambda h: h["variable"], None),
    "PARAMETRO_OUTPUT_SIN_VALOR": ("parámetros OUTPUT que nunca reciben un valor", lambda h: h["variable"], None),
    "FUNCION_ESCALAR_POR_FILA": ("funciones escalares dentro de una consulta", lambda h: h["funcion"], None),
    "TOP_SIN_ORDER_BY": ("TOP sin ORDER BY", lambda h: h["top"], None),
    "LIKE_COMODIN_INICIO": ("LIKE con el comodín al inicio", lambda h: f"{h['columna']} LIKE '{h['patron']}'", None),
    "OR_ENTRE_COLUMNAS": ("OR entre columnas en el WHERE", lambda h: f"{h['primera']} OR {h['segunda']}", None),
    "COLUMNA_REPETIDA_EN_TABLA": ("columnas que se definen dos veces", lambda h: f"{h['columna']} en {h['tabla']}", None),
    "TEMPORAL_CREADA_DOS_VECES": ("tablas temporales que se crean dos veces en el mismo bloque",
                                  lambda h: h["tabla"], None),
    # Con divisores distintos, el «Qué hacer» en plural (sin nombrar uno solo).
    "DIVISION_SIN_NULLIF": ("divisiones sin proteger el divisor", lambda h: h["expresion"], None),
    # Sin repetir la frase en cada caso (usuaria, 22 nov.: «que ni una regla muestre el mensaje antiguo»).
    "VARIABLE_SIN_VALOR": ("variables que se leen antes de recibir un valor, por lo que valen NULL",
                           lambda h: h["variable"], None),
    "ASIGNACION_VARIAS_FILAS": ("asignaciones SELECT @variable = … FROM sin WHERE, TOP ni agregado",
                                lambda h: h["variable"], None),
    "BETWEEN_FECHA_SIN_HORA": ("BETWEEN sobre datos que guardan fecha y hora",
                               lambda h: f"{h['expresion']} BETWEEN … AND {h['hasta']}", None),
    "COMPARACION_CON_NULL": ("comparaciones con NULL que nunca son verdaderas", lambda h: h["comparacion"], None),
    "CONVERSION_PREVISIBLE": ("comparaciones de columnas de texto con valores de otro tipo",
                              lambda h: f"{h['columna']} con {h['otro']} ({h['tipoDato']})", None),
    "COUNT_EN_LUGAR_DE_EXISTS": ("COUNT(*) para saber si hay registros", lambda h: h["comparacion"], None),
    "INSERT_COLUMNAS_NO_COINCIDEN": (
        "INSERT con distinta cantidad de columnas y valores",
        lambda h: (f"{h.get('tabla') or 'INSERT'} ({_cantidad(int(h['columnas']), 'columna', 'columnas')} y "
                   + (f"su SELECT devuelve {_cantidad(int(h['valores']), 'columna', 'columnas')})"
                      if h.get("origen") == "SELECT" else f"{_cantidad(int(h['valores']), 'valor', 'valores')})")),
        None),
    "ISNULL_EN_CONDICION": ("ISNULL en condiciones", lambda h: h["expresion"], None),
    "ISNULL_TRUNCA": ("ISNULL que cortan el texto",
                      lambda h: f"ISNULL({h['variable']}, '{h['texto']}') devuelve '{h['queda']}'", None),
    "PUNTO_Y_COMA_ANTES_DE_WITH": ("lugares sin «;» antes de la instrucción WITH", lambda h: _donde_falta(h), None),
    "PUNTO_Y_COMA_FALTANTE": ("lugares sin «;» antes de la instrucción THROW", lambda h: _donde_falta(h), None),
    "TAMANO_FUERA_DE_RANGO": ("tipos fuera del tamaño permitido",
                              lambda h: f"{h['valor']} ({h['tipoDato']}: {h['limite']})", None),
    "VARCHAR_SIN_TAMANO": (
        "tipos de texto sin tamaño",
        lambda h: (f"{h['tipoDato']} {'en un CAST o CONVERT' if h.get('contexto') == 'conversion' else 'al declarar'} "
                   f"(SQL Server lo toma como {h['tipoDato']}({h['largo']}))"),
        None),
    "NOT_IN_SUBCONSULTA": ("NOT IN que excluyen registros mediante una subconsulta", lambda h: h["expresion"], None),
    "ALIAS_REPETIDO_EN_FROM": ("nombres repetidos en el mismo FROM",
                               lambda h: f"el alias {h['nombre']}" if h.get("esAlias") else f"la tabla {h['nombre']}",
                               None),
    # 22 nov. (usuaria): estos 11 tipos aún salían con «Se identificaron N casos: …; …». Se encontraron simulando
    # todos los tipos agrupados (prueba permanente test_sin_mensaje_agrupado_antiguo), no solo los de los ejemplos.
    "DOS_PRIMARY_KEY": ("tablas que definen más de una PRIMARY KEY", lambda h: f"{h['tabla']} ({h['cantidad']})", None),
    "DOS_IDENTITY": ("tablas que definen más de una columna IDENTITY", lambda h: f"{h['tabla']} ({h['cantidad']})",
                     None),
    "THROW_TOMADO_COMO_TRANSACCION": ("THROW después de un COMMIT o ROLLBACK sin «;», que SQL Server toma como el "
                                      "nombre de la transacción, por lo que el error nunca se relanza",
                                      lambda h: f"después de {h['instruccion']}", None),
    "VARIABLE_DECLARADA_DOS_VECES": ("variables que se declaran dos veces", lambda h: h["variable"], None),
    "CTE_NOMBRE_REPETIDO": ("CTE que se definen dos veces en el mismo WITH", lambda h: h["cte"], None),
    "BREAK_FUERA_DE_WHILE": ("instrucciones fuera de un WHILE", lambda h: h["instruccion"], None),
    "GOTO_SIN_ETIQUETA": ("GOTO a etiquetas que no existen en el bloque", lambda h: h["etiqueta"], None),
    "ROWCOUNT_DESPUES_DE_OTRA": ("lecturas justo después de otra instrucción y no después del INSERT, UPDATE o DELETE",
                                 lambda h: h["variable"], None),
    "SUBCONSULTAS_A_APPLY": ("grupos de subconsultas a la misma tabla con la misma condición en el SELECT",
                             lambda h: f"{h['cantidad']} a {h['tabla']}", None),
    "ISNULL_EN_COLUMNA_NOT_NULL": ("ISNULL sobre columnas que se definen NOT NULL",
                                   lambda h: f"{h['expresion']} ({h['columna']} de {h['tabla']})", None),
    "UNION_COLUMNAS_DISTINTAS": ("UNION, EXCEPT o INTERSECT cuyos SELECT devuelven distinta cantidad de columnas",
                                 lambda h: f"{h['operacion']} ({h['primera']} y {h['segunda']})", None),
    "CTE_COLUMNAS_DISTINTAS": ("CTE que indican una cantidad de columnas distinta a la que devuelve su consulta",
                               lambda h: f"{h['cte']} ({h['columnas']} y {h['consulta']})", None),
    "TEXTO_MAS_LARGO_QUE_VARIABLE": ("textos más largos que la variable que los recibe",
                                     lambda h: f"'{h['texto']}' en {h['variable']} (queda '{h['queda']}')", None),
}


def _donde_falta(h: Dict) -> str:
    """Dónde falta el «;»: al finalizar el bloque END o la instrucción anterior."""
    termina = (h.get("termina") or "").strip().upper()
    return "al finalizar el bloque END" if termina == "END" else "al finalizar la instrucción anterior"

# El «Qué hacer» en plural cuando el de un solo caso no concuerda («Declararla» → «Declararlas»).
_QUE_HACER_EN_PLURAL = {
    "VARIABLE_NO_DECLARADA": "Declararlas con DECLARE antes de usarlas, ya que SQL Server no ejecutará el código "
                             "(error 137).",
    "PARAMETRO_SIN_USO": "Se recomienda retirarlos o revisar si falta usarlos, ya que confunden a quien llama al "
                         "procedimiento.",
    "PARAMETRO_OUTPUT_SIN_VALOR": "Asignarles el valor que deben devolver, ya que el procedimiento siempre los "
                                  "devolverá en NULL.",
    "FUNCION_ESCALAR_POR_FILA": "Se recomienda evaluar reemplazarlas por un JOIN o un APPLY, ya que una función "
                                "escalar propia se ejecuta una vez por cada fila.",
    "COLUMNA_REPETIDA_EN_TABLA": "Retirar las columnas repetidas, ya que SQL Server no podrá crear la tabla "
                                 "(error 2705).",
    "OR_ENTRE_COLUMNAS": "Se recomienda evaluar separarlos en dos consultas con UNION ALL, ya que un OR entre "
                         "columnas distintas suele impedir el uso de los índices.",
    "DIVISION_SIN_NULLIF": "Se recomienda proteger cada divisor con NULLIF(divisor, 0), ya que si el divisor es 0 el "
                           "procedimiento falla con error de división entre cero.",
    "VARIABLE_SIN_VALOR": "Se recomienda asignarles un valor inicial o confirmar que el NULL es intencional, ya que una "
                          "operación con NULL (+ 1, concatenación, comparación) también da NULL.",
    "ASIGNACION_VARIAS_FILAS": "Se recomienda filtrar a una sola fila (WHERE por la clave o TOP 1 con ORDER BY), ya que "
                               "si la tabla tiene varias filas la variable queda con el valor de cualquiera de ellas.",
    "BETWEEN_FECHA_SIN_HORA": "Usar columna >= fecha inicial AND columna < día siguiente a la fecha final, ya que BETWEEN "
                              "deja fuera todo el último día después de las 00:00.",
    "COMPARACION_CON_NULL": "Usar IS NULL o IS NOT NULL, ya que en SQL Server una comparación con NULL usando = o <> no "
                            "devuelve verdadero ni falso.",
    "COUNT_EN_LUGAR_DE_EXISTS": "Se recomienda usar EXISTS o NOT EXISTS (SELECT 1 FROM …), ya que EXISTS se detiene en el "
                                "primer registro y COUNT(*) los cuenta todos.",
    "INSERT_COLUMNAS_NO_COINCIDEN": "Igualar la cantidad de columnas y de valores en cada INSERT, ya que SQL Server no "
                                    "los ejecutará.",
    "ISNULL_EN_CONDICION": "Se recomienda validar si las columnas aceptan valores nulos con la consulta adjunta, ya que, "
                           "si no los aceptan, el ISNULL no es necesario y en una condición impide usar el índice.",
    "ISNULL_TRUNCA": "Usar COALESCE o ampliar el tamaño de las variables, ya que ISNULL corta el texto al tamaño de la "
                     "primera expresión sin avisar.",
    "PUNTO_Y_COMA_ANTES_DE_WITH": "Se recomienda agregar el punto y coma (;) en cada uno, para evitar el error de "
                                  "sintaxis 319 durante la ejecución del procedimiento.",
    "PUNTO_Y_COMA_FALTANTE": "Se recomienda agregar el punto y coma (;) en cada uno, para evitar el error de sintaxis "
                             "102 durante la ejecución del procedimiento.",
    "NOT_IN_SUBCONSULTA": "Se recomienda evaluar reemplazarlos por NOT EXISTS, ya que si la subconsulta devuelve "
                          "valores NULL, la comparación con NOT IN puede generar resultados inesperados.",
    "TAMANO_FUERA_DE_RANGO": "Corregir los tamaños, ya que SQL Server no ejecutará el código.",
    "VARCHAR_SIN_TAMANO": "Indicar el tamaño (ej.: VARCHAR(100)), ya que, sin él, SQL Server corta el texto sin avisar.",
    "ALIAS_REPETIDO_EN_FROM": "Usar un nombre o alias distinto para cada tabla, ya que SQL Server no ejecutará la "
                              "consulta.",
    "DOS_PRIMARY_KEY": "Dejar una sola en cada tabla, ya que una tabla solo puede tener una clave primaria y SQL Server "
                       "no podrá crearlas (error 8110).",
    "DOS_IDENTITY": "Dejar una sola en cada tabla, ya que una tabla solo puede tener una columna IDENTITY y SQL Server "
                    "no podrá crearlas (error 2744).",
    "THROW_TOMADO_COMO_TRANSACCION": "Agregar «;» al final de cada COMMIT o ROLLBACK, ya que sin él el error original "
                                     "se pierde (con ROLLBACK, además, falla al ejecutarse con el error 6401).",
    "VARIABLE_DECLARADA_DOS_VECES": "Dejar una sola declaración de cada una o usar otro nombre, ya que SQL Server no "
                                    "ejecutará el código (error 134).",
    "BREAK_FUERA_DE_WHILE": "Retirarlas o ubicarlas dentro del WHILE, ya que BREAK y CONTINUE solo funcionan dentro de "
                            "un bucle y SQL Server no ejecutará el código (error 135).",
    "GOTO_SIN_ETIQUETA": "Crear las etiquetas o corregir sus nombres, ya que SQL Server no ejecutará el código "
                         "(error 133).",
    "ROWCOUNT_DESPUES_DE_OTRA": "Guardar cada valor en una variable inmediatamente después de la instrucción que "
                                "interesa, ya que cada instrucción, incluso un SET, lo reemplaza.",
    "SUBCONSULTAS_A_APPLY": "Se recomienda evaluar unir cada grupo en un APPLY, ya que así cada tabla se leería una "
                            "sola vez por fila.",
    "ISNULL_EN_COLUMNA_NOT_NULL": "Se recomienda retirar el ISNULL, ya que estas columnas no aceptan valores nulos.",
    "UNION_COLUMNAS_DISTINTAS": "Igualar la cantidad de columnas de cada SELECT, ya que SQL Server no ejecutará las "
                                "consultas (error 205).",
    "CTE_COLUMNAS_DISTINTAS": "Igualar la cantidad de columnas en cada CTE, ya que SQL Server no ejecutará las consultas "
                              "(error 8159).",
    "TEXTO_MAS_LARGO_QUE_VARIABLE": "Ampliar el tamaño de las variables, ya que SQL Server corta el texto sin avisar.",
}


def _sin_se_identifico(texto: str) -> Optional[str]:
    """«Se identificó un CASE sin ELSE.» → «un CASE sin ELSE»; None si la frase no empieza así."""
    coincide = re.match(r"Se identificó (.+?)\.?$", texto.strip(), re.DOTALL)
    return coincide.group(1) if coincide else None


def _casos_de(resto: str) -> str:
    """«un CASE sin ELSE» → «casos de CASE sin ELSE»; «que la tabla #T…» → «casos en que la tabla #T…»."""
    if resto.startswith("que "):
        return f"casos en {resto}"
    return "casos de " + re.sub(r"^(?:un|una|el|la|los|las)\s+", "", resto)


def _comun_al_inicio(restos: List[str]) -> Tuple[str, List[str]]:
    """Palabras iguales al inicio de todos los casos, si lo distinto queda solo al final (una o dos palabras)."""
    palabras = [resto.split(" ") for resto in restos]
    largo = 0
    while all(len(p) > largo + 1 for p in palabras) and len({p[largo] for p in palabras}) == 1:
        largo += 1
    finales = [" ".join(p[largo:]) for p in palabras]
    if largo < 2 or any(len(p) - largo > 2 for p in palabras):
        return "", []
    return " ".join(palabras[0][:largo]), finales


def _mayuscula(texto: str) -> str:
    """Mayúscula inicial solo si empieza con una palabra común («un», «la», «que»…), no con un nombre de columna."""
    texto = re.sub(r"^que\s+", "", texto)
    if re.match(r"(?:un|una|el|la|los|las|lo)\s", texto):
        return texto[:1].upper() + texto[1:]
    return texto


# Líneas que el texto ya no dice y van arriba de la tarjeta junto a la del hallazgo (usuaria, 21 nov.: las líneas no
# se mencionan dentro del texto): la primera declaración, el RETURN, la definición de la columna…
_LINEAS_EXTRA = {
    "COLUMNA_REPETIDA_EN_TABLA": ("primera",),
    "TEMPORAL_CREADA_DOS_VECES": ("primera",),
    "VARIABLE_DECLARADA_DOS_VECES": ("primera",),
    "PUNTO_Y_COMA_FALTANTE": ("fin", "anterior"),
    "PUNTO_Y_COMA_ANTES_DE_WITH": ("fin", "anterior"),
    "THROW_TOMADO_COMO_TRANSACCION": ("inicio",),
    "ROWCOUNT_DESPUES_DE_OTRA": ("anterior",),
    "CODIGO_INALCANZABLE": ("retorno",),
    "ISNULL_EN_COLUMNA_NOT_NULL": ("definicion",),
}


def lineas_del_hecho(h: Dict) -> List[int]:
    """La línea del hallazgo y las que antes iban dentro del texto."""
    lineas = [h["linea"]]
    claves = _LINEAS_EXTRA.get(h.get("tipo"), ())
    if h.get("tipo", "").startswith("PUNTO_Y_COMA"):
        claves = ("fin",) if h.get("fin") else ("anterior",)
    lineas += [h[clave] for clave in claves if h.get(clave)]
    if h.get("tipo") == "BLOQUE_REPETIDO":
        lineas += list(h.get("lineas") or [])
    return [int(n) for n in lineas]
