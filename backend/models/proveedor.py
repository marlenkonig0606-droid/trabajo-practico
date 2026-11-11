import re


def normalizar_cuit(cuit):
    return re.sub(r"[^0-9]", "", cuit)