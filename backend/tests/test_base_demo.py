import sqlite3

from database import base_demo


def test_preparar_base_copia_plantilla_completa_si_no_hay_base_local(tmp_path, monkeypatch):
    plantilla = tmp_path / "plantilla.db"
    local = tmp_path / "tp_cd_locales.db"
    contenido = b"base de demostracion completa"
    plantilla.write_bytes(contenido)
    monkeypatch.setattr(base_demo, "BASE_DEMO", str(plantilla))
    monkeypatch.setattr(base_demo, "BASE_TRABAJO", str(local))

    base_demo.preparar_base_de_trabajo()

    assert local.read_bytes() == contenido


def test_plantilla_copiada_contiene_ventas_de_varios_anios(tmp_path, monkeypatch):
    local = tmp_path / "tp_cd_locales.db"
    monkeypatch.setattr(base_demo, "BASE_TRABAJO", str(local))

    base_demo.preparar_base_de_trabajo()

    with sqlite3.connect(local) as cx:
        cantidad, primera, ultima = cx.execute(
            "SELECT COUNT(*), MIN(fecha), MAX(fecha) FROM venta").fetchone()
    assert cantidad > 3000
    assert primera.startswith("2025-")
    assert ultima.startswith("2026-")


def test_preparar_base_conserva_base_local_existente(tmp_path, monkeypatch):
    plantilla = tmp_path / "plantilla.db"
    local = tmp_path / "tp_cd_locales.db"
    plantilla.write_bytes(b"datos demo")
    contenido_local = b"datos locales"
    local.write_bytes(contenido_local)
    monkeypatch.setattr(base_demo, "BASE_DEMO", str(plantilla))
    monkeypatch.setattr(base_demo, "BASE_TRABAJO", str(local))

    base_demo.preparar_base_de_trabajo()

    assert local.read_bytes() == contenido_local
