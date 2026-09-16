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
from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_en_umbral
from copiloto_triaje.modelo.reporte import escribir_reporte_markdown, guardar_curva_roc


def test_pipeline_completo_en_cpu(tmp_path):
    rng = np.random.default_rng(0)
    dir_png = tmp_path / "png"
    dir_png.mkdir()

    # 50 pacientes: los positivos llevan una mancha clara. La intencion es
    # que el modelo tenga *algo* que en principio podria aprender, pero esta
    # prueba no lo comprueba: ningun aserto mide si lo aprende. Es una
    # prueba de cableado (las piezas encajan y el pipeline corre en CPU),
    # no de calidad del modelo.
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

    # epocas_ajuste=0 => el historial solo contiene la fase "cabeza"; con la
    # paciencia por defecto (cfg.paciencia=3) y solo 2 epocas, la paciencia
    # nunca se agota, asi que deben correr las 2 completas. El numero exacto
    # detecta una regresion que trunque el entrenamiento antes de tiempo.
    assert len(resultado["historial"]) == cfg.epocas_cabeza
    assert resultado["ruta_mejor_checkpoint"].exists()

    # El umbral se elige SOLO con el conjunto de VALIDACION y se congela
    # antes de tocar el de prueba (regla central del proyecto: ver el
    # docstring de `elegir_umbral`). Decidir el punto de corte mirando la
    # prueba contaminaria esa estimacion; por eso la prueba se evalua una
    # unica vez, ya con el umbral fijo.
    y_true_val, y_score_val = evaluar_epoca(modelo, cargador("val", False), torch.device("cpu"))
    umbral, metricas_val, paso = elegir_umbral(y_true_val, y_score_val)
    pasos_validos = {
        "paso_1_especificidad_objetivo",
        "paso_2_especificidad_minima",
        "paso_3_se_conserva_paso_1",
        "sin_umbral_con_especificidad_objetivo",
    }
    assert paso in pasos_validos

    y_true_test, y_score_test = evaluar_epoca(modelo, cargador("test", False), torch.device("cpu"))
    assert len(y_true_test) == len(y_score_test) > 0
    # `metricas_en_umbral`, no `metricas_binarias`: es lo que hace que el AUC
    # del conjunto de PRUEBA quede reportado (hallazgo I2). Esta linea es la
    # misma que ejecuta la celda de evaluacion del notebook.
    metricas_test = metricas_en_umbral(y_true_test, y_score_test, umbral)
    total = metricas_test["tp"] + metricas_test["tn"] + metricas_test["fp"] + metricas_test["fn"]
    assert total == len(y_true_test)
    assert 0.0 <= metricas_test["auc"] <= 1.0

    # Los entregables del spec §12, generados con las mismas llamadas del
    # notebook: si esta parte se rompe, se rompe en local y no a los 40
    # minutos de GPU en Colab.
    ruta_roc = guardar_curva_roc(y_true_test, y_score_test,
                                 tmp_path / "curva_roc.svg", umbral=umbral)
    ruta_md = escribir_reporte_markdown(
        tmp_path / "reporte_metricas.md", umbral=umbral, paso=paso,
        metricas_validacion=metricas_val, metricas_prueba=metricas_test,
        historial=resultado["historial"], mejor_epoca=resultado["mejor_epoca"],
        ruta_roc=ruta_roc)
    assert ruta_roc.exists() and ruta_md.exists()
    assert "Matriz de confusion" in ruta_md.read_text(encoding="utf-8")

    # Y el entregable para SP2: los pesos limpios, en CPU (hallazgo I3).
    pesos = torch.load(resultado["ruta_pesos_cpu"], map_location="cpu",
                       weights_only=True)
    construir_modelo(congelar_backbone=True, preentrenado=False).load_state_dict(pesos)
