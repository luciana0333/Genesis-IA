# -*- coding: utf-8 -*-
"""Base común para todas las reglas del proyecto."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReglaDiccionario:
    codigo: str
    nombre: str
    severidad: str
    descripcion: str
    alcance: str
    activo: bool = True
