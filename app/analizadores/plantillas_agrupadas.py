"""Plantillas de «agrupar_casos» que comparten Reportes y Procedimientos (mismo texto en los dos módulos)."""

from app.analizadores.agrupar_casos import Plantilla
from app.analizadores.esquema_entre_bases import QUE_HACER_ESQUEMA_ENTRE_BASES

PLANTILLA_ESQUEMA_ENTRE_BASES = Plantilla(
    parrafo="Se verificó el uso de las tablas {casos} de otra base de datos sin indicar el esquema correspondiente.",
    lista="Se verificó el uso de las siguientes tablas de otra base de datos sin indicar el esquema correspondiente",
    que_hacer=QUE_HACER_ESQUEMA_ENTRE_BASES,
    fila="Tabla",
)

# Siempre el mismo caso («COLLATE DATABASE_DEFAULT»): su mensaje una vez, con las líneas arriba de la tarjeta.
PLANTILLA_COLLATE_DATABASE_DEFAULT = Plantilla()
