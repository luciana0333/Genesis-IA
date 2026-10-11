"""Árbol del plan de ejecución para dibujarlo (estilo SQL Sentry Plan Explorer).

Por cada sentencia del plan devuelve sus datos generales (texto, costo, duración,
CPU) y sus operadores con el padre de cada uno, el porcentaje de costo propio,
las filas y las advertencias que SQL Server dejó en el XML (spills, conversiones,
memoria concedida de más...). El primer nodo de cada sentencia es la propia
sentencia (SELECT, INSERT...), como en el diagrama de SSMS y Plan Explorer.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Union

_CONVERSION_IMPLICITA = re.compile(r"CONVERT_IMPLICIT\((?:[^()]|\([^()]*\))*\)")


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
        megas = valor / 1024
        return f"{megas:,.0f} MB" if megas >= 100 else f"{megas:,.1f} MB"
    return f"{valor:,.0f} KB"


def _entero(valor: Optional[float]) -> str:
    return "?" if valor is None else f"{valor:,.0f}"


def _advertencia(tipo: str, texto: str, resaltados: Iterable[str] = ()) -> Dict:
    return {"tipo": tipo, "texto": texto, "resaltados": [r for r in resaltados if r]}


def _memoria(solicitada: Optional[float], concedida: Optional[float], usada: Optional[float]) -> Dict:
    """Mismo texto que SSMS y Plan Explorer, con los valores resaltados."""
    valores = [f"({_kb(solicitada)})", f"({_kb(concedida)})", f"({_kb(usada)})"]
    return _advertencia(
        "memoria",
        f"Excessive Grant: Requested {valores[0]}, Granted {valores[1]}, Max Used {valores[2]}",
        valores,
    )


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
            if detalles_spill is not None:
                operador = _local(detalles_spill).replace("SpillDetails", "")
                escritas = _entero(_numero(detalles_spill, "WritesToTempDb"))
                leidas = _entero(_numero(detalles_spill, "ReadsFromTempDb"))
                texto += (f", {operador} wrote {escritas} pages to and read {leidas} pages from tempdb with granted "
                          f"memory {_numero(detalles_spill, 'GrantedMemoryKb') or 0:.0f}KB and used memory "
                          f"{_numero(detalles_spill, 'UsedMemoryKb') or 0:.0f}KB")
                resaltados += [f"wrote {escritas} pages", f"read {leidas} pages"]
            advertencias.append(_advertencia("spill", texto, resaltados))
        elif nombre == "PlanAffectingConvert":
            expresion = atributos.get("Expression", "")
            problema = atributos.get("ConvertIssue", "").replace(" ", "")
            advertencias.append(_advertencia(
                "conversion",
                f"Convert Issue: {problema} {expresion}",
                ["CONVERT_IMPLICIT" if "CONVERT_IMPLICIT" in expresion else expresion],
            ))
        elif nombre == "MemoryGrantWarning":
            advertencias.append(_memoria(
                _numero(hijo, "RequestedMemory"), _numero(hijo, "GrantedMemory"), _numero(hijo, "MaxUsedMemory"),
            ))
        elif nombre == "NoJoinPredicate":
            advertencias.append(_advertencia("join", "No Join Predicate", ["No Join Predicate"]))
        elif nombre == "ColumnsWithNoStatistics":
            columnas = [c.attrib.get("Column", "") for c in hijo.iter() if _local(c) == "ColumnReference"]
            advertencias.append(_advertencia("estadisticas", f"Columns With No Statistics: {', '.join(columnas)}", columnas))
        elif nombre not in {"SortSpillDetails", "HashSpillDetails", "ExchangeSpillDetails"}:
            advertencias.append(_advertencia("otra", nombre))
    return advertencias


def _conversiones_implicitas(relop: ET.Element) -> List[str]:
    expresiones = []
    for elemento in _propios(relop):
        expresiones.extend(_CONVERSION_IMPLICITA.findall(elemento.attrib.get("ScalarString", "")))
    return list(dict.fromkeys(expresiones))


def _objeto(relop: ET.Element) -> Dict[str, str]:
    for elemento in _propios(relop):
        if _local(elemento) == "Object" and elemento.attrib.get("Table"):
            atributos = elemento.attrib
            esquema = atributos.get("Schema", "")
            return {
                "objeto": f"{esquema}.{atributos['Table']}" if esquema else atributos["Table"],
                "indice": atributos.get("Index", ""),
            }
    return {"objeto": "", "indice": ""}


def _contadores(relop: ET.Element) -> Dict[str, Optional[float]]:
    """Suma los contadores reales de todos los hilos del operador."""
    hilos = [e for e in _propios(relop) if _local(e) == "RunTimeCountersPerThread"]
    if not hilos:
        return {"filasReales": None, "ejecuciones": None, "lecturas": None}

    def suma(nombre: str) -> Optional[float]:
        valores = [_numero(hilo, nombre) for hilo in hilos]
        valores = [v for v in valores if v is not None]
        return sum(valores) if valores else None

    return {"filasReales": suma("ActualRows"), "ejecuciones": suma("ActualExecutions"), "lecturas": suma("ActualLogicalReads")}


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
    nodos.append({
        "id": relop.attrib.get("NodeId", "?"),
        "padre": padre,
        "fisica": relop.attrib.get("PhysicalOp", ""),
        "logica": relop.attrib.get("LogicalOp", ""),
        **_objeto(relop),
        "costoPct": round(propio / costo_total * 100, 1) if costo_total > 0 else 0.0,
        "filasEstimadas": (_numero(relop, "EstimateRows") or 0) * ejecuciones_estimadas,
        **_contadores(relop),
        "advertencias": advertencias,
        "conversiones": _conversiones_implicitas(relop),
    })
    for hijo in hijos:
        _nodos_de(hijo, relop.attrib.get("NodeId", "?"), costo_total, nodos)


def _memoria_de_mas(plan: ET.Element) -> List[Dict]:
    """Memoria concedida que duplica (o más) la usada, cuando SQL Server no dejó su advertencia."""
    info = next((e for e in plan if _local(e) == "MemoryGrantInfo"), None)
    concedida, usada = _numero(info, "GrantedMemory"), _numero(info, "MaxUsedMemory")
    if not concedida or usada is None or concedida < 2 * max(usada, 1):
        return []
    return [_memoria(_numero(info, "RequestedMemory"), concedida, usada)]


def _indices_faltantes(plan: ET.Element) -> List[Dict]:
    grupos = [e for e in plan.iter() if _local(e) == "MissingIndexGroup"]
    if not grupos:
        return []
    return [_advertencia("indice_faltante", "Missing indexes found.", ["Missing indexes found."])]


def _completar_filas_reales(nodos: List[Dict]) -> None:
    """Compute Scalar y similares no traen contadores: muestran las filas de su primer hijo."""
    if not any(n["filasReales"] is not None for n in nodos):
        return  # plan estimado: no hay filas reales que mostrar
    for nodo in reversed(nodos[1:]):  # los hijos van después del padre: se recorren primero
        if nodo["filasReales"] is None:
            hijo = next((n for n in nodos if n["padre"] == nodo["id"]), None)
            if hijo is not None:
                nodo["filasReales"] = hijo["filasReales"]


def construir_diagrama(contenido: Union[str, bytes]) -> List[Dict]:
    """Devuelve una lista de sentencias, cada una con sus nodos listos para dibujar."""
    raiz = ET.fromstring(contenido)
    sentencias = []
    numero = 0
    for sentencia in raiz.iter():
        if _local(sentencia) != "StmtSimple":
            continue
        numero += 1  # mismo orden que usan los hallazgos («consulta N»)
        plan = next((e for e in sentencia if _local(e) == "QueryPlan"), None)
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
        if not any(a["tipo"] == "memoria" for a in advertencias):
            advertencias.extend(_memoria_de_mas(plan))
        advertencias.extend(_indices_faltantes(plan))

        tipo = sentencia.attrib.get("StatementType", "SELECT").split(" ")[0]
        nodos = [{
            "id": "raiz", "padre": None, "fisica": tipo, "logica": tipo, "objeto": "", "indice": "",
            "costoPct": 0.0, "filasEstimadas": _numero(sentencia, "StatementEstRows"),
            "filasReales": None, "ejecuciones": None, "lecturas": None,
            "advertencias": advertencias, "conversiones": [],
        }]
        for relop in superiores:
            _nodos_de(relop, "raiz", costo_total, nodos)
        _completar_filas_reales(nodos)

        sentencias.append({
            "numero": numero,
            "tipo": tipo,
            "texto": re.sub(r"\s+", " ", sentencia.attrib.get("StatementText", "")).strip(),
            "costo": costo_total,
            "duracionMs": _numero(tiempos, "ElapsedTime"),
            "cpuMs": _numero(tiempos, "CpuTime"),
            "nodos": nodos,
        })
    return sentencias
