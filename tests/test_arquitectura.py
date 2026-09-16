import torch

from copiloto_triaje.modelo.arquitectura import (
    construir_modelo, contar_parametros_entrenables, descongelar_para_ajuste,
)


def test_el_modelo_tiene_una_sola_salida():
    """Una salida (logit) + BCEWithLogitsLoss, no dos clases con softmax."""
    modelo = construir_modelo(preentrenado=False)
    salida = modelo(torch.randn(2, 3, 224, 224))
    assert salida.shape == (2, 1)


def test_congelar_backbone_deja_entrenable_solo_la_cabeza():
    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    assert all(not p.requires_grad for p in modelo.features.parameters())
    assert any(p.requires_grad for p in modelo.classifier.parameters())


def test_descongelar_aumenta_los_parametros_entrenables():
    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    antes = contar_parametros_entrenables(modelo)
    descongelar_para_ajuste(modelo, n_bloques=3)
    assert contar_parametros_entrenables(modelo) > antes


def test_sin_congelar_todo_es_entrenable():
    modelo = construir_modelo(congelar_backbone=False, preentrenado=False)
    assert all(p.requires_grad for p in modelo.parameters())


def test_descongelar_con_cero_bloques_no_cambia_parametros():
    """Guardia contra la trampa del cero negativo: bloques[-0:] es bloques[0:],
    la lista entera. Verificamos que n_bloques=0 no descongela nada."""
    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    antes = contar_parametros_entrenables(modelo)
    descongelar_para_ajuste(modelo, n_bloques=0)
    despues = contar_parametros_entrenables(modelo)
    assert antes == despues, "n_bloques=0 descongelo parametros cuando no deberia"


def test_latencia_de_inferencia_en_cpu_bajo_el_limite():
    """Criterio de aceptacion del spec: menos de 4 s por imagen en CPU, que es
    lo que SP2 debe poder servir desde el VPS. Se mide la mediana de 5 pasadas
    para no depender de la primera, que incluye calentamiento."""
    import time
    modelo = construir_modelo(preentrenado=False).eval()
    entrada = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        modelo(entrada)  # calentamiento
        tiempos = []
        for _ in range(5):
            inicio = time.perf_counter()
            modelo(entrada)
            tiempos.append(time.perf_counter() - inicio)
    mediana = sorted(tiempos)[2]
    assert mediana < 4.0, f"latencia {mediana:.3f}s supera el limite de 4 s"
