# -*- coding: utf-8 -*-
"""
Validador SQL Server dentro de cada módulo (usuaria, 22 nov.: opción B, pestañas «Buenas prácticas» y
«Validador SQL Server»).

Las reglas de cada módulo (buenas prácticas de la Caja) no cambian: esto solo agrega, aparte, lo que dice el
lector oficial de SQL Server (ScriptDom) sobre el mismo código.

Alcance por módulo:
- Procedimientos y Reportes: todo el validador (estructura, errores silenciosos y rendimiento): es código que se
  ejecuta.
- Tablas y Diccionarios: solo lo crítico (lo que haría fallar el script). Las sugerencias de consultas no aplican a
  un CREATE TABLE ni a un sp_addextendedproperty.

Cada cajita se valida por separado (el objeto, el diccionario, los índices) y la observación lleva su `seccion`,
para que «Ver en el código» marque la cajita correcta.

Lo que ya informa una buena práctica de la Caja no se repite en el validador (EQUIVALENTES).
"""

from typing import Dict, List, Optional

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura
from app.modelos.hallazgo import Hallazgo, Severidad

COMPLETO = "completo"
ESTRUCTURA = "estructura"

# tipoRevision → alcance del validador.
ALCANCE = {
    "procedimiento_normal": COMPLETO,
    "reporte": COMPLETO,
    "tabla_estructura": ESTRUCTURA,
    "tabla": ESTRUCTURA,          # diccionario de tabla
    "procedimiento": ESTRUCTURA,  # diccionario de procedimiento
    "funcion": ESTRUCTURA,        # diccionario de función
}

# Observación del validador → buenas prácticas de la Caja que ya dicen lo mismo (más estrictas): si alguna salió en
# la revisión, la del validador no se muestra. El SQL dinámico está prohibido en la Caja; el validador solo avisa
# cuando concatena un parámetro.
EQUIVALENTES = {
    "SQL_DINAMICO_CONCATENA_PARAMETRO": {"SQL_DINAMICO_PROHIBIDO"},
}


def _cajitas(tipo: str, sql: str, diccionario: str, indices: str) -> List[tuple]:
    """(seccion, texto) de cada cajita que se valida; la principal no lleva sección."""
    cajitas = [(None, sql)]
    if tipo in ("tabla", "procedimiento", "funcion"):
        cajitas.append(("diccionario", diccionario))
    if tipo == "tabla_estructura":
        cajitas.append(("indices", indices))
    return [(seccion, texto) for seccion, texto in cajitas if (texto or "").strip()]


def validar_para_modulo(tipo: str, sql: str, diccionario: str = "", indices: str = "",
                        buenas_practicas: Optional[List[Hallazgo]] = None) -> Optional[Dict]:
    """
    {disponible, alcance, hallazgos} del validador para la revisión de un módulo, o
    {disponible: False, motivo} si esta PC no tiene ScriptDom. None si el tipo de revisión no lleva validador.
    """
    alcance = ALCANCE.get(tipo)
    if alcance is None:
        return None
    reglas_caja = {hallazgo.regla for hallazgo in buenas_practicas or []}
    hallazgos: List[Hallazgo] = []
    for seccion, texto in _cajitas(tipo, sql, diccionario, indices):
        encontrados = validar_estructura(texto)
        if encontrados is None:
            estado = LECTOR_SCRIPTDOM.estado()
            return {"disponible": False, "alcance": alcance,
                    "motivo": estado.get("motivo") or "El Validador SQL Server no está disponible en esta PC."}
        for hallazgo in encontrados:
            if alcance == ESTRUCTURA and hallazgo.severidad != Severidad.CRITICO:
                continue
            if EQUIVALENTES.get(hallazgo.regla, set()) & reglas_caja:
                continue
            if seccion:
                hallazgo.seccion = seccion
            hallazgos.append(hallazgo)
    return {"disponible": True, "alcance": alcance, "hallazgos": hallazgos}
