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
    """{(lo encontrado, la corrección): {consultas, nodos}} en el orden en que aparecen."""
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
                        operador, numero = despues.group(1), despues.group(2)
                        clave = (f"«{expresion} {operador} {numero}»", f"{expresion} {operador} '{numero}'")
                    elif antes:
                        numero, operador = antes.group(1), antes.group(2)
                        clave = (f"«{numero} {operador} {expresion}»", f"'{numero}' {operador} {expresion}")
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


def _consultas(numeros: List[int]) -> str:
    if len(numeros) == 1:
        return f"consulta {numeros[0]}"
    return f"consultas {', '.join(map(str, numeros[:-1]))} y {numeros[-1]}"


def conversion_texto_a_numero(sentencias: List[Dict]) -> List[Hallazgo]:
    casos = _casos(sentencias)
    if not casos:
        return []
    lista = "; ".join(
        f"{encontrado} → «{correccion}» ({_consultas(caso['consultas'])})"
        for (encontrado, correccion), caso in casos.items()
    )
    if len(casos) == 1:
        mensaje = (f"Se identificó una comparación en la que un texto se convierte implícitamente a número: {lista}. "
                   f"Se recomienda comparar con un valor de texto, como se indica, ya que si el dato no es numérico "
                   f"la consulta generará un error de conversión.")
    else:
        mensaje = (f"Se identificaron {len(casos)} comparaciones en las que un texto se convierte implícitamente a "
                   f"número: {lista}. Se recomienda comparar con valores de texto, como se indica en cada caso, ya "
                   f"que si el dato no es numérico la consulta generará un error de conversión.")
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
    lista = "; ".join(
        f"{columna} de {tabla} a {tipo} ({_consultas(caso['consultas'])})"
        for (columna, tabla, tipo), caso in casos.items()
    )
    # Texto de la usuaria (9 nov.).
    if len(casos) == 1:
        mensaje = (f"Se identificó una conversión implícita sobre la columna {lista}. Se recomienda definir la columna "
                   f"con el tipo de dato correcto, ya que un valor con formato inválido genera un error de conversión.")
    else:
        mensaje = (f"Se identificaron conversiones implícitas sobre las columnas: {lista}. Se recomienda definir las "
                   f"columnas con el tipo de dato correcto, ya que un valor con formato inválido genera un error de "
                   f"conversión.")
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


def riesgos_genesis(sentencias: List[Dict]) -> List[Hallazgo]:
    """Todas las reglas de riesgos propios de Genesis: texto a número en comparaciones y columna de texto convertida."""
    return conversion_texto_a_numero(sentencias) + columna_texto_convertida(sentencias)
