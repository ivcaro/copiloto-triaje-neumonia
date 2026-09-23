"""Convierte la salida del modelo en evidencia que SP4 pueda combinar.

El modelo se entreno con `BCEWithLogitsLoss(pos_weight=3.44)` para compensar
que solo el 22,15% de las radiografias son positivas. Eso desplaza su salida
hacia arriba: un 0,74 NO significa 74% de probabilidad de neumonia.

SP4 va a multiplicar la evidencia de imagen por las probabilidades a favor
(odds) de la regla clinica. Meter ahi la salida cruda produce un posterior
equivocado sin que nada falle de forma visible, que es la peor clase de error
en un sistema clinico.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression


class Calibrador:
    """Mapea la salida cruda del modelo a probabilidad y razon de verosimilitud.

    Se guarda como una lista de puntos (x, y) de la curva isotonica, no como un
    objeto de scikit-learn serializado: asi son unos kilobytes que se versionan
    en Git y el despliegue no queda atado a la version exacta de la libreria.
    """

    def __init__(self, x, y, prevalencia: float, procedencia: str):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        self.prevalencia = float(prevalencia)
        self.procedencia = str(procedencia)

    def calibrar(self, probabilidad_cruda: float) -> float:
        """Probabilidad calibrada a la prevalencia del conjunto de ajuste.

        El resultado se recorta a [1e-6, 1-1e-6] y no se deja salir 0 ni 1
        exactos, que es lo que la isotonica devuelve en los extremos cuando
        un tramo de la curva no tiene positivos (o no tiene negativos). No es
        cosmetica: lo primero que hace quien recibe una probabilidad para
        combinarla bayesianamente es calcular p/(1-p), y con p=1 eso es una
        division por cero. Ademas, ninguna radiografia justifica certeza
        absoluta.
        """
        bruto = float(np.interp(float(probabilidad_cruda), self.x, self.y))
        return min(max(bruto, 1e-6), 1 - 1e-6)

    def razon_de_verosimilitud(self, probabilidad_cruda: float) -> float:
        """Lo que SP4 debe multiplicar por las odds de la regla clinica.

        RV = odds_posterior / odds_previo. No recorta: `calibrar` ya garantiza
        que la probabilidad esta dentro del intervalo abierto, y recortar en
        dos sitios daria dos fuentes de verdad que pueden divergir.
        """
        p = self.calibrar(probabilidad_cruda)
        odds_posterior = p / (1 - p)
        odds_previo = self.prevalencia / (1 - self.prevalencia)
        return float(odds_posterior / odds_previo)

    def a_json(self, ruta) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps({
            "x": self.x.tolist(),
            "y": self.y.tolist(),
            "prevalencia": self.prevalencia,
            "procedencia": self.procedencia,
        }, indent=2), encoding="utf-8")
        return ruta

    @classmethod
    def desde_json(cls, ruta) -> "Calibrador":
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return cls(d["x"], d["y"], d["prevalencia"], d["procedencia"])


def ajustar_calibrador(y_true, y_score, prevalencia: float,
                       procedencia: str, n_puntos: int = 200) -> Calibrador:
    """Ajusta una regresion isotonica sobre VALIDACION.

    Isotonica y no Platt porque no impone forma sigmoide: solo exige que la
    probabilidad no baje cuando la puntuacion sube, que es la unica propiedad
    que aqui es innegociable. Con 3 810 ejemplos de validacion hay datos de
    sobra para estimarla.

    NUNCA se ajusta sobre el conjunto de prueba: eso seria usar la prueba para
    construir el modelo e invalidaria todas sus metricas.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_score = np.asarray(y_score, dtype=float)
    modelo = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    modelo.fit(y_score, y_true)
    # Se muestrea la curva en una rejilla: es lo que viaja en el JSON.
    x = np.linspace(float(y_score.min()), float(y_score.max()), n_puntos)
    return Calibrador(x, modelo.predict(x), prevalencia, procedencia)
