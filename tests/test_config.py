import pytest
from pathlib import Path
from copiloto_triaje.config import Config


def test_config_usa_valores_por_defecto_del_spec():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/rsna.zip"))
    assert cfg.semilla == 42
    assert cfg.tam_imagen == 224
    assert cfg.proporciones == (0.70, 0.15, 0.15)
    assert cfg.especificidad_objetivo == 0.75
    assert cfg.especificidad_minima == 0.70
    assert cfg.recall_objetivo == 0.85


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
