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


def test_paso_2_solo_si_alcanza_el_recall_objetivo():
    """Clases muy solapadas: con especificidad 0,75 no se alcanza 0,85 de
    recall. La regla solo se queda en el paso 2 si ALCANZA el objetivo."""
    rng = np.random.default_rng(1)
    y = np.array([1] * 200 + [0] * 800)
    score = np.where(y == 1, rng.normal(0.55, 0.20, 1000), rng.normal(0.45, 0.20, 1000))
    umbral, m, paso = elegir_umbral(y, score)
    if paso == "paso_2_especificidad_minima":
        assert m["recall"] >= 0.85
    assert m["especificidad"] >= 0.70


def test_prefiere_el_punto_que_cumple_AMBOS_minimos():
    """El fallo real que esto previene, medido en la primera corrida:

    con especificidad >= 0,75 el recall maximo era 78% -incumple el minimo de
    80%-, mientras que relajando a especificidad >= 0,70 llegaba a 83,4%, que
    cumple los dos minimos. La regla vieja conservaba el primero "por no
    forzar el umbral" y reportaba un recall por debajo del minimo teniendo
    disponible uno que si lo cumplia. En triaje eso es exactamente al reves:
    el falso negativo es el error caro.
    """
    # Curva construida para que exista esa disyuntiva de forma nitida.
    rng = np.random.default_rng(7)
    y = np.array([1] * 300 + [0] * 700)
    score = np.where(y == 1, rng.normal(0.62, 0.17, 1000), rng.normal(0.40, 0.17, 1000))
    umbral, m, paso = elegir_umbral(y, score, 0.75, 0.70, 0.85, 0.80)

    if m["recall"] < 0.85:  # no se alcanza el objetivo: estamos en pasos 3/4/5
        assert paso.startswith(("paso_3", "paso_4", "paso_5"))
        # Si la eleccion cumple el minimo de recall, la especificidad debe
        # seguir respetando el piso: nunca se baja de 0,70 para maquillar.
        if m["recall"] >= 0.80:
            assert m["especificidad"] >= 0.70
            assert paso.startswith(("paso_3", "paso_4"))


def test_relaja_la_especificidad_si_es_lo_unico_que_cumple_el_recall_minimo():
    """Si con especificidad objetivo se queda corto del recall minimo pero
    relajando al piso si se cumple, la regla DEBE relajar. Es el caso que la
    version anterior resolvia al reves."""
    # tpr/fpr controlados: puntajes ordenados a mano en dos tramos.
    y = np.array([1] * 100 + [0] * 300)
    score = np.concatenate([
        np.linspace(0.95, 0.55, 82),   # 82 positivos bien puntuados
        np.linspace(0.45, 0.05, 18),   # 18 positivos mal puntuados
        np.linspace(0.60, 0.50, 60),   # 60 negativos que estorban arriba
        np.linspace(0.40, 0.01, 240),  # 240 negativos bien puntuados
    ])
    umbral, m, paso = elegir_umbral(y, score, 0.75, 0.70, 0.85, 0.80)
    assert m["recall"] >= 0.80, "no se cumplio el recall minimo teniendo como"
    assert m["especificidad"] >= 0.70, "se bajo del piso de especificidad"


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


def _puntuaciones_separables(n=4000, semilla=7, separacion=1.72):
    """Puntuaciones con la prevalencia (22,15%) y el AUC (~0,888) reales."""
    rng = np.random.default_rng(semilla)
    y = (rng.random(n) < 0.2215).astype(int)
    return y, rng.normal(separacion * y, 1.0)


def test_el_margen_aleja_el_umbral_del_suelo_de_especificidad():
    """Corrida de DenseNet121 del 23-sep: el umbral se eligio en validacion
    con especificidad 0,70027 -veintisiete diezmilesimas por encima del suelo
    de 0,70- y en prueba cayo a 0,69869. No fue mala suerte: elegir el punto
    que roza el suelo deja el resultado en datos no vistos a merced del
    muestreo, y medido por simulacion falla una de cada seis veces.

    El margen eleva el suelo AL ELEGIR, sin tocar los criterios de aceptacion.
    """
    y, s = _puntuaciones_separables()

    _, sin_margen, _ = elegir_umbral(y, s, 0.75, 0.70, 0.85, 0.80)
    _, con_margen, _ = elegir_umbral(y, s, 0.75, 0.70, 0.85, 0.80,
                                     margen_especificidad=0.05)

    assert con_margen["especificidad"] > sin_margen["especificidad"], (
        "el margen tiene que empujar el punto de operacion lejos del suelo")
    assert con_margen["especificidad"] >= 0.75, (
        f"con margen 0,05 sobre un suelo de 0,70 la especificidad elegida "
        f"deberia superar 0,75; salio {con_margen['especificidad']:.4f}")


def test_sin_margen_el_comportamiento_es_el_de_antes():
    """El parametro es nuevo y su ausencia no puede cambiar nada: las corridas
    ya reportadas tienen que seguir siendo reproducibles con el mismo codigo."""
    y, s = _puntuaciones_separables()
    esperado = elegir_umbral(y, s, 0.75, 0.70, 0.85, 0.80)
    con_cero = elegir_umbral(y, s, 0.75, 0.70, 0.85, 0.80,
                             margen_especificidad=0.0)
    assert esperado[0] == con_cero[0]
    assert esperado[2] == con_cero[2]


def test_el_margen_cuesta_recall_pero_poco():
    """El margen no es gratis: exigir mas especificidad baja el recall. Se fija
    que el precio sea pequenio, porque si fuera grande la cura seria peor que
    la enfermedad y habria que elegir otro valor por defecto."""
    y, s = _puntuaciones_separables()
    _, sin_margen, _ = elegir_umbral(y, s, 0.75, 0.70, 0.85, 0.80)
    _, con_margen, _ = elegir_umbral(y, s, 0.75, 0.70, 0.85, 0.80,
                                     margen_especificidad=0.02)
    caida = sin_margen["recall"] - con_margen["recall"]
    assert caida < 0.05, f"el margen de 0,02 costo {caida:.4f} de recall"
