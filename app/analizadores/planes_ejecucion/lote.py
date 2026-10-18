# -*- coding: utf-8 -*-
"""
Revisión de planes por lote: varios .sqlplan sueltos, un .zip o un .rar (o una
mezcla), tal como llegan adjuntos en el correo.

- Los .zip se abren con Python (zipfile), sin escribir nada en disco.
- Los .rar se abren con el tar.exe de Windows 10/11 (bsdtar), sin instalar nada.
  Si esa computadora no puede, se avisa: se extrae con clic derecho y se sube.
- Un archivo es un plan si su contenido es ShowPlanXML (no basta la extensión).
- Los planes repetidos (mismo contenido) se analizan una sola vez.
- Cada plan pasa por analizar_plan_completo: las mismas reglas que un plan suelto.
"""

import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

from app.analizadores.planes_ejecucion.servicio import SEVERIDADES, analizar_plan_completo

MAXIMO_PLANES = 60
MAXIMO_POR_ARCHIVO = 25 * 1024 * 1024  # igual que un plan suelto
MAXIMO_DESCOMPRIMIDO = 300 * 1024 * 1024  # protección ante comprimidos enormes
MAXIMA_PROFUNDIDAD = 3  # comprimidos dentro de comprimidos

_MARCA_PLAN = (b"ShowPlanXML", "ShowPlanXML".encode("utf-16-le"), "ShowPlanXML".encode("utf-16-be"))
_CARPETAS_DE_SISTEMA = ("__MACOSX/",)


@dataclass
class ArchivoPlan:
    nombre: str  # nombre del archivo (sin carpetas)
    ruta: str  # dónde estaba: «Planes.zip › Reportes/plan.sqlplan»
    contenido: bytes


@dataclass
class Ignorado:
    ruta: str
    motivo: str


@dataclass
class Extraccion:
    planes: List[ArchivoPlan] = field(default_factory=list)
    ignorados: List[Ignorado] = field(default_factory=list)
    descomprimido: int = 0


def es_plan(contenido: bytes) -> bool:
    """El archivo es un plan de SQL Server (ShowPlanXML), en UTF-8 o UTF-16 como los guarda SSMS."""
    inicio = contenido[:8192]
    return any(marca in inicio for marca in _MARCA_PLAN)


def _es_zip(nombre: str, contenido: bytes) -> bool:
    return nombre.lower().endswith(".zip") or contenido[:4] == b"PK\x03\x04"


def _es_rar(nombre: str, contenido: bytes) -> bool:
    return nombre.lower().endswith(".rar") or contenido[:6] == b"Rar!\x1a\x07"


def _tar_de_windows() -> Optional[str]:
    """
    El tar.exe de Windows (bsdtar) sabe abrir .rar. Se evita el tar de Git, que no puede.
    """
    sistema = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
    candidatos = [str(sistema)] if sistema.exists() else []
    candidatos += [c for c in (shutil.which("bsdtar"), shutil.which("tar")) if c]
    for candidato in candidatos:
        try:
            version = subprocess.run([candidato, "--version"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if "bsdtar" in version:
            return candidato
    return None


def _entradas_rar(contenido: bytes) -> List[Tuple[str, bytes]]:
    """Archivos de un .rar (ruta interna, contenido). Lanza RuntimeError si no se puede abrir."""
    tar = _tar_de_windows()
    if tar is None:
        raise RuntimeError("esta computadora no tiene una herramienta para abrir .rar")
    with tempfile.TemporaryDirectory(prefix="genesis_rar_") as carpeta:
        origen = Path(carpeta) / "lote.rar"
        destino = Path(carpeta) / "contenido"
        destino.mkdir()
        origen.write_bytes(contenido)
        # bsdtar no escribe fuera de la carpeta destino (rutas absolutas o con «..»).
        resultado = subprocess.run(
            [tar, "-xf", str(origen), "-C", str(destino)], capture_output=True, text=True, timeout=120,
        )
        if resultado.returncode != 0:
            raise RuntimeError("el .rar está dañado o este Windows no puede abrirlo")
        entradas = []
        for archivo in sorted(destino.rglob("*")):
            if archivo.is_file():
                entradas.append((archivo.relative_to(destino).as_posix(), archivo.read_bytes()))
        return entradas


def _entradas_zip(contenido: bytes) -> List[Tuple[str, bytes]]:
    """Archivos de un .zip (ruta interna, contenido), leídos en memoria. Lanza zipfile.BadZipFile."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as comprimido:
        return [
            (info.filename, comprimido.read(info))
            for info in comprimido.infolist()
            if not info.is_dir() and info.file_size <= MAXIMO_DESCOMPRIMIDO
        ]


def _recorrer(nombre: str, ruta: str, contenido: bytes, extraccion: Extraccion, profundidad: int) -> None:
    if any(c in ruta for c in _CARPETAS_DE_SISTEMA):  # restos que agrega macOS al comprimir
        return
    if _es_zip(nombre, contenido) or _es_rar(nombre, contenido):
        tipo = "zip" if _es_zip(nombre, contenido) else "rar"
        if profundidad >= MAXIMA_PROFUNDIDAD:
            extraccion.ignorados.append(Ignorado(ruta, "Hay demasiados comprimidos uno dentro de otro."))
            return
        try:
            entradas = _entradas_zip(contenido) if tipo == "zip" else _entradas_rar(contenido)
        except zipfile.BadZipFile:
            extraccion.ignorados.append(Ignorado(ruta, "El .zip está dañado y no se pudo abrir."))
            return
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            motivo = str(error) if isinstance(error, RuntimeError) else "no se pudo abrir el .rar"
            extraccion.ignorados.append(Ignorado(
                ruta,
                f"No se pudo abrir el .rar: {motivo}. Extráelo con clic derecho → «Extraer todo» y sube los planes.",
            ))
            return
        for interna, datos in entradas:
            extraccion.descomprimido += len(datos)
            if extraccion.descomprimido > MAXIMO_DESCOMPRIMIDO:
                extraccion.ignorados.append(Ignorado(ruta, "El contenido descomprimido supera los 300 MB."))
                return
            _recorrer(PurePosixPath(interna).name, f"{ruta} › {interna}", datos, extraccion, profundidad + 1)
        return
    if not es_plan(contenido):
        extraccion.ignorados.append(Ignorado(ruta, "No es un plan de ejecución (ShowPlanXML)."))
        return
    if len(contenido) > MAXIMO_POR_ARCHIVO:
        extraccion.ignorados.append(Ignorado(ruta, "El plan supera los 25 MB."))
        return
    extraccion.planes.append(ArchivoPlan(nombre, ruta, contenido))


def extraer_planes(archivos: List[Tuple[str, bytes]]) -> Extraccion:
    """
    Planes encontrados en los archivos subidos (sueltos o dentro de .zip/.rar) y
    lo que se dejó fuera, con su motivo. Los repetidos se cuentan una sola vez.
    """
    extraccion = Extraccion()
    for nombre, contenido in archivos:
        _recorrer(PurePosixPath(nombre.replace("\\", "/")).name, nombre, contenido, extraccion, 0)

    unicos: List[ArchivoPlan] = []
    vistos: Dict[str, str] = {}
    for plan in extraccion.planes:
        huella = hashlib.sha1(plan.contenido).hexdigest()
        if huella in vistos:
            extraccion.ignorados.append(Ignorado(plan.ruta, f"Es el mismo plan que {vistos[huella]}."))
            continue
        vistos[huella] = plan.ruta
        unicos.append(plan)
    if len(unicos) > MAXIMO_PLANES:
        for plan in unicos[MAXIMO_PLANES:]:
            extraccion.ignorados.append(Ignorado(plan.ruta, f"Se revisan como máximo {MAXIMO_PLANES} planes por lote."))
        unicos = unicos[:MAXIMO_PLANES]
    extraccion.planes = unicos
    return extraccion


_PROCEDIMIENTO_EN_TEXTO = re.compile(
    r"\b(?:EXEC(?:UTE)?|(?:CREATE|ALTER)\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?)\s+"
    r"((?:\[[^\]]+\]|[A-Za-z_#][\w$#]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Za-z_][\w$#]*)){0,3})",
    re.IGNORECASE,
)


def _limpiar_nombre(nombre: str) -> str:
    return ".".join(parte.strip().strip("[]") for parte in nombre.split("."))


def nombre_procedimiento(contenido: bytes, archivo: str) -> str:
    """
    Procedimiento del plan: el que nombra el propio XML (StoredProc o el EXEC / CREATE PROCEDURE
    de una sentencia) o, si no viene, el nombre del archivo sin extensión.
    """
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError:
        raiz = None
    if raiz is not None:
        for elemento in raiz.iter():
            etiqueta = elemento.tag.rsplit("}", 1)[-1]
            if etiqueta == "StoredProc" and elemento.attrib.get("ProcName"):
                return _limpiar_nombre(elemento.attrib["ProcName"])
        for elemento in raiz.iter():
            texto = elemento.attrib.get("StatementText", "")
            coincidencia = _PROCEDIMIENTO_EN_TEXTO.search(texto)
            if coincidencia and not coincidencia.group(1).lower().startswith(("sp_executesql", "@")):
                return _limpiar_nombre(coincidencia.group(1))
    return PurePosixPath(archivo).stem


def _resumen_plan(plan: ArchivoPlan, analisis: Dict, limite: Optional[float]) -> Dict:
    con_tiempo = [s for s in analisis["diagrama"] if s.get("duracionMs") is not None]
    duracion_ms = sum(s["duracionMs"] for s in con_tiempo) if con_tiempo else None
    return {
        "archivo": plan.nombre,
        "ruta": plan.ruta,
        "procedimiento": nombre_procedimiento(plan.contenido, plan.nombre),
        "duracionMs": duracion_ms,
        "superaLimite": bool(limite is not None and duracion_ms is not None and duracion_ms / 1000 > limite),
        "resumen": analisis["resumen"],
        "totalHallazgos": len(analisis["hallazgos"]),
    }


def analizar_lote(archivos: List[Tuple[str, bytes]], area: str = "negocio", limite: Optional[float] = None) -> Dict:
    """
    Analiza todos los planes del lote con las reglas del área y su límite de tiempo.
    Cada plan trae su análisis completo (igual que un plan suelto) para ver su detalle
    sin volver a subirlo. Un plan que no se puede leer no detiene a los demás.
    """
    extraccion = extraer_planes(archivos)
    planes = []
    for indice, plan in enumerate(extraccion.planes):
        try:
            analisis = analizar_plan_completo(plan.nombre, plan.contenido, area, limite)
        except ET.ParseError:
            planes.append({
                "id": indice, "archivo": plan.nombre, "ruta": plan.ruta,
                "procedimiento": PurePosixPath(plan.nombre).stem,
                "error": "El plan está incompleto o dañado y no se pudo leer.",
            })
            continue
        planes.append({"id": indice, **_resumen_plan(plan, analisis, limite), "analisis": analisis})

    leidos = [p for p in planes if "error" not in p]
    totales = {severidad: sum(p["resumen"][severidad] for p in leidos) for severidad in SEVERIDADES}
    return {
        "area": area,
        "limite": limite,
        "planes": planes,
        "ignorados": [{"ruta": i.ruta, "motivo": i.motivo} for i in extraccion.ignorados],
        "totales": {
            "planes": len(leidos),
            "conError": len(planes) - len(leidos),
            "superanLimite": sum(1 for p in leidos if p["superaLimite"]),
            "hallazgos": sum(p["totalHallazgos"] for p in leidos),
            "sinHallazgos": sum(1 for p in leidos if p["totalHallazgos"] == 0),
            "porSeveridad": totales,
        },
    }
