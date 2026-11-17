import sqlite3
import subprocess
import sys
from pathlib import Path


def test_generador_acepta_nombre_de_archivo_sin_directorio(tmp_path):
    script = Path(__file__).resolve().parents[1] / "generar_datos_demo.py"
    salida = tmp_path / "datos.db"
    resultado = subprocess.run(
        [sys.executable, str(script), salida.name, "2025-01-06"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stderr
    with sqlite3.connect(salida) as cx:
        assert cx.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
