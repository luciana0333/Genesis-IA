"""«Uso de COLLATE DATABASE_DEFAULT» en una sola observación (compartido por Reportes y Negocio; usuaria, 8 nov.).

«Se identificó el uso de COLLATE DATABASE_DEFAULT sobre las columnas CCTACOD y cReprogCov de la tabla #Tmp, que
toma la intercalación predeterminada…». Las columnas se agrupan por su tabla; la frase va una sola vez.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple

from app.analizadores.openjson_collate import dentro_de_openjson
from app.analizadores.sql_parentesis import sin_parentesis_cerrados

_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_REFERENCIA = rf"{_IDENTIFICADOR}(?:\s*\.\s*(?:\.\s*)?{_IDENTIFICADOR}){{0,2}}"
_DATABASE_DEFAULT = re.compile(r"\bCOLLATE\s+DATABASE_DEFAULT\b", re.IGNORECASE)

# Lo que separa una columna de la anterior: coma, paréntesis, comparación o palabra de la consulta.
_ANTES_DE_LA_COLUMNA = re.compile(
    r"[,(=<>]|\b(?:ON|WHERE|AND|OR|SELECT|BY|WHEN|THEN|ELSE|HAVING|SET|ADD|COLUMN)\b", re.IGNORECASE
)
# Tabla que se define: CREATE TABLE #T ( … / DECLARE @T TABLE ( …
_DEFINE_TABLA = re.compile(
    rf"\b(?:CREATE\s+TABLE\s+({_REFERENCIA})|DECLARE\s+(@[A-Za-z_]\w*)\s+(?:AS\s+)?TABLE)\s*$", re.IGNORECASE
)
_ALTER_TABLA = re.compile(rf"\bALTER\s+TABLE\s+({_REFERENCIA})\s+(?:ADD|ALTER\s+COLUMN)\b", re.IGNORECASE)

# «Qué hacer» y explicación: texto de la usuaria (8 nov.), igual en Reportes y Negocio.
EXPLICACION = "que toma la intercalación predeterminada de la base de datos donde se ejecuta la consulta"
QUE_HACER_COLLATE_DATABASE_DEFAULT = (
    "Se recomienda utilizar el COLLATE correspondiente (SQL_Latin1_General_CP1_CI_AS), para evitar conflictos al "
    "comparar o combinar textos entre bases de datos con distintas intercalaciones."
)


def _columna_antes_de(limpio: str, posicion: int) -> Optional[str]:
    """La columna del COLLATE: «cCod» en «cCod VARCHAR(10) NOT NULL COLLATE …», «a.c» en «a.c COLLATE …»."""
    previo = sin_parentesis_cerrados(limpio[:posicion])
    cortes = list(_ANTES_DE_LA_COLUMNA.finditer(previo))
    inicio = cortes[-1].end() if cortes else 0
    nombre = re.compile(r"\s*([\w.\[\]@#]+)").match(previo, inicio)
    if not nombre or re.match(r"\s*\(", limpio[nombre.end():]):
        return None  # sin nombre, o es una función (LTRIM(a.c) COLLATE …)
    return nombre.group(1)


def _tabla_que_se_define(limpio: str, posicion: int) -> Optional[str]:
    """#T si el COLLATE está dentro de CREATE TABLE #T ( … ), DECLARE @T TABLE ( … ) o ALTER TABLE T ADD …."""
    previo = sin_parentesis_cerrados(limpio[:posicion])
    abre = previo.rfind("(")
    if abre >= 0:
        define = _DEFINE_TABLA.search(previo[:abre])
        if define:
            return (define.group(1) or define.group(2)).strip()
    sentencia = previo[previo.rfind(";") + 1:]
    alter = list(_ALTER_TABLA.finditer(sentencia))
    return alter[-1].group(1).strip() if alter else None


def _tabla_del_alias(limpio: str, posicion: int, alias: str) -> Optional[str]:
    """La tabla del alias en el FROM/JOIN más cercano (b en «JOIN dbo.B b» → dbo.B)."""
    candidatos = [
        m for m in re.finditer(
            rf"\b(?:FROM|JOIN|UPDATE)\s+({_REFERENCIA})\s+(?:AS\s+)?{re.escape(alias)}\b", limpio, re.IGNORECASE)
    ]
    if not candidatos:
        return None
    return min(candidatos, key=lambda m: abs(m.start() - posicion)).group(1).strip()


def _enumerar(nombres: List[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _columna_y_tabla(limpio: str, posicion: int) -> Tuple[Optional[str], Optional[str]]:
    columna = _columna_antes_de(limpio, posicion)
    if not columna:
        return None, None
    tabla = _tabla_que_se_define(limpio, posicion)
    if "." in columna:
        alias, columna = columna.rsplit(".", 1)
        tabla = tabla or _tabla_del_alias(limpio, posicion, alias) or alias
    return columna.strip("[]"), tabla


def mensaje_collate_database_default(casos: List[Tuple[Optional[str], Optional[str]]]) -> str:
    """casos: [(columna, tabla)] en orden; sin columna o sin tabla si no se reconoce."""
    por_tabla: Dict[str, List[str]] = {}
    for columna, tabla in casos:
        if not columna:
            continue
        columnas = por_tabla.setdefault(tabla or "", [])
        if columna.lower() not in {c.lower() for c in columnas}:
            columnas.append(columna)
    partes = []
    for tabla, columnas in por_tabla.items():
        sustantivo = "la columna" if len(columnas) == 1 else "las columnas"
        partes.append(f"{sustantivo} {_enumerar(columnas)}" + (f" de la tabla {tabla}" if tabla else ""))
    sobre = f" sobre {_enumerar(partes)}" if partes else ""
    return f"Se identificó el uso de COLLATE DATABASE_DEFAULT{sobre}, {EXPLICACION}. {QUE_HACER_COLLATE_DATABASE_DEFAULT}"


def collate_database_default_agrupado(
    limpio: str, linea_de: Callable[[int], int]
) -> Optional[Tuple[int, str, List[int]]]:
    """(posición del primero, mensaje, líneas) con todos los COLLATE DATABASE_DEFAULT, o None.

    Los de OPENJSON no cuentan: los observa «COLLATE innecesario en OPENJSON».
    """
    posiciones = [m.start() for m in _DATABASE_DEFAULT.finditer(limpio) if not dentro_de_openjson(limpio, m.start())]
    if not posiciones:
        return None
    mensaje = mensaje_collate_database_default([_columna_y_tabla(limpio, p) for p in posiciones])
    return posiciones[0], mensaje, sorted({linea_de(p) for p in posiciones})
