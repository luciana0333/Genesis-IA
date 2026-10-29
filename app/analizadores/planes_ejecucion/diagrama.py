"""Árbol del plan de ejecución para dibujarlo (estilo SQL Sentry Plan Explorer).

Por cada sentencia del plan devuelve sus datos generales (texto, costo, duración,
CPU) y sus operadores con el padre de cada uno, el porcentaje de costo propio,
las filas y las advertencias que SQL Server dejó en el XML (spills, conversiones,
Excessive Grant...), tal como vienen en el XML, sin agregar nada. El primer nodo de cada sentencia es la propia
sentencia (SELECT, INSERT...), como en el diagrama de SSMS y Plan Explorer.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Union



def _local(elemento: ET.Element) -> str:
    return elemento.tag.rsplit("}", 1)[-1]


def _numero(elemento: Optional[ET.Element], nombre: str) -> Optional[float]:
    if elemento is None:
        return None
    try:
        return float(elemento.attrib[nombre])
    except (KeyError, ValueError):
        return None


def _propios(relop: ET.Element) -> Iterable[ET.Element]:
    """Elementos de un operador sin entrar en sus operadores hijos."""
    for hijo in relop:
        if _local(hijo) == "RelOp":
            continue
        yield hijo
        yield from _propios(hijo)


def _relops_hijos(elemento: ET.Element) -> List[ET.Element]:
    """Operadores hijos directos: los RelOp más cercanos, sin atravesar otro RelOp."""
    hijos = []
    for hijo in elemento:
        if _local(hijo) == "RelOp":
            hijos.append(hijo)
        else:
            hijos.extend(_relops_hijos(hijo))
    return hijos


def _kb(valor: Optional[float]) -> str:
    if valor is None:
        return "?"
    if valor >= 1024:
        return f"{valor / 1024:,.0f} MB"  # como SSMS: «899 MB», «3 MB»
    return f"{valor:,.0f} KB"


def _entero(valor: Optional[float]) -> str:
    return "?" if valor is None else f"{valor:,.0f}"


def _advertencia(tipo: str, texto: str, resaltados: Iterable[str] = (), datos: Optional[Dict] = None) -> Dict:
    """Advertencia del XML: su texto (como SSMS), lo que se resalta y, si hace falta, sus valores sueltos."""
    advertencia = {"tipo": tipo, "texto": texto, "resaltados": [r for r in resaltados if r]}
    if datos:
        advertencia["datos"] = datos
    return advertencia


def _memoria(solicitada: Optional[float], concedida: Optional[float], usada: Optional[float],
             tipo: str = "Excessive Grant") -> Dict:
    """Mismo texto que SSMS y Plan Explorer, con los valores resaltados.

    tipo: GrantWarningKind del XML (Excessive Grant, Grant Increase, Used More Than Granted).
    """
    valores = [f"({_kb(solicitada)})", f"({_kb(concedida)})", f"({_kb(usada)})"]
    return _advertencia(
        "memoria",
        f"{tipo}: Requested {valores[0]}, Granted {valores[1]}, Max Used {valores[2]}",
        valores,
        {"tipo": tipo, "solicitada": _kb(solicitada), "concedida": _kb(concedida), "usada": _kb(usada),
         "concedidaKb": concedida},
    )


def _memoria_de(plan: ET.Element) -> Optional[Dict[str, Optional[float]]]:
    """MemoryGrantInfo de la consulta: memoria solicitada, concedida y máxima usada (KB)."""
    info = next((e for e in plan if _local(e) == "MemoryGrantInfo"), None)
    if info is None:
        return None
    return {
        "solicitada": _numero(info, "RequestedMemory"),
        "concedida": _numero(info, "GrantedMemory"),
        "usada": _numero(info, "MaxUsedMemory"),
    }


def _leer_advertencias(warnings: ET.Element) -> List[Dict]:
    """El bloque <Warnings> de SQL Server con los mismos textos que muestran SSMS y Plan Explorer."""
    advertencias = []
    detalles_spill = next(
        (hijo for hijo in warnings if _local(hijo) in {"SortSpillDetails", "HashSpillDetails", "ExchangeSpillDetails"}),
        None,
    )
    for hijo in warnings:
        nombre = _local(hijo)
        atributos = hijo.attrib
        if nombre == "SpillToTempDb":
            texto = (f"Operator used tempdb to spill data during execution with spill level "
                     f"{atributos.get('SpillLevel', '?')} and {atributos.get('SpilledThreadCount', '1')} spilled thread(s)")
            resaltados = [f"spill level {atributos.get('SpillLevel', '?')}"]
            datos = {"nivel": atributos.get("SpillLevel", "?"), "escritas": None}
            if detalles_spill is not None:
                datos["escritas"] = _numero(detalles_spill, "WritesToTempDb")
                operador = _local(detalles_spill).replace("SpillDetails", "")
                escritas = _entero(_numero(detalles_spill, "WritesToTempDb"))
                leidas = _entero(_numero(detalles_spill, "ReadsFromTempDb"))
                texto += (f", {operador} wrote {escritas} pages to and read {leidas} pages from tempdb with granted "
                          f"memory {_numero(detalles_spill, 'GrantedMemoryKb') or 0:.0f}KB and used memory "
                          f"{_numero(detalles_spill, 'UsedMemoryKb') or 0:.0f}KB")
                resaltados += [f"wrote {escritas} pages", f"read {leidas} pages"]
            advertencias.append(_advertencia("spill", texto, resaltados, datos))
        elif nombre == "PlanAffectingConvert":
            expresion = atributos.get("Expression", "")
            problema = atributos.get("ConvertIssue", "").replace(" ", "")
            advertencias.append(_advertencia(
                "conversion",
                f"Convert Issue: {problema} {expresion}",
                # Solo se resalta la conversión implícita; un CONVERT o CAST escrito en la consulta no.
                ["CONVERT_IMPLICIT"] if "CONVERT_IMPLICIT" in expresion else [],
            ))
        elif nombre == "MemoryGrantWarning":
            advertencias.append(_memoria(
                _numero(hijo, "RequestedMemory"), _numero(hijo, "GrantedMemory"), _numero(hijo, "MaxUsedMemory"),
                atributos.get("GrantWarningKind", "Excessive Grant"),
            ))
        elif nombre == "NoJoinPredicate":
            advertencias.append(_advertencia("join", "No Join Predicate", ["No Join Predicate"]))
        elif nombre == "ColumnsWithNoStatistics":
            columnas = [c.attrib.get("Column", "") for c in hijo.iter() if _local(c) == "ColumnReference"]
            advertencias.append(_advertencia("estadisticas", f"Columns With No Statistics: {', '.join(columnas)}", columnas))
        elif nombre not in {"SortSpillDetails", "HashSpillDetails", "ExchangeSpillDetails"}:
            advertencias.append(_advertencia("otra", nombre))
    return advertencias


def _objeto(relop: ET.Element) -> Dict[str, str]:
    for elemento in _propios(relop):
        if _local(elemento) == "Object" and elemento.attrib.get("Table"):
            atributos = elemento.attrib
            esquema = atributos.get("Schema", "")
            completo = ".".join(p for p in (atributos.get("Database"), esquema, atributos["Table"], atributos.get("Index")) if p)
            return {
                "objeto": f"{esquema}.{atributos['Table']}" if esquema else atributos["Table"],
                "indice": atributos.get("Index", ""),
                # Como el «Object» del tooltip de SSMS: [Base].[Esquema].[Tabla].[Índice] [Alias]
                "objetoCompleto": f"{completo} {atributos['Alias']}" if atributos.get("Alias") else completo,
            }
    return {"objeto": "", "indice": "", "objetoCompleto": ""}


def _contadores(relop: ET.Element) -> Dict[str, Optional[float]]:
    """Suma los contadores reales de todos los hilos del operador."""
    hilos = [e for e in _propios(relop) if _local(e) == "RunTimeCountersPerThread"]
    if not hilos:
        return {
            "filasReales": None, "filasLeidas": None, "ejecuciones": None, "lecturas": None,
            "lecturasFisicas": None, "duracionMs": None, "cpuMs": None,
        }

    def valores(nombre: str) -> List[float]:
        return [v for v in (_numero(hilo, nombre) for hilo in hilos) if v is not None]

    def suma(nombre: str) -> Optional[float]:
        encontrados = valores(nombre)
        return sum(encontrados) if encontrados else None

    def maximo(nombre: str) -> Optional[float]:
        encontrados = valores(nombre)
        return max(encontrados) if encontrados else None

    return {
        "filasReales": suma("ActualRows"),
        "filasLeidas": suma("ActualRowsRead"),
        "ejecuciones": suma("ActualExecutions"),
        "lecturas": suma("ActualLogicalReads"),
        "lecturasFisicas": suma("ActualPhysicalReads"),
        # Como SSMS: el tiempo transcurrido es el del hilo que más tardó; el CPU se suma entre hilos.
        "duracionMs": maximo("ActualElapsedms"),
        "cpuMs": suma("ActualCPUms"),
    }


def _columna(referencia: ET.Element) -> str:
    """Columna como la escribe SSMS: [Base].[Esquema].[Tabla].[Columna] as [Alias].[Columna]."""
    atributos = referencia.attrib
    columna = atributos.get("Column", "")
    if atributos.get("Table") and not columna.startswith("["):
        columna = f"[{columna}]"
    completa = ".".join(p for p in (atributos.get("Database"), atributos.get("Schema"), atributos.get("Table")) if p)
    texto = f"{completa}.{columna}" if completa else columna
    if atributos.get("Alias"):
        texto += f" as {atributos['Alias']}.{columna}"
    return texto


def _columnas(elemento: ET.Element) -> str:
    return ", ".join(_columna(c) for c in elemento if _local(c) == "ColumnReference")


def _expresion(elemento: ET.Element) -> str:
    """ScalarString del primer ScalarOperator dentro del elemento."""
    escalar = next((e for e in elemento.iter() if _local(e) == "ScalarOperator" and e.attrib.get("ScalarString")), None)
    return escalar.attrib["ScalarString"] if escalar is not None else ""


_OPERADORES_SEEK = {"EQ": "=", "GT": ">", "GE": ">=", "LT": "<", "LE": "<=", "IS": "=", "ISNOT": "<>", "NE": "<>"}
_TIPOS_SEEK = {"Prefix": "Prefix", "StartRange": "Start", "EndRange": "End"}


def _seek_predicates(elemento: ET.Element) -> str:
    """Seek Predicates como los muestra SSMS: Seek Keys[1]: Prefix: [col] = Scalar Operator(expr)."""
    partes = []
    for numero, claves in enumerate((e for e in elemento.iter() if _local(e) == "SeekKeys"), start=1):
        rangos = []
        for rango in claves:
            tipo = _TIPOS_SEEK.get(_local(rango))
            if not tipo:
                continue
            columnas = next((e for e in rango if _local(e) == "RangeColumns"), None)
            expresiones = next((e for e in rango if _local(e) == "RangeExpressions"), None)
            operador = _OPERADORES_SEEK.get(rango.attrib.get("ScanType", "EQ"), "=")
            nombres = [_columna(c) for c in columnas] if columnas is not None else []
            valores = [e.attrib.get("ScalarString", "") for e in expresiones] if expresiones is not None else []
            comparaciones = ", ".join(f"{c} {operador} Scalar Operator({v})" for c, v in zip(nombres, valores))
            rangos.append(f"{tipo}: {comparaciones}")
        if rangos:
            partes.append(f"Seek Keys[{numero}]: " + ", ".join(rangos))
    return "; ".join(partes)


# Datos del operador que SSMS muestra en su tooltip, con el mismo nombre.
_PREDICADOS = [
    ("SeekPredicates", "Seek Predicates", _seek_predicates),
    ("Predicate", "Predicate", _expresion),
    ("HashKeysBuild", "Hash Keys Build", _columnas),
    ("HashKeysProbe", "Hash Keys Probe", _columnas),
    ("ProbeResidual", "Probe Residual", _expresion),
    ("OuterReferences", "Outer References", _columnas),
    ("InnerSideJoinColumns", "Inner Side Join Columns", _columnas),
    ("OuterSideJoinColumns", "Outer Side Join Columns", _columnas),
    ("Residual", "Residual", _expresion),
]


def _valores_definidos(elemento: ET.Element) -> str:
    """Defined Values como SSMS: «[Expr1004] = Scalar Operator(CONVERT_IMPLICIT(...))» o solo las columnas."""
    partes = []
    for definido in elemento:
        if _local(definido) != "DefinedValue":
            continue
        columnas = [_columna(c) for c in definido if _local(c) == "ColumnReference"]
        escalar = next((e for e in definido if _local(e) == "ScalarOperator"), None)
        if escalar is not None and escalar.attrib.get("ScalarString"):
            # Las columnas calculadas van entre corchetes, como en SSMS: [Expr1002] = Scalar Operator(...)
            columnas = [c if c.startswith("[") else f"[{c}]" for c in columnas]
            partes.append(f"{', '.join(columnas)} = Scalar Operator({escalar.attrib['ScalarString']})")
        else:
            partes.extend(columnas)
    return ", ".join(partes)


def _orden(elemento: ET.Element) -> str:
    """Order By como SSMS: [Tabla].[Columna] Ascending."""
    return ", ".join(
        f"{_columna(c)} {'Ascending' if columna.attrib.get('Ascending', 'true') == 'true' else 'Descending'}"
        for columna in elemento if _local(columna) == "OrderByColumn"
        for c in columna if _local(c) == "ColumnReference"
    )


_PREDICADOS += [
    ("OrderBy", "Order By", _orden),
    ("GroupBy", "Group By", _columnas),
    ("DefinedValues", "Defined Values", _valores_definidos),
]


def _predicados(relop: ET.Element) -> List[Dict]:
    """Predicados, columnas y expresiones del operador (Seek Predicates, Defined Values...) tal cual el XML."""
    encontrados = []
    for elemento in _propios(relop):
        for etiqueta, nombre, leer in _PREDICADOS:
            if _local(elemento) == etiqueta:
                texto = leer(elemento)
                if texto:
                    encontrados.append({"nombre": nombre, "texto": texto})
    salida = next((e for e in relop if _local(e) == "OutputList"), None)
    if salida is not None and len(salida):
        encontrados.append({"nombre": "Output List", "texto": _columnas(salida)})
    return encontrados


def _decimal(valor: Optional[float]) -> str:
    """Número como lo escribe SSMS: sin ceros de más (0.0032831, 1, 1.11156)."""
    if valor is None:
        return ""
    texto = f"{valor:.7f}".rstrip("0").rstrip(".")
    return texto if texto not in ("", "-0") else "0"


def _propiedades(relop: ET.Element, propio: float, costo_pct: float, contadores: Dict) -> List[List[str]]:
    """
    Datos del operador con los nombres y el orden del recuadro de SQL Server (SSMS), tomados del XML.
    Solo los que el plan trae (un plan estimado no tiene los «Actual»).
    """
    atributos = relop.attrib
    hilos = [e for e in _propios(relop) if _local(e) == "RunTimeCountersPerThread"]
    almacenamiento = next((e for e in _propios(relop) if e.attrib.get("Storage")), None)
    ordenado = next((e for e in _propios(relop) if "Ordered" in e.attrib), None)

    def suma(nombre: str) -> Optional[float]:
        valores = [v for v in (_numero(h, nombre) for h in hilos) if v is not None]
        return sum(valores) if valores else None

    filas_estimadas = _numero(relop, "EstimateRows")
    ejecuciones_estimadas = 1 + (_numero(relop, "EstimateRebinds") or 0) + (_numero(relop, "EstimateRewinds") or 0)
    tamano = _numero(relop, "AvgRowSize")
    filas = [
        ["Physical Operation", atributos.get("PhysicalOp", "")],
        ["Logical Operation", atributos.get("LogicalOp", "")],
        ["Actual Execution Mode", hilos[0].attrib.get("ActualExecutionMode", "") if hilos else ""],
        ["Estimated Execution Mode", atributos.get("EstimatedExecutionMode", "")],
        ["Storage", almacenamiento.attrib["Storage"] if almacenamiento is not None else ""],
        ["Number of Rows Read", _decimal(contadores.get("filasLeidas"))],
        ["Actual Number of Rows for All Executions", _decimal(contadores.get("filasReales"))],
        ["Actual Number of Batches", _decimal(suma("Batches"))],
        ["Actual Logical Reads", _decimal(contadores.get("lecturas"))],
        ["Actual Physical Reads", _decimal(contadores.get("lecturasFisicas"))],
        ["Actual Elapsed Time (ms)", _decimal(contadores.get("duracionMs"))],
        ["Actual Elapsed CPU Time (ms)", _decimal(contadores.get("cpuMs"))],
        ["Estimated I/O Cost", _decimal(_numero(relop, "EstimateIO"))],
        ["Estimated Operator Cost", f"{_decimal(propio)} ({round(costo_pct):.0f}%)"],
        ["Estimated CPU Cost", _decimal(_numero(relop, "EstimateCPU"))],
        ["Estimated Subtree Cost", _decimal(_numero(relop, "EstimatedTotalSubtreeCost"))],
        ["Number of Executions", _decimal(contadores.get("ejecuciones"))],
        ["Estimated Number of Executions", _decimal(ejecuciones_estimadas)],
        ["Estimated Number of Rows for All Executions",
         _decimal(filas_estimadas * ejecuciones_estimadas if filas_estimadas is not None else None)],
        ["Estimated Number of Rows Per Execution", _decimal(filas_estimadas)],
        ["Estimated Number of Rows to be Read", _decimal(_numero(relop, "EstimatedRowsRead"))],
        ["Estimated Row Size", f"{tamano:.0f} B" if tamano is not None else ""],
        ["Actual Rebinds", _decimal(suma("ActualRebinds"))],
        ["Actual Rewinds", _decimal(suma("ActualRewinds"))],
        # El XML lo escribe «true/false» o «1/0»; SSMS lo muestra como True/False.
        ["Ordered", ("True" if ordenado.attrib["Ordered"].lower() in ("1", "true") else "False")
         if ordenado is not None else ""],
        ["Node ID", atributos.get("NodeId", "")],
    ]
    return [fila for fila in filas if fila[1]]


def _parametros(plan: ET.Element) -> List[Dict]:
    """ParameterList: cada parámetro con su tipo y sus valores al compilar y al ejecutar."""
    lista = next((e for e in plan if _local(e) == "ParameterList"), None)
    if lista is None:
        return []
    return [
        {
            "nombre": c.attrib.get("Column", ""),
            "tipo": c.attrib.get("ParameterDataType", ""),
            "valorCompilado": c.attrib.get("ParameterCompiledValue"),
            "valorEjecucion": c.attrib.get("ParameterRuntimeValue"),
        }
        for c in lista
        if _local(c) == "ColumnReference"
    ]


def _detalle_indices_faltantes(plan: ET.Element) -> List[Dict]:
    """MissingIndexes: tabla, columnas por uso e impacto, con el CREATE INDEX que sugiere SSMS."""
    indices = []
    for grupo in (e for e in plan.iter() if _local(e) == "MissingIndexGroup"):
        for indice in (e for e in grupo if _local(e) == "MissingIndex"):
            columnas = {"EQUALITY": [], "INEQUALITY": [], "INCLUDE": []}
            for conjunto in (e for e in indice if _local(e) == "ColumnGroup"):
                columnas.setdefault(conjunto.attrib.get("Usage", ""), []).extend(
                    c.attrib.get("Name", "") for c in conjunto if _local(c) == "Column"
                )
            tabla = ".".join(p for p in (indice.attrib.get("Schema"), indice.attrib.get("Table")) if p)
            claves = columnas["EQUALITY"] + columnas["INEQUALITY"]
            sentencia = f"CREATE NONCLUSTERED INDEX [<Name of Missing Index, sysname,>]\nON {tabla} ({', '.join(claves)})"
            if columnas["INCLUDE"]:
                sentencia += f"\nINCLUDE ({', '.join(columnas['INCLUDE'])})"
            indices.append({
                "impacto": _numero(grupo, "Impact"),
                "base": indice.attrib.get("Database", ""),
                "tabla": tabla,
                "igualdad": columnas["EQUALITY"],
                "desigualdad": columnas["INEQUALITY"],
                "incluidas": columnas["INCLUDE"],
                "sentencia": sentencia,
            })
    return indices


def _nodos_de(relop: ET.Element, padre: str, costo_total: float, nodos: List[Dict]) -> None:
    hijos = _relops_hijos(relop)
    subarbol = _numero(relop, "EstimatedTotalSubtreeCost") or 0.0
    costo_hijos = sum(_numero(hijo, "EstimatedTotalSubtreeCost") or 0.0 for hijo in hijos)
    propio = max(subarbol - costo_hijos, 0.0)
    advertencias = []
    for elemento in relop:
        if _local(elemento) == "Warnings":
            advertencias.extend(_leer_advertencias(elemento))
    ejecuciones_estimadas = 1 + (_numero(relop, "EstimateRebinds") or 0) + (_numero(relop, "EstimateRewinds") or 0)
    contadores = _contadores(relop)
    costo_pct = round(propio / costo_total * 100, 1) if costo_total > 0 else 0.0
    fisica, logica = relop.attrib.get("PhysicalOp", ""), relop.attrib.get("LogicalOp", "")
    # Búsqueda en el índice clúster para traer columnas que faltan (Lookup="true"): SSMS y Plan Explorer
    # la muestran como Key Lookup, aunque el XML la guarde como Clustered Index Seek.
    if fisica == "Clustered Index Seek" and any(
        _local(e) == "IndexScan" and e.attrib.get("Lookup", "").lower() in ("true", "1") for e in relop
    ):
        fisica = logica = "Key Lookup"
    nodos.append({
        "id": relop.attrib.get("NodeId", "?"),
        "padre": padre,
        "fisica": fisica,
        "logica": logica,
        **_objeto(relop),
        "costoPct": costo_pct,
        "_propio": propio,
        "filasEstimadas": (_numero(relop, "EstimateRows") or 0) * ejecuciones_estimadas,
        **contadores,
        "advertencias": advertencias,
        "predicados": _predicados(relop),
        # Recuadro del operador: todos los datos del XML con los nombres y el orden de SQL Server.
        "propiedades": _propiedades(relop, propio, costo_pct, contadores),
    })
    for hijo in hijos:
        _nodos_de(hijo, relop.attrib.get("NodeId", "?"), costo_total, nodos)


def _costos_sobre_la_suma(nodos: List[Dict]) -> None:
    """
    % de costo de cada operador sobre la suma de los costos propios de todos (como SSMS y Plan Explorer),
    no sobre el costo de la consulta: con un «row goal» (IF EXISTS, TOP, OR EXISTS) un hijo puede costar más
    que su padre y la suma pasa del costo de la consulta (un Scan salía con 100 % en vez de 50 %).
    """
    total = sum(n.get("_propio", 0.0) for n in nodos)
    for nodo in nodos:
        propio = nodo.pop("_propio", None)
        if propio is None or total <= 0:
            continue
        nodo["costoPct"] = round(propio / total * 100, 1)
        for fila in nodo.get("propiedades", []):
            if fila[0] == "Estimated Operator Cost":
                fila[1] = f"{_decimal(propio)} ({round(nodo['costoPct']):.0f}%)"
        for fila in nodo.get("propiedades", []):
            if fila[0] in ("Physical Operation", "Logical Operation") and nodo["fisica"] == "Key Lookup":
                fila[1] = "Key Lookup"


def _indices_faltantes(plan: ET.Element) -> List[Dict]:
    grupos = [e for e in plan.iter() if _local(e) == "MissingIndexGroup"]
    if not grupos:
        return []
    # Se muestra tal cual el XML, pero sin resaltar: en Reportes solo se consulta, no se crean índices.
    return [_advertencia("indice_faltante", "Missing indexes found.")]


def _completar_filas_reales(nodos: List[Dict]) -> None:
    """Compute Scalar y similares no traen contadores: muestran las filas de su primer hijo."""
    if not any(n["filasReales"] is not None for n in nodos):
        return  # plan estimado: no hay filas reales que mostrar
    for nodo in reversed(nodos[1:]):  # los hijos van después del padre: se recorren primero
        if nodo["filasReales"] is None:
            hijo = next((n for n in nodos if n["padre"] == nodo["id"]), None)
            if hijo is not None:
                nodo["filasReales"] = hijo["filasReales"]


def _suma_estimada(plan: ET.Element, atributo: str) -> float:
    """Costo estimado de CPU o de E/S de todos los operadores de la sentencia."""
    total = 0.0
    for relop in (e for e in plan.iter() if _local(e) == "RelOp"):
        ejecuciones = 1 + (_numero(relop, "EstimateRebinds") or 0) + (_numero(relop, "EstimateRewinds") or 0)
        total += (_numero(relop, atributo) or 0) * ejecuciones
    return total


def _filas_reales_de(superiores: List[ET.Element]) -> Optional[float]:
    """Filas reales que devuelve la sentencia: las del primer operador (un INSERT devuelve 0)."""
    if not superiores:
        return None
    return _contadores(superiores[0])["filasReales"]


# Sentencias con plan propio: las consultas (StmtSimple) y la condición de cada IF (StmtCond).
SENTENCIAS = {"StmtSimple", "StmtCond", "StmtCursor"}


def plan_de_sentencia(sentencia: ET.Element) -> Optional[ET.Element]:
    """
    QueryPlan propio de la sentencia; en un IF, el de su condición (sin los bloques THEN / ELSE);
    en un cursor (DECLARE CURSOR / OPEN / FETCH), el de su consulta (CursorPlan > Operation > QueryPlan).
    """
    if _local(sentencia) == "StmtCond":
        condicion = next((e for e in sentencia if _local(e) == "Condition"), None)
        return next((e for e in condicion if _local(e) == "QueryPlan"), None) if condicion is not None else None
    if _local(sentencia) == "StmtCursor":
        cursor = next((e for e in sentencia if _local(e) == "CursorPlan"), None)
        operaciones = [e for e in cursor if _local(e) == "Operation"] if cursor is not None else []
        return next((p for o in operaciones for p in o if _local(p) == "QueryPlan"), None)
    return next((e for e in sentencia if _local(e) == "QueryPlan"), None)


def construir_diagrama(contenido: Union[str, bytes]) -> List[Dict]:
    """Devuelve una lista de sentencias, cada una con sus nodos listos para dibujar."""
    raiz = ET.fromstring(contenido)
    sentencias = []
    numero = 0
    for sentencia in raiz.iter():
        if _local(sentencia) not in SENTENCIAS:
            continue
        numero += 1  # mismo orden que usan los hallazgos («consulta N»)
        plan = plan_de_sentencia(sentencia)
        if plan is None:
            continue
        tiempos = next((e for e in plan if _local(e) == "QueryTimeStats"), None)
        superiores = _relops_hijos(plan)
        costo_total = _numero(sentencia, "StatementSubTreeCost") or sum(
            _numero(r, "EstimatedTotalSubtreeCost") or 0.0 for r in superiores
        )
        advertencias = []
        for elemento in plan:
            if _local(elemento) == "Warnings":
                advertencias.extend(_leer_advertencias(elemento))
        advertencias.extend(_indices_faltantes(plan))

        # La condición de un IF llega como «COND»: se muestra como IF, igual que en Plan Explorer.
        tipo_xml = sentencia.attrib.get("StatementType", "SELECT")
        tipo = ("IF" if _local(sentencia) == "StmtCond"
                # «COND WITH QUERY» (IF con subconsulta) se muestra completo, como en Plan Explorer.
                else tipo_xml if tipo_xml.upper().startswith("COND WITH QUERY")
                else tipo_xml.split(" ")[0])
        nodos = [{
            "id": "raiz", "padre": None, "fisica": tipo, "logica": tipo, "objeto": "", "indice": "",
            "costoPct": 0.0, "filasEstimadas": _numero(sentencia, "StatementEstRows"),
            "filasReales": None, "filasLeidas": None, "ejecuciones": None, "lecturas": None,
            "lecturasFisicas": None, "duracionMs": None, "cpuMs": None,
            "advertencias": advertencias, "predicados": [],
        }]
        for relop in superiores:
            _nodos_de(relop, "raiz", costo_total, nodos)
        _costos_sobre_la_suma(nodos)
        _completar_filas_reales(nodos)

        sentencias.append({
            "numero": numero,
            "tipo": tipo,
            "texto": re.sub(r"\s+", " ", sentencia.attrib.get("StatementText", "")).strip(),
            # El código tal cual viene en el XML (con saltos de línea y comentarios): panel «Text Data».
            "codigo": sentencia.attrib.get("StatementText", "").replace("\r\n", "\n").strip("\n"),
            "costo": costo_total,
            "duracionMs": _numero(tiempos, "ElapsedTime"),
            "cpuMs": _numero(tiempos, "CpuTime"),
            # Columnas de la grilla de sentencias de Plan Explorer, tal como vienen en el XML.
            "compilacionMs": _numero(plan, "CompileTime"),
            "udfDuracionMs": _numero(tiempos, "UdfElapsedTime"),
            "udfCpuMs": _numero(tiempos, "UdfCpuTime"),
            "costoCpu": _suma_estimada(plan, "EstimateCPU"),
            "costoIo": _suma_estimada(plan, "EstimateIO"),
            "lecturas": sum(n["lecturas"] or 0 for n in nodos[1:]) if any(n["lecturas"] is not None for n in nodos) else None,
            "filasEstimadas": _numero(sentencia, "StatementEstRows"),
            "filasReales": _filas_reales_de(superiores),
            "parametros": _parametros(plan),
            # Memoria de la consulta (MemoryGrantInfo), en KB: para detectar reservas desproporcionadas.
            "memoria": _memoria_de(plan),
            "indicesFaltantes": _detalle_indices_faltantes(plan),
            "nodos": nodos,
        })
    return sentencias
