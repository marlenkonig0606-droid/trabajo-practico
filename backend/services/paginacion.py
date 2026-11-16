"""Búsqueda y paginación de listados (las usan las rutas de la API).

La paginación se hace en el backend: la API devuelve solo la página pedida y
el total de resultados, así el navegador no recibe todos los registros."""
import math
import unicodedata

from services.excepciones import ReglaNegocioError

POR_PAGINA_DEFECTO = 10
POR_PAGINA_MAXIMO = 100


def normalizar(texto):
    """Minúsculas y sin acentos: 'Café Molido' -> 'cafe molido'.
    Permite buscar sin distinguir mayúsculas, minúsculas ni tildes."""
    if texto is None:
        return ""
    sin_acentos = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn").lower()


def coincide(busqueda, *textos):
    """True si la búsqueda aparece como parte de alguno de los textos
    ('rem' coincide con 'Remera básica')."""
    buscado = normalizar(busqueda).strip()
    return not buscado or any(buscado in normalizar(t) for t in textos)


def leer_paginacion(args):
    """Lee ?pagina=&por_pagina= de la URL. Devuelve None si no se pidió paginar
    (así las rutas siguen devolviendo la lista completa a quien no pagina)."""
    if "pagina" not in args:
        return None
    try:
        pagina = int(args.get("pagina", 1))
        por_pagina = int(args.get("por_pagina", POR_PAGINA_DEFECTO))
    except ValueError as error:
        raise ReglaNegocioError("pagina y por_pagina deben ser números enteros") from error
    if pagina < 1 or not 1 <= por_pagina <= POR_PAGINA_MAXIMO:
        raise ReglaNegocioError(
            f"La página debe ser 1 o más y por_pagina entre 1 y {POR_PAGINA_MAXIMO}")
    return pagina, por_pagina


def respuesta_paginada(items, total, pagina, por_pagina):
    return {
        "items": items,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "paginas": max(1, math.ceil(total / por_pagina)),
    }


def paginar(items, paginacion):
    """Pagina una lista ya filtrada. Sin paginación devuelve la lista tal cual."""
    if paginacion is None:
        return items
    pagina, por_pagina = paginacion
    inicio = (pagina - 1) * por_pagina
    return respuesta_paginada(items[inicio:inicio + por_pagina], len(items),
                              pagina, por_pagina)
