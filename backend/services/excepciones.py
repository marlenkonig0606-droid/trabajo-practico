class ReglaNegocioError(Exception):
    """Se lanza cuando una operación viola una validación de negocio.
    La API la convierte en un HTTP 400 con el mensaje para el usuario."""


class NoEncontradoError(Exception):
    """El recurso pedido no existe -> HTTP 404."""


class AccesoDenegadoError(Exception):
    """El usuario autenticado no tiene permiso para acceder al recurso -> HTTP 403."""
