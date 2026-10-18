# -*- coding: utf-8 -*-
"""
Análisis completo de un plan de ejecución, listo para la pantalla.

Lo usan tanto la revisión de un plan suelto (/api/analizar-plan) como la
revisión por lote (/api/analizar-planes): así cada plan del lote pasa por las
mismas reglas y devuelve exactamente los mismos datos que un plan suelto.
"""

from typing import Dict, Optional, Union

from app.analizadores.planes_ejecucion import (
    analizar_plan_ejecucion,
    analizar_plan_negocio,
    analizar_plan_reporte,
    construir_diagrama,
)

SEVERIDADES = ("critico", "alto", "medio", "bajo")


def analizar_plan_completo(
    nombre: str, contenido: Union[str, bytes], area: str = "negocio", limite: Optional[float] = None,
) -> Dict:
    """
    Hallazgos (según el área), operadores, memoria y diagrama de un plan.
    Lanza xml.etree.ElementTree.ParseError si el contenido no es un plan XML válido.
    """
    hallazgos, operadores, memoria = analizar_plan_ejecucion(contenido)
    diagrama = construir_diagrama(contenido)
    if area == "reporte":
        hallazgos = analizar_plan_reporte(diagrama, limite)
    elif area == "negocio":
        hallazgos = analizar_plan_negocio(diagrama, limite)

    resumen = {severidad: 0 for severidad in SEVERIDADES}
    hallazgos_serializados = []
    for hallazgo in hallazgos:
        severidad = hallazgo.severidad.value.lower()
        resumen[severidad] += 1
        hallazgos_serializados.append({
            "linea": hallazgo.linea,
            "origen": hallazgo.origen.value,
            "severidad": severidad,
            "regla": hallazgo.regla,
            "mensaje": hallazgo.mensaje,
            "nodos": getattr(hallazgo, "nodos", []),
            "codigo": getattr(hallazgo, "codigo", None),
        })

    operadores_serializados = [
        {
            "nodoId": operador.nodo_id,
            "operacionFisica": operador.operacion_fisica,
            "operacionLogica": operador.operacion_logica,
            "estimacionFilas": operador.estimacion_filas,
            "filasReales": operador.filas_reales,
            "filasLeidas": operador.filas_leidas,
            "lecturasLogicas": operador.lecturas_logicas,
            "duracionMs": operador.duracion_ms,
            "cpuMs": operador.cpu_ms,
            "objeto": operador.objeto,
            "tieneSpill": operador.tiene_spill,
            "tieneConversionImplicita": operador.tiene_conversion_implicita,
        }
        for operador in operadores
    ]
    memoria_serializada = None if memoria is None else {
        "solicitadaKb": memoria.memoria_solicitada_kb,
        "concedidaKb": memoria.memoria_concedida_kb,
        "maximaUtilizadaKb": memoria.memoria_maxima_utilizada_kb,
    }
    return {
        "archivo": nombre,
        "resumen": resumen,
        "hallazgos": hallazgos_serializados,
        "operadores": operadores_serializados,
        "memoria": memoria_serializada,
        "diagrama": diagrama,
    }
