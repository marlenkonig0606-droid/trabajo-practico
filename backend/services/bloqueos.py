"""
BLOQUEO EN MEMORIA POR PRODUCTO
-------------------------------
Problema (condición de carrera):
    Usuario A y usuario B hacen clic en "Empaquetar" al mismo tiempo, los dos
    piden 300 unidades de Agua y en el CD hay 500.
        A lee: libre = 500  ✔ alcanza
        B lee: libre = 500  ✔ alcanza        <- todavía no vio lo de A
        A reserva 300
        B reserva 300                         <- ¡600 reservadas sobre 500!

Solución: "leer, validar y reservar" tiene que ser UNA operación que solo
un usuario por vez puede hacer sobre ese producto.

    with GestorBloqueos().bloquear([(cd_id, producto_id), ...]):
        with db.transaccion():
            # sección crítica: nadie más puede tocar estos productos acá adentro
            ...

- Hay un candado (threading.Lock) por cada par (sucursal, producto). Así dos
  usuarios que piden productos DISTINTOS no se esperan entre sí.
- Si el candado está tomado, el segundo usuario espera (como mucho TIMEOUT
  segundos) y después ve el stock ya actualizado por el primero.
- Es un Singleton: todos los services tienen que compartir los mismos candados.
- REGLA para evitar deadlock (dos usuarios esperándose para siempre):
    1) los candados de producto se toman SIEMPRE ordenados (sorted), y
    2) SIEMPRE antes de abrir db.transaccion(), nunca adentro.

Limitación (para la defensa): el candado vive en la memoria del proceso de
Flask. Si corrieran varios servidores a la vez no se verían entre sí; por eso
además el UPDATE en StockService tiene la condición `disponible - reservado >= ?`
(la base de datos es la última barrera).
"""
import threading
from contextlib import contextmanager

from services.excepciones import ReglaNegocioError


class GestorBloqueos:
    _instancia = None
    TIMEOUT = 5  # segundos que un usuario espera a que el otro libere el producto

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._candados = {}
            cls._instancia._candado_del_diccionario = threading.Lock()
        return cls._instancia

    def _candado_de(self, sucursal_id, producto_id):
        # El propio diccionario también se protege: dos hilos podrían crear
        # a la vez el candado del mismo producto.
        with self._candado_del_diccionario:
            clave = (sucursal_id, producto_id)
            if clave not in self._candados:
                self._candados[clave] = threading.Lock()
            return self._candados[clave]

    @contextmanager
    def bloquear(self, claves):
        """claves: lista de (sucursal_id, producto_id)."""
        tomados = []
        try:
            for sucursal_id, producto_id in sorted(set(claves)):   # orden fijo
                candado = self._candado_de(sucursal_id, producto_id)
                if not candado.acquire(timeout=self.TIMEOUT):
                    raise ReglaNegocioError(
                        f"El producto {producto_id} está siendo tomado por otro usuario. "
                        "Intentá de nuevo en unos segundos.")
                tomados.append(candado)
            yield
        finally:
            for candado in reversed(tomados):   # se liberan SIEMPRE, aunque haya error
                candado.release()
