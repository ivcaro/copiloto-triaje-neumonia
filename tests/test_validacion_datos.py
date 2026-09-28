"""Los insumos congelados de la simulación semisintética (spec SP5 §4.1, §4.8).

Ninguno es simulación: son las puntuaciones reales del modelo desplegado
sobre las placas reales de prueba, y el calibrador que sirve el contenedor.
"""
import re

import numpy as np
import pytest

from copiloto_triaje.validacion import datos


def test_las_crudas_congeladas_son_las_3811_placas_de_prueba():
    df = datos.cargar_crudas()
    assert len(df) == 3811
    assert df["patientId"].is_unique
    assert int(df["etiqueta"].sum()) == 844
    assert set(df["vista"].unique()) == {"AP", "PA"}
    assert set(df["sexo"].unique()) == {"F", "M"}
    assert df["cruda"].between(0.0, 1.0).all()


def test_el_hash_congelado_es_un_sha256_y_coincide_con_la_cache_si_existe():
    texto = datos.HASH_CONGELADO.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{64}", texto)
    cache = datos.REPO / "pruebas" / "crudas_prueba.sha256"
    if cache.is_file():
        assert cache.read_text(encoding="utf-8").strip() == texto


def test_la_evidencia_de_imagen_usa_la_prevalencia_del_calibrador():
    """p_cal ⇔ prevalencia × RV: es la misma cadena que `heckerling.combinar`
    recorre, y por eso el previo de la simulación es el del calibrador."""
    cal = datos.calibrador_desplegado()
    df = datos.cargar_crudas()
    p, q, rv = datos.evidencia_imagen(df["cruda"].values[:200], cal)
    odds_previas = cal.prevalencia / (1 - cal.prevalencia)
    assert np.allclose(np.exp(q), odds_previas * rv)
    assert np.allclose(p, 1 / (1 + np.exp(-q)))
    assert cal.prevalencia == pytest.approx(844 / 3811, abs=5e-5)


def test_cargar_rechaza_pacientes_repetidos_y_columnas_que_faltan(tmp_path):
    df = datos.cargar_crudas().head(3)
    repetidos = tmp_path / "repetidos.csv"
    df.iloc[[0, 0, 1]].to_csv(repetidos, index=False)
    with pytest.raises(ValueError, match="repite pacientes"):
        datos.cargar_crudas(repetidos)
    sin_vista = tmp_path / "sin_vista.csv"
    df.drop(columns=["vista"]).to_csv(sin_vista, index=False)
    with pytest.raises(ValueError, match="faltan las columnas"):
        datos.cargar_crudas(sin_vista)
