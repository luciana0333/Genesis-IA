"""«Columna numérica comparada con texto» (compartido por Reportes y Negocio; pedido de la usuaria, 8 nov.).

    WHERE CT.nConsCod = '3001'      → nConsCod es INT: se compara con 3001, sin comillas.

SQL Server convierte el texto a número una sola vez (el índice se sigue usando), pero si algún día el valor no es
numérico la consulta falla con un error de conversión, y el código no refleja el tipo real de la columna.

- Columna de una temporal o variable de tabla del script: el tipo se lee de su CREATE TABLE / DECLARE ... TABLE y se
  afirma (certeza). Si el tipo real es de texto (nCodigo VARCHAR(10), prefijo mal puesto), no se observa.
- Columna de una tabla física: solo se conoce el prefijo (n = número), que a veces está mal puesto. Se pide validar
  y se adjunta la consulta a INFORMATION_SCHEMA.COLUMNS que muestra el tipo real.

Solo se marcan textos con dígitos ('3001', '1'): comparar una columna numérica con 'A' es otra clase de error.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple

from app.analizadores.collate_temporales import _contenido, _por_comas
from app.analizadores.sql_parentesis import sin_parentesis_cerrados

_IDENT = r"(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)"
# Tabla: también temporales y variables de tabla (#T, @T).
_REFERENCIA = rf"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)(?:\s*\.\s*(?:\.\s*)?{_IDENT}){{0,3}}"
_COLUMNA = rf"(?<![\w$#@.\]])(?P<col>(?:{_IDENT}\s*\.\s*)?{_IDENT})"
_TEXTO = r"(?P<lit>N?'[^']*')"
_OPERADOR = r"(?:=|<>|!=|<=|>=|<|>)"
_COMPARACIONES = (
    re.compile(rf"{_COLUMNA}\s*{_OPERADOR}\s*{_TEXTO}", re.IGNORECASE),
    re.compile(rf"{_TEXTO}\s*{_OPERADOR}\s*{_COLUMNA}", re.IGNORECASE),
    re.compile(rf"{_COLUMNA}\s+(?:NOT\s+)?IN\s*\((?P<lista>\s*N?'[^']*'(?:\s*,\s*N?'[^']*')*\s*)\)", re.IGNORECASE),
)
_DEFINE_TABLA = re.compile(
    r"\b(?:CREATE\s+TABLE\s+(#[A-Za-z_][\w$#]*)|DECLARE\s+(@[A-Za-z_]\w*)\s+(?:AS\s+)?TABLE)\s*\(", re.IGNORECASE,
)
_TIPOS_NUMERO = {"INT", "BIGINT", "SMALLINT", "TINYINT", "DECIMAL", "NUMERIC", "MONEY", "SMALLMONEY", "FLOAT", "REAL"}
# Cláusulas donde la comparación es un filtro (no una asignación de SET ni un alias del SELECT).
_CLAUSULAS = re.compile(r"\b(WHERE|ON|HAVING|WHEN|SET|SELECT|VALUES)\b", re.IGNORECASE)
_PALABRAS_SQL = {"AND", "OR", "NOT", "WHERE", "ON", "WHEN", "THEN", "ELSE", "CASE", "HAVING", "IS", "NULL", "LIKE"}

# Varias columnas: el texto de la usuaria (8 nov.) en general.
QUE_HACER_NUMERO_CON_TEXTO = (
    "Se recomienda verificar el tipo de dato de cada columna y realizar la comparación utilizando el mismo tipo: "
    "si la columna es numérica, se debe comparar con un valor numérico, sin utilizar comillas."
)


def _sin_corchetes(nombre: str) -> str:
    return re.sub(r"\s+", "", nombre).replace("[", "").replace("]", "")


def tipos_de_temporales(limpio: str) -> Dict[str, Dict[str, str]]:
    """{#tabla (minúsculas): {columna (minúsculas): TIPO}} de cada CREATE TABLE #T / DECLARE @T TABLE del script."""
    tablas: Dict[str, Dict[str, str]] = {}
    for match in _DEFINE_TABLA.finditer(limpio):
        tabla = (match.group(1) or match.group(2)).lower()
        columnas = tablas.setdefault(tabla, {})
        for definicion, _ in _por_comas(_contenido(limpio, match.end() - 1)):
            columna = re.match(rf"\s*({_IDENT})\s+([A-Za-z]+)", definicion)
            if columna:
                columnas[_sin_corchetes(columna.group(1)).lower()] = columna.group(2).upper()
    return tablas


def _tabla_del_alias(limpio: str, posicion: int, alias: str) -> Optional[str]:
    """La tabla del alias en el FROM/JOIN/UPDATE más cercano (CT en «JOIN DBCMACICA.DBO.Constante CT»)."""
    candidatos = list(re.finditer(
        rf"\b(?:FROM|JOIN|UPDATE)\s+({_REFERENCIA})\s+(?:AS\s+)?{re.escape(alias)}(?![\w$#])", limpio, re.IGNORECASE))
    if not candidatos:
        # Sin alias: la tabla se usa por su nombre (FROM #T WHERE #T.n = '1').
        return alias if alias.startswith(("#", "@")) else None
    return _sin_corchetes(min(candidatos, key=lambda m: abs(m.start() - posicion)).group(1))


def _tabla_unica_del_from(limpio: str, posicion: int) -> Optional[str]:
    """Columna sin alias: la tabla, solo si la sentencia tiene una sola tabla (sin JOIN)."""
    inicio = max(limpio.rfind(";", 0, posicion), 0)
    froms = list(re.finditer(rf"\bFROM\s+({_REFERENCIA})", limpio[inicio:posicion], re.IGNORECASE))
    if not froms or re.search(r"\bJOIN\b", limpio[inicio + froms[-1].start():posicion], re.IGNORECASE):
        return None
    return _sin_corchetes(froms[-1].group(1))


def _es_filtro(limpio: str, posicion: int) -> bool:
    previo = sin_parentesis_cerrados(limpio[:posicion])
    clausulas = _CLAUSULAS.findall(previo[previo.rfind(";") + 1:])
    return bool(clausulas) and clausulas[-1].upper() in {"WHERE", "ON", "HAVING", "WHEN"}


def _consulta_tipo(tabla: str, columna: str) -> str:
    """Consulta a INFORMATION_SCHEMA.COLUMNS que muestra el tipo real (Genesis no se conecta a la base)."""
    partes = tabla.split(".")
    base, esquema, nombre = ([""] * (3 - len(partes)) + partes)[-3:]
    vista = f"{base}.INFORMATION_SCHEMA.COLUMNS" if base else "INFORMATION_SCHEMA.COLUMNS"
    filtro_esquema = f"TABLE_SCHEMA = '{esquema}' AND " if esquema else ""
    return (f"SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE\nFROM {vista}\n"
            f"WHERE {filtro_esquema}TABLE_NAME = '{nombre}' AND COLUMN_NAME = '{columna}'")


def numero_comparado_con_texto(
    texto: str, limpio: str, linea_de: Callable[[int], int],
) -> Optional[Tuple[int, str, List[int], bool, Optional[str]]]:
    """(posición, mensaje, líneas, hay_certeza, consulta) con todas las comparaciones, o None.

    `limpio` vacía el contenido de los textos (mismas posiciones): el valor se lee de `texto`.
    """
    temporales = tipos_de_temporales(limpio)
    casos, vistos, consultas = [], set(), []
    for patron in _COMPARACIONES:
        for match in patron.finditer(limpio):
            expresion = re.sub(r"\s+", "", match.group("col"))
            if expresion.upper() in _PALABRAS_SQL or not _es_filtro(limpio, match.start()):
                continue
            if "lista" in match.re.groupindex:
                valores = re.findall(r"N?'[^']*'", texto[match.start("lista"):match.end("lista")])
            else:
                valores = [texto[match.start("lit"):match.end("lit")]]
            if not valores or not all(re.fullmatch(r"N?'\d+'", v) for v in valores):
                continue
            alias, _, columna = expresion.rpartition(".")
            columna = _sin_corchetes(columna)
            tabla = (_tabla_del_alias(limpio, match.start(), _sin_corchetes(alias)) if alias
                     else _tabla_unica_del_from(limpio, match.start()))
            tipo, certeza = None, False
            if tabla and tabla.startswith(("#", "@")):
                tipo = temporales.get(tabla.lower(), {}).get(columna.lower())
                if tipo is not None:
                    if tipo not in _TIPOS_NUMERO:
                        continue  # el tipo real es texto (o fecha): la comparación está bien
                    certeza = True
            if not certeza and not re.match(r"n[A-Z]", columna):
                continue
            clave = (expresion.lower(), tuple(valores))
            if clave in vistos:
                continue
            vistos.add(clave)
            numeros = ", ".join(v.lstrip("N").strip("'") for v in valores)
            uno = len(valores) == 1
            valor = f"un valor de texto ({valores[0]})" if uno else f"valores de texto ({', '.join(valores)})"
            ejemplo = f"{expresion} = {numeros}" if uno else f"{expresion} IN ({numeros})"
            # Con certeza (temporal del script) se afirma el tipo, como en el texto de la usuaria; en una tabla
            # física solo se conoce el prefijo y no se afirma un tipo que no se verificó.
            if certeza:
                hecho = f"{expresion}, definida como {tipo}, se compara con {valor}"
                regla = f"En este caso, como {expresion} es de tipo {tipo}, se debe comparar"
            else:
                hecho = f"{expresion}, de tipo numérico según su prefijo, se compara con {valor}"
                regla = f"Si {expresion} es de tipo numérico, se debe comparar"
                if tabla and not tabla.startswith(("#", "@")):
                    consultas.append(_consulta_tipo(tabla, columna))
            sin_comillas = f"con {'un valor numérico' if uno else 'valores numéricos'}, sin utilizar comillas"
            casos.append((match.start(), hecho, certeza, f"{regla} {sin_comillas} (ej.: {ejemplo})."))
    if not casos:
        return None
    casos.sort()
    if len(casos) == 1:
        _, hecho, _, que_hacer = casos[0]
        mensaje = (f"Se identificó que la columna {hecho}. Se recomienda verificar el tipo de dato de la columna y "
                   f"realizar la comparación utilizando el mismo tipo. {que_hacer}")
    else:
        mensaje = (f"Se identificaron las siguientes columnas numéricas comparadas con texto: "
                   f"{'; '.join(hecho for _, hecho, _, _ in casos)}. {QUE_HACER_NUMERO_CON_TEXTO}")
    consulta = "\nUNION ALL\n".join(dict.fromkeys(consultas)) or None
    return (casos[0][0], mensaje, sorted({linea_de(p) for p, *_ in casos}),
            any(certeza for _, _, certeza, _ in casos), consulta)
