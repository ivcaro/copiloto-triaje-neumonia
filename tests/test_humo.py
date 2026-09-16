# tests/test_humo.py
"""Entrenamiento completo de punta a punta con imagenes sinteticas.

No mide calidad del modelo: demuestra que las piezas encajan y que el
pipeline corre en CPU. Debe tardar menos de un minuto.
"""
import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader

from copiloto_triaje.config import Config
from copiloto_triaje.datos.dataset import DatasetRadiografias
from copiloto_triaje.datos.particion import particionar_por_paciente, verificar_sin_fuga
from copiloto_triaje.datos.preparacion import escribir_manifiestos
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.modelo.entrenamiento import entrenar, evaluar_epoca
from copiloto_triaje.modelo.evaluacion import elegir_umbral


def test_pipeline_completo_en_cpu(tmp_path):
    rng = np.random.default_rng(0)
    dir_png = tmp_path / "png"
    dir_png.mkdir()

    # 50 pacientes: los positivos llevan una mancha clara, para que el modelo
    # tenga algo que aprender en dos epocas.
    registros = []
    for i in range(50):
        etiqueta = int(i < 15)
        arr = rng.integers(0, 120, (64, 64), dtype=np.uint8)
        if etiqueta:
            arr[20:40, 20:40] = 240
        nombre = f"P{i:04d}.png"
        Image.fromarray(arr).save(dir_png / nombre)
        registros.append({"patientId": f"P{i:04d}", "archivo_png": nombre,
                          "etiqueta": etiqueta})

    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 tam_imagen=64, lote=8, epocas_cabeza=2, epocas_ajuste=0)

    particiones = particionar_por_paciente(registros, cfg.proporciones, cfg.semilla)
    verificar_sin_fuga(particiones)
    escribir_manifiestos(particiones, cfg.dir_manifiestos, cfg.semilla)

    def cargador(nombre, entrenamiento):
        df = pd.read_csv(cfg.dir_manifiestos / f"{nombre}.csv")
        ds = DatasetRadiografias(df, dir_png, cfg.tam_imagen, entrenamiento)
        return DataLoader(ds, batch_size=cfg.lote, shuffle=entrenamiento)

    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    resultado = entrenar(modelo, cargador("train", True), cargador("val", False),
                         cfg, torch.device("cpu"), cfg.dir_checkpoints)

    assert len(resultado["historial"]) >= 1
    assert resultado["ruta_mejor_checkpoint"].exists()

    y_true, y_score = evaluar_epoca(modelo, cargador("test", False), torch.device("cpu"))
    assert len(y_true) == len(y_score) > 0
    umbral, metricas, paso = elegir_umbral(y_true, y_score)
    assert 0.0 <= metricas["recall"] <= 1.0
    assert "umbral" in metricas and paso
