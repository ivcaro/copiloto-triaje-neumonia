"""Metricas binarias y seleccion de umbral segun la regla del spec.

La metrica primaria es el Recall: en triaje, un falso negativo (paciente
enfermo despriorizado) es el error mas costoso. No se reporta accuracy
como metrica principal porque con 22,15% de positivos es enganosa.
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


def metricas_en_umbral(y_true, y_score, umbral: float) -> dict:
    """Metricas binarias al `umbral` dado, mas el AUC-ROC de los puntajes.

    El AUC no depende del umbral -mide el ordenamiento completo, no un punto
    de corte-, pero es uno de los cuatro criterios de aceptacion del spec (§2:
    AUC >= 0,85). Hasta ahora solo se calculaba dentro de `elegir_umbral`, es
    decir solo sobre VALIDACION, de modo que el criterio quedaba inreportable
    sobre el conjunto de PRUEBA, que es donde el spec lo exige. Esta funcion
    existe para poder reportarlo tambien alli.
    """
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    metricas = metricas_binarias(y_true, (y_score >= umbral).astype(int))
    metricas["auc"] = float(roc_auc_score(y_true, y_score))
    metricas["umbral"] = float(umbral)
    return metricas


def elegir_umbral(
    y_true,
    y_score,
    especificidad_objetivo: float = 0.75,
    especificidad_minima: float = 0.70,
    recall_objetivo: float = 0.85,
    recall_minimo: float = 0.80,
    margen_especificidad: float = 0.0,
) -> tuple[float, dict, str]:
    """Elige el umbral sobre la curva ROC de VALIDACION (nunca la de prueba).

    La regla ordena los puntos de operacion por cuanto del spec satisfacen, y
    ante empate prefiere el de MAYOR especificidad:

    1. Recall >= objetivo con especificidad >= objetivo.
    2. Recall >= objetivo relajando a la especificidad minima.
    3. Recall >= minimo con especificidad >= objetivo.
    4. Recall >= minimo relajando a la especificidad minima.
    5. Ninguno alcanza el recall minimo: se toma el de mayor recall dentro
       del piso de especificidad y se reporta tal cual, sin forzar nada.

    `margen_especificidad` eleva los dos suelos de especificidad al elegir,
    para que el punto escogido no quede rozando el minimo: ver el comentario
    junto a `i_objetivo`. Por defecto 0,0, que es el comportamiento anterior.

    El orden importa: una version anterior conservaba el punto de la
    especificidad objetivo aunque incumpliera el recall minimo, teniendo
    disponible otro que cumplia AMBOS minimos. En triaje eso es al reves de
    lo que interesa, porque el falso negativo es el error caro.

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

    # Los dos suelos se elevan por el margen. El umbral se elige aqui sobre
    # VALIDACION y se aplica despues a datos que el modelo no vio, asi que el
    # punto que justo roza el suelo cae por encima o por debajo en prueba
    # segun el azar del muestreo. Medido por simulacion con las dimensiones
    # reales del proyecto (3 810 validacion / 3 811 prueba, 22,15% positivos,
    # AUC 0,888): sin margen solo el 84% de las corridas cumple el suelo en
    # prueba, y con 0,02 sube al 97% a cambio de 0,003 de recall. La corrida
    # de DenseNet121 del 23-sep cayo en ese 16%: especificidad 0,699 contra un
    # minimo de 0,700, trece diezmilesimas.
    i_objetivo = mejor_indice(especificidad_objetivo + margen_especificidad)
    i_minima = mejor_indice(especificidad_minima + margen_especificidad)

    def recall_de(indice):
        return -1.0 if indice is None else float(tpr[indice])

    if recall_de(i_objetivo) >= recall_objetivo:
        indice, paso = i_objetivo, "paso_1_especificidad_objetivo"
    elif recall_de(i_minima) >= recall_objetivo:
        indice, paso = i_minima, "paso_2_especificidad_minima"
    elif recall_de(i_objetivo) >= recall_minimo:
        indice, paso = i_objetivo, "paso_3_recall_minimo_con_especificidad_objetivo"
    elif recall_de(i_minima) >= recall_minimo:
        indice, paso = i_minima, "paso_4_recall_minimo_con_especificidad_minima"
    elif i_minima is not None:
        indice, paso = i_minima, "paso_5_no_se_alcanza_el_recall_minimo"
    else:
        indice, paso = int(np.argmax(tpr - fpr)), "sin_umbral_con_especificidad_minima"

    umbral = float(umbrales[indice])
    if not np.isfinite(umbral):  # roc_curve devuelve inf en el primer punto
        umbral = float(y_score.max()) + 1.0
    return umbral, metricas_en_umbral(y_true, y_score, umbral), paso
