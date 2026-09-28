"""La lógica del formulario de la sesión vive en JavaScript y la prueba `node`;
esto la mete en la suite de pytest, como el redactor."""
import pathlib
import shutil
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_la_logica_del_formulario_pasa_sus_pruebas_en_node():
    node = shutil.which("node")
    assert node, "hace falta node: el redactor y las pruebas de los nodos ya lo exigen"
    salida = subprocess.run([node, str(REPO / "tests" / "formulario.mjs")],
                            capture_output=True, text=True, encoding="utf-8")
    assert salida.returncode == 0, salida.stderr
    assert salida.stdout.strip().endswith("12 OK"), salida.stdout


def test_el_html_carga_la_logica_y_los_datos_por_lectura():
    html = (REPO / "pruebas" / "formulario" / "index.html").read_text(encoding="utf-8")
    assert '<script src="formulario.js"></script>' in html
    assert "datos_lectura" in html and "datos_planb.js" in html
    assert "opacidad o infiltrado compatible con neumonía" in html
    assert "no se puede volver atrás" in html
    assert "simulación semisintética" in html
