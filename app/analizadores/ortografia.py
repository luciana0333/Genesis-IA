# -*- coding: utf-8 -*-
"""
ortografia.py
-------------
Detecta palabras mal escritas en las descripciones del diccionario.

- Usa el diccionario de español de pyspellchecker (funciona sin internet).
- No exige tildes: "unico" y "único" se aceptan por igual.
- Acepta las formas del español a partir de su raíz (plurales, femeninos,
  conjugaciones, participios, derivados en -dor o -mente), porque el
  diccionario base solo trae la forma principal de cada palabra.
- Ignora nombres de objetos (columnas, tablas), siglas en mayúsculas,
  palabras con mayúsculas internas (nEstadoId) y el vocabulario técnico del
  equipo (app/reglas/vocabulario_tecnico.txt).
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
# Fragmentos sin espacios; si contienen _ . @ # $ son identificadores técnicos
# (sys.sp_addextendedproperty, @level2name, TB_Estado) y no se revisan.
_FRAGMENTO = re.compile(r"[\w@#$.]+")
_IDENTIFICADOR_TECNICO = re.compile(r"[_@#$]|\w\.\w")
# Verbos con cambio de raíz: puede -> poder, tiene -> tener, sirve -> servir.
_CAMBIOS_DE_RAIZ = (("ue", "o"), ("ie", "e"), ("i", "e"))
_VOCABULARIO = Path(__file__).resolve().parent.parent / "reglas" / "vocabulario_tecnico.txt"
_LONGITUD_MINIMA = 3

# Terminación -> terminaciones de la forma base que se prueban en su lugar.
_TERMINACIONES = (
    # participios y adjetivos verbales
    ("ados", ("ar", "ado")), ("adas", ("ar", "ado")), ("ado", ("ar",)), ("ada", ("ar", "ado")),
    ("idos", ("er", "ir", "ido")), ("idas", ("er", "ir", "ido")), ("ido", ("er", "ir")), ("ida", ("er", "ir", "ido")),
    # gerundios
    ("ando", ("ar",)), ("iendo", ("er", "ir")),
    # derivados agentivos: identificador -> identificar
    ("dores", ("r",)), ("doras", ("r",)), ("dora", ("r",)), ("dor", ("r",)),
    # sustantivos de acción: actualización -> actualizar
    ("ciones", ("r",)), ("cion", ("r",)),
    # adverbios
    ("mente", ("",)),
    # conjugaciones frecuentes en descripciones
    ("amos", ("ar",)), ("emos", ("er",)), ("imos", ("ir",)),
    ("an", ("ar", "a")), ("en", ("er", "ir", "e")),
    # infinitivos que el diccionario solo trae por su familia: auditar <- auditor
    ("ar", ("or", "o", "a", "acion")), ("er", ("or", "o", "imiento")), ("ir", ("or", "o", "cion")),
    # plurales
    ("es", ("",)), ("s", ("",)),
    # género y persona: registra -> registrar, encuentra -> encuentro
    ("a", ("ar", "o", "e", "")), ("o", ("ar", "er", "ir", "a", "e")), ("e", ("er", "ir", "ar", "a", "o")),
)


def normalizar(palabra: str) -> str:
    """Minúsculas y sin tildes (la ñ se conserva)."""
    descompuesta = unicodedata.normalize("NFD", palabra.lower().replace("ñ", "\0"))
    sin_tildes = "".join(c for c in descompuesta if unicodedata.category(c) != "Mn")
    return sin_tildes.replace("\0", "ñ")


@lru_cache(maxsize=1)
def _corrector():
    """Carga el diccionario una sola vez. None si pyspellchecker no está instalado."""
    try:
        from spellchecker import SpellChecker
    except ImportError:  # pragma: no cover - depende del entorno
        return None
    return SpellChecker(language="es")


@lru_cache(maxsize=1)
def _palabras_validas() -> Set[str]:
    corrector = _corrector()
    base = {normalizar(p) for p in corrector.word_frequency.dictionary} if corrector else set()
    return base | _vocabulario_tecnico()


@lru_cache(maxsize=1)
def _vocabulario_tecnico() -> Set[str]:
    if not _VOCABULARIO.is_file():
        return set()
    palabras = set()
    for linea in _VOCABULARIO.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea:
            palabras.add(normalizar(linea))
    return palabras


def disponible() -> bool:
    """True si el corrector de español está instalado."""
    return _corrector() is not None


def _variantes_de_raiz(raiz: str) -> Set[str]:
    """La raíz tal cual y con el cambio vocálico revertido (pued -> pod)."""
    variantes = {raiz}
    for actual, original in _CAMBIOS_DE_RAIZ:
        posicion = raiz.rfind(actual)
        if posicion > 0:
            variantes.add(raiz[:posicion] + original + raiz[posicion + len(actual):])
    return variantes


def es_palabra_valida(palabra: str) -> bool:
    validas = _palabras_validas()
    n = normalizar(palabra)
    if n in validas:
        return True
    for terminacion, reemplazos in _TERMINACIONES:
        if n.endswith(terminacion) and len(n) - len(terminacion) >= 2:
            for raiz in _variantes_de_raiz(n[: -len(terminacion)]):
                if any(raiz + reemplazo in validas for reemplazo in reemplazos):
                    return True
    return False


def _debe_ignorarse(palabra: str, nombres_objeto: Set[str]) -> bool:
    if len(palabra) < _LONGITUD_MINIMA:
        return True
    if palabra.isupper():  # siglas: RUC, DNI, SQL
        return True
    if any(c.isupper() for c in palabra[1:]):  # nEstadoId, SolicitudArchivos
        return True
    return normalizar(palabra) in nombres_objeto


def sugerencias(palabra: str, maximo: int = 1) -> List[str]:
    """Palabras parecidas del diccionario (la más frecuente primero), con la
    misma mayúscula inicial que la palabra original."""
    corrector = _corrector()
    if corrector is None:
        return []
    candidatas = corrector.candidates(palabra.lower()) or set()
    candidatas.discard(palabra.lower())
    ordenadas = sorted(candidatas, key=lambda c: -corrector.word_usage_frequency(c))[:maximo]
    if palabra[:1].isupper():
        ordenadas = [c[:1].upper() + c[1:] for c in ordenadas]
    return ordenadas


def palabras_mal_escritas(
    texto: str, nombres_objeto: Iterable[str] = ()
) -> List[Tuple[str, Optional[List[str]]]]:
    """
    Devuelve [(palabra, sugerencias)] por cada palabra mal escrita del texto,
    sin repetir. Si el corrector no está instalado devuelve [].
    """
    if not disponible() or not texto:
        return []
    ignorar = {normalizar(n) for n in nombres_objeto if n}
    resultado: List[Tuple[str, Optional[List[str]]]] = []
    vistas: Set[str] = set()
    palabras = [
        palabra
        for fragmento in _FRAGMENTO.findall(texto)
        if not _IDENTIFICADOR_TECNICO.search(fragmento.strip("."))
        for palabra in _PALABRA.findall(fragmento)
    ]
    for palabra in palabras:
        clave = normalizar(palabra)
        if clave in vistas or _debe_ignorarse(palabra, ignorar):
            continue
        vistas.add(clave)
        if not es_palabra_valida(palabra):
            resultado.append((palabra, sugerencias(palabra)))
    return resultado
