"""Riesgos identificados por Genesis en el plan, para los que SQL Server no emite alerta.

Se muestran aparte, debajo de las demás observaciones («Análisis complementario»): no vienen de una
alerta del plan, sino del criterio de Genesis al leer sus expresiones. Lo comparten Reportes y Negocio.

Conversión de texto a número: SUBSTRING, LEFT o RIGHT (siempre devuelven texto) que el plan convierte
implícitamente a número al compararlo con un número, por ejemplo SUBSTRING(cCtaCod, 9, 1) = 1. SQL Server solo alerta las
conversiones que cambian el plan (WHERE/JOIN); estas, en el SELECT o en un CASE, no las alerta, pero si el
dato no es numérico la consulta se cae con «Conversion failed when converting the varchar value…».
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

_TIPO_NUMERICO = r"tinyint|smallint|int|bigint|decimal\(\d+,\d+\)|numeric\(\d+,\d+\)|money|smallmoney|float|real"
# CONVERT_IMPLICIT(int,substring([Base].[dbo].[Tabla].[cCtaCod] as [A].[cCtaCod],(9),(1)),0)
_CONVERSION = re.compile(
    rf"CONVERT_IMPLICIT\((?P<tipo>{_TIPO_NUMERICO}),(?P<funcion>substring|left|right)\("
    r"(?P<columna>(?:\[[^\]]+\]\.)*\[(?P<nombre>[^\]]+)\])(?: as (?:\[[^\]]+\]\.)*\[[^\]]+\])?"
    r"(?P<argumentos>(?:,\(-?\d+\))+)\),0\)",
    re.IGNORECASE,
)
_COMPARACION_DESPUES = re.compile(r"\s*(=|<>|!=|>=|<=|>|<)\s*\((-?\d+)\)")
_COMPARACION_ANTES = re.compile(r"\((-?\d+)\)\s*(=|<>|!=|>=|<=|>|<)\s*$")


def _expresion(conversion: re.Match) -> str:
    """SUBSTRING(cCtaCod, 9, 1) / LEFT(cCodigo, 2), como lo escribiría el desarrollador."""
    argumentos = ", ".join(re.findall(r"-?\d+", conversion.group("argumentos")))
    return f"{conversion.group('funcion').upper()}({conversion.group('nombre')}, {argumentos})"


def _casos(sentencias: List[Dict]) -> Dict[Tuple[str, str], Dict]:
    """{(la expresión de texto, el número con que se compara): {consultas, nodos}} en el orden en que aparecen."""
    casos: Dict[Tuple[str, str], Dict] = {}
    for sentencia in sentencias:
        for nodo in sentencia["nodos"]:
            for predicado in nodo.get("predicados", []):
                texto = predicado.get("texto", "")
                for conversion in _CONVERSION.finditer(texto):
                    expresion = _expresion(conversion)
                    despues = _COMPARACION_DESPUES.match(texto, conversion.end())
                    antes = _COMPARACION_ANTES.search(texto[:conversion.start()])
                    if despues:
                        clave = (expresion, despues.group(2))
                    elif antes:
                        clave = (expresion, antes.group(1))
                    else:
                        # Sin comparación (asignación a una variable numérica, cálculo): suele ser intencional y no
                        # decide un resultado. Solo se observan las comparaciones (decisión de la usuaria, 1 nov.).
                        continue
                    caso = casos.setdefault(clave, {"consultas": [], "nodos": []})
                    if sentencia["numero"] not in caso["consultas"]:
                        caso["consultas"].append(sentencia["numero"])
                        # Un operador por consulta en la imagen: SQL Server puede calcular la misma comparación en
                        # varios Compute Scalar (una por columna del SELECT), pero en el código es un solo cambio.
                        caso["nodos"].append({"consulta": sentencia["numero"], "nodo": nodo["id"]})
    return casos


def conversion_texto_a_numero(sentencias: List[Dict]) -> List[Hallazgo]:
    casos = _casos(sentencias)
    if not casos:
        return []
    # Modelo de redacción de la usuaria (13 nov.) para los riesgos de Genesis. Sin «(consulta N)» (la imagen ya la
    # marca) y pidiendo validar el resultado: con número, ' ' vale 0 y '01' vale 1; con texto no.
    if len(casos) == 1:
        (expresion, numero), = casos
        mensaje = (f"Se identificó una conversión implícita al comparar {expresion} con el valor numérico {numero}. "
                   f"Se recomienda corregir la conversión implícita identificada, realizando la comparación con un "
                   f"valor del mismo tipo de dato y validando que el cambio no altere el resultado esperado.")
    else:
        comparaciones = "; ".join(f"{expresion} con el valor numérico {numero}" for expresion, numero in casos)
        mensaje = (f"Se identificaron conversiones implícitas al comparar: {comparaciones}. Se recomienda corregir "
                   f"las conversiones implícitas identificadas, realizando cada comparación con un valor del mismo tipo "
                   f"de dato y validando que el cambio no altere el resultado esperado.")
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.MEDIO,
        regla="CONVERSION_TEXTO_A_NUMERO",
        mensaje=mensaje,
    )
    hallazgo.nodos = [marca for caso in casos.values() for marca in caso["nodos"]]
    hallazgo.complementario = True  # va en «Riesgos identificados por Genesis»
    return [hallazgo]


# Columna de texto convertida a fecha o número (usuaria, 9 nov.): CONVERT_IMPLICIT(datetime,[#CtaSaldoAuxTemp].[cFecha],0).
# Solo columnas reales con el prefijo de texto del estándar (c + mayúscula: cFecha, cCtaCod). No cuentan: [Expr…]
# (COUNT y cálculos), variables (@…, se convierten una sola vez), valores de XML/JSON ni SUBSTRING/LEFT/RIGHT
# (los revisa la regla de arriba, que solo observa las comparaciones).
_TIPO_FECHA = r"date|datetime|datetime2(?:\(\d\))?|smalldatetime|datetimeoffset(?:\(\d\))?|time(?:\(\d\))?"
_COLUMNA_CONVERTIDA = re.compile(
    rf"CONVERT_IMPLICIT\((?P<tipo>{_TIPO_FECHA}|{_TIPO_NUMERICO}),"
    r"(?P<calificadores>(?:(?:\[[^\]]+\]|#?[\w#$]+)\.)+)\[(?P<nombre>[^\]]+)\]"
    r"(?: as (?:\[[^\]]+\]\.)*\[[^\]]+\])?,\d+\)",
    re.IGNORECASE,
)
_PREFIJO_TEXTO = re.compile(r"c[A-Z]")


def _casos_columna_texto(sentencias: List[Dict]) -> Dict[Tuple[str, str, str], Dict]:
    """{(columna, tabla, tipo): {consultas, nodos}} en el orden en que aparecen."""
    casos: Dict[Tuple[str, str, str], Dict] = {}
    for sentencia in sentencias:
        # Lo que SQL Server ya alertó (Convert Issue) lo observa «Conversión implícita detectada»: no se repite.
        # Se compara columna y tipo: la alerta usa el alias ([CL].[cCodCliente]) y el Compute Scalar el nombre completo.
        alertadas = {
            (m.group("nombre").lower(), m.group("tipo").lower())
            for nodo in sentencia["nodos"] for a in nodo.get("advertencias", []) if a["tipo"] == "conversion"
            for m in _COLUMNA_CONVERTIDA.finditer(a["texto"])
        }
        for nodo in sentencia["nodos"]:
            for predicado in nodo.get("predicados", []):
                for conversion in _COLUMNA_CONVERTIDA.finditer(predicado.get("texto", "")):
                    nombre = conversion.group("nombre")
                    if not _PREFIJO_TEXTO.match(nombre) or (nombre.lower(), conversion.group("tipo").lower()) in alertadas:
                        continue
                    tabla = conversion.group("calificadores").rstrip(".").split(".")[-1].strip("[]")
                    caso = casos.setdefault((nombre, tabla, conversion.group("tipo").lower()), {"consultas": [], "nodos": []})
                    if sentencia["numero"] not in caso["consultas"]:
                        caso["consultas"].append(sentencia["numero"])
                        caso["nodos"].append({"consulta": sentencia["numero"], "nodo": nodo["id"]})
    return casos


def columna_texto_convertida(sentencias: List[Dict]) -> List[Hallazgo]:
    casos = _casos_columna_texto(sentencias)
    if not casos:
        return []
    # Sin «(consulta N)»: la imagen ya marca la consulta y el operador (usuaria, 9 nov.).
    lista = "; ".join(f"{columna} de {tabla} a {tipo}" for columna, tabla, tipo in casos)
    # Modelo de redacción de la usuaria (13 nov.) para los riesgos de Genesis.
    if len(casos) == 1:
        mensaje = (f"Se identificó una conversión implícita de la columna de texto {lista}. Se recomienda corregir la "
                   f"conversión implícita identificada, definiendo la columna con el tipo de dato que corresponde y "
                   f"validando que el cambio no altere el resultado esperado.")
    else:
        mensaje = (f"Se identificaron conversiones implícitas de las columnas de texto: {lista}. Se recomienda corregir "
                   f"las conversiones implícitas identificadas, definiendo cada columna con el tipo de dato que "
                   f"corresponde y validando que el cambio no altere el resultado esperado.")
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.MEDIO,
        regla="COLUMNA_TEXTO_CONVERTIDA",
        mensaje=mensaje,
    )
    hallazgo.nodos = [marca for caso in casos.values() for marca in caso["nodos"]]
    hallazgo.complementario = True  # va en «Riesgos identificados por Genesis»
    return [hallazgo]


# --- Conversión de una columna (BIT, número, fecha) dentro de un filtro o un JOIN (usuaria, 18 nov.) ----------------
# Comprobado en SQL Server: convertida en el resultado (SELECT, SET de un UPDATE) no afecta; en un filtro o un JOIN
# impide usar el índice y obliga a recorrer la tabla, y SQL Server no siempre lo alerta. Para no llenar el informe,
# solo se marca cuando cuesta: el recorrido de esa tabla lee muchas filas y devuelve pocas.
FILAS_LEIDAS_MINIMAS = 10_000
PROPORCION_DEVUELTA_MAXIMA = 0.10  # devuelve como mucho el 10 % de lo que lee
FILAS_PARA_NIVEL_MEDIO = 1_000_000
# Dónde la conversión filtra o une (no las columnas de salida ni los Defined Values).
_PREDICADOS_DE_FILTRO = {"Seek Predicates", "Predicate", "Probe Residual", "Residual", "Hash Keys Probe",
                         "Hash Keys Build", "Inner Side Join Columns", "Outer Side Join Columns"}
# [Expr1003] = Scalar Operator(CONVERT_IMPLICIT(int,[Base].[Esquema].[Tabla].[bColumna] as [B].[bColumna],0))
_EXPR_CONVERTIDA = re.compile(
    r"\[(?P<expr>Expr\d+)\] = Scalar Operator\((?P<conversion>CONVERT_IMPLICIT\((?:[^()]|\(\d+(?:,\d+)?\))*\))\)")
_REFERENCIA_EXPR = re.compile(r"\[(Expr\d+)\]")


def _conversiones_de_columnas(texto: str) -> List[re.Match]:
    """Conversiones sobre una columna real que no es de texto (las de texto las ve «columna de texto convertida»)."""
    return [m for m in _COLUMNA_CONVERTIDA.finditer(texto) if not _PREFIJO_TEXTO.match(m.group("nombre"))]


def _recorrido_costoso(sentencia: Dict, tabla: str):
    """El recorrido (Scan) de esa tabla que más lee, si lee mucho y devuelve poco: (leídas, devueltas, nodo) o None."""
    peor = None
    for nodo in sentencia["nodos"]:
        objeto = nodo.get("objeto", "").split(".")[-1].strip("[]")
        leidas, devueltas = nodo.get("filasLeidas"), nodo.get("filasReales")
        if ("scan" not in nodo.get("fisica", "").lower() or objeto.lower() != tabla.lower()
                or leidas is None or devueltas is None):
            continue
        if leidas >= FILAS_LEIDAS_MINIMAS and devueltas <= leidas * PROPORCION_DEVUELTA_MAXIMA:
            if peor is None or leidas > peor[0]:
                peor = (leidas, devueltas, nodo)
    return peor


def conversion_columna_en_filtro(sentencias: List[Dict]) -> List[Hallazgo]:
    casos: Dict[Tuple[str, str, str], Dict] = {}
    for sentencia in sentencias:
        # Lo que SQL Server ya alertó (Convert Issue) lo observa «Conversión implícita detectada»: no se repite.
        alertadas = {
            (m.group("nombre").lower(), m.group("tipo").lower())
            for nodo in sentencia["nodos"] for a in nodo.get("advertencias", []) if a["tipo"] == "conversion"
            for m in _COLUMNA_CONVERTIDA.finditer(a["texto"])
        }
        # Expresiones que son solo la conversión de una columna ([Expr1003] = CONVERT_IMPLICIT(int, bColumna)): si un
        # filtro o un JOIN usa [Expr1003], la conversión está en el filtro aunque se calcule en un Compute Scalar.
        exprs: Dict[str, re.Match] = {}
        for nodo in sentencia["nodos"]:
            for predicado in nodo.get("predicados", []):
                if predicado.get("nombre") == "Defined Values":
                    for definida in _EXPR_CONVERTIDA.finditer(predicado.get("texto", "")):
                        conversiones = _conversiones_de_columnas(definida.group("conversion"))
                        if conversiones:
                            exprs[definida.group("expr")] = conversiones[0]
        for nodo in sentencia["nodos"]:
            for predicado in nodo.get("predicados", []):
                if predicado.get("nombre") not in _PREDICADOS_DE_FILTRO:
                    continue
                texto = predicado.get("texto", "")
                encontradas = _conversiones_de_columnas(texto) + [
                    exprs[e] for e in _REFERENCIA_EXPR.findall(texto) if e in exprs]
                for conversion in encontradas:
                    nombre, tipo = conversion.group("nombre"), conversion.group("tipo").lower()
                    if (nombre.lower(), tipo) in alertadas:
                        continue
                    tabla = conversion.group("calificadores").rstrip(".").split(".")[-1].strip("[]")
                    costo = _recorrido_costoso(sentencia, tabla)
                    if costo is None:
                        continue
                    caso = casos.setdefault((nombre, tabla, tipo), {"leidas": 0, "devueltas": 0, "nodos": []})
                    if costo[0] > caso["leidas"]:
                        caso["leidas"], caso["devueltas"] = costo[0], costo[1]
                    for marca in ({"consulta": sentencia["numero"], "nodo": nodo["id"]},
                                  {"consulta": sentencia["numero"], "nodo": costo[2]["id"]}):
                        if marca not in caso["nodos"]:
                            caso["nodos"].append(marca)
    if not casos:
        return []

    # Modelo de redacción de los riesgos de Genesis (usuaria, 13 nov.). Texto propuesto, por aprobar (18 nov.).
    def detalle(clave, caso) -> str:
        columna, tabla, tipo = clave
        return (f"{columna} de {tabla} a {tipo}, que obliga a leer {caso['leidas']:,.0f} filas para devolver "
                f"{caso['devueltas']:,.0f}")

    if len(casos) == 1:
        clave, caso = next(iter(casos.items()))
        mensaje = (f"Se identificó una conversión implícita en un filtro de la columna {detalle(clave, caso)}. Se "
                   f"recomienda corregir la conversión implícita identificada, comparando la columna con un valor del "
                   f"mismo tipo de dato y validando que el cambio no altere el resultado esperado.")
    else:
        lista = "; ".join(detalle(clave, caso) for clave, caso in casos.items())
        mensaje = (f"Se identificaron conversiones implícitas en filtros de las columnas: {lista}. Se recomienda "
                   f"corregir las conversiones implícitas identificadas, comparando cada columna con un valor del "
                   f"mismo tipo de dato y validando que el cambio no altere el resultado esperado.")
    severidad = (Severidad.MEDIO if max(c["leidas"] for c in casos.values()) >= FILAS_PARA_NIVEL_MEDIO
                 else Severidad.BAJO)
    hallazgo = Hallazgo(linea=1, origen=OrigenAnalisis.PLAN_EJECUCION, severidad=severidad,
                        regla="CONVERSION_COLUMNA_EN_FILTRO", mensaje=mensaje)
    hallazgo.nodos = [marca for caso in casos.values() for marca in caso["nodos"]]
    hallazgo.complementario = True  # va en «Riesgos identificados por Genesis»
    return [hallazgo]


def riesgos_genesis(sentencias: List[Dict]) -> List[Hallazgo]:
    """Riesgos propios de Genesis: texto a número en comparaciones, columna de texto convertida y conversión de una
    columna dentro de un filtro que obliga a recorrer la tabla."""
    return (conversion_texto_a_numero(sentencias) + columna_texto_convertida(sentencias)
            + conversion_columna_en_filtro(sentencias))
