import pytest
from pathlib import Path
from copiloto_triaje.config import Config


def test_config_usa_valores_por_defecto_del_spec():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/rsna.zip"))
    assert cfg.semilla == 42
    assert cfg.proporciones == (0.70, 0.15, 0.15)
    assert cfg.especificidad_objetivo == 0.75
    assert cfg.especificidad_minima == 0.70
    assert cfg.recall_objetivo == 0.85
    assert cfg.recall_minimo == 0.80
    # Revisados el 21-sep-2026 con la evidencia de la primera corrida, que
    # con 224 px y MobileNetV3 quedo en AUC 0,845 y recall 76,6%: por debajo
    # del minimo que el propio spec exige (0,85 y 80%).
    assert cfg.tam_imagen == 320
    assert cfg.arquitectura == "densenet121"
    assert cfg.descongelar_todo is True
    assert cfg.usar_scheduler is True


def test_config_rechaza_una_arquitectura_no_soportada():
    with pytest.raises(ValueError, match="no soportada"):
        Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/r.zip"),
               arquitectura="inventada")


def test_config_rechaza_umbrales_incoherentes():
    """El minimo nunca puede ser mas exigente que el objetivo: seria una
    configuracion que no se puede satisfacer ni describir."""
    with pytest.raises(ValueError, match="recall minimo"):
        Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/r.zip"),
               recall_minimo=0.90, recall_objetivo=0.85)
    with pytest.raises(ValueError, match="especificidad minima"):
        Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/r.zip"),
               especificidad_minima=0.90, especificidad_objetivo=0.75)


def test_config_rechaza_proporciones_que_no_suman_uno():
    with pytest.raises(ValueError, match="deben sumar 1"):
        Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/r.zip"),
               proporciones=(0.7, 0.2, 0.2))


def test_config_es_inmutable():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/r.zip"))
    with pytest.raises(Exception):
        cfg.semilla = 7


def test_rutas_derivadas_cuelgan_de_la_raiz():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/r.zip"))
    assert cfg.dir_png == Path("/tmp/d/png")
    assert cfg.dir_manifiestos == Path("/tmp/d/manifiestos")
    assert cfg.dir_checkpoints == Path("/tmp/d/checkpoints")


def test_el_margen_de_especificidad_por_defecto_es_el_medido(tmp_path):
    """0,02 no es un numero redondo elegido a ojo.

    Es el que en simulacion -con las dimensiones reales de las particiones,
    3 810 validacion y 3 811 prueba al 22,15% de positivos y AUC 0,888- lleva
    el cumplimiento del suelo de especificidad en PRUEBA del 84% al 97%,
    costando 0,003 de recall. Sin margen, la corrida de DenseNet121 del
    23-sep eligio el umbral con especificidad 0,70027 en validacion y cayo a
    0,69869 en prueba: incumplio el minimo por trece diezmilesimas.

    Queda fijado para que cambiarlo sea una decision y no un descuido.
    """
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip")
    assert cfg.margen_especificidad == 0.02


def test_un_margen_negativo_se_rechaza(tmp_path):
    """Un margen negativo BAJA el suelo al elegir, que es lo contrario de lo
    que el parametro existe para hacer: dejaria pasar puntos de operacion que
    ya incumplen el minimo en la propia validacion."""
    with pytest.raises(ValueError, match="margen_especificidad"):
        Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
               margen_especificidad=-0.01)
