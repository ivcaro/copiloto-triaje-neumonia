import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from copiloto_triaje.modelo.evaluacion import (
    elegir_umbral, metricas_binarias, metricas_en_umbral,
)


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


def test_paso_2_solo_si_alcanza_recall_objetivo_sino_paso_3():
    """Clases muy solapadas: con especificidad 0,75 no se alcanza 0,85 de
    recall. La regla relaja a especificidad minima solo si ALCANZA 0,85."""
    rng = np.random.default_rng(1)
    y = np.array([1] * 200 + [0] * 800)
    score = np.where(y == 1, rng.normal(0.55, 0.20, 1000), rng.normal(0.45, 0.20, 1000))
    umbral, m, paso = elegir_umbral(y, score)
    # Relacion: paso_2 solo si recall >= 0.85; si recall < 0.85, debe ser paso_3
    if paso == "paso_2_especificidad_minima":
        assert m["recall"] >= 0.85
    if m["recall"] < 0.85:
        assert paso == "paso_3_se_conserva_paso_1"
    assert m["especificidad"] >= 0.70


def test_metricas_en_umbral_reporta_el_auc_de_cualquier_conjunto():
    """Hallazgo I2 (Important) de la oleada final: `roc_auc_score` solo se
    calculaba dentro de `elegir_umbral`, es decir solo sobre VALIDACION. El
    conjunto de prueba se reportaba con `metricas_binarias`, que recibe
    etiquetas ya binarizadas y por tanto no puede calcular un AUC. Resultado:
    'AUC-ROC >= 0,85', uno de los cuatro criterios de aceptacion del spec §2,
    era inreportable justo donde el spec lo exige.
    """
    rng = np.random.default_rng(5)
    y = np.array([1] * 150 + [0] * 350)
    score = np.where(y == 1, rng.normal(0.7, 0.15, 500), rng.normal(0.35, 0.15, 500))

    # La funcion vieja no puede dar el AUC: no ve los puntajes.
    assert "auc" not in metricas_binarias(y, (score >= 0.5).astype(int))

    m = metricas_en_umbral(y, score, 0.5)
    assert m["auc"] == pytest.approx(float(roc_auc_score(y, score)))
    assert m["umbral"] == 0.5
    # El resto de las metricas son exactamente las de ese umbral.
    for clave, valor in metricas_binarias(y, (score >= 0.5).astype(int)).items():
        assert m[clave] == valor


def test_el_auc_no_depende_del_umbral_elegido():
    """El AUC mide el ordenamiento completo, no un punto de corte: reportarlo
    junto a las metricas de un umbral no lo contamina con ese umbral."""
    rng = np.random.default_rng(6)
    y = np.array([1] * 100 + [0] * 300)
    score = np.where(y == 1, rng.normal(0.7, 0.2, 400), rng.normal(0.4, 0.2, 400))
    aucs = {metricas_en_umbral(y, score, u)["auc"] for u in (0.2, 0.5, 0.8)}
    assert len(aucs) == 1


def test_el_umbral_devuelto_reproduce_las_metricas_reportadas():
    rng = np.random.default_rng(2)
    y = np.array([1] * 100 + [0] * 300)
    score = np.where(y == 1, rng.normal(0.8, 0.1, 400), rng.normal(0.2, 0.1, 400))
    umbral, m, _ = elegir_umbral(y, score)
    recalculadas = metricas_binarias(y, (score >= umbral).astype(int))
    assert recalculadas["recall"] == m["recall"]
    assert recalculadas["especificidad"] == m["especificidad"]
