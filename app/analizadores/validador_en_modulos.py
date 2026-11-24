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

import re
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


# --- Firma sola en Diccionarios (usuaria, 23 nov.) -------------------------------------------------------------------
_SIN_COMENTARIOS_NI_TEXTOS = re.compile(r"/\*[\s\S]*?(?:\*/|$)|--[^\n]*|'(?:[^']|'')*'?")
_CABECERA = re.compile(r"\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(PROC(?:EDURE)?|FUNCTION)\b", re.IGNORECASE)


def _tiene_cuerpo(limpio: str, desde: int, hasta: int) -> bool:
    """Si la firma que empieza en `desde` trae su AS (fuera de paréntesis) antes de `hasta`."""
    profundidad = 0
    for token in re.finditer(r"[()]|\bAS\b", limpio[desde:hasta], re.IGNORECASE):
        if token.group(0) == "(":
            profundidad += 1
        elif token.group(0) == ")":
            profundidad -= 1
        elif profundidad == 0:
            return True
    return False


def _cuerpo_minimo(es_procedimiento: bool, firma_limpia: str) -> str:
    if es_procedimiento:
        return "\nAS\nRETURN"
    devuelve = re.search(r"\bRETURNS\s+(@\w+\s+)?(TABLE\b)?", firma_limpia, re.IGNORECASE)
    if not devuelve:
        return "\nRETURNS INT\nAS\nBEGIN\nRETURN NULL\nEND"
    if devuelve.group(1):  # RETURNS @t TABLE (…)
        return "\nAS\nBEGIN\nRETURN\nEND"
    if devuelve.group(2):  # RETURNS TABLE
        return "\nAS\nRETURN (SELECT 1 AS c)"
    return "\nAS\nBEGIN\nRETURN NULL\nEND"


def _ultima_linea(texto: str) -> int:
    return max(1, len(texto.rstrip().splitlines()))


def _partes_a_validar(tipo: str, texto: str) -> List[tuple]:
    """(a_validar, original, tope) de cada parte de la cajita del objeto.

    En Diccionarios se pega solo la firma (ALTER PROCEDURE x (@a INT, …)) sin el AS ni el cuerpo, a veces varias
    firmas juntas (usuaria, 23 nov.: «como solo está validando no necesita todo completo»). Para que el validador no
    diga «fin de archivo inesperado», cada firma se valida por separado con un cuerpo mínimo agregado por dentro; los
    errores de la firma (una coma, un tipo mal escrito) se siguen viendo. Cada parte lleva delante tantos saltos de
    línea como líneas hay antes, así los números de línea son los de la cajita. Si todas traen su AS, la cajita se
    valida entera, como siempre. `tope`: última línea de la parte (None si no se le agregó nada)."""
    entero = [(texto, texto, None)]
    if tipo not in ("procedimiento", "funcion"):
        return entero
    limpio = _SIN_COMENTARIOS_NI_TEXTOS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto)
    cabeceras = list(_CABECERA.finditer(limpio))
    limites = [c.start() for c in cabeceras[1:]] + [len(texto)]
    if not cabeceras or all(_tiene_cuerpo(limpio, c.end(), fin) for c, fin in zip(cabeceras, limites)):
        return entero
    partes = []
    for numero, (cabecera, fin) in enumerate(zip(cabeceras, limites)):
        desde = 0 if numero == 0 else cabecera.start()
        original = "\n" * texto.count("\n", 0, desde) + texto[desde:fin]
        if _tiene_cuerpo(limpio, cabecera.end(), fin):
            partes.append((original, original, None))
            continue
        cuerpo = _cuerpo_minimo(cabecera.group(1).upper().startswith("PROC"), limpio[cabecera.end():fin])
        firma = original.rstrip()
        if firma.endswith(";"):
            # «ALTER PROCEDURE x (@a INT);» pegado solo como firma: ese ; final no hace daño (usuaria, 23 nov.). Se
            # cambia por un espacio para no mover las columnas.
            firma = firma[:-1] + " "
        partes.append((firma + cuerpo, original, _ultima_linea(original)))
    return partes


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
        partes = _partes_a_validar(tipo, texto) if seccion is None else [(texto, texto, None)]
        for a_validar, original, tope in partes:
            encontrados = validar_estructura(a_validar)
            if encontrados and tope and any(h.regla == "ERROR_SINTAXIS" and h.linea > tope for h in encontrados):
                # El error cae en el cuerpo agregado («cerca de 'AS'»): la firma de verdad está incompleta (un
                # paréntesis sin cerrar, una coma al final). El mensaje sin el cuerpo agregado es el que corresponde.
                encontrados = validar_estructura(original)
            if encontrados is None:
                estado = LECTOR_SCRIPTDOM.estado()
                return {"disponible": False, "alcance": alcance,
                        "motivo": estado.get("motivo") or "El Validador SQL Server no está disponible en esta PC."}
            for hallazgo in encontrados:
                if alcance == ESTRUCTURA and hallazgo.severidad != Severidad.CRITICO:
                    continue
                if EQUIVALENTES.get(hallazgo.regla, set()) & reglas_caja:
                    continue
                if tope:
                    # Nunca más abajo de lo que se pegó.
                    hallazgo.linea = min(hallazgo.linea, tope)
                    if getattr(hallazgo, "lineas", None):
                        hallazgo.lineas = sorted({min(n, tope) for n in hallazgo.lineas})
                if seccion:
                    hallazgo.seccion = seccion
                hallazgos.append(hallazgo)
    return {"disponible": True, "alcance": alcance, "hallazgos": hallazgos}
