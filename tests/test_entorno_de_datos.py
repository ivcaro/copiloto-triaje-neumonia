# -*- coding: utf-8 -*-
"""Lo que vive fuera del repositorio y algunas pruebas necesitan: el dataset
de RSNA (`RSNA_RAIZ`) y los pesos desplegados.

Ninguno de los dos se versiona, asi que en un clon limpio no estan. Las pruebas
que los usan tienen que SALTARSE diciendo que se queda sin verificar, y no
fallar con un `FileNotFoundError` que no informa de nada. Aqui se prueban las
dos funciones de `conftest.py` que lo deciden; los fijadores `rsna_raiz` y
`pesos_desplegados` solo las llaman.
"""
import pytest

import conftest


def test_sin_rsna_raiz_se_salta_diciendo_que_falta_y_como_verificarlo(monkeypatch):
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(pytest.skip.Exception) as salto:
        conftest.raiz_rsna_o_salta()
    mensaje = str(salto.value)
    assert "SIN VERIFICAR" in mensaje
    assert "RSNA_RAIZ" in mensaje
    assert "crudo/stage_2_train_images" in mensaje, "debe decir que carpeta es"


def test_con_rsna_raiz_vacia_tambien_se_salta(monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", "")
    with pytest.raises(pytest.skip.Exception, match="RSNA_RAIZ"):
        conftest.raiz_rsna_o_salta()


def test_con_rsna_raiz_se_devuelve_la_carpeta(tmp_path, monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path))
    assert conftest.raiz_rsna_o_salta() == tmp_path


def test_sin_los_pesos_se_salta_diciendo_cuales_faltan(tmp_path, monkeypatch):
    from pruebas import puntuaciones
    monkeypatch.setattr(puntuaciones, "PESOS", tmp_path / "pesos_modelo_cpu.pt")
    with pytest.raises(pytest.skip.Exception) as salto:
        conftest.pesos_desplegados_o_salta()
    mensaje = str(salto.value)
    assert "SIN VERIFICAR" in mensaje
    assert "pesos_modelo_cpu.pt" in mensaje
    # los tres grupos de pruebas que piden los pesos, y de dónde salen
    for grupo in ("la selección de casos", "las dos pruebas del recorte",
                  "del bot del profesional que suben una placa"):
        assert grupo in " ".join(mensaje.split()), grupo
    assert "README" in mensaje


def test_con_los_pesos_se_devuelve_su_ruta(tmp_path, monkeypatch):
    from pruebas import puntuaciones
    pesos = tmp_path / "pesos_modelo_cpu.pt"
    pesos.write_bytes(b"pesos de mentira")
    monkeypatch.setattr(puntuaciones, "PESOS", pesos)
    assert conftest.pesos_desplegados_o_salta() == pesos


@pytest.mark.parametrize("nombre", ["rsna_raiz", "pesos_desplegados"])
def test_los_fijadores_sirven_a_fijadores_de_modulo(nombre, request):
    """De modulo, por dos razones. `casos` y los `dicom_*` son de modulo, y
    un fijador de modulo no puede pedir uno de funcion (ScopeMismatch). Y no
    de sesion, porque pytest prepara antes lo de alcance mayor: el skip del
    dataset le quitaria el sitio al de `copiloto_vivo`, que es `autouse` y de
    modulo y tiene que ir primero (sin servidor no hace falta mirar nada mas)."""
    definiciones = request.session._fixturemanager.getfixturedefs(
        nombre, request.node)
    assert definiciones, f"no existe el fijador {nombre}"
    assert definiciones[-1].scope == "module"
