class ReglaNegocioError(Exception):
    """Se lanza cuando una operación viola una validación de negocio.
    La API la convierte en un HTTP 400 con el mensaje para el usuario."""


class NoEncontradoError(Exception):
    """El recurso pedido no existe -> HTTP 404."""


class AccesoDenegadoError(Exception):
    """El usuario autenticado no tiene permiso para acceder al recurso -> HTTP 403."""


class CuentaNoHabilitadaError(Exception):
    """Las credenciales son correctas pero la cuenta todavía no puede operar
    (PENDIENTE de validación o RECHAZADA por el administrador del local) -> HTTP 403.
    Lleva el estado para que el frontend muestre el aviso correspondiente."""

    def __init__(self, mensaje, estado, motivo=None):
        super().__init__(mensaje)
        self.estado = estado
        self.motivo = motivo
