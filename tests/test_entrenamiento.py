import copy

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from copiloto_triaje.config import Config
from copiloto_triaje.modelo.entrenamiento import entrenar, evaluar_epoca


class ModeloTrivial(torch.nn.Module):
    """Un lineal sobre la media de la imagen: entrena rapido en CPU."""

    def __init__(self):
        super().__init__()
        self.capa = torch.nn.Linear(1, 1)

    def forward(self, x):
        return self.capa(x.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(1))


def cargadores_sinteticos(n=32):
    g = torch.Generator().manual_seed(0)
    y = torch.cat([torch.ones(n // 2), torch.zeros(n // 2)])
    x = torch.randn(n, 3, 8, 8, generator=g) + y.view(-1, 1, 1, 1) * 2.0
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=8), DataLoader(ds, batch_size=8)


def test_evaluar_epoca_devuelve_etiquetas_y_puntajes_alineados():
    _, val = cargadores_sinteticos()
    y_true, y_score = evaluar_epoca(ModeloTrivial(), val, torch.device("cpu"))
    assert len(y_true) == len(y_score) == 32
    assert set(np.unique(y_true)).issubset({0.0, 1.0})


def test_entrenar_devuelve_historial_y_guarda_checkpoint(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=2, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    assert len(res["historial"]) == 2
    assert "recall" in res["historial"][0]
    assert res["ruta_mejor_checkpoint"].exists()


def test_el_checkpoint_guardado_se_puede_recargar(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=1, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    estado = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)
    assert "modelo" in estado and "epoca" in estado
    ModeloTrivial().load_state_dict(estado["modelo"])


def test_early_stopping_corta_antes_del_maximo_de_epocas(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=20, epocas_ajuste=0, paciencia=1)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    assert len(res["historial"]) < 20


def cargadores_sinteticos_barajados(n=32):
    """Igual que `cargadores_sinteticos`, pero el de entrenamiento se baraja
    (shuffle=True) sin pasarle un `generator` propio. El `RandomSampler` de
    torch, en ese caso, saca una semilla interna del generador GLOBAL en cada
    epoca (ver `torch/utils/data/sampler.py::RandomSampler.__iter__`): es el
    mismo mecanismo por el que RandomAffine/ColorJitter dependen del global,
    asi que sirve para ejercitar la siembra de `entrenar` sin necesitar el
    dataset real ni sus transformaciones."""
    g = torch.Generator().manual_seed(0)
    y = torch.cat([torch.ones(n // 2), torch.zeros(n // 2)])
    x = torch.randn(n, 3, 8, 8, generator=g) + y.view(-1, 1, 1, 1) * 2.0
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=8, shuffle=True), DataLoader(ds, batch_size=8)


def test_entrenar_con_la_misma_semilla_y_modelo_inicial_es_reproducible(tmp_path):
    """`entrenar` debe sembrar el generador global de torch con `cfg.semilla`
    al inicio. Sin esa siembra, esta prueba queda en rojo: el barajado del
    DataLoader de entrenamiento (que consume el generador global, igual que
    RandomAffine/ColorJitter en el dataset real) heredaria el estado que dejo
    la primera llamada a `entrenar` en vez de arrancar siempre desde la misma
    semilla, y las dos corridas divergirian."""
    train1, val1 = cargadores_sinteticos_barajados()
    train2, val2 = cargadores_sinteticos_barajados()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=3, epocas_ajuste=0)

    # Mismo modelo inicial en las dos corridas: se copian los pesos, no se
    # reconstruye con la misma semilla, para no depender de otro mecanismo
    # de reproducibilidad distinto al que se quiere probar.
    estado_inicial = copy.deepcopy(ModeloTrivial().state_dict())

    modelo1 = ModeloTrivial()
    modelo1.load_state_dict(estado_inicial)
    res1 = entrenar(modelo1, train1, val1, cfg, torch.device("cpu"), tmp_path / "ck1")

    modelo2 = ModeloTrivial()
    modelo2.load_state_dict(estado_inicial)
    res2 = entrenar(modelo2, train2, val2, cfg, torch.device("cpu"), tmp_path / "ck2")

    assert res1["historial"] == res2["historial"]
