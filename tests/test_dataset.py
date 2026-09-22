import numpy as np
import pandas as pd
import pytest
import torch
from PIL import Image

from copiloto_triaje.datos.dataset import DatasetRadiografias, construir_transformaciones


def manifiesto_y_pngs(tmp_path, n=6):
    dir_png = tmp_path / "png"
    dir_png.mkdir()
    filas = []
    for i in range(n):
        nombre = f"P{i:04d}.png"
        arr = (np.random.default_rng(i).integers(0, 255, (100, 100))).astype(np.uint8)
        Image.fromarray(arr).save(dir_png / nombre)
        filas.append({"archivo_png": nombre, "patientId": f"P{i:04d}", "etiqueta": i % 2})
    return pd.DataFrame(filas), dir_png


def test_devuelve_tensor_de_tres_canales_del_tamano_pedido(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, tam_imagen=224, entrenamiento=False)
    x, y = ds[0]
    assert x.shape == (3, 224, 224)
    assert x.dtype == torch.float32
    assert isinstance(y, torch.Tensor) and y.dtype == torch.float32


def test_la_longitud_coincide_con_el_manifiesto(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path, n=6)
    assert len(DatasetRadiografias(man, dir_png, 224, False)) == 6


def test_la_etiqueta_corresponde_a_su_fila(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, 224, False)
    for i in range(len(ds)):
        assert float(ds[i][1]) == float(man.iloc[i]["etiqueta"])


def test_sin_aumento_el_resultado_es_determinista(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, 224, entrenamiento=False)
    assert torch.equal(ds[0][0], ds[0][0])


def test_el_aumento_solo_se_aplica_en_entrenamiento():
    t_train = construir_transformaciones(224, entrenamiento=True)
    t_eval = construir_transformaciones(224, entrenamiento=False)
    nombres_train = [type(t).__name__ for t in t_train.transforms]
    nombres_eval = [type(t).__name__ for t in t_eval.transforms]

    # Verificar que evaluación tiene EXACTAMENTE: Resize, ToTensor, Normalize
    assert nombres_eval == ["Resize", "ToTensor", "Normalize"]

    # Verificar que entrenamiento tiene aumento: Resize, RandomAffine, ColorJitter, ToTensor, Normalize
    assert "RandomAffine" in nombres_train
    assert "ColorJitter" in nombres_train

    # Verificar que evaluación no contiene transformaciones aleatorias
    assert not any(n.startswith("Random") for n in nombres_eval)


def test_no_se_usa_volteo_horizontal():
    """La lateralidad cardiaca es informacion clinica: voltear produciria
    imagenes anatomicamente imposibles."""
    nombres = [type(t).__name__ for t in construir_transformaciones(224, True).transforms]
    assert not any("Flip" in n for n in nombres)


def test_dataset_guarda_el_manifiesto_como_atributo(tmp_path):
    """Tarea 7 lee self.manifiesto para calcular peso de clase sin cargar imagenes.
    Un renombre futuro la romperia en silencio si no fijamos este contrato."""
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, 224, False)
    assert hasattr(ds, "manifiesto")
    assert isinstance(ds.manifiesto, pd.DataFrame)
    assert len(ds.manifiesto) == len(man)


def test_un_png_ilegible_dice_cual_es(tmp_path):
    """El fallo en Colab fue `OSError: image file is truncated` a secas. Dentro
    de un DataLoader con 8 procesos ese mensaje llega envuelto en dos trazas y
    SIN el nombre del archivo, asi que no se puede reparar: hay que buscar el
    defectuoso entre 25 403. El error tiene que nombrar la ruta y la fila.
    """
    dir_png = tmp_path / "png"
    dir_png.mkdir()
    buena = dir_png / "ok.png"
    Image.new("L", (32, 32)).save(buena)
    # Cortar DENTRO del IDAT reproduce el fallo real de Colab: firma y
    # cabecera intactas, datos a medias, y PIL dice "image file is truncated".
    # Cortar antes (p. ej. a 40 bytes) da otro error distinto -no puede ni
    # identificar el formato- y no probaria el caso que nos interesa.
    intacto = buena.read_bytes()
    rota = dir_png / "rota.png"
    rota.write_bytes(intacto[: intacto.index(b"IDAT") + 12])

    manifiesto = pd.DataFrame([{"archivo_png": "ok.png", "etiqueta": 0},
                               {"archivo_png": "rota.png", "etiqueta": 1}])
    ds = DatasetRadiografias(manifiesto, dir_png, tam_imagen=32)

    ds[0]  # la sana no molesta

    with pytest.raises(OSError) as fallo:
        ds[1]
    mensaje = str(fallo.value)
    assert "rota.png" in mensaje
    assert "fila 1" in mensaje
    assert "truncated" in mensaje.lower()
