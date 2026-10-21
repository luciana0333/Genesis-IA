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
# Identificadores dentro del texto: nEstadoId, cCodPersona / SolicitudArchivos.
_IDENTIFICADOR_CAMEL = re.compile(r"^[a-z]{1,4}(?:[A-Z][a-z0-9]+)+[A-Z]?[a-z0-9]*$")
_IDENTIFICADOR_PASCAL = re.compile(r"^(?:[A-Z][a-z0-9]+){2,}$")
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


_PREFIJOS = ("des", "re", "in", "pre", "sub", "auto")


def es_palabra_valida(palabra: str) -> bool:
    validas = _palabras_validas()
    n = normalizar(palabra)
    if n in validas:
        return True
    # Prefijos comunes: si «activa» es válida, «desactiva» también.
    for prefijo in _PREFIJOS:
        if n.startswith(prefijo) and len(n) - len(prefijo) >= 4 and es_palabra_valida(n[len(prefijo):]):
            return True
    for terminacion, reemplazos in _TERMINACIONES:
        if n.endswith(terminacion) and len(n) - len(terminacion) >= 2:
            for raiz in _variantes_de_raiz(n[: -len(terminacion)]):
                if any(raiz + reemplazo in validas for reemplazo in reemplazos):
                    return True
    return False


_CONECTORES = {"y", "o", "e", "u", "de", "al", "el", "la", "lo", "en", "un", "mi", "su", "tu", "a"}


def separar_palabras(texto: str) -> Optional[List[str]]:
    """
    Separa palabras pegadas en minúsculas con el diccionario de español
    («esquematotalizadoejecutivos» -> ['esquema', 'totalizado', 'ejecutivos']).
    Elige la separación con menos palabras (y, a igual cantidad, palabras más largas).
    None si no hay diccionario o alguna parte no es una palabra conocida.
    """
    n = normalizar(texto)
    if not disponible() or not n.isalpha() or len(n) > 80:
        return None
    # mejor[i]: (cantidad de palabras, -suma de cuadrados de longitudes, cortes) para n[:i].
    mejor: List[Optional[Tuple[int, int, List[int]]]] = [None] * (len(n) + 1)
    mejor[0] = (0, 0, [])
    for fin in range(1, len(n) + 1):
        for inicio in range(max(0, fin - 25), fin):
            anterior = mejor[inicio]
            pieza = n[inicio:fin]
            # Trozos de 1 o 2 letras solo si son conectores (de, y, en...): evita «ti + enda».
            if anterior is None or (len(pieza) <= 2 and pieza not in _CONECTORES) or not es_palabra_valida(pieza):
                continue
            candidato = (anterior[0] + 1, anterior[1] - len(pieza) ** 2, anterior[2] + [fin])
            if mejor[fin] is None or candidato[:2] < mejor[fin][:2]:
                mejor[fin] = candidato
    if mejor[-1] is None:
        return None
    cortes = [0] + mejor[-1][2]
    return [texto[cortes[i]:cortes[i + 1]].lower() for i in range(len(cortes) - 1)]


def _parece_identificador(palabra: str) -> bool:
    """
    Nombres de columnas u objetos escritos dentro de la descripción:
    prefijo en minúsculas + partes con mayúscula inicial (nEstadoId,
    cCodPersona) o PascalCase compuesto (SolicitudArchivos). Una palabra con
    mayúsculas sueltas al final ('clienteYY') no lo es y se revisa.
    """
    return bool(_IDENTIFICADOR_CAMEL.match(palabra) or _IDENTIFICADOR_PASCAL.match(palabra))


def _debe_ignorarse(palabra: str, nombres_objeto: Set[str], texto_en_mayusculas: bool = False) -> bool:
    if len(palabra) < _LONGITUD_MINIMA:
        return True
    # Siglas (RUC, DNI, SQL). Si la descripción está escrita en mayúsculas, solo se toman
    # como siglas las palabras cortas: las demás se revisan (CONSULTA LA ROJSH DEL CLIENTE).
    if palabra.isupper() and (not texto_en_mayusculas or len(palabra) <= 3):
        return True
    if _parece_identificador(palabra):
        return True
    return normalizar(palabra) in nombres_objeto


def _distancia(a: str, b: str) -> int:
    """
    Distancia de edición que cuenta como un solo error el intercambio de dos
    letras vecinas (Fehca -> Fecha), el tipeo más común.
    """
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            costo = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + costo)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


_LETRAS = "abcdefghijklmnopqrstuvwxyzáéíóúñü"


def _a_una_letra(palabra: str) -> Set[str]:
    """Todas las variantes a un cambio de letra: quitar, cambiar, agregar o intercambiar vecinas."""
    partes = [(palabra[:i], palabra[i:]) for i in range(len(palabra) + 1)]
    quitar = {a + b[1:] for a, b in partes if b}
    intercambiar = {a + b[1] + b[0] + b[2:] for a, b in partes if len(b) > 1}
    cambiar = {a + letra + b[1:] for a, b in partes if b for letra in _LETRAS}
    agregar = {a + letra + b for a, b in partes for letra in _LETRAS}
    return quitar | intercambiar | cambiar | agregar


# Letras que se confunden al escribir en español (desactiba → desactiva, actualisa → actualiza).
_CONFUSIONES = {frozenset(par) for par in ("bv", "sz", "cs", "cz", "yi", "gj", "kc", "qc")}


def _es_confusion_tipica(original: str, candidata: str) -> bool:
    """True si la candidata cambia una sola letra por otra que se confunde al escribir."""
    if len(original) != len(candidata):
        return False
    distintas = [(a, b) for a, b in zip(original, candidata) if a != b]
    return len(distintas) == 1 and frozenset(distintas[0]) in _CONFUSIONES


def sugerencias(palabra: str, maximo: int = 1) -> List[str]:
    """
    Palabras parecidas del diccionario, con la misma mayúscula inicial que la
    original. Solo se sugieren palabras que empiezan con la misma letra (los
    errores de tipeo rara vez cambian la primera), ordenadas por cercanía y
    luego por frecuencia. Si no hay una buena candidata, no se sugiere nada.
    """
    corrector = _corrector()
    if corrector is None:
        return []
    original = palabra.lower()
    candidatas = {
        c for c in (corrector.candidates(original) or set())
        if c != original and normalizar(c)[:1] == normalizar(original)[:1]
    }
    # Palabras válidas a un cambio de letra, incluidas formas verbales que el diccionario
    # no trae (Actualisa → Actualiza): s/z, b/v, c/s, letras de más o de menos.
    candidatas |= {
        c for c in _a_una_letra(original)
        if c != original and normalizar(c)[:1] == normalizar(original)[:1] and es_palabra_valida(c)
    }
    # Solo se sugiere si la corrección es casi segura: una letra de diferencia (o dos en
    # palabras largas). Si no, se pide revisar la palabra en vez de adivinar (ROJSH ≠ ROJO).
    tolerancia = 2 if len(original) >= 7 else 1
    candidatas = {c for c in candidatas if _distancia(normalizar(c), normalizar(original)) <= tolerancia}
    def prioridad(candidata: str):
        # 1) más cercana; 2) sin tildes agregadas; 3) confusión típica del español (b/v, s/z...);
        # 4) palabra que el diccionario conoce; 5) la más usada.
        tilde_nueva = any(letra in "áéíóú" and letra not in original for letra in candidata)
        return (
            _distancia(normalizar(candidata), normalizar(original)),
            tilde_nueva,
            not _es_confusion_tipica(original, candidata),
            normalizar(candidata) not in _palabras_validas(),
            -corrector.word_usage_frequency(candidata),
        )

    ordenadas = sorted(candidatas, key=prioridad)[:maximo]
    if palabra.isupper() and len(palabra) > 1:
        ordenadas = [c.upper() for c in ordenadas]
    elif palabra[:1].isupper():
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
    # Descripción escrita en mayúsculas: al menos dos palabras en mayúsculas que existen en
    # español (CONSULTA, CLIENTE). Entonces las mayúsculas no indican siglas.
    en_mayusculas = sum(
        1 for palabra in palabras
        if palabra.isupper() and len(palabra) >= _LONGITUD_MINIMA and es_palabra_valida(palabra)
    ) >= 2
    for palabra in palabras:
        clave = normalizar(palabra)
        if clave in vistas or _debe_ignorarse(palabra, ignorar, en_mayusculas):
            continue
        vistas.add(clave)
        if not es_palabra_valida(palabra):
            resultado.append((palabra, sugerencias(palabra)))
    return resultado


def redactar_error_ortografico(objeto: str, errores: List[Tuple[str, Optional[List[str]]]], documento: str) -> str:
    """
    Mensaje del hallazgo de ortografía: qué palabras están mal y por cuál
    corregir cada una (o que se revise, si no hay sugerencia).
    objeto: "del procedimiento dbo.PA_X", "de la columna cNombre"...
    documento: a qué documenta el diccionario ("del procedimiento", "de la tabla").
    """
    palabras = ", ".join(f"'{palabra}'" for palabra, _ in errores)
    error = "un error de escritura" if len(errores) == 1 else f"{len(errores)} errores de escritura"
    con_sugerencia = [f"'{palabra}' por '{opciones[0]}'" for palabra, opciones in errores if opciones]
    sin_sugerencia = [f"'{palabra}'" for palabra, opciones in errores if not opciones]
    acciones = []
    if con_sugerencia:
        acciones.append("corregir " + _enumerar(con_sugerencia))
    if sin_sugerencia:
        palabra_s = "la palabra " if len(sin_sugerencia) == 1 else "las palabras "
        acciones.append(f"revisar {palabra_s}{_enumerar(sin_sugerencia)} y escribir correctamente la descripción")
    return (
        f"Se {'identificó' if len(errores) == 1 else 'identificaron'} {error} en la descripción {objeto}: "
        f"{palabras}. "
        f"Se recomienda {' y '.join(acciones)}, ya que el diccionario es la documentación oficial "
        f"{documento}."
    )


def _enumerar(elementos: List[str]) -> str:
    return elementos[0] if len(elementos) == 1 else ", ".join(elementos[:-1]) + " y " + elementos[-1]


def elemento_ortografico(objeto: str, errores: List[Tuple[str, Optional[List[str]]]]) -> str:
    """Línea de la lista cuando se agrupan varios errores: "del parámetro @x: 'a' → 'b'"."""
    cambios = ", ".join(
        f"'{palabra}' → '{opciones[0]}'" if opciones else f"'{palabra}'" for palabra, opciones in errores
    )
    return f"Descripción {objeto}: {cambios}"
