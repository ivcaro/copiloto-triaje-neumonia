"""Metricas binarias y seleccion de umbral segun la regla del spec.

La metrica primaria es el Recall: en triaje, un falso negativo (paciente
enfermo despriorizado) es el error mas costoso. No se reporta accuracy
como metrica principal porque con 22,5% de positivos es enganosa.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve


def metricas_binarias(y_true, y_pred) -> dict:
    """Recall, especificidad, precision y F1 para etiquetas 0/1."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    especificidad = tn / (tn + fp) if (tn + fp) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "recall": float(recall),
        "especificidad": float(especificidad),
        "precision": float(precision),
        "f1": float(f1),
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
    }


def elegir_umbral(
    y_true,
    y_score,
    especificidad_objetivo: float = 0.75,
    especificidad_minima: float = 0.70,
    recall_objetivo: float = 0.85,
) -> tuple[float, dict, str]:
    """Elige el umbral sobre la curva ROC de VALIDACION (nunca la de prueba).

    1. Entre los umbrales con especificidad >= objetivo, toma el de mayor recall.
    2. Si ese recall no alcanza `recall_objetivo`, repite con la especificidad minima.
    3. Si aun asi no se alcanza, conserva el umbral del paso 1 y reporta tal cual.

    Devuelve (umbral, metricas, nombre_del_paso_aplicado).
    """
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    fpr, tpr, umbrales = roc_curve(y_true, y_score)
    especificidades = 1.0 - fpr

    def mejor_indice(minimo: float):
        candidatos = np.where(especificidades >= minimo)[0]
        if candidatos.size == 0:
            return None
        return int(candidatos[np.argmax(tpr[candidatos])])

    i1 = mejor_indice(especificidad_objetivo)
    if i1 is None:
        indice = int(np.argmax(tpr - fpr))
        paso = "sin_umbral_con_especificidad_objetivo"
    elif tpr[i1] >= recall_objetivo:
        indice, paso = i1, "paso_1_especificidad_objetivo"
    else:
        i2 = mejor_indice(especificidad_minima)
        if i2 is not None and tpr[i2] > tpr[i1]:
            indice, paso = i2, "paso_2_especificidad_minima"
        else:
            indice, paso = i1, "paso_3_se_conserva_paso_1"

    umbral = float(umbrales[indice])
    if not np.isfinite(umbral):  # roc_curve devuelve inf en el primer punto
        umbral = float(y_score.max()) + 1.0
    metricas = metricas_binarias(y_true, (y_score >= umbral).astype(int))
    metricas["auc"] = float(roc_auc_score(y_true, y_score))
    metricas["umbral"] = umbral
    return umbral, metricas, paso
