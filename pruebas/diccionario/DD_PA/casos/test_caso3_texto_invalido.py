# -*- coding: utf-8 -*-
"""
CASO 3: El texto no es un CREATE/ALTER PROCEDURE valido.
RESULTADO ESPERADO: 0 hallazgos (no debe reventar ni inventar errores).
"""

from app.analizadores.diccionario import verificar_diccionario

PROCEDIMIENTO = """
-- esto no es un procedimiento valido
SELECT * FROM Persona
"""

DICCIONARIO = ""

if __name__ == "__main__":
    hallazgos = verificar_diccionario(PROCEDIMIENTO, DICCIONARIO)
    print(f"Hallazgos encontrados: {len(hallazgos)} (se esperaba: 0)\n")
    for h in hallazgos:
        print(h)