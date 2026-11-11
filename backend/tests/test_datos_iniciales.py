from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar


def test_carga_datos_demo_utiles_y_no_duplica_al_reiniciar(tmp_path):
    BaseDeDatos.reiniciar()
    db = BaseDeDatos(str(tmp_path / "datos_demo.db"))

    cargar()
    antes = {
        "sucursales": db.consultar_uno("SELECT COUNT(*) AS n FROM sucursal")["n"],
        "proveedores": db.consultar_uno("SELECT COUNT(*) AS n FROM proveedor")["n"],
        "productos": db.consultar_uno("SELECT COUNT(*) AS n FROM producto")["n"],
        "ventas": db.consultar_uno("SELECT COUNT(*) AS n FROM venta")["n"],
        "devoluciones": db.consultar_uno("SELECT COUNT(*) AS n FROM devolucion")["n"],
        "stock_local": db.consultar(
            """SELECT s.nombre, p.codigo, st.disponible
               FROM stock st
               JOIN sucursal s ON s.id=st.sucursal_id
               JOIN producto p ON p.id=st.producto_id
               WHERE s.tipo='LOCAL' ORDER BY s.nombre, p.codigo"""),
    }

    assert antes["sucursales"] == 4
    assert antes["proveedores"] == 3
    assert antes["productos"] == 6
    assert antes["ventas"] == 4
    assert antes["devoluciones"] == 1
    assert {fila["nombre"] for fila in db.consultar(
        "SELECT nombre FROM sucursal WHERE tipo='CD'")} == {"CD Central", "CD Norte"}

    cargar()
    despues = {
        "sucursales": db.consultar_uno("SELECT COUNT(*) AS n FROM sucursal")["n"],
        "proveedores": db.consultar_uno("SELECT COUNT(*) AS n FROM proveedor")["n"],
        "productos": db.consultar_uno("SELECT COUNT(*) AS n FROM producto")["n"],
        "ventas": db.consultar_uno("SELECT COUNT(*) AS n FROM venta")["n"],
        "devoluciones": db.consultar_uno("SELECT COUNT(*) AS n FROM devolucion")["n"],
        "stock_local": db.consultar(
            """SELECT s.nombre, p.codigo, st.disponible
               FROM stock st
               JOIN sucursal s ON s.id=st.sucursal_id
               JOIN producto p ON p.id=st.producto_id
               WHERE s.tipo='LOCAL' ORDER BY s.nombre, p.codigo"""),
    }
    assert despues == antes
    BaseDeDatos.reiniciar()
