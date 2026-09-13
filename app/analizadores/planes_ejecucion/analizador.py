"""Analisis conservador de planes de ejecucion reales en formato XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Union

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.analizadores.planes_ejecucion.modelos import MemoriaPlan, OperadorPlan


@dataclass(frozen=True)
class UmbralesPlan:
    lecturas_logicas_altas: float = 100000
    diferencia_filas_alta: float = 10
    memoria_sobrante_factor: float = 2


def _nombre_local(elemento: ET.Element) -> str:
    return elemento.tag.rsplit("}", 1)[-1]


def _numero(atributos: dict, nombre: str) -> Optional[float]:
    valor = atributos.get(nombre)
    if valor in (None, "", "NULL"):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _atributo(elemento: ET.Element, *nombres: str) -> Optional[float]:
    for nombre in nombres:
        valor = _numero(elemento.attrib, nombre)
        if valor is not None:
            return valor
    return None


def _descendientes(elemento: ET.Element, nombre: str) -> Iterable[ET.Element]:
    return (hijo for hijo in elemento.iter() if _nombre_local(hijo) == nombre)


def _elementos_del_operador(elemento: ET.Element) -> Iterable[ET.Element]:
    """Recorre un RelOp sin absorber los subarboles de sus operadores hijos."""
    for hijo in elemento:
        if _nombre_local(hijo) == "RelOp":
            continue
        yield hijo
        yield from _elementos_del_operador(hijo)


def _primer_atributo_descendiente(elemento: ET.Element, nombre: str, *atributos: str) -> Optional[float]:
    for descendiente in _elementos_del_operador(elemento):
        if _nombre_local(descendiente) != nombre:
            continue
        valor = _atributo(descendiente, *atributos)
        if valor is not None:
            return valor
    return None


def _tiene_conversion_implicita(elemento: ET.Element) -> bool:
    return any(
        hijo.attrib.get("Implicit", "").lower() in {"1", "true"}
        for hijo in _elementos_del_operador(elemento)
        if _nombre_local(hijo) == "Convert"
    )


def _tiene_spill(elemento: ET.Element) -> bool:
    for hijo in _elementos_del_operador(elemento):
        nombre = _nombre_local(hijo).lower()
        if "spill" in nombre or "spill" in " ".join(hijo.attrib).lower():
            return True
        if hijo.attrib.get("SpillOccurred", "").lower() in {"1", "true"}:
            return True
    return False


def _objeto_operador(elemento: ET.Element) -> str:
    for descendiente in _elementos_del_operador(elemento):
        if _nombre_local(descendiente) != "Object":
            continue
        partes = [descendiente.attrib.get(nombre, "") for nombre in ("Database", "Schema", "Table", "Index")]
        referencia = ".".join(parte for parte in partes if parte)
        if referencia:
            return referencia
    return ""


def _extraer_operadores(raiz: ET.Element) -> List[OperadorPlan]:
    operadores = []

    def recorrer(elemento: ET.Element, profundidad: int) -> None:
        if _nombre_local(elemento) == "RelOp":
            runtime = next(
                (hijo for hijo in _elementos_del_operador(elemento) if _nombre_local(hijo) == "RunTimeCountersPerThread"),
                None,
            )
            operadores.append(OperadorPlan(
                nodo_id=elemento.attrib.get("NodeId", "?"),
                operacion_fisica=elemento.attrib.get("PhysicalOp", ""),
                operacion_logica=elemento.attrib.get("LogicalOp", ""),
                estimacion_filas=_atributo(elemento, "EstimateRows"),
                filas_reales=_atributo(runtime, "ActualRows") if runtime is not None else _primer_atributo_descendiente(elemento, "RunTimeCountersPerThread", "ActualRows"),
                filas_leidas=_atributo(runtime, "ActualRowsRead") if runtime is not None else _primer_atributo_descendiente(elemento, "RunTimeCountersPerThread", "ActualRowsRead"),
                lecturas_logicas=_atributo(runtime, "ActualLogicalReads") if runtime is not None else _primer_atributo_descendiente(elemento, "RunTimeCountersPerThread", "ActualLogicalReads"),
                costo_subarbol=_atributo(elemento, "EstimatedTotalSubtreeCost"),
                objeto=_objeto_operador(elemento),
                profundidad=profundidad,
                tiene_spill=_tiene_spill(elemento),
                tiene_conversion_implicita=_tiene_conversion_implicita(elemento),
            ))
        for hijo in elemento:
            recorrer(hijo, profundidad + (1 if _nombre_local(elemento) == "RelOp" else 0))

    recorrer(raiz, 0)
    return operadores


def _extraer_memoria(raiz: ET.Element) -> Optional[MemoriaPlan]:
    memoria = next(iter(_descendientes(raiz, "MemoryGrantInfo")), None)
    if memoria is None:
        return None
    return MemoriaPlan(
        memoria_solicitada_kb=_atributo(memoria, "SerialDesiredMemory", "RequestedMemory"),
        memoria_concedida_kb=_atributo(memoria, "GrantedMemory"),
        memoria_maxima_utilizada_kb=_atributo(memoria, "MaxUsedMemory"),
    )


def _hallazgo(regla: str, severidad: Severidad, mensaje: str) -> Hallazgo:
    return Hallazgo(
        linea=1,
        origen=OrigenAnalisis.PLAN_EJECUCION,
        severidad=severidad,
        regla=regla,
        mensaje=mensaje,
    )


def _revisar_operador(operador: OperadorPlan, umbrales: UmbralesPlan) -> List[Hallazgo]:
    hallazgos = []
    referencia = operador.objeto or f"nodo {operador.nodo_id}"
    if operador.tiene_conversion_implicita:
        hallazgos.append(_hallazgo(
            "CONVERSION_IMPLICITA",
            Severidad.ALTO,
            f"El operador {referencia} contiene una conversion implicita que puede impedir el uso eficiente de un indice.",
        ))
    if operador.tiene_spill:
        hallazgos.append(_hallazgo(
            "SPILL_TEMPDB",
            Severidad.ALTO,
            f"El operador {referencia} reporta un spill hacia TempDB; revise memoria, cardinalidad e indices.",
        ))
    if operador.operacion_fisica.lower() == "table scan":
        hallazgos.append(_hallazgo(
            "TABLE_SCAN",
            Severidad.MEDIO,
            f"Se detecto Table Scan en {referencia}; confirme si la lectura completa de la tabla es necesaria.",
        ))
    if operador.lecturas_logicas is not None and operador.lecturas_logicas >= umbrales.lecturas_logicas_altas:
        hallazgos.append(_hallazgo(
            "LECTURAS_LOGICAS_ELEVADAS",
            Severidad.ALTO,
            f"El operador {referencia} registra {operador.lecturas_logicas:.0f} lecturas logicas, por encima del umbral configurado.",
        ))
    if (
        operador.estimacion_filas
        and operador.filas_reales
        and operador.estimacion_filas > 0
        and operador.filas_reales / operador.estimacion_filas >= umbrales.diferencia_filas_alta
    ):
        hallazgos.append(_hallazgo(
            "SOBREESTIMACION_FILAS",
            Severidad.ALTO,
            f"El operador {referencia} produjo {operador.filas_reales:.0f} filas frente a {operador.estimacion_filas:.0f} estimadas; revise estadisticas y cardinalidad.",
        ))
    return hallazgos


def analizar_plan_ejecucion(
    contenido: Union[str, bytes],
    umbrales: Optional[UmbralesPlan] = None,
) -> Tuple[List[Hallazgo], List[OperadorPlan], Optional[MemoriaPlan]]:
    """Analiza un plan XML real y devuelve hallazgos, operadores y memoria."""
    raiz = ET.fromstring(contenido)
    configuracion = umbrales or UmbralesPlan()
    operadores = _extraer_operadores(raiz)
    memoria = _extraer_memoria(raiz)
    hallazgos = []
    for operador in operadores:
        hallazgos.extend(_revisar_operador(operador, configuracion))
    if (
        memoria
        and memoria.memoria_concedida_kb
        and memoria.memoria_maxima_utilizada_kb
        and memoria.memoria_maxima_utilizada_kb > 0
        and memoria.memoria_concedida_kb >= memoria.memoria_maxima_utilizada_kb * configuracion.memoria_sobrante_factor
    ):
        hallazgos.append(_hallazgo(
            "MEMORIA_CONCEDIDA_SOBREDIMENSIONADA",
            Severidad.MEDIO,
            f"La memoria concedida ({memoria.memoria_concedida_kb:.0f} KB) supera ampliamente la maxima utilizada ({memoria.memoria_maxima_utilizada_kb:.0f} KB).",
        ))
    return hallazgos, operadores, memoria