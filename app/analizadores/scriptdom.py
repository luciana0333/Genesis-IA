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

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

DLL = "Microsoft.SqlServer.TransactSql.ScriptDom.dll"
# Producción de la Caja usa SQL Server 2022: se lee con su versión (TSql160Parser), así también se
# marca lo que solo existe en versiones más nuevas.
LECTOR = "TSql160Parser"
VERSION_SQL = "SQL Server 2022"
ESPERA_INICIO_S = 30
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
  [Console]::Out.WriteLine((ConvertTo-Json -Compress -InputObject @{ listo = $true; version = $ensamblado.GetName().Version.ToString() }))
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
    $null = $lector.Parse((New-Object System.IO.StringReader($sql)), [ref]$errores)
    $lista = New-Object System.Collections.ArrayList
    foreach ($e in $errores) { $null = $lista.Add(@{ numero = $e.Number; linea = $e.Line; columna = $e.Column; mensaje = $e.Message }) }
    [Console]::Out.WriteLine((ConvertTo-Json -Compress -Depth 4 -InputObject @{ errores = $lista.ToArray() }))
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
        entorno = {**os.environ, "GENESIS_SCRIPTDOM_DLL": str(dll), "GENESIS_SCRIPTDOM_LECTOR": LECTOR}
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

    def errores_de_sintaxis(self, sql: str) -> Optional[List[Dict]]:
        """[{numero, linea, columna, mensaje}] de SQL Server; None si ScriptDom no está disponible."""
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
            errores = respuesta["errores"]
            # ConvertTo-Json de PowerShell 5.1 escribe una lista de un solo elemento como el elemento.
            return [errores] if isinstance(errores, dict) else list(errores or [])


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


def validar_estructura(sql: str) -> Optional[List[Hallazgo]]:
    """Errores de sintaxis que haría SQL Server al crear el objeto; None si ScriptDom no está disponible."""
    errores = LECTOR_SCRIPTDOM.errores_de_sintaxis(sql)
    if errores is None:
        return None
    return [
        Hallazgo(
            linea=int(error.get("linea") or 1),
            origen=OrigenAnalisis.REGLAS_ESTATICAS,
            severidad=Severidad.CRITICO,
            regla="ERROR_SINTAXIS",
            mensaje=mensaje_error_sintaxis(error),
        )
        for error in errores
    ]
