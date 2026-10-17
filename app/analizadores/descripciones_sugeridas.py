# -*- coding: utf-8 -*-
"""
Descripciones sugeridas para el diccionario («Generar diccionario faltante»).

Se deducen del nombre según el manual de CAJA ICA: prefijo del tipo
(c, n, d, b) + palabras en PascalCase (nClienteId, dFechaRegistro). Se
redactan en español correcto con tres apoyos, todos locales:

- el glosario (app/reglas/glosario_diccionario.txt): abreviaturas, géneros y
  adjetivos propios de la Caja; se puede ampliar;
- el diccionario del corrector ortográfico (pyspellchecker) para las tildes
  (telefono -> teléfono);
- spaCy (es_core_news_sm), si está instalado, para el género y el singular.
  Sin spaCy se usan las reglas del español.

Son un punto de partida: el script las marca «Sugerida: revisar y mejorar».
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

_GLOSARIO = Path(__file__).resolve().parents[1] / "reglas" / "glosario_diccionario.txt"

_PALABRAS_NOMBRE = re.compile(r"[A-ZÁÉÍÓÚÑ]{2,}(?=[A-ZÁÉÍÓÚÑ][a-záéíóúñ]|[^A-Za-zÁÉÍÓÚÑáéíóúñ]|$)|[A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]+|\d+")
_PREFIJO = re.compile(r"^[a-z]{1,2}(?=[A-ZÁÉÍÓÚÑ])")

# Primeras palabras que nombran el dato: «Monto del desembolso», «Código del cliente».
_CABEZAS = {
    "monto", "importe", "código", "número", "cantidad", "tipo", "estado", "nombre", "descripción", "tasa",
    "porcentaje", "saldo", "plazo", "correo", "teléfono", "dirección", "valor", "total", "fecha", "hora",
    "observación", "motivo", "detalle", "razón", "documento", "clave", "nivel", "orden", "categoría", "glosa",
    "apellido", "celular", "edad", "sexo", "profesión", "ocupación", "nacionalidad", "firma", "foto", "ubigeo",
}
# Con estas el complemento va sin artículo: «Fecha de registro», «Tipo de documento».
_SIN_ARTICULO = {"fecha", "hora", "número", "tipo", "tasa", "porcentaje", "plazo", "nivel", "categoría", "motivo", "saldo"}
_VERBOS_BIT = {"es", "tiene", "requiere", "permite", "aplica", "esta", "está", "posee", "usa", "genera", "envia", "envía"}
_ACCIONES = {
    "sel": "Consulta", "lis": "Lista", "listar": "Lista", "ins": "Registra", "reg": "Registra",
    "upd": "Actualiza", "act": "Actualiza", "del": "Elimina", "eli": "Elimina",
}


@lru_cache(maxsize=1)
def _glosario() -> Dict[str, object]:
    secciones: Dict[str, object] = {"abreviaturas": {}, "femeninas": set(), "masculinas": set(), "adjetivos": set()}
    actual = None
    for linea in _GLOSARIO.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("[") and linea.endswith("]"):
            actual = linea[1:-1].strip().lower()
            continue
        if actual == "abreviaturas" and "=" in linea:
            abreviatura, palabra = (parte.strip().lower() for parte in linea.split("=", 1))
            secciones["abreviaturas"][abreviatura] = palabra
        elif actual in secciones and actual != "abreviaturas":
            secciones[actual].add(linea.lower())
    return secciones


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def _palabras_con_tilde() -> Dict[str, str]:
    """Del diccionario del corrector: forma sin tildes -> forma correcta más usada."""
    try:
        from spellchecker import SpellChecker
    except ImportError:
        return {}
    frecuencias = SpellChecker(language="es").word_frequency
    indice: Dict[str, str] = {}
    for palabra in frecuencias.keys():
        clave = _sin_tildes(palabra)
        if clave != palabra and (clave not in indice or frecuencias[palabra] > frecuencias[indice[clave]]):
            indice[clave] = palabra
    # Solo se corrige si la forma sin tilde no es una palabra válida por sí misma (periodo, fecha...).
    return {clave: palabra for clave, palabra in indice.items() if clave not in frecuencias}


@lru_cache(maxsize=1)
def _spacy():
    try:
        import spacy
        return spacy.load("es_core_news_sm", disable=["parser", "ner"])
    except Exception:  # sin spaCy o sin su modelo: se usan las reglas del español
        return None


def spacy_disponible() -> bool:
    return _spacy() is not None


def _acentuar(palabra: str) -> str:
    return _palabras_con_tilde().get(palabra, palabra)


def _palabras(nombre: str) -> List[str]:
    """nClienteId -> ['cliente', 'identificador']; con abreviaturas expandidas y tildes."""
    nombre = nombre.lstrip("@")
    sin_prefijo = _PREFIJO.sub("", nombre)
    partes = _PALABRAS_NOMBRE.findall(sin_prefijo.replace("_", " ")) or [sin_prefijo]
    abreviaturas = _glosario()["abreviaturas"]
    palabras = []
    for parte in partes:
        if parte.isupper() and len(parte) > 1:  # siglas: RUC, DNI, CCI
            palabras.append(parte)
            continue
        minuscula = parte.lower()
        palabras.append(_acentuar(abreviaturas.get(minuscula, minuscula)))
    return palabras


def prefijo(nombre: str) -> str:
    m = _PREFIJO.match(nombre.lstrip("@"))
    return m.group(0) if m else ""


def _es_femenina(palabra: str) -> bool:
    glosario = _glosario()
    if palabra in glosario["femeninas"]:
        return True
    if palabra in glosario["masculinas"] or palabra.isupper():
        return False
    if re.search(r"(ción|sión|dad|tad|tud|umbre|ez|sis|ie)$", palabra):
        return True
    if re.search(r"(aje|or|o|ón)$", palabra):
        return False
    nlp = _spacy()
    if nlp is not None:
        token = nlp(f"Registra {palabra} nuevos")[1]
        genero = token.morph.get("Gender")
        if token.pos_ == "NOUN" and genero:
            return genero[0] == "Fem"
    return palabra.endswith("a")


def _singular(palabra: str) -> str:
    if palabra.isupper() or not palabra.endswith("s") or palabra.endswith(("is", "us")):
        return palabra
    nlp = _spacy()
    if nlp is not None:
        token = nlp(f"Registra {palabra} nuevos")[1]
        if token.pos_ == "NOUN" and token.morph.get("Number") == ["Plur"] and token.lemma_:
            return _acentuar(token.lemma_)
    if palabra.endswith("ces"):
        return palabra[:-3] + "z"
    if palabra.endswith("iones"):
        return _acentuar(palabra[:-5] + "ion")
    # «solicitudes» -> solicitud, «clientes» -> cliente: se queda la forma que es una palabra real.
    candidatas = [palabra[:-2], palabra[:-1]] if palabra.endswith("es") and len(palabra) > 4 else [palabra[:-1]]
    for candidata in candidatas:
        if _reconocida(candidata) and len(candidata) > 2:
            return candidata
    return palabra[:-1]


def _plural(palabra: str) -> str:
    if palabra.isupper():
        return palabra
    if palabra.endswith("z"):
        return palabra[:-1] + "ces"
    if palabra.endswith("ión"):
        return palabra[:-3] + "iones"
    if palabra[-1] in "aeiouáéó":
        return palabra + "s"
    return palabra + "es"


def _frase(palabras: List[str]) -> str:
    """['tipo', 'documento'] -> 'tipo de documento'; ['cuenta', 'principal'] -> 'cuenta principal'."""
    adjetivos = _glosario()["adjetivos"]
    frase = palabras[0]
    for palabra in palabras[1:]:
        frase += f" {palabra}" if palabra in adjetivos or palabra.isdigit() else f" de {palabra}"
    return frase


def _con_de(palabras: List[str], plural: bool = False, articulo: bool = True) -> str:
    """'del cliente', 'de la agencia', 'de los clientes' (o 'de registro' sin artículo)."""
    primera = palabras[0]
    if not articulo:
        return f"de {_frase(palabras)}"
    femenina = _es_femenina(_singular(primera))
    frase = _frase(([_plural(primera)] if plural else [primera]) + palabras[1:])
    if primera.isupper():
        return f"de {frase}"
    if plural:
        return f"de {'las' if femenina else 'los'} {frase}"
    return f"de la {frase}" if femenina else f"del {frase}"


def _capitalizar(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _entidad(nombre_objeto: str) -> List[str]:
    """Tabla 'Clientes' o 'SolicitudArchivos' -> ['cliente'] / ['solicitud', 'archivos']."""
    palabras = _palabras(nombre_objeto)
    return [_singular(palabras[0])] + palabras[1:] if palabras else []


_AUDITORIA = {
    ("usuario", "registro"): "Usuario que realizó el registro",
    ("fecha", "registro"): "Fecha y hora en que se realizó el registro",
    ("usuario", "modificación"): "Usuario que realizó la última modificación",
    ("fecha", "modificación"): "Fecha y hora de la última modificación",
    ("usuario", "actualización"): "Usuario que realizó la última actualización",
    ("fecha", "actualización"): "Fecha y hora de la última actualización",
}


def _reconocida(palabra: str) -> bool:
    """Palabra del glosario, sigla, número o palabra válida del español: con otras no se inventa nada."""
    if palabra.isupper() or palabra.isdigit():
        return True
    glosario = _glosario()
    if palabra in glosario["abreviaturas"].values() or any(palabra in glosario[s] for s in ("femeninas", "masculinas", "adjetivos")):
        return True
    try:
        from app.analizadores.ortografia import disponible, es_palabra_valida
    except ImportError:
        return True
    return not disponible() or es_palabra_valida(palabra)


def sugerir_columna(columna: str, tabla: str, es_parametro: bool = False) -> Optional[str]:
    """Descripción de una columna (o parámetro) según su nombre y el de su tabla (o procedimiento)."""
    palabras = _palabras(columna)
    if not palabras or not all(_reconocida(p) for p in palabras):
        return None
    entidad = _entidad(tabla)
    tipo = prefijo(columna)

    if tuple(palabras) in _AUDITORIA:
        return _AUDITORIA[tuple(palabras)]

    if palabras[-1] == "identificador" and len(palabras) > 1:
        referida = palabras[:-1]
        if [_singular(p).lower() for p in referida] == [_singular(p).lower() for p in entidad]:
            return f"Identificador {_con_de(entidad)}" if es_parametro else f"Identificador único {_con_de(entidad)}"
        femenina = _es_femenina(referida[0])
        return f"Identificador {_con_de(referida)} {'asociada' if femenina else 'asociado'}"
    if palabras == ["identificador"]:
        return f"Identificador único {_con_de(entidad)}" if entidad else "Identificador único del registro"

    if tipo == "b":
        if palabras[0] in _VERBOS_BIT:
            return _capitalizar(f"Indica si {' '.join(['está' if palabras[0] == 'esta' else palabras[0]] + palabras[1:])}")
        if len(palabras) == 1:
            return f"Indica si el registro está {palabras[0]}"
        return f"Indica si {_frase(palabras)}"

    if tipo == "d" and palabras[0] != "fecha":
        return f"Fecha {_con_de(palabras, articulo=False)}"

    if palabras[0] in _CABEZAS:
        cabeza, resto = palabras[0], palabras[1:]
        if resto and resto[0] in _glosario()["adjetivos"]:
            return _capitalizar(_frase(palabras))
        if resto:
            return _capitalizar(f"{cabeza} {_con_de(resto, articulo=cabeza not in _SIN_ARTICULO)}")
        return _capitalizar(f"{cabeza} {_con_de(entidad)}") if entidad else _capitalizar(cabeza)

    return _capitalizar(_frase(palabras))


def sugerir_tabla(tabla: str) -> Optional[str]:
    entidad = _entidad(tabla)
    if not entidad or not all(_reconocida(p) for p in entidad):
        return None
    return f"Registra la información {_con_de(entidad, plural=True)}"


def sugerir_procedimiento(procedimiento: str) -> Optional[str]:
    """PA_Tabla_Acción_Finalidad -> 'Consulta los datos del cliente por su identificador'."""
    partes = [p for p in procedimiento.split("_") if p]
    if len(partes) < 3 or partes[0].upper() != "PA":
        return None
    entidad = _entidad(partes[1])
    accion = _ACCIONES.get(partes[2].lower())
    if not entidad or not accion or not all(_reconocida(p) for p in entidad):
        return None
    femenina = _es_femenina(entidad[0])
    if accion == "Registra":
        base = f"Registra {'una nueva' if femenina else 'un nuevo'} {_frase(entidad)}"
    elif accion == "Lista":
        base = f"Lista {'las' if femenina else 'los'} {_frase([_plural(entidad[0])] + entidad[1:])}"
    elif accion == "Elimina":
        base = f"Elimina {'la' if femenina else 'el'} {_frase(entidad)}"
    else:
        base = f"{accion} los datos {_con_de(entidad)}"
    finalidad = _palabras("".join(partes[3:])) if len(partes) > 3 else []
    if finalidad[:1] == ["por"] and len(finalidad) > 1:
        detalle = finalidad[1:]
        if detalle == ["identificador"]:
            return f"{base} por su identificador"
        return f"{base} por {_frase(detalle)}"
    if len(finalidad) == 1 and accion in ("Consulta", "Lista"):
        # PA_Credito_Sel_Pendientes -> «Consulta los créditos pendientes».
        plural = _frase([_plural(entidad[0])] + entidad[1:])
        return f"{accion} {'las' if femenina else 'los'} {plural} {finalidad[0]}"
    if finalidad:
        return f"{base} ({' '.join(finalidad)})"
    return base


def precargar() -> None:
    """Carga de antemano el glosario, las tildes y spaCy (se llama al iniciar el servidor)."""
    _glosario()
    _palabras_con_tilde()
    if _spacy() is None:
        print("AVISO: spaCy no está instalado; las descripciones sugeridas usarán solo las reglas del español.")


def palabras_reconocidas() -> Set[str]:
    """Para pruebas: abreviaturas del glosario."""
    return set(_glosario()["abreviaturas"])
