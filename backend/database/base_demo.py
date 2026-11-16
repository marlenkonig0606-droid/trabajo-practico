"""Base de DEMOSTRACIÓN compartida por todo el equipo.

database/demo/datos_demo.db se genera con generar_datos_demo.py (casi dos años
de operación simulada con los servicios reales) y se sube al repositorio, así
todos ven exactamente los mismos datos.

- Al iniciar el backend, si todavía no existe tp_cd_locales.db, se crea como
  copia de la base de demo.
- restaurar_demo.py reemplaza la base actual por la de demo (guardando una
  copia de respaldo de la anterior)."""
import os
import shutil
from datetime import datetime

CARPETA = os.path.dirname(os.path.abspath(__file__))
BASE_DEMO = os.path.join(CARPETA, "demo", "datos_demo.db")
BASE_TRABAJO = os.path.join(CARPETA, "..", "tp_cd_locales.db")


def preparar_base_de_trabajo():
    """Primera vez: copia la base de demo. Si ya hay una base, no la toca."""
    if not os.path.exists(BASE_TRABAJO) and os.path.exists(BASE_DEMO):
        shutil.copyfile(BASE_DEMO, BASE_TRABAJO)
        print("Se creó tp_cd_locales.db con los datos de demostración del equipo.")


def restaurar_demo():
    """Reemplaza la base de trabajo por la de demo; la anterior queda de respaldo."""
    if not os.path.exists(BASE_DEMO):
        raise SystemExit("No se encontró database/demo/datos_demo.db")
    if os.path.exists(BASE_TRABAJO):
        respaldo = os.path.join(os.path.dirname(BASE_TRABAJO),
                                f"respaldo_{datetime.now():%Y%m%d_%H%M%S}.db")
        shutil.move(BASE_TRABAJO, respaldo)
        print(f"La base anterior quedó guardada como {os.path.basename(respaldo)}")
    shutil.copyfile(BASE_DEMO, BASE_TRABAJO)
    print("Listo: tp_cd_locales.db tiene los datos de demostración del equipo.")
