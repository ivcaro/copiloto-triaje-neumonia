"""El script debe fallar al inicio si le falta algo, no a mitad de evaluar
3 810 imagenes."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ajustar_calibrador.py"


def _cargar():
    especificacion = importlib.util.spec_from_file_location("ajustar_calibrador", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


ajustar = _cargar()


def test_falla_si_no_estan_los_pesos(tmp_path, capsys):
    """Citando la ruta que busco, no un mensaje generico."""
    codigo = ajustar.main(["--corrida", str(tmp_path / "no_existe"),
                           "--raiz", str(tmp_path)])
    assert codigo == 2
    assert "no_existe" in capsys.readouterr().err


def test_falla_si_no_esta_el_manifiesto_de_validacion(tmp_path, capsys):
    """El calibrador se ajusta SOLO sobre validacion; sin ese manifiesto no
    hay nada que hacer, y usar otro conjunto seria un error silencioso."""
    corrida = tmp_path / "corrida"
    (corrida / "checkpoints").mkdir(parents=True)
    (corrida / "checkpoints" / "pesos_modelo_cpu.pt").write_bytes(b"x")
    codigo = ajustar.main(["--corrida", str(corrida), "--raiz", str(tmp_path)])
    assert codigo == 2
    assert "val.csv" in capsys.readouterr().err
