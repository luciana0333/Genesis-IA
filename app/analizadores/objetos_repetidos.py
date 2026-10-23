# -*- coding: utf-8 -*-
"""El mismo objeto creado dos veces en un script (dos CREATE TABLE o dos CREATE PROCEDURE iguales).

SQL Server falla en la segunda creación (error 2714: «There is already an object named ...»).
Se avisa una sola vez y la copia repetida se quita del texto (con espacios, para conservar las
líneas), así el resto de reglas revisa el objeto una sola vez y sus errores no salen dobles.
Un CREATE TABLE seguido de un ALTER TABLE de la misma tabla es correcto y no se marca.
"""

import re
from typing import Dict, List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

_ID = r"(?:\[[^\]]+\]|[A-Za-z_#][\w$#@]*)"
_NOMBRE = rf"((?:{_ID}\s*\.\s*){{0,2}}{_ID})"
_COMENTARIOS = re.compile(r"--[^\n]*|/\*[\s\S]*?\*/")

# Solo CREATE: un CREATE OR ALTER repetido no intenta crear un objeto que ya existe.
_CREACION = {
    "tabla": re.compile(rf"\bCREATE\s+TABLE\s+{_NOMBRE}", re.IGNORECASE),
    "procedimiento": re.compile(rf"\bCREATE\s+PROC(?:EDURE)?\s+{_NOMBRE}", re.IGNORECASE),
}
_SIGUIENTE_OBJETO = re.compile(r"\b(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?(?:TABLE|PROC(?:EDURE)?)\b", re.IGNORECASE)
_GO = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)

_EN_LETRAS = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez"}
_VECES = {2: "dos veces", 3: "tres veces"}


def _en_blanco(texto: str) -> str:
    return re.sub(r"[^\n]", " ", texto)


def _clave(nombre: str) -> Tuple[str, str]:
    """(esquema, nombre) sin corchetes; sin esquema se toma dbo, el esquema por defecto."""
    partes = [p.strip().strip("[]").upper() for p in nombre.split(".")]
    return (partes[-2] if len(partes) > 1 else "DBO"), partes[-1]


def _fin_de_tabla(limpio: str, desde: int) -> int:
    """Fin del CREATE TABLE: el paréntesis que cierra sus columnas (y su punto y coma)."""
    abre = limpio.find("(", desde)
    siguiente = _SIGUIENTE_OBJETO.search(limpio, desde + 1)
    if abre < 0 or (siguiente and siguiente.start() < abre):
        return siguiente.start() if siguiente else len(limpio)
    nivel = 0
    for i in range(abre, len(limpio)):
        if limpio[i] == "(":
            nivel += 1
        elif limpio[i] == ")":
            nivel -= 1
            if nivel == 0:
                fin = re.match(r"\s*;", limpio[i + 1:])
                return i + 1 + (fin.end() if fin else 0)
    return len(limpio)


def _fin_de_procedimiento(limpio: str, desde: int) -> int:
    """Fin del CREATE PROCEDURE: hasta el siguiente GO o el siguiente objeto."""
    finales = [m.start() for m in (_GO.search(limpio, desde), _SIGUIENTE_OBJETO.search(limpio, desde + 1)) if m]
    return min(finales) if finales else len(limpio)


def quitar_creaciones_repetidas(texto: str, tipo: str) -> Tuple[str, List[Tuple[str, List[int]]]]:
    """
    tipo: «tabla» o «procedimiento». Devuelve el texto sin las creaciones repetidas y la lista
    [(nombre, líneas de cada CREATE)] de los objetos que se crean más de una vez.
    """
    limpio = _COMENTARIOS.sub(lambda m: _en_blanco(m.group(0)), texto or "")
    vistos: Dict[Tuple[str, str], Tuple[str, List[int]]] = {}
    tramos: List[Tuple[int, int]] = []
    for m in _CREACION[tipo].finditer(limpio):
        linea = limpio.count("\n", 0, m.start()) + 1
        clave = _clave(m.group(1))
        if clave not in vistos:
            vistos[clave] = (m.group(1).split(".")[-1].strip().strip("[]"), [linea])
            continue
        vistos[clave][1].append(linea)
        fin = _fin_de_tabla(limpio, m.end()) if tipo == "tabla" else _fin_de_procedimiento(limpio, m.end())
        tramos.append((m.start(), fin))
    for inicio, fin in reversed(tramos):
        texto = texto[:inicio] + _en_blanco(texto[inicio:fin]) + texto[fin:]
    return texto, [(nombre, lineas) for nombre, lineas in vistos.values() if len(lineas) > 1]


def _lineas(lineas: List[int]) -> str:
    return f"líneas {', '.join(map(str, lineas[:-1]))} y {lineas[-1]}"


def hallazgo_repetidos(
    repetidas: List[Tuple[str, List[int]]], tipo: str, regla: str, severidad: str, origen: OrigenAnalisis
) -> Optional[Hallazgo]:
    """Una sola observación con todos los objetos creados más de una vez (o None si no hay)."""
    if not repetidas:
        return None
    objeto, sentencia = ("la tabla", "CREATE TABLE") if tipo == "tabla" else ("el procedimiento", "CREATE PROCEDURE")
    motivo = "ya que SQL Server genera un error al intentar crear un objeto que ya existe."
    if len(repetidas) == 1:
        nombre, lineas = repetidas[0]
        veces = _VECES.get(len(lineas), f"{len(lineas)} veces")
        mensaje = (f"Se identificó que {objeto} {nombre} se crea {veces} en el script ({_lineas(lineas)}). "
                   f"Se recomienda retirar {'una de las sentencias' if len(lineas) == 2 else 'las sentencias repetidas'} "
                   f"{sentencia}, {motivo}")
    else:
        plural = "tablas" if tipo == "tabla" else "procedimientos"
        cantidad = _EN_LETRAS.get(len(repetidas), str(len(repetidas)))
        casos = "; ".join(f"{nombre} ({_lineas(lineas)})" for nombre, lineas in repetidas)
        mensaje = (f"Se identificaron {cantidad} {plural} que se crean más de una vez en el script: {casos}. "
                   f"Se recomienda retirar las sentencias {sentencia} repetidas, {motivo}")
    todas = sorted({linea for _, lineas in repetidas for linea in lineas})
    hallazgo = Hallazgo(
        linea=repetidas[0][1][1],
        origen=origen,
        severidad=Severidad(severidad),
        regla=regla,
        mensaje=mensaje,
    )
    hallazgo.lineas = todas
    return hallazgo
