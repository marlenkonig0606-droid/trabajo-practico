"""Cálculos de análisis para los reportes gerenciales.

Son funciones puras (reciben listas, devuelven diccionarios): no tocan la base,
así se pueden probar con datos conocidos y no se mezclan con el SQL."""
import math
import statistics
from datetime import date, datetime

# Valor crítico de chi-cuadrado con 2 grados de libertad al 5 %:
# si el estadístico de Jarque-Bera lo supera, se rechaza la normalidad.
CHI2_2GL_95 = 5.991
MINIMO_TICKETS_ESTADISTICA = 8


def _redondear(valor, decimales=2):
    return None if valor is None else round(valor, decimales)


# ---------------------------------------------------------------------------
#  Estadística de tickets
# ---------------------------------------------------------------------------
def estadistica_tickets(importes):
    """Analiza la distribución real de los importes de las ventas.

    - Medidas de posición y dispersión (media, mediana, desvío, cuartiles).
    - Valores atípicos por rango intercuartílico (Tukey): fuera de
      [Q1 - 1,5·RIC ; Q3 + 1,5·RIC].
    - Forma de la distribución (asimetría y curtosis) y prueba de Jarque-Bera
      para decidir si una curva normal es una aproximación razonable.
    - Histograma y, solo si corresponde, la curva normal de referencia."""
    n = len(importes)
    if n < 2:
        return {"n": n, "suficiente": False,
                "mensaje": "Se necesitan al menos 2 ventas en el período para calcular "
                           "la dispersión de los tickets."}

    datos = sorted(float(x) for x in importes)
    media = statistics.fmean(datos)
    desvio = statistics.stdev(datos)                     # muestral (n - 1)
    q1, mediana, q3 = statistics.quantiles(datos, n=4, method="inclusive")
    ric = q3 - q1
    limite_bajo, limite_alto = q1 - 1.5 * ric, q3 + 1.5 * ric

    asimetria = curtosis = jarque_bera = None
    if desvio > 0:
        m2 = sum((x - media) ** 2 for x in datos) / n
        m3 = sum((x - media) ** 3 for x in datos) / n
        m4 = sum((x - media) ** 4 for x in datos) / n
        asimetria = m3 / m2 ** 1.5
        curtosis = m4 / m2 ** 2 - 3                      # exceso de curtosis
        jarque_bera = n / 6 * (asimetria ** 2 + curtosis ** 2 / 4)

    if n < MINIMO_TICKETS_ESTADISTICA:
        normal, motivo = False, (
            f"Hay {n} ventas: con menos de {MINIMO_TICKETS_ESTADISTICA} no se puede "
            "evaluar la forma de la distribución.")
    elif desvio == 0:
        normal, motivo = False, "Todos los tickets tienen el mismo importe."
    elif jarque_bera > CHI2_2GL_95:
        normal, motivo = False, (
            f"La distribución no es normal (Jarque-Bera = {jarque_bera:.2f} > "
            f"{CHI2_2GL_95}): asimetría {asimetria:.2f}, curtosis {curtosis:.2f}. "
            "Conviene leer la mediana y los cuartiles en lugar de la media.")
    else:
        normal, motivo = True, (
            f"La curva normal es una aproximación razonable (Jarque-Bera = "
            f"{jarque_bera:.2f} ≤ {CHI2_2GL_95}).")

    histograma = _histograma(datos)
    curva = _curva_normal(media, desvio, n, histograma) if normal else []

    return {
        "n": n,
        "suficiente": True,
        "media": _redondear(media),
        "mediana": _redondear(mediana),
        "desvio": _redondear(desvio),
        "coef_variacion": _redondear(desvio / media * 100, 1) if media else None,
        "minimo": _redondear(datos[0]),
        "maximo": _redondear(datos[-1]),
        "q1": _redondear(q1),
        "q3": _redondear(q3),
        "ric": _redondear(ric),
        "limite_atipico_bajo": _redondear(limite_bajo),
        "limite_atipico_alto": _redondear(limite_alto),
        "atipicos_altos": sum(1 for x in datos if x > limite_alto),
        "atipicos_bajos": sum(1 for x in datos if x < limite_bajo),
        "asimetria": _redondear(asimetria, 3),
        "curtosis": _redondear(curtosis, 3),
        "jarque_bera": _redondear(jarque_bera, 3),
        "aproximacion_normal": normal,
        "diagnostico": motivo,
        "histograma": histograma,
        "curva_normal": curva,
    }


def _histograma(datos):
    """Regla de Sturges: k = 1 + log2(n) intervalos (entre 4 y 12)."""
    minimo, maximo = datos[0], datos[-1]
    k = max(4, min(12, math.ceil(1 + math.log2(len(datos)))))
    if maximo == minimo:
        return [{"desde": minimo, "hasta": maximo, "cantidad": len(datos)}]
    ancho = (maximo - minimo) / k
    clases = [{"desde": round(minimo + i * ancho, 2),
               "hasta": round(minimo + (i + 1) * ancho, 2), "cantidad": 0}
              for i in range(k)]
    for x in datos:
        indice = min(int((x - minimo) / ancho), k - 1)   # el máximo cae en la última
        clases[indice]["cantidad"] += 1
    return clases


def _curva_normal(media, desvio, n, histograma):
    """Densidad normal escalada a 'cantidad de ventas por intervalo' para
    superponerla al histograma."""
    ancho = histograma[0]["hasta"] - histograma[0]["desde"]
    inicio, fin = histograma[0]["desde"], histograma[-1]["hasta"]
    puntos = []
    for i in range(61):
        x = inicio + (fin - inicio) * i / 60
        densidad = math.exp(-((x - media) ** 2) / (2 * desvio ** 2)) / (
            desvio * math.sqrt(2 * math.pi))
        puntos.append({"x": round(x, 2), "y": round(densidad * n * ancho, 4)})
    return puntos


# ---------------------------------------------------------------------------
#  Permanencia de productos en stock
# ---------------------------------------------------------------------------
def _a_fecha(texto):
    return datetime.strptime(texto[:19], "%Y-%m-%d %H:%M:%S")


def periodos_con_stock(movimientos, desde=None, hasta=None, ahora=None):
    """Reconstruye, con el libro de movimientos, los períodos en que cada producto
    tuvo stock disponible (saldo > 0) en el local.

    - Ingreso: el saldo pasa de 0 a positivo.
    - Salida (agotamiento): el saldo vuelve a 0.
    - Si al final sigue habiendo stock, el período queda abierto.
    Se devuelven los períodos que se superponen con [desde, hasta].

    Limitación: el sistema no registra lotes, así que no se puede saber cuánto
    tiempo estuvo cada unidad; se mide el tiempo con stock disponible."""
    ahora = ahora or datetime.now()
    corte = min(ahora, datetime.combine(date.fromisoformat(hasta), datetime.max.time())) \
        if hasta else ahora
    inicio_periodo = datetime.combine(date.fromisoformat(desde), datetime.min.time()) \
        if desde else None

    por_producto = {}
    for m in movimientos:
        por_producto.setdefault((m["producto_id"], m["producto"]), []).append(m)

    periodos = []
    for (producto_id, producto), lista in por_producto.items():
        saldo, abierto_desde = 0, None
        for m in lista:
            fecha = _a_fecha(m["fecha"])
            anterior, saldo = saldo, saldo + m["cantidad"]
            if anterior <= 0 < saldo:
                abierto_desde = fecha
            elif anterior > 0 >= saldo and abierto_desde is not None:
                periodos.append((producto_id, producto, abierto_desde, fecha, False))
                abierto_desde = None
        if abierto_desde is not None:
            periodos.append((producto_id, producto, abierto_desde, corte, True))

    resultado = []
    for producto_id, producto, ingreso, salida, abierto in periodos:
        if inicio_periodo and salida < inicio_periodo:
            continue
        if ingreso > corte:
            continue
        resultado.append({
            "producto_id": producto_id,
            "producto": producto,
            "ingreso": ingreso.strftime("%Y-%m-%d %H:%M"),
            "salida": None if abierto else salida.strftime("%Y-%m-%d %H:%M"),
            "sigue_en_stock": abierto,
            "dias": round((salida - ingreso).total_seconds() / 86400, 1),
        })
    resultado.sort(key=lambda p: p["dias"], reverse=True)
    return resultado


def resumen_permanencia(periodos):
    """Por producto: cuántas veces se agotó y cuánto duró en promedio el stock."""
    productos = {}
    for p in periodos:
        r = productos.setdefault(p["producto"], {
            "producto": p["producto"], "periodos": 0, "agotamientos": 0,
            "dias_maximos": 0, "dias_hasta_agotar": []})
        r["periodos"] += 1
        r["dias_maximos"] = max(r["dias_maximos"], p["dias"])
        if not p["sigue_en_stock"]:
            r["agotamientos"] += 1
            r["dias_hasta_agotar"].append(p["dias"])
    filas = []
    for r in productos.values():
        dias = r.pop("dias_hasta_agotar")
        r["promedio_dias_hasta_agotar"] = round(sum(dias) / len(dias), 1) if dias else None
        filas.append(r)
    mayor_permanencia = sorted(filas, key=lambda r: r["dias_maximos"], reverse=True)
    se_agotan_rapido = sorted(
        (r for r in filas if r["promedio_dias_hasta_agotar"] is not None),
        key=lambda r: r["promedio_dias_hasta_agotar"])
    return {"por_producto": mayor_permanencia, "se_agotan_rapido": se_agotan_rapido}
