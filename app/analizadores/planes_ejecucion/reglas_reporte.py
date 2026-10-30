"""Reglas de los planes de ejecución del área Reportes (las define la usuaria, una por una).

Trabajan sobre el mismo árbol que se dibuja (construir_diagrama), así lo que dice
la observación y lo que se ve en el diagrama siempre coinciden.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

# Basta con que la expresión tenga CONVERT_IMPLICIT( : la conversión puede llevar funciones con varios
# niveles de paréntesis (CONVERT_IMPLICIT(int,substring([T].[c],(1),(14)),0)) y aun así es la misma alerta.
_CONVERSION_IMPLICITA = re.compile(r"\bCONVERT_IMPLICIT\s*\(", re.IGNORECASE)

# Qué provoca cada tipo de «Convert Issue» de SQL Server.
_EFECTO = {
    "SeekPlan": "impide buscar en el índice (SeekPlan)",
    "CardinalityEstimate": "altera la estimación de filas (CardinalityEstimate)",
}


def _nombre_operador(nodo: Dict) -> str:
    return nodo["fisica"].upper() if nodo["padre"] is None else nodo["fisica"]


def _lee_xml(sentencia: Dict) -> bool:
    """La consulta lee un XML: operadores «XML Reader» (OPENXML, .nodes()) o UDX (métodos .value(), .query())."""
    return any(
        "XML READER" in (nodo.get("objeto") or "").upper() or nodo["fisica"].upper() == "UDX"
        for nodo in sentencia["nodos"]
    )


def _conversiones_con_alerta(sentencias: List[Dict]) -> List[Dict]:
    """Conversiones implícitas que SQL Server marcó con alerta (Convert Issue con CONVERT_IMPLICIT).

    Una conversión explícita (CONVERT o CAST escrito en la consulta) o una
    conversión implícita sin alerta no cuentan.
    """
    casos = []
    for sentencia in sentencias:
        lee_xml = _lee_xml(sentencia)
        for nodo in sentencia["nodos"]:
            for advertencia in nodo["advertencias"]:
                if advertencia["tipo"] != "conversion":
                    continue
                if not _CONVERSION_IMPLICITA.search(advertencia["texto"]):
                    continue
                # «Convert Issue: <Problema> <expresión tal cual el XML>»
                partes = advertencia["texto"].split(" ", 3)
                problema = partes[2] if len(partes) > 2 else ""
                # Al leer un XML (OPENXML, .nodes(), .value()) sus valores llegan como texto y SQL Server los
                # convierte al tipo de cada columna: esas conversiones de valores internos no se observan.
                expresion = partes[3] if len(partes) > 3 else ""
                if _VALOR_DEL_XML.fullmatch(expresion) or (lee_xml and _CONVERSION_INTERNA.fullmatch(expresion)):
                    continue
                casos.append({
                    "consulta": sentencia["numero"],
                    "nodo": nodo,
                    "expresion": partes[3] if len(partes) > 3 else advertencia["texto"],
                    "efecto": _EFECTO.get(problema, problema),
                })
    return casos


def _ubicacion(caso: Dict, varias_consultas: bool, mayuscula: bool = False) -> str:
    nodo = caso["nodo"]
    # Sin el número de nodo (NodeId): confunde en el informe; la imagen ya señala el operador.
    if nodo["padre"] is None and nodo["fisica"] == "IF":
        lugar = "la condición IF"
    else:
        lugar = f"el operador {_nombre_operador(nodo)}"
    if varias_consultas:
        lugar += f" de la consulta {caso['consulta']}"
    if mayuscula:  # en las listas va sin artículo: «Operador SELECT…», «Condición IF…»
        lugar = lugar.split(" ", 1)[1]
        return lugar[:1].upper() + lugar[1:]
    return lugar


# Recomendaciones con el estilo de la usuaria: directas y simples.
_RECOMENDACION_CONVERSION = (
    "Se recomienda revisar la alerta por conversión implícita y homologar los tipos de datos de las columnas "
    "involucradas para evitar conversiones implícitas y mejorar el rendimiento de la consulta."
)
_RECOMENDACION_CONVERSIONES = (
    "Se recomienda revisar las alertas por conversiones implícitas y homologar los tipos de datos de las "
    "columnas involucradas para evitar conversiones implícitas y mejorar el rendimiento de las consultas."
)
# Varias alertas en un mismo operador (una sola consulta).
_RECOMENDACION_CONVERSIONES_UNA_CONSULTA = _RECOMENDACION_CONVERSIONES.replace("de las consultas.", "de la consulta.")


# Al insertar, los valores del SELECT se convierten al tipo de las columnas de la tabla destino.
_RECOMENDACION_INSERT = (
    "Se recomienda revisar que los tipos de datos de las columnas de la tabla donde se inserta coincidan con los "
    "de los valores del SELECT, para evitar conversiones implícitas y mejorar el rendimiento de la consulta."
)
_RECOMENDACION_INSERTS = (
    "Se recomienda revisar que los tipos de datos de las columnas de las tablas donde se inserta coincidan con los "
    "de los valores del SELECT, para evitar conversiones implícitas y mejorar el rendimiento de las consultas."
)

# Conversión de un valor calculado por SQL Server ([Expr1019]): su nombre interno no le dice nada al lector,
# así que se resume por tipo («6 a varchar(10)»). Si es sobre una columna real, se muestra la expresión.
_CONVERSION_INTERNA = re.compile(r"CONVERT_IMPLICIT\((\w+(?:\([^()]*\))?),\[Expr\d+\],\d+\)", re.IGNORECASE)
# El valor viene directo del lector del XML: «CONVERT_IMPLICIT(int,XML Reader with XPath filter.[value],0)».
_VALOR_DEL_XML = re.compile(r"CONVERT_IMPLICIT\(\w+(?:\([^()]*\))?,XML Reader[^,]*\.\[\w+\],\d+\)", re.IGNORECASE)
_OPERADORES_INSERT = {"INSERT", "TABLE INSERT", "CLUSTERED INDEX INSERT", "INDEX INSERT"}


def _en_plural(efecto: str) -> str:
    """«altera la estimación…» → «alteran la estimación…»; «impide buscar…» → «impiden buscar…»."""
    verbo, _, resto = efecto.partition(" ")
    return f"{verbo}n {resto}" if verbo.endswith(("a", "e")) else efecto


def _enumerar(partes: List[str]) -> str:
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} y {partes[-1]}"


def _elementos(casos: List[Dict]) -> str:
    """Las expresiones sobre columnas reales tal cual y las internas resumidas por tipo de dato."""
    reales = [f"«{c['expresion']}»" for c in casos if not _CONVERSION_INTERNA.fullmatch(c["expresion"])]
    por_tipo: Dict[str, int] = {}
    for caso in casos:
        interna = _CONVERSION_INTERNA.fullmatch(caso["expresion"])
        if interna:
            por_tipo[interna.group(1)] = por_tipo.get(interna.group(1), 0) + 1
    resumen = [f"{cantidad} a {tipo}" for tipo, cantidad in sorted(por_tipo.items(), key=lambda par: -par[1])]
    return _enumerar(list(dict.fromkeys(reales)) + resumen)


def _describir_operador(grupo: List[Dict]) -> str:
    """«…, que altera…» o, con varios efectos, cada parte con el suyo."""
    efectos: Dict[str, List[Dict]] = {}
    for caso in grupo:
        efectos.setdefault(caso["efecto"], []).append(caso)
    return "; ".join(
        f"{_elementos(casos)}, que {_en_plural(efecto) if len(casos) > 1 else efecto}" for efecto, casos in efectos.items()
    )


def _conversion_implicita(sentencias: List[Dict]) -> List[Hallazgo]:
    casos = _conversiones_con_alerta(sentencias)
    if not casos:
        return []
    varias_consultas = len({s["numero"] for s in sentencias}) > 1
    # Varias conversiones en el mismo operador de la misma consulta van juntas: se nombra una vez.
    por_operador: Dict[tuple, List[Dict]] = {}
    for caso in casos:
        por_operador.setdefault((caso["consulta"], caso["nodo"]["id"]), []).append(caso)
    grupos = list(por_operador.values())
    en_insert = all(
        _CONVERSION_INTERNA.fullmatch(c["expresion"]) and c["nodo"]["fisica"].upper() in _OPERADORES_INSERT for c in casos
    )
    if len(casos) == 1:
        caso = casos[0]
        recomendacion = _RECOMENDACION_INSERT if en_insert else _RECOMENDACION_CONVERSION
        mensaje = (
            f"Se ha identificado una conversión implícita en {_ubicacion(caso, varias_consultas)}: "
            f"«{caso['expresion']}», que {caso['efecto']}. {recomendacion}"
        )
    elif len(grupos) == 1:
        # Un solo operador: «Se han identificado 12 conversiones implícitas en el operador INSERT…».
        grupo = grupos[0]
        efectos = {c["efecto"] for c in grupo}
        ubicacion = _ubicacion(grupo[0], varias_consultas)
        if len(efectos) == 1:
            detalle = f"{ubicacion}, que {_en_plural(grupo[0]['efecto'])}: {_elementos(grupo)}"
        else:
            detalle = f"{ubicacion}: {_describir_operador(grupo)}"
        recomendacion = _RECOMENDACION_INSERT if en_insert else _RECOMENDACION_CONVERSIONES_UNA_CONSULTA
        mensaje = f"Se han identificado {len(casos)} conversiones implícitas en {detalle}. {recomendacion}"
    else:
        consultas = sorted({c["consulta"] for c in casos})
        encabezado = ("la consulta " if len(consultas) == 1 else "las consultas ") + ", ".join(map(str, consultas))

        def linea(grupo: List[Dict]) -> str:
            lugar = _ubicacion(grupo[0], varias_consultas, mayuscula=True)
            if len(grupo) == 1:
                return f"{lugar}: «{grupo[0]['expresion']}», que {grupo[0]['efecto']}"
            if len({c["efecto"] for c in grupo}) == 1:
                return (f"{lugar}: {len(grupo)} conversiones ({_elementos(grupo)}), que "
                        f"{_en_plural(grupo[0]['efecto'])}")
            return f"{lugar}: {len(grupo)} conversiones ({_describir_operador(grupo)})"

        recomendacion = _RECOMENDACION_INSERTS if en_insert else _RECOMENDACION_CONVERSIONES
        mensaje = (
            f"Se identificaron {len(casos)} conversiones implícitas, en {encabezado}: "
            f"{'; '.join(linea(g) for g in grupos)}. {recomendacion}"
        )
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.ALTO,
        regla="CONVERSION_IMPLICITA_DETECTADA",
        mensaje=mensaje,
    )
    # Un operador con varias alertas aparece una sola vez (su imagen ya las muestra todas).
    hallazgo.nodos = list({(c["consulta"], c["nodo"]["id"]): {"consulta": c["consulta"], "nodo": c["nodo"]["id"]} for c in casos}.values())
    return [hallazgo]


# Lectura residual: filas leídas (ActualRowsRead) a partir de las cuales se marca.
LECTURA_RESIDUAL_MINIMA = 1_000_000


def _cifra(valor: float) -> str:
    return f"{valor:,.0f}"


def _lectura_residual(sentencias: List[Dict]) -> List[Hallazgo]:
    """Scans que leen más de un millón de filas y devuelven menos de las que leen.

    Un Scan (Table Scan, Clustered Index Scan, Index Scan) recorre la tabla completa
    o casi completa y descarta con el filtro las filas que no sirven: «lectura residual».
    Un Seek no se marca: ya busca directo en el índice, es el acceso óptimo.
    """
    varias_consultas = len({s["numero"] for s in sentencias}) > 1
    casos = []
    for sentencia in sentencias:
        for nodo in sentencia["nodos"]:
            if "scan" not in nodo["fisica"].lower():
                continue
            leidas, devueltas = nodo.get("filasLeidas"), nodo.get("filasReales")
            if leidas is None or devueltas is None or leidas <= LECTURA_RESIDUAL_MINIMA or devueltas >= leidas:
                continue
            casos.append({"consulta": sentencia["numero"], "nodo": nodo, "leidas": leidas, "devueltas": devueltas})
    if not casos:
        return []

    # La misma tabla por el mismo índice en varias consultas es un solo problema (se arregla una vez):
    # una observación con la imagen del caso más grave y las cifras de cada consulta.
    grupos: Dict[tuple, List[Dict]] = {}
    for caso in casos:
        clave = (caso["nodo"].get("objeto", "").upper(), caso["nodo"].get("indice", "").upper(),
                 caso["nodo"]["fisica"].upper())
        grupos.setdefault(clave, []).append(caso)

    def mas_grave(grupo: List[Dict]) -> Dict:
        """El que lee más filas por cada fila que devuelve; si empatan, el de mayor costo."""
        return max(grupo, key=lambda c: (c["leidas"] / max(c["devueltas"], 1), c["nodo"].get("costoPct") or 0))

    def describir(grupo: List[Dict]) -> str:
        nodo = grupo[0]["nodo"]
        tabla = f"la tabla {nodo['objeto']}" if nodo.get("objeto") else "una tabla"
        indice = f", índice {nodo['indice'].strip('[]')}" if nodo.get("indice") else ""
        if len(grupo) == 1:
            caso = grupo[0]
            lugar = f"{tabla} ({_nombre_operador(nodo)}{indice}"
            lugar += f", consulta {caso['consulta']})" if varias_consultas else ")"
            return f"{lugar}: se leen {_cifra(caso['leidas'])} filas y solo se devuelven {_cifra(caso['devueltas'])}"
        ordenados = sorted(grupo, key=lambda c: c["consulta"])
        consultas = [str(c["consulta"]) for c in ordenados]
        lugar = (f"{tabla} ({_nombre_operador(nodo)}{indice}), que se repite en {len(grupo)} consultas "
                 f"({', '.join(consultas[:-1])} y {consultas[-1]})")
        if len({c["leidas"] for c in grupo}) == 1:
            # Lee lo mismo en todas: se dice una vez y se listan las filas devueltas.
            devueltas = [f"{_cifra(c['devueltas'])} (consulta {c['consulta']})" for c in ordenados]
            return (f"{lugar}: se leen {_cifra(ordenados[0]['leidas'])} filas en cada una y solo se devuelven "
                    f"{', '.join(devueltas[:-1])} y {devueltas[-1]}")
        cifras = [f"en la consulta {c['consulta']} se leen {_cifra(c['leidas'])} filas y solo se devuelven "
                  f"{_cifra(c['devueltas'])}" for c in ordenados]
        return f"{lugar}: {', '.join(cifras[:-1])} y {cifras[-1]}"

    lista = list(grupos.values())
    if len(lista) == 1:
        mensaje = (
            f"Se ha identificado una lectura residual elevada sobre {describir(lista[0])}. Optimizar "
            f"las condiciones de filtrado o revisar los índices existentes, ya que la lectura abarca la totalidad "
            f"o casi la totalidad de los registros."
        )
    else:
        consultas = sorted({c["consulta"] for c in casos})
        encabezado = ("la consulta " if len(consultas) == 1 else "las consultas ") + ", ".join(map(str, consultas))
        detalle = "; ".join(d[:1].upper() + d[1:] for d in (describir(g) for g in lista))
        mensaje = (
            f"Se identificaron {len(lista)} lecturas residuales elevadas, en {encabezado}: {detalle}. "
            f"Optimizar las condiciones de filtrado o revisar los índices existentes, ya que estas lecturas abarcan, "
            f"en algunos casos, la totalidad de los registros."
        )
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.ALTO,
        regla="LECTURA_RESIDUAL_ELEVADA",
        mensaje=mensaje,
    )
    # Una imagen por tabla e índice: la del caso más grave.
    hallazgo.nodos = [{"consulta": c["consulta"], "nodo": c["nodo"]["id"]} for c in map(mas_grave, lista)]
    return [hallazgo]


def _segundos(valor: float) -> str:
    return f"{valor:,.2f} s" if valor < 10 else f"{valor:,.1f} s"


def _segundos_texto(valor: float) -> str:
    """26.8 segundos; 8.20 segundos (dos decimales si es menos de 10)."""
    return f"{valor:,.2f} segundos" if valor < 10 else f"{valor:,.1f} segundos"


def _tiempo_superado(sentencias: List[Dict], limite_s: Optional[float]) -> List[Hallazgo]:
    """El procedimiento tarda más que el límite de tiempo del área (suma de Duration de sus consultas)."""
    con_tiempo = [s for s in sentencias if s.get("duracionMs") is not None]
    if not limite_s or not con_tiempo:
        return []
    total_s = sum(s["duracionMs"] for s in con_tiempo) / 1000
    if total_s <= limite_s:
        return []
    lenta = max(con_tiempo, key=lambda s: s["duracionMs"])
    lenta_s = lenta["duracionMs"] / 1000
    motivo = f"presenta un tiempo de ejecución de {_segundos_texto(lenta_s)}"
    if len(con_tiempo) > 1:
        motivo += f", equivalente al {lenta_s / total_s * 100:.0f} % del tiempo total"
    mensaje = (
        f"El procedimiento supera el umbral de tiempo establecido: su ejecución tomó {_segundos_texto(total_s)} "
        f"y el límite es de {limite_s:g} segundos. Revisar y optimizar el siguiente bloque de la "
        f"consulta, ya que {motivo}."
    )
    hallazgo = Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=Severidad.ALTO,
        regla="TIEMPO_EJECUCION_SUPERADO",
        mensaje=mensaje,
    )
    hallazgo.nodos = [{"consulta": lenta["numero"], "nodo": "raiz"}]
    hallazgo.codigo = lenta.get("codigo") or lenta.get("texto", "")  # el bloque, tal cual el XML
    return [hallazgo]


def analizar_plan_reporte(sentencias: List[Dict], limite_s: Optional[float] = None) -> List[Hallazgo]:
    """Hallazgos del plan para el área Reportes, a partir del árbol de construir_diagrama.

    limite_s: límite de tiempo del área en segundos (None = sin límite definido).
    """
    return (
        _tiempo_superado(sentencias, limite_s)
        + _conversion_implicita(sentencias)
        + _lectura_residual(sentencias)
    )
