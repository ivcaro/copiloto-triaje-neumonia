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
    assert salida.stdout.strip().endswith("16 OK"), salida.stdout


def test_el_html_carga_la_logica_y_los_datos_por_lectura():
    html = (REPO / "pruebas" / "formulario" / "index.html").read_text(encoding="utf-8")
    assert '<script src="formulario.js"></script>' in html
    assert "datos_lectura" in html and "datos_planb.js" in html
    assert "opacidad o infiltrado compatible con neumonía" in html
    assert "no se puede volver atrás" in html
    assert "simulación semisintética" in html
    assert "Los síntomas referidos son iguales en todos los casos." in html


def test_el_html_guarda_el_estado_por_lectura_y_por_preparacion():
    """Ruling 14: el ensayo o una elección anterior no se retoman en la
    sesión real; ?nuevo=1 borra el estado de esta lectura antes de retomar;
    la cabecera dice cuántas respuestas se retoman."""
    html = (REPO / "pruebas" / "formulario" / "index.html").read_text(encoding="utf-8")
    assert 'clave = "sesion-h7-" + lectura + "-" + window.DATOS.preparacion;' in html
    assert html.index("window.DATOS.preparacion") < html.index("localStorage.removeItem(clave)") \
        < html.index("Formulario.retomar(")
    assert 'params.get("nuevo") === "1"' in html
    assert "Se retoma: " in html and " respuestas guardadas." in html
