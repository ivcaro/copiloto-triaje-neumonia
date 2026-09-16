import copy

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

import copiloto_triaje.modelo.entrenamiento as entrenamiento_mod
from copiloto_triaje.config import Config
from copiloto_triaje.modelo.entrenamiento import entrenar, evaluar_epoca


class ModeloTrivial(torch.nn.Module):
    """Un lineal sobre la media de la imagen: entrena rapido en CPU."""

    def __init__(self):
        super().__init__()
        self.capa = torch.nn.Linear(1, 1)

    def forward(self, x):
        return self.capa(x.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(1))


class ModeloTrivialConFeatures(ModeloTrivial):
    """Variante de ModeloTrivial con un `.features` minimo. Solo la necesitan
    las pruebas que ejercitan la fase de ajuste fino: `descongelar_para_ajuste`
    accede a `modelo.features`, y el ModeloTrivial comun no lo tiene (a
    proposito, para el resto de las pruebas de este archivo)."""

    def __init__(self):
        super().__init__()
        self.features = torch.nn.ModuleList([torch.nn.Identity()])


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


def test_paciencia_agotada_en_cabeza_no_impide_la_fase_de_ajuste(tmp_path):
    """Hallazgo 1 (Critical) de la ronda de arreglo 1/5: agotar la paciencia
    en la fase 'cabeza' debe cortar SOLO esa fase -la cabeza convergio, que es
    justo el momento de empezar el ajuste fino-, no el entrenamiento completo.
    Antes del fix, el `return` dentro del bucle de epocas salia de toda
    `entrenar` y la fase 'ajuste' nunca se ejecutaba pese a pedirse 3 epocas."""
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=20, epocas_ajuste=3, paciencia=1)
    res = entrenar(ModeloTrivialConFeatures(), train, val, cfg,
                    torch.device("cpu"), tmp_path / "ck")
    epocas_cabeza = [r for r in res["historial"] if r["fase"] == "cabeza"]
    epocas_ajuste = [r for r in res["historial"] if r["fase"] == "ajuste"]
    assert len(epocas_cabeza) < 20, "la fase 'cabeza' deberia haber cortado por paciencia"
    assert len(epocas_ajuste) >= 1, \
        "la fase 'ajuste' nunca se ejecuto tras agotar la paciencia en 'cabeza'"


def _y_true_y_score_con(detectados: int, n: int = 10):
    """(y_true, y_score) sinteticos de n positivos y n negativos: `detectados`
    positivos con score alto (bien clasificados al umbral 0.5) y el resto con
    score bajo; los negativos siempre se clasifican bien. El recall resultante
    es exactamente `detectados / n`."""
    y_true = np.array([1.0] * n + [0.0] * n)
    y_score = np.array([0.9] * detectados + [0.1] * (n - detectados) + [0.1] * n)
    return y_true, y_score


def test_el_mejor_checkpoint_sigue_al_recall_no_a_la_perdida(tmp_path, monkeypatch):
    """Hallazgo 2 (Important) de la ronda de arreglo 1/5: fija el criterio de
    'mejor' epoca al Recall, no a la perdida. Se controlan perdida y recall
    por epoca -con monkeypatch de `_pasada_de_entrenamiento` y `evaluar_epoca`,
    para no depender de que converjan igual bajo entrenamiento real- de modo
    que diverjan a proposito: la perdida es minima en la ultima epoca, pero
    el Recall es maximo en la epoca 1. Si el criterio de seleccion cambiara
    de `m["recall"]` a una funcion de la perdida, esta prueba debe fallar
    (verificacion de mutacion documentada en el reporte)."""
    perdidas = [0.9, 0.9, 0.1]  # minima -"mejor" si el criterio fuera la perdida- en la epoca 2
    recalls = [0.3, 1.0, 0.3]  # maxima en la epoca 1
    contador = {"epoca": -1}

    def _pasada_falsa(modelo, cargador, criterio, optimizador, dispositivo):
        contador["epoca"] += 1
        return perdidas[contador["epoca"]]

    def _evaluar_falso(modelo, cargador, dispositivo):
        detectados = round(recalls[contador["epoca"]] * 10)
        return _y_true_y_score_con(detectados)

    monkeypatch.setattr(entrenamiento_mod, "_pasada_de_entrenamiento", _pasada_falsa)
    monkeypatch.setattr(entrenamiento_mod, "evaluar_epoca", _evaluar_falso)

    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=3, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")

    assert res["mejor_epoca"] == 1
    assert res["mejor_recall"] == 1.0
    estado_mejor = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)
    assert estado_mejor["epoca"] == 1


def test_el_checkpoint_guarda_lo_necesario_para_reanudar(tmp_path):
    """Hallazgo 4 (Important) de la ronda de arreglo 1/5: el spec exige poder
    reanudar el entrenamiento tras una caida de sesion (p.ej. en Colab). Sin
    el estado del optimizador, reanudar reiniciaria el momento de Adam en vez
    de continuar; sin la fase y el historial acumulado no se sabe en que
    punto del plan de dos fases se quedo el entrenamiento."""
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=2, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    estado = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)

    for clave in ("modelo", "optimizador", "epoca", "fase", "metricas", "historial"):
        assert clave in estado, f"falta '{clave}' en el checkpoint"
    assert estado["fase"] == "cabeza"
    assert len(estado["historial"]) >= 1

    # El estado del optimizador debe ser recargable de verdad, no solo estar
    # presente como clave.
    optimizador_nuevo = torch.optim.Adam(ModeloTrivial().parameters(), lr=cfg.lr_cabeza)
    optimizador_nuevo.load_state_dict(estado["optimizador"])
