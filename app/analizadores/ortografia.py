# -*- coding: utf-8 -*-
"""
ortografia.py
-------------
Detecta palabras mal escritas en las descripciones del diccionario.

- Usa el diccionario oficial de español Perú (RLA-ES, es_PE, el de LibreOffice),
  expandido a todas sus formas en app/reglas/diccionario_es_pe.txt.gz (funciona
  sin internet y sin instalar nada). Licencia: GPL / LGPL / MPL (proyecto RLA-ES).
- Revisa las tildes: si la palabra solo existe con otra tilde («codigo» → «código»,
  «guión» → «guion»), se marca y se sugiere la forma correcta.
- Acepta además formas derivadas a partir de su raíz (prefijos como re- o des-,
  participios, derivados en -dor o -mente) que el diccionario no trae sueltas.
- Ignora nombres de objetos (columnas, tablas), siglas en mayúsculas,
  palabras con mayúsculas internas (nEstadoId) y el vocabulario técnico del
  equipo (app/reglas/vocabulario_tecnico.txt).
"""

import gzip
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

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
_DICCIONARIO_ES = Path(__file__).resolve().parent.parent / "reglas" / "diccionario_es_pe.txt.gz"
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
def _diccionario_es() -> FrozenSet[str]:
    """Todas las palabras del español (en minúsculas y con sus tildes). Vacío si falta el archivo."""
    if not _DICCIONARIO_ES.is_file():
        return frozenset()
    with gzip.open(_DICCIONARIO_ES, "rt", encoding="utf-8") as archivo:
        return frozenset(linea.strip().lower() for linea in archivo if linea.strip())


@lru_cache(maxsize=1)
def _formas_con_tilde() -> Dict[str, Tuple[str, ...]]:
    """Palabra sin tildes -> sus formas correctas («codigo» -> ('código',); «practico» -> ('práctico', ...))."""
    formas: Dict[str, List[str]] = {}
    for palabra in _diccionario_es():
        formas.setdefault(normalizar(palabra), []).append(palabra)
    return {clave: tuple(sorted(valores)) for clave, valores in formas.items()}


@lru_cache(maxsize=1)
def _corrector():
    """
    pyspellchecker, si está instalado: solo para desempatar sugerencias por lo frecuente que es
    cada palabra. Ya no decide qué palabra es válida (su lista viene de subtítulos y está incompleta).
    """
    try:
        from spellchecker import SpellChecker
    except ImportError:  # pragma: no cover - depende del entorno
        return None
    return SpellChecker(language="es")


@lru_cache(maxsize=1)
def _palabras_validas() -> Set[str]:
    """Palabras válidas sin tildes: el diccionario de español y el vocabulario técnico del equipo."""
    return set(_formas_con_tilde()) | _vocabulario_tecnico()


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
    """True si el diccionario de español está en el proyecto."""
    return bool(_diccionario_es())


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
    # Prefijos comunes: si «programados» es válida, «reprogramados» también.
    for prefijo in _PREFIJOS:
        if n.startswith(prefijo) and len(n) - len(prefijo) >= 4 and es_palabra_valida(n[len(prefijo):]):
            return True
    # Sin diccionario completo (falta el archivo), se aceptan además las formas que se deducen de la
    # raíz. Con el diccionario no hace falta: ya trae todas las formas, y deducirlas deja pasar
    # errores (actualisa ≈ actuales).
    if _diccionario_es():
        return False
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
_LETRAS_SIN_TILDE = "abcdefghijklmnopqrstuvwxyzñ"


def _a_una_letra(palabra: str, letras: str = _LETRAS) -> Set[str]:
    """Todas las variantes a un cambio de letra: quitar, cambiar, agregar o intercambiar vecinas."""
    partes = [(palabra[:i], palabra[i:]) for i in range(len(palabra) + 1)]
    quitar = {a + b[1:] for a, b in partes if b}
    intercambiar = {a + b[1] + b[0] + b[2:] for a, b in partes if len(b) > 1}
    cambiar = {a + letra + b[1:] for a, b in partes if b for letra in letras}
    agregar = {a + letra + b for a, b in partes for letra in letras}
    return quitar | intercambiar | cambiar | agregar


# Letras que se confunden al escribir en español (desactiba → desactiva, actualisa → actualiza).
_CONFUSIONES = {frozenset(par) for par in ("bv", "sz", "cs", "cz", "yi", "gj", "kc", "qc")}


def _es_confusion_tipica(original: str, candidata: str) -> bool:
    """True si la candidata cambia una sola letra por otra que se confunde al escribir."""
    if len(original) != len(candidata):
        return False
    distintas = [(a, b) for a, b in zip(original, candidata) if a != b]
    return len(distintas) == 1 and frozenset(distintas[0]) in _CONFUSIONES


def tilde_correcta(palabra: str) -> Optional[List[str]]:
    """
    Si la palabra está bien escrita salvo por la tilde, sus formas correctas («codigo» -> ['código'],
    «guión» -> ['guion']); si no, None. Las palabras del vocabulario técnico no se revisan.
    """
    minuscula = palabra.lower()
    if minuscula in _diccionario_es() or normalizar(palabra) in _vocabulario_tecnico():
        return None
    formas = _formas_con_tilde().get(normalizar(palabra))
    return list(formas) if formas else None


def _falta_una_letra(escrita: str, candidata: str) -> bool:
    """True si la candidata es la palabra escrita con una letra más en algún lugar (vencdos → vencidos)."""
    if len(candidata) != len(escrita) + 1:
        return False
    return any(candidata[:i] + candidata[i + 1:] == escrita for i in range(len(candidata)))


def sugerencias(palabra: str, maximo: int = 1) -> List[str]:
    """
    Palabras parecidas del diccionario, con la misma mayúscula inicial que la
    original. Solo se sugieren palabras que empiezan con la misma letra (los
    errores de tipeo rara vez cambian la primera), ordenadas por cercanía y
    luego por frecuencia. Si no hay una buena candidata, no se sugiere nada.
    """
    formas = _formas_con_tilde()
    if not formas:
        return []
    original = palabra.lower()
    base = normalizar(original)
    # Se busca sin tildes (más rápido) y luego se toman las formas reales con su tilde:
    # palabras a un cambio de letra (s/z, b/v, letras de más o de menos, vecinas intercambiadas)
    # y, en palabras largas, a dos cambios.
    cercanas = _a_una_letra(base, _LETRAS_SIN_TILDE)
    claves = {c for c in cercanas if c in formas}
    if len(base) >= 7 and not claves:
        claves = {c for primera in cercanas for c in _a_una_letra(primera, _LETRAS_SIN_TILDE) if c in formas}
    candidatas = {f for clave in claves if clave[:1] == base[:1] for f in formas[clave] if f != original}
    corrector = _corrector()
    # Solo se sugiere si la corrección es casi segura: una letra de diferencia (o dos en
    # palabras largas). Si no, se pide revisar la palabra en vez de adivinar (ROJSH ≠ ROJO).
    tolerancia = 2 if len(original) >= 7 else 1
    candidatas = {c for c in candidatas if _distancia(normalizar(c), normalizar(original)) <= tolerancia}
    def prioridad(candidata: str):
        # 1) más cercana; 2) le falta una letra (vencdos → vencidos, Cdigo → Código: el error de tipeo más
        # común, antes que cambiar una letra: venados, caigo); 3) sin tildes agregadas; 4) confusión típica
        # del español (b/v, s/z...); 5) la más usada (si pyspellchecker está instalado); 6) orden alfabético.
        tilde_nueva = any(letra in "áéíóú" and letra not in original for letra in candidata)
        return (
            _distancia(normalizar(candidata), normalizar(original)),
            not _falta_una_letra(normalizar(original), normalizar(candidata)),
            tilde_nueva,
            not _es_confusion_tipica(original, candidata),
            -(corrector.word_usage_frequency(candidata) if corrector else 0),
            candidata,
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
    sin_que = falta_que(texto)
    if sin_que:
        resultado.append((sin_que[0], [sin_que[1]]))
    for indice, palabra in enumerate(palabras):
        clave = normalizar(palabra)
        if clave in vistas or _debe_ignorarse(palabra, ignorar, en_mayusculas):
            continue
        vistas.add(clave)
        # Bien escrita salvo la tilde (codigo → código). En una descripción escrita toda en
        # mayúsculas no se exige la tilde: es común omitirla y llenaría el informe de avisos.
        tilde = None if palabra.isupper() else tilde_correcta(palabra)
        anterior = palabras[indice - 1].lower() if indice else ""
        siguiente = palabras[indice + 1].lower() if indice + 1 < len(palabras) else ""
        pasado = _pasado_sin_tilde(palabra, anterior, siguiente)
        if tilde:
            resultado.append((palabra, [_con_mayusculas(f, palabra) for f in tilde]))
        elif pasado:
            resultado.append((palabra, [pasado]))
        elif not es_palabra_valida(palabra):
            resultado.append((palabra, sugerencias(palabra)))
    return resultado


# Tras «que», «el cual» o «se», un verbo terminado en -o casi siempre es el pasado sin su tilde:
# «el usuario el cual solicito la disponibilidad» → «solicitó». «Solicito» existe («yo solicito»),
# pero en una descripción no se escribe en primera persona.
_ANTES_DEL_PASADO = {"que", "cual", "cuales", "quien", "quienes", "se"}


def _pasado_sin_tilde(palabra: str, anterior: str, siguiente: str) -> Optional[str]:
    """«solicitó» si «solicito» va tras «que / el cual / se» (no ante «de»: «que tipo de»)."""
    if anterior not in _ANTES_DEL_PASADO or siguiente == "de" or palabra.isupper():
        return None
    if not palabra.endswith("o") or len(palabra) < 4:
        return None
    forma = palabra[:-1] + "ó"
    return forma if forma.lower() in _diccionario_es() else None


# «Procedimiento almacenado actualiza…» / «Tabla almacena…»: falta el «que» antes del verbo.
# Después del verbo va lo que hace («actualiza el estado», «almacena los créditos»); así no se toma
# como verbo un adjetivo que también lo es («Tabla maestra de agencias»: maestrar).
_INICIO_SIN_QUE = re.compile(
    r"^\s*((?:Procedimiento(?:\s+almacenado)?|Tabla)\s+([a-záéíóúñ]+))\s+"
    r"(?:el|la|los|las|lo|un|una|unos|unas|al|todos|todas|información|datos)\b",
    re.IGNORECASE,
)
_NO_SON_VERBOS = {"para", "contra", "hacia", "sobre", "entre"}


def _es_verbo_conjugado(palabra: str) -> bool:
    """«actualiza» (actualizar), «obtiene» (obtener), «devuelve» (devolver)."""
    # Palabras cortas («de», «se», «la») no se toman como verbo.
    if palabra in _NO_SON_VERBOS or len(palabra) < 4:
        return False
    if palabra.endswith("a"):
        infinitivos = {palabra + "r"}
    elif palabra.endswith("e"):
        infinitivos = {raiz + fin for raiz in _variantes_de_raiz(palabra[:-1]) for fin in ("er", "ir")}
    else:
        return False
    return any(infinitivo in _diccionario_es() for infinitivo in infinitivos)


def falta_que(texto: str) -> Optional[Tuple[str, str]]:
    """('Procedimiento almacenado actualiza', 'Procedimiento almacenado que actualiza') o None."""
    inicio = _INICIO_SIN_QUE.match(texto or "")
    if not inicio or not _es_verbo_conjugado(inicio.group(2).lower()):
        return None
    frase, verbo = inicio.group(1), inicio.group(2)
    return frase, f"{frase[:len(frase) - len(verbo)]}que {verbo}"


def _con_mayusculas(forma: str, original: str) -> str:
    """La forma sugerida con las mayúsculas de la palabra original (Codigo → Código)."""
    if original.isupper() and len(original) > 1:
        return forma.upper()
    return forma[:1].upper() + forma[1:] if original[:1].isupper() else forma


def es_error_de_tilde(palabra: str, opciones: Optional[List[str]]) -> bool:
    """True si la palabra solo se diferencia de la sugerida en la tilde."""
    return bool(opciones) and normalizar(palabra) == normalizar(opciones[0]) and palabra != opciones[0]


def _opciones(palabra: str, opciones: List[str]) -> str:
    """'código', o 'práctico' o 'practicó' cuando la tilde depende del sentido."""
    if es_error_de_tilde(palabra, opciones) and len(opciones) > 1:
        return " o ".join(f"'{o}'" for o in opciones[:2])
    return f"'{opciones[0]}'"


# «Qué hacer» de las faltas de ortografía (texto de la usuaria), igual en tablas y procedimientos.
ACCION_ORTOGRAFIA = (
    "Se recomienda corregir las palabras según las sugerencias proporcionadas o revisar su escritura "
    "si no hay sugerencias, para mantener una documentación clara y correcta."
)


def redactar_error_ortografico(objeto: str, errores: List[Tuple[str, Optional[List[str]]]], documento: str) -> str:
    """
    Mensaje del hallazgo de ortografía: cada palabra con su corrección (o sola, si no hay sugerencia)
    y el «Qué hacer» común. objeto: "del procedimiento dbo.PA_X", "de la columna cNombre"...
    documento: a qué documenta el diccionario (se conserva por compatibilidad con quien llama).
    """
    error = "un error de escritura" if len(errores) == 1 else f"{len(errores)} errores de escritura"
    return (
        f"Se {'identificó' if len(errores) == 1 else 'identificaron'} {error} en la descripción {objeto}: "
        f"{_cambios(errores)}. {ACCION_ORTOGRAFIA}"
    )


def _cambios(errores: List[Tuple[str, Optional[List[str]]]]) -> str:
    """«'codigo' → 'código' (tilde), 'clinete' → 'cliente', 'ROJSH'»."""
    return ", ".join(
        (f"'{palabra}' → {_opciones(palabra, opciones)}"
         + (" (tilde)" if es_error_de_tilde(palabra, opciones) else ""))
        if opciones else f"'{palabra}'"
        for palabra, opciones in errores
    )


def _enumerar(elementos: List[str]) -> str:
    return elementos[0] if len(elementos) == 1 else ", ".join(elementos[:-1]) + " y " + elementos[-1]


def elemento_ortografico(objeto: str, errores: List[Tuple[str, Optional[List[str]]]]) -> str:
    """Línea de la lista cuando se agrupan varios errores: "del parámetro @x: 'a' → 'b'"."""
    return f"Descripción {objeto}: {_cambios(errores)}"
