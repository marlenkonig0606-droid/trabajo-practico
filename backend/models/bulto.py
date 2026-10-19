"""
Ciclo de vida del bulto (lo que la cátedra va a evaluar "críticamente").

    PREPARADO ──precintar──▶ PRECINTADO ──despachar──▶ EN_TRANSITO
                                                          │
                                                       recibir
                                                          ▼
                                                      RECIBIDO
                                                     ╱        ╲
                                     precinto intacto          precinto roto
                                           ▼                        ▼
                                      VERIFICADO               RECHAZADO

VERIFICADO y RECHAZADO son estados FINALES: desde ahí no se puede ir a ningún lado.
"""



class EstadoBulto:
    PREPARADO = "PREPARADO"
    PRECINTADO = "PRECINTADO"
    EN_TRANSITO = "EN_TRANSITO"
    RECIBIDO = "RECIBIDO"
    VERIFICADO = "VERIFICADO"
    RECHAZADO = "RECHAZADO"
    ANULADO = "ANULADO"                   

    TRANSICIONES = {
        PREPARADO: {PRECINTADO, ANULADO},    
        PRECINTADO: {EN_TRANSITO, ANULADO},  
        EN_TRANSITO: {RECIBIDO},
        RECIBIDO: {VERIFICADO, RECHAZADO},
        VERIFICADO: set(),
        RECHAZADO: set(),
        ANULADO: set(),                  
    }

    FINALES = {VERIFICADO, RECHAZADO, ANULADO}

    @classmethod
    def puede_pasar(cls, desde, hacia):
        return hacia in cls.TRANSICIONES.get(desde, set())


class Bulto:
    def __init__(self, id, remito_id, estado=EstadoBulto.PREPARADO, precinto=None,
                 fecha_despacho=None, fecha_recepcion=None, items=None):
        self.id = id
        self.remito_id = remito_id
        self.estado = estado
        self.precinto = precinto
        self.fecha_despacho = fecha_despacho
        self.fecha_recepcion = fecha_recepcion
        self.items = items or []          # lista de {"producto_id", "cantidad"}

    def cambiar_estado(self, nuevo_estado):
        """El objeto se protege a sí mismo: no acepta transiciones inválidas."""
        if not EstadoBulto.puede_pasar(self.estado, nuevo_estado):
            raise ValueError(
                f"El bulto {self.id} no puede pasar de {self.estado} a {nuevo_estado}"
            )
        self.estado = nuevo_estado

    def esta_finalizado(self):
        return self.estado in EstadoBulto.FINALES

    @classmethod
    def desde_fila(cls, fila, items=None):
        return cls(
            id=fila["id"], remito_id=fila["remito_id"], estado=fila["estado"],
            precinto=fila["precinto"], fecha_despacho=fila["fecha_despacho"],
            fecha_recepcion=fila["fecha_recepcion"], items=items,
        )

    def to_dict(self):
        return {
            "id": self.id, "remito_id": self.remito_id, "estado": self.estado,
            "precinto": self.precinto, "fecha_despacho": self.fecha_despacho,
            "fecha_recepcion": self.fecha_recepcion, "items": self.items,
        }
