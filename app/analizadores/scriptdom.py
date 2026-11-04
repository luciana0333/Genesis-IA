# -*- coding: utf-8 -*-
"""Lector oficial de T-SQL de Microsoft (ScriptDom), el mismo que usan SSMS y Visual Studio.

Genesis no instala nada: usa la DLL de ScriptDom que ya trae SSMS (o una copia indicada en la
variable GENESIS_SCRIPTDOM) y la carga desde PowerShell 5.1, que viene en todo Windows. El código
se lee en esta PC; no se conecta a ninguna base de datos.

PowerShell tarda 1-2 s en abrir: se abre una sola vez y queda esperando. Cada pedido es una línea
con el SQL en base64 y cada respuesta, una línea JSON. Se lanza con -EncodedCommand (no es un
archivo .ps1, así que no depende de la política de scripts del equipo).

Si la DLL no está o PowerShell no responde, Genesis sigue igual que siempre: la validación dice
que no está disponible y no se rompe nada.
"""

from __future__ import annotations

import base64
import glob
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

from app.analizadores.scriptdom_mensajes import MENSAJES, mensaje_agrupado, mensaje_hecho, severidad
from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

DLL = "Microsoft.SqlServer.TransactSql.ScriptDom.dll"
# Producción de la Caja usa SQL Server 2022: se lee con su versión (TSql160Parser), así también se
# marca lo que solo existe en versiones más nuevas.
LECTOR = "TSql160Parser"
VERSION_SQL = "SQL Server 2022"
ESPERA_INICIO_S = 60
# Revisor sobre el árbol de ScriptDom (C#), para lo que es sintaxis válida pero SQL Server rechaza.
REVISOR = Path(__file__).with_name("scriptdom_revisor.cs")
ESPERA_PEDIDO_S = 20

# Dónde suele estar la DLL: SSMS 18 a 22 y las herramientas de SQL Server (DacFx).
_UBICACIONES = (
    r"C:\Program Files*\Microsoft SQL Server Management Studio*\**\{dll}",
    r"C:\Program Files*\Microsoft SQL Server\*\DAC\bin\{dll}",
)

_PROGRAMA = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
try {
  $ensamblado = [System.Reflection.Assembly]::LoadFrom($env:GENESIS_SCRIPTDOM_DLL)
  $tipo = $ensamblado.GetType('Microsoft.SqlServer.TransactSql.ScriptDom.' + $env:GENESIS_SCRIPTDOM_LECTOR)
  if ($tipo -eq $null) { throw 'La versión de ScriptDom no trae el lector ' + $env:GENESIS_SCRIPTDOM_LECTOR }
  # Revisor sobre el árbol (C#): se compila una vez. Si no se puede, sigue solo la sintaxis.
  $revisor = $true
  $motivoRevisor = ''
  try {
    $referencias = @($env:GENESIS_SCRIPTDOM_DLL, 'System.Core')
    $netstandard = Join-Path ([System.Runtime.InteropServices.RuntimeEnvironment]::GetRuntimeDirectory()) 'netstandard.dll'
    if (Test-Path $netstandard) { $referencias += $netstandard }
    Add-Type -TypeDefinition ([System.IO.File]::ReadAllText($env:GENESIS_SCRIPTDOM_REVISOR)) -ReferencedAssemblies $referencias
  } catch {
    $revisor = $false
    $motivoRevisor = $_.Exception.Message
  }
  [Console]::Out.WriteLine((ConvertTo-Json -Compress -InputObject @{ listo = $true; version = $ensamblado.GetName().Version.ToString(); revisor = $revisor; motivoRevisor = $motivoRevisor }))
} catch {
  [Console]::Out.WriteLine((ConvertTo-Json -Compress -InputObject @{ listo = $false; error = $_.Exception.Message }))
  exit
}
while ($true) {
  $pedido = [Console]::In.ReadLine()
  if ($pedido -eq $null) { break }
  try {
    $sql = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($pedido))
    $lector = [Activator]::CreateInstance($tipo, @($true))
    $errores = $null
    $arbol = $lector.Parse((New-Object System.IO.StringReader($sql)), [ref]$errores)
    $lista = New-Object System.Collections.ArrayList
    foreach ($e in $errores) { $null = $lista.Add(@{ numero = $e.Number; linea = $e.Line; columna = $e.Column; mensaje = $e.Message }) }
    # Con errores de sintaxis el árbol está incompleto: primero se corrige la sintaxis.
    $hechos = @()
    if ($revisor -and $lista.Count -eq 0) { $hechos = @([GenesisRevisor]::Revisar($arbol)) }
    [Console]::Out.WriteLine((ConvertTo-Json -Compress -Depth 5 -InputObject @{ errores = $lista.ToArray(); hechos = $hechos }))
  } catch {
    [Console]::Out.WriteLine((ConvertTo-Json -Compress -InputObject @{ fallo = $_.Exception.Message }))
  }
}
"""


def buscar_dll() -> Optional[Path]:
    """La DLL indicada en GENESIS_SCRIPTDOM o la primera que se encuentre en SSMS / SQL Server."""
    propia = os.environ.get("GENESIS_SCRIPTDOM")
    if propia and Path(propia).is_file():
        return Path(propia)
    for patron in _UBICACIONES:
        encontradas = sorted(glob.glob(patron.format(dll=DLL), recursive=True), reverse=True)
        if encontradas:
            return Path(encontradas[0])
    return None


class _LectorScriptDom:
    """Un solo PowerShell abierto con ScriptDom cargado, compartido por todos los pedidos."""

    def __init__(self) -> None:
        self._candado = threading.Lock()
        self._proceso: Optional[subprocess.Popen] = None
        self._salida: "queue.Queue[str]" = queue.Queue()
        self._estado: Dict = {"disponible": False, "motivo": "Aún no se ha iniciado."}

    def _iniciar(self) -> None:
        if sys.platform != "win32":
            self._estado = {"disponible": False, "motivo": "ScriptDom solo funciona en Windows."}
            return
        dll = buscar_dll()
        if dll is None:
            self._estado = {
                "disponible": False,
                "motivo": "No se encontró ScriptDom en esta PC (viene con SQL Server Management Studio).",
            }
            return
        comando = base64.b64encode(_PROGRAMA.encode("utf-16-le")).decode("ascii")
        entorno = {**os.environ, "GENESIS_SCRIPTDOM_DLL": str(dll), "GENESIS_SCRIPTDOM_LECTOR": LECTOR,
                   "GENESIS_SCRIPTDOM_REVISOR": str(REVISOR)}
        try:
            self._proceso = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-EncodedCommand", comando],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=entorno,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            self._estado = {"disponible": False, "motivo": f"No se pudo abrir PowerShell: {exc}"}
            return
        self._salida = queue.Queue()
        threading.Thread(target=self._leer_salida, args=(self._proceso, self._salida), daemon=True).start()
        inicio = self._respuesta(ESPERA_INICIO_S)
        if not inicio or not inicio.get("listo"):
            motivo = (inicio or {}).get("error") or "PowerShell no respondió al cargar ScriptDom."
            self._cerrar()
            self._estado = {"disponible": False, "motivo": motivo, "dll": str(dll)}
            return
        self._estado = {
            "disponible": True, "dll": str(dll), "version": inicio.get("version"), "lector": VERSION_SQL,
            "revisor": bool(inicio.get("revisor")), "motivoRevisor": inicio.get("motivoRevisor") or None,
        }

    @staticmethod
    def _leer_salida(proceso: subprocess.Popen, salida: "queue.Queue[str]") -> None:
        for linea in iter(proceso.stdout.readline, b""):
            salida.put(linea.decode("utf-8", errors="replace").strip())

    def _respuesta(self, espera: float) -> Optional[Dict]:
        try:
            return json.loads(self._salida.get(timeout=espera))
        except (queue.Empty, json.JSONDecodeError):
            return None

    def _cerrar(self) -> None:
        if self._proceso is not None:
            try:
                self._proceso.kill()
            except OSError:
                pass
        self._proceso = None

    def _activo(self) -> bool:
        return self._proceso is not None and self._proceso.poll() is None

    def estado(self) -> Dict:
        with self._candado:
            if not self._activo():
                self._iniciar()
            return dict(self._estado)

    def leer(self, sql: str) -> Optional[Dict[str, List[Dict]]]:
        """
        {errores: [{numero, linea, columna, mensaje}], hechos: [{tipo, linea, ...}]} de ScriptDom; None si
        no está disponible. Los hechos solo se revisan cuando no hay errores de sintaxis.
        """
        with self._candado:
            if not self._activo():
                self._iniciar()
            if not self._activo():
                return None
            try:
                self._proceso.stdin.write(base64.b64encode(sql.encode("utf-8")) + b"\n")
                self._proceso.stdin.flush()
            except OSError:
                self._cerrar()
                return None
            respuesta = self._respuesta(ESPERA_PEDIDO_S)
            if respuesta is None or "errores" not in respuesta:
                # Sin respuesta (o un fallo inesperado): se reinicia en el próximo pedido.
                self._cerrar()
                return None
            return {"errores": _lista(respuesta.get("errores")), "hechos": _lista(respuesta.get("hechos"))}

    def errores_de_sintaxis(self, sql: str) -> Optional[List[Dict]]:
        """[{numero, linea, columna, mensaje}] de SQL Server; None si ScriptDom no está disponible."""
        lectura = self.leer(sql)
        return None if lectura is None else lectura["errores"]


def _lista(valor) -> List[Dict]:
    # ConvertTo-Json de PowerShell 5.1 escribe una lista de un solo elemento como el elemento.
    if not valor:
        return []
    return [valor] if isinstance(valor, dict) else list(valor)


LECTOR_SCRIPTDOM = _LectorScriptDom()


def mensaje_error_sintaxis(error: Dict) -> str:
    mensaje = str(error.get("mensaje", "")).strip()
    if mensaje and not mensaje.endswith("."):
        mensaje += "."
    return (
        f"Se identificó un error de sintaxis en la línea {error.get('linea')}, columna {error.get('columna')}: "
        f"{mensaje} Corregir la estructura en esa línea o justo antes (comas, paréntesis, comillas, BEGIN/END), "
        f"ya que SQL Server no podrá crear ni ejecutar el código con este error."
    )


def _hallazgo(linea, regla: str, mensaje: str, severidad: Severidad = Severidad.CRITICO) -> Hallazgo:
    return Hallazgo(linea=int(linea or 1), origen=OrigenAnalisis.REGLAS_ESTATICAS, severidad=severidad,
                    regla=regla, mensaje=mensaje)


def validar_estructura(sql: str) -> Optional[List[Hallazgo]]:
    """
    Validación SQL Server: errores de sintaxis y, si no hay, lo que revisa el árbol de ScriptDom (lo que hace
    fallar el script, errores silenciosos, rendimiento, seguridad y mantenibilidad). Varios casos del mismo
    tipo van en una sola observación. None si ScriptDom no está disponible.
    """
    lectura = LECTOR_SCRIPTDOM.leer(sql)
    if lectura is None:
        return None
    hallazgos = [
        _hallazgo(error.get("linea"), "ERROR_SINTAXIS", mensaje_error_sintaxis(error)) for error in lectura["errores"]
    ]
    por_tipo: Dict[str, List[Dict]] = {}
    for hecho in lectura["hechos"]:
        if hecho.get("tipo") in MENSAJES:
            por_tipo.setdefault(hecho["tipo"], []).append(hecho)
    for tipo, hechos in por_tipo.items():
        mensaje = mensaje_agrupado(hechos)
        if not mensaje:
            continue
        lineas = sorted({int(h["linea"]) for h in hechos if mensaje_hecho(h)})
        hallazgo = _hallazgo(lineas[0], tipo, mensaje, severidad(tipo))
        if len(lineas) > 1:
            hallazgo.lineas = lineas  # para recorrerlas con la barra «1 de N»
        hallazgos.append(hallazgo)
    return hallazgos
