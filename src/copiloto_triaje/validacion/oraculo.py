# -*- coding: utf-8 -*-
"""El modelo generador y su oráculo en forma cerrada (spec de SP5 §4.4-§4.5).

EL MODELO
---------
Para cada placa `i` con imagen `q_i = logit p_cal` y etiqueta `y_i`, la
puntuación de Heckerling sale de un umbral latente ordinal:

    u_i = ρ_y · z_y(q_i) + √(1 − ρ_y²) · ε_i,   ε ~ N(0, 1)
    k_i = #{j : u_i > τ_{y,j}},   j = 1..5

`z_y(q)` es la puntuación normal del rango medio de `q` en la clase `y`, y
los umbrales `τ_{y,j}` se resuelven para que `P(k | y)` sea EXACTAMENTE la de
los recuentos de la derivación, con cualquier ρ y pese a los empates de
`p_cal`. `ρ_y` es la correlación latente, dentro de la clase, entre lo que la
puntuación mide y lo que la imagen mide; con ρ = 0 la clínica es
condicionalmente independiente de la imagen y el escenario es el 0A.

EL ORÁCULO, Y LA TRAMPA
-----------------------
    P(k | q, y) = Φ((τ_{y,k+1} − ρ_y z_y(q)) / s_y) − Φ((τ_{y,k} − ρ_y z_y(q)) / s_y)
    logit P(Y = 1 | q, k) = q + ln P(k | q, 1) − ln P(k | q, 0)

El oráculo es función de `(q, k)` y NUNCA de la etiqueta: para cada placa se
evalúan las dos, `z_1(q_i)` y `z_0(q_i)`, en el mismo `q_i`, sea cual sea su
clase. Por eso `F̂_y` está definida sobre todo `q` real y no solo sobre las
placas de la clase. Usar el rango de la placa dentro de su propia clase para
las dos densidades pasa todas las pruebas de ρ = 0 y de marginales, y da
fracciones de log-RV conservado > 1: invierte la conclusión del §4.5. La
prueba `test_la_trampa_del_rango_propio_invierte_la_conclusion` lo caza.

Con `asma = no_se` el sistema solo ve `k4` (los cuatro signos), y el oráculo
marginaliza el asma con la regla de reparto del §4.2 (`matriz_k4`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.special import ndtr, ndtri

# Recuentos de la cohorte de DERIVACION de Heckerling por puntuacion 0..5
# (SP4 §4, PMC7422644 tabla 2). Son la verdad del generador: la RV verdadera
# de cada puntuacion es el cociente exacto de estas celdas, y la del sistema
# es la publicada redondeada (`heckerling.RV_POR_PUNTUACION`).
RECUENTOS = {1: (1, 11, 28, 42, 37, 15), 0: (48, 316, 232, 149, 30, 5)}
TOTALES = {1: 134, 0: 780}
PUNTUACIONES = np.arange(6)

# P(asma presente | k), la regla de reparto del spec §4.2: con k = 0 el asma
# esta presente (falta el punto de «sin asma»), con k = 5 ausente, y entre
# medias el punto de «sin asma» se asigna con probabilidad 0,9.
PROBABILIDAD_ASMA_PRESENTE = (1.0, 0.1, 0.1, 0.1, 0.1, 0.0)

# La rejilla del §4.5 y las seis celdas destacadas (ρ1, ρ0).
RHO_REJILLA = (0.0, 0.15, 0.3, 0.45, 0.6)
CELDAS_DESTACADAS = ((0.3, 0.3), (0.6, 0.6), (0.3, 0.0), (0.6, 0.0),
                     (0.0, 0.3), (0.0, 0.6))


def probabilidad_puntuacion(y: int) -> np.ndarray:
    """P(k | y) de los recuentos, k = 0..5."""
    return np.asarray(RECUENTOS[y], dtype=float) / TOTALES[y]


def rv_recuentos(k: int) -> float:
    """La RV verdadera de la puntuacion en el generador: el cociente exacto."""
    return (RECUENTOS[1][k] / TOTALES[1]) / (RECUENTOS[0][k] / TOTALES[0])


def fda_rango_medio(q_clase, q) -> np.ndarray:
    """F̂_y(q) = (#{q_j < q} + ½·#{q_j = q}) / n_y, sobre TODO q, acotada a
    [0,5/n_y ; 1 − 0,5/n_y]. En las placas de la propia clase coincide con
    su rango medio; la cota solo actua fuera del recorrido de la clase."""
    ordenadas = np.sort(np.asarray(q_clase, dtype=float))
    q = np.asarray(q, dtype=float)
    n = ordenadas.size
    menores = np.searchsorted(ordenadas, q, side="left")
    iguales = np.searchsorted(ordenadas, q, side="right") - menores
    return np.clip((menores + 0.5 * iguales) / n, 0.5 / n, 1.0 - 0.5 / n)


def puntuaciones_normales(q, etiquetas):
    """(z_1(q_i), z_0(q_i)) para TODAS las placas, evaluadas en el mismo q."""
    q = np.asarray(q, dtype=float)
    y = np.asarray(etiquetas, dtype=int)
    return (ndtri(fda_rango_medio(q[y == 1], q)),
            ndtri(fda_rango_medio(q[y == 0], q)))


def umbrales(z_clase, rho: float, y: int, pasos: int = 200) -> np.ndarray:
    """τ_{y,1..5} por biseccion: la media sobre las placas de la clase de
    Φ((τ − ρ z)/s) es P(k ≤ j − 1 | y). Con ρ = 0 sale Φ⁻¹(P(k ≤ j − 1 | y)).
    Monotona en τ, asi que la biseccion converge; 200 pasos sobre [−12, 12]
    dejan el umbral mas alla de la precision del double."""
    z = np.asarray(z_clase, dtype=float)
    s = math.sqrt(1.0 - rho * rho)
    acumulada = np.cumsum(probabilidad_puntuacion(y))[:-1]
    taus = []
    for objetivo in acumulada:
        bajo, alto = -12.0, 12.0
        for _ in range(pasos):
            medio = 0.5 * (bajo + alto)
            if float(np.mean(ndtr((medio - rho * z) / s))) < objetivo:
                bajo = medio
            else:
                alto = medio
        taus.append(0.5 * (bajo + alto))
    return np.asarray(taus)


def probabilidad_k_dado_q(z, rho: float, taus) -> np.ndarray:
    """(n, 6): P(k | q, y) con z = z_y(q) y los umbrales de la clase y."""
    z = np.asarray(z, dtype=float)
    s = math.sqrt(1.0 - rho * rho)
    bordes = np.concatenate(([-np.inf], np.asarray(taus, dtype=float), [np.inf]))
    fda = ndtr((bordes[None, :] - rho * z[:, None]) / s)
    return np.diff(fda, axis=1)


def matriz_k4() -> np.ndarray:
    """M[k, k4] = P(k4 | k): con el asma presente k4 = k (el punto de «sin
    asma» no esta); con el asma ausente, k4 = k − 1."""
    m = np.zeros((6, 5))
    for k, presente in enumerate(PROBABILIDAD_ASMA_PRESENTE):
        if k <= 4:
            m[k, k] += presente
        if k >= 1:
            m[k, k - 1] += 1.0 - presente
    return m


@dataclass(frozen=True)
class Modelo:
    rho1: float
    rho0: float
    etiquetas: np.ndarray
    z1: np.ndarray      # z_1(q_i) de TODAS las placas
    z0: np.ndarray      # z_0(q_i) de TODAS las placas
    tau1: np.ndarray
    tau0: np.ndarray

    def z_propia(self) -> np.ndarray:
        """z_y(q_i) de cada placa dentro de SU clase: para SORTEAR. El oraculo
        no la usa nunca (ver la trampa en el docstring del modulo)."""
        return np.where(self.etiquetas == 1, self.z1, self.z0)

    def probabilidades(self):
        """(P(k | q_i, 1), P(k | q_i, 0)) para todas las placas, las dos en el mismo q."""
        return (probabilidad_k_dado_q(self.z1, self.rho1, self.tau1),
                probabilidad_k_dado_q(self.z0, self.rho0, self.tau0))


def ajustar(q, etiquetas, rho1: float = 0.0, rho0: float = 0.0) -> Modelo:
    """El modelo de una celda (ρ1, ρ0) sobre las placas dadas."""
    for rho in (rho1, rho0):
        if not 0.0 <= rho < 1.0:
            raise ValueError(f"rho debe estar en [0, 1), y es {rho!r}")
    y = np.asarray(etiquetas, dtype=int)
    z1, z0 = puntuaciones_normales(q, y)
    return Modelo(float(rho1), float(rho0), y, z1, z0,
                  umbrales(z1[y == 1], rho1, 1), umbrales(z0[y == 0], rho0, 0))


def log_rv_condicional(modelo: Modelo) -> np.ndarray:
    """(n, 6): ln P(k | q_i, 1) − ln P(k | q_i, 0), la RV de la puntuacion una
    vez vista la imagen. Con ρ = 0 es ln RV_recuentos(k) en todas las filas."""
    p1, p0 = modelo.probabilidades()
    return np.log(p1) - np.log(p0)


def logit_oraculo(modelo: Modelo, q, k) -> np.ndarray:
    """logit P(Y = 1 | q, k) = q + ln P(k | q, 1) − ln P(k | q, 0)."""
    k = np.asarray(k, dtype=int)
    return (np.asarray(q, dtype=float)
            + log_rv_condicional(modelo)[np.arange(k.size), k])


def logit_oraculo_no_se(modelo: Modelo, q, k4) -> np.ndarray:
    """Con el asma oculta el sistema ve k4 (los cuatro signos): el oraculo
    condiciona en (q, k4) y marginaliza el asma con la regla de reparto."""
    k4 = np.asarray(k4, dtype=int)
    p1, p0 = modelo.probabilidades()
    m = matriz_k4()
    filas = np.arange(k4.size)
    return (np.asarray(q, dtype=float)
            + np.log((p1 @ m)[filas, k4]) - np.log((p0 @ m)[filas, k4]))


def correlacion_teorica(modelo: Modelo, y: int) -> float:
    """r_y = Cov(k, z_y) / (sd(k | y) · sd(z_y)) dentro de la clase, en forma
    cerrada con E[k | q_i, y] = Σ_k k · P(k | q_i, y) (spec §4.5)."""
    en_clase = modelo.etiquetas == y
    z = (modelo.z1 if y == 1 else modelo.z0)[en_clase]
    rho, tau = (modelo.rho1, modelo.tau1) if y == 1 else (modelo.rho0, modelo.tau0)
    esperanza = probabilidad_k_dado_q(z, rho, tau) @ PUNTUACIONES
    cov = float(np.mean(z * esperanza) - np.mean(z) * np.mean(esperanza))
    pk = probabilidad_puntuacion(y)
    sd_k = math.sqrt(float(pk @ PUNTUACIONES ** 2 - (pk @ PUNTUACIONES) ** 2))
    return cov / (sd_k * float(np.std(z)))
