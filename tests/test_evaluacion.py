import numpy as np
from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_binarias


def test_separacion_perfecta_da_recall_y_especificidad_uno():
    y = [0, 0, 1, 1]
    m = metricas_binarias(y, [0, 0, 1, 1])
    assert m["recall"] == 1.0
    assert m["especificidad"] == 1.0
    assert m["f1"] == 1.0


def test_predecir_todo_negativo_da_recall_cero():
    """El fracaso que la metrica primaria debe impedir: 77,5% de acierto y
    cero pacientes detectados."""
    y = [1] * 225 + [0] * 775
    m = metricas_binarias(y, [0] * 1000)
    assert m["recall"] == 0.0
    assert m["especificidad"] == 1.0


def test_matriz_de_confusion_conocida():
    y_true = [1, 1, 1, 0, 0, 0, 0]
    y_pred = [1, 1, 0, 1, 0, 0, 0]
    m = metricas_binarias(y_true, y_pred)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (2, 1, 1, 3)
    assert m["recall"] == 2 / 3
    assert m["especificidad"] == 3 / 4


def test_umbral_paso_1_cuando_se_cumplen_ambos_objetivos():
    rng = np.random.default_rng(0)
    y = np.array([1] * 200 + [0] * 800)
    score = np.where(y == 1, rng.normal(0.85, 0.05, 1000), rng.normal(0.15, 0.05, 1000))
    umbral, m, paso = elegir_umbral(y, score)
    assert paso == "paso_1_especificidad_objetivo"
    assert m["recall"] >= 0.85
    assert m["especificidad"] >= 0.75


def test_umbral_relaja_al_paso_2_si_el_recall_no_llega():
    """Clases muy solapadas: con especificidad 0,75 no se alcanza 0,85 de
    recall, asi que la regla debe relajar hasta la especificidad minima."""
    rng = np.random.default_rng(1)
    y = np.array([1] * 200 + [0] * 800)
    score = np.where(y == 1, rng.normal(0.55, 0.20, 1000), rng.normal(0.45, 0.20, 1000))
    umbral, m, paso = elegir_umbral(y, score)
    assert paso in ("paso_2_especificidad_minima", "paso_3_se_conserva_paso_1")
    assert m["especificidad"] >= 0.70


def test_el_umbral_devuelto_reproduce_las_metricas_reportadas():
    rng = np.random.default_rng(2)
    y = np.array([1] * 100 + [0] * 300)
    score = np.where(y == 1, rng.normal(0.8, 0.1, 400), rng.normal(0.2, 0.1, 400))
    umbral, m, _ = elegir_umbral(y, score)
    recalculadas = metricas_binarias(y, (score >= umbral).astype(int))
    assert recalculadas["recall"] == m["recall"]
    assert recalculadas["especificidad"] == m["especificidad"]
