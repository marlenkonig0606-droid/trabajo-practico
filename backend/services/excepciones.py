class ReglaNegocioError(Exception):
    """Se lanza cuando una operación viola una validación de negocio.
    La API la convierte en un HTTP 400 con el mensaje para el usuario."""
    status_code  = 400
    mensaje_especial = "bla"



class NoEncontradoError(Exception):
    """El recurso pedido no existe -> HTTP 404."""
    status_code = 404
    mensaje_especial = "no hay solucion"
