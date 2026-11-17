"""Inicialización de la base local desde la plantilla completa de demostración."""
import os
import shutil

CARPETA = os.path.dirname(os.path.abspath(__file__))
BASE_DEMO = os.path.join(CARPETA, "demo", "datos_demo.db")
BASE_TRABAJO = os.path.join(CARPETA, "..", "tp_cd_locales.db")


# generar_datos_demo.py guarda esta versión en la base de demostración.
VERSION_DATOS = 20261116


def preparar_base_de_trabajo():
    """Crea la base local completa solo si todavía no existe."""
    if os.path.exists(BASE_TRABAJO):
        return
    if not os.path.isfile(BASE_DEMO):
        raise FileNotFoundError(f"No se encontró la plantilla de datos: {BASE_DEMO}")
    shutil.copyfile(BASE_DEMO, BASE_TRABAJO)
    print("Se creó tp_cd_locales.db con la plantilla completa de demostración.")
