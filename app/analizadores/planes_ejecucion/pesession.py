# -*- coding: utf-8 -*-
"""
Sesiones de SQL Sentry Plan Explorer (.pesession) en la pestaña Planes (usuaria, 24 nov.).

Un .pesession es un .zip con:
- meta.json: datos de la sesión (base, instancia, usuario de conexión…). NO se usa ni se muestra: trae datos de
  conexión de la Caja.
- N.queryanalysis: una por cada consulta ejecutada en Plan Explorer. Es un objeto .NET serializado (BinaryFormatter)
  que guarda, como texto XML normal, un ShowPlanXML por cada sentencia ejecutada.

Seguridad: el objeto .NET nunca se carga ni se ejecuta (deserializar BinaryFormatter es inseguro); solo se buscan
en sus bytes los documentos <ShowPlanXML>…</ShowPlanXML>, que son texto.

Cada .queryanalysis se convierte en UN plan, con todas sus sentencias en orden (StatementId), igual que el .sqlplan
que guarda SSMS de un procedimiento. El nombre del procedimiento sale del EXEC que guarda la sesión.
Caso real: «PE CONCILIACION.PA_PagosSeguros_Ins_PagosSegurosDetalleHistorico.pesession», 6 sentencias.
"""

import io
import re
import zipfile
from pathlib import PurePosixPath
from typing import List, Optional, Tuple

_PLAN = re.compile(rb"<ShowPlanXML\b[\s\S]*?</ShowPlanXML>")
_SENTENCIAS = re.compile(rb"(<Statements>)([\s\S]*)(</Statements>)")
_ID = re.compile(rb'StatementId="(\d+)"')
# Sin \b: en el objeto .NET el texto va pegado al byte de su largo («oEXEC Conciliacion.PA_X …»).
_EXEC = re.compile(rb"EXEC(?:UTE)?\s+((?:\[[^\]\r\n]+\]|[A-Za-z_][\w$#]*)(?:\.(?:\[[^\]\r\n]+\]|[A-Za-z_][\w$#]*)){0,2})")
_MAXIMO_ANALISIS = 300 * 1024 * 1024  # protección ante una sesión enorme


def es_pesession(nombre: str, contenido: bytes) -> bool:
    """Un .zip de Plan Explorer: trae al menos un *.queryanalysis (no basta la extensión)."""
    if contenido[:4] != b"PK\x03\x04":
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
            return any(i.filename.lower().endswith(".queryanalysis") for i in comprimido.infolist())
    except zipfile.BadZipFile:
        return False


def _numero_de_sentencia(plan: bytes, orden: int) -> Tuple[int, int]:
    coincidencia = _ID.search(plan)
    return (int(coincidencia.group(1)) if coincidencia else 10 ** 9, orden)


def unir_planes(planes: List[bytes]) -> Optional[bytes]:
    """Un solo ShowPlanXML con las sentencias de todos, en el orden de StatementId. None si no se pueden unir."""
    if not planes:
        return None
    ordenados = [p for _, p in sorted(((_numero_de_sentencia(p, i), p) for i, p in enumerate(planes)),
                                       key=lambda par: par[0])]
    if len(ordenados) == 1:
        return ordenados[0]
    partes = [_SENTENCIAS.search(p) for p in ordenados]
    if not all(partes):
        return None
    interior = b"".join(parte.group(2) for parte in partes)
    base, primera = ordenados[0], partes[0]
    return base[:primera.start(2)] + interior + base[primera.end(2):]


def nombre_del_procedimiento(analisis: bytes) -> Optional[str]:
    """El procedimiento del EXEC que guarda la sesión («EXEC Conciliacion.PA_X 29, '…'»), sin corchetes."""
    coincidencia = _EXEC.search(analisis)
    if not coincidencia:
        return None
    nombre = coincidencia.group(1).decode("utf-8", "ignore")
    if nombre.lower().startswith("sp_executesql"):
        return None
    return ".".join(parte.strip("[]") for parte in nombre.split("."))


def planes_de_la_sesion(nombre: str, contenido: bytes) -> Tuple[List[Tuple[str, str, bytes]], List[Tuple[str, str]]]:
    """
    ([(nombre del plan, ruta, plan)], [(ruta, motivo)]) de una sesión de Plan Explorer.
    Cada consulta de la sesión da un plan; si sus sentencias no se pueden unir, va una por plan.
    """
    planes, ignorados = [], []
    base = PurePosixPath(nombre).stem
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
            consultas = [i for i in comprimido.infolist() if i.filename.lower().endswith(".queryanalysis")]
            for numero, info in enumerate(sorted(consultas, key=lambda i: i.filename), start=1):
                ruta = f"{nombre} › consulta {numero}"
                if info.file_size > _MAXIMO_ANALISIS:
                    ignorados.append((ruta, "La consulta de la sesión es demasiado grande."))
                    continue
                datos = comprimido.read(info)
                sentencias = _PLAN.findall(datos)
                if not sentencias:
                    ignorados.append((ruta, "La sesión no trae un plan de ejecución para esta consulta."))
                    continue
                procedimiento = nombre_del_procedimiento(datos) or base
                sufijo = "" if len(consultas) == 1 else f" (consulta {numero})"
                unido = unir_planes(sentencias)
                if unido is not None:
                    planes.append((f"{procedimiento}{sufijo}.sqlplan", ruta, unido))
                else:
                    for indice, sentencia in enumerate(sentencias, start=1):
                        planes.append((f"{procedimiento}{sufijo} (sentencia {indice}).sqlplan",
                                       f"{ruta} › sentencia {indice}", sentencia))
    except zipfile.BadZipFile:
        ignorados.append((nombre, "La sesión de Plan Explorer está dañada y no se pudo abrir."))
    return planes, ignorados
