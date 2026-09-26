"""Convierte la salida del modelo en evidencia que SP4 pueda combinar.

El modelo se entreno con `BCEWithLogitsLoss(pos_weight = negativos/positivos)`
para compensar que solo el 22,15% de las radiografias son positivas; sobre esa
proporcion el peso ronda 3,5. (Este docstring decia `pos_weight=3.44`, que se
contradecia con el 22,15% de la frase siguiente: el 3,44 sale del 22,53% de
RSNA ENTERO, antes de descartar los 1 276 menores y los 5 de edad imposible. El
calibrador desplegado declara `prevalencia = 0,2215`, que da 3,51.) Eso desplaza su salida
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

# Ultimo recurso para una curva DEGENERADA -toda ella saturada en 0,0 o en 1,0,
# es decir sin un solo tramo con positivos y negativos a la vez-. No es la cota
# normal: la cota normal la pone la propia curva (ver `Calibrador.__init__`).
# Aqui solo evita la division por cero cuando no hay ningun valor sostenido del
# que sacarla. Un calibrador asi esta roto y no deberia llegar a produccion.
MARGEN_CURVA_DEGENERADA = 1e-6


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
        # La cota de la evidencia sale de la CURVA, no de una constante. La
        # isotonica satura en 0,0 y en 1,0 en los tramos donde no queda ningun
        # negativo (o ningun positivo): en el calibrador desplegado eso es UN
        # punto de 200 en cada extremo, estimado desde un pedazo de curva sin
        # contraejemplos. Fuera de esos dos puntos, el valor sostenido mas
        # extremo es lo mas lejos que las 3 810 radiografias de validacion
        # permiten llegar, y ahi se pone el tope.
        #
        # Se calculan aqui y no se clavan como literales a proposito: el
        # calibrador se reajusta cada vez que se reentrena, y unos literales
        # seguirian describiendo la curva vieja mientras el JSON ya describe
        # otra. Se recalculan tambien tras `desde_json`, que pasa por aqui.
        sostenidos = self.y[(self.y > 0.0) & (self.y < 1.0)]
        if sostenidos.size:
            self.probabilidad_minima_sostenida = float(sostenidos.min())
            self.probabilidad_maxima_sostenida = float(sostenidos.max())
        else:
            # Curva degenerada: no hay ningun valor sostenido del que sacar la
            # cota. Se cae al margen minimo solo para no dividir por cero.
            self.probabilidad_minima_sostenida = MARGEN_CURVA_DEGENERADA
            self.probabilidad_maxima_sostenida = 1 - MARGEN_CURVA_DEGENERADA

    def calibrar(self, probabilidad_cruda: float) -> float:
        """Probabilidad calibrada a la prevalencia del conjunto de ajuste.

        El resultado se acota a los extremos SOSTENIDOS de la curva -el valor
        mas bajo que no sea 0,0 y el mas alto que no sea 1,0-, y no a una
        constante cerca de 0 y de 1. La diferencia no es cosmetica y no es
        solo la division por cero:

        La isotonica devuelve 0,0 y 1,0 exactos en los tramos de los extremos
        donde no queda ningun negativo (o ningun positivo). Recortarlos a
        1e-6 y 1-1e-6 evita el p/(1-p) infinito, pero deja salir por
        `razon_de_verosimilitud` un numero perfectamente utilizable -3,5e-06 y
        3,5e+06 con el calibrador desplegado- que SP4 multiplicara por las
        odds de la regla clinica. Un paciente con sospecha alta (previo 0,90)
        acabaria con posterior 0,003% si la imagen cae en ese unico punto
        saturado, frente al 12,8% del vecino inmediato que si tiene datos
        detras: un salto de 4 630x decidido por una sola radiografia, en la
        direccion de fabricar certeza de ausencia. En el extremo alto pasa lo
        simetrico y fabrica certeza de presencia.

        Ninguna radiografia justifica mas certeza que la que los datos de
        validacion sostienen, asi que el tope es lo que la curva sostiene. Que
        se derive de `self.y` -y no de un literal- es lo que mantiene la cota
        pegada al calibrador que de verdad se esta sirviendo.
        """
        bruto = float(np.interp(float(probabilidad_cruda), self.x, self.y))
        return min(max(bruto, self.probabilidad_minima_sostenida),
                   self.probabilidad_maxima_sostenida)

    def razon_de_verosimilitud(self, probabilidad_cruda: float) -> float:
        """Lo que SP4 debe multiplicar por las odds de la regla clinica.

        RV = odds_posterior / odds_previo. No acota por su cuenta: `calibrar`
        ya deja la probabilidad dentro de lo que la curva sostiene, y acotar en
        dos sitios daria dos fuentes de verdad que pueden divergir. Por tanto
        la RV queda dentro de [RV(minima_sostenida), RV(maxima_sostenida)] sin
        que aqui haga falta ninguna comprobacion.
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
