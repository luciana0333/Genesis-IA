"""Análisis conservador de planes de ejecución reales en formato XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Union

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.analizadores.planes_ejecucion.modelos import MemoriaPlan, OperadorPlan
from app.analizadores.planes_ejecucion.diagrama import SENTENCIAS, plan_de_sentencia


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


def _tiempo_real(relop: ET.Element, atributo: str, combinar) -> Optional[float]:
    """Tiempo real del operador entre todos sus hilos (max para la duración, suma para el CPU)."""
    valores = [
        _atributo(hijo, atributo) for hijo in _elementos_del_operador(relop)
        if _nombre_local(hijo) == "RunTimeCountersPerThread"
    ]
    valores = [v for v in valores if v is not None]
    return combinar(valores) if valores else None


def _extraer_operadores(raiz: ET.Element) -> List[OperadorPlan]:
    operadores = []
    consulta = 0

    def recorrer(elemento: ET.Element, profundidad: int) -> None:
        nonlocal consulta
        if _nombre_local(elemento) in SENTENCIAS:  # misma numeración que el diagrama (IF incluido)
            consulta += 1
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
                consulta=max(consulta, 1),
                duracion_ms=_tiempo_real(elemento, "ActualElapsedms", max),
                cpu_ms=_tiempo_real(elemento, "ActualCPUms", sum),
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


@dataclass(frozen=True)
class _Observacion:
    regla: str
    severidad: Severidad
    hecho: str    # qué se encontró, sin el nodo (permite agrupar la misma tabla)
    accion: str   # qué hacer
    operador: OperadorPlan


def _revisar_operador(operador: OperadorPlan, umbrales: UmbralesPlan) -> List[_Observacion]:
    observaciones = []
    referencia = operador.objeto or "un operador sin tabla"

    def agregar(regla: str, severidad: Severidad, hecho: str, accion: str) -> None:
        observaciones.append(_Observacion(regla, severidad, hecho, accion, operador))

    if operador.tiene_conversion_implicita:
        agregar(
            "CONVERSION_IMPLICITA", Severidad.ALTO,
            f"En {referencia} SQL Server convierte un tipo de dato a otro por su cuenta (conversión implícita), "
            f"lo que puede impedir usar el índice.",
            "Compare columnas y variables del mismo tipo.",
        )
    if operador.tiene_spill:
        agregar(
            "SPILL_TEMPDB", Severidad.ALTO,
            f"En {referencia} la memoria no alcanzó y SQL Server tuvo que usar el disco (TempDB).",
            "Revise que las estadísticas estén actualizadas y que existan los índices necesarios.",
        )
    if operador.operacion_fisica.lower() == "table scan":
        agregar(
            "TABLE_SCAN", Severidad.MEDIO,
            f"Se lee la tabla {referencia} completa con un Table Scan.",
            "Confirme si es necesario; si la consulta filtra datos, cree un índice sobre las columnas del filtro.",
        )
    if operador.lecturas_logicas is not None and operador.lecturas_logicas >= umbrales.lecturas_logicas_altas:
        agregar(
            "LECTURAS_LOGICAS_ELEVADAS", Severidad.ALTO,
            f"En {referencia} se leyeron {operador.lecturas_logicas:.0f} páginas (lecturas lógicas), más de lo "
            f"permitido.",
            "Revise los filtros y los índices para leer menos datos.",
        )
    if (
        operador.estimacion_filas
        and operador.filas_reales
        and operador.estimacion_filas > 0
        and operador.filas_reales / operador.estimacion_filas >= umbrales.diferencia_filas_alta
    ):
        agregar(
            "SOBREESTIMACION_FILAS", Severidad.ALTO,
            f"En {referencia} SQL Server estimó {operador.estimacion_filas:.0f} filas, pero salieron "
            f"{operador.filas_reales:.0f}.",
            "Una estimación tan distinta lleva a malos planes: actualice las estadísticas de la tabla "
            "(UPDATE STATISTICS).",
        )
    return observaciones


def _ubicacion(operadores: List[OperadorPlan], varias_consultas: bool) -> str:
    """'nodo 3', 'nodos 3, 9' o, si el plan tiene varias consultas, 'nodo 5 de la consulta 2'."""
    if not varias_consultas:
        nodos = sorted({o.nodo_id for o in operadores}, key=_orden_nodo)
        return ("nodo " if len(nodos) == 1 else "nodos ") + ", ".join(nodos)
    return ", ".join(dict.fromkeys(f"nodo {o.nodo_id} de la consulta {o.consulta}" for o in operadores))


# Reglas cuyo grupo se resume con una introducción propia y lista solo las tablas.
_INTRO_GRUPO = {"TABLE_SCAN": "tablas que se leen completas con un Table Scan"}


def _orden_nodo(nodo_id: str):
    return (0, int(nodo_id)) if nodo_id.isdigit() else (1, nodo_id)


def _agrupar(observaciones: List[_Observacion], varias_consultas: bool) -> List[Hallazgo]:
    """Une las observaciones de una misma regla en un solo hallazgo (como en los demás módulos).

    La misma tabla con el mismo problema en varios nodos se nombra una sola vez.
    """
    por_regla: dict = {}
    for observacion in observaciones:
        por_regla.setdefault(observacion.regla, {}).setdefault(observacion.hecho, []).append(observacion)

    hallazgos = []
    for regla, por_hecho in por_regla.items():
        primera = next(iter(por_hecho.values()))[0]
        casos = [
            (hecho, _ubicacion([o.operador for o in grupo], varias_consultas))
            for hecho, grupo in por_hecho.items()
        ]
        if len(casos) == 1:
            hecho, donde = casos[0]
            mensaje = f"{hecho[:-1]} ({donde}). {primera.accion}"
        else:
            consultas = sorted({o.operador.consulta for grupo in por_hecho.values() for o in grupo})
            if varias_consultas:
                encabezado = ("la consulta " if len(consultas) == 1 else "las consultas ") + ", ".join(map(str, consultas))
            else:
                nodos = sorted({o.operador.nodo_id for grupo in por_hecho.values() for o in grupo}, key=_orden_nodo)
                encabezado = "los nodos " + ", ".join(nodos)
            if regla in _INTRO_GRUPO:
                tablas = [next(iter(grupo)).operador.objeto or "operador sin tabla" for grupo in por_hecho.values()]
                detalle = "; ".join(f"{tabla} ({donde})" for tabla, (_, donde) in zip(tablas, casos))
                intro = f"Se identificaron {len(casos)} {_INTRO_GRUPO[regla]}"
            else:
                detalle = "; ".join(f"{hecho[:1].lower()}{hecho[1:-1]} ({donde})" for hecho, donde in casos)
                intro = f"Se encontraron {len(casos)} observaciones de este tipo"
            mensaje = f"{intro}, en {encabezado}: {detalle}. {primera.accion}"
        hallazgo = _hallazgo(regla, primera.severidad, mensaje)
        # Nodos del diagrama donde está cada caso: la interfaz arma con ellos la captura del plan.
        hallazgo.nodos = [
            {"consulta": o.operador.consulta, "nodo": o.operador.nodo_id}
            for grupo in por_hecho.values() for o in grupo
        ]
        hallazgos.append(hallazgo)
    return hallazgos


def _consulta_con_memoria(raiz: ET.Element) -> int:
    """Número de la primera sentencia (consulta o condición de IF) que trae MemoryGrantInfo."""
    numero = 0
    for elemento in raiz.iter():
        if _nombre_local(elemento) in SENTENCIAS:
            numero += 1
            plan = plan_de_sentencia(elemento)
            if plan is not None and any(_nombre_local(e) == "MemoryGrantInfo" for e in plan):
                return numero
    return 1


def analizar_plan_ejecucion(
    contenido: Union[str, bytes],
    umbrales: Optional[UmbralesPlan] = None,
) -> Tuple[List[Hallazgo], List[OperadorPlan], Optional[MemoriaPlan]]:
    """Analiza un plan XML real y devuelve hallazgos, operadores y memoria."""
    raiz = ET.fromstring(contenido)
    configuracion = umbrales or UmbralesPlan()
    operadores = _extraer_operadores(raiz)
    memoria = _extraer_memoria(raiz)
    observaciones = [o for operador in operadores for o in _revisar_operador(operador, configuracion)]
    hallazgos = _agrupar(observaciones, varias_consultas=len({o.consulta for o in operadores}) > 1)
    if (
        memoria
        and memoria.memoria_concedida_kb
        and memoria.memoria_maxima_utilizada_kb
        and memoria.memoria_maxima_utilizada_kb > 0
        and memoria.memoria_concedida_kb >= memoria.memoria_maxima_utilizada_kb * configuracion.memoria_sobrante_factor
    ):
        hallazgo = _hallazgo(
            "MEMORIA_CONCEDIDA_SOBREDIMENSIONADA",
            Severidad.MEDIO,
            f"La consulta reservó {memoria.memoria_concedida_kb:.0f} KB de memoria pero solo usó "
            f"{memoria.memoria_maxima_utilizada_kb:.0f} KB, quitándosela a otras consultas. Suele deberse a "
            f"estadísticas desactualizadas o a columnas de texto demasiado grandes.",
        )
        hallazgo.nodos = [{"consulta": _consulta_con_memoria(raiz), "nodo": "raiz"}]  # la memoria es de la sentencia
        hallazgos.append(hallazgo)
    return hallazgos, operadores, memoria