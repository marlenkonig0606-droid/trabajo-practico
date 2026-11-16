"""Base de DEMOSTRACIÓN compartida por todo el equipo.

database/demo/datos_demo.db se genera con generar_datos_demo.py (casi dos años
de operación simulada con los servicios reales) y se sube al repositorio, así
todos ven exactamente los mismos datos.

- Al iniciar el backend:
    * si todavía no existe tp_cd_locales.db, se crea como copia de la base de demo;
    * si existe pero es de una versión de datos ANTERIOR (PRAGMA user_version
      menor que la de la base de demo), se guarda un respaldo y se reemplaza
      por la base de demo. Así, con solo hacer git pull y python app.py, todos
      quedan con los mismos datos. Pasa una sola vez por cada versión nueva.
- restaurar_demo.py reemplaza la base actual por la de demo (guardando una
  copia de respaldo de la anterior)."""
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime

CARPETA = os.path.dirname(os.path.abspath(__file__))
BASE_DEMO = os.path.join(CARPETA, "demo", "datos_demo.db")
BASE_TRABAJO = os.path.join(CARPETA, "..", "tp_cd_locales.db")


# Versión de los datos de demostración. Se guarda dentro de la base de demo
# (PRAGMA user_version); generar_datos_demo.py la escribe al generarla.
VERSION_DATOS = 20261116


def version_de(ruta):
    # Se cierra la conexión SÍ o SÍ: en Windows un archivo abierto no se puede mover.
    # (with sqlite3.connect(...) solo confirma la transacción, no la cierra).
    with closing(sqlite3.connect(ruta)) as cx:
        return cx.execute("PRAGMA user_version").fetchone()[0]


def preparar_base_de_trabajo():
    """Deja tp_cd_locales.db con los datos del equipo:
    - no existe -> se copia la base de demo;
    - existe pero es de una versión anterior -> respaldo + base de demo;
    - ya está al día -> no se toca (se conservan los cambios hechos después)."""
    if not os.path.exists(BASE_DEMO):
        return
    if not os.path.exists(BASE_TRABAJO):
        shutil.copyfile(BASE_DEMO, BASE_TRABAJO)
        print("Se creó tp_cd_locales.db con los datos de demostración del equipo.")
        return
    if version_de(BASE_TRABAJO) < version_de(BASE_DEMO):
        try:
            restaurar_demo()
        except PermissionError:
            print("AVISO: no se pudo actualizar tp_cd_locales.db porque otro programa la está "
                  "usando (¿quedó otro 'python app.py' abierto?). Cerralo y volvé a iniciar.")


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
