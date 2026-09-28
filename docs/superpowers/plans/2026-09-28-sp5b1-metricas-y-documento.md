# SP5-B1 — Métricas, rejilla con bootstrap, figuras y documento de la validación semisintética: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos
> usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** medir, sobre las 3 811 placas del conjunto de prueba y con la
clínica sorteada por el generador de SP5-A, qué le pasa a la combinación
bayesiana del sistema cuando la clínica y la imagen no son condicionalmente
independientes —cuatro modelos puntuales, la horquilla frente al oráculo, la
sensibilidad al previo y 0C—, con bootstrap en 0A y en las seis celdas
destacadas, y dejarlo publicado: `resultados_simulacion.json`, figuras a 300
DPI y un documento de análisis generado sin teclear ninguna cifra. Además, la
herramienta que medirá la latencia de extremo a extremo y los residuos que la
revisión final de SP5-A dejó apuntados.

**Arquitectura:** dos módulos puros nuevos en `copiloto_triaje.validacion`:
`metricas` (funciones sobre vectores: calibración, ECE con su suelo,
horquilla, percentiles) y `simulacion` (une las placas congeladas, el
generador, el oráculo de la celda y el SISTEMA, que es
`heckerling.combinacion` / `combinar` llamado caso a caso; evalúa una celda
`(ρ1, ρ0)`, su bootstrap, la escala legible, la sensibilidad al previo y 0C).
Un tercer módulo puro, `informe`, redacta el documento desde el diccionario
de resultados. El script `scripts/validar_combinacion.py` corre la rejilla
(una celda por proceso), escribe el JSON, **lo vuelve a leer** y de esa
lectura dibuja las figuras y escribe el documento. `matplotlib` vive solo en
el script.

**Pila:** Python ≥ 3.11 (intérprete de la máquina de desarrollo:
`C:/venv-copiloto/Scripts/python.exe`, 3.13), numpy, pandas, scipy
(`brentq`, `expit`), scikit-learn (`roc_auc_score`; `LogisticRegression` solo
en una prueba de contraste), matplotlib ≥ 3.9 como extra `figuras`, pytest.
Las pruebas se corren desde la raíz del repo con
`C:/venv-copiloto/Scripts/python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`
— §4.3 a §4.8 (lo que se mide y dónde vive), §6.3 (latencia), §8 (pruebas) y
§11.2-§11.3 (criterios de aceptación). En cualquier contradicción manda el
spec, salvo en lo que la sección «Decisiones del plan» fija porque el spec lo
dejaba abierto. **No cubre** 0B (recortado: el artículo de Ebell es de pago y
no está en manos del equipo), la anonimización del §6.1 (plan SP5-B2) ni los
documentos del §6.7 (plan SP5-C).

**Parte de:** `main` en `1f328da` (SP5-A fusionado). Rama de trabajo:
`sp5b1-metricas`.

## Restricciones globales

Copiadas del spec de SP5. **Los requisitos de cada tarea las incluyen.**

1. **La combinación se calcula llamando a `heckerling.combinacion` y
   `heckerling.combinar`** —el mismo código que sirve el contenedor—, nunca a
   una reimplementación (spec §4.6). Nadie toca `heckerling.py`.
2. **No se reentrena, no se recalibra y no se ajusta** ninguna RV ni ninguna
   prevalencia con estos datos. Solo se mide (spec §4.8, §7).
3. **El previo del análisis principal es la prevalencia del conjunto, 0,2215**,
   leída de `servidor/calibrador.json`; la sensibilidad usa
   `heckerling.PREVALENCIA_COHORTE` (0,1466). Ninguna de las dos se teclea.
4. **Bootstrap (spec §4.6):** `B = 1 000` réplicas; cada réplica remuestrea con
   reemplazo las 3 811 placas y vuelve a sortear la clínica; `z_y`, los
   umbrales `τ` y el calibrador quedan **fijos**, calculados una vez sobre el
   conjunto completo; intervalos del 95 % por percentiles; las diferencias
   entre modelos se calculan **dentro de cada réplica**. Se corre en 0A y en
   las seis celdas destacadas; el resto de la rejilla va sin intervalos.
5. **Los modelos puntuales leen `independencia` y `dependencia` del bloque,
   nunca `minima` ni `maxima`**, y solo sobre los casos con el asma conocida;
   los `no_se` van en fila aparte.
6. **La horquilla se compara con el oráculo en log-odds, sobre los extremos sin
   redondear** (`combinar`), con la tolerancia `ε = 0,015` —la misma de 0A.3,
   definida UNA vez en `metricas.EPSILON`—. **La fila 0A es la comprobación de
   la métrica: colas exactamente 0 y contención 100 %.** Se llama contención,
   no cobertura: no es un intervalo de confianza.
7. **La ECE** usa 10 bins de igual masa, con los empates de `p` rotos por el
   orden de `patientId`, y se publica **al lado de su suelo de ruido**
   (etiquetas `Bernoulli(p)` del propio modelo, 200 veces: media y percentil
   95), nunca contra un umbral absoluto.
8. **Regla de rótulo (spec §6.7.7):** todo artefacto de resultados lleva
   «simulación semisintética» en su título o cabecera y vive en
   `docs/validacion-semisintetica/`; el análisis, en
   `docs/validacion-semisintetica-sp5.md`, lo lleva en el título.
9. **Ninguna cifra del análisis se teclea:** el documento y las figuras se
   generan leyendo `resultados_simulacion.json`.
10. **`matplotlib` solo en `scripts/`, nunca en `src/`** (el Dockerfile instala
    el paquete entero en el contenedor). Se importa dentro de las funciones
    de figura, con `matplotlib.use("Agg")` antes de `pyplot`, y se declara en
    `pyproject.toml` como extra `figuras`, nunca en `dependencies`. Figuras a
    300 DPI.
11. **Las pruebas corren sin red, sin Docker y sin los pesos.** Los insumos son
    `docs/validacion-semisintetica/crudas_prueba.csv` (congelada) y
    `servidor/calibrador.json`.
12. **Ningún identificador del cliente, del equipo ni de la máquina** en lo que
    se escriba: ni rutas absolutas con usuario, ni dominios, ni nombres
    propios. En ejemplos, `<RSNA_RAIZ>` y `https://n8n.ejemplo.test`.
13. **Lo que la simulación puede afirmar y lo que no** (spec §4.7) va escrito en
    el documento: no mide exactitud clínica; las viñetas no son pacientes; la
    exactitud de la regla es la publicada y la dependencia es la supuesta.
14. Mensajes de commit al estilo del repo (`feat(validacion): …`,
    `test(…): …`, `docs(sp5): …`), con la línea final
    `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Decisiones del plan

Lo que el spec dejaba abierto, fijado aquí con su razón.

- **D1. Dos módulos, no uno.** El spec §4.8 nombra `metricas.py`; la
  orquestación por celda (sistema, oráculo, bootstrap, previo, 0C) va en un
  módulo aparte, `simulacion.py`, para que `metricas.py` sea solo funciones
  sobre vectores que se prueban con valores a mano.
- **D2. Semillas.** La estimación puntual usa la clínica de
  `generar(modelo, SEMILLA_PUNTUAL)` con `SEMILLA_PUNTUAL = 1` (la misma que
  comprueba 0A). La réplica `b = 0 … B − 1` usa
  `generar(modelo, SEMILLA_CLINICA + b)` y los índices de
  `default_rng(SEMILLA_INDICES + b).integers(0, n, n)`, con
  `SEMILLA_CLINICA = 10 000` y `SEMILLA_INDICES = 20 000`. El spec dice «la
  semilla `b`»; se desplaza para que ninguna réplica repita la clínica de la
  estimación puntual, y las tres constantes se escriben en el JSON.
- **D3. La réplica llama al sistema caso a caso.** Cada réplica genera la
  clínica con `generador.generar` y llama a `combinacion` para las 3 811
  placas (≈ 0,08 s por réplica con las métricas; 1 000 réplicas ≈ 1,3 min por
  celda). No hay camino vectorizado: sería una reimplementación. El coste se
  reparte con **un proceso por celda** (`ProcessPoolExecutor`); el trabajador
  es `simulacion.evaluar_tarea`, en el paquete, para que un proceso hijo lo
  pueda importar.
- **D4. Probabilidades redondeadas, extremos sin redondear.** Los modelos
  puntuales usan lo que el sistema entrega (`independencia[0]`,
  `dependencia[0]`: 4 decimales). Los extremos de la horquilla se recalculan
  con `combinar` y `mas_informativa`, y `salidas_del_sistema` comprueba en
  cada caso que el bloque es su redondeo; si no lo fuera, se detiene.
- **D5. Pendiente e intercepto sin librería.** La pendiente es la de la
  regresión logística sin penalizar de `Y` sobre `logit p` (2 parámetros); el
  intercepto, el de la calibración global con la pendiente fijada en 1, por
  `brentq`. scikit-learn no admite *offset* y `statsmodels` no está
  instalado. **Antes de iterar se dice cuándo la pendiente no existe**: con
  una sola clase, con todas las `p` iguales, o con las clases separadas por
  las `p` (el máximo de una clase no supera el mínimo de la otra). Si existe,
  es única: la busca Newton con retroceso (un paso que empeora la
  verosimilitud se acorta; sin eso Newton se dispara cuando el modelo está
  muy lejos de calibrado) y, si se queda sin paso, una región de confianza
  con la hessiana exacta (`scipy.optimize.minimize`, `trust-exact`) que
  Newton pule. Las pruebas la contrastan con `LogisticRegression(C=np.inf)`
  —una de ellas con un modelo que ordena al revés— y con la forma cerrada de
  dos grupos. **Si una pendiente no se puede calcular, la corrida se
  detiene** (`ArithmeticError`): una réplica del bootstrap no se cuenta en
  silencio como dato ausente.
- **D5 bis. Las métricas rechazan lo que no pueden medir.** Las métricas por
  modelo exigen `y` en 0/1 y `p` entre 0 y 1; las de log-odds (`horquilla`,
  `error_puntual`, `contencion_en_rango`), vectores de la misma forma y
  finitos. Un NaN no es mayor ni menor que nada: sin la guarda, un caso sin
  horquilla contaría como «dentro».
- **D6. Las colas, en log-odds.** `λ < −ε/|Δ|` equivale a «el oráculo queda más
  allá del extremo conservador en más de ε log-odds»; se implementa así, sin
  dividir. `λ` se publica como posición (mediana y cuartiles).
- **D7. La escala legible, en forma cerrada.** El spec pide mediana y cuartiles
  de `ln[P(k | q, 1) / P(k | q, 0)]` por puntuación y por lado de la imagen,
  sin decir sobre qué casos. Se calculan sobre todas las placas del lado,
  **ponderando cada placa por `P(k | q_i, y_i)`**, la probabilidad con que el
  generador le da esa puntuación: es la distribución esperada entre los casos
  con esa puntuación, sin ruido de sorteo. La «fracción mediana de las
  puntuaciones extremas» junta k ∈ {0, 1, 4, 5} con los mismos pesos.
- **D8. Sensibilidad al previo.** Para los dos modelos combinados: Brier, ECE
  con su suelo e intercepto con 0,1466, al lado de los del análisis principal,
  y los casos que cambian de banda con su sentido. La prueba afirma que la
  **diferencia** de interceptos es el desplazamiento analítico (+0,5045): el
  «≈ +0,50» del spec §4.3. Además, los cambios de banda de la categoría del
  sistema (`categoria_del_sistema(bloque)["primaria"]`) sobre los 3 811 casos.
- **D9. 0C** se calcula sobre la clínica de 0A, en los casos con el asma
  conocida, comparando la banda de `independencia[0]` con la de
  `combinar(previo, RV_VALIDACION[k], rv_imagen)`. `combinar` es el código del
  servidor; lo único distinto es la RV, que es el objeto del cálculo.
- **D10. El JSON no lleva fecha** y las huellas de los insumos se calculan con
  los finales de línea normalizados a LF (`datos.huella_de_texto`): el repo
  tiene `core.autocrlf=true`, y la huella del mismo fichero versionado tiene
  que ser la misma en Windows y en Linux. Así una prueba puede comprobar que
  lo publicado corresponde a los insumos y al código de hoy.
- **D11. El suelo de la ECE y la curva de fiabilidad** se calculan solo en la
  estimación puntual, no dentro de cada réplica (200 × 7 000 ECE sería lo
  único caro del script). Por eso `suelo` no lleva intervalo.
- **D12. Los intervalos van en un diccionario plano** `"ruta.con.puntos" →
  [li, ls]` por celda (`"horquilla.todos.contencion"`), con una entrada por
  cada cifra `float` medida. Los recuentos no llevan intervalo.
- **D13. El punto medio de los `no_se`** es la media de los logits de las dos
  posteriores de independencia (spec §4.6: «el punto medio en log-odds»).

## Estructura de ficheros

| Fichero | Tarea | Qué es |
| :--- | :--- | :--- |
| `src/copiloto_triaje/validacion/metricas.py` | 1 | métricas puras sobre vectores |
| `tests/test_metricas.py` | 1 | valores conocidos a mano y casos de borde |
| `tests/test_validacion_0a.py` | 1 | pasa a usar `metricas.EPSILON` |
| `src/copiloto_triaje/validacion/simulacion.py` | 2, 3 | la simulación por celda |
| `tests/test_simulacion.py` | 2, 3 | sobre las placas congeladas; la fila 0A |
| `src/copiloto_triaje/validacion/datos.py` | 4 | gana `huella_de_texto` |
| `scripts/validar_combinacion.py` | 4, 5, 6 | rejilla, JSON, figuras, documento |
| `tests/conftest.py` | 4 | fixtures `validar` y `resultados_minimos` |
| `tests/test_validar_combinacion.py` | 4, 5, 6 | el script |
| `pyproject.toml` | 5 | el extra `figuras` |
| `src/copiloto_triaje/validacion/informe.py` | 6 | el documento, desde el diccionario |
| `tests/test_informe.py` | 6 | el documento |
| `docs/validacion-semisintetica/resultados_simulacion.json`, `*.png` | 7 | la corrida real |
| `docs/validacion-semisintetica-sp5.md` | 7 | el análisis generado |
| `tests/test_resultados_publicados.py` | 7 | lo publicado corresponde a hoy |
| `docs/validacion-semisintetica/README.md` | 7, 8 | una sección por artefacto |
| `scripts/medir_latencia.py`, `tests/test_medir_latencia.py` | 8 | la latencia |
| `pruebas/reproducir_casos.py` | 8, 9 | `latencias.json`; `patientId` repetido |
| `src/copiloto_triaje/validacion/concordancia.py`, `generador.py`, `scripts/preparar_sesion.py` | 9 | residuos de SP5-A |
| `README.md` | 10 | el estado de SP5 |

---

### Tarea 1: Las métricas

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/metricas.py`
- Crear: `tests/test_metricas.py`
- Modificar: `tests/test_validacion_0a.py` (la tolerancia pasa a ser `metricas.EPSILON`)

**Interfaces:**
- Consume: nada del paquete. `numpy`, `scipy.optimize` (`brentq`, `minimize`),
  `scipy.special.expit`, `sklearn.metrics.roc_auc_score`.
- Produce (todas aceptan listas o arrays):
  - Constantes `EPSILON = 0.015`, `BINS = 10`, `REPETICIONES_SUELO = 200`,
    `SEMILLA_SUELO = 20261009`, `MARGEN = 1e-6`, `CUARTILES = (0.25, 0.5, 0.75)`.
  - `logit(p) -> np.ndarray`
  - `auc(y, p) -> float`, `brier(y, p) -> float`
  - `auc(y, p)`, `pendiente_de_calibracion(y, p, pasos=100)` e
    `intercepto_de_calibracion(y, p)` lanzan `ArithmeticError` con una sola
    clase; la pendiente, además, con todas las `p` iguales o con las clases
    separadas por las `p`
  - `pendiente_de_calibracion(y, p, pasos=100) -> float`
  - `intercepto_de_calibracion(y, p) -> float`
  - `ece(y, p, orden, bins=BINS) -> float`
  - `fiabilidad(y, p, orden, bins=BINS) -> list[dict]` con `n`, `p_media`, `observada`
  - `suelo_de_ece(p, orden, repeticiones=REPETICIONES_SUELO, semilla=SEMILLA_SUELO, bins=BINS) -> dict` con `media`, `p95`
  - `resumen_de_modelo(y, p, orden) -> dict` con `auc`, `brier`, `pendiente`, `intercepto`, `ece`
  - `horquilla(l_oraculo, l_dependencia, l_independencia, epsilon=EPSILON) -> dict`
    con `n`, `sin_horquilla`, `lambda` (`q1`, `mediana`, `q3`), `bajo`, `sobre`, `contencion`
  - `error_puntual(l_sistema, l_oraculo) -> dict` con `n`, `error_abs_mediano`, `sesgo_mediano`
  - `contencion_en_rango(l_oraculo, l_minima, l_maxima, epsilon=EPSILON) -> dict`
    con `n`, `bajo`, `sobre`, `contencion`
  - `percentiles(valores, alfa=0.05) -> list` (`[li, ls]`, o `[None, None]`)
  - `cuantiles_ponderados(valores, pesos, cuantiles=CUARTILES) -> np.ndarray`

**Qué significa cada cosa** (léelo antes de copiar el código):
`pendiente < 1` es la forma cuantitativa de «el modelo exagera»; el
`intercepto` es lo que habría que sumar a todos los logits para que la media
predicha fuera la observada. En `horquilla`, `λ = 0` es el extremo
conservador (dependencia total) y `λ = 1` la independencia, apunte la
evidencia hacia donde apunte; `bajo` es la fracción de casos en que el
oráculo queda más allá del extremo conservador en más de `ε` log-odds, y
`sobre`, más allá de la independencia.

- [ ] **Paso 1: Crear la rama**

```bash
git checkout main
git checkout -b sp5b1-metricas
```

- [ ] **Paso 2: Escribir las pruebas de las métricas por modelo**

Crea `tests/test_metricas.py` con este contenido:

```python
"""Las métricas de la simulación (spec de SP5 §4.6, §8): cada una sobre
vectores cuyos valores se conocen a mano."""
import math

import numpy as np
import pytest

from copiloto_triaje.validacion import metricas


def _logit(p):
    return math.log(p / (1.0 - p))


def _grupos(*grupos):
    """(y, p) a partir de (p, casos, positivos) por grupo."""
    y, p = [], []
    for prob, casos, positivos in grupos:
        y += [1] * positivos + [0] * (casos - positivos)
        p += [prob] * casos
    return np.array(y), np.array(p)


def test_logit_acota_los_extremos():
    assert metricas.logit([0.5])[0] == 0.0
    assert metricas.logit([0.0])[0] == pytest.approx(_logit(metricas.MARGEN))
    assert metricas.logit([1.0])[0] == pytest.approx(-_logit(metricas.MARGEN))


def test_auc_y_brier_a_mano():
    assert metricas.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert metricas.brier([0, 1], [0.2, 0.7]) == pytest.approx((0.04 + 0.09) / 2)


def test_un_modelo_calibrado_tiene_pendiente_uno_e_intercepto_cero():
    y, p = _grupos((0.2, 10, 2), (0.8, 10, 8))
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(1.0, abs=1e-8)
    assert metricas.intercepto_de_calibracion(y, p) == pytest.approx(0.0, abs=1e-8)


def test_un_modelo_que_exagera_tiene_pendiente_menor_que_uno():
    """Dice 0,1 y 0,9 donde ocurre 0,2 y 0,8: la pendiente es el cociente de logits."""
    y, p = _grupos((0.1, 10, 2), (0.9, 10, 8))
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(
        _logit(0.8) / _logit(0.9), abs=1e-8)


def test_un_modelo_que_se_queda_corto_tiene_pendiente_mayor_que_uno():
    y, p = _grupos((0.3, 10, 1), (0.7, 10, 9))
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(
        _logit(0.9) / _logit(0.7), abs=1e-8)


def test_la_pendiente_sale_aunque_el_modelo_este_muy_lejos_de_calibrado():
    """Un modelo que ordena AL REVÉS (pendiente verdadera −0,5): la pendiente
    existe, y Newton sin retroceso se dispara desde (0, 1) sin encontrarla."""
    from sklearn.linear_model import LogisticRegression
    rng = np.random.default_rng(11)
    p = rng.uniform(0.02, 0.98, 2000)
    y = (rng.random(2000) < 1.0 / (1.0 + np.exp(0.5 * metricas.logit(p)))).astype(int)
    modelo = LogisticRegression(C=np.inf, solver="lbfgs", tol=1e-10, max_iter=5000).fit(
        metricas.logit(p).reshape(-1, 1), y)
    pendiente = metricas.pendiente_de_calibracion(y, p)
    assert pendiente == pytest.approx(float(modelo.coef_[0, 0]), abs=1e-4)
    assert -0.6 < pendiente < -0.4


def test_con_dos_valores_de_p_y_el_orden_invertido_la_pendiente_es_la_exacta():
    """Con dos grupos la regresión reproduce las dos frecuencias, así que la
    pendiente tiene forma cerrada. Desde (0, 1) el primer paso de Newton cae
    donde la hessiana ya no distingue nada: lo resuelve el respaldo."""
    y, p = _grupos((0.0283, 1088, 1065), (0.336, 1589, 695))
    exacta = ((_logit(695 / 1589) - _logit(1065 / 1088))
              / (_logit(0.336) - _logit(0.0283)))
    assert exacta == pytest.approx(-1.431, abs=1e-3)
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(exacta, abs=1e-8)


def test_sin_pendiente_finita_se_dice_antes_de_iterar():
    # clases separadas del todo, en los dos sentidos, y casi del todo (un empate)
    for y, p in (([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]),
                 ([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]),
                 ([0, 0, 1, 1], [0.1, 0.5, 0.5, 0.9])):
        with pytest.raises(ArithmeticError, match="separan del todo"):
            metricas.pendiente_de_calibracion(y, p)
    # todas las p iguales: la pendiente no está identificada, valgan lo que valgan
    for constante in (0.3, 0.5, 0.7, 0.9):
        with pytest.raises(ArithmeticError, match="todas las p iguales"):
            metricas.pendiente_de_calibracion(np.tile([0, 1], 2000), np.full(4000, constante))
    # y con una sola clase no hay ni pendiente, ni intercepto, ni AUC
    for medida in (metricas.pendiente_de_calibracion, metricas.intercepto_de_calibracion,
                   metricas.auc):
        with pytest.raises(ArithmeticError, match="una sola clase"):
            medida([1, 1, 1], [0.2, 0.5, 0.8])


def test_el_intercepto_sale_aunque_una_clase_sea_rarisima():
    y = np.zeros(4000, dtype=int)
    y[0] = 1
    p = np.full(4000, 0.5)
    assert metricas.intercepto_de_calibracion(1 - y, p) == pytest.approx(
        _logit(3999 / 4000), abs=1e-9)
    # y con las p acotadas en el extremo: hace falta un intercepto de más de 20
    assert metricas.intercepto_de_calibracion(1 - y, np.zeros(4000)) == pytest.approx(
        _logit(3999 / 4000) - _logit(metricas.MARGEN), abs=1e-6)


def test_el_intercepto_es_el_desplazamiento_en_log_odds():
    """Dice 0,2 donde ocurre 0,3: hay que sumar logit 0,3 − logit 0,2."""
    y, p = _grupos((0.2, 10, 3))
    assert metricas.intercepto_de_calibracion(y, p) == pytest.approx(
        _logit(0.3) - _logit(0.2), abs=1e-9)


def test_la_pendiente_coincide_con_la_de_sklearn_sin_penalizar():
    from sklearn.linear_model import LogisticRegression
    rng = np.random.default_rng(7)
    p = rng.uniform(0.02, 0.98, 500)
    y = (rng.random(500) < p ** 1.5).astype(int)
    modelo = LogisticRegression(C=np.inf, solver="lbfgs", tol=1e-10, max_iter=5000).fit(
        metricas.logit(p).reshape(-1, 1), y)
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(
        float(modelo.coef_[0, 0]), abs=1e-4)


def test_ece_a_mano_con_dos_bins():
    y, p = np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])
    assert metricas.ece(y, p, orden=[0, 1, 2, 3], bins=2) == pytest.approx(0.15)


def test_los_empates_de_p_se_rompen_con_el_orden_declarado():
    y, p = np.array([1, 0, 1, 0]), np.array([0.5, 0.5, 0.5, 0.5])
    assert metricas.ece(y, p, orden=[0, 1, 2, 3], bins=2) == pytest.approx(0.0)
    assert metricas.ece(y, p, orden=[0, 2, 1, 3], bins=2) == pytest.approx(0.5)


def test_la_fiabilidad_reparte_todos_los_casos_en_bins_de_igual_masa():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.0, 1.0, 105)
    y = (rng.random(105) < p).astype(int)
    curva = metricas.fiabilidad(y, p, orden=np.arange(105))
    assert len(curva) == metricas.BINS
    assert sum(b["n"] for b in curva) == 105
    assert {b["n"] for b in curva} == {10, 11}
    medias = [b["p_media"] for b in curva]
    assert medias == sorted(medias)
    assert metricas.ece(y, p, np.arange(105)) == pytest.approx(
        sum(b["n"] / 105 * abs(b["observada"] - b["p_media"]) for b in curva))


def test_el_suelo_de_la_ece_es_reproducible_con_semilla():
    rng = np.random.default_rng(5)
    p = rng.uniform(0.05, 0.95, 400)
    orden = np.arange(400)
    a = metricas.suelo_de_ece(p, orden, repeticiones=50, semilla=11)
    assert a == metricas.suelo_de_ece(p, orden, repeticiones=50, semilla=11)
    assert a != metricas.suelo_de_ece(p, orden, repeticiones=50, semilla=12)
    assert 0.0 < a["media"] < a["p95"] < 0.1


def test_resumen_de_modelo_lleva_las_cinco_cifras():
    y, p = _grupos((0.2, 10, 2), (0.8, 10, 8))
    r = metricas.resumen_de_modelo(y, p, np.arange(20))
    assert set(r) == {"auc", "brier", "pendiente", "intercepto", "ece"}
    assert all(isinstance(v, float) for v in r.values())
    assert r == {"auc": metricas.auc(y, p), "brier": metricas.brier(y, p),
                 "pendiente": metricas.pendiente_de_calibracion(y, p),
                 "intercepto": metricas.intercepto_de_calibracion(y, p),
                 "ece": metricas.ece(y, p, np.arange(20))}


def test_vectores_de_distinta_forma_se_rechazan():
    with pytest.raises(ValueError, match="misma forma"):
        metricas.brier([0, 1], [0.2])
    with pytest.raises(ValueError, match="misma forma"):
        metricas.auc([], [])


def test_lo_que_no_es_una_etiqueta_o_una_probabilidad_se_rechaza():
    with pytest.raises(ValueError, match="0 o 1"):
        metricas.brier([0, 0.7], [0.2, 0.5])          # antes se truncaba a 0
    with pytest.raises(ValueError, match="0 o 1"):
        metricas.auc([0, 2], [0.2, 0.5])
    for mala in (1.2, -0.1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="probabilidad"):
            metricas.brier([0, 1], [0.2, mala])
    with pytest.raises(ValueError, match="probabilidad"):
        metricas.pendiente_de_calibracion([0, 1], [0.2, float("nan")])
    # los booleanos y los enteros de numpy son etiquetas
    assert metricas.brier(np.array([False, True]), [0.2, 0.7]) == pytest.approx(0.065)
    assert metricas.brier(np.array([0, 1], dtype=np.int8), [0.2, 0.7]) == pytest.approx(0.065)
```

- [ ] **Paso 3: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_metricas.py -q`

Esperado: error de colección,
`ImportError: cannot import name 'metricas' from 'copiloto_triaje.validacion'`.

- [ ] **Paso 4: Escribir las métricas por modelo**

Crea `src/copiloto_triaje/validacion/metricas.py` con este contenido:

```python
# -*- coding: utf-8 -*-
"""Las métricas de la simulación semisintética (spec de SP5 §4.6).

Funciones puras sobre vectores: ni leen ficheros ni dibujan. Todo lo que se
compara con el oráculo se compara en LOG-ODDS, que es la escala en la que el
sistema suma evidencia.

- Por modelo: AUC, Brier, pendiente e intercepto de calibracion, ECE con su
  suelo de ruido y la curva de fiabilidad.
- La horquilla frente al oraculo: posicion λ, las dos colas y la contencion,
  con la tolerancia ε = 0,015 (el redondeo maximo de las RV publicadas, la
  misma de 0A.3).
- Un solo numero o un rango frente al oraculo: error puntual (los
  discordantes) y contencion en un rango (el asma desconocida).
- Percentiles, para los intervalos del bootstrap, y cuantiles ponderados,
  para la escala legible.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import expit
from sklearn.metrics import roc_auc_score

EPSILON = 0.015              # log-odds; la tolerancia de 0A.3
BINS = 10                    # ECE y fiabilidad: deciles de igual masa
REPETICIONES_SUELO = 200     # etiquetas simuladas para el suelo de la ECE
SEMILLA_SUELO = 20261009
MARGEN = 1e-6                # una p redondeada a 4 decimales no llega a 0 ni a 1
CUARTILES = (0.25, 0.5, 0.75)


def logit(p) -> np.ndarray:
    """ln(p / (1 − p)), con p acotada a [MARGEN, 1 − MARGEN]."""
    p = np.clip(np.asarray(p, dtype=float), MARGEN, 1.0 - MARGEN)
    return np.log(p / (1.0 - p))


def _vectores(y, p):
    """`y` como 0/1 y `p` como probabilidades, de la misma forma. Se rechaza
    lo que no lo es en vez de truncarlo: un 0,7 en `y` pasaria a 0 sin aviso."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if y.ndim != 1 or y.shape != p.shape or y.size == 0:
        raise ValueError(f"y y p deben ser vectores no vacíos de la misma forma, "
                         f"y son {y.shape} y {p.shape}")
    if not np.isin(y, (0.0, 1.0)).all():
        raise ValueError("y debe valer 0 o 1 en todos los casos")
    if not (np.isfinite(p).all() and (p >= 0.0).all() and (p <= 1.0).all()):
        raise ValueError("p debe ser una probabilidad (entre 0 y 1) en todos los casos")
    return y.astype(int), p


def _dos_clases(y, que: str) -> None:
    if float(np.ptp(y)) == 0.0:
        raise ArithmeticError(f"con una sola clase no hay {que} que estimar")


def auc(y, p) -> float:
    y, p = _vectores(y, p)
    _dos_clases(y, "AUC")
    return float(roc_auc_score(y, p))


def brier(y, p) -> float:
    y, p = _vectores(y, p)
    return float(np.mean((p - y) ** 2))


def _verosimilitud(y, x, a: float, b: float) -> float:
    eta = a + b * x
    return float(np.sum(y * eta - np.logaddexp(0.0, eta)))


def _gradiente_y_hessiana(y, x, a: float, b: float):
    mu = expit(a + b * x)
    w = mu * (1.0 - mu)
    g = np.array([np.sum(y - mu), np.sum((y - mu) * x)])
    h = np.array([[np.sum(w), np.sum(w * x)],
                  [np.sum(w * x), np.sum(w * x * x)]])
    return g, h


def _newton(y, x, a: float, b: float, pasos: int):
    """Newton con retroceso desde (a, b): (a, b) al converger, o None si se
    queda sin paso que dar. La verosimilitud es concava, asi que un paso que
    la empeora se acorta a la mitad; el margen de la comparacion es el ruido
    de redondeo de la propia verosimilitud (cerca del maximo un paso bueno la
    cambia menos que eso)."""
    for _ in range(pasos):
        g, h = _gradiente_y_hessiana(y, x, a, b)
        try:
            paso = np.linalg.solve(h, g)
        except np.linalg.LinAlgError:
            return None
        if not np.all(np.isfinite(paso)):
            return None
        if float(np.max(np.abs(paso))) < 1e-8:
            return a + paso[0], b + paso[1]
        actual, t = _verosimilitud(y, x, a, b), 1.0
        margen = 1e-10 * (1.0 + abs(actual))
        while _verosimilitud(y, x, a + t * paso[0], b + t * paso[1]) < actual - margen:
            t *= 0.5
            if t < 1e-10:
                return None
        a, b = a + t * paso[0], b + t * paso[1]
    return None


def pendiente_de_calibracion(y, p, pasos: int = 100) -> float:
    """La pendiente de la regresion logistica SIN penalizar de Y sobre
    logit p (con intercepto libre). Menor que 1: el modelo exagera; mayor
    que 1: se queda corto.

    Antes de iterar se dice cuando NO existe: con una sola clase, con todas
    las p iguales, o con las clases separadas por las p (la pendiente seria
    infinita). Si existe, es unica: la busca Newton con retroceso y, si se
    queda sin paso (con muy pocos valores distintos de p y el orden invertido,
    el primer paso puede caer donde la hessiana ya no distingue nada), una
    region de confianza con la hessiana exacta, que Newton pule despues."""
    y, p = _vectores(y, p)
    _dos_clases(y, "pendiente de calibración")
    x = logit(p)
    if float(np.ptp(x)) == 0.0:
        raise ArithmeticError("con todas las p iguales no hay pendiente de calibración "
                              "que estimar")
    unos, ceros = x[y == 1], x[y == 0]
    if unos.min() >= ceros.max() or ceros.min() >= unos.max():
        raise ArithmeticError("las p separan del todo las clases: la pendiente de "
                              "calibración no es finita")
    solucion = _newton(y, x, 0.0, 1.0, pasos)
    if solucion is None:
        n = float(y.size)
        respaldo = minimize(
            lambda t: -_verosimilitud(y, x, t[0], t[1]) / n, np.array([0.0, 1.0]),
            jac=lambda t: -_gradiente_y_hessiana(y, x, t[0], t[1])[0] / n,
            hess=lambda t: _gradiente_y_hessiana(y, x, t[0], t[1])[1] / n,
            method="trust-exact", options={"gtol": 1e-8, "maxiter": 1000})
        solucion = _newton(y, x, float(respaldo.x[0]), float(respaldo.x[1]), pasos)
    if solucion is None:
        raise ArithmeticError("la regresión de calibración no converge, aunque la "
                              "pendiente existe: revisa las p")
    return float(solucion[1])


def intercepto_de_calibracion(y, p) -> float:
    """El intercepto con la pendiente FIJADA en 1 (calibracion global): la
    `a` que iguala la media de expit(a + logit p) a la frecuencia observada.
    Positivo: el modelo predice de menos."""
    y, p = _vectores(y, p)
    _dos_clases(y, "intercepto de calibración")
    x = logit(p)
    objetivo = float(np.mean(y))
    # logit() acota x a ±13,8: con a = ±50 la media predicha pasa de la
    # observada por los dos lados, por desequilibradas que esten las clases.
    return float(brentq(lambda a: float(np.mean(expit(a + x))) - objetivo, -50.0, 50.0,
                        xtol=1e-12))


def _deciles(p, orden, bins: int):
    """Los indices de cada bin de igual masa: se ordena por p y los empates
    se rompen con `orden` (el rango de patientId, declarado en el spec)."""
    return np.array_split(np.lexsort((np.asarray(orden), np.asarray(p, dtype=float))), bins)


def ece(y, p, orden, bins: int = BINS) -> float:
    y, p = _vectores(y, p)
    return float(sum(len(b) / y.size * abs(float(y[b].mean()) - float(p[b].mean()))
                     for b in _deciles(p, orden, bins) if len(b)))


def fiabilidad(y, p, orden, bins: int = BINS) -> list:
    """La curva de fiabilidad: por bin, cuantos casos, la p media y la
    frecuencia observada."""
    y, p = _vectores(y, p)
    return [{"n": int(len(b)), "p_media": float(p[b].mean()), "observada": float(y[b].mean())}
            for b in _deciles(p, orden, bins) if len(b)]


def suelo_de_ece(p, orden, repeticiones: int = REPETICIONES_SUELO,
                 semilla: int = SEMILLA_SUELO, bins: int = BINS) -> dict:
    """La ECE que daria un modelo PERFECTAMENTE calibrado con estas mismas p:
    etiquetas simuladas Bernoulli(p), `repeticiones` veces. Una ECE solo se
    lee al lado de este suelo, nunca contra un umbral absoluto."""
    p = np.asarray(p, dtype=float)
    rng = np.random.default_rng(semilla)
    valores = np.array([ece((rng.random(p.size) < p).astype(int), p, orden, bins)
                        for _ in range(repeticiones)])
    return {"media": float(valores.mean()), "p95": float(np.percentile(valores, 95))}


def resumen_de_modelo(y, p, orden) -> dict:
    """Las cinco cifras de un modelo puntual (sin el suelo, que es caro)."""
    return {"auc": auc(y, p), "brier": brier(y, p),
            "pendiente": pendiente_de_calibracion(y, p),
            "intercepto": intercepto_de_calibracion(y, p),
            "ece": ece(y, p, orden)}


def _log_odds(*vectores) -> list:
    """Los vectores como float, de la misma forma y FINITOS. Un NaN no es
    mayor ni menor que nada: sin esta guarda, un caso sin dato (la dependencia
    vacia de un discordante) contaria en silencio como «dentro». Y dos
    infinitos restados dan otro NaN."""
    v = [np.asarray(x, dtype=float) for x in vectores]
    if any(x.ndim != 1 or x.shape != v[0].shape for x in v):
        raise ValueError("los vectores deben tener la misma forma")
    if not all(np.isfinite(x).all() for x in v):
        raise ValueError("hay valores sin dato (NaN) o infinitos: se mide solo donde "
                         "hay dato; filtra los casos antes de medir")
    return v
```

- [ ] **Paso 5: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_metricas.py -q`

Esperado: `18 passed`.

- [ ] **Paso 6: Escribir las pruebas de la horquilla, los percentiles y los cuantiles**

Añade al final de `tests/test_metricas.py` (dos líneas en blanco antes):

```python
# La horquilla: los casos de borde del spec §8. Dependencia en 0, independencia
# en 1 (evidencia a favor) salvo el ultimo, que apunta hacia abajo.
L_DEP = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
L_IND = [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
L_ORA = [0.5,     # dentro
         1.01,    # mas alla de la independencia, pero dentro de ε: cuenta dentro
         1.02,    # mas alla de la independencia en mas de ε: cola «sobre»
         -0.02,   # mas alla del extremo conservador en mas de ε: cola «bajo»
         0.3,     # Δ = 0: sin horquilla
         -0.02]   # evidencia en contra: mas alla de la independencia (0) en 0,02


def test_la_horquilla_en_los_casos_de_borde():
    h = metricas.horquilla(L_ORA, L_DEP, L_IND)
    assert h["n"] == 5 and h["sin_horquilla"] == 1
    assert h["bajo"] == pytest.approx(1 / 5)
    assert h["sobre"] == pytest.approx(2 / 5)
    assert h["contencion"] == pytest.approx(2 / 5)
    # λ: 0,5; 1,01; 1,02; −0,02; y (−0,02 − 1)/(0 − 1) = 1,02
    assert h["lambda"]["mediana"] == pytest.approx(1.01)
    assert h["lambda"]["q1"] == pytest.approx(0.5)
    assert h["lambda"]["q3"] == pytest.approx(1.02)


def test_la_tolerancia_es_la_de_0a3_y_se_puede_cambiar():
    assert metricas.EPSILON == 0.015
    h = metricas.horquilla(L_ORA, L_DEP, L_IND, epsilon=0.0)
    assert h["sobre"] == pytest.approx(3 / 5) and h["contencion"] == pytest.approx(1 / 5)
    assert h["bajo"] == pytest.approx(1 / 5)
    # y del lado conservador: 0,01 más allá cuenta dentro; 0,02, fuera
    dentro = metricas.horquilla([-0.01, 1.01], [0.0, 1.0], [1.0, 0.0])
    assert (dentro["bajo"], dentro["sobre"], dentro["contencion"]) == (0.0, 0.0, 1.0)
    fuera = metricas.horquilla([-0.02, 1.02], [0.0, 1.0], [1.0, 0.0])
    assert (fuera["bajo"], fuera["sobre"], fuera["contencion"]) == (1.0, 0.0, 0.0)


def test_sin_ningun_caso_con_horquilla_no_hay_fracciones():
    h = metricas.horquilla([0.3], [0.0], [0.0])
    assert h == {"n": 0, "sin_horquilla": 1,
                 "lambda": {"q1": None, "mediana": None, "q3": None},
                 "bajo": None, "sobre": None, "contencion": None}
    assert metricas.horquilla([], [], [])["n"] == 0


def test_un_valor_sin_dato_no_cuenta_como_contenido():
    """Un NaN no es mayor ni menor que nada: sin la guarda, un caso sin
    horquilla (un discordante, con la dependencia vacía) contaría «dentro»
    aunque el oráculo quedara a 4 log-odds."""
    with pytest.raises(ValueError, match="sin dato"):
        metricas.horquilla([0.5, 5.0], [0.0, None], [1.0, 1.0])
    with pytest.raises(ValueError, match="sin dato"):
        metricas.horquilla([float("nan")], [0.0], [1.0])
    with pytest.raises(ValueError, match="sin dato"):
        metricas.contencion_en_rango([0.5], [float("nan")], [1.0])
    with pytest.raises(ValueError, match="sin dato"):
        metricas.error_puntual([0.5], [float("nan")])
    # dos infinitos restados dan otro NaN
    with pytest.raises(ValueError, match="infinitos"):
        metricas.horquilla([0.0], [float("inf")], [float("inf")])
    with pytest.raises(ValueError, match="infinitos"):
        metricas.error_puntual([float("inf")], [float("inf")])


def test_los_vectores_de_log_odds_tienen_que_casar():
    with pytest.raises(ValueError, match="misma forma"):
        metricas.horquilla([0.5], [0.0, 0.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="misma forma"):
        metricas.error_puntual([1.0], [0.5, 2.5, 0.0])
    with pytest.raises(ValueError, match="misma forma"):
        metricas.contencion_en_rango([0.5, 0.5], [0.0], [1.0])
    with pytest.raises(ValueError, match="mínima"):
        metricas.contencion_en_rango([0.5], [1.0], [0.0])


def test_error_puntual_y_contencion_en_rango():
    e = metricas.error_puntual([1.0, 2.0, 0.0], [0.5, 2.5, 0.0])
    assert e == {"n": 3, "error_abs_mediano": 0.5, "sesgo_mediano": 0.0}
    assert metricas.error_puntual([], [])["error_abs_mediano"] is None
    c = metricas.contencion_en_rango([0.0, 1.01, 1.02, -0.02], [0.0] * 4, [1.0] * 4)
    assert c["n"] == 4
    assert (c["bajo"], c["sobre"], c["contencion"]) == pytest.approx((0.25, 0.25, 0.5))
    assert metricas.contencion_en_rango([], [], [])["contencion"] is None


def test_percentiles_ignora_lo_que_no_es_un_numero():
    lo, hi = metricas.percentiles(list(range(1, 101)) + [float("nan")])
    assert (lo, hi) == pytest.approx((3.475, 97.525))
    assert metricas.percentiles([float("nan")]) == [None, None]


def test_cuantiles_ponderados():
    q = metricas.cuantiles_ponderados([3.0, 1.0, 2.0], [2.0, 1.0, 1.0])
    assert list(q) == [1.0, 2.0, 3.0]
    # con un peso nulo el valor no cuenta
    assert list(metricas.cuantiles_ponderados([5.0, 1.0], [0.0, 1.0], (0.5,))) == [1.0]
    with pytest.raises(ValueError, match="masa positiva"):
        metricas.cuantiles_ponderados([1.0], [0.0])
```

- [ ] **Paso 7: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_metricas.py -q`

Esperado: `8 failed, 18 passed`; los fallos son
`AttributeError: module 'copiloto_triaje.validacion.metricas' has no attribute 'horquilla'`
(y `error_puntual`, `percentiles`, `cuantiles_ponderados`).

- [ ] **Paso 8: Escribir la horquilla, los percentiles y los cuantiles**

Añade al final de `src/copiloto_triaje/validacion/metricas.py` (dos líneas
en blanco antes):

```python
def _cuartiles(x) -> dict:
    if x.size == 0:
        return {"q1": None, "mediana": None, "q3": None}
    q1, mediana, q3 = np.percentile(x, [25, 50, 75])
    return {"q1": float(q1), "mediana": float(mediana), "q3": float(q3)}


def horquilla(l_oraculo, l_dependencia, l_independencia, epsilon: float = EPSILON) -> dict:
    """Donde cae el oraculo respecto a [dependencia, independencia], en
    log-odds. λ = 0 es el extremo conservador y λ = 1 la independencia,
    apunte la evidencia hacia donde apunte. Las colas cuentan los casos en
    que el oraculo queda MAS ALLA de un extremo en mas de ε log-odds."""
    o, d, i = _log_odds(l_oraculo, l_dependencia, l_independencia)
    delta = i - d
    con = delta != 0.0
    n = int(con.sum())
    if n == 0:
        return {"n": 0, "sin_horquilla": int((~con).sum()), "lambda": _cuartiles(o[con]),
                "bajo": None, "sobre": None, "contencion": None}
    sentido = np.sign(delta[con])
    bajo = (o[con] - d[con]) * sentido < -epsilon
    sobre = (o[con] - i[con]) * sentido > epsilon
    return {"n": n, "sin_horquilla": int((~con).sum()),
            "lambda": _cuartiles((o[con] - d[con]) / delta[con]),
            "bajo": float(bajo.mean()), "sobre": float(sobre.mean()),
            "contencion": float(1.0 - bajo.mean() - sobre.mean())}


def error_puntual(l_sistema, l_oraculo) -> dict:
    """Un solo numero del sistema frente al oraculo: |Δ logit| mediano y el
    sesgo (mediana de sistema − oraculo; positivo: el sistema da de mas)."""
    sistema, oraculo = _log_odds(l_sistema, l_oraculo)
    e = sistema - oraculo
    if e.size == 0:
        return {"n": 0, "error_abs_mediano": None, "sesgo_mediano": None}
    return {"n": int(e.size), "error_abs_mediano": float(np.median(np.abs(e))),
            "sesgo_mediano": float(np.median(e))}


def contencion_en_rango(l_oraculo, l_minima, l_maxima, epsilon: float = EPSILON) -> dict:
    """Fraccion de casos con el oraculo dentro de [minima − ε, maxima + ε]."""
    o, lo, hi = _log_odds(l_oraculo, l_minima, l_maxima)
    if np.any(lo > hi):
        raise ValueError("la mínima no puede superar a la máxima")
    if o.size == 0:
        return {"n": 0, "bajo": None, "sobre": None, "contencion": None}
    bajo, sobre = o < lo - epsilon, o > hi + epsilon
    return {"n": int(o.size), "bajo": float(bajo.mean()), "sobre": float(sobre.mean()),
            "contencion": float(1.0 - bajo.mean() - sobre.mean())}


def percentiles(valores, alfa: float = 0.05) -> list:
    """El intervalo por percentiles de las replicas, ignorando las que no
    se pudieron calcular (nan)."""
    v = np.asarray(valores, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return [None, None]
    lo, hi = np.percentile(v, [100 * alfa / 2, 100 * (1 - alfa / 2)])
    return [float(lo), float(hi)]


def cuantiles_ponderados(valores, pesos, cuantiles=CUARTILES) -> np.ndarray:
    """Cuantiles de `valores` con pesos: el menor valor cuya masa acumulada
    alcanza el cuantil."""
    v = np.asarray(valores, dtype=float)
    w = np.asarray(pesos, dtype=float)
    if v.shape != w.shape or v.ndim != 1 or v.size == 0 or float(w.sum()) <= 0:
        raise ValueError("valores y pesos deben ser vectores no vacíos con masa positiva")
    orden = np.argsort(v, kind="stable")
    acumulada = np.cumsum(w[orden]) / float(w.sum())
    return np.array([v[orden][min(int(np.searchsorted(acumulada, c, side="left")), v.size - 1)]
                     for c in cuantiles])
```

- [ ] **Paso 9: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_metricas.py -q`

Esperado: `26 passed`.

- [ ] **Paso 10: Una sola definición de la tolerancia**

En `tests/test_validacion_0a.py` sustituye

```python
from copiloto_triaje.validacion import datos, generador, oraculo
```

por

```python
from copiloto_triaje.validacion import datos, generador, metricas, oraculo
```

y

```python
TOLERANCIA = 0.015   # el redondeo máximo de las RV publicadas (0,013 en k = 1)
```

por

```python
TOLERANCIA = metricas.EPSILON   # 0,015: el redondeo máximo de las RV publicadas (0,013 en k = 1)
```

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validacion_0a.py tests/test_metricas.py -q`

Esperado: `36 passed` (las 26 de las métricas y las 10 de 0A).

- [ ] **Paso 11: Commit**

```bash
git add src/copiloto_triaje/validacion/metricas.py tests/test_metricas.py tests/test_validacion_0a.py
git commit -m "feat(validacion): las métricas de la simulación: calibración, ECE con su suelo y horquilla" -m "Funciones puras sobre vectores (spec de SP5 §4.6): AUC, Brier, pendiente e intercepto de calibración, ECE por deciles con los empates rotos por el orden declarado y su suelo de ruido, curva de fiabilidad, posición, colas y contención de la horquilla con la tolerancia de 0A.3, percentiles y cuantiles ponderados. La tolerancia queda definida una sola vez, en metricas.EPSILON." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 2: El sistema y el oráculo, caso a caso, y las métricas de una celda

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/simulacion.py`
- Crear: `tests/test_simulacion.py`

**Interfaces:**
- Consume:
  - `heckerling.combinacion(prevalencia, hallazgos, rv_imagen) -> dict`,
    `heckerling.combinar(prevalencia, rv_clinica, rv_imagen) -> float`,
    `heckerling.mas_informativa(rv_a, rv_b) -> float`, `heckerling.RV_POR_PUNTUACION`.
  - `datos.cargar_crudas(ruta) -> DataFrame`, `datos.calibrador_desplegado()`,
    `datos.evidencia_imagen(crudas, calibrador) -> (p_cal, q, rv)`, `datos.CRUDAS_CONGELADAS`.
  - `generador.generar(modelo, semilla) -> DataFrame` (columnas `k`, `k4`,
    `asma_real`, `asma` y los cuatro signos), `generador.hallazgos(fila) -> dict`.
  - `oraculo.ajustar(q, etiquetas, rho1, rho0) -> Modelo`,
    `oraculo.logit_oraculo(modelo, q, k)`, `oraculo.logit_oraculo_no_se(modelo, q, k4)`.
  - `categoria.categoria_del_sistema(bloque) -> dict` (clave `primaria`).
  - `metricas.resumen_de_modelo`, `metricas.horquilla`, `metricas.error_puntual`,
    `metricas.contencion_en_rango` (tarea 1).
- Produce:
  - Constantes `SEMILLA_PUNTUAL = 1`, `MODELOS = ("imagen", "clinica", "independencia", "conservador")`,
    `COMBINADOS = ("independencia", "conservador")`.
  - `Conjunto` (dataclass congelada): `ids`, `y`, `p_cal`, `q`, `rv`, `orden`, `prevalencia`.
  - `cargar_conjunto(ruta=datos.CRUDAS_CONGELADAS, calibrador=None) -> Conjunto`
  - `nombre_de_celda(rho1, rho0) -> str` (`"0A"`, `"(0,3; 0)"`)
  - `salidas_del_sistema(prevalencia, clinica, rv) -> dict` de arrays de longitud n:
    `conocida`, `concordantes` (bool), `puntuacion` (int), `primaria` (texto),
    `independencia`, `conservador`, `clinica` (probabilidades),
    `l_independencia`, `l_dependencia` (`nan` sin concordancia), `l_minima`,
    `l_maxima`, `l_medio` (log-odds sin redondear).
  - `oraculo_de_los_casos(modelo, q, clinica) -> np.ndarray` (log-odds)
  - `medir(conjunto, salidas, l_oraculo, filas=None) -> dict` con `recuentos`,
    `modelos`, `pareadas`, `horquilla` (`todos`, `a_favor`, `en_contra`),
    `discordantes`, `no_se`.
  - `aplanar(d, prefijo="") -> dict` (`"a.b.c" -> float`)

**Por qué el oráculo recibe `k` o `k4`:** el oráculo tiene que condicionar en
lo mismo que ve el sistema. Con el asma conocida el sistema ve la puntuación
`k`; con `asma = no_se` solo ve los cuatro signos (`k4`) y entrega dos
puntuaciones, y el oráculo marginaliza el asma (`logit_oraculo_no_se`).

- [ ] **Paso 1: Escribir las pruebas del conjunto, del sistema y del oráculo**

Crea `tests/test_simulacion.py` con este contenido:

```python
"""La simulación celda a celda sobre las 3 811 placas congeladas (spec de
SP5 §4.3-§4.6, §8, §11.2-§11.3). La fila 0A es la comprobación de la
métrica: con dependencia nula el oráculo no puede salirse de la horquilla."""
import numpy as np
import pytest

from copiloto_triaje.servicio.heckerling import combinacion
from copiloto_triaje.validacion import generador, metricas, oraculo, simulacion


@pytest.fixture(scope="module")
def conjunto():
    return simulacion.cargar_conjunto()


def _escenario(conjunto, rho1, rho0):
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, rho1, rho0)
    clinica = generador.generar(modelo, simulacion.SEMILLA_PUNTUAL)
    salidas = simulacion.salidas_del_sistema(conjunto.prevalencia, clinica, conjunto.rv)
    l_or = simulacion.oraculo_de_los_casos(modelo, conjunto.q, clinica)
    return modelo, clinica, salidas, l_or


@pytest.fixture(scope="module")
def escenario_0a(conjunto):
    return _escenario(conjunto, 0.0, 0.0)


def test_el_conjunto_es_el_de_prueba_con_su_previo(conjunto):
    assert conjunto.y.size == 3811 and int(conjunto.y.sum()) == 844
    assert conjunto.prevalencia == pytest.approx(0.2215)
    assert sorted(conjunto.orden) == list(range(3811))
    # el orden es el de patientId: el primero en orden alfabetico lleva el 0
    assert conjunto.ids[int(np.argmin(conjunto.orden))] == min(conjunto.ids)
    assert np.allclose(conjunto.q, metricas.logit(conjunto.p_cal))


def test_los_nombres_de_las_celdas():
    assert simulacion.nombre_de_celda(0.0, 0.0) == "0A"
    assert simulacion.nombre_de_celda(0.3, 0.0) == "(0,3; 0)"
    assert simulacion.nombre_de_celda(0.15, 0.45) == "(0,15; 0,45)"


def test_las_salidas_son_las_del_codigo_del_servidor(conjunto, escenario_0a):
    _, clinica, salidas, _ = escenario_0a
    filas = clinica.to_dict("records")
    for i in (0, 1, 2, 500, 3810):
        b = combinacion(conjunto.prevalencia, generador.hallazgos(filas[i]), float(conjunto.rv[i]))
        assert salidas["independencia"][i] == b["independencia"][0]
        assert salidas["concordantes"][i] == b["concordantes"]
        assert salidas["conservador"][i] == (b["dependencia"][0] if b["concordantes"]
                                             else b["independencia"][0])
        assert salidas["puntuacion"][i] == b["puntuacion"][0]
    conocida = salidas["conocida"]
    assert np.array_equal(conocida, (clinica["asma"] != "no_se").values)
    assert np.array_equal(salidas["puntuacion"][conocida], clinica["k"].values[conocida])
    assert np.array_equal(salidas["puntuacion"][~conocida], clinica["k4"].values[~conocida])
    # la horquilla solo existe con concordancia
    assert np.array_equal(np.isfinite(salidas["l_dependencia"]), salidas["concordantes"])
    assert np.all(salidas["l_minima"] <= salidas["l_maxima"])
    assert set(salidas["primaria"]) <= {"baja", "intermedia", "alta"}


def test_un_bloque_que_no_es_el_redondeo_de_combinar_se_denuncia(conjunto, escenario_0a,
                                                                 monkeypatch):
    """Los extremos sin redondear se recalculan con `combinar`; si el bloque
    dejara de ser su redondeo, la simulación se detiene en vez de medir otra cosa."""
    _, clinica, _, _ = escenario_0a

    def alterada(prevalencia, hallazgos, rv_imagen):
        b = combinacion(prevalencia, hallazgos, rv_imagen)
        b["independencia"] = [round(x + 0.0001, 4) for x in b["independencia"]]
        return b

    monkeypatch.setattr(simulacion, "combinacion", alterada)
    with pytest.raises(AssertionError, match="no es el redondeo"):
        simulacion.salidas_del_sistema(conjunto.prevalencia, clinica.head(5), conjunto.rv[:5])


def test_el_oraculo_usa_la_misma_informacion_que_el_sistema(conjunto, escenario_0a):
    modelo, clinica, salidas, l_or = escenario_0a
    s = salidas["conocida"]
    assert np.allclose(l_or[s], oraculo.logit_oraculo(
        modelo, conjunto.q[s], clinica["k"].values[s]))
    assert np.allclose(l_or[~s], oraculo.logit_oraculo_no_se(
        modelo, conjunto.q[~s], clinica["k4"].values[~s]))
```

- [ ] **Paso 2: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: error de colección,
`ImportError: cannot import name 'simulacion' from 'copiloto_triaje.validacion'`.

- [ ] **Paso 3: Escribir el conjunto, las salidas del sistema y el oráculo de los casos**

Crea `src/copiloto_triaje/validacion/simulacion.py` con este contenido:

```python
# -*- coding: utf-8 -*-
"""La simulación semisintética, celda a celda (spec de SP5 §4.3-§4.6).

Une las cuatro piezas: las placas congeladas (`datos`), el generador de la
clínica (`generador`), el oráculo de la celda (`oraculo`) y el SISTEMA, que
es `heckerling.combinacion` y `heckerling.combinar`: el mismo código que
sirve el contenedor, llamado caso a caso, nunca una reimplementación.

Una CELDA es un par (ρ1, ρ0). Su estimación puntual usa la clínica sorteada
con `SEMILLA_PUNTUAL` sobre las 3 811 placas. Su bootstrap remuestrea placas
con reemplazo y vuelve a sortear la clínica en cada réplica, con `z_y`, los
umbrales y el calibrador FIJOS: el generador es el mismo en todas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from copiloto_triaje.servicio.heckerling import (
    RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from . import datos, generador, metricas, oraculo
from .categoria import categoria_del_sistema

SEMILLA_PUNTUAL = 1          # la misma clinica que comprueba 0A
MODELOS = ("imagen", "clinica", "independencia", "conservador")
COMBINADOS = ("independencia", "conservador")


@dataclass(frozen=True, eq=False)
class Conjunto:
    """Las placas de prueba y su evidencia de imagen, en el orden del CSV."""
    ids: np.ndarray
    y: np.ndarray
    p_cal: np.ndarray
    q: np.ndarray
    rv: np.ndarray
    orden: np.ndarray        # el rango de patientId: rompe los empates de la ECE
    prevalencia: float


def cargar_conjunto(ruta=datos.CRUDAS_CONGELADAS, calibrador=None) -> Conjunto:
    df = datos.cargar_crudas(ruta)
    cal = calibrador if calibrador is not None else datos.calibrador_desplegado()
    p, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    ids = df["patientId"].values.astype(str)
    return Conjunto(ids, df["etiqueta"].values.astype(int), p, q, rv,
                    np.argsort(np.argsort(ids, kind="stable"), kind="stable"),
                    float(cal.prevalencia))


def nombre_de_celda(rho1: float, rho0: float) -> str:
    if rho1 == 0.0 and rho0 == 0.0:
        return "0A"
    return f"({rho1:g}; {rho0:g})".replace(".", ",")


def salidas_del_sistema(prevalencia: float, clinica: pd.DataFrame, rv) -> dict:
    """Lo que el codigo del servidor da para cada caso. Las probabilidades de
    los modelos puntuales son las del BLOQUE (redondeadas a 4 decimales, lo
    que el sistema entrega); los extremos de la horquilla van SIN redondear,
    recalculados con `combinar` y contrastados con el bloque."""
    n = len(clinica)
    s = {"conocida": np.zeros(n, bool), "concordantes": np.zeros(n, bool),
         "puntuacion": np.zeros(n, int), "primaria": np.empty(n, dtype=object)}
    for nombre in ("independencia", "conservador", "clinica", "l_independencia",
                   "l_dependencia", "l_minima", "l_maxima", "l_medio"):
        s[nombre] = np.full(n, np.nan)
    for i, (fila, r) in enumerate(zip(clinica.to_dict("records"), rv)):
        r = float(r)
        b = combinacion(prevalencia, generador.hallazgos(fila), r)
        ind = [combinar(prevalencia, rc, r) for rc in b["rv_clinica"]]
        dep = ([combinar(prevalencia, mas_informativa(rc, r), 1.0) for rc in b["rv_clinica"]]
               if b["concordantes"] else [])
        if ([round(x, 4) for x in ind] != b["independencia"]
                or ([round(x, 4) for x in dep] or None) != b["dependencia"]):
            raise AssertionError(f"el bloque del caso {i} no es el redondeo de combinar(): {b}")
        s["conocida"][i] = fila["asma"] != "no_se"
        s["concordantes"][i] = b["concordantes"]
        s["puntuacion"][i] = b["puntuacion"][0]
        s["primaria"][i] = categoria_del_sistema(b)["primaria"]
        s["independencia"][i] = b["independencia"][0]
        s["conservador"][i] = b["dependencia"][0] if b["concordantes"] else b["independencia"][0]
        s["clinica"][i] = combinar(prevalencia, RV_POR_PUNTUACION[b["puntuacion"][0]], 1.0)
        l_ind = [math.log(x / (1.0 - x)) for x in ind]
        todas = [math.log(x / (1.0 - x)) for x in ind + dep]
        s["l_independencia"][i] = l_ind[0]
        if dep:
            s["l_dependencia"][i] = math.log(dep[0] / (1.0 - dep[0]))
        s["l_minima"][i], s["l_maxima"][i] = min(todas), max(todas)
        s["l_medio"][i] = sum(l_ind) / len(l_ind)
    return s


def oraculo_de_los_casos(modelo: oraculo.Modelo, q, clinica: pd.DataFrame) -> np.ndarray:
    """El logit del oraculo con la MISMA informacion que el sistema: (q, k)
    con el asma conocida y (q, k4) con el asma oculta."""
    q = np.asarray(q, dtype=float)
    conocida = (clinica["asma"] != "no_se").values
    salida = np.empty(q.size)
    salida[conocida] = oraculo.logit_oraculo(modelo, q[conocida],
                                             clinica["k"].values[conocida])
    salida[~conocida] = oraculo.logit_oraculo_no_se(modelo, q[~conocida],
                                                    clinica["k4"].values[~conocida])
    return salida
```

- [ ] **Paso 4: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `5 passed`.

- [ ] **Paso 5: Escribir las pruebas de las métricas de una celda**

Añade al final de `tests/test_simulacion.py` (dos líneas en blanco antes):

```python
# --------------------------------------------------------------------------
# Las metricas de una celda
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def medida_0a(conjunto, escenario_0a):
    _, _, salidas, l_or = escenario_0a
    return simulacion.medir(conjunto, salidas, l_or)


@pytest.fixture(scope="module")
def medida_simetrica(conjunto):
    _, _, salidas, l_or = _escenario(conjunto, 0.3, 0.3)
    return simulacion.medir(conjunto, salidas, l_or)


def test_la_fila_0a_es_la_comprobacion_de_la_metrica(medida_0a):
    """Colas exactamente 0 y contención 100 %, por cada lado de la imagen y
    también con el asma oculta (spec §4.6, §11.2)."""
    for lado in ("todos", "a_favor", "en_contra"):
        h = medida_0a["horquilla"][lado]
        assert h["bajo"] == 0.0 and h["sobre"] == 0.0 and h["contencion"] == 1.0
        assert h["sin_horquilla"] == 0
    assert medida_0a["no_se"]["contencion"] == 1.0
    # sin dependencia la independencia ES el oraculo salvo el redondeo de las RV
    assert medida_0a["horquilla"]["todos"]["lambda"]["mediana"] == pytest.approx(0.9915, abs=1e-3)
    assert medida_0a["discordantes"]["error_abs_mediano"] < metricas.EPSILON


def test_sin_la_tolerancia_la_fila_0a_acusaria_a_la_independencia(conjunto, escenario_0a):
    """Por qué hace falta ε: la RV publicada 1,64 es menos extrema que la
    exacta 1,6408, y sin tolerancia el oráculo queda «más allá de la
    independencia» en los concordantes con k = 3 (spec §4.6)."""
    _, _, salidas, l_or = escenario_0a
    h = salidas["conocida"] & salidas["concordantes"]
    sin = metricas.horquilla(l_or[h], salidas["l_dependencia"][h],
                             salidas["l_independencia"][h], epsilon=0.0)
    assert 0.05 < sin["sobre"] < 0.25


def test_los_recuentos_cuadran(medida_0a):
    r = medida_0a["recuentos"]
    assert r == {"casos": 3811, "asma_conocida": 3460, "concordantes": 2217,
                 "concordantes_a_favor": 523, "concordantes_en_contra": 1694,
                 "discordantes": 1243, "no_se": 351}
    assert r["asma_conocida"] + r["no_se"] == r["casos"]
    assert r["concordantes"] + r["discordantes"] == r["asma_conocida"]
    assert r["concordantes_a_favor"] + r["concordantes_en_contra"] == r["concordantes"]


def test_los_cuatro_modelos_de_0a(medida_0a):
    m = medida_0a["modelos"]
    assert set(m) == set(simulacion.MODELOS)
    assert m["imagen"]["auc"] == pytest.approx(0.8847, abs=5e-4)
    assert m["clinica"]["auc"] == pytest.approx(0.7897, abs=5e-4)
    assert m["independencia"]["auc"] == pytest.approx(0.9304, abs=5e-4)
    assert m["independencia"]["pendiente"] == pytest.approx(1.025, abs=5e-3)
    # el extremo conservador se queda corto: tira informacion que si era nueva
    assert m["conservador"]["pendiente"] > 1.2
    p = medida_0a["pareadas"]
    assert set(p) == set(simulacion.COMBINADOS)
    assert p["independencia"]["auc"] == pytest.approx(
        m["independencia"]["auc"] - m["imagen"]["auc"])
    assert p["conservador"]["brier"] == pytest.approx(
        m["conservador"]["brier"] - m["imagen"]["brier"])
    assert p["independencia"]["auc"] > 0.04 and p["independencia"]["brier"] < -0.02


def test_con_dependencia_simetrica_la_independencia_exagera(medida_simetrica):
    assert medida_simetrica["modelos"]["independencia"]["pendiente"] == pytest.approx(
        0.788, abs=5e-3)
    h = medida_simetrica["horquilla"]["todos"]
    assert h["n"] == 2430
    assert h["contencion"] == pytest.approx(0.7066, abs=5e-4)
    assert h["bajo"] == pytest.approx(0.2934, abs=5e-4) and h["sobre"] == 0.0


def test_la_direccion_depende_de_donde_vive_la_dependencia(conjunto):
    """Solo entre enfermos: con la imagen a favor el oráculo queda MÁS ALLÁ de
    la independencia. Solo entre sanos: con la imagen a favor queda por el
    lado conservador. La dirección es un resultado de la celda (spec §4.5)."""
    def horquilla(rho1, rho0):
        _, _, salidas, l_or = _escenario(conjunto, rho1, rho0)
        return simulacion.medir(conjunto, salidas, l_or)["horquilla"]

    enfermos, sanos = horquilla(0.6, 0.0), horquilla(0.0, 0.6)
    assert enfermos["a_favor"]["sobre"] > 0.7 and enfermos["a_favor"]["bajo"] < 0.05
    assert enfermos["en_contra"]["bajo"] > 0.7
    assert sanos["a_favor"]["bajo"] > 0.8 and sanos["a_favor"]["sobre"] == 0.0
    assert sanos["en_contra"]["sobre"] > 0.7


def test_medir_sobre_filas_repetidas_es_medir_ese_remuestreo(conjunto, escenario_0a):
    _, _, salidas, l_or = escenario_0a
    filas = np.random.default_rng(3).integers(0, 3811, 3811)
    m = simulacion.medir(conjunto, salidas, l_or, filas)
    assert m["recuentos"]["casos"] == 3811
    s = salidas["conocida"][filas]
    assert m["recuentos"]["asma_conocida"] == int(s.sum())
    assert m["modelos"]["imagen"]["brier"] == pytest.approx(
        metricas.brier(conjunto.y[filas][s], conjunto.p_cal[filas][s]))
    # con dependencia nula, ningun remuestreo saca al oraculo de la horquilla
    assert m["horquilla"]["todos"]["contencion"] == 1.0


def test_aplanar_se_queda_con_las_cifras():
    plano = simulacion.aplanar({"a": {"b": 1.5, "n": 3, "c": None, "d": {"e": 0.25}},
                                "f": 2.0, "g": "texto", "h": True})
    assert plano == {"a.b": 1.5, "a.d.e": 0.25, "f": 2.0}
```

- [ ] **Paso 6: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `5 passed` y el resto en rojo (fallos y errores de fixture) con
`AttributeError: module 'copiloto_triaje.validacion.simulacion' has no attribute 'medir'`
(y `'aplanar'`). La única de las nuevas que ya pasa es
`test_sin_la_tolerancia_la_fila_0a_acusaria_a_la_independencia`, que solo usa
`metricas.horquilla`.

- [ ] **Paso 7: Escribir `medir` y `aplanar`**

Añade al final de `src/copiloto_triaje/validacion/simulacion.py` (dos líneas
en blanco antes):

```python
def medir(conjunto: Conjunto, salidas: dict, l_oraculo, filas=None) -> dict:
    """Todas las metricas del §4.6 sobre las filas dadas (con repeticiones en
    el bootstrap; todas si `filas` es None)."""
    f = np.arange(conjunto.y.size) if filas is None else np.asarray(filas, dtype=int)
    y, orden, rv = conjunto.y[f], conjunto.orden[f], conjunto.rv[f]
    l_or = np.asarray(l_oraculo, dtype=float)[f]
    conocida, conc = salidas["conocida"][f], salidas["concordantes"][f]
    p = {"imagen": conjunto.p_cal[f], "clinica": salidas["clinica"][f],
         "independencia": salidas["independencia"][f],
         "conservador": salidas["conservador"][f]}
    modelos = {m: metricas.resumen_de_modelo(y[conocida], p[m][conocida], orden[conocida])
               for m in MODELOS}
    pareadas = {c: {m: modelos[c][m] - modelos["imagen"][m]
                    for m in ("auc", "brier", "pendiente")} for c in COMBINADOS}
    l_ind, l_dep = salidas["l_independencia"][f], salidas["l_dependencia"][f]
    h = conocida & conc
    lados = {"todos": h, "a_favor": h & (rv >= 1.0), "en_contra": h & (rv < 1.0)}
    d = conocida & ~conc
    ns = ~conocida
    no_se = metricas.contencion_en_rango(l_or[ns], salidas["l_minima"][f][ns],
                                         salidas["l_maxima"][f][ns])
    no_se["punto_medio"] = metricas.error_puntual(salidas["l_medio"][f][ns], l_or[ns])
    return {
        "recuentos": {"casos": int(f.size), "asma_conocida": int(conocida.sum()),
                      "concordantes": int(h.sum()),
                      "concordantes_a_favor": int(lados["a_favor"].sum()),
                      "concordantes_en_contra": int(lados["en_contra"].sum()),
                      "discordantes": int(d.sum()), "no_se": int(ns.sum())},
        "modelos": modelos,
        "pareadas": pareadas,
        "horquilla": {lado: metricas.horquilla(l_or[m], l_dep[m], l_ind[m])
                      for lado, m in lados.items()},
        "discordantes": metricas.error_puntual(l_ind[d], l_or[d]),
        "no_se": no_se,
    }


def aplanar(d: dict, prefijo: str = "") -> dict:
    """{«a.b.c»: valor} con las hojas `float` de un diccionario anidado: son
    las cifras que llevan intervalo. Los recuentos (`int`) y los `None` no."""
    plano = {}
    for clave, valor in d.items():
        ruta = f"{prefijo}.{clave}" if prefijo else str(clave)
        if isinstance(valor, dict):
            plano.update(aplanar(valor, ruta))
        elif isinstance(valor, float):
            plano[ruta] = valor
    return plano
```

- [ ] **Paso 8: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py tests/test_metricas.py -q`

Esperado: `39 passed`.

Si `test_los_recuentos_cuadran` o alguna cifra fijada no coincide, **no
cambies la prueba**: las cifras salen de la semilla 1 sobre las crudas
congeladas y están medidas. Revisa que el código es el de este plan, carácter
a carácter.

- [ ] **Paso 9: Commit**

```bash
git add src/copiloto_triaje/validacion/simulacion.py tests/test_simulacion.py
git commit -m "feat(validacion): el sistema y el oráculo caso a caso, y las métricas de una celda" -m "simulacion.py llama a heckerling.combinacion para cada placa y recalcula con combinar los extremos sin redondear, contrastándolos con el bloque; el oráculo condiciona en lo mismo que ve el sistema (k, o k4 con el asma oculta). medir() da los cuatro modelos puntuales, las diferencias pareadas, la horquilla por lado de la imagen, los discordantes y los no_se. La fila 0A sale con colas 0 y contención 100 %." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 3: Bootstrap, escala legible, sensibilidad al previo, 0C y la celda completa

**Ficheros:**
- Modificar: `src/copiloto_triaje/validacion/simulacion.py`
- Modificar: `tests/test_simulacion.py`

**Interfaces:**
- Consume: todo lo de la tarea 2; `heckerling.PREVALENCIA_COHORTE`;
  `categoria.BANDAS`, `categoria.banda(pct) -> str`,
  `categoria.porcentaje_entero(p) -> int`; `oraculo.log_rv_condicional(modelo)`,
  `oraculo.rv_recuentos(k)`, `oraculo.correlacion_teorica(modelo, y)`,
  `Modelo.probabilidades()`; `metricas.percentiles`,
  `metricas.cuantiles_ponderados`, `metricas.suelo_de_ece`,
  `metricas.fiabilidad`, `metricas.brier`, `metricas.ece`,
  `metricas.intercepto_de_calibracion`.
- Produce:
  - Constantes `SEMILLA_CLINICA = 10_000`, `SEMILLA_INDICES = 20_000`,
    `B_REPLICAS = 1000`, `HIPOTESIS_CONTENCION = 0.90`,
    `RV_VALIDACION = {0: 0.19, 1: 0.19, 2: 1.04, 3: 1.04, 4: 8.33, 5: 8.33}`,
    `POCO_INFORMATIVA = 0.5`, `EXTREMAS = (0, 1, 4, 5)`.
  - `replica(conjunto, modelo, b) -> dict` (plano)
  - `bootstrap(conjunto, modelo, replicas=B_REPLICAS) -> dict` (`ruta -> [li, ls]`)
  - `escala_legible(modelo, conjunto) -> dict` (`a_favor`, `en_contra`)
  - `cambios_de_banda(antes, despues) -> dict` (`casos`, `cambian`, `transiciones`)
  - `sensibilidad_al_previo(conjunto, clinica, salidas, previo=PREVALENCIA_COHORTE) -> dict`
  - `optimismo_de_la_derivacion(conjunto, clinica, salidas) -> dict`
  - `evaluar_celda(conjunto, rho1, rho0, replicas=0, con_sensibilidad=False) -> dict`
  - `evaluar_tarea(tarea) -> dict`, con `tarea = (rho1, rho0, replicas, con_sensibilidad)`
  - `imagen_sola(conjunto) -> dict`

- [ ] **Paso 0: Cerrar tres menores de la revisión de la tarea 2**

La revisión aprobó la tarea 2 y dejó tres menores sobre `salidas_del_sistema`,
que se cierran aquí porque esta tarea edita el mismo fichero:

- con el asma desconocida el diccionario guardaba, en `independencia`,
  `conservador`, `clinica`, `l_independencia` y `l_dependencia`, el valor de la
  PRIMERA de las dos puntuaciones. `medir` lo filtraba, pero era una trampa
  para quien recibiera el diccionario: pasan a `nan`, y las métricas rechazan
  un `nan`;
- `zip` cortaba en silencio si las RV de imagen y los casos no tenían la misma
  longitud;
- ninguna prueba afirmaba el punto medio de los `no_se` ni ejercitaba la rama
  de `dependencia` de la guarda del bloque.

Primero las pruebas.

**1.** En `tests/test_simulacion.py`, busca

```python
from copiloto_triaje.servicio.heckerling import combinacion
```

y sustitúyelo por

```python
from copiloto_triaje.servicio.heckerling import RV_POR_PUNTUACION, combinacion, combinar
```

**2.** En `tests/test_simulacion.py`, busca

```python
    _, clinica, salidas, _ = escenario_0a
    filas = clinica.to_dict("records")
    for i in (0, 1, 2, 500, 3810):
        b = combinacion(conjunto.prevalencia, generador.hallazgos(filas[i]), float(conjunto.rv[i]))
        assert salidas["independencia"][i] == b["independencia"][0]
        assert salidas["concordantes"][i] == b["concordantes"]
        assert salidas["conservador"][i] == (b["dependencia"][0] if b["concordantes"]
                                             else b["independencia"][0])
        assert salidas["puntuacion"][i] == b["puntuacion"][0]
    conocida = salidas["conocida"]
    assert np.array_equal(conocida, (clinica["asma"] != "no_se").values)
    assert np.array_equal(salidas["puntuacion"][conocida], clinica["k"].values[conocida])
    assert np.array_equal(salidas["puntuacion"][~conocida], clinica["k4"].values[~conocida])
    # la horquilla solo existe con concordancia
    assert np.array_equal(np.isfinite(salidas["l_dependencia"]), salidas["concordantes"])
    assert np.all(salidas["l_minima"] <= salidas["l_maxima"])
    assert set(salidas["primaria"]) <= {"baja", "intermedia", "alta"}
```

y sustitúyelo por

```python
    _, clinica, salidas, _ = escenario_0a
    filas = clinica.to_dict("records")
    conocida = salidas["conocida"]
    assert np.array_equal(conocida, (clinica["asma"] != "no_se").values)
    for i in np.flatnonzero(conocida)[[0, 1, 2, 500, -1]]:
        b = combinacion(conjunto.prevalencia, generador.hallazgos(filas[i]), float(conjunto.rv[i]))
        assert salidas["independencia"][i] == b["independencia"][0]
        assert salidas["concordantes"][i] == b["concordantes"]
        assert salidas["conservador"][i] == (b["dependencia"][0] if b["concordantes"]
                                             else b["independencia"][0])
        assert salidas["puntuacion"][i] == b["puntuacion"][0]
    assert np.array_equal(salidas["puntuacion"][conocida], clinica["k"].values[conocida])
    assert np.array_equal(salidas["puntuacion"][~conocida], clinica["k4"].values[~conocida])
    # la horquilla solo existe con concordancia y con UNA puntuacion
    assert np.array_equal(np.isfinite(salidas["l_dependencia"]),
                          salidas["concordantes"] & conocida)
    assert np.all(salidas["l_minima"] <= salidas["l_maxima"])
    assert set(salidas["primaria"]) <= {"baja", "intermedia", "alta"}


def test_con_el_asma_desconocida_no_hay_un_modelo_puntual_sino_un_rango(conjunto, escenario_0a):
    """Dos puntuaciones, [k4, k4 + 1]: los modelos puntuales quedan sin dato y
    lo que se mide es el rango y su punto medio EN LOG-ODDS."""
    _, clinica, salidas, _ = escenario_0a
    no_se = np.flatnonzero(~salidas["conocida"])
    assert no_se.size == 351
    for nombre in ("independencia", "conservador", "clinica", "l_independencia",
                   "l_dependencia"):
        assert np.all(np.isnan(salidas[nombre][no_se])), nombre
        assert np.all(np.isfinite(salidas[nombre][salidas["conocida"]])
                      | (nombre == "l_dependencia")), nombre
    for i in no_se[[0, 1, 2, 100, -1]]:
        k4, r = int(clinica["k4"].values[i]), float(conjunto.rv[i])
        dos = [metricas.logit([combinar(conjunto.prevalencia, RV_POR_PUNTUACION[k], r)])[0]
               for k in (k4, k4 + 1)]
        assert salidas["l_medio"][i] == pytest.approx(sum(dos) / 2, abs=1e-12)
        assert salidas["l_minima"][i] <= min(dos) and max(dos) <= salidas["l_maxima"][i]
        assert salidas["l_minima"][i] <= salidas["l_medio"][i] <= salidas["l_maxima"][i]


def test_las_rv_de_imagen_tienen_que_casar_con_los_casos(conjunto, escenario_0a):
    _, clinica, _, _ = escenario_0a
    with pytest.raises(ValueError, match="tienen que casar"):
        simulacion.salidas_del_sistema(conjunto.prevalencia, clinica.head(5), conjunto.rv[:4])
```

**3.** En `tests/test_simulacion.py`, busca

```python
    def alterada(prevalencia, hallazgos, rv_imagen):
        b = combinacion(prevalencia, hallazgos, rv_imagen)
        b["independencia"] = [round(x + 0.0001, 4) for x in b["independencia"]]
        return b

    monkeypatch.setattr(simulacion, "combinacion", alterada)
    with pytest.raises(AssertionError, match="no es el redondeo"):
        simulacion.salidas_del_sistema(conjunto.prevalencia, clinica.head(5), conjunto.rv[:5])
```

y sustitúyelo por

```python
    def con(campo):
        def alterada(prevalencia, hallazgos, rv_imagen):
            b = combinacion(prevalencia, hallazgos, rv_imagen)
            if b[campo] is not None:
                b[campo] = [round(x + 0.0001, 4) for x in b[campo]]
            return b
        return alterada

    concordantes = clinica[escenario_0a[2]["concordantes"]].head(5)
    rv = conjunto.rv[concordantes.index.values]
    for campo in ("independencia", "dependencia"):
        monkeypatch.setattr(simulacion, "combinacion", con(campo))
        with pytest.raises(AssertionError, match="no es el redondeo"):
            simulacion.salidas_del_sistema(conjunto.prevalencia, concordantes, rv)
```

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `3 failed, 12 passed`. Fallan
`test_las_salidas_son_las_del_codigo_del_servidor` (la horquilla aún existe
para los `no_se` concordantes),
`test_con_el_asma_desconocida_no_hay_un_modelo_puntual_sino_un_rango` y
`test_las_rv_de_imagen_tienen_que_casar_con_los_casos`. La prueba de la guarda
del bloque ya pasa: la guarda miraba `dependencia`; lo que faltaba era la
prueba.

Después el código.

**1.** En `src/copiloto_triaje/validacion/simulacion.py`, busca

```python
    """Lo que el codigo del servidor da para cada caso. Las probabilidades de
    los modelos puntuales son las del BLOQUE (redondeadas a 4 decimales, lo
    que el sistema entrega); los extremos de la horquilla van SIN redondear,
    recalculados con `combinar` y contrastados con el bloque."""
    n = len(clinica)
```

y sustitúyelo por

```python
    """Lo que el codigo del servidor da para cada caso. Las probabilidades de
    los modelos puntuales son las del BLOQUE (redondeadas a 4 decimales, lo
    que el sistema entrega); los extremos de la horquilla van SIN redondear,
    recalculados con `combinar` y contrastados con el bloque.

    Con el asma desconocida el sistema da DOS puntuaciones: no hay UN modelo
    puntual ni UNA horquilla, y `independencia`, `conservador`, `clinica`,
    `l_independencia` y `l_dependencia` quedan en nan. Esos casos se miden con
    `l_minima`, `l_maxima` y `l_medio`."""
    n = len(clinica)
    rv = np.asarray(rv, dtype=float)
    if rv.shape != (n,):
        raise ValueError(f"hay {n} casos y {rv.size} RV de imagen: tienen que casar")
```

**2.** En `src/copiloto_triaje/validacion/simulacion.py`, busca

```python
        s["conocida"][i] = fila["asma"] != "no_se"
        s["concordantes"][i] = b["concordantes"]
        s["puntuacion"][i] = b["puntuacion"][0]
        s["primaria"][i] = categoria_del_sistema(b)["primaria"]
        s["independencia"][i] = b["independencia"][0]
        s["conservador"][i] = b["dependencia"][0] if b["concordantes"] else b["independencia"][0]
        s["clinica"][i] = combinar(prevalencia, RV_POR_PUNTUACION[b["puntuacion"][0]], 1.0)
        l_ind = [math.log(x / (1.0 - x)) for x in ind]
        todas = [math.log(x / (1.0 - x)) for x in ind + dep]
        s["l_independencia"][i] = l_ind[0]
        if dep:
            s["l_dependencia"][i] = math.log(dep[0] / (1.0 - dep[0]))
        s["l_minima"][i], s["l_maxima"][i] = min(todas), max(todas)
        s["l_medio"][i] = sum(l_ind) / len(l_ind)
    return s
```

y sustitúyelo por

```python
        s["conocida"][i] = fila["asma"] != "no_se"
        s["concordantes"][i] = b["concordantes"]
        s["puntuacion"][i] = b["puntuacion"][0]
        s["primaria"][i] = categoria_del_sistema(b)["primaria"]
        l_ind = [math.log(x / (1.0 - x)) for x in ind]
        todas = [math.log(x / (1.0 - x)) for x in ind + dep]
        s["l_minima"][i], s["l_maxima"][i] = min(todas), max(todas)
        s["l_medio"][i] = sum(l_ind) / len(l_ind)
        if not s["conocida"][i]:
            continue
        s["independencia"][i] = b["independencia"][0]
        s["conservador"][i] = b["dependencia"][0] if b["concordantes"] else b["independencia"][0]
        s["clinica"][i] = combinar(prevalencia, RV_POR_PUNTUACION[b["puntuacion"][0]], 1.0)
        s["l_independencia"][i] = l_ind[0]
        if dep:
            s["l_dependencia"][i] = math.log(dep[0] / (1.0 - dep[0]))
    return s
```

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py tests/test_metricas.py -q`

Esperado: `41 passed` (15 de la simulación y 26 de las métricas). Las cifras
fijadas de la tarea 2 no cambian: solo cambia lo que se guarda de los casos
que `medir` ya dejaba fuera.

```bash
git add src/copiloto_triaje/validacion/simulacion.py tests/test_simulacion.py
git commit -m "fix(validacion): con el asma desconocida no hay modelo puntual, y las RV casan con los casos" -m "salidas_del_sistema deja en nan los modelos puntuales y la horquilla de los casos con dos puntuaciones, en vez de guardar los de la primera, y rechaza unas RV de imagen que no casan con los casos. Pruebas del punto medio de los no_se, en log-odds, y de la rama de dependencia de la guarda del bloque." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Paso 1: Escribir las pruebas del bootstrap**

En `tests/test_simulacion.py` sustituye la línea

```python
from copiloto_triaje.servicio.heckerling import RV_POR_PUNTUACION, combinacion, combinar
```

por

```python
from copiloto_triaje.servicio.heckerling import (
    PREVALENCIA_COHORTE, RV_POR_PUNTUACION, combinacion, combinar,
)
```

y añade al final del fichero (dos líneas en blanco antes):

```python
# --------------------------------------------------------------------------
# El bootstrap
# --------------------------------------------------------------------------
def test_el_bootstrap_es_pareado_reproducible_y_por_percentiles(conjunto):
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)
    a = simulacion.bootstrap(conjunto, modelo, replicas=4)
    assert a == simulacion.bootstrap(conjunto, modelo, replicas=4)
    for ruta in ("modelos.independencia.auc", "pareadas.independencia.auc",
                 "pareadas.conservador.pendiente", "horquilla.todos.contencion",
                 "horquilla.a_favor.lambda.mediana", "discordantes.sesgo_mediano",
                 "no_se.contencion", "no_se.punto_medio.error_abs_mediano"):
        lo, hi = a[ruta]
        assert lo <= hi, ruta
    assert not any(ruta.startswith("recuentos") for ruta in a)
    # cada replica sortea su clinica y sus placas
    r0, r1 = (simulacion.replica(conjunto, modelo, b) for b in (0, 1))
    assert r0 != r1 and r0 == simulacion.replica(conjunto, modelo, 0)
    # y el intervalo son los percentiles 2,5 y 97,5 de las replicas
    corridas = [simulacion.replica(conjunto, modelo, b) for b in range(4)]
    ruta = "pareadas.independencia.auc"
    assert a[ruta] == pytest.approx(list(np.percentile([c[ruta] for c in corridas],
                                                       [2.5, 97.5])))


def test_las_replicas_no_reajustan_el_generador(conjunto, monkeypatch):
    """z_y, los umbrales y el calibrador quedan fijos: una réplica no vuelve
    a llamar a `oraculo.ajustar` (spec §4.6)."""
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)

    def prohibido(*a, **k):
        raise AssertionError("una réplica no reajusta el modelo")

    monkeypatch.setattr(oraculo, "ajustar", prohibido)
    assert simulacion.bootstrap(conjunto, modelo, replicas=1)
```

- [ ] **Paso 2: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `2 failed, 15 passed`, con
`AttributeError: module 'copiloto_triaje.validacion.simulacion' has no attribute 'bootstrap'`.

- [ ] **Paso 3: Ampliar los imports y las constantes, y escribir la réplica y el bootstrap**

En `src/copiloto_triaje/validacion/simulacion.py` sustituye el bloque de
imports del paquete

```python
from copiloto_triaje.servicio.heckerling import (
    RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from . import datos, generador, metricas, oraculo
from .categoria import categoria_del_sistema
```

por

```python
from copiloto_triaje.servicio.heckerling import (
    PREVALENCIA_COHORTE, RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from . import datos, generador, metricas, oraculo
from .categoria import BANDAS, banda, categoria_del_sistema, porcentaje_entero
```

y el bloque de constantes

```python
SEMILLA_PUNTUAL = 1          # la misma clinica que comprueba 0A
MODELOS = ("imagen", "clinica", "independencia", "conservador")
COMBINADOS = ("independencia", "conservador")
```

por

```python
SEMILLA_PUNTUAL = 1          # la misma clinica que comprueba 0A
SEMILLA_CLINICA = 10_000     # replica b: generar(modelo, SEMILLA_CLINICA + b)
SEMILLA_INDICES = 20_000     # replica b: default_rng(SEMILLA_INDICES + b)
B_REPLICAS = 1000
HIPOTESIS_CONTENCION = 0.90  # «el oraculo queda dentro en ≥ 90 % de los concordantes»
MODELOS = ("imagen", "clinica", "independencia", "conservador")
COMBINADOS = ("independencia", "conservador")
# Las bandas de la validacion externa de Heckerling (SP4 §4.1), para 0C.
RV_VALIDACION = {0: 0.19, 1: 0.19, 2: 1.04, 3: 1.04, 4: 8.33, 5: 8.33}
POCO_INFORMATIVA = 0.5       # |ln RV_recuentos(k)| por debajo: k = 2 y k = 3
EXTREMAS = (0, 1, 4, 5)
```

Y añade al final del fichero (dos líneas en blanco antes):

```python
def replica(conjunto: Conjunto, modelo: oraculo.Modelo, b: int) -> dict:
    clinica = generador.generar(modelo, SEMILLA_CLINICA + b)
    salidas = salidas_del_sistema(conjunto.prevalencia, clinica, conjunto.rv)
    l_or = oraculo_de_los_casos(modelo, conjunto.q, clinica)
    n = conjunto.y.size
    filas = np.random.default_rng(SEMILLA_INDICES + b).integers(0, n, n)
    return aplanar(medir(conjunto, salidas, l_or, filas))


def bootstrap(conjunto: Conjunto, modelo: oraculo.Modelo, replicas: int = B_REPLICAS) -> dict:
    """{ruta: [li, ls]} al 95 % por percentiles, pareado: cada replica mide
    todos los modelos sobre las mismas placas y la misma clinica."""
    corridas = [replica(conjunto, modelo, b) for b in range(replicas)]
    rutas = sorted(set().union(*corridas)) if corridas else []
    return {r: metricas.percentiles([c.get(r, float("nan")) for c in corridas])
            for r in rutas}
```

- [ ] **Paso 4: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `17 passed`.

- [ ] **Paso 5: Escribir las pruebas de la celda completa**

Añade al final de `tests/test_simulacion.py` (dos líneas en blanco antes):

```python
# --------------------------------------------------------------------------
# La celda completa: escala legible, previo, 0C e intervalos
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def celda_0a(conjunto):
    return simulacion.evaluar_celda(conjunto, 0.0, 0.0, con_sensibilidad=True)


@pytest.fixture(scope="module")
def celda_simetrica(conjunto):
    return simulacion.evaluar_celda(conjunto, 0.3, 0.3, con_sensibilidad=True)


def test_la_celda_lleva_lo_medido_y_lo_que_solo_se_calcula_una_vez(celda_0a, medida_0a):
    assert celda_0a["nombre"] == "0A" and (celda_0a["rho1"], celda_0a["rho0"]) == (0.0, 0.0)
    for clave in ("recuentos", "pareadas", "horquilla", "discordantes", "no_se"):
        assert celda_0a[clave] == medida_0a[clave]
    assert celda_0a["hipotesis"] == {"umbral": 0.9, "contencion": 1.0, "se_sostiene": True}
    for nombre in simulacion.MODELOS:
        m = celda_0a["modelos"][nombre]
        assert m["auc"] == medida_0a["modelos"][nombre]["auc"]
        assert 0.0 < m["suelo"]["media"] < m["suelo"]["p95"]
        assert len(m["fiabilidad"]) == metricas.BINS
        assert sum(b["n"] for b in m["fiabilidad"]) == 3460
    # con independencia de verdad, la ECE de la combinacion no supera su suelo
    independencia = celda_0a["modelos"]["independencia"]
    assert independencia["ece"] < independencia["suelo"]["p95"]


def test_la_hipotesis_del_90_no_se_sostiene_con_dependencia_simetrica(celda_simetrica):
    c = celda_simetrica
    assert c["correlacion_teorica"]["con_neumonia"] == pytest.approx(0.2860, abs=5e-4)
    assert c["correlacion_teorica"]["sin_neumonia"] == pytest.approx(0.2751, abs=5e-4)
    assert c["hipotesis"]["contencion"] == c["horquilla"]["todos"]["contencion"]
    assert c["hipotesis"]["se_sostiene"] is False
    independencia = c["modelos"]["independencia"]
    assert independencia["ece"] > independencia["suelo"]["p95"]


def test_evaluar_celda_lleva_intervalos_solo_si_se_piden(conjunto, celda_0a):
    assert "intervalos" not in celda_0a and "replicas" not in celda_0a
    c = simulacion.evaluar_celda(conjunto, 0.3, 0.0, replicas=2)
    assert c["replicas"] == 2
    medido = {k: c[k] for k in ("modelos", "pareadas", "horquilla", "discordantes", "no_se")}
    solo_puntuales = {f"modelos.{m}.suelo.{x}" for m in simulacion.MODELOS
                      for x in ("media", "p95")}
    assert set(c["intervalos"]) == set(simulacion.aplanar(medido)) - solo_puntuales
    assert "sensibilidad_al_previo" not in c and "optimismo_de_la_derivacion" not in c


def test_una_tarea_es_una_celda_desde_cero(celda_simetrica):
    c = simulacion.evaluar_tarea((0.3, 0.3, 0, True))
    assert c == celda_simetrica


def test_sin_dependencia_la_puntuacion_conserva_todo_su_log_rv(celda_0a):
    for lado in ("a_favor", "en_contra"):
        e = celda_0a["escala_legible"][lado]
        assert e["fraccion_mediana_extremas"] == pytest.approx(1.0, abs=1e-9)
        for fila in e["por_puntuacion"]:
            assert fila["log_rv"]["mediana"] == pytest.approx(fila["ln_rv_recuentos"], abs=1e-9)
            assert fila["fraccion"]["q1"] == pytest.approx(1.0, abs=1e-9)
            assert fila["fraccion"]["q3"] == pytest.approx(1.0, abs=1e-9)
            assert fila["signo_invertido"] == 0.0
            assert fila["poco_informativa"] == (fila["k"] in (2, 3))
    placas = [celda_0a["escala_legible"][lado]["placas"] for lado in ("a_favor", "en_contra")]
    assert placas == [1248, 2563]


def test_con_dependencia_simetrica_conserva_menos_en_los_dos_lados(celda_simetrica):
    e = celda_simetrica["escala_legible"]
    assert e["a_favor"]["fraccion_mediana_extremas"] == pytest.approx(0.639, abs=5e-3)
    assert e["en_contra"]["fraccion_mediana_extremas"] == pytest.approx(0.484, abs=5e-3)
    # los casos esperados de cada lado suman sus placas
    for lado in ("a_favor", "en_contra"):
        assert sum(f["casos_esperados"] for f in e[lado]["por_puntuacion"]) == pytest.approx(
            e[lado]["placas"])


def test_cambios_de_banda():
    c = simulacion.cambios_de_banda(["baja", "intermedia", "alta", "alta"],
                                    ["baja", "baja", "intermedia", "alta"])
    assert c == {"casos": 4, "cambian": 2,
                 "transiciones": {"intermedia→baja": 1, "alta→intermedia": 1}}


def test_declarar_el_previo_de_la_cohorte_desplaza_medio_logit(celda_0a, celda_simetrica):
    for celda in (celda_0a, celda_simetrica):
        s = celda["sensibilidad_al_previo"]
        assert s["previo"] == pytest.approx(PREVALENCIA_COHORTE)
        assert s["previo_principal"] == pytest.approx(0.2215)
        assert s["desplazamiento_log_odds"] == pytest.approx(-0.5045, abs=5e-4)
        for nombre in simulacion.COMBINADOS:
            m = s["modelos"][nombre]
            # el intercepto sube lo que el previo bajo: ≈ +0,50 (spec §4.3)
            assert m["intercepto"] - m["intercepto_principal"] == pytest.approx(
                -s["desplazamiento_log_odds"], abs=2e-3)
            assert m["ece"] > m["suelo"]["p95"]
            # con un previo mas bajo, los casos solo pueden bajar de banda
            assert set(m["bandas"]["transiciones"]) <= {"intermedia→baja", "alta→intermedia"}
            assert m["bandas"]["cambian"] == sum(m["bandas"]["transiciones"].values())
        assert s["categoria_del_sistema"]["casos"] == 3811
    assert celda_0a["sensibilidad_al_previo"]["modelos"]["independencia"]["bandas"] == {
        "casos": 3460, "cambian": 338,
        "transiciones": {"intermedia→baja": 224, "alta→intermedia": 114}}
    assert celda_0a["sensibilidad_al_previo"]["categoria_del_sistema"]["cambian"] == 408


def test_0c_es_un_calculo_sobre_las_rv_publicadas(celda_0a, celda_simetrica):
    c = celda_0a["optimismo_de_la_derivacion"]
    assert [round(f["diferencia_log"], 2) for f in c["por_puntuacion"]] == [
        -0.46, 0.05, -0.40, 0.46, -0.15, 0.74]
    assert [f["rv_validacion"] for f in c["por_puntuacion"]] == [
        0.19, 0.19, 1.04, 1.04, 8.33, 8.33]
    assert c["bandas"] == {"casos": 3460, "cambian": 225,
                           "transiciones": {"baja→intermedia": 73, "intermedia→baja": 90,
                                            "intermedia→alta": 23, "alta→intermedia": 39}}
    assert "optimismo_de_la_derivacion" not in celda_simetrica


def test_la_imagen_sola_es_el_suelo_de_calibracion(conjunto):
    r = simulacion.imagen_sola(conjunto)
    assert r["casos"] == 3811
    assert r["auc"] == pytest.approx(0.8844, abs=5e-4)
    assert r["pendiente"] == pytest.approx(0.983, abs=5e-3)
    assert r["ece"] == pytest.approx(0.0163, abs=5e-4)
    assert r["ece"] < r["suelo"]["p95"]
    assert sum(b["n"] for b in r["fiabilidad"]) == 3811
```

- [ ] **Paso 6: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `17 passed` y las 10 nuevas en
rojo (fallos y errores de fixture), con
`AttributeError: … has no attribute 'evaluar_celda'` (y `'cambios_de_banda'`,
`'evaluar_tarea'`, `'imagen_sola'`).

- [ ] **Paso 7: Escribir la escala legible, el previo, 0C y la celda completa**

Añade al final de `src/copiloto_triaje/validacion/simulacion.py` (dos líneas
en blanco antes):

```python
def escala_legible(modelo: oraculo.Modelo, conjunto: Conjunto) -> dict:
    """Por lado de la imagen y por puntuacion: la RV de la puntuacion una vez
    vista la imagen, en log-odds, y que fraccion de su log-RV conserva. En
    forma cerrada: cada placa pesa P(k | q_i, y_i), la probabilidad con que
    el generador le da esa puntuacion."""
    lrv = oraculo.log_rv_condicional(modelo)
    p1, p0 = modelo.probabilidades()
    pesos = np.where((conjunto.y == 1)[:, None], p1, p0)
    salida = {}
    for lado, m in (("a_favor", conjunto.rv >= 1.0), ("en_contra", conjunto.rv < 1.0)):
        por_k, fr_ext, w_ext = [], [], []
        for k in range(6):
            ln_rv = math.log(oraculo.rv_recuentos(k))
            v, w = lrv[m, k], pesos[m, k]
            fr = v / ln_rv
            q = metricas.cuantiles_ponderados(v, w)
            qf = metricas.cuantiles_ponderados(fr, w)
            por_k.append({
                "k": k, "ln_rv_recuentos": ln_rv, "casos_esperados": float(w.sum()),
                "log_rv": {"q1": float(q[0]), "mediana": float(q[1]), "q3": float(q[2])},
                "fraccion": {"q1": float(qf[0]), "mediana": float(qf[1]), "q3": float(qf[2])},
                "signo_invertido": float(w[fr < 0].sum() / w.sum()),
                "poco_informativa": abs(ln_rv) < POCO_INFORMATIVA,
            })
            if k in EXTREMAS:
                fr_ext.append(fr)
                w_ext.append(w)
        salida[lado] = {
            "placas": int(m.sum()), "por_puntuacion": por_k,
            "fraccion_mediana_extremas": float(metricas.cuantiles_ponderados(
                np.concatenate(fr_ext), np.concatenate(w_ext), (0.5,))[0]),
        }
    return salida


def _bandas(p) -> np.ndarray:
    return np.array([banda(porcentaje_entero(float(x))) for x in p], dtype=object)


def cambios_de_banda(antes, despues) -> dict:
    """Cuantos casos cambian de banda y en que sentido («antes→despues»)."""
    antes, despues = np.asarray(antes, dtype=object), np.asarray(despues, dtype=object)
    transiciones = {}
    for a in BANDAS:
        for d in BANDAS:
            n = int(np.sum((antes == a) & (despues == d)))
            if a != d and n:
                transiciones[f"{a}→{d}"] = n
    return {"casos": int(antes.size), "cambian": int(np.sum(antes != despues)),
            "transiciones": transiciones}


def sensibilidad_al_previo(conjunto: Conjunto, clinica: pd.DataFrame, salidas: dict,
                           previo: float = PREVALENCIA_COHORTE) -> dict:
    """Lo que cuesta declarar `previo` en una poblacion cuya prevalencia es la
    del conjunto (spec §4.3): Brier, ECE e intercepto de los dos modelos
    combinados, y cuantos casos cambian de banda. El AUC no cambia."""
    otras = salidas_del_sistema(previo, clinica, conjunto.rv)
    s = salidas["conocida"]
    y, orden = conjunto.y[s], conjunto.orden[s]
    modelos = {}
    for c in COMBINADOS:
        antes, despues = salidas[c][s], otras[c][s]
        modelos[c] = {
            "brier": metricas.brier(y, despues), "brier_principal": metricas.brier(y, antes),
            "ece": metricas.ece(y, despues, orden), "ece_principal": metricas.ece(y, antes, orden),
            "suelo": metricas.suelo_de_ece(despues, orden),
            "intercepto": metricas.intercepto_de_calibracion(y, despues),
            "intercepto_principal": metricas.intercepto_de_calibracion(y, antes),
            "bandas": cambios_de_banda(_bandas(antes), _bandas(despues)),
        }
    desplazamiento = (math.log(previo / (1 - previo))
                      - math.log(conjunto.prevalencia / (1 - conjunto.prevalencia)))
    return {"previo": float(previo), "previo_principal": conjunto.prevalencia,
            "desplazamiento_log_odds": desplazamiento, "modelos": modelos,
            "categoria_del_sistema": cambios_de_banda(salidas["primaria"], otras["primaria"])}


def optimismo_de_la_derivacion(conjunto: Conjunto, clinica: pd.DataFrame, salidas: dict) -> dict:
    """0C, un CALCULO y no un experimento: cuanto difieren las RV de la
    derivacion (las del sistema) de las bandas de la validacion externa, y
    cuantos casos con el asma conocida cambiarian de banda con las segundas."""
    s = salidas["conocida"]
    k = salidas["puntuacion"][s]
    con_validacion = np.array([combinar(conjunto.prevalencia, RV_VALIDACION[int(kk)], float(r))
                               for kk, r in zip(k, conjunto.rv[s])])
    return {
        "por_puntuacion": [{"k": kk, "rv_derivacion": RV_POR_PUNTUACION[kk],
                            "rv_validacion": RV_VALIDACION[kk],
                            "diferencia_log": math.log(RV_POR_PUNTUACION[kk] / RV_VALIDACION[kk])}
                           for kk in range(6)],
        "bandas": cambios_de_banda(_bandas(salidas["independencia"][s]), _bandas(con_validacion)),
    }


def evaluar_celda(conjunto: Conjunto, rho1: float, rho0: float, replicas: int = 0,
                  con_sensibilidad: bool = False) -> dict:
    """La celda (ρ1, ρ0): estimacion puntual, suelo de la ECE y fiabilidad
    por modelo, escala legible, y si se piden, intervalos y sensibilidad."""
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, rho1, rho0)
    clinica = generador.generar(modelo, SEMILLA_PUNTUAL)
    salidas = salidas_del_sistema(conjunto.prevalencia, clinica, conjunto.rv)
    l_or = oraculo_de_los_casos(modelo, conjunto.q, clinica)
    celda = {"rho1": float(rho1), "rho0": float(rho0),
             "nombre": nombre_de_celda(rho1, rho0),
             "correlacion_teorica": {"con_neumonia": oraculo.correlacion_teorica(modelo, 1),
                                     "sin_neumonia": oraculo.correlacion_teorica(modelo, 0)}}
    celda.update(medir(conjunto, salidas, l_or))
    s = salidas["conocida"]
    p = {"imagen": conjunto.p_cal, "clinica": salidas["clinica"],
         "independencia": salidas["independencia"], "conservador": salidas["conservador"]}
    for m in MODELOS:
        celda["modelos"][m]["suelo"] = metricas.suelo_de_ece(p[m][s], conjunto.orden[s])
        celda["modelos"][m]["fiabilidad"] = metricas.fiabilidad(
            conjunto.y[s], p[m][s], conjunto.orden[s])
    contencion = celda["horquilla"]["todos"]["contencion"]
    celda["hipotesis"] = {"umbral": HIPOTESIS_CONTENCION, "contencion": contencion,
                          "se_sostiene": bool(contencion >= HIPOTESIS_CONTENCION)}
    celda["escala_legible"] = escala_legible(modelo, conjunto)
    if replicas:
        celda["replicas"] = int(replicas)
        celda["intervalos"] = bootstrap(conjunto, modelo, replicas)
    if con_sensibilidad:
        celda["sensibilidad_al_previo"] = sensibilidad_al_previo(conjunto, clinica, salidas)
        if rho1 == 0.0 and rho0 == 0.0:
            celda["optimismo_de_la_derivacion"] = optimismo_de_la_derivacion(
                conjunto, clinica, salidas)
    return celda


def evaluar_tarea(tarea) -> dict:
    """Una celda desde cero, para correrla en su propio proceso: `tarea` es
    (ρ1, ρ0, replicas, con_sensibilidad). Carga el conjunto congelado."""
    rho1, rho0, replicas, con_sensibilidad = tarea
    return evaluar_celda(cargar_conjunto(), rho1, rho0, int(replicas), bool(con_sensibilidad))


def imagen_sola(conjunto: Conjunto) -> dict:
    """La calibracion de la imagen sobre las 3 811 placas: el suelo de todo
    lo demas (spec §4.4)."""
    r = metricas.resumen_de_modelo(conjunto.y, conjunto.p_cal, conjunto.orden)
    r["suelo"] = metricas.suelo_de_ece(conjunto.p_cal, conjunto.orden)
    r["fiabilidad"] = metricas.fiabilidad(conjunto.y, conjunto.p_cal, conjunto.orden)
    r["casos"] = int(conjunto.y.size)
    return r
```

- [ ] **Paso 8: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py tests/test_metricas.py tests/test_validacion_0a.py tests/test_oraculo.py tests/test_generador.py -q`

Esperado: todo en verde; `tests/test_simulacion.py` aporta
`27` pruebas.

- [ ] **Paso 9: Commit**

```bash
git add src/copiloto_triaje/validacion/simulacion.py tests/test_simulacion.py
git commit -m "feat(validacion): bootstrap pareado, escala legible, sensibilidad al previo y 0C" -m "Cada réplica remuestrea placas y vuelve a sortear la clínica con el generador fijo; los intervalos son percentiles y las diferencias entre modelos se calculan dentro de la réplica. La escala legible va en forma cerrada, ponderando cada placa por la probabilidad con que el generador le da la puntuación. evaluar_celda reúne la estimación puntual, el suelo de la ECE, la fiabilidad, la hipótesis del 90 % y, si se piden, intervalos, sensibilidad al previo y 0C." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 4: El script corre la rejilla y escribe `resultados_simulacion.json`

**Ficheros:**
- Modificar: `src/copiloto_triaje/validacion/datos.py` (gana `huella_de_texto`)
- Crear: `scripts/validar_combinacion.py`
- Modificar: `tests/conftest.py` (fixtures `validar` y `resultados_minimos`)
- Crear: `tests/test_validar_combinacion.py`

**Interfaces:**
- Consume: `simulacion.evaluar_tarea`, `simulacion.cargar_conjunto`,
  `simulacion.imagen_sola` y las constantes de `simulacion` y `metricas`
  (tareas 1-3); `oraculo.RHO_REJILLA`, `oraculo.CELDAS_DESTACADAS`;
  `datos.CARPETA`, `datos.CRUDAS_CONGELADAS`, `datos.HASH_CONGELADO`,
  `datos.CALIBRADOR`, `datos.sha256_de`.
- Produce:
  - `datos.huella_de_texto(ruta) -> str`
  - En el script: `REPO`, `CARPETA`, `NOMBRE_RESULTADOS = "resultados_simulacion.json"`,
    `ANALISIS`, `ROTULO = "simulación semisintética"`, `TITULO`, `ADVERTENCIA`;
    `tareas_de_la_rejilla(replicas, rejilla=oraculo.RHO_REJILLA, destacadas=oraculo.CELDAS_DESTACADAS) -> list[tuple]`;
    `calcular(replicas=simulacion.B_REPLICAS, procesos=1, rejilla=…, destacadas=…) -> dict`;
    `escribir_resultados(resultados, ruta) -> Path`; `leer_resultados(ruta) -> dict`;
    `main(argv=None) -> int` con `--replicas`, `--procesos` y `--salida`.
    La línea de órdenes se fija aquí de una vez: `main()` declara también
    `--sin-figuras`, `--analisis` y `--solo-documento`. En esta tarea
    `--solo-documento` ya hace su parte (no recalcula, y sale con mensaje si
    el JSON no existe); `--sin-figuras` y `--analisis` cobran efecto en las
    tareas 5 y 6, que son las que dibujan y redactan.
  - Fixtures de sesión en `tests/conftest.py`: `validar` (el script cargado
    como módulo) y `resultados_minimos` (rejilla 2 × 2 con 2 réplicas, pasada
    por JSON: celdas `0A`, `(0; 0,3)`, `(0,3; 0)` y `(0,3; 0,3)`).

**La estructura de `resultados`** (la usan las tareas 5, 6 y 7): raíz con
`rotulo`, `titulo`, `advertencia`, `insumos`, `parametros`, `imagen_sola` y
`celdas` (lista en el orden de la rejilla: ρ1 creciente y, dentro, ρ0
creciente). Cada celda es lo que devuelve `simulacion.evaluar_celda` más
`destacada` (bool; 0A **no** es destacada: se cuenta aparte). Solo 0A y las
destacadas llevan `replicas`, `intervalos` y `sensibilidad_al_previo`; solo 0A
lleva `optimismo_de_la_derivacion`.

- [ ] **Paso 1: Escribir la prueba de la huella de texto**

Crea `tests/test_validar_combinacion.py` con este contenido:

```python
"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
from copiloto_triaje.validacion import datos


def test_la_huella_de_texto_no_depende_del_fin_de_linea(tmp_path):
    lf, crlf = tmp_path / "lf.csv", tmp_path / "crlf.csv"
    lf.write_bytes(b"a,b\n1,2\n")
    crlf.write_bytes(b"a,b\r\n1,2\r\n")
    assert datos.huella_de_texto(lf) == datos.huella_de_texto(crlf) == datos.sha256_de(lf)
    assert datos.sha256_de(crlf) != datos.sha256_de(lf)
```

- [ ] **Paso 2: Correrla y ver que falla**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validar_combinacion.py -q`

Esperado: `1 failed`, con
`AttributeError: module 'copiloto_triaje.validacion.datos' has no attribute 'huella_de_texto'`.

- [ ] **Paso 3: Escribir `huella_de_texto`**

En `src/copiloto_triaje/validacion/datos.py`, entre `sha256_de` y
`cargar_crudas`, añade:

```python
def huella_de_texto(ruta) -> str:
    """El sha256 de un fichero de TEXTO con los finales de linea normalizados
    a LF: con `core.autocrlf` el mismo fichero versionado tiene CRLF en un
    clon de Windows y LF en uno de Linux, y la huella tiene que ser la misma."""
    crudo = pathlib.Path(ruta).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(crudo).hexdigest()
```

- [ ] **Paso 4: Correrla y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validar_combinacion.py tests/test_validacion_datos.py -q`

Esperado: todo en verde (`1 passed` de este fichero).

- [ ] **Paso 5: Escribir las fixtures y las pruebas del script**

Añade al final de `tests/conftest.py`:

```python
# --------------------------------------------------------------------------
# La simulacion semisintetica (SP5 §4.6): el script y una rejilla minima
# --------------------------------------------------------------------------
def _cargar_validar_combinacion():
    import importlib.util
    import pathlib
    ruta = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "validar_combinacion.py"
    spec = importlib.util.spec_from_file_location("validar_combinacion", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="session")
def validar():
    """`scripts/validar_combinacion.py` cargado como modulo."""
    return _cargar_validar_combinacion()


@pytest.fixture(scope="session")
def resultados_minimos(validar):
    """Una rejilla de 2 x 2 con 2 replicas, tal como quedaria en el JSON: las
    celdas 0A, (0; 0,3), (0,3; 0) y (0,3; 0,3); con intervalos y sensibilidad
    en 0A y en (0,3; 0,3)."""
    import json
    r = validar.calcular(replicas=2, procesos=1, rejilla=(0.0, 0.3),
                         destacadas=((0.3, 0.3),))
    return json.loads(json.dumps(r, ensure_ascii=False))
```

Y sustituye el contenido de `tests/test_validar_combinacion.py` por este (la
prueba de la huella se conserva, en su sitio):

```python
"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
import json

import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE
from copiloto_triaje.validacion import datos, oraculo, simulacion


def test_las_tareas_de_la_rejilla(validar):
    tareas = validar.tareas_de_la_rejilla(1000)
    assert len(tareas) == 25
    assert tareas[0] == (0.0, 0.0, 1000, True)            # 0A
    completas = [(a, b) for a, b, replicas, todo in tareas if todo]
    assert set(completas) == {(0.0, 0.0)} | set(oraculo.CELDAS_DESTACADAS)
    assert all(replicas == (1000 if todo else 0) for _, _, replicas, todo in tareas)
    assert [(a, b) for a, b, _, _ in tareas[:6]] == [
        (0.0, 0.0), (0.0, 0.15), (0.0, 0.3), (0.0, 0.45), (0.0, 0.6), (0.15, 0.0)]


def test_los_resultados_llevan_rotulo_insumos_y_parametros(resultados_minimos):
    r = resultados_minimos
    assert r["rotulo"] == "simulación semisintética"
    assert "simulación semisintética" in r["titulo"]
    assert "exactitud clínica" in r["advertencia"]
    i = r["insumos"]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert len(i["pesos_sha256"]) == 64
    p = r["parametros"]
    assert p["replicas"] == 2 and p["epsilon"] == 0.015 and p["bins"] == 10
    assert p["previo_desplegado"] == pytest.approx(PREVALENCIA_COHORTE)
    assert p["semilla_puntual"] == simulacion.SEMILLA_PUNTUAL
    assert p["rejilla"] == [0.0, 0.3] and p["destacadas"] == [[0.3, 0.3]]


def test_las_celdas_van_en_el_orden_de_la_rejilla(resultados_minimos):
    celdas = resultados_minimos["celdas"]
    assert [c["nombre"] for c in celdas] == ["0A", "(0; 0,3)", "(0,3; 0)", "(0,3; 0,3)"]
    assert [c["destacada"] for c in celdas] == [False, False, False, True]
    con_intervalos = [c["nombre"] for c in celdas if "intervalos" in c]
    assert con_intervalos == ["0A", "(0,3; 0,3)"]
    assert [c["nombre"] for c in celdas if "sensibilidad_al_previo" in c] == con_intervalos
    assert [c["nombre"] for c in celdas if "optimismo_de_la_derivacion" in c] == ["0A"]
    cero = celdas[0]
    assert cero["horquilla"]["todos"]["contencion"] == 1.0
    assert cero["intervalos"]["horquilla.todos.contencion"] == [1.0, 1.0]
    assert resultados_minimos["imagen_sola"]["casos"] == 3811


def test_el_json_se_escribe_en_utf8_con_lf_y_se_lee_igual(validar, resultados_minimos, tmp_path):
    ruta = validar.escribir_resultados(resultados_minimos, tmp_path / "sub" / "r.json")
    crudo = ruta.read_bytes()
    assert b"\r\n" not in crudo and crudo.endswith(b"\n")
    assert "simulación semisintética".encode("utf-8") in crudo
    assert "intermedia→baja".encode("utf-8") in crudo
    assert validar.leer_resultados(ruta) == resultados_minimos
    assert json.loads(crudo.decode("utf-8")) == resultados_minimos


def test_la_huella_de_texto_no_depende_del_fin_de_linea(tmp_path):
    lf, crlf = tmp_path / "lf.csv", tmp_path / "crlf.csv"
    lf.write_bytes(b"a,b\n1,2\n")
    crlf.write_bytes(b"a,b\r\n1,2\r\n")
    assert datos.huella_de_texto(lf) == datos.huella_de_texto(crlf) == datos.sha256_de(lf)
    assert datos.sha256_de(crlf) != datos.sha256_de(lf)


def test_en_paralelo_sale_lo_mismo_que_en_serie(validar, resultados_minimos):
    r = validar.calcular(replicas=2, procesos=2, rejilla=(0.0, 0.3),
                         destacadas=((0.3, 0.3),))
    assert json.loads(json.dumps(r, ensure_ascii=False)) == resultados_minimos


def test_main_escribe_los_resultados_donde_se_le_dice(validar, tmp_path, monkeypatch, capsys):
    llamadas = []

    def calcular_falso(replicas, procesos):
        llamadas.append((replicas, procesos))
        return {"rotulo": validar.ROTULO, "celdas": []}

    monkeypatch.setattr(validar, "calcular", calcular_falso)
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert llamadas == [(3, 1)]
    assert validar.leer_resultados(tmp_path / "resultados_simulacion.json")["celdas"] == []
    assert "resultados_simulacion.json" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        validar.main(["--procesos", "0", "--salida", str(tmp_path)])
```

- [ ] **Paso 6: Correrlas y ver que fallan**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validar_combinacion.py -q`

Esperado: `1 passed, 6 errors`: pasa la de la huella y las otras seis dan
error de fixture, `FileNotFoundError` sobre `scripts/validar_combinacion.py`.

- [ ] **Paso 7: Escribir el script**

Crea `scripts/validar_combinacion.py` con este contenido:

```python
# -*- coding: utf-8 -*-
"""Corre la simulacion semisintetica de la combinacion y deja sus resultados.

USO
    python scripts/validar_combinacion.py
    python scripts/validar_combinacion.py --replicas 50 --sin-figuras     (ensayo rapido)
    python scripts/validar_combinacion.py --solo-documento                (sin recalcular)

Lee docs/validacion-semisintetica/crudas_prueba.csv (congelada) y
servidor/calibrador.json; no necesita los pesos, ni Docker, ni red. Escribe en
docs/validacion-semisintetica/ el fichero resultados_simulacion.json y las
figuras a 300 DPI, y en docs/validacion-semisintetica-sp5.md el analisis.
Ninguna cifra del analisis se teclea: el documento y las figuras se generan
LEYENDO resultados_simulacion.json, no las variables en memoria.

La rejilla son 25 celdas (ρ1, ρ0); el bootstrap (1 000 replicas) se corre en
0A y en las seis celdas destacadas, una celda por proceso.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402
from copiloto_triaje.validacion import datos, metricas, oraculo, simulacion  # noqa: E402

CARPETA = datos.CARPETA
NOMBRE_RESULTADOS = "resultados_simulacion.json"
ANALISIS = REPO / "docs" / "validacion-semisintetica-sp5.md"
ROTULO = "simulación semisintética"
TITULO = "Validación de la combinación de clínica e imagen: simulación semisintética (SP5 §4)"
ADVERTENCIA = (
    "Las placas y sus etiquetas son reales (conjunto de prueba de RSNA); la clínica "
    "se sortea con la distribución publicada de la puntuación de Heckerling y la "
    "dependencia entre clínica e imagen es un supuesto declarado. Nada de esto mide "
    "exactitud clínica en pacientes.")


def tareas_de_la_rejilla(replicas: int, rejilla=oraculo.RHO_REJILLA,
                         destacadas=oraculo.CELDAS_DESTACADAS) -> list:
    """(ρ1, ρ0, replicas, con_sensibilidad) por celda, en el orden de la
    rejilla. Solo 0A y las destacadas llevan bootstrap y sensibilidad."""
    tareas = []
    for rho1 in rejilla:
        for rho0 in rejilla:
            completa = (rho1 == 0.0 and rho0 == 0.0) or (rho1, rho0) in tuple(destacadas)
            tareas.append((float(rho1), float(rho0), replicas if completa else 0, completa))
    return tareas


def _relativa(ruta: Path) -> str:
    try:
        return Path(ruta).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(ruta).name


def calcular(replicas: int = simulacion.B_REPLICAS, procesos: int = 1,
             rejilla=oraculo.RHO_REJILLA, destacadas=oraculo.CELDAS_DESTACADAS) -> dict:
    conjunto = simulacion.cargar_conjunto()
    tareas = tareas_de_la_rejilla(replicas, rejilla, destacadas)
    if procesos > 1:
        with ProcessPoolExecutor(max_workers=procesos) as grupo:
            celdas = list(grupo.map(simulacion.evaluar_tarea, tareas))
    else:
        celdas = [simulacion.evaluar_tarea(t) for t in tareas]
    for celda, (rho1, rho0, _, completa) in zip(celdas, tareas):
        celda["destacada"] = bool(completa and not (rho1 == 0.0 and rho0 == 0.0))
    return {
        "rotulo": ROTULO,
        "titulo": TITULO,
        "advertencia": ADVERTENCIA,
        "insumos": {
            "crudas": _relativa(datos.CRUDAS_CONGELADAS),
            "crudas_sha256": datos.huella_de_texto(datos.CRUDAS_CONGELADAS),
            "pesos_sha256": datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0],
            "calibrador": _relativa(datos.CALIBRADOR),
            "calibrador_sha256": datos.huella_de_texto(datos.CALIBRADOR),
            "placas": int(conjunto.y.size),
            "positivas": int(conjunto.y.sum()),
            "prevalencia": conjunto.prevalencia,
        },
        "parametros": {
            "replicas": int(replicas),
            "semilla_puntual": simulacion.SEMILLA_PUNTUAL,
            "semilla_clinica": simulacion.SEMILLA_CLINICA,
            "semilla_indices": simulacion.SEMILLA_INDICES,
            "epsilon": metricas.EPSILON,
            "bins": metricas.BINS,
            "repeticiones_suelo": metricas.REPETICIONES_SUELO,
            "semilla_suelo": metricas.SEMILLA_SUELO,
            "hipotesis_contencion": simulacion.HIPOTESIS_CONTENCION,
            "previo_desplegado": PREVALENCIA_COHORTE,
            "rejilla": [float(r) for r in rejilla],
            "destacadas": [[float(a), float(b)] for a, b in destacadas],
        },
        "imagen_sola": simulacion.imagen_sola(conjunto),
        "celdas": celdas,
    }


def escribir_resultados(resultados: dict, ruta) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(resultados, ensure_ascii=False, indent=1) + "\n")
    return ruta


def leer_resultados(ruta) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--replicas", type=int, default=simulacion.B_REPLICAS,
                   help="réplicas del bootstrap en 0A y las seis celdas destacadas")
    p.add_argument("--procesos", type=int, default=min(7, os.cpu_count() or 1),
                   help="celdas en paralelo (1: en serie)")
    p.add_argument("--salida", default=str(CARPETA),
                   help="carpeta de resultados_simulacion.json y de las figuras")
    p.add_argument("--analisis", default=str(ANALISIS), help="el documento de análisis")
    p.add_argument("--sin-figuras", action="store_true")
    p.add_argument("--solo-documento", action="store_true",
                   help="no recalcula: lee el JSON de --salida y regenera figuras y documento")
    args = p.parse_args(argv)
    if args.replicas < 0 or args.procesos < 1:
        raise SystemExit("--replicas no puede ser negativo y --procesos debe ser al menos 1")
    salida = Path(args.salida)
    ruta = salida / NOMBRE_RESULTADOS
    if not args.solo_documento:
        escribir_resultados(calcular(args.replicas, args.procesos), ruta)
        print(f"resultados: {ruta}")
    elif not ruta.is_file():
        raise SystemExit(f"no existe {ruta}: corre primero sin --solo-documento")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Paso 8: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validar_combinacion.py -q`

Esperado: `7 passed` (unos 10 s: la fixture calcula cuatro celdas y la prueba
del paralelo las vuelve a calcular en dos procesos).

- [ ] **Paso 9: Un ensayo de verdad, sin escribir en el repo**

Orden (Git Bash; la carpeta de salida es temporal):

```bash
C:/venv-copiloto/Scripts/python.exe scripts/validar_combinacion.py --replicas 20 --salida "$TEMP/ensayo-validar"
```

Esperado: termina en menos de un minuto e imprime
`resultados: …/ensayo-validar/resultados_simulacion.json`. Comprueba que no ha
escrito nada en el repo: `git status --short` no enseña nada nuevo bajo
`docs/`.

- [ ] **Paso 10: Commit**

```bash
git add src/copiloto_triaje/validacion/datos.py scripts/validar_combinacion.py tests/conftest.py tests/test_validar_combinacion.py
git commit -m "feat(validacion): validar_combinacion.py corre la rejilla y escribe resultados_simulacion.json" -m "Las 25 celdas de la rejilla, una por proceso; bootstrap y sensibilidad al previo en 0A y en las seis destacadas. El JSON lleva el rótulo, las huellas de los insumos (con los finales de línea normalizados, para que sean las mismas en Windows y en Linux), las semillas y los parámetros, y no lleva fecha: dos corridas dan el mismo fichero." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 5: Las figuras

**Ficheros:**
- Modificar: `scripts/validar_combinacion.py` (bloque nuevo «LAS FIGURAS» antes de `main()`, y dos cambios dentro de `main()`)
- Modificar: `pyproject.toml` (el extra `figuras`)
- Prueba: `tests/test_validar_combinacion.py` (un cambio en una prueba de la tarea 4 y seis pruebas nuevas al final)

**Interfaces:**
- Consume: del propio script, `ROTULO`, `NOMBRE_RESULTADOS`, `leer_resultados(ruta) -> dict`,
  `escribir_resultados`, `calcular`; `simulacion.MODELOS`; el diccionario `resultados`
  (de cada celda: `nombre`, `rho1`, `rho0`, `destacada`, `modelos[m].fiabilidad[] {p_media, observada}`,
  `modelos[m].ece`, `modelos[m].suelo.media`, `modelos.independencia.pendiente`,
  `horquilla.{todos,a_favor,en_contra}.{bajo,contencion,sobre}`; y `parametros.rejilla`);
  las fixtures de sesión `validar` y `resultados_minimos` de `tests/conftest.py`.
- Produce, en `scripts/validar_combinacion.py`:
  - constantes `DPI = 300`, `FIGURAS_GLOBALES = ("horquilla_por_celda", "contencion_rejilla", "pendiente_rejilla")`,
    `PREFIJO_FIABILIDAD = "fiabilidad_"`, `REJILLAS = ("contencion", "pendiente")`,
    y las de estilo (`TINTA`, `COLOR_DIAGONAL`, `COLOR_MODELO`, `MARCA_MODELO`, `NOMBRE_MODELO`,
    `TRAMOS`, `LADOS`, `RAMPA_AZUL`, `RAMPA_DIVERGENTE`);
  - `slug_de_celda(celda: dict) -> str` (`"0a"`; `"r1-030_r0-000"`);
  - `celdas_con_figura(resultados: dict) -> list` (0A y las destacadas, en el orden de la rejilla);
  - `figura_fiabilidad(celda: dict, destino) -> Path`;
  - `figura_horquilla(resultados: dict, destino) -> Path`;
  - `figura_rejilla(resultados: dict, destino, que: str) -> Path` (`que` fuera de `REJILLAS`: `ValueError`);
  - `figuras(resultados: dict, carpeta) -> list[Path]` (en orden: las `fiabilidad_<slug>.png`
    en el orden de la rejilla, `horquilla_por_celda.png`, `contencion_rejilla.png`, `pendiente_rejilla.png`);
  - `figuras_presentes(carpeta) -> list[Path]` (los PNG propios que existen, ordenados; `[]` si la carpeta no existe);
  - privadas `_pyplot()`, `_ejes(ax, titulo, x, y)`, `_coma(valor, decimales)`, `_rho(valor)`,
    `_guardar(plt, fig, destino, titulo) -> Path`;
  - `main()`: tras escribir el JSON lo lee con `leer_resultados(ruta)` y, salvo `--sin-figuras`,
    llama a `figuras(resultados, salida)` e imprime `figura: <ruta>` por cada una.
  - Todo PNG mide 2700 × 1650 píxeles (9 × 5,5 pulgadas a 300 DPI) y lleva su título —con
    «simulación semisintética» y, si es de una celda, el nombre de la celda— también en el
    metadato `Title` del PNG (`PIL.Image.open(ruta).info["Title"]`).

**Notas para quien ejecuta:**
- `destino` es la ruta del FICHERO PNG (como en `scripts/diagnostico_curvas.py`); `carpeta` es una carpeta.
- `matplotlib` y `pillow` ya están en el venv: no hay que instalar nada ni usar la red. El extra
  `figuras` solo se DECLARA en `pyproject.toml`.
- El analizador de argumentos de `main()` que dejó la tarea 4 YA declara `--sin-figuras`,
  `--analisis` y `--solo-documento`; esta tarea no añade opciones: le da efecto a `--sin-figuras`
  (y le pone texto de ayuda). `--analisis` y `--solo-documento` son de la tarea 6.
- Las órdenes se corren desde la raíz del repo. `pyproject.toml` tiene fines de línea CRLF en el
  árbol de trabajo: edítalo con la herramienta de edición (no lo reescribas entero).

- [ ] **Paso 1: Escribir las pruebas que fallan**

En `tests/test_validar_combinacion.py` hay que hacer dos cosas.

(a) La prueba `test_main_escribe_los_resultados_donde_se_le_dice` (de la tarea 4) llama a
`main()` con un `calcular` falso que devuelve `"celdas": []`; desde esta tarea `main()` dibujaría
con ese diccionario. Se le añade `--sin-figuras`. Busca exactamente:

```python
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert llamadas == [(3, 1)]
```

y sustitúyelo por:

```python
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path),
                         "--sin-figuras"]) == 0
    assert llamadas == [(3, 1)]
```

(b) Añade AL FINAL del fichero (tras la última línea de
`test_main_escribe_los_resultados_donde_se_le_dice`, dejando dos líneas en blanco):

```python
# --------------------------------------------------------------------------
# Las figuras (tarea 5). Cada prueba que dibuja pide matplotlib: sin el extra
# `figuras` instalado se saltan, y las del calculo siguen corriendo.
# --------------------------------------------------------------------------
NOMBRES_MINIMOS = ["fiabilidad_0a.png", "fiabilidad_r1-030_r0-030.png",
                   "horquilla_por_celda.png", "contencion_rejilla.png",
                   "pendiente_rejilla.png"]


def test_el_slug_de_celda(validar, resultados_minimos):
    assert [validar.slug_de_celda(c) for c in resultados_minimos["celdas"]] == [
        "0a", "r1-000_r0-030", "r1-030_r0-000", "r1-030_r0-030"]
    assert validar.slug_de_celda(
        {"nombre": "(0,15; 0,6)", "rho1": 0.15, "rho0": 0.6}) == "r1-015_r0-060"
    assert validar.FIGURAS_GLOBALES == (
        "horquilla_por_celda", "contencion_rejilla", "pendiente_rejilla")
    assert validar.PREFIJO_FIABILIDAD == "fiabilidad_"
    assert validar.DPI == 300


def test_las_figuras_salen_con_su_nombre_a_300_dpi_y_con_el_rotulo(
        validar, resultados_minimos, tmp_path):
    pytest.importorskip("matplotlib")
    from PIL import Image
    rutas = validar.figuras(resultados_minimos, tmp_path / "figuras")
    assert [r.name for r in rutas] == NOMBRES_MINIMOS
    assert all(r.parent == tmp_path / "figuras" for r in rutas)
    for ruta in rutas:
        assert ruta.stat().st_size > 10_000
        with Image.open(ruta) as imagen:
            assert imagen.format == "PNG"
            assert imagen.size == (2700, 1650)            # 9 x 5,5 pulgadas a 300 DPI
            assert imagen.info["dpi"] == pytest.approx((300, 300), abs=1)
            assert "simulación semisintética" in imagen.info["Title"]
    titulos = {}
    for ruta in rutas:
        with Image.open(ruta) as imagen:
            titulos[ruta.name] = imagen.info["Title"]
    assert "0A" in titulos["fiabilidad_0a.png"]
    assert "(0,3; 0,3)" in titulos["fiabilidad_r1-030_r0-030.png"]
    assert validar.figuras_presentes(tmp_path / "figuras") == sorted(rutas)


def test_cada_figura_se_puede_dibujar_por_separado(validar, resultados_minimos, tmp_path):
    pytest.importorskip("matplotlib")
    celda = resultados_minimos["celdas"][3]
    destino = tmp_path / "una.png"
    assert validar.figura_fiabilidad(celda, destino) == destino
    assert validar.figura_horquilla(resultados_minimos, tmp_path / "dos.png").is_file()
    assert validar.figura_rejilla(resultados_minimos, tmp_path / "tres.png",
                                  "contencion").is_file()
    assert validar.figura_rejilla(resultados_minimos, tmp_path / "cuatro.png",
                                  "pendiente").is_file()
    assert destino.stat().st_size > 10_000
    with pytest.raises(ValueError, match="contencion"):
        validar.figura_rejilla(resultados_minimos, tmp_path / "cinco.png", "auc")
    assert not (tmp_path / "cinco.png").exists()


def test_las_figuras_borran_las_propias_rancias_y_respetan_las_ajenas(
        validar, resultados_minimos, tmp_path):
    pytest.importorskip("matplotlib")
    rancia = tmp_path / "fiabilidad_viejo.png"
    rancia.write_bytes(b"rancio")
    ajena = tmp_path / "latencia.png"
    ajena.write_bytes(b"ajeno")
    otra = tmp_path / "resultados_simulacion.json"
    otra.write_text("{}", encoding="utf-8")
    assert validar.figuras_presentes(tmp_path) == [rancia]
    rutas = validar.figuras(resultados_minimos, tmp_path)
    assert not rancia.exists()
    assert ajena.read_bytes() == b"ajeno"
    assert otra.read_text(encoding="utf-8") == "{}"
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted(
        NOMBRES_MINIMOS + ["latencia.png"])
    assert validar.figuras_presentes(tmp_path) == sorted(rutas)
    assert validar.figuras_presentes(tmp_path / "no_existe") == []


def test_main_dibuja_las_figuras_leyendo_el_json(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys):
    pytest.importorskip("matplotlib")
    leidos = []
    leer = validar.leer_resultados

    def leer_espia(ruta):
        leidos.append(ruta)
        return leer(ruta)

    monkeypatch.setattr(validar, "calcular", lambda replicas, procesos: resultados_minimos)
    monkeypatch.setattr(validar, "leer_resultados", leer_espia)
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert leidos == [tmp_path / "resultados_simulacion.json"]
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted(NOMBRES_MINIMOS)
    salida = capsys.readouterr().out
    assert [linea[len("figura: "):] for linea in salida.splitlines()
            if linea.startswith("figura: ")] == [str(tmp_path / n) for n in NOMBRES_MINIMOS]


def test_main_sin_figuras_no_dibuja_nada(validar, tmp_path, capsys):
    """La unica prueba que corre la rejilla entera (25 celdas, sin bootstrap)."""
    assert validar.main(["--replicas", "0", "--procesos", "1", "--salida", str(tmp_path),
                         "--sin-figuras"]) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["resultados_simulacion.json"]
    assert len(validar.leer_resultados(tmp_path / "resultados_simulacion.json")["celdas"]) == 25
    assert "figura:" not in capsys.readouterr().out
```

- [ ] **Paso 2: Correr las pruebas y ver que fallan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_validar_combinacion.py`

Esperado: `5 failed, 8 passed`. Fallan las cinco que dibujan o usan lo nuevo:

```
E       AttributeError: module 'validar_combinacion' has no attribute 'slug_de_celda'
E       AttributeError: module 'validar_combinacion' has no attribute 'figuras'
E       AttributeError: module 'validar_combinacion' has no attribute 'figura_fiabilidad'
E       AttributeError: module 'validar_combinacion' has no attribute 'figuras_presentes'
E       AssertionError: assert [] == [WindowsPath(...lacion.json')]
FAILED tests/test_validar_combinacion.py::test_el_slug_de_celda - AttributeEr...
FAILED tests/test_validar_combinacion.py::test_las_figuras_salen_con_su_nombre_a_300_dpi_y_con_el_rotulo
FAILED tests/test_validar_combinacion.py::test_cada_figura_se_puede_dibujar_por_separado
FAILED tests/test_validar_combinacion.py::test_las_figuras_borran_las_propias_rancias_y_respetan_las_ajenas
FAILED tests/test_validar_combinacion.py::test_main_dibuja_las_figuras_leyendo_el_json
5 failed, 8 passed
```

`test_main_sin_figuras_no_dibuja_nada` y la prueba modificada en (a) PASAN ya en este paso: el
`main()` de la tarea 4 acepta `--sin-figuras` y todavía no dibuja. Es lo esperado: esas dos
pruebas guardan el comportamiento, no lo estrenan. La última de las cinco falla porque `main()`
aún no lee el JSON que acaba de escribir.

- [ ] **Paso 3: Declarar el extra `figuras`**

En `pyproject.toml`, busca exactamente:

```toml
dev = ["pytest>=8", "pytest-asyncio", "httpx", "psycopg[binary]==3.2.3"]
```

y sustitúyelo por:

```toml
dev = ["pytest>=8", "pytest-asyncio", "httpx", "psycopg[binary]==3.2.3"]
figuras = ["matplotlib>=3.9"]
```

(`matplotlib` NO va en `dependencies`: el Dockerfile instala el paquete entero.)

- [ ] **Paso 4: Escribir las figuras**

En `scripts/validar_combinacion.py`, inserta este bloque ENTRE la función `leer_resultados` y
`def main(argv=None) -> int:` (con dos líneas en blanco antes y dos después):

```python
# ---------------------------------------------------------------------------
# LAS FIGURAS
#
# Se dibujan LEYENDO el diccionario de resultados_simulacion.json, a 300 DPI y
# con el estilo de scripts/diagnostico_curvas.py. matplotlib se importa DENTRO
# de las funciones, y con el motor «Agg» (sin ventana), para que el calculo se
# pueda correr -y probar- sin tenerlo instalado: es el extra `figuras` del
# pyproject, no una dependencia del paquete.
#
# Los colores salen de una paleta comprobada para daltonismo; ademas cada
# modelo lleva su marca, para que la identidad no dependa solo del color.
# ---------------------------------------------------------------------------
DPI = 300
TINTA = "#0b0b0b"
COLOR_DIAGONAL = "#7a7974"
COLOR_MODELO = {"imagen": "#2a78d6", "clinica": "#eb6834",
                "independencia": "#1baf7a", "conservador": "#4a3aa7"}
MARCA_MODELO = {"imagen": "o", "clinica": "s", "independencia": "^", "conservador": "D"}
NOMBRE_MODELO = {"imagen": "imagen sola", "clinica": "clínica sola",
                 "independencia": "combinación por independencia",
                 "conservador": "combinación conservadora"}
# Las tres fracciones de la horquilla, en el orden del eje de λ: por debajo de
# 0 (mas alla del extremo conservador), dentro, y por encima de 1.
TRAMOS = (("bajo", "por el lado conservador (λ < 0)", "#2a78d6"),
          ("contencion", "dentro de la horquilla", "#c9c8c3"),
          ("sobre", "más allá de la independencia (λ > 1)", "#e34948"))
LADOS = (("a_favor", "imagen a favor (RV ≥ 1)"),
         ("en_contra", "imagen en contra (RV < 1)"))
RAMPA_AZUL = ("#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
RAMPA_DIVERGENTE = ("#e34948", "#f0efec", "#2a78d6")
FIGURAS_GLOBALES = ("horquilla_por_celda", "contencion_rejilla", "pendiente_rejilla")
PREFIJO_FIABILIDAD = "fiabilidad_"
REJILLAS = ("contencion", "pendiente")


def _pyplot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _ejes(ax, titulo, x, y):
    ax.set_title(titulo, fontsize=12, fontweight="bold")
    ax.set_xlabel(x, fontsize=10)
    ax.set_ylabel(y, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=9)


def _coma(valor, decimales: int) -> str:
    """La cifra con coma decimal; «n/d» si no hay cifra."""
    if valor is None or valor != valor:
        return "n/d"
    return f"{valor:.{decimales}f}".replace(".", ",")


def _rho(valor) -> str:
    return f"{valor:g}".replace(".", ",")


def _guardar(plt, fig, destino, titulo) -> Path:
    """300 DPI, y el titulo -con su rotulo- tambien en los metadatos del PNG."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=DPI, metadata={"Title": titulo})
    plt.close(fig)
    return destino


def slug_de_celda(celda: dict) -> str:
    """`0a` para 0A; `r1-030_r0-000` para el resto (ρ × 100, tres cifras)."""
    if celda["nombre"] == "0A":
        return "0a"
    return f"r1-{round(celda['rho1'] * 100):03d}_r0-{round(celda['rho0'] * 100):03d}"


def celdas_con_figura(resultados: dict) -> list:
    """0A y las destacadas, en el orden de la rejilla."""
    return [c for c in resultados["celdas"] if c["nombre"] == "0A" or c["destacada"]]


def figura_fiabilidad(celda: dict, destino) -> Path:
    """La curva de fiabilidad por deciles de los cuatro modelos de una celda.

    La ECE va en la leyenda AL LADO de su suelo: sola no dice nada."""
    plt = _pyplot()
    from matplotlib.ticker import FuncFormatter
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot([0, 1], [0, 1], "--", color=COLOR_DIAGONAL, linewidth=1.2,
            label="calibración perfecta")
    for modelo in simulacion.MODELOS:
        m = celda["modelos"][modelo]
        curva = [b for b in m["fiabilidad"]
                 if b["p_media"] is not None and b["observada"] is not None]
        ax.plot([b["p_media"] for b in curva], [b["observada"] for b in curva],
                "-" + MARCA_MODELO[modelo], color=COLOR_MODELO[modelo], linewidth=1.6,
                markersize=5, markeredgecolor="white", markeredgewidth=0.6,
                label=f"{NOMBRE_MODELO[modelo]} — ECE {_coma(m['ece'], 3)}"
                      f" (suelo {_coma(m['suelo']['media'], 3)})")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    for eje in (ax.xaxis, ax.yaxis):
        eje.set_major_formatter(FuncFormatter(lambda v, _: _coma(v, 1)))
    titulo = f"Fiabilidad por deciles — celda {celda['nombre']} — {ROTULO}"
    _ejes(ax, titulo, "probabilidad predicha (media del decil)", "frecuencia observada")
    ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout()
    return _guardar(plt, fig, destino, titulo)


def figura_horquilla(resultados: dict, destino) -> Path:
    """Donde queda el oraculo respecto de la horquilla, en 0A y las destacadas.

    Un panel por lado de la imagen; en cada celda, una barra apilada con las
    tres fracciones de los casos concordantes. No es una cobertura."""
    plt = _pyplot()
    from matplotlib.patches import Patch
    celdas = celdas_con_figura(resultados)
    posiciones = list(range(len(celdas)))
    fig, paneles = plt.subplots(1, 2, figsize=(9, 5.5), sharey=True)
    for ax, (lado, rotulo) in zip(paneles, LADOS):
        izquierda = [0.0] * len(celdas)
        for clave, _, color in TRAMOS:
            anchos = [100.0 * (c["horquilla"][lado][clave] or 0.0) for c in celdas]
            ax.barh(posiciones, anchos, left=izquierda, height=0.68, color=color,
                    edgecolor="white", linewidth=1.2)
            for y, (x0, ancho) in enumerate(zip(izquierda, anchos)):
                if ancho >= 12.0:
                    ax.text(x0 + ancho / 2, y, f"{_coma(ancho, 0)} %", ha="center",
                            va="center", fontsize=8,
                            color=TINTA if clave == "contencion" else "white")
            izquierda = [a + b for a, b in zip(izquierda, anchos)]
        _ejes(ax, rotulo, "% de los casos concordantes", "")
        ax.set_title(rotulo, fontsize=10)
        ax.set_xlim(0, 100)
        ax.grid(False, axis="y")
    paneles[0].set_yticks(posiciones)
    paneles[0].set_yticklabels([c["nombre"] for c in celdas], fontsize=9)
    paneles[0].set_ylabel("celda (ρ1; ρ0)", fontsize=10)
    paneles[0].invert_yaxis()
    titulo = f"El oráculo frente a la horquilla, por celda y lado — {ROTULO}"
    fig.suptitle(titulo, fontsize=12, fontweight="bold")
    fig.legend(handles=[Patch(facecolor=color, label=nombre) for _, nombre, color in TRAMOS],
               loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return _guardar(plt, fig, destino, titulo)


def figura_rejilla(resultados: dict, destino, que: str) -> Path:
    """Mapa de calor ρ1 × ρ0 con la cifra escrita en cada casilla.

    `contencion`: la de `horquilla.todos`, en un solo tono. `pendiente`: la del
    modelo de independencia, en dos tonos alrededor de 1 (por debajo exagera;
    por encima se queda corta)."""
    if que not in REJILLAS:
        raise ValueError(f"que debe ser uno de {REJILLAS}: {que!r}")
    plt = _pyplot()
    from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm
    from matplotlib.ticker import FuncFormatter
    rejilla = [float(r) for r in resultados["parametros"]["rejilla"]]
    lugar = {round(r, 6): i for i, r in enumerate(rejilla)}
    numeros = [[float("nan")] * len(rejilla) for _ in rejilla]
    for c in resultados["celdas"]:
        valor = (c["horquilla"]["todos"]["contencion"] if que == "contencion"
                 else c["modelos"]["independencia"]["pendiente"])
        if valor is not None:
            numeros[lugar[round(c["rho1"], 6)]][lugar[round(c["rho0"], 6)]] = (
                100.0 * valor if que == "contencion" else float(valor))
    if que == "contencion":
        mapa = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
        norma = Normalize(vmin=0.0, vmax=100.0)
        decimales, unidad, centro, corte = 1, " %", 0.0, 0.5
        titulo = f"Contención del oráculo en la horquilla, por celda — {ROTULO}"
        barra = "contención (% de los casos concordantes)"
    else:
        presentes = [v for fila in numeros for v in fila if v == v]
        desvio = max([abs(v - 1.0) for v in presentes] + [0.05])
        mapa = LinearSegmentedColormap.from_list("divergente", RAMPA_DIVERGENTE)
        norma = TwoSlopeNorm(vcenter=1.0, vmin=1.0 - desvio, vmax=1.0 + desvio)
        decimales, unidad, centro, corte = 2, "", 0.5, 0.3
        titulo = f"Pendiente de la independencia, por celda — {ROTULO}"
        barra = "pendiente de calibración (< 1 exagera; > 1 se queda corta)"
    mapa = mapa.with_extremes(bad="#f0efec")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    imagen = ax.imshow(numeros, cmap=mapa, norm=norma, origin="lower", aspect="auto")
    for i, fila in enumerate(numeros):
        for j, v in enumerate(fila):
            oscuro = v == v and abs(float(norma(v)) - centro) > corte
            ax.text(j, i, _coma(v, decimales) + (unidad if v == v else ""),
                    ha="center", va="center", fontsize=10 if len(rejilla) <= 5 else 8,
                    color="white" if oscuro else TINTA)
    _ejes(ax, titulo, "ρ0 (dependencia entre los casos sin neumonía)",
          "ρ1 (dependencia entre los casos con neumonía)")
    ax.grid(False)
    ax.set_xticks(range(len(rejilla)))
    ax.set_xticklabels([_rho(r) for r in rejilla])
    ax.set_yticks(range(len(rejilla)))
    ax.set_yticklabels([_rho(r) for r in rejilla])
    cifras = 0 if que == "contencion" else 2
    cbar = fig.colorbar(imagen, ax=ax, format=FuncFormatter(lambda v, _: _coma(v, cifras)))
    cbar.set_label(barra, fontsize=10)
    fig.tight_layout()
    return _guardar(plt, fig, destino, titulo)


def figuras_presentes(carpeta) -> list[Path]:
    """Los PNG PROPIOS que hay en la carpeta, ordenados: los `fiabilidad_*.png`
    y los tres globales. Cualquier otro PNG es de otro y no se toca."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    globales = {f"{nombre}.png" for nombre in FIGURAS_GLOBALES}
    return sorted(p for p in carpeta.glob("*.png")
                  if p.name.startswith(PREFIJO_FIABILIDAD) or p.name in globales)


def figuras(resultados: dict, carpeta) -> list[Path]:
    """Dibuja todas las figuras y devuelve sus rutas en orden.

    Borra antes las propias que hubiera: si cambian las celdas destacadas, una
    `fiabilidad_*.png` de la corrida anterior quedaria en la carpeta con cifras
    que ya no son las del JSON."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    for rancia in figuras_presentes(carpeta):
        rancia.unlink()
    rutas = [figura_fiabilidad(c, carpeta / f"{PREFIJO_FIABILIDAD}{slug_de_celda(c)}.png")
             for c in celdas_con_figura(resultados)]
    rutas.append(figura_horquilla(resultados, carpeta / "horquilla_por_celda.png"))
    rutas.append(figura_rejilla(resultados, carpeta / "contencion_rejilla.png", "contencion"))
    rutas.append(figura_rejilla(resultados, carpeta / "pendiente_rejilla.png", "pendiente"))
    return rutas
```

- [ ] **Paso 5: Conectar las figuras en `main()`**

En el mismo fichero, dentro de `main()`, busca exactamente:

```python
    p.add_argument("--sin-figuras", action="store_true")
```

y sustitúyelo por:

```python
    p.add_argument("--sin-figuras", action="store_true",
                   help="no dibuja: deja las figuras que hubiera como estaban")
```

Y busca exactamente:

```python
        raise SystemExit(f"no existe {ruta}: corre primero sin --solo-documento")
    return 0
```

y sustitúyelo por:

```python
        raise SystemExit(f"no existe {ruta}: corre primero sin --solo-documento")
    resultados = leer_resultados(ruta)
    if not args.sin_figuras:
        for figura in figuras(resultados, salida):
            print(f"figura: {figura}")
    return 0
```

- [ ] **Paso 6: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_validar_combinacion.py`

Esperado: `13 passed`, sin avisos (tarda cerca de medio minuto). Si aparece un `PendingDeprecationWarning` de
`set_bad`, el bloque no se copió bien: el código usa `mapa.with_extremes(bad=...)`.

- [ ] **Paso 7: Correr los vecinos**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_validar_combinacion.py tests/test_metricas.py tests/test_simulacion.py tests/test_comparar_corridas.py tests/test_arquitectura.py`

Esperado: ningún fallo ni error.

- [ ] **Paso 8: Dibujar con la rejilla completa y MIRAR las figuras**

Las pruebas comprueban nombres, tamaño, DPI y rótulo; que el texto no se solape solo se ve
mirando. Corre el script con pocas réplicas y con la salida FUERA del repo (en esta tarea no se
versiona ningún resultado):

Run: `C:/venv-copiloto/Scripts/python.exe -B scripts/validar_combinacion.py --replicas 20 --salida <CARPETA_TEMPORAL>`

Esperado (menos de un minuto): una línea `resultados: …resultados_simulacion.json` y diez líneas `figura: …`,
en este orden: `fiabilidad_0a.png`, `fiabilidad_r1-000_r0-030.png`, `fiabilidad_r1-000_r0-060.png`,
`fiabilidad_r1-030_r0-000.png`, `fiabilidad_r1-030_r0-030.png`, `fiabilidad_r1-060_r0-000.png`,
`fiabilidad_r1-060_r0-060.png`, `horquilla_por_celda.png`, `contencion_rejilla.png`,
`pendiente_rejilla.png`.

Abre al menos `fiabilidad_r1-060_r0-060.png`, `horquilla_por_celda.png`, `contencion_rejilla.png`
y `pendiente_rejilla.png` y comprueba:
- el título cabe entero y acaba en «— simulación semisintética» (los de fiabilidad llevan además «celda (0,6; 0,6)»);
- fiabilidad: la leyenda (arriba a la izquierda, con la ECE al lado de su suelo) no tapa ningún punto; las marcas de los ejes llevan coma («0,2»);
- horquilla: siete barras por panel, con 0A arriba y al 100 % en gris; los porcentajes escritos dentro de los tramos de 12 % o más; la leyenda de los tres tramos debajo, sin pisar el rótulo del eje;
- rejillas: 25 casillas con su cifra («70,7 %», «0,79»), con ρ1 = 0 abajo y ρ0 = 0 a la izquierda; la barra de color de la pendiente tiene el gris en 1,00.

No copies nada de `<CARPETA_TEMPORAL>` al repo.

- [ ] **Paso 9: Commit**

```bash
git add pyproject.toml scripts/validar_combinacion.py tests/test_validar_combinacion.py
git commit -m "feat(validacion): las figuras de la simulacion, a 300 DPI y desde el JSON (SP5-B1 T5)" -m "Fiabilidad por deciles de 0A y las destacadas, la horquilla por celda y lado, y los mapas de contencion y de pendiente. Se dibujan leyendo resultados_simulacion.json; matplotlib es el extra figuras y solo se importa dentro de las funciones. Todo titulo lleva el rotulo de simulacion semisintetica." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 6: El documento de análisis

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/informe.py`
- Modificar: `scripts/validar_combinacion.py` (el `import` del paquete, un bloque nuevo «EL DOCUMENTO» antes de `main()`, y dos líneas al final de `main()`)
- Prueba: `tests/test_informe.py` (nuevo, 20 pruebas)
- Prueba: `tests/test_validar_combinacion.py` (una fixture `autouse` al principio, un cambio en una prueba de la tarea 4 y cuatro pruebas nuevas al final)

**Interfaces:**
- Consume: el diccionario `resultados` (la estructura de `resultados_simulacion.json`, entera:
  `rotulo`, `advertencia`, `insumos`, `parametros`, `imagen_sola` y `celdas`, con `intervalos`,
  `sensibilidad_al_previo` y `optimismo_de_la_derivacion` donde los haya); del script,
  `leer_resultados(ruta) -> dict`, `escribir_resultados`, `calcular`, `figuras(resultados, carpeta) -> list[Path]`,
  `figuras_presentes(carpeta) -> list[Path]`, `slug_de_celda(celda) -> str`, `ANALISIS`, `NOMBRE_RESULTADOS`;
  las fixtures de sesión `validar` y `resultados_minimos` de `tests/conftest.py`.
- Produce, en `copiloto_triaje.validacion.informe` (puro: sin ficheros, sin matplotlib, sin numpy):
  - `redactar(resultados: dict, figuras: dict | None = None) -> str`: el Markdown completo, acabado en un
    solo salto de línea. `figuras` es `{nombre_sin_extension: enlace_relativo_desde_el_documento}`.
  - `numero(x, decimales: int = 3, signo: bool = False) -> str` (coma decimal, espacio en los millares,
    «−» tipográfico, «n/d» si falta la cifra), `porcentaje(x, decimales: int = 1) -> str` («70,7 %»),
    `entero(n) -> str` («3 811»), `rho(x) -> str` («0,15»), `huella(sha256: str) -> str` (12 caracteres).
  - constantes `TITULO`, `GUION`, `GENERADOR`, `RESULTADOS`, `PRUEBA_0A`, `SIN_CIFRA = "n/d"`, `MENOS = "−"`,
    `HUELLA = 12`, `RHO_EXTREMO = 0.6`, `MODELOS`, `COMBINADOS`, `LADOS`, `LADOS_DE_LA_IMAGEN`, `METRICAS`,
    `PAREADAS`, `PREFIJO_FIABILIDAD`, `FIGURAS_GLOBALES`, `EJES`.
- Produce, en `scripts/validar_combinacion.py`:
  - `escribir_analisis(resultados: dict, figuras: list, ruta) -> Path` (crea la carpeta, UTF-8, LF;
    enlaces con `os.path.relpath` desde la carpeta del documento y barras `/`);
  - `main()`: tras las figuras escribe SIEMPRE el análisis en `--analisis` con las figuras que haya en
    `--salida` (`figuras_presentes`) e imprime `análisis: <ruta>`.

**Notas para quien ejecuta:**
- El analizador de argumentos de `main()` YA declara `--analisis` y `--solo-documento`, y `main()` ya
  sale con `SystemExit` si se pide `--solo-documento` y no existe el JSON (lo dejó la tarea 4). Esta
  tarea no añade opciones: le da efecto a `--analisis`.
- Desde esta tarea `main()` escribe un documento. La fixture `autouse` del paso 5 desvía `ANALISIS` a
  una carpeta temporal en TODAS las pruebas de `tests/test_validar_combinacion.py`: sin ella, las
  pruebas de `main()` de las tareas 4 y 5 escribirían `docs/validacion-semisintetica-sp5.md` en el repo.
- En esta tarea NO se versiona ningún resultado: ni el JSON, ni las figuras, ni el documento. El paso
  10 genera el documento FUERA del repo, para leerlo.
- `informe.py` lleva líneas con tres acentos graves dentro de cadenas; por eso su bloque va entre
  cercas de cuatro. El fichero empieza en `# -*- coding: utf-8 -*-` y acaba en la línea de
  `return "\n".join(...)`.
- Los ficheros con barras invertidas (`"\n"`, `b"\r"`) se escriben con la herramienta de escritura o
  de edición, no con un heredoc de la consola: la consola de esta máquina interpreta `\r` y `\n`.
- Las órdenes se corren desde la raíz del repo.

- [ ] **Paso 1: Escribir las pruebas del documento, que fallan**

Crea `tests/test_informe.py` con este contenido:

```python
"""validacion/informe.py: el documento de analisis, generado desde el JSON."""
import copy
import pathlib
import re

import pytest

from copiloto_triaje.validacion import informe

SECCIONES = [
    "Insumos y parámetros",
    "La imagen sola",
    "Escenario 0A: la aritmética",
    "Dependencia entre clínica e imagen",
    "La horquilla frente al oráculo",
    "Cuánto de su evidencia conserva la puntuación",
    "La rejilla completa",
    "Sensibilidad al previo",
    "0C: optimismo de la derivación (cálculo, no experimento)",
    "Lectura de los resultados",
    "Lo que esta simulación puede afirmar y lo que no",
    "Figuras",
    "Cómo se reproduce",
]


@pytest.fixture(scope="module")
def texto(resultados_minimos):
    return informe.redactar(resultados_minimos)


def _seccion(documento: str, titulo: str) -> str:
    """El cuerpo de la seccion `## titulo`, hasta la siguiente."""
    partes = documento.split(f"\n## {titulo}\n")
    assert len(partes) == 2, titulo
    return partes[1].split("\n## ")[0]


def test_los_formatos():
    assert informe.numero(0.70712, 3) == "0,707"
    assert informe.numero(-0.5, 2) == "−0,50"
    assert informe.numero(0.5, 2, signo=True) == "+0,50"
    assert informe.numero(-1.8e-17, 3) == "0,000"          # ni «-0,000» ni «+0,000»
    assert informe.numero(-1.8e-17, 3, signo=True) == "0,000"
    assert informe.numero(None, 3) == "n/d"
    assert informe.numero(float("nan"), 3) == "n/d"
    assert informe.numero(float("inf"), 3) == "n/d"
    assert informe.numero(1054.66, 1) == "1 054,7"
    assert informe.porcentaje(0.70712) == "70,7 %"
    assert informe.porcentaje(1.0) == "100,0 %"
    assert informe.porcentaje(None) == "n/d"
    assert informe.entero(3811) == "3 811"
    assert informe.entero(844) == "844"
    assert informe.entero(None) == "n/d"
    assert informe.rho(0.0) == "0" and informe.rho(0.15) == "0,15"
    assert informe.huella("414dd3a5cfc58320ac3f69ef090c9dcd") == "414dd3a5cfc5"


def test_el_titulo_lleva_el_rotulo_la_advertencia_y_la_nota(texto, resultados_minimos):
    lineas = texto.splitlines()
    assert lineas[0] == ("# Validación de la combinación de clínica e imagen: "
                         "simulación semisintética (SP5)")
    assert resultados_minimos["rotulo"] in lineas[0]
    assert f"**{resultados_minimos['advertencia']}**" in texto
    cabecera = texto.split("\n## ")[0]
    assert "scripts/validar_combinacion.py" in cabecera
    assert "resultados_simulacion.json" in cabecera
    assert "no se edita a mano" in cabecera
    assert texto.endswith("\n") and not texto.endswith("\n\n")
    assert "\r" not in texto


def test_las_secciones_van_en_el_orden_del_contrato(texto):
    assert [l[3:] for l in texto.splitlines() if l.startswith("## ")] == SECCIONES


def test_aparecen_las_cuatro_celdas(texto, resultados_minimos):
    nombres = [c["nombre"] for c in resultados_minimos["celdas"]]
    assert nombres == ["0A", "(0; 0,3)", "(0,3; 0)", "(0,3; 0,3)"]
    rejilla = _seccion(texto, "La rejilla completa")
    filas = [l for l in rejilla.splitlines() if l.startswith("| ")][2:]
    assert [f.split(" | ")[0][2:] for f in filas] == nombres
    # las tablas con intervalos solo llevan 0A y la destacada
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    assert "| (0,3; 0,3) | todos los concordantes |" in horquilla
    assert "| (0; 0,3) | todos los concordantes |" not in horquilla


def test_las_cifras_salen_formateadas_del_diccionario(texto, resultados_minimos):
    r = resultados_minimos
    insumos = _seccion(texto, "Insumos y parámetros")
    assert "3 811" in insumos and "844" in insumos and "0,2215" in insumos
    for clave in ("crudas_sha256", "pesos_sha256", "calibrador_sha256"):
        assert f"`{r['insumos'][clave][:12]}…`" in insumos
        assert r["insumos"][clave][:13] not in texto
    assert "ε = 0,015" in insumos
    assert "0,1466" in insumos
    imagen = _seccion(texto, "La imagen sola")
    for clave, decimales in (("auc", 3), ("brier", 3), ("pendiente", 2),
                             ("intercepto", 3), ("ece", 3)):
        assert informe.numero(r["imagen_sola"][clave], decimales) in imagen
    assert informe.numero(r["imagen_sola"]["suelo"]["p95"], 3) in imagen
    celda = r["celdas"][3]
    li, ls = celda["intervalos"]["horquilla.todos.contencion"]
    esperado = (f"{informe.porcentaje(celda['horquilla']['todos']['contencion'])} "
                f"(IC 95 %: {informe.numero(100 * li, 1)} a {informe.numero(100 * ls, 1)})")
    assert esperado in _seccion(texto, "La horquilla frente al oráculo")
    li, ls = celda["intervalos"]["pareadas.independencia.auc"]
    esperado = (f"{informe.numero(celda['pareadas']['independencia']['auc'], 3, signo=True)} "
                f"(IC 95 %: {informe.numero(li, 3, signo=True)} a "
                f"{informe.numero(ls, 3, signo=True)})")
    assert esperado in _seccion(texto, "Dependencia entre clínica e imagen")
    cero = _seccion(texto, "Escenario 0A: la aritmética")
    assert "tests/test_validacion_0a.py" in cero
    assert "100,0 %" in cero
    sensibilidad = _seccion(texto, "Sensibilidad al previo")
    s = celda["sensibilidad_al_previo"]
    assert informe.numero(s["previo"], 4) in sensibilidad
    assert informe.numero(s["modelos"]["independencia"]["intercepto"], 3, signo=True) in sensibilidad
    assert "intermedia→baja" in sensibilidad
    assert "El AUC no cambia" in sensibilidad
    assert "no recomienda configurar el despliegue" in sensibilidad
    optimismo = _seccion(texto, "0C: optimismo de la derivación (cálculo, no experimento)")
    assert "17,50" in optimismo and "8,33" in optimismo and "+0,74" in optimismo
    assert "cálculo, no un experimento" in optimismo


def test_cambiar_una_cifra_del_diccionario_cambia_el_texto(texto, resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    vieja = informe.numero(resultados_minimos["imagen_sola"]["auc"], 3)
    assert vieja in _seccion(texto, "La imagen sola")
    otro["imagen_sola"]["auc"] = 0.1234
    otro["insumos"]["placas"] = 9876
    otro["parametros"]["epsilon"] = 0.025
    otro["parametros"]["hipotesis_contencion"] = 0.8
    for celda in otro["celdas"]:
        celda["hipotesis"]["umbral"] = 0.8
    nuevo = informe.redactar(otro)
    assert nuevo != texto
    assert "0,123" in _seccion(nuevo, "La imagen sola")
    assert vieja not in _seccion(nuevo, "La imagen sola")
    insumos = _seccion(nuevo, "Insumos y parámetros")
    assert "9 876" in insumos and "3 811" not in insumos
    assert "3 811" in _seccion(texto, "Insumos y parámetros")
    assert "ε = 0,025" in nuevo and "ε = 0,015" not in nuevo
    assert "ε = 0,015" in texto
    assert "≥ 80 %" in nuevo and "90 %" not in nuevo
    assert "≥ 90 %" in texto
    assert informe.redactar(resultados_minimos) == texto      # no toca el diccionario


def test_el_veredicto_sale_de_la_hipotesis_de_cada_celda(texto, resultados_minimos):
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    celda = resultados_minimos["celdas"][3]
    assert celda["hipotesis"]["se_sostiene"] is False
    assert "| (0,3; 0,3) | " in horquilla
    veredictos = {l.split(" | ")[0][2:]: l.split(" | ")[-1].rstrip(" |")
                  for l in horquilla.splitlines() if l.endswith("se sostiene |")}
    assert veredictos == {"0A": "se sostiene", "(0; 0,3)": "no se sostiene",
                          "(0,3; 0)": "no se sostiene", "(0,3; 0,3)": "no se sostiene"}
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["hipotesis"]["se_sostiene"] = True
    nuevo = _seccion(informe.redactar(otro), "La horquilla frente al oráculo")
    assert [l for l in nuevo.splitlines()
            if l.startswith("| (0,3; 0,3) | ") and l.endswith("| se sostiene |")]


def test_la_lectura_se_genera_desde_las_cifras(texto, resultados_minimos):
    lectura = _seccion(texto, "Lectura de los resultados")
    celda = resultados_minimos["celdas"][3]
    assert celda["modelos"]["independencia"]["pendiente"] < 1
    assert "menor que 1: 1 de 1" in lectura
    assert "Se sostiene en 1 de las 4 celdas de la rejilla: 0A." in lectura
    assert informe.porcentaje(celda["horquilla"]["a_favor"]["bajo"]) in lectura
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["modelos"]["independencia"]["pendiente"] = 1.25
    otro["celdas"][3]["intervalos"]["modelos.independencia.pendiente"] = [1.1, 1.4]
    for celda in otro["celdas"]:
        celda["hipotesis"]["se_sostiene"] = False
    nueva = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "menor que 1: 0 de 1" in nueva
    assert "No se sostiene en ninguna de las 4 celdas de la rejilla." in nueva


def test_la_lectura_cuenta_las_cifras_fuera_de_su_intervalo(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        for ruta, par in celda.get("intervalos", {}).items():
            valor = celda
            for clave in ruta.split("."):
                valor = valor[clave]
            par[0], par[1] = valor - 1.0, valor + 1.0
    total = sum(len(c.get("intervalos", {})) for c in otro["celdas"])
    assert total > 50
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert f"quedan fuera de su intervalo 0 de las {total} cifras que lo llevan" in lectura
    otro["celdas"][3]["intervalos"]["modelos.imagen.auc"] = [0.1, 0.2]
    otro["celdas"][0]["intervalos"]["modelos.imagen.auc"] = [0.99, 0.999]
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert f"quedan fuera de su intervalo 2 de las {total} cifras que lo llevan" in lectura
    assert "de 2 réplicas" in lectura


def test_los_ejes_de_la_lectura_van_en_orden_fijo(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"][1:]:
        celda["destacada"] = True
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    ejes = [l for l in lectura.splitlines() if l.startswith("- **Dependencia")]
    assert ejes == ["- **Dependencia simétrica (ρ1 = ρ0).**",
                    "- **Dependencia solo entre los casos con neumonía (ρ0 = 0).**",
                    "- **Dependencia solo entre los casos sin neumonía (ρ1 = 0).**"]
    celdas = [l.strip()[2:].split(":")[0] for l in lectura.splitlines() if l.startswith("  - ")]
    assert celdas == ["(0,3; 0,3)", "(0,3; 0)", "(0; 0,3)"]


def test_la_cola_mayor_se_lee_de_las_dos_colas(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    lado = otro["celdas"][3]["horquilla"]["a_favor"]
    lado.update(bajo=0.0, sobre=0.25, contencion=0.75)
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert ("con la imagen a favor queda dentro el 75,0 %; la cola mayor es la de más allá "
            "de la independencia (25,0 %, frente a 0,0 % por el lado conservador)") in lectura
    lado.update(bajo=0.0, sobre=0.0, contencion=1.0)
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "con la imagen a favor queda dentro el 100,0 %; ninguna cola tiene casos" in lectura


def test_los_enlaces_de_las_figuras_recibidas_y_ninguno_mas(resultados_minimos, validar):
    sin = informe.redactar(resultados_minimos)
    assert "![" not in sin and ".png" not in sin
    assert "sin figuras" in _seccion(sin, "Figuras")
    figuras = {"fiabilidad_r1-030_r0-030": "validacion-semisintetica/fiabilidad_r1-030_r0-030.png",
               "contencion_rejilla": "validacion-semisintetica/contencion_rejilla.png"}
    con = informe.redactar(resultados_minimos, figuras)
    enlaces = re.findall(r"!\[([^\]]*)\]\(([^)]*)\)", con)
    assert [e[1] for e in enlaces] == [
        "validacion-semisintetica/fiabilidad_r1-030_r0-030.png",
        "validacion-semisintetica/contencion_rejilla.png"]
    assert "(0,3; 0,3)" in enlaces[0][0]
    assert all("simulación semisintética" in e[0] for e in enlaces)
    assert con.count(".png") == 2
    assert con.split("\n## Figuras\n")[0] == sin.split("\n## Figuras\n")[0]
    # el nombre de cada figura de fiabilidad es el que le pone el script
    todas = {f"fiabilidad_{validar.slug_de_celda(c)}": f"f/{i}.png"
             for i, c in enumerate(resultados_minimos["celdas"])}
    enlaces = re.findall(r"!\[([^\]]*)\]\(([^)]*)\)", informe.redactar(resultados_minimos, todas))
    assert [e[1] for e in enlaces] == ["f/0.png", "f/1.png", "f/2.png", "f/3.png"]
    assert [c["nombre"] in e[0] for c, e in zip(resultados_minimos["celdas"], enlaces)] == [True] * 4


def test_no_aparecen_nan_none_llaves_ni_puntos_decimales(resultados_minimos):
    figuras = {"horquilla_por_celda": "validacion-semisintetica/horquilla_por_celda.png"}
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["horquilla"]["a_favor"]["lambda"] = {"q1": None, "mediana": None, "q3": None}
    otro["celdas"][3]["discordantes"]["sesgo_mediano"] = float("nan")
    otro["celdas"][3]["intervalos"]["discordantes.sesgo_mediano"] = [float("nan"), float("nan")]
    for documento in (informe.redactar(resultados_minimos, figuras), informe.redactar(otro)):
        assert not re.search(r"\bnan\b", documento, flags=re.IGNORECASE)
        assert "None" not in documento
        assert "{" not in documento and "}" not in documento
        # los «§4.7» son referencias, no cifras
        assert not re.search(r"(?<![§\d.])\d+\.\d", documento)
        assert "-0," not in documento                       # el menos es «−»
    assert "n/d" not in informe.redactar(resultados_minimos)
    assert "n/d (IC 95 %: n/d a n/d)" in informe.redactar(otro)


def test_sin_bootstrap_no_hay_intervalos(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    otro["parametros"]["replicas"] = 0
    for celda in otro["celdas"]:
        celda.pop("intervalos", None)
        celda.pop("replicas", None)
    documento = informe.redactar(otro)
    assert "(IC 95 %:" not in documento
    assert "sin bootstrap" in documento
    assert "(IC 95 %:" in informe.redactar(resultados_minimos)


def test_los_limites_del_spec_estan_escritos(texto):
    limites = _seccion(texto, "Lo que esta simulación puede afirmar y lo que no")
    assert "no mide exactitud clínica" in limites
    assert "las viñetas no son pacientes" in limites
    assert "la exactitud es la publicada y la dependencia es la supuesta" in limites
    assert "**No puede afirmar**" in limites
    assert "reproduce caso a caso la posterior del generador" in limites


def test_la_escala_legible_rotula_las_puntuaciones_poco_informativas(texto, resultados_minimos):
    escala = _seccion(texto, "Cuánto de su evidencia conserva la puntuación")
    assert "### Celda (0,3; 0,3)" in escala
    assert "### Celda (0; 0,3)" not in escala                 # solo las destacadas
    filas = [l for l in escala.splitlines() if l.startswith("| ")]
    assert len([l for l in filas if "poco informativa" in l]) == 4     # k = 2 y 3, dos lados
    assert all(l.startswith(("| 2 |", "| 3 |")) for l in filas if "poco informativa" in l)
    lado = resultados_minimos["celdas"][3]["escala_legible"]["en_contra"]
    assert informe.numero(lado["fraccion_mediana_extremas"], 2) in escala


def test_como_se_reproduce_cita_la_orden_y_las_replicas(texto):
    reproducir = _seccion(texto, "Cómo se reproduce")
    assert "python scripts/validar_combinacion.py --replicas 2" in reproducir
    assert "--solo-documento" in reproducir
    assert "sin los pesos" in reproducir


def test_el_modulo_es_puro():
    fuente = pathlib.Path(informe.__file__).read_text(encoding="utf-8")
    for prohibido in ("matplotlib", "open(", "pathlib", "import os", "numpy", "pandas"):
        assert prohibido not in fuente, prohibido


def test_los_nombres_de_las_figuras_son_los_del_guion(validar):
    """El documento y el guion nombran las figuras por separado (el paquete
    no puede importar el guion): que no se separen."""
    assert [clave for clave, _ in informe.FIGURAS_GLOBALES] == list(validar.FIGURAS_GLOBALES)
    assert informe.PREFIJO_FIABILIDAD == validar.PREFIJO_FIABILIDAD


def test_las_definiciones_del_diseno_que_la_prosa_da_por_fijas_son_las_del_codigo():
    """La prosa del documento escribe cuatro definiciones del diseño, que no
    son resultados y no están en el JSON: el nivel del intervalo (95 %), los
    cortes de banda (20 y 70 %), el umbral de «poco informativa» (0,5) y las
    puntuaciones extremas (k ≤ 1 y k ≥ 4). Si el código las cambia, esta
    prueba falla y hay que cambiar la prosa de `informe.py`."""
    import inspect

    from copiloto_triaje.validacion import categoria, metricas, simulacion
    assert inspect.signature(metricas.percentiles).parameters["alfa"].default == 0.05
    assert [categoria.banda(p) for p in (19, 20, 70, 71)] == [
        "baja", "intermedia", "intermedia", "alta"]
    assert simulacion.POCO_INFORMATIVA == 0.5
    assert simulacion.EXTREMAS == (0, 1, 4, 5)
    assert simulacion.HIPOTESIS_CONTENCION == 0.90
```

- [ ] **Paso 2: Correr las pruebas y ver que fallan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_informe.py`

Esperado: un error de recolección, porque el módulo no existe:

```
E   ImportError: cannot import name 'informe' from 'copiloto_triaje.validacion' (...)
ERROR tests/test_informe.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

- [ ] **Paso 3: Escribir `informe.py`**

Crea `src/copiloto_triaje/validacion/informe.py` con este contenido:

````python
# -*- coding: utf-8 -*-
"""El documento de análisis de la simulación semisintética (spec de SP5 §4.8).

`redactar(resultados, figuras)` devuelve el Markdown del análisis a partir
del diccionario de `resultados_simulacion.json`. Es una función pura: ni lee
ni escribe ficheros, ni dibuja; de eso se ocupa
`scripts/validar_combinacion.py`.

NINGUNA CIFRA SE TECLEA. Todo número del documento sale del diccionario: los
de las tablas y también los de la prosa (placas, prevalencia, réplicas, ε, el
umbral de la hipótesis, los ρ de la rejilla). Las frases de la «Lectura de
los resultados» se componen contando sobre las cifras, de modo que el texto
no puede decir algo que sus tablas no sostengan. Lo único fijo son las
definiciones del diseño: las bandas (< 20 %, 20-70 %, > 70 %), el nivel de
los intervalos (95 %), el corte de «poco informativa» (|ln RV| < 0,5, que
son k = 2 y k = 3; las extremas son k ≤ 1 y k ≥ 4), los valores de λ en los
extremos de la horquilla (0 y 1) y lo que la fila 0A tiene que dar (colas 0,
contención 100 %).

Formato: coma decimal, el menos tipográfico («−»), porcentajes con un
decimal, y «n/d» donde no hay cifra.
"""
from __future__ import annotations

import math

TITULO = "Validación de la combinación de clínica e imagen: simulación semisintética (SP5)"
GUION = "scripts/validar_combinacion.py"
GENERADOR = "src/copiloto_triaje/validacion/informe.py"
RESULTADOS = "resultados_simulacion.json"
PRUEBA_0A = "tests/test_validacion_0a.py"
SIN_CIFRA = "n/d"
MENOS = "−"
HUELLA = 12                  # caracteres de cada sha256 que se imprimen
RHO_EXTREMO = 0.6            # spec §4.5: a partir de aqui, «caso extremo, no plausible»
MODELOS = (("imagen", "imagen sola"), ("clinica", "clínica sola"),
           ("independencia", "combinación, independencia"),
           ("conservador", "combinación, extremo conservador"))
COMBINADOS = MODELOS[2:]
LADOS = (("todos", "todos los concordantes"), ("a_favor", "imagen a favor (RV ≥ 1)"),
         ("en_contra", "imagen en contra (RV < 1)"))
LADOS_DE_LA_IMAGEN = (("a_favor", "con la imagen a favor"),
                      ("en_contra", "con la imagen en contra"))
METRICAS = (("auc", "AUC", 3), ("brier", "Brier", 3), ("pendiente", "pendiente", 2),
            ("intercepto", "intercepto", 3), ("ece", "ECE", 3))
PAREADAS = (("auc", "ΔAUC", 3), ("brier", "ΔBrier", 3), ("pendiente", "Δpendiente", 2))
# Los nombres de las figuras son los que les pone el script (tarea 5).
PREFIJO_FIABILIDAD = "fiabilidad_"
FIGURAS_GLOBALES = (
    ("horquilla_por_celda", "El oráculo frente a la horquilla, por celda y lado"),
    ("contencion_rejilla", "Contención del oráculo en la horquilla, por celda"),
    ("pendiente_rejilla", "Pendiente de la independencia, por celda"),
)


# ---------------------------------------------------------------------------
# Formatos
# ---------------------------------------------------------------------------
def _falta(x) -> bool:
    return x is None or (isinstance(x, float) and not math.isfinite(x))


def numero(x, decimales: int = 3, signo: bool = False) -> str:
    """La cifra con coma decimal y un espacio en los millares; con `signo`,
    las positivas llevan «+». Un valor que se redondea a cero no lleva signo."""
    if _falta(x):
        return SIN_CIFRA
    x = float(x)
    texto = f"{abs(x):,.{decimales}f}"
    nulo = float(texto.replace(",", "")) == 0.0
    texto = texto.replace(",", " ").replace(".", ",")
    if x < 0 and not nulo:
        return MENOS + texto
    if signo and not nulo:
        return "+" + texto
    return texto


def porcentaje(x, decimales: int = 1) -> str:
    if _falta(x):
        return SIN_CIFRA
    return numero(100.0 * float(x), decimales) + " %"


def entero(n) -> str:
    """Con un espacio en los millares: 3 811."""
    if _falta(n):
        return SIN_CIFRA
    return f"{int(n):,}".replace(",", " ")


def rho(x) -> str:
    return f"{float(x):g}".replace(".", ",")


def huella(sha256: str) -> str:
    return str(sha256)[:HUELLA]


def _valor(d: dict, ruta: str):
    for clave in ruta.split("."):
        d = d[clave]
    return d


def _intervalo(celda: dict, ruta: str, formato) -> str:
    """« (IC 95 %: a a b)» si la celda tiene intervalo para esa ruta."""
    par = (celda.get("intervalos") or {}).get(ruta)
    if not par:
        return ""
    return f" (IC 95 %: {formato(par[0])} a {formato(par[1])})"


def _cifra(celda: dict, ruta: str, decimales: int, signo: bool = False) -> str:
    return (numero(_valor(celda, ruta), decimales, signo)
            + _intervalo(celda, ruta, lambda v: numero(v, decimales, signo)))


def _fraccion(celda: dict, ruta: str) -> str:
    """Un porcentaje con su intervalo: «70,7 % (IC 95 %: 69,5 a 72,7)»."""
    return (porcentaje(_valor(celda, ruta))
            + _intervalo(celda, ruta, lambda v: numero(None if _falta(v) else 100.0 * v, 1)))


def _cuartiles(d: dict, decimales: int = 2) -> str:
    """«mediana (q1 a q3)»."""
    if _falta(d["mediana"]):
        return SIN_CIFRA
    return (f"{numero(d['mediana'], decimales)} "
            f"({numero(d['q1'], decimales)} a {numero(d['q3'], decimales)})")


def _tabla(cabeceras, filas, izquierdas: int = 1) -> list:
    """Una tabla de Markdown: las primeras columnas a la izquierda, las
    cifras a la derecha."""
    guia = [":---" if i < izquierdas else "---:" for i in range(len(cabeceras))]
    lineas = ["| " + " | ".join(cabeceras) + " |", "| " + " | ".join(guia) + " |"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return lineas + [""]


def _lista(nombres) -> str:
    """«a, b y c»."""
    nombres = list(nombres)
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _transiciones(bandas: dict) -> str:
    if not bandas["transiciones"]:
        return "ninguna"
    return "; ".join(f"{sentido}: {entero(n)}" for sentido, n in bandas["transiciones"].items())


def _slug(celda: dict) -> str:
    """El de `slug_de_celda` del script: `0a`, `r1-030_r0-000`."""
    if celda["nombre"] == "0A":
        return "0a"
    return f"r1-{round(celda['rho1'] * 100):03d}_r0-{round(celda['rho0'] * 100):03d}"


def _frente_al_suelo(ece, suelo: dict) -> str:
    """La ECE solo se lee al lado de su suelo de ruido."""
    if _falta(ece) or _falta(suelo["p95"]):
        return "no se puede comparar con su suelo"
    if ece <= suelo["p95"]:
        return "no supera el percentil 95 de su suelo: no se distingue del ruido de muestreo"
    return "supera el percentil 95 de su suelo: hay descalibración más allá del ruido de muestreo"


# ---------------------------------------------------------------------------
# Las celdas
# ---------------------------------------------------------------------------
def _cero(resultados: dict):
    for celda in resultados["celdas"]:
        if celda["nombre"] == "0A":
            return celda
    return None


def _destacadas(resultados: dict) -> list:
    return [c for c in resultados["celdas"] if c["destacada"]]


def _completas(resultados: dict) -> list:
    """0A y las destacadas, en el orden de la rejilla."""
    return [c for c in resultados["celdas"] if c["nombre"] == "0A" or c["destacada"]]


# ---------------------------------------------------------------------------
# Las secciones
# ---------------------------------------------------------------------------
def _cabecera(r: dict) -> list:
    return [
        f"# {TITULO}",
        "",
        f"**{r['advertencia']}**",
        "",
        f"> Este documento es GENERADO por `{GUION}` a partir de `{RESULTADOS}`: ninguna "
        f"cifra se teclea y no se edita a mano. Para cambiar una frase se cambia "
        f"`{GENERADOR}` y se vuelve a generar; para cambiar una cifra, se vuelve a correr "
        f"la simulación.",
        "",
    ]


def _insumos(r: dict) -> list:
    i, p = r["insumos"], r["parametros"]
    destacadas = [c["nombre"] for c in _destacadas(r)]
    replicas = (f"{entero(p['replicas'])} réplicas en 0A y en las celdas destacadas; cada "
                f"réplica remuestrea las placas con reemplazo (una placa por paciente, así "
                f"que es un bootstrap por paciente) y vuelve a sortear la clínica. El "
                f"generador queda fijo en todas. Intervalos del 95 % por percentiles; las "
                f"diferencias entre modelos se calculan dentro de cada réplica (pareadas)"
                if p["replicas"] else
                "sin bootstrap: esta corrida no tiene intervalos")
    return [
        "## Insumos y parámetros",
        "",
        "Qué es real y qué se supone:",
        "",
        f"- **Placas y verdad:** las {entero(i['placas'])} placas del conjunto de prueba de "
        f"RSNA (una por paciente; {entero(i['positivas'])} positivas, prevalencia "
        f"{numero(i['prevalencia'], 4)}), nunca usadas para entrenar ni calibrar, con su "
        f"etiqueta real de opacidad. Es un desenlace análogo al de Heckerling (infiltrado "
        f"radiográfico) en una población distinta: RSNA no es una cohorte con sospecha de "
        f"neumonía.",
        "- **Clínica:** a cada placa se le sortea la puntuación de Heckerling dada su "
        "etiqueta, con las frecuencias publicadas de la cohorte de derivación. No se "
        "inventa la exactitud de la regla: se usa la publicada, tal como la usa el sistema.",
        "- **Dependencia:** la estructura de dependencia entre clínica e imagen es un "
        "supuesto: nula en 0A y barrida en el resto de la rejilla.",
        "- **Transporte:** el generador supone que la distribución de la puntuación por "
        "clase, medida en la cohorte de derivación, se transporta al espectro de RSNA. Eso "
        "no se comprueba ni se puede comprobar aquí.",
        "",
        "Con qué se calculó:",
        "",
        f"- Puntuaciones crudas del modelo desplegado: `{i['crudas']}` "
        f"(sha256 `{huella(i['crudas_sha256'])}…`), generadas con los pesos de sha256 "
        f"`{huella(i['pesos_sha256'])}…`.",
        f"- Calibrador: `{i['calibrador']}` (sha256 `{huella(i['calibrador_sha256'])}…`).",
        f"- Previo del análisis principal: {numero(i['prevalencia'], 4)}, la prevalencia de "
        f"la población simulada. El previo desplegado, "
        f"{numero(p['previo_desplegado'], 4)}, solo entra en la sensibilidad al previo.",
        f"- Rejilla: ρ1 y ρ0 toman los valores {' / '.join(rho(x) for x in p['rejilla'])}: "
        f"{entero(len(r['celdas']))} celdas. El origen es 0A y se cuenta aparte; "
        + (f"celdas destacadas: {_lista(destacadas)}." if destacadas
           else "esta corrida no tiene celdas destacadas."),
        f"- Bootstrap: {replicas}.",
        f"- Semillas: clínica de la estimación puntual, {entero(p['semilla_puntual'])}; "
        f"clínica de la réplica b, {entero(p['semilla_clinica'])} + b; placas de la réplica "
        f"b, {entero(p['semilla_indices'])} + b.",
        f"- Tolerancia de las colas de la horquilla: ε = {numero(p['epsilon'], 3)} log-odds, "
        f"el redondeo máximo de las RV publicadas (la misma tolerancia de la comprobación "
        f"0A).",
        f"- ECE: {entero(p['bins'])} tramos de igual masa, con los empates rotos por el orden "
        f"del identificador de la placa. Su suelo de ruido: "
        f"{entero(p['repeticiones_suelo'])} juegos de etiquetas simuladas con las "
        f"probabilidades del propio modelo (semilla {entero(p['semilla_suelo'])}); se "
        f"publican la media y el percentil 95.",
        f"- Hipótesis de la horquilla: contención ≥ "
        f"{numero(100.0 * p['hipotesis_contencion'], 0)} % de los concordantes.",
        "",
    ]


def _imagen_sola(r: dict) -> list:
    m = r["imagen_sola"]
    return [
        "## La imagen sola",
        "",
        f"La probabilidad calibrada de la imagen sobre las {entero(m['casos'])} placas. El "
        f"oráculo toma esa probabilidad como la verdad de la imagen: así la diferencia entre "
        f"el sistema y el oráculo aísla la parte clínica, y la calibración de la imagen se "
        f"publica aparte, aquí, como el suelo de calibración de todo lo demás.",
        "",
        *_tabla(["AUC", "Brier", "pendiente", "intercepto", "ECE", "suelo de la ECE (media)",
                 "suelo de la ECE (p95)"],
                [[numero(m["auc"], 3), numero(m["brier"], 3), numero(m["pendiente"], 2),
                  numero(m["intercepto"], 3), numero(m["ece"], 3),
                  numero(m["suelo"]["media"], 3), numero(m["suelo"]["p95"], 3)]],
                izquierdas=0),
        f"La ECE ({numero(m['ece'], 3)}) {_frente_al_suelo(m['ece'], m['suelo'])}. La ECE "
        f"solo se lee al lado de su suelo, nunca contra un umbral absoluto. Una pendiente "
        f"menor que 1 quiere decir que el modelo exagera; mayor que 1, que se queda corto.",
        "",
    ]


def _fila_de_modelo(celda: dict, clave: str, con_intervalos: bool) -> list:
    m = celda["modelos"][clave]
    cifras = [(_cifra(celda, f"modelos.{clave}.{metrica}", decimales) if con_intervalos
               else numero(m[metrica], decimales))
              for metrica, _, decimales in METRICAS]
    return cifras + [numero(m["suelo"]["media"], 3), numero(m["suelo"]["p95"], 3)]


def _escenario_0a(r: dict) -> list:
    lineas = [
        "## Escenario 0A: la aritmética",
        "",
        "Con dependencia nula (ρ1 = ρ0 = 0) el oráculo de cada caso es la suma, en log-odds, "
        "de la evidencia de la imagen y del logaritmo de la RV de recuentos de su "
        "puntuación. Las tres comprobaciones de 0A son deterministas y caso a caso, y no "
        f"viven en este documento sino en `{PRUEBA_0A}`: la puntuación que calcula el "
        "sistema es la que sorteó el generador; el bloque que entrega es el redondeo de su "
        "propia aritmética; y la posterior del sistema coincide con la del oráculo dentro "
        f"de ε = {numero(r['parametros']['epsilon'], 3)} log-odds en todos los casos. Son "
        "pruebas, no estadísticas: una RV o un corte mutados las hacen fallar.",
        "",
        "Lo que 0A demuestra es que el sistema calcula lo que dice calcular; no que la "
        "posterior sea exacta en pacientes.",
        "",
    ]
    cero = _cero(r)
    if cero is None:
        return lineas + ["Esta corrida no incluye la celda 0A.", ""]
    n = cero["recuentos"]
    h = cero["horquilla"]["todos"]
    limpia = h["bajo"] == 0 and h["sobre"] == 0 and h["contencion"] == 1
    lineas += [
        f"Los cuatro modelos puntuales en 0A, sobre los {entero(n['asma_conocida'])} casos "
        f"con el asma conocida:",
        "",
        *_tabla(["modelo"] + [titulo for _, titulo, _ in METRICAS]
                + ["suelo de la ECE (media)", "suelo de la ECE (p95)"],
                [[nombre] + _fila_de_modelo(cero, clave, True) for clave, nombre in MODELOS]),
        f"La ECE de la combinación por independencia "
        f"({numero(cero['modelos']['independencia']['ece'], 3)}) "
        f"{_frente_al_suelo(cero['modelos']['independencia']['ece'], cero['modelos']['independencia']['suelo'])}.",
        "",
        "**La fila 0A de la horquilla es la comprobación de la métrica.** Con ρ = 0 el único "
        "desvío entre el sistema y el oráculo es el redondeo de las RV, así que las dos "
        "colas tienen que ser exactamente 0 y la contención, 100 %:",
        "",
        *_tabla(["celda", "concordantes", "por el lado conservador",
                 "más allá de la independencia", "contención"],
                [[cero["nombre"], entero(h["n"]), _fraccion(cero, "horquilla.todos.bajo"),
                  _fraccion(cero, "horquilla.todos.sobre"),
                  _fraccion(cero, "horquilla.todos.contencion")]]),
        ("Se cumple: la métrica de la horquilla mide lo que tiene que medir." if limpia else
         "**NO se cumple: la métrica de la horquilla o el generador tienen un defecto, y las "
         "tablas de la horquilla de este documento no se pueden leer hasta corregirlo.**"),
        "",
    ]
    return lineas


def _dependencia(r: dict) -> list:
    p = r["parametros"]
    celdas = _completas(r)
    mayor = max(p["rejilla"])
    extremo = (f" Un ρ de {rho(mayor)} sobre la puntuación es un caso extremo, no plausible: "
               f"se incluye para acotar, no porque se espere." if mayor >= RHO_EXTREMO else "")
    lineas = [
        "## Dependencia entre clínica e imagen",
        "",
        "Crepitantes, murmullo y opacidad son el mismo fenómeno físico visto de dos maneras: "
        "la clínica y la imagen no son independientes. El sistema solo ve la puntuación, y "
        "los recuentos publicados no la descomponen por hallazgo; por eso la dependencia se "
        "induce sobre la puntuación entera. **ρ1** es la correlación latente, entre los "
        "casos con neumonía, entre lo que la puntuación mide y lo que la imagen mide; "
        "**ρ0**, la misma entre los casos sin neumonía. Temperatura, pulso y asma diluyen "
        f"esa correlación.{extremo}",
        "",
        "Son dos parámetros y no uno porque con un solo ρ, simétrico, la dirección del sesgo "
        "quedaría decidida de antemano por el diseño. Con dos, la dirección es un resultado "
        "de cada celda y de cada lado de la imagen, no una premisa. En todas las celdas la "
        "distribución de la puntuación dentro de cada clase es la publicada: lo que cambia "
        "es la RV de la puntuación una vez vista la imagen.",
        "",
        "La correlación de Pearson, dentro de cada clase, entre la puntuación y la imagen "
        "que implica cada celda:",
        "",
        *_tabla(["celda", "ρ1", "ρ0", "correlación con neumonía", "correlación sin neumonía"],
                [[c["nombre"], rho(c["rho1"]), rho(c["rho0"]),
                  numero(c["correlacion_teorica"]["con_neumonia"], 3),
                  numero(c["correlacion_teorica"]["sin_neumonia"], 3)] for c in celdas]),
        "Los cuatro modelos puntuales por celda (casos con el asma conocida). La pendiente "
        "lleva su intervalo; la ECE va al lado de su suelo:",
        "",
    ]
    filas = []
    for c in celdas:
        for clave, nombre in MODELOS:
            m = c["modelos"][clave]
            filas.append([c["nombre"], nombre, numero(m["auc"], 3), numero(m["brier"], 3),
                          _cifra(c, f"modelos.{clave}.pendiente", 2),
                          numero(m["intercepto"], 3), numero(m["ece"], 3),
                          numero(m["suelo"]["media"], 3), numero(m["suelo"]["p95"], 3)])
    lineas += _tabla(["celda", "modelo", "AUC", "Brier", "pendiente", "intercepto", "ECE",
                      "suelo de la ECE (media)", "suelo de la ECE (p95)"], filas, izquierdas=2)
    lineas += ["Diferencias pareadas de cada combinación frente a la imagen sola (combinación "
               "menos imagen, sobre los mismos casos):", ""]
    lineas += _tabla(
        ["celda", "modelo"] + [titulo for _, titulo, _ in PAREADAS],
        [[c["nombre"], nombre]
         + [_cifra(c, f"pareadas.{clave}.{metrica}", decimales, signo=True)
            for metrica, _, decimales in PAREADAS]
         for c in celdas for clave, nombre in COMBINADOS], izquierdas=2)
    lineas += ["Un ΔBrier negativo es una mejora. Estas diferencias dicen cuánto aporta la "
               "clínica sorteada en la simulación, no cuánto aporta la clínica en pacientes.",
               ""]
    return lineas


def _horquilla(r: dict) -> list:
    p = r["parametros"]
    umbral = numero(100.0 * p["hipotesis_contencion"], 0)
    celdas = _completas(r)
    lineas = [
        "## La horquilla frente al oráculo",
        "",
        "La horquilla solo existe en los casos concordantes (clínica e imagen del mismo lado) "
        "con el asma conocida. Sus extremos son el conservador (dependencia total: solo "
        "cuenta la evidencia más informativa) y la independencia. La posición del oráculo se "
        "mide con λ, en log-odds: λ = 0 es el extremo conservador y λ = 1, la independencia.",
        "",
        f"- **Por el lado conservador:** el oráculo queda más allá del extremo conservador en "
        f"más de ε = {numero(p['epsilon'], 3)} log-odds. Ni la dependencia total recoge tanta "
        f"redundancia.",
        "- **Más allá de la independencia:** el oráculo queda más allá de la independencia en "
        "más de ε. La independencia se queda corta.",
        "- **Contención:** el complemento de las dos colas. Se llama contención y no "
        "cobertura: no es un intervalo de confianza.",
        "",
        f"**Hipótesis declarada de antemano, a refutar celda a celda:** «el oráculo queda "
        f"dentro de la horquilla en ≥ {umbral} % de los concordantes». La expectativa, "
        f"escrita antes de correr nada, era que solo se sostuviera en 0A y en las celdas más "
        f"suaves. Una contención baja es un resultado igual de publicable, y obliga a "
        f"repensar la cota, no a ocultarla.",
        "",
    ]
    filas = []
    for c in celdas:
        for lado, nombre in LADOS:
            h = c["horquilla"][lado]
            filas.append([c["nombre"], nombre, entero(h["n"]), _cuartiles(h["lambda"]),
                          _fraccion(c, f"horquilla.{lado}.bajo"),
                          _fraccion(c, f"horquilla.{lado}.sobre"),
                          _fraccion(c, f"horquilla.{lado}.contencion")])
    lineas += _tabla(["celda", "lado de la imagen", "n", "λ: mediana (q1 a q3)",
                      "por el lado conservador", "más allá de la independencia",
                      "contención"], filas, izquierdas=2)
    sin_horquilla = sum(c["horquilla"]["todos"]["sin_horquilla"] for c in celdas)
    lineas += [f"Casos concordantes sin horquilla (RV de imagen exactamente 1) en estas "
               f"celdas: {entero(sin_horquilla)}.", "",
               "El veredicto, celda a celda, sobre todos los concordantes:", ""]
    lineas += _tabla(
        ["celda", "contención", "umbral", "veredicto"],
        [[c["nombre"], _fraccion(c, "horquilla.todos.contencion"),
          f"≥ {numero(100.0 * c['hipotesis']['umbral'], 0)} %",
          "se sostiene" if c["hipotesis"]["se_sostiene"] else "no se sostiene"]
         for c in r["celdas"]])
    lineas += ["**Casos discordantes** (clínica e imagen en lados opuestos): el sistema da un "
               "solo número, el de la independencia. Error frente al oráculo, en log-odds; "
               "el sesgo es sistema menos oráculo:", ""]
    lineas += _tabla(
        ["celda", "n", "error absoluto mediano", "sesgo mediano"],
        [[c["nombre"], entero(c["discordantes"]["n"]),
          _cifra(c, "discordantes.error_abs_mediano", 3),
          _cifra(c, "discordantes.sesgo_mediano", 3, signo=True)] for c in celdas])
    lineas += ["**Casos con el asma desconocida:** el sistema entrega un rango (dos "
               "puntuaciones posibles) y el oráculo marginaliza el asma con la misma "
               "información. La tabla dice si el oráculo cae dentro de ese rango, con la "
               "misma ε, y el error del punto medio del rango en log-odds:", ""]
    lineas += _tabla(
        ["celda", "n", "por debajo del rango", "por encima del rango", "dentro",
         "punto medio: error absoluto mediano", "punto medio: sesgo mediano"],
        [[c["nombre"], entero(c["no_se"]["n"]), _fraccion(c, "no_se.bajo"),
          _fraccion(c, "no_se.sobre"), _fraccion(c, "no_se.contencion"),
          _cifra(c, "no_se.punto_medio.error_abs_mediano", 3),
          _cifra(c, "no_se.punto_medio.sesgo_mediano", 3, signo=True)] for c in celdas])
    lineas += ["Cuántos casos hay de cada tipo:", ""]
    lineas += _tabla(
        ["celda", "casos", "asma conocida", "concordantes", "concordantes, imagen a favor",
         "concordantes, imagen en contra", "discordantes", "asma desconocida"],
        [[c["nombre"]] + [entero(c["recuentos"][clave]) for clave in (
            "casos", "asma_conocida", "concordantes", "concordantes_a_favor",
            "concordantes_en_contra", "discordantes", "no_se")] for c in celdas])
    return lineas


def _escala_legible(r: dict) -> list:
    lineas = [
        "## Cuánto de su evidencia conserva la puntuación",
        "",
        "Por puntuación y por lado de la imagen: la RV de la puntuación una vez vista la "
        "imagen, en log-odds, y la **fracción** de su log-RV de recuentos que conserva. Una "
        "fracción de 1 es la independencia (la puntuación conserva toda su evidencia); menor "
        "que 1, que la imagen ya contaba parte; mayor que 1, que la independencia se queda "
        "corta; negativa, que el signo se invierte. Las puntuaciones k = 2 y k = 3 se "
        "rotulan «poco informativa» (|ln RV de recuentos| < 0,5): dividir por un número tan "
        "pequeño amplifica cualquier variación. La dirección se lee por lado, no global.",
        "",
    ]
    cero = _cero(r)
    if cero is not None:
        lineas += ["En 0A la fracción mediana de las puntuaciones extremas (k ≤ 1 y k ≥ 4) es "
                   + _lista([f"{numero(cero['escala_legible'][lado]['fraccion_mediana_extremas'], 2)} "
                             f"{nombre}" for lado, nombre in LADOS_DE_LA_IMAGEN])
                   + ": sin dependencia la puntuación conserva toda su evidencia.", ""]
    destacadas = _destacadas(r)
    if not destacadas:
        return lineas + ["Esta corrida no tiene celdas destacadas.", ""]
    for c in destacadas:
        lineas += [f"### Celda {c['nombre']}", ""]
        lineas += ["Fracción mediana de las puntuaciones extremas (k ≤ 1 y k ≥ 4): "
                   + _lista([f"{numero(c['escala_legible'][lado]['fraccion_mediana_extremas'], 2)} "
                             f"{nombre}" for lado, nombre in LADOS_DE_LA_IMAGEN]) + ".", ""]
        for lado, nombre in LADOS[1:]:
            e = c["escala_legible"][lado]
            lineas += [f"{nombre[0].upper()}{nombre[1:]}, {entero(e['placas'])} placas:", ""]
            lineas += _tabla(
                ["k", "ln RV de recuentos", "casos esperados", "log-RV: mediana (q1 a q3)",
                 "fracción: mediana (q1 a q3)", "signo invertido", "rótulo"],
                [[str(f["k"]), numero(f["ln_rv_recuentos"], 2, signo=True),
                  numero(f["casos_esperados"], 1), _cuartiles(f["log_rv"]),
                  _cuartiles(f["fraccion"]), porcentaje(f["signo_invertido"]),
                  "poco informativa" if f["poco_informativa"] else ""]
                 for f in e["por_puntuacion"]])
    return lineas


def _rejilla(r: dict) -> list:
    return [
        "## La rejilla completa",
        "",
        f"Las {entero(len(r['celdas']))} celdas, sin intervalos (el bootstrap solo se corre "
        f"en 0A y en las destacadas). La contención y las colas son las de todos los "
        f"concordantes.",
        "",
        *_tabla(["celda", "destacada", "contención", "por el lado conservador",
                 "más allá de la independencia", "pendiente de la independencia",
                 "AUC de la independencia", "pendiente del extremo conservador"],
                [[c["nombre"], "sí" if c["destacada"] else "",
                  porcentaje(c["horquilla"]["todos"]["contencion"]),
                  porcentaje(c["horquilla"]["todos"]["bajo"]),
                  porcentaje(c["horquilla"]["todos"]["sobre"]),
                  numero(c["modelos"]["independencia"]["pendiente"], 2),
                  numero(c["modelos"]["independencia"]["auc"], 3),
                  numero(c["modelos"]["conservador"]["pendiente"], 2)]
                 for c in r["celdas"]], izquierdas=2),
    ]


def _sensibilidad(r: dict) -> list:
    celdas = [c for c in r["celdas"] if "sensibilidad_al_previo" in c]
    lineas = ["## Sensibilidad al previo", ""]
    if not celdas:
        return lineas + ["Esta corrida no calculó la sensibilidad al previo.", ""]
    s = celdas[0]["sensibilidad_al_previo"]
    previo, principal = numero(s["previo"], 4), numero(s["previo_principal"], 4)
    d = s["desplazamiento_log_odds"]
    lineas += [
        f"El análisis principal usa {principal}, la prevalencia de la población simulada; el "
        f"sistema desplegado arranca con {previo}. Declarar {previo} en una población de "
        f"{principal} tiene un efecto analítico: todas las odds posteriores se multiplican "
        f"por {numero(math.exp(d), 3)}, es decir, se desplazan {numero(d, 2, signo=True)} en "
        f"log-odds por igual. El intercepto de calibración debe moverse, por tanto, en "
        f"torno a {numero(-d, 2, signo=True)} respecto del principal.",
        "",
        "**El AUC no cambia** (un desplazamiento común no altera el orden de los casos) y "
        "no se reporta en esta tabla. **Esto no recomienda configurar el despliegue con "
        f"{principal}:** es la prevalencia del conjunto de datos de un reto, no la de ningún "
        "servicio.",
        "",
        f"Con el previo {previo} (casos con el asma conocida); «principal» es la misma cifra "
        f"con {principal}. Las bandas son < 20 %, 20-70 % y > 70 %:",
        "",
    ]
    filas = []
    for c in celdas:
        for clave, nombre in COMBINADOS:
            m = c["sensibilidad_al_previo"]["modelos"][clave]
            filas.append([
                c["nombre"], nombre, numero(m["brier"], 3), numero(m["brier_principal"], 3),
                numero(m["ece"], 3),
                f"{numero(m['suelo']['media'], 3)}; {numero(m['suelo']['p95'], 3)}",
                numero(m["ece_principal"], 3), numero(m["intercepto"], 3, signo=True),
                numero(m["intercepto_principal"], 3, signo=True),
                numero(None if _falta(m["intercepto"]) or _falta(m["intercepto_principal"])
                       else m["intercepto"] - m["intercepto_principal"], 3, signo=True),
                f"{entero(m['bandas']['cambian'])} de {entero(m['bandas']['casos'])}",
                _transiciones(m["bandas"])])
    lineas += _tabla(["celda", "modelo", "Brier", "Brier principal", "ECE",
                      "suelo de la ECE (media; p95)", "ECE principal", "intercepto",
                      "intercepto principal", "diferencia", "cambian de banda",
                      "en qué sentido"], filas, izquierdas=2)
    lineas += ["La categoría que el sistema imprime (todos los casos, también los del asma "
               "desconocida):", ""]
    lineas += _tabla(
        ["celda", "cambian de categoría", "en qué sentido"],
        [[c["nombre"],
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['cambian'])} de "
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['casos'])}",
          _transiciones(c["sensibilidad_al_previo"]["categoria_del_sistema"])]
         for c in celdas])
    return lineas


def _optimismo(r: dict) -> list:
    lineas = ["## 0C: optimismo de la derivación (cálculo, no experimento)", ""]
    cero = _cero(r)
    if cero is None or "optimismo_de_la_derivacion" not in cero:
        return lineas + ["Esta corrida no calculó 0C.", ""]
    o = cero["optimismo_de_la_derivacion"]
    mas, menos = [], []
    for f in o["por_puntuacion"]:
        extrema = abs(math.log(f["rv_derivacion"])) > abs(math.log(f["rv_validacion"]))
        (mas if extrema else menos).append(str(f["k"]))
    reparto = []
    if mas:
        reparto.append(f"más extrema que la de validación en k = {_lista(mas)}")
    if menos:
        reparto.append(f"menos extrema en k = {_lista(menos)}")
    lineas += [
        "El sistema usa las RV de la cohorte de derivación, por puntuación; la validación "
        "externa solo las publica por bandas de puntuación. **Esto es un cálculo, no un "
        "experimento:** no se sortea nada; se compara, puntuación a puntuación, la RV de la "
        "derivación con la de la banda de validación que le corresponde.",
        "",
        *_tabla(["k", "RV de la derivación", "RV de la validación",
                 "ln RV derivación − ln RV validación"],
                [[str(f["k"]), numero(f["rv_derivacion"], 2), numero(f["rv_validacion"], 2),
                  numero(f["diferencia_log"], 2, signo=True)] for f in o["por_puntuacion"]]),
        f"La RV de la derivación es {_lista(reparto)} (más extrema: más lejos de 1)."
        + (" El «optimismo» de la derivación no es uniforme." if mas and menos else ""),
        "",
        f"Si el sistema usara las RV de la validación, cambiarían de banda "
        f"{entero(o['bandas']['cambian'])} de los {entero(o['bandas']['casos'])} casos con el "
        f"asma conocida de 0A (combinación por independencia): {_transiciones(o['bandas'])}.",
        "",
    ]
    return lineas


def _colas(h: dict) -> str:
    """Hacia donde cae el oraculo, leido de las dos colas."""
    dentro = f"queda dentro el {porcentaje(h['contencion'])}"
    bajo, sobre = h["bajo"], h["sobre"]
    if _falta(bajo) or _falta(sobre):
        return "no hay casos"
    if bajo == 0 and sobre == 0:
        return f"{dentro}; ninguna cola tiene casos"
    if bajo == sobre:
        return f"{dentro}; las dos colas pesan lo mismo ({porcentaje(bajo)} cada una)"
    if sobre > bajo:
        return (f"{dentro}; la cola mayor es la de más allá de la independencia "
                f"({porcentaje(sobre)}, frente a {porcentaje(bajo)} por el lado conservador)")
    return (f"{dentro}; la cola mayor es la del lado conservador ({porcentaje(bajo)}, frente "
            f"a {porcentaje(sobre)} más allá de la independencia)")


EJES = ("Dependencia simétrica (ρ1 = ρ0)",
        "Dependencia solo entre los casos con neumonía (ρ0 = 0)",
        "Dependencia solo entre los casos sin neumonía (ρ1 = 0)",
        "Otras celdas")


def _eje(celda: dict) -> str:
    if celda["rho1"] == celda["rho0"]:
        return EJES[0]
    if celda["rho0"] == 0:
        return EJES[1]
    if celda["rho1"] == 0:
        return EJES[2]
    return EJES[3]


def _fuera_de_su_intervalo(celdas) -> tuple:
    """(cuantas cifras con intervalo quedan fuera de el, cuantas hay)."""
    fuera = total = 0
    for celda in celdas:
        for ruta, par in (celda.get("intervalos") or {}).items():
            valor = _valor(celda, ruta)
            if _falta(valor) or _falta(par[0]) or _falta(par[1]):
                continue
            total += 1
            fuera += valor < par[0] - 1e-9 or valor > par[1] + 1e-9
    return fuera, total


def _lectura(r: dict) -> list:
    lineas = [
        "## Lectura de los resultados",
        "",
        "Estas frases se componen contando sobre las cifras de las tablas: dicen lo que las "
        "cifras dicen, y nada más. Todo se refiere a la simulación.",
        "",
    ]
    destacadas = _destacadas(r)
    total = len(destacadas)
    cero = _cero(r)
    if cero is not None:
        par = (cero.get("intervalos") or {}).get("modelos.independencia.pendiente")
        lineas.append(
            f"- **0A.** La pendiente de la combinación por independencia es "
            f"{_cifra(cero, 'modelos.independencia.pendiente', 2)}"
            + ("" if not par or _falta(par[0]) or _falta(par[1]) else
               ("; su intervalo contiene el 1" if par[0] <= 1 <= par[1]
                else "; su intervalo no contiene el 1"))
            + f". En la horquilla, {_colas(cero['horquilla']['todos'])}.")
    if not destacadas:
        lineas.append("- Esta corrida no tiene celdas destacadas.")
    else:
        debajo = [c for c in destacadas
                  if not _falta(c["modelos"]["independencia"]["pendiente"])
                  and c["modelos"]["independencia"]["pendiente"] < 1]
        lineas.append(
            f"- **La independencia.** Celdas destacadas en las que la pendiente de la "
            f"combinación por independencia es menor que 1: {len(debajo)} de {total}"
            + (" (" + "; ".join(
                f"{c['nombre']}: {_cifra(c, 'modelos.independencia.pendiente', 2)}"
                for c in debajo) + ")" if debajo else "")
            + ". Una pendiente menor que 1 es la forma cuantitativa de «exagera».")
        con_intervalo = [c for c in debajo
                         if (c.get("intervalos") or {}).get("modelos.independencia.pendiente")]
        if con_intervalo:
            enteros = [c for c in con_intervalo
                       if c["intervalos"]["modelos.independencia.pendiente"][1] < 1]
            lineas.append(
                f"- De esas, con el intervalo entero por debajo de 1: {len(enteros)} de "
                f"{len(con_intervalo)}"
                + (f" ({_lista(c['nombre'] for c in enteros)})" if enteros else "") + ".")
        encima = [c for c in destacadas
                  if not _falta(c["modelos"]["conservador"]["pendiente"])
                  and c["modelos"]["conservador"]["pendiente"] > 1]
        lineas.append(
            f"- **El extremo conservador.** Celdas destacadas en las que su pendiente es "
            f"mayor que 1 (se queda corto): {len(encima)} de {total}"
            + (" (" + "; ".join(
                f"{c['nombre']}: {_cifra(c, 'modelos.conservador.pendiente', 2)}"
                for c in encima) + ")" if encima else "") + ".")
        mejoran = [c for c in destacadas
                   if (c.get("intervalos") or {}).get("pareadas.independencia.auc")
                   and c["intervalos"]["pareadas.independencia.auc"][0] > 0]
        if any((c.get("intervalos") or {}).get("pareadas.independencia.auc")
               for c in destacadas):
            lineas.append(
                f"- **Discriminación.** Celdas destacadas en las que el intervalo de la "
                f"diferencia de AUC entre la independencia y la imagen sola queda entero por "
                f"encima de 0: {len(mejoran)} de {total}"
                + (f" ({_lista(c['nombre'] for c in mejoran)})" if mejoran else "") + ".")
    sostienen = [c["nombre"] for c in r["celdas"] if c["hipotesis"]["se_sostiene"]]
    rejilla = len(r["celdas"])
    lineas.append(
        "- **La hipótesis de la horquilla.** "
        + (f"Se sostiene en {len(sostienen)} de las {rejilla} celdas de la rejilla: "
           f"{_lista(sostienen)}." if sostienen else
           f"No se sostiene en ninguna de las {rejilla} celdas de la rejilla."))
    fuera, cifras = _fuera_de_su_intervalo(r["celdas"])
    if cifras:
        lineas.append(
            f"- **Los intervalos.** La estimación puntual usa la clínica sorteada con la "
            f"semilla {entero(r['parametros']['semilla_puntual'])} sobre todas las placas; "
            f"cada réplica remuestrea las placas y sortea otra clínica. El intervalo son los "
            f"percentiles de las réplicas y no está centrado en la estimación puntual: en "
            f"esta corrida, de {entero(r['parametros']['replicas'])} réplicas, quedan fuera "
            f"de su intervalo {entero(fuera)} de las {entero(cifras)} cifras que lo "
            f"llevan.")
    if destacadas:
        lineas += ["", "Hacia qué lado cae el oráculo, por eje y por lado de la imagen:", ""]
        for eje in EJES:
            celdas = [c for c in destacadas if _eje(c) == eje]
            if not celdas:
                continue
            lineas.append(f"- **{eje}.**")
            for c in celdas:
                lineas.append(
                    f"  - {c['nombre']}: "
                    + "; ".join(f"{nombre} {_colas(c['horquilla'][lado])}"
                                for lado, nombre in LADOS_DE_LA_IMAGEN) + ".")
    return lineas + [""]


def _limites(r: dict) -> list:
    return [
        "## Lo que esta simulación puede afirmar y lo que no",
        "",
        "**Puede afirmar:**",
        "",
        "- que el sistema reproduce caso a caso la posterior del generador (0A);",
        "- que, **si** la puntuación tiene la exactitud publicada y es condicionalmente "
        "independiente de la imagen, la aritmética y la calibración de la imagen dan una "
        "posterior calibrada en el conjunto de prueba de RSNA;",
        "- cuánto se desvía la independencia de la posterior del generador **bajo cada "
        "supuesto de dependencia**, en qué dirección, y dónde cae el oráculo respecto a la "
        "horquilla;",
        "- cuánto desplaza la calibración un previo equivocado.",
        "",
        "**No puede afirmar** exactitud clínica real ni cuánto aporta la clínica en "
        "pacientes: las viñetas no son pacientes, la exactitud es la publicada y la "
        "dependencia es la supuesta. Esta simulación no mide exactitud clínica.",
        "",
        "Aquí no se reentrena ni se recalibra el modelo de imagen, ni se ajustan las RV ni "
        "la prevalencia con estos datos. Solo se mide.",
        "",
    ]


def _titulo_de_figura(nombre: str, r: dict) -> str:
    rotulo = r["rotulo"]
    for clave, titulo in FIGURAS_GLOBALES:
        if nombre == clave:
            return f"{titulo} ({rotulo})"
    if nombre.startswith(PREFIJO_FIABILIDAD):
        for c in r["celdas"]:
            if nombre == PREFIJO_FIABILIDAD + _slug(c):
                return f"Fiabilidad por deciles, celda {c['nombre']} ({rotulo})"
    return f"{nombre} ({rotulo})"


def _figuras(r: dict, figuras: dict) -> list:
    lineas = ["## Figuras", ""]
    if not figuras:
        return lineas + ["Esta versión del documento se generó sin figuras.", ""]
    orden = [PREFIJO_FIABILIDAD + _slug(c) for c in r["celdas"]]
    orden += [clave for clave, _ in FIGURAS_GLOBALES]
    orden = [n for n in orden if n in figuras] + sorted(n for n in figuras if n not in orden)
    lineas += ["El guion las dibuja leyendo el mismo fichero de resultados que este "
               "documento. Con `--sin-figuras` no se redibujan: se enlazan las que ya "
               "hubiera en la carpeta.", ""]
    for nombre in orden:
        lineas += [f"![{_titulo_de_figura(nombre, r)}]({figuras[nombre]})", ""]
    return lineas


def _reproducir(r: dict) -> list:
    i, p = r["insumos"], r["parametros"]
    return [
        "## Cómo se reproduce",
        "",
        "Desde la raíz del repositorio:",
        "",
        "```",
        f"python {GUION} --replicas {p['replicas']}",
        "```",
        "",
        f"La orden lee `{i['crudas']}` (una copia congelada de las puntuaciones crudas) y "
        f"`{i['calibrador']}`, y escribe `{RESULTADOS}`, las figuras y este documento. Se "
        f"reproduce **sin los pesos** del modelo, sin red y sin contenedores, y con las "
        f"semillas fijas que se citan arriba. Las figuras necesitan el extra "
        f"`figuras` del paquete; con `--sin-figuras` no se dibujan.",
        "",
        "Para regenerar las figuras y el documento sin recalcular:",
        "",
        "```",
        f"python {GUION} --solo-documento",
        "```",
        "",
    ]


def redactar(resultados: dict, figuras: dict | None = None) -> str:
    """El documento de analisis, en Markdown.

    `figuras` es {nombre sin extension: enlace relativo desde el documento};
    las figuras que no esten en el diccionario no se enlazan."""
    r = resultados
    lineas = (_cabecera(r) + _insumos(r) + _imagen_sola(r) + _escenario_0a(r)
              + _dependencia(r) + _horquilla(r) + _escala_legible(r) + _rejilla(r)
              + _sensibilidad(r) + _optimismo(r) + _lectura(r) + _limites(r)
              + _figuras(r, dict(figuras or {})) + _reproducir(r))
    return "\n".join(lineas).rstrip("\n") + "\n"
````

- [ ] **Paso 4: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_informe.py`

Esperado: `20 passed` (casi todo el tiempo es la fixture `resultados_minimos`, que calcula la rejilla mínima).

- [ ] **Paso 5: Escribir las pruebas del script, que fallan**

En `tests/test_validar_combinacion.py` hay que hacer tres cosas.

(a) La fixture que saca el análisis del repo. Busca exactamente (es la línea 7 del fichero):

```python
from copiloto_triaje.validacion import datos, oraculo, simulacion
```

y sustitúyelo por:

```python
from copiloto_triaje.validacion import datos, oraculo, simulacion


@pytest.fixture(autouse=True)
def analisis_fuera_del_repo(validar, tmp_path_factory, monkeypatch):
    """Ninguna prueba escribe el analisis del repo: `main()` sin `--analisis`
    lo deja en una carpeta temporal."""
    ruta = tmp_path_factory.mktemp("analisis") / "validacion-semisintetica-sp5.md"
    monkeypatch.setattr(validar, "ANALISIS", ruta)
    return ruta
```

(b) La prueba `test_main_escribe_los_resultados_donde_se_le_dice` llama a `main()` con un `calcular`
falso que devuelve `{"rotulo": ..., "celdas": []}`; desde esta tarea `main()` redacta el documento con
lo que lee, y con ese diccionario no puede. El `calcular` falso pasa a devolver `resultados_minimos`.
Busca exactamente:

```python
def test_main_escribe_los_resultados_donde_se_le_dice(validar, tmp_path, monkeypatch, capsys):
    llamadas = []

    def calcular_falso(replicas, procesos):
        llamadas.append((replicas, procesos))
        return {"rotulo": validar.ROTULO, "celdas": []}

    monkeypatch.setattr(validar, "calcular", calcular_falso)
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path),
                         "--sin-figuras"]) == 0
    assert llamadas == [(3, 1)]
    assert validar.leer_resultados(tmp_path / "resultados_simulacion.json")["celdas"] == []
    assert "resultados_simulacion.json" in capsys.readouterr().out
```

y sustitúyelo por:

```python
def test_main_escribe_los_resultados_donde_se_le_dice(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys):
    llamadas = []

    def calcular_falso(replicas, procesos):
        llamadas.append((replicas, procesos))
        return resultados_minimos

    monkeypatch.setattr(validar, "calcular", calcular_falso)
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path),
                         "--sin-figuras"]) == 0
    assert llamadas == [(3, 1)]
    assert validar.leer_resultados(tmp_path / "resultados_simulacion.json") == resultados_minimos
    assert "resultados_simulacion.json" in capsys.readouterr().out
```

(c) Añade AL FINAL del fichero (tras la última línea de `test_main_sin_figuras_no_dibuja_nada`,
dejando dos líneas en blanco):

```python
# --------------------------------------------------------------------------
# El documento de analisis (tarea 6)
# --------------------------------------------------------------------------
def test_escribir_analisis_enlaza_las_figuras_con_rutas_relativas(
        validar, resultados_minimos, tmp_path):
    carpeta = tmp_path / "docs" / "validacion-semisintetica"
    figuras = [carpeta / "fiabilidad_0a.png", carpeta / "contencion_rejilla.png"]
    destino = tmp_path / "docs" / "sub" / "analisis.md"
    assert validar.escribir_analisis(resultados_minimos, figuras, destino) == destino
    crudo = destino.read_bytes()
    assert b"\r" not in crudo and crudo.endswith(b"\n")
    texto = crudo.decode("utf-8")
    assert texto.startswith("# Validación de la combinación de clínica e imagen: "
                            "simulación semisintética (SP5)\n")
    assert "](../validacion-semisintetica/fiabilidad_0a.png)" in texto
    assert "](../validacion-semisintetica/contencion_rejilla.png)" in texto
    assert texto.count(".png") == 2
    assert "\\" not in texto and str(tmp_path) not in texto
    sin = validar.escribir_analisis(resultados_minimos, [], tmp_path / "sin.md")
    assert ".png" not in sin.read_text(encoding="utf-8")


def test_main_escribe_el_analisis_leyendo_el_json(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys, analisis_fuera_del_repo):
    pytest.importorskip("matplotlib")
    monkeypatch.setattr(validar, "calcular", lambda replicas, procesos: resultados_minimos)
    salida = tmp_path / "docs" / "validacion-semisintetica"
    analisis = tmp_path / "docs" / "analisis.md"
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(salida),
                         "--analisis", str(analisis)]) == 0
    texto = analisis.read_text(encoding="utf-8")
    assert [linea for linea in texto.splitlines() if linea.startswith("![")] == [
        f"![{titulo} (simulación semisintética)](validacion-semisintetica/{nombre})"
        for titulo, nombre in (
            ("Fiabilidad por deciles, celda 0A", "fiabilidad_0a.png"),
            ("Fiabilidad por deciles, celda (0,3; 0,3)", "fiabilidad_r1-030_r0-030.png"),
            ("El oráculo frente a la horquilla, por celda y lado", "horquilla_por_celda.png"),
            ("Contención del oráculo en la horquilla, por celda", "contencion_rejilla.png"),
            ("Pendiente de la independencia, por celda", "pendiente_rejilla.png"))]
    assert capsys.readouterr().out.splitlines()[-1] == f"análisis: {analisis}"
    assert not analisis_fuera_del_repo.exists()
    # sin --analisis va al de por defecto (aqui, desviado a una carpeta temporal)
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(salida),
                         "--sin-figuras"]) == 0
    assert analisis_fuera_del_repo.is_file()


def test_solo_documento_sin_json_sale_con_un_mensaje(validar, tmp_path, monkeypatch):
    monkeypatch.setattr(validar, "calcular", lambda *a, **k: pytest.fail("ha recalculado"))
    analisis = tmp_path / "analisis.md"
    with pytest.raises(SystemExit) as salida:
        validar.main(["--solo-documento", "--salida", str(tmp_path),
                      "--analisis", str(analisis)])
    assert "resultados_simulacion.json" in str(salida.value)
    assert "sin --solo-documento" in str(salida.value)
    assert not analisis.exists()
    assert list(tmp_path.iterdir()) == []


def test_solo_documento_escribe_el_documento_sin_recalcular(
        validar, resultados_minimos, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(validar, "calcular", lambda *a, **k: pytest.fail("ha recalculado"))
    otro = json.loads(json.dumps(resultados_minimos))
    otro["insumos"]["placas"] = 9876
    ruta = validar.escribir_resultados(otro, tmp_path / "resultados_simulacion.json")
    antes = ruta.read_bytes()
    ajena = tmp_path / "fiabilidad_0a.png"
    ajena.write_bytes(b"de una corrida anterior")
    analisis = tmp_path / "analisis.md"
    assert validar.main(["--solo-documento", "--sin-figuras", "--salida", str(tmp_path),
                         "--analisis", str(analisis)]) == 0
    assert ruta.read_bytes() == antes
    texto = analisis.read_text(encoding="utf-8")
    assert "9 876" in texto                                   # leido del JSON
    assert "](fiabilidad_0a.png)" in texto                    # las figuras que hubiera
    assert ajena.read_bytes() == b"de una corrida anterior"
    salida = capsys.readouterr().out
    assert "resultados:" not in salida and "figura:" not in salida
    assert salida.splitlines() == [f"análisis: {analisis}"]
```

- [ ] **Paso 6: Correr las pruebas y ver que fallan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_validar_combinacion.py`

Esperado: `3 failed, 14 passed`:

```
E       AttributeError: module 'validar_combinacion' has no attribute 'escribir_analisis'
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\test_main_escribe_el_analisis_0\\docs\\analisis.md'
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\test_solo_documento_escribe_el0\\analisis.md'
FAILED tests/test_validar_combinacion.py::test_escribir_analisis_enlaza_las_figuras_con_rutas_relativas
FAILED tests/test_validar_combinacion.py::test_main_escribe_el_analisis_leyendo_el_json
FAILED tests/test_validar_combinacion.py::test_solo_documento_escribe_el_documento_sin_recalcular
3 failed, 14 passed
```

`test_solo_documento_sin_json_sale_con_un_mensaje` y la prueba modificada en (b) PASAN ya en este
paso: el `main()` de la tarea 4 ya sale con `SystemExit` cuando falta el JSON, y todavía no redacta.
Guardan el comportamiento, no lo estrenan.

- [ ] **Paso 7: Escribir el documento desde el script**

En `scripts/validar_combinacion.py`, tres cambios.

(a) El `import`. Busca exactamente:

```python
from copiloto_triaje.validacion import datos, metricas, oraculo, simulacion  # noqa: E402
```

y sustitúyelo por:

```python
from copiloto_triaje.validacion import (  # noqa: E402
    datos, informe, metricas, oraculo, simulacion,
)
```

(b) El bloque nuevo, ENTRE la función `figuras` y `def main(argv=None) -> int:`. Busca exactamente:

```python
    rutas.append(figura_rejilla(resultados, carpeta / "pendiente_rejilla.png", "pendiente"))
    return rutas


def main(argv=None) -> int:
```

y sustitúyelo por:

```python
    rutas.append(figura_rejilla(resultados, carpeta / "pendiente_rejilla.png", "pendiente"))
    return rutas


# ---------------------------------------------------------------------------
# EL DOCUMENTO
# ---------------------------------------------------------------------------
def _enlace(figura: Path, desde: Path) -> str:
    """El enlace relativo desde la carpeta del documento, con barras `/`. Si
    no hay camino relativo (otra unidad de disco), el nombre del fichero: una
    ruta absoluta llevaria al documento el nombre de la maquina."""
    try:
        return os.path.relpath(figura.resolve(), desde.resolve()).replace(os.sep, "/")
    except ValueError:
        return figura.name


def escribir_analisis(resultados: dict, figuras: list, ruta) -> Path:
    """Escribe el documento de analisis en `ruta`, en UTF-8 y con LF.

    `figuras` son las rutas de los PNG que se enlazan; el texto lo redacta
    `informe.redactar` LEYENDO `resultados`."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    enlaces = {Path(f).stem: _enlace(Path(f), ruta.parent) for f in figuras}
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        f.write(informe.redactar(resultados, enlaces))
    return ruta


def main(argv=None) -> int:
```

(c) El final de `main()`. Busca exactamente:

```python
            print(f"figura: {figura}")
    return 0
```

y sustitúyelo por:

```python
            print(f"figura: {figura}")
    analisis = escribir_analisis(resultados, figuras_presentes(salida), args.analisis)
    print(f"análisis: {analisis}")
    return 0
```

- [ ] **Paso 8: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_validar_combinacion.py`

Esperado: `17 passed`. Después comprueba que ninguna prueba ha escrito en el repo:

Run: `git status --short docs/`

Esperado: nada (ni `docs/validacion-semisintetica-sp5.md` ni ficheros nuevos bajo `docs/validacion-semisintetica/`).

- [ ] **Paso 9: Correr los vecinos**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_informe.py tests/test_validar_combinacion.py tests/test_metricas.py tests/test_simulacion.py tests/test_validacion_0a.py tests/test_validacion_datos.py`

Esperado: ningún fallo ni error.

- [ ] **Paso 10: Generar el documento con la rejilla completa y LEERLO**

Las pruebas comprueban el formato y que las cifras salen del diccionario; que el documento se lea
solo se ve leyéndolo. Corre el script con pocas réplicas y con TODO fuera del repo:

Run: `C:/venv-copiloto/Scripts/python.exe -B scripts/validar_combinacion.py --replicas 20 --salida <CARPETA_TEMPORAL>/docs/validacion-semisintetica --analisis <CARPETA_TEMPORAL>/docs/validacion-semisintetica-sp5.md`

Esperado (menos de un minuto): una línea `resultados: …`, diez líneas `figura: …` y, la última,
`análisis: …validacion-semisintetica-sp5.md`. El documento tiene 560 líneas y este índice:

```
# Validación de la combinación de clínica e imagen: simulación semisintética (SP5)
## Insumos y parámetros
## La imagen sola
## Escenario 0A: la aritmética
## Dependencia entre clínica e imagen
## La horquilla frente al oráculo
## Cuánto de su evidencia conserva la puntuación
### Celda (0; 0,3)
### Celda (0; 0,6)
### Celda (0,3; 0)
### Celda (0,3; 0,3)
### Celda (0,6; 0)
### Celda (0,6; 0,6)
## La rejilla completa
## Sensibilidad al previo
## 0C: optimismo de la derivación (cálculo, no experimento)
## Lectura de los resultados
## Lo que esta simulación puede afirmar y lo que no
## Figuras
## Cómo se reproduce
```

Léelo entero y comprueba:
- la cabecera: el título con «simulación semisintética», la advertencia en negrita y la nota de que
  es un documento generado;
- «Escenario 0A»: la fila de la horquilla da 0,0 %, 0,0 % y 100,0 %, y debajo dice «Se cumple: la
  métrica de la horquilla mide lo que tiene que medir»;
- «Dependencia»: la tabla de correlaciones da 0,000 en 0A (no «−0,000») y ≈ 0,275 / 0,286 con ρ = 0,3;
- «La horquilla»: la tabla del veredicto tiene 25 filas y solo llevan intervalo 0A y las seis
  destacadas; con 20 réplicas se sostiene en 0A y en (0,15; 0,15);
- «Lectura de los resultados»: cada frase se puede comprobar contra su tabla (p. ej. «menor que 1:
  6 de 6» contra la columna de la pendiente); los ejes salen en el orden simétrica, solo con
  neumonía, solo sin neumonía;
- «Figuras»: diez enlaces, todos `validacion-semisintetica/<nombre>.png`, sin ninguna barra invertida
  ni ruta absoluta;
- en todo el documento: ningún `nan`, `None`, llave ni punto decimal.

Con 20 réplicas algunos intervalos no contienen su estimación puntual (la «Lectura» dice cuántos: 13
de 357); no es un fallo del documento, que imprime lo que hay en el JSON.

No copies nada de `<CARPETA_TEMPORAL>` al repo.

- [ ] **Paso 11: Commit**

```bash
git add src/copiloto_triaje/validacion/informe.py scripts/validar_combinacion.py tests/test_informe.py tests/test_validar_combinacion.py
git commit -m "feat(validacion): el documento de analisis, generado desde el JSON (SP5-B1 T6)" -m "informe.redactar compone el Markdown leyendo resultados_simulacion.json: ninguna cifra se teclea y las frases de la lectura se cuentan sobre las tablas. El script lo escribe con las figuras que haya, tambien con --solo-documento. Las pruebas de main() desvian el analisis a una carpeta temporal." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 7: La corrida real: resultados, figuras y análisis publicados

Hasta aquí todo se ha probado con rejillas mínimas y en carpetas temporales.
Esta tarea corre la simulación entera —25 celdas, 1 000 réplicas en 0A y en
las seis destacadas—, versiona lo que sale y deja en la suite la prueba que
vigila que lo versionado corresponde a los insumos y al código de hoy.

**Ficheros:**
- Crear: `tests/test_resultados_publicados.py`
- Crear (generados por el script, no a mano): `docs/validacion-semisintetica/resultados_simulacion.json`,
  los diez PNG de `docs/validacion-semisintetica/` y `docs/validacion-semisintetica-sp5.md`
- Modificar: `docs/validacion-semisintetica/README.md`

**Interfaces:**
- Consume: `scripts/validar_combinacion.py` entero (tareas 4, 5 y 6):
  `slug_de_celda`, `FIGURAS_GLOBALES`, `figuras_presentes`; `informe.redactar(resultados, figuras)`;
  `simulacion.evaluar_celda`, `simulacion.aplanar`, `simulacion.cargar_conjunto`;
  `datos.huella_de_texto`; la fixture `validar` de `tests/conftest.py`.
- Produce: los artefactos publicados y `tests/test_resultados_publicados.py`.

**La simulación es determinista.** Con las crudas congeladas, el calibrador
versionado y las semillas del plan, la corrida da siempre las mismas cifras.
Las de referencia, medidas al escribir este plan, están en el paso 4: si la
corrida no las da, algo de las tareas 1 a 6 no es lo que el plan dice, y
**no se versiona nada** hasta saber qué.

- [ ] **Paso 1: Escribir la prueba que vigila lo publicado**

Crea `tests/test_resultados_publicados.py` con este contenido:

```python
"""Lo publicado de la simulación semisintética (spec de SP5 §4.8, §11.2-§11.3):
el JSON versionado corresponde a los insumos y al código de hoy, y el
documento y las figuras salen de él.

No vuelve a correr el bootstrap (son minutos): recalcula la estimación
puntual de dos celdas y la compara con la publicada, y regenera el documento
desde el JSON para comprobar que el versionado es ese. Si alguien cambia las
crudas, el calibrador, el generador, el oráculo, las métricas o el documento
sin volver a correr `scripts/validar_combinacion.py`, esto falla.
"""
import json
import os

import pytest

from copiloto_triaje.validacion import datos, informe, metricas, oraculo, simulacion

RESULTADOS = datos.CARPETA / "resultados_simulacion.json"
ANALISIS = datos.REPO / "docs" / "validacion-semisintetica-sp5.md"
ROTULO = "simulación semisintética"
MEDIDO = ("modelos", "pareadas", "horquilla", "discordantes", "no_se")


@pytest.fixture(scope="module")
def publicados():
    return json.loads(RESULTADOS.read_text(encoding="utf-8"))


def _celda(publicados, nombre):
    return next(c for c in publicados["celdas"] if c["nombre"] == nombre)


def test_llevan_el_rotulo_y_las_huellas_de_los_insumos_de_hoy(publicados):
    assert publicados["rotulo"] == ROTULO and ROTULO in publicados["titulo"]
    i = publicados["insumos"]
    assert i["crudas"] == "docs/validacion-semisintetica/crudas_prueba.csv"
    assert i["calibrador"] == "servidor/calibrador.json"
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)


def test_son_la_rejilla_entera_con_mil_replicas_en_0a_y_las_destacadas(publicados):
    p = publicados["parametros"]
    assert p["replicas"] == simulacion.B_REPLICAS == 1000
    assert p["epsilon"] == metricas.EPSILON
    assert p["rejilla"] == list(oraculo.RHO_REJILLA)
    assert [tuple(d) for d in p["destacadas"]] == list(oraculo.CELDAS_DESTACADAS)
    celdas = publicados["celdas"]
    assert len(celdas) == 25
    assert [(c["rho1"], c["rho0"]) for c in celdas] == [
        (a, b) for a in oraculo.RHO_REJILLA for b in oraculo.RHO_REJILLA]
    destacadas = {(c["rho1"], c["rho0"]) for c in celdas if c["destacada"]}
    assert destacadas == set(oraculo.CELDAS_DESTACADAS)
    con_intervalos = {(c["rho1"], c["rho0"]) for c in celdas if "intervalos" in c}
    assert con_intervalos == destacadas | {(0.0, 0.0)}
    assert all(c["replicas"] == 1000 for c in celdas if "intervalos" in c)
    assert {(c["rho1"], c["rho0"]) for c in celdas
            if "sensibilidad_al_previo" in c} == con_intervalos


def test_la_fila_0a_publicada_es_la_comprobacion_de_la_metrica(publicados):
    cero = _celda(publicados, "0A")
    for lado in ("todos", "a_favor", "en_contra"):
        h = cero["horquilla"][lado]
        assert (h["bajo"], h["sobre"], h["contencion"]) == (0.0, 0.0, 1.0)
        assert cero["intervalos"][f"horquilla.{lado}.contencion"] == [1.0, 1.0]
        assert cero["intervalos"][f"horquilla.{lado}.bajo"] == [0.0, 0.0]
        assert cero["intervalos"][f"horquilla.{lado}.sobre"] == [0.0, 0.0]
    assert cero["hipotesis"]["se_sostiene"] is True
    assert "optimismo_de_la_derivacion" in cero


@pytest.mark.parametrize("nombre, rho1, rho0", [("0A", 0.0, 0.0), ("(0,3; 0,3)", 0.3, 0.3)])
def test_el_codigo_de_hoy_reproduce_las_cifras_publicadas(publicados, nombre, rho1, rho0):
    publicada = _celda(publicados, nombre)
    hoy = simulacion.evaluar_celda(simulacion.cargar_conjunto(), rho1, rho0,
                                   con_sensibilidad=True)
    assert hoy["recuentos"] == publicada["recuentos"]
    a = simulacion.aplanar({k: hoy[k] for k in MEDIDO})
    b = simulacion.aplanar({k: publicada[k] for k in MEDIDO})
    assert set(a) == set(b)
    for ruta in a:
        assert a[ruta] == pytest.approx(b[ruta], abs=1e-9), ruta
    assert simulacion.aplanar(hoy["escala_legible"]) == pytest.approx(
        simulacion.aplanar(publicada["escala_legible"]), abs=1e-9)
    assert simulacion.aplanar(hoy["sensibilidad_al_previo"]) == pytest.approx(
        simulacion.aplanar(publicada["sensibilidad_al_previo"]), abs=1e-9)


def test_cada_intervalo_publicado_esta_bien_formado(publicados):
    for celda in publicados["celdas"]:
        for ruta, (li, ls) in celda.get("intervalos", {}).items():
            assert li is not None and ls is not None and li <= ls, (celda["nombre"], ruta)


def test_las_figuras_publicadas_son_las_de_las_celdas_del_json(publicados, validar):
    esperadas = sorted(
        [f"fiabilidad_{validar.slug_de_celda(c)}.png" for c in publicados["celdas"]
         if c["nombre"] == "0A" or c["destacada"]]
        + [f"{nombre}.png" for nombre in validar.FIGURAS_GLOBALES])
    presentes = validar.figuras_presentes(datos.CARPETA)
    assert [p.name for p in presentes] == esperadas
    assert len(esperadas) == 10
    from PIL import Image
    for ruta in presentes:
        with Image.open(ruta) as imagen:
            assert imagen.info["dpi"] == pytest.approx((300, 300), abs=1), ruta.name
            assert ROTULO in imagen.info["Title"], ruta.name


def test_el_documento_versionado_es_el_que_sale_del_json(publicados, validar):
    figuras = validar.figuras_presentes(datos.CARPETA)
    enlaces = {f.stem: os.path.relpath(f, ANALISIS.parent).replace(os.sep, "/")
               for f in figuras}
    esperado = informe.redactar(publicados, enlaces)
    versionado = ANALISIS.read_text(encoding="utf-8")       # newline=None: CRLF y LF valen igual
    assert versionado == esperado
    assert versionado.startswith("# ") and ROTULO in versionado.splitlines()[0]
    assert "validacion-semisintetica/fiabilidad_0a.png" in versionado
```

- [ ] **Paso 2: Correrla y ver que falla**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_resultados_publicados.py -q`

Esperado: `8 errors`, todos en la fixture `publicados`, con
`FileNotFoundError` sobre `resultados_simulacion.json`: todavía no se ha
publicado nada.

- [ ] **Paso 3: La corrida real**

Tarda entre 3 y 5 minutos con 7 procesos (hasta 12 en serie): lánzala con un
tiempo límite de 10 minutos o en segundo plano.

Orden: `C:/venv-copiloto/Scripts/python.exe scripts/validar_combinacion.py`

Esperado, en este orden: una línea `resultados: …resultados_simulacion.json`;
diez líneas `figura: …` (`fiabilidad_0a.png`, `fiabilidad_r1-000_r0-030.png`,
`fiabilidad_r1-000_r0-060.png`, `fiabilidad_r1-030_r0-000.png`,
`fiabilidad_r1-030_r0-030.png`, `fiabilidad_r1-060_r0-000.png`,
`fiabilidad_r1-060_r0-060.png`, `horquilla_por_celda.png`,
`contencion_rejilla.png`, `pendiente_rejilla.png`); y una línea
`análisis: …validacion-semisintetica-sp5.md`. Código de salida 0.

- [ ] **Paso 4: Contrastar con las cifras de referencia**

Orden:

```bash
C:/venv-copiloto/Scripts/python.exe -c "
import json
r = json.load(open('docs/validacion-semisintetica/resultados_simulacion.json', encoding='utf-8'))
print(r['parametros']['replicas'], len(r['celdas']))
for c in r['celdas']:
    if 'intervalos' in c:
        h, i = c['horquilla']['todos'], c['intervalos']
        print(c['nombre'], round(100 * h['contencion'], 1), [round(100 * x, 1) for x in i['horquilla.todos.contencion']],
              round(100 * h['bajo'], 1), round(100 * h['sobre'], 1),
              round(c['modelos']['independencia']['pendiente'], 3))
print([c['nombre'] for c in r['celdas'] if c['hipotesis']['se_sostiene']])
"
```

Esperado, exactamente:

```
1000 25
0A 100.0 [100.0, 100.0] 0.0 0.0 1.025
(0; 0,3) 43.7 [40.6, 46.2] 10.9 45.4 0.87
(0; 0,6) 17.4 [16.0, 19.9] 28.6 54.0 0.756
(0,3; 0) 50.5 [47.4, 52.7] 32.7 16.8 0.932
(0,3; 0,3) 70.7 [68.9, 74.0] 29.3 0.0 0.788
(0,6; 0) 19.2 [17.4, 22.0] 57.2 23.5 0.865
(0,6; 0,6) 44.8 [43.5, 48.6] 55.2 0.0 0.648
['0A', '(0,15; 0,15)']
```

Si alguna cifra difiere, **para**: no toques las cifras de este paso ni las
pruebas. Informa con estado BLOCKED y la salida completa.

- [ ] **Paso 5: Mirar las figuras y leer el análisis**

Las pruebas comprueban nombres, DPI y rótulo; que se lean bien solo se ve
mirando. Abre `horquilla_por_celda.png`, `contencion_rejilla.png`,
`pendiente_rejilla.png` y `fiabilidad_r1-060_r0-060.png` y comprueba que el
título cabe y acaba en «— simulación semisintética», que ningún texto se
solapa y que las cifras van con coma decimal. Lee
`docs/validacion-semisintetica-sp5.md` entero: no puede aparecer `nan`,
`None` ni `{{`, las tablas tienen que leerse, y la sección «Lo que esta
simulación puede afirmar y lo que no» tiene que estar.

- [ ] **Paso 6: Correr la prueba y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_resultados_publicados.py -q`

Esperado: `8 passed`.

- [ ] **Paso 7: El README de la carpeta dice qué es cada cosa**

En `docs/validacion-semisintetica/README.md`, sustituye el primer párrafo (el
que empieza por «**Todo lo que hay en esta carpeta, salvo `crudas_prueba.csv`,
es resultado» y acaba en «lleva ese rótulo en su título.») por:

```markdown
**Todo lo que hay en esta carpeta, salvo `crudas_prueba.csv` y
`latencia.json`, es resultado de una simulación semisintética** (spec de
SP5, §4): las placas y sus etiquetas son reales (conjunto de prueba de
RSNA), la clínica se sortea con la distribución publicada de la puntuación
de Heckerling, y la dependencia entre clínica e imagen es un supuesto
declarado. Nada de aquí mide exactitud clínica en pacientes. Cada tabla,
figura y JSON de resultados lleva ese rótulo en su título.

## `resultados_simulacion.json`

Lo escribe `scripts/validar_combinacion.py`. Lleva el rótulo, las huellas de
los insumos (las crudas congeladas, los pesos con que se generaron y el
calibrador), las semillas y los parámetros, la calibración de la imagen sola
y las 25 celdas `(ρ1, ρ0)` de la rejilla: en cada una, los cuatro modelos
puntuales, las diferencias pareadas frente a la imagen sola, la posición, las
colas y la contención de la horquilla frente al oráculo por lado de la
imagen, los casos discordantes, los del asma desconocida y la escala
legible. 0A y las seis celdas destacadas llevan además los intervalos del
95 % (bootstrap de 1 000 réplicas) y la sensibilidad al previo; 0A, el
cálculo 0C. No lleva fecha: dos corridas dan el mismo fichero.

## Las figuras (`fiabilidad_*.png`, `horquilla_por_celda.png`, `contencion_rejilla.png`, `pendiente_rejilla.png`)

A 300 DPI, dibujadas **leyendo** `resultados_simulacion.json`. Cada una lleva
«simulación semisintética» en el título, que va también en el metadato
`Title` del PNG.

## El análisis

`docs/validacion-semisintetica-sp5.md`, una carpeta más arriba. Lo redacta
`src/copiloto_triaje/validacion/informe.py` desde el mismo JSON: ninguna
cifra se teclea y el documento no se edita a mano.

## Cómo se regenera todo

    python scripts/validar_combinacion.py

Sin los pesos, sin red y sin contenedores; de 3 a 5 minutos. Con
`--solo-documento` se regeneran las figuras y el análisis sin recalcular.
`tests/test_resultados_publicados.py` falla si lo versionado deja de
corresponder a los insumos o al código.
```

- [ ] **Paso 8: Los vecinos**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_resultados_publicados.py tests/test_validar_combinacion.py tests/test_informe.py tests/test_simulacion.py tests/test_metricas.py -q`

Esperado: todo en verde.

- [ ] **Paso 9: Commit**

```bash
git add tests/test_resultados_publicados.py docs/validacion-semisintetica/resultados_simulacion.json docs/validacion-semisintetica/*.png docs/validacion-semisintetica-sp5.md docs/validacion-semisintetica/README.md
git status --short
```

Comprueba con `git status --short` que en el índice están el JSON, los diez
PNG, el análisis, el README y la prueba, y nada más. Entonces:

```bash
git commit -m "feat(validacion): la simulación semisintética, publicada: resultados, figuras y análisis" -m "La rejilla de 25 celdas con 1 000 réplicas de bootstrap en 0A y en las seis destacadas. La fila 0A sale con colas 0 y contención 100 %; la hipótesis del 90 % solo se sostiene en 0A y en (0,15; 0,15). El análisis se genera desde el JSON, sin teclear ninguna cifra, y una prueba vigila que lo versionado corresponde a los insumos y al código." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 8: La latencia de extremo a extremo

Spec de SP5 §6.3. La latencia NO es simulación: es una medición del sistema
desplegado con casos de prueba. Esta tarea no habla con ningún sistema: deja
el instrumento (el arnés escribe `latencias.json`; un script lo resume en
`latencia.json`) y lo prueba con filas fabricadas. La corrida real con bots
la hace después una persona, con el túnel y los secretos.

**Ficheros:**
- Crear: `scripts/medir_latencia.py`
- Crear: `tests/test_medir_latencia.py`
- Modificar: `pruebas/reproducir_casos.py` (dos funciones nuevas entre `escribir_corpus` y el resumen; una llamada en `main()`)
- Modificar: `docs/sp5-sesion.md` (sección nueva «6. Medir la latencia» y el párrafo de lo que se versiona)
- Modificar: `docs/validacion-semisintetica/README.md` (sección nueva `latencia.json`, al final)
- Prueba: `tests/test_reproducir_casos.py` (tres pruebas nuevas, al final), `tests/test_medir_latencia.py`

**Interfaces:**
- Consume: de `pruebas/reproducir_casos.py`, las filas `(caso, obs, redaccion)` que `main()` ya construye y pasa a `escribir_corpus(destino, filas)` y a `resumen(...)`:
  `caso["patientId"]`, `caso["perfil"].carpeta`; `obs["con_bots"]`, `obs.get("fallo")`, `obs.get("ms_extremo")` (el de la tabla `consultas`; solo con bots), `obs.get("ms_arnes")`;
  `redaccion["error"]`, `redaccion["resultado"]["milisegundos"]` (si hay resultado). `numpy` y `statistics` en el script. Nada de `src/`.
- Produce, en `pruebas/reproducir_casos.py`:
  - `LATENCIAS = "latencias.json"`
  - `filas_de_latencia(filas) -> list[dict]`: una fila por caso, con las claves, en este orden, `patientId`, `perfil`, `con_bots`, `fallo`, `error`, `ms_extremo`, `ms_modelo`, `ms_arnes`.
  - `escribir_latencias(destino, filas) -> pathlib.Path`: escribe `<destino>/latencias.json` (una lista JSON con esas filas) y devuelve la ruta.
  - `main()` llama a `escribir_latencias(destino, filas)` SIEMPRE, justo después de `escribir_corpus(destino, filas)`.
- Produce, en `scripts/medir_latencia.py`:
  - constantes `TITULO`, `TRAMO`, `MINIMO = 30`, `UMBRALES_S = {"minimo": 8, "objetivo": 3}`, `NO_MEDIDO = "no medido"`, `MOTIVOS = ("sin_bots", "fallo", "error", "sin_ms_extremo")`, `CARPETA`, `NOMBRE = "latencia.json"`.
  - `_es_una_medida(v) -> bool` (milisegundos: número finito y no negativo; ni cadena ni booleano).
  - `resumir(filas, minimo=MINIMO, manual=None) -> dict` con las claves, en este orden, `titulo`, `tramo`, `n`, `p50_ms`, `p95_ms`, `minimo_ms`, `maximo_ms`, `modelo_p50_ms`, `umbrales_s`, `frente_a_umbrales` (`{"p50": {"cumple_minimo": bool, "cumple_objetivo": bool}, "p95": {...}}`), `tramo_manual` (`{"valores_s": [...], "n": int, "mediana_s": float}` o `"no medido"`), `descartadas` (`{"total", "sin_bots", "fallo", "error", "sin_ms_extremo"}`). Con menos de `minimo` consultas válidas, `SystemExit`.
  - `leer_manual(texto) -> list[float] | None`: los segundos de `--manual`; `SystemExit` si no son números positivos separados por comas.
  - `main(argv=None) -> int` con `--corrida` (obligatoria), `--salida` (por defecto `docs/validacion-semisintetica/latencia.json`) y `--manual`.

**Avisos para quien ejecuta:**
- Los ficheros del repo tienen finales de línea CRLF en el árbol de trabajo (`core.autocrlf=true`). Las sustituciones de abajo se dan por su texto; si la herramienta de edición compara byte a byte, busca línea por línea.
- `tests/test_reproducir_casos.py` importa `torch` en cadena: que tarde unos segundos en arrancar es normal.
- No se cambia nada más del arnés: ni `resumen()`, ni `escribir_corpus()`, ni `mensajes.json`.
- Todas las órdenes se corren desde la raíz del repo.

- [ ] **Paso 1: Escribir las pruebas del arnés, que fallan**

Añadir AL FINAL de `tests/test_reproducir_casos.py` (después de
`test_mensajes_json_lleva_el_veredicto_coincide_del_bot`, dejando dos líneas
en blanco). No se toca la lista de imports de la cabecera: cada prueba importa
lo suyo, y `_caso`, `PERFILES`, `UN_RESULTADO`, `json` y `sys` ya están en el
fichero.

```python
# --------------------------------------------------------------------------
# latencias.json: lo que `scripts/medir_latencia.py` lee (SP5 §6.3). Filas
# fabricadas: no hay sistema desplegado al que hablar desde una prueba.
# --------------------------------------------------------------------------
CLAVES_DE_LATENCIA = ["patientId", "perfil", "con_bots", "fallo", "error",
                      "ms_extremo", "ms_modelo", "ms_arnes"]


def test_filas_de_latencia_da_una_fila_por_caso_con_lo_que_se_midio():
    from pruebas.reproducir_casos import filas_de_latencia
    bien = {"texto": "x", "texto_paciente": "", "error": None,
            "resultado": UN_RESULTADO}
    rechazo = {"texto": "NO PROCEDE", "texto_paciente": "",
               "error": "fuera_de_alcance: eso", "resultado": None}
    filas = [
        (_caso(pid="p-1"),
         {"con_bots": True, "ms_extremo": 1840, "ms_arnes": 61.5,
          "error": None, "resultado": dict(UN_RESULTADO, milisegundos=150.0)},
         bien),
        (_caso(perfil=PERFILES[4], pid="p-2"),
         {"con_bots": True, "ms_extremo": 410, "ms_arnes": 12.0,
          "error": "otro_codigo: lo que guardo el bot"}, rechazo),
        (_caso(pid="p-3"),
         {"con_bots": True, "fallo": "no se pudo subir la placa",
          "ms_arnes": 60.0}, bien),
        (_caso(pid="p-4"), {"con_bots": False, "ms_arnes": 58.25}, bien),
    ]
    salida = filas_de_latencia(filas)
    assert [list(f) for f in salida] == [CLAVES_DE_LATENCIA] * 4
    assert salida[0] == {
        "patientId": "p-1", "perfil": "03-banda_contradictoria",
        "con_bots": True, "fallo": None, "error": None,
        "ms_extremo": 1840, "ms_modelo": 37.4, "ms_arnes": 61.5}
    # El error es el de la REDACCION y no el que guardo el bot; y sin
    # resultado no hay milisegundos del modelo.
    assert salida[1]["perfil"] == "05-menor_edad"
    assert salida[1]["error"] == "fuera_de_alcance: eso"
    assert salida[1]["ms_modelo"] is None and salida[1]["ms_extremo"] == 410
    assert salida[2]["fallo"] == "no se pudo subir la placa"
    assert salida[2]["ms_extremo"] is None
    assert salida[3]["con_bots"] is False and salida[3]["ms_extremo"] is None
    assert salida[3]["ms_arnes"] == 58.25
    # Tal cual a un fichero: ni perfiles ni tipos que JSON no sepa escribir.
    assert json.loads(json.dumps(salida)) == salida
    assert filas_de_latencia([]) == []


def test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida(tmp_path):
    from pruebas.reproducir_casos import escribir_latencias, filas_de_latencia
    red = {"texto": "x", "texto_paciente": "", "error": None,
           "resultado": UN_RESULTADO}
    filas = [(_caso(pid="p-1"),
              {"con_bots": True, "ms_extremo": 1840, "ms_arnes": 61.5}, red)]
    destino = tmp_path / "no" / "existe"
    ruta = escribir_latencias(destino, filas)
    assert ruta == destino / "latencias.json"
    assert json.loads(ruta.read_text(encoding="utf-8")) == filas_de_latencia(filas)
    # Una corrida posterior lo pisa entero: no se acumulan las de otro dia.
    escribir_latencias(destino, [])
    assert json.loads(ruta.read_text(encoding="utf-8")) == []


def test_main_escribe_latencias_json_tambien_sin_bots(tmp_path, monkeypatch, capsys):
    """`main` escribe SIEMPRE latencias.json, despues del corpus. Aqui sin
    bots y con el copiloto y el redactor suplantados: lo que se ata es que el
    fichero sale, con una fila por caso, y que el corpus sigue saliendo."""
    from pruebas import reproducir_casos as rc
    casos = [_caso(pid="p-1"), _caso(perfil=PERFILES[4], pid="p-2")]
    redacciones = [
        {"texto": "CRIBADO — opacidad probable\nEl cribado marca esta placa",
         "texto_paciente": "", "error": None, "resultado": UN_RESULTADO},
        {"texto": "NO PROCEDE", "texto_paciente": "",
         "error": "fuera_de_alcance: eso", "resultado": None}]
    monkeypatch.setattr(rc, "comprobar_el_copiloto", lambda url: None)
    monkeypatch.setattr(rc, "construir_casos", lambda por_perfil, solo, destino: casos)
    monkeypatch.setattr(rc, "llamar_al_copiloto", lambda *a, **k: (200, ""))
    monkeypatch.setattr(rc, "redactar", lambda lote: redacciones[:len(lote)])
    monkeypatch.setattr(sys, "argv", ["reproducir_casos.py", "--sin-bots",
                                      "--salida", str(tmp_path)])
    assert rc.main() == 0
    capsys.readouterr()
    filas = json.loads((tmp_path / "latencias.json").read_text(encoding="utf-8"))
    assert [f["patientId"] for f in filas] == ["p-1", "p-2"]
    assert [list(f) for f in filas] == [CLAVES_DE_LATENCIA] * 2
    assert all(f["con_bots"] is False and f["ms_extremo"] is None for f in filas)
    assert all(isinstance(f["ms_arnes"], float) for f in filas)
    assert filas[0]["ms_modelo"] == 37.4 and filas[1]["error"].startswith("fuera_de_alcance")
    # El arnes sigue haciendo lo de siempre.
    assert (tmp_path / "RESUMEN.txt").is_file()
    assert (tmp_path / "03-banda_contradictoria" / "p-1.txt").is_file()
```

- [ ] **Paso 2: Correrlas y ver el fallo**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_reproducir_casos.py -k latencia
```

Salida esperada: `3 failed` y el resto sin seleccionar. Las dos primeras fallan con
`ImportError: cannot import name 'filas_de_latencia' from 'pruebas.reproducir_casos'`
(la segunda, con `escribir_latencias`), y la tercera llega hasta el final de
`main()` y falla al leer el fichero: `FileNotFoundError: ... latencias.json`.
Ese tercer fallo es el que interesa: dice que `main()` corre entero con el
copiloto y el redactor suplantados, y que lo único que falta es el fichero.

```
FAILED tests/test_reproducir_casos.py::test_filas_de_latencia_da_una_fila_por_caso_con_lo_que_se_midio
FAILED tests/test_reproducir_casos.py::test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida
FAILED tests/test_reproducir_casos.py::test_main_escribe_latencias_json_tambien_sin_bots
3 failed
```

- [ ] **Paso 3: Escribir `filas_de_latencia` y `escribir_latencias`, y llamarla en `main()`**

En `pruebas/reproducir_casos.py`, DOS cambios.

Primero, insertar el bloque siguiente entre el final de `escribir_corpus` y
la cabecera del resumen. Buscar este texto (la última línea de
`escribir_corpus` y el comentario que abre la sección del resumen):

```python
            texto_del_caso(caso, obs, redaccion), encoding="utf-8")


# --------------------------------------------------------------------------
# El resumen: tiene que decir algo que no supieramos
```

y sustituirlo por:

```python
            texto_del_caso(caso, obs, redaccion), encoding="utf-8")


# --------------------------------------------------------------------------
# Las latencias, caso a caso, para `scripts/medir_latencia.py` (SP5 §6.3)
# --------------------------------------------------------------------------
LATENCIAS = "latencias.json"


def filas_de_latencia(filas):
    """Una fila por caso con lo que esta corrida midio, lista para JSON.

    `ms_extremo` es el de `consultas` y solo existe con bots: lo escribe el
    flujo, desde que `Normalizar update` recibe el update con la placa hasta
    que `Desenlace` compone la respuesta. `ms_modelo` es lo que el servidor
    dice que tardo el modelo, y `ms_arnes` la ida y vuelta de este arnes con
    el copiloto: ninguno de los dos es la latencia de extremo a extremo.

    El `error` es el de la redaccion, el mismo que cuenta el resumen. Aqui no
    se filtra ni se resume nada: que filas cuentan lo decide quien mide.
    """
    salida = []
    for caso, obs, redaccion in filas:
        resultado = redaccion.get("resultado") or {}
        salida.append({
            "patientId": caso["patientId"],
            "perfil": caso["perfil"].carpeta,
            "con_bots": bool(obs.get("con_bots")),
            "fallo": obs.get("fallo"),
            "error": redaccion.get("error"),
            "ms_extremo": obs.get("ms_extremo"),
            "ms_modelo": resultado.get("milisegundos"),
            "ms_arnes": obs.get("ms_arnes"),
        })
    return salida


def escribir_latencias(destino, filas):
    """Escribe `<destino>/latencias.json`, pisando el de la corrida anterior."""
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / LATENCIAS
    ruta.write_text(json.dumps(filas_de_latencia(filas), ensure_ascii=False,
                               indent=1), encoding="utf-8")
    return ruta


# --------------------------------------------------------------------------
# El resumen: tiene que decir algo que no supieramos
```

Segundo, en `main()`, casi al final. Buscar:

```python
    escribir_corpus(destino, filas)
    texto = resumen(filas, con_bots, destino, url_copiloto)
```

y sustituirlo por:

```python
    escribir_corpus(destino, filas)
    # Siempre, tambien sin bots: `scripts/medir_latencia.py` decide que filas
    # cuentan, y una corrida sin bots tiene que poder decir que no midio nada.
    escribir_latencias(destino, filas)
    texto = resumen(filas, con_bots, destino, url_copiloto)
```

- [ ] **Paso 4: Correr y ver el verde, con el fichero entero**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_reproducir_casos.py
```

Salida esperada (el aviso es de una dependencia y ya estaba):

```
ningún fallo: las tres nuevas pasan y las que había siguen pasando
```

- [ ] **Paso 5: Commit**

```bash
git add pruebas/reproducir_casos.py tests/test_reproducir_casos.py
git commit -m "feat(arnes): latencias.json, una fila por caso con lo que midio la corrida (SP5-B1 T8)" -m "El arnes escribe siempre <salida>/latencias.json despues del corpus: patientId, perfil, con_bots, fallo, error, ms_extremo, ms_modelo y ms_arnes. No filtra ni resume: eso lo hace scripts/medir_latencia.py." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Paso 6: Escribir las pruebas del script, que fallan**

`tests/test_medir_latencia.py` (fichero nuevo):

```python
# -*- coding: utf-8 -*-
"""La latencia de extremo a extremo (spec de SP5 §6.3), con filas fabricadas.

No hay sistema desplegado al que hablar desde una prueba: las filas son las
que `pruebas/reproducir_casos.py` deja en `latencias.json`, escritas a mano.
Lo que se ata es que filas cuentan, que cifras salen de ellas y que con
menos de 30 no se escribe nada: la latencia queda «no medida».
"""
import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def medir():
    """`scripts/medir_latencia.py` cargado como modulo."""
    spec = importlib.util.spec_from_file_location(
        "medir_latencia", REPO / "scripts" / "medir_latencia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fila(ms_extremo=1000, ms_modelo=150.0, **cambios):
    fila = {"patientId": "p", "perfil": "01-positiva_clara", "con_bots": True,
            "fallo": None, "error": None, "ms_extremo": ms_extremo,
            "ms_modelo": ms_modelo, "ms_arnes": 60.0}
    fila.update(cambios)
    return fila


def _validas(n=40):
    """n consultas validas de 1000, 1100, 1200... ms."""
    return [_fila(ms_extremo=1000 + 100 * i, ms_modelo=140.0 + i) for i in range(n)]


def test_resumir_da_p50_y_p95_de_las_consultas_validas(medir):
    r = medir.resumir(_validas(40))
    assert r["n"] == 40
    assert r["p50_ms"] == 2950.0
    assert r["p95_ms"] == 4705.0
    assert r["minimo_ms"] == 1000.0 and r["maximo_ms"] == 4900.0
    assert r["modelo_p50_ms"] == 159.5
    assert r["umbrales_s"] == {"minimo": 8, "objetivo": 3}
    assert r["frente_a_umbrales"] == {
        "p50": {"cumple_minimo": True, "cumple_objetivo": True},
        "p95": {"cumple_minimo": True, "cumple_objetivo": False}}
    assert r["descartadas"] == {"total": 0, "sin_bots": 0, "fallo": 0,
                                "error": 0, "sin_ms_extremo": 0}
    assert r["tramo_manual"] == "no medido"


def test_el_titulo_dice_que_es_una_medicion_y_el_tramo_dice_que_excluye(medir):
    r = medir.resumir(_validas(30))
    assert r["titulo"] == ("Latencia de extremo a extremo: medición con el "
                           "arnés sobre el sistema desplegado (no es una "
                           "simulación)")
    for trozo in ("`Normalizar update`", "`Desenlace`", "la subida a Telegram",
                  "la entrega del webhook", "el envío de `Responder`"):
        assert trozo in r["tramo"], trozo
    assert list(r) == ["titulo", "tramo", "n", "p50_ms", "p95_ms", "minimo_ms",
                       "maximo_ms", "modelo_p50_ms", "umbrales_s",
                       "frente_a_umbrales", "tramo_manual", "descartadas"]


def test_solo_cuentan_las_consultas_con_bots_sin_fallo_ni_error(medir):
    filas = _validas(30) + [
        _fila(con_bots=False, ms_extremo=None),
        _fila(con_bots=False, ms_extremo=None),
        _fila(fallo="no se pudo subir la placa", ms_extremo=None),
        _fila(error="fuera_de_alcance: eso", ms_extremo=90000, ms_modelo=None),
        _fila(ms_extremo=None),
        # Cada fila se descarta por UN motivo, el primero que le toca.
        _fila(con_bots=False, fallo="x", error="y", ms_extremo=None),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 30
    assert r["maximo_ms"] == 3900.0, "el rechazo de 90 s no cuenta"
    assert r["descartadas"] == {"total": 6, "sin_bots": 3, "fallo": 1,
                                "error": 1, "sin_ms_extremo": 1}


def test_los_umbrales_se_comparan_en_segundos_y_el_limite_cumple(medir):
    r = medir.resumir([_fila(ms_extremo=3000)] * 20 + [_fila(ms_extremo=8000)] * 10,
                      minimo=30)
    assert r["p50_ms"] == 3000.0 and r["p95_ms"] == 8000.0
    assert r["frente_a_umbrales"] == {
        "p50": {"cumple_minimo": True, "cumple_objetivo": True},
        "p95": {"cumple_minimo": True, "cumple_objetivo": False}}
    lento = medir.resumir([_fila(ms_extremo=8001)] * 30)
    assert lento["frente_a_umbrales"]["p50"] == {"cumple_minimo": False,
                                                 "cumple_objetivo": False}


def test_los_umbrales_se_comparan_sin_redondear(medir):
    """8 000,04 ms se escribe «8000,0», pero no cumple los 8 s."""
    r = medir.resumir([_fila(ms_extremo=8000.04)] * 30)
    assert r["p50_ms"] == 8000.0 and r["p95_ms"] == 8000.0
    assert r["frente_a_umbrales"]["p50"] == {"cumple_minimo": False,
                                             "cumple_objetivo": False}


def test_un_ms_extremo_que_no_es_una_medida_se_descarta(medir):
    malas = [_fila(ms_extremo="1500"), _fila(ms_extremo=True), _fila(ms_extremo=-1),
             _fila(ms_extremo=float("nan")), _fila(ms_extremo=float("inf"))]
    r = medir.resumir(_validas(30) + malas)
    assert r["n"] == 30 and r["maximo_ms"] == 3900.0
    assert r["descartadas"] == {"total": 5, "sin_bots": 0, "fallo": 0,
                                "error": 0, "sin_ms_extremo": 5}
    # y un ms_modelo que no es una medida no entra en la mediana del modelo
    r = medir.resumir([_fila(ms_modelo="x")] * 15 + [_fila(ms_modelo=150.0)] * 15)
    assert r["modelo_p50_ms"] == 150.0


def test_con_menos_del_minimo_no_se_mide_y_dice_cuantas_hay(medir):
    filas = _validas(29) + [_fila(error="fuera_de_alcance: eso")]
    with pytest.raises(SystemExit) as salida:
        medir.resumir(filas)
    mensaje = str(salida.value)
    assert "29 consultas" in mensaje and "30" in mensaje
    assert "no medida" in mensaje
    with pytest.raises(SystemExit, match="0 consultas"):
        medir.resumir([])
    assert medir.resumir(filas, minimo=29)["n"] == 29


def test_el_tramo_manual_lleva_los_valores_y_su_mediana(medir):
    r = medir.resumir(_validas(30), manual=[5.2, 4.8, 6.1, 5.0, 5.5])
    assert r["tramo_manual"] == {"valores_s": [5.2, 4.8, 6.1, 5.0, 5.5],
                                 "n": 5, "mediana_s": 5.2}
    assert medir.resumir(_validas(30), manual=[])["tramo_manual"] == "no medido"


def test_leer_manual_acepta_segundos_con_punto_y_rechaza_lo_demas(medir):
    assert medir.leer_manual("5.2,4.8, 6.1,5.0,5.5") == [5.2, 4.8, 6.1, 5.0, 5.5]
    assert medir.leer_manual(None) is None
    for malo in ("5.2;4.8", "cinco", "5.2,,4.8", "5.2,-1", "5.2,0", ""):
        with pytest.raises(SystemExit, match="--manual"):
            medir.leer_manual(malo)


def test_la_cli_escribe_el_json_y_no_lo_escribe_si_no_hay_minimo(medir, tmp_path, capsys):
    corrida = tmp_path / "corpus" / "latencias.json"
    corrida.parent.mkdir()
    corrida.write_text(json.dumps(_validas(36)), encoding="utf-8")
    salida = tmp_path / "docs" / "latencia.json"
    assert medir.main(["--corrida", str(corrida), "--salida", str(salida),
                       "--manual", "5.2,4.8,6.1,5.0,5.5"]) == 0
    escrito = json.loads(salida.read_text(encoding="utf-8"))
    assert escrito == medir.resumir(_validas(36), manual=[5.2, 4.8, 6.1, 5.0, 5.5])
    assert "simulación)" in salida.read_text(encoding="utf-8"), "sin escapes \\u"
    dicho = capsys.readouterr().out
    assert "36 consultas" in dicho and "p50 2,75 s" in dicho and "p95 4,33 s" in dicho

    corta = tmp_path / "corta.json"
    corta.write_text(json.dumps(_validas(12)), encoding="utf-8")
    otra = tmp_path / "no-se-escribe.json"
    with pytest.raises(SystemExit, match="12 consultas"):
        medir.main(["--corrida", str(corta), "--salida", str(otra)])
    assert not otra.exists()


def test_la_cli_rechaza_una_corrida_que_no_existe_o_no_es_una_lista(medir, tmp_path):
    with pytest.raises(SystemExit, match="no existe"):
        medir.main(["--corrida", str(tmp_path / "nada.json"),
                    "--salida", str(tmp_path / "s.json")])
    rara = tmp_path / "rara.json"
    rara.write_text(json.dumps({"filas": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="no es una lista"):
        medir.main(["--corrida", str(rara), "--salida", str(tmp_path / "s.json")])
```

- [ ] **Paso 7: Correrlas y ver el fallo**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_medir_latencia.py
```

Salida esperada: las once pruebas dan ERROR en la fixture `medir`, con
`FileNotFoundError: [Errno 2] No such file or directory: '...scripts\\medir_latencia.py'`
(el script no existe todavía):

```
11 errors
```

- [ ] **Paso 8: Escribir el script**

`scripts/medir_latencia.py` (fichero nuevo):

```python
# -*- coding: utf-8 -*-
"""Mide la latencia de extremo a extremo: de latencias.json del arnes a latencia.json.

USO
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "5.2,4.8,6.1,5.0,5.5"

Lee el `latencias.json` que deja una corrida CON BOTS de
`pruebas/reproducir_casos.py` contra el sistema desplegado y escribe
docs/validacion-semisintetica/latencia.json (spec de SP5 §6.3). Es una
MEDICION, no una simulacion: lo dice el titulo del JSON.

Cuenta solo las consultas que pasaron por los bots, llegaron al final, no
dieron error y llevan `ms_extremo`. Con menos de 30 no escribe nada: la
latencia queda «no medida», y el informe lo dice con la causa.

`--manual` son segundos medidos a mano en el cliente de Telegram (hora del
envio de la placa frente a hora de la respuesta), en los 5 casos con que se
acota el tramo que `ms_extremo` no ve.
"""
import argparse
import json
import math
import pathlib
import statistics
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
CARPETA = REPO / "docs" / "validacion-semisintetica"
NOMBRE = "latencia.json"

TITULO = ("Latencia de extremo a extremo: medición con el arnés sobre el "
          "sistema desplegado (no es una simulación)")
TRAMO = ("`ms_extremo` de la tabla `consultas`: desde que `Normalizar update` "
         "recibe el update con la placa hasta que `Desenlace` compone la "
         "respuesta. Excluye la subida a Telegram, la entrega del webhook y "
         "el envío de `Responder`: no es el tiempo desde que el profesional "
         "sube la radiografía hasta que recibe el pre-informe.")
MINIMO = 30
UMBRALES_S = {"minimo": 8, "objetivo": 3}
NO_MEDIDO = "no medido"
# Los motivos de descarte, en el orden en que se miran: cada fila cuenta en
# uno solo, el primero que le toca.
MOTIVOS = ("sin_bots", "fallo", "error", "sin_ms_extremo")


def _es_una_medida(v) -> bool:
    """Unos milisegundos: un numero finito y no negativo. Ni `None`, ni una
    cadena, ni un booleano (`True` contaria como 1 ms)."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v >= 0)


def _motivo(fila):
    """Por que una fila no cuenta, o None si cuenta."""
    if not fila.get("con_bots"):
        return "sin_bots"
    if fila.get("fallo"):
        return "fallo"
    if fila.get("error"):
        return "error"
    if not _es_una_medida(fila.get("ms_extremo")):
        return "sin_ms_extremo"
    return None


def _frente_a(ms):
    return {"cumple_minimo": bool(ms <= UMBRALES_S["minimo"] * 1000),
            "cumple_objetivo": bool(ms <= UMBRALES_S["objetivo"] * 1000)}


def resumir(filas, minimo=MINIMO, manual=None) -> dict:
    """El contenido de latencia.json, desde las filas de latencias.json.

    `manual` son los segundos del tramo que falta, medidos a mano; sin ellos,
    `tramo_manual` dice «no medido». Con menos de `minimo` consultas validas
    sale con `SystemExit`: no hay cifra que dar.
    """
    descartadas = {"total": 0, **{m: 0 for m in MOTIVOS}}
    validas = []
    for fila in filas:
        motivo = _motivo(fila)
        if motivo is None:
            validas.append(fila)
        else:
            descartadas[motivo] += 1
            descartadas["total"] += 1
    if len(validas) < minimo:
        raise SystemExit(
            f"hay {len(validas)} consultas con bots, sin fallo ni error y con "
            f"ms_extremo, y hacen falta {minimo}: la latencia de extremo a "
            f"extremo queda «no medida» y no se escribe nada "
            f"(descartadas: {descartadas})")

    ms = np.array([float(f["ms_extremo"]) for f in validas])
    # Los umbrales se comparan con el percentil SIN redondear: 8 000,04 ms se
    # escribe «8000,0» y no cumple los 8 s. Se redondea solo lo que se escribe.
    p50, p95 = (float(v) for v in np.percentile(ms, [50, 95]))
    modelo = [float(f["ms_modelo"]) for f in validas if _es_una_medida(f.get("ms_modelo"))]
    manual = [float(v) for v in (manual or [])]
    return {
        "titulo": TITULO,
        "tramo": TRAMO,
        "n": len(validas),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "minimo_ms": round(float(ms.min()), 1),
        "maximo_ms": round(float(ms.max()), 1),
        "modelo_p50_ms": round(statistics.median(modelo), 1) if modelo else None,
        "umbrales_s": dict(UMBRALES_S),
        "frente_a_umbrales": {"p50": _frente_a(p50), "p95": _frente_a(p95)},
        "tramo_manual": ({"valores_s": manual, "n": len(manual),
                          "mediana_s": round(statistics.median(manual), 2)}
                         if manual else NO_MEDIDO),
        "descartadas": descartadas,
    }


def leer_manual(texto):
    """Los segundos de `--manual`: separados por comas y con punto decimal."""
    if texto is None:
        return None
    try:
        valores = [float(trozo) for trozo in texto.split(",")]
    except ValueError:
        valores = []
    if not valores or any(not 0 < v < float("inf") for v in valores):
        raise SystemExit(
            f"--manual espera segundos positivos separados por comas y con "
            f"punto decimal, como \"5.2,4.8,6.1,5.0,5.5\"; llegó «{texto}»")
    return valores


def _segundos(ms):
    return f"{ms / 1000:.2f}".replace(".", ",") + " s"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corrida", required=True,
                   help="el latencias.json de una corrida con bots del arnés")
    p.add_argument("--salida", default=str(CARPETA / NOMBRE))
    p.add_argument("--manual", metavar="SEGUNDOS",
                   help="el tramo que falta, medido a mano en el cliente de "
                        "Telegram: \"5.2,4.8,6.1,5.0,5.5\"")
    args = p.parse_args(argv)

    manual = leer_manual(args.manual)
    corrida = pathlib.Path(args.corrida)
    if not corrida.is_file():
        raise SystemExit(f"no existe {corrida}: lo escribe una corrida de "
                         f"pruebas/reproducir_casos.py en su carpeta de salida")
    filas = json.loads(corrida.read_text(encoding="utf-8"))
    if not isinstance(filas, list):
        raise SystemExit(f"{corrida} no es una lista de filas de latencia")
    resultado = resumir(filas, manual=manual)

    salida = pathlib.Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n")
    print(f"{resultado['n']} consultas: p50 {_segundos(resultado['p50_ms'])}, "
          f"p95 {_segundos(resultado['p95_ms'])} "
          f"({resultado['descartadas']['total']} descartadas); {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Las cifras de las pruebas salen de `numpy.percentile` con su interpolación
lineal por defecto: con 40 consultas de 1000 a 4900 ms, p50 = 2950 y
p95 = 4705; con 36, p50 = 2750 y p95 = 4325 (que se imprime «4,33 s»).

- [ ] **Paso 9: Correr y ver el verde**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_medir_latencia.py
```

Salida esperada:

```
11 passed
```

Y el script, a mano, sin corrida (sale con código 1 y este mensaje):

```bash
C:/venv-copiloto/Scripts/python.exe scripts/medir_latencia.py --corrida nada.json
```

```
no existe nada.json: lo escribe una corrida de pruebas/reproducir_casos.py en su carpeta de salida
```

- [ ] **Paso 10: Commit**

```bash
git add scripts/medir_latencia.py tests/test_medir_latencia.py
git commit -m "feat(validacion): medir_latencia.py, p50 y p95 de ms_extremo frente a 8 s y 3 s (SP5-B1 T8)" -m "Lee el latencias.json de una corrida con bots y escribe docs/validacion-semisintetica/latencia.json: es una medicion, no una simulacion, y el titulo lo dice. Cuenta solo las consultas con bots, sin fallo ni error y con ms_extremo; con menos de 30 no escribe nada y la latencia queda «no medida». El tramo que ms_extremo no ve se acota a mano con --manual." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Paso 11: Documentar cómo se mide**

En `docs/sp5-sesion.md`, DOS cambios.

Primero, insertar la sección nueva justo ANTES del título
`## Qué se versiona y qué no` (después del último párrafo de «5. El análisis
y el acta», con una línea en blanco antes y otra después):

````markdown
## 6. Medir la latencia

No es parte de la sesión ni es simulación: es una **medición del sistema
desplegado** con casos de prueba (spec de SP5 §6.3). Los mensajes de la
sesión no la miden; hace falta una corrida propia del arnés **con bots**, y
tiene que estar hecha antes del 16-oct: sin ella, la latencia de extremo a
extremo se declara «no medida», con la causa.

Lo pone quien la corre, en el entorno y nunca en un fichero del repositorio:
`N8N_URL` (la dirección del n8n desplegado, p. ej. `https://n8n.ejemplo.test`),
el túnel a la base (`COPILOTO_BD_DSN`), los dos secretos
(`TELEGRAM_SECRET_PRUEBA` y `TELEGRAM_TOKEN_PROFESIONAL`), `CHAT_SUBIDA_PLACAS`
y `COPILOTO_URL`; la cabecera de `pruebas/reproducir_casos.py` dice qué es
cada uno. Si falta `COPILOTO_BD_DSN` o alguno de los dos secretos, el arnés
corre sin bots y no mide nada.

    C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --por-perfil 12 --salida pruebas/corpus/latencia

Solo cuentan las consultas que dan un resultado: los perfiles 01, 02 y 03
(12 cada uno) y el 04 (siempre 1) suman 37, por encima de las 30 que pide el
spec y con margen para alguna conversación que no llegue al final. Los otros
cinco perfiles son rechazos (20 casos más) y se descartan. Con el
`--por-perfil 10` por defecto serían 31: una sola conversación fallida
dejaría la medición sin hacer. Son 57 casos y unos 20 minutos. El arnés
imprime «N casos» al arrancar: si salen menos de 57, algún perfil no tiene 12
placas en la caché y hay que subir `--por-perfil` hasta que las consultas
válidas (`3 × por_perfil + 1`) pasen holgadamente de 30.

La corrida deja `pruebas/corpus/latencia/latencias.json` (una fila por caso;
la carpeta está ignorada). Después:

    C:/venv-copiloto/Scripts/python.exe scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "5.2,4.8,6.1,5.0,5.5"

Escribe `docs/validacion-semisintetica/latencia.json` con el p50 y el p95 de
`ms_extremo` frente a los umbrales de 8 s y 3 s, y cuántas filas se
descartaron y por qué. Con menos de 30 consultas válidas se detiene, lo dice
y no escribe nada.

`ms_extremo` va desde que `Normalizar update` recibe el update con la placa
hasta que `Desenlace` compone la respuesta: no ve la subida a Telegram, la
entrega del webhook ni el envío de `Responder`. Ese tramo se acota **a mano
en 5 casos**, con un chat real y el cliente de Telegram: la hora en que se
envía la placa frente a la hora en que llega la respuesta, en segundos. Son
los valores de `--manual` (con punto decimal y separados por comas); sin
`--manual`, el JSON dice «no medido» en ese tramo.

Al terminar, las filas que el arnés dejó en `consultas` se borran con la
orden que él mismo imprime.
````

Segundo, en el párrafo de «Qué se versiona y qué no». Buscar:

```markdown
Se versionan `sesion.json` y `acta-h7.md` (cifras, `patientId`, estratos y
las dos huellas). No se versionan las placas, los mensajes, los CSV del médico
```

y sustituirlo por:

```markdown
Se versionan `sesion.json`, `acta-h7.md` (cifras, `patientId`, estratos y
las dos huellas) y `latencia.json` (solo cifras agregadas). No se versionan
las placas, los mensajes, los CSV del médico
```

En `docs/validacion-semisintetica/README.md`, añadir AL FINAL del fichero
(después de «…no hay ningún dato de persona.», con una línea en blanco antes).
La cabecera del README ya dice, desde la tarea 7, que `latencia.json` no es
simulación; aquí se añade su sección:

````markdown
## `latencia.json`

Tampoco es simulación: es una **medición del sistema desplegado con casos de
prueba** (spec de SP5, §6.3), y su título lo dice. Lo escribe
`scripts/medir_latencia.py` desde el `latencias.json` de una corrida con
bots de `pruebas/reproducir_casos.py`: el p50 y el p95 de `ms_extremo` sobre
al menos 30 consultas sin error, frente a los umbrales de 8 s y 3 s. El tramo
medido va desde que `Normalizar update` recibe el update con la placa hasta
que `Desenlace` compone la respuesta; la subida a Telegram, la entrega del
webhook y el envío de `Responder` quedan fuera y se acotan a mano en 5 casos
(`tramo_manual`). Los casos son placas de RSNA con clínica inventada: no hay
usuarios ni pacientes. Si el fichero no está, la latencia de extremo a
extremo no se midió. Cómo se mide: `docs/sp5-sesion.md`, «Medir la latencia».
````

Por qué `--por-perfil 12` y no 4: el arnés no da `por_perfil × 9` casos. El
perfil 04 reusa UNA placa del 03, los tres fabricados llevan un caso cada uno
y solo existen 5 edades imposibles; y los perfiles 05 a 09 son rechazos, que
llevan `error` y no cuentan. Las consultas válidas son `3 × por_perfil + 1`:
13 con `--por-perfil 4`, 31 con 10 (el valor por defecto), 37 con 12.

- [ ] **Paso 12: Correr la suite afectada**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_reproducir_casos.py tests/test_medir_latencia.py tests/test_sesion.py tests/test_arquitectura.py tests/test_validar_combinacion.py
```

Salida esperada: ningún fallo ni error (un aviso de `pydicom`, que ya
estaba). `tests/test_validar_combinacion.py` tarda cerca de un minuto: dibuja
figuras y corre la rejilla entera una vez.

`tests/test_seleccion_casos.py` no entra en la lista: necesita la caché
`pruebas/crudas_prueba.csv`, que está ignorada, y sin ella da 5 errores con o
sin esta tarea.

- [ ] **Paso 13: Commit**

```bash
git add docs/sp5-sesion.md docs/validacion-semisintetica/README.md
git commit -m "docs(sp5): como se mide la latencia de extremo a extremo y que es latencia.json (SP5-B1 T8)" -m "Runbook: corrida con bots del arnes con --por-perfil 12 (37 consultas validas), scripts/medir_latencia.py y el tramo manual en 5 casos. El README de la carpeta dice que latencia.json es una medicion del sistema desplegado con casos de prueba, no una simulacion." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 9: Residuos de SP5-A

Ocho arreglos pequeños sobre código de SP5-A que ya está fusionado y probado.
Cada letra cambia solo lo que dice; van en cuatro commits: el acta (a, b, d),
la preparación (c, e), el generador y los datos (f, g) y el spec (h).

**Ficheros:**
- Modificar: `src/copiloto_triaje/validacion/concordancia.py` (a, b, d)
- Modificar: `docs/validacion-semisintetica/acta-h7-plantilla.md` (d)
- Modificar: `scripts/preparar_sesion.py` (c)
- Modificar: `pruebas/reproducir_casos.py` (e)
- Modificar: `docs/sp5-sesion.md` (c: el párrafo del runbook que describe `--fase mensajes`)
- Modificar: `src/copiloto_triaje/validacion/generador.py` (f)
- Modificar: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md` (h)
- Prueba: `tests/test_concordancia.py` (a, b, d)
- Prueba: `tests/test_sesion.py` (c)
- Prueba: `tests/test_reproducir_casos.py` (e)
- Prueba: `tests/test_generador.py` (f)
- Prueba: `tests/test_validacion_datos.py` (g)

**Interfaces:**
- Consume: `categoria.porcentaje_entero(p: float) -> int`;
  `heckerling.ESTADOS_ASMA = ("si", "no", "no_se")`;
  `datos.sha256_de(ruta) -> str` (ya existe: la letra g solo le pone prueba);
  `concordancia._f(x, decimales=2) -> str`.
- Produce (las firmas públicas no cambian):
  - `concordancia.acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict`:
    mismas claves; el límite inferior de la horquilla es 0 si `minima < 0.01`
    y el superior es 100 si `maxima > 0.99`.
  - `concordancia.ZONA_DE_LA_SESION = datetime.timezone(datetime.timedelta(hours=-5))`
    y `concordancia._fecha(ms) -> str` en esa zona.
  - `concordancia.UMBRALES_KAPPA = (0.4, 0.6)` y
    `concordancia._f_frente_a_umbral(x) -> str`; `concordancia._criterio(nombre, k) -> str`
    imprime sus cifras con ella. Tres decimales, y los que hagan falta hasta
    seis; a menos de 5e-7 de un umbral saldría «0,400000», y se acepta: un
    kappa no se conoce con esa precisión. La TABLA del acta (`_kappa_texto`)
    sigue a dos decimales, como cualquier tabla: la frase es la que compara.
  - `preparar_sesion.fase_mensajes(salida, imagen_tag=None, imagen_digest=None)`:
    `SystemExit` nuevo, «los mensajes mezclan orígenes: …».
  - `reproducir_casos.casos_desde_fichero(ruta)`: `SystemExit` nuevo,
    «… repite el patientId … en los casos i y j».
  - `generador.sortear_caso(modelo, indice, rng, asma=None) -> dict`:
    `ValueError` si `asma` no es `None` ni uno de `heckerling.ESTADOS_ASMA`.

**Cómo aplicar los cambios.** Cada cambio da el texto exacto que hay que
buscar y el texto por el que se sustituye; cada texto buscado aparece UNA sola
vez en su fichero. Usa la herramienta de edición, no un heredoc de Bash (en
esta máquina Bash interpreta las barras invertidas de los heredocs). Todas las
órdenes se corren desde la raíz del repo.

#### Grupo 1 — El acta (letras a, b, d)

- [ ] **Paso 1: Escribir las pruebas que fallan (a, b, d)**

Letra a. La prueba parametrizada de hoy afirma que un 100 frente a una máxima
de 0,9940 queda fuera; el bot imprime esa máxima como «> 99 %», así que el
caso cambia de signo y se añaden los de los bordes.

En `tests/test_concordancia.py`, busca:

```python
    (0.8000, 0.9940, 99, True),     # 0,9940 → 99
    (0.8000, 0.9940, 100, False),
])
```

y sustitúyelo por:

```python
    (0.8000, 0.9940, 99, True),
    (0.8000, 0.9940, 100, True),    # 0,9940 se imprime «> 99 %»: el límite superior es 100
    (0.8000, 0.9900, 100, False),   # 0,99 exacto se imprime «99 %»
    (0.0060, 0.3000, 0, True),      # 0,0060 se imprime «< 1 %»: el límite inferior es 0
    (0.0100, 0.3000, 0, False),     # 0,01 exacto se imprime «1 %»
])
```

Letra b. Se añade a la prueba de la frase del criterio el caso pegado a un
umbral.

En `tests/test_concordancia.py`, busca:

```python
    nan = float("nan")
    assert cc.frente_a_umbrales({"kappa": nan, "ic95": [nan, nan], "ic95_bca": [nan, nan]}) is None
```

y sustitúyelo por:

```python
    # pegado a un umbral, los dos decimales contradirían la frase: se imprimen los que hagan falta
    frase = cc._criterio("K", k(0.3996, 0.397, 0.4))
    assert frase.startswith("K (0,3996) no alcanza el mínimo de 0,4 de la Semana 1;")
    assert "con el método analítico (0,397) y no con el BCa (0,40)" in frase
    assert cc._criterio("K", k(0.5996, 0.1, 0.1)).startswith("K (0,5996) alcanza el mínimo de 0,4 de la Semana 1 y no el objetivo")
    assert cc._criterio("K", k(0.6, 0.4049, 0.1)).startswith("K (0,60) alcanza el mínimo de 0,4 de la Semana 1 y el objetivo")
    assert "con el BCa (0,10) y no con el método analítico (0,405)" in cc._criterio("K", k(0.6, 0.4049, 0.1))
    nan = float("nan")
    assert cc.frente_a_umbrales({"kappa": nan, "ic95": [nan, nan], "ic95_bca": [nan, nan]}) is None
```

Letras b y d. Tres pruebas nuevas, delante de la de la tabla de desacuerdos.

En `tests/test_concordancia.py`, busca:

```python
def test_la_tabla_de_desacuerdos_imprime_la_horquilla_como_el_bot(tmp_path):
```

y sustitúyelo por:

```python
def test_pegado_a_un_umbral_imprime_los_decimales_que_lo_distinguen():
    assert cc._f_frente_a_umbral(0.3996) == "0,3996"
    assert cc._f_frente_a_umbral(0.397) == "0,397"
    assert cc._f_frente_a_umbral(0.4049) == "0,405"
    assert cc._f_frente_a_umbral(0.6041) == "0,604"
    assert cc._f_frente_a_umbral(0.4) == "0,40" and cc._f_frente_a_umbral(0.6) == "0,60"
    assert cc._f_frente_a_umbral(0.41) == "0,41" and cc._f_frente_a_umbral(0.5) == "0,50"
    assert cc._f_frente_a_umbral(-0.12) == "-0,12"
    assert cc._f_frente_a_umbral(float("nan")) == "—"


def test_la_fecha_es_la_de_ecuador_continental_y_no_la_de_la_maquina():
    import datetime
    assert cc.ZONA_DE_LA_SESION == datetime.timezone(datetime.timedelta(hours=-5))

    def ms(*cuando):
        return int(datetime.datetime(*cuando, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert cc._fecha(ms(2026, 10, 7, 4, 59, 59)) == "2026-10-06"     # las 23:59:59 del 6 en UTC−5
    assert cc._fecha(ms(2026, 10, 7, 5, 0, 0)) == "2026-10-07"       # las 00:00:00 del 7
    assert cc._fecha(None) == "—" and cc._fecha(0) == "—"


def test_el_acta_dice_la_zona_horaria_de_las_fechas(tmp_path):
    clave = _clave()
    l1, _ = _lecturas(clave)
    s = cc.analizar(clave, _leidas(tmp_path, "l1.csv", l1))
    plano = _plano(cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave)))
    assert (f"**Fechas:** lectura el {cc._fecha(INICIO + 100000)}. Cada fecha es el día en la hora "
            f"de Ecuador continental (UTC−5).") in plano


def test_la_tabla_de_desacuerdos_imprime_la_horquilla_como_el_bot(tmp_path):
```

- [ ] **Paso 2: Correr las pruebas y ver que fallan**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_concordancia.py
```

Esperado: FALLA. La última línea es `6 failed, 38 passed` y el resumen lista:

```text
FAILED tests/test_concordancia.py::test_dentro_de_la_horquilla_compara_enteros_como_los_imprime_el_bot[0.8-0.994-100-True]
FAILED tests/test_concordancia.py::test_dentro_de_la_horquilla_compara_enteros_como_los_imprime_el_bot[0.006-0.3-0-True]
FAILED tests/test_concordancia.py::test_la_frase_del_criterio_cubre_cada_combinacion
FAILED tests/test_concordancia.py::test_pegado_a_un_umbral_imprime_los_decimales_que_lo_distinguen
FAILED tests/test_concordancia.py::test_la_fecha_es_la_de_ecuador_continental_y_no_la_de_la_maquina
FAILED tests/test_concordancia.py::test_el_acta_dice_la_zona_horaria_de_las_fechas
```

Las dos de la horquilla y la del criterio fallan con `AssertionError`; las de
`_f_frente_a_umbral` y `ZONA_DE_LA_SESION`, con
`AttributeError: module 'copiloto_triaje.validacion.concordancia' has no attribute …`;
la del acta, con `AssertionError` (la frase de la zona no está en la plantilla).

- [ ] **Paso 3: Escribir el código (a, b, d)**

Todo en `src/copiloto_triaje/validacion/concordancia.py`, salvo el último
cambio, que es de la plantilla del acta.

El módulo importa `datetime` arriba (hoy `_fecha` lo importa dentro):

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
import csv
import math
```

y sustitúyelo por:

```python
import csv
import datetime
import math
```

Letra d. La zona fija, debajo de `TEXTO_FIJADO`:

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
    "límite inferior queda por debajo de 0,4, se dice.")
```

y sustitúyelo por:

```python
    "límite inferior queda por debajo de 0,4, se dice.")
# Las fechas del acta son el dia en la hora de Ecuador continental (UTC−5, sin
# horario de verano), no en la zona de la maquina que analiza.
ZONA_DE_LA_SESION = datetime.timezone(datetime.timedelta(hours=-5))
```

Letra a. El docstring de `acuerdo_continuo`:

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
    «Dentro» compara el porcentaje entero del medico, SIN acotar, con la
    horquilla tal como la imprime el bot: `porcentaje_entero` de la minima y
    de la maxima (Math.round en Desenlace). Una horquilla de un solo valor
    (los discordantes con el asma conocida) solo admite ese entero, y se
    cuentan aparte para que el acta lo diga."""
```

y sustitúyelo por:

```python
    «Dentro» compara el porcentaje entero del medico, SIN acotar, con la
    horquilla tal como la imprime el bot: `porcentaje_entero` de la minima y
    de la maxima (Math.round en Desenlace), salvo en las cotas: una minima
    por debajo de 0,01 se imprime «< 1 %» y su limite es 0, y una maxima por
    encima de 0,99 se imprime «> 99 %» y su limite es 100. Una horquilla de
    un solo valor (los discordantes con el asma conocida) solo admite ese
    entero, y se cuentan aparte para que el acta lo diga."""
```

Letra a. Los dos límites:

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
        lo = np.array([porcentaje_entero(x) for x in minima], dtype=int)
        hi = np.array([porcentaje_entero(x) for x in maxima], dtype=int)
```

y sustitúyelo por:

```python
        lo = np.array([0 if x < 0.01 else porcentaje_entero(x) for x in minima], dtype=int)
        hi = np.array([100 if x > 0.99 else porcentaje_entero(x) for x in maxima], dtype=int)
```

Letra d. `_fecha`, entera:

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
def _fecha(ms) -> str:
    """El dia (YYYY-MM-DD, hora local) de un instante del formulario en ms."""
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else "—"
```

y sustitúyelo por:

```python
def _fecha(ms) -> str:
    """El dia (YYYY-MM-DD, en `ZONA_DE_LA_SESION`) de un instante del
    formulario en ms."""
    if not ms:
        return "—"
    return datetime.datetime.fromtimestamp(ms / 1000, tz=ZONA_DE_LA_SESION).strftime("%Y-%m-%d")
```

Letra b. La función nueva, delante de `NOMBRES_KAPPA`:

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
NOMBRES_KAPPA = {
```

y sustitúyelo por:

```python
UMBRALES_KAPPA = (0.4, 0.6)
_DECIMALES_MAXIMOS = 6


def _f_frente_a_umbral(x) -> str:
    """Un kappa, o un limite de su intervalo, para la frase que lo compara
    con 0,4 y 0,6. La comparacion es sin redondear: si los dos decimales de
    siempre dieran justo un umbral sin que el valor lo sea (0,3996 → «0,40»),
    la frase se contradiria; entonces se imprime con tres decimales, y con
    los que hagan falta (hasta seis) si tres aun dan el umbral."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return _f(x)
    for umbral in UMBRALES_KAPPA:
        if x != umbral and round(x, 2) == umbral:
            for decimales in range(3, _DECIMALES_MAXIMOS + 1):
                if round(x, decimales) != umbral:
                    break
            return _f(x, decimales)
    return _f(x)


NOMBRES_KAPPA = {
```

Letra b. `_criterio` imprime con ella los dos límites inferiores y el kappa, y
su docstring lo dice:

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
    """Una frase: el kappa frente a 0,4 y 0,6, y su limite inferior frente a
    0,4 con los dos intervalos (spec §5.5, §11.4), desde `frente_a_umbrales`."""
```

y sustitúyelo por:

```python
    """Una frase: el kappa frente a 0,4 y 0,6, y su limite inferior frente a
    0,4 con los dos intervalos (spec §5.5, §11.4), desde `frente_a_umbrales`.
    Las cifras van con `_f_frente_a_umbral`, para que no contradigan la frase."""
```

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
    la, lb = _f(k["ic95"][0]), _f(k["ic95_bca"][0])
```

y sustitúyelo por:

```python
    la, lb = _f_frente_a_umbral(k["ic95"][0]), _f_frente_a_umbral(k["ic95_bca"][0])
```

En `src/copiloto_triaje/validacion/concordancia.py`, busca:

```python
    return f"{nombre} ({_f(k['kappa'])}) {alcance}; el límite inferior del intervalo {limite}."
```

y sustitúyelo por:

```python
    return (f"{nombre} ({_f_frente_a_umbral(k['kappa'])}) {alcance}; "
            f"el límite inferior del intervalo {limite}.")
```

Letra d. La plantilla del acta dice la zona junto a las fechas (el signo de
«UTC−5» es el menos tipográfico, U+2212, el mismo de la prueba):

En `docs/validacion-semisintetica/acta-h7-plantilla.md`, busca:

```markdown
**Fechas:** {{fechas}}.
```

y sustitúyelo por:

```markdown
**Fechas:** {{fechas}}. Cada fecha es el día en la hora de Ecuador continental
(UTC−5).
```

- [ ] **Paso 4: Correr las pruebas y ver el verde**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_concordancia.py
```

Esperado: `44 passed`.

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/validacion/concordancia.py docs/validacion-semisintetica/acta-h7-plantilla.md tests/test_concordancia.py
git commit -m "fix(validacion): el acta compara la horquilla como la imprime el bot y fecha en UTC-5 (SP5-B1 T9)" -m "Dentro de la horquilla: una minima bajo 0,01 tiene limite 0 y una maxima sobre 0,99, limite 100. La frase del criterio imprime los decimales que distinguen un kappa pegado a 0,4 o a 0,6. Las fechas del acta son el dia en UTC-5, no en la zona de la maquina que analiza." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Grupo 2 — La preparación (letras c, e)

- [ ] **Paso 6: Escribir las pruebas que fallan (c, e)**

Letra c. La prueba de hoy de «sin bots exige el tag y el digest» usa
precisamente una mezcla (26 con bots y uno sin); con la regla nueva esa mezcla
se rechaza antes, así que la prueba pasa a usar 27 mensajes sin bots, y la
mezcla tiene su prueba propia.

En `tests/test_sesion.py`, busca:

```python
def test_fase_mensajes_sin_bots_exige_el_tag_y_el_digest_de_la_imagen(sesion_elegida):
    preparar, salida = sesion_elegida
    mensajes = _mensajes_coherentes(_leer_clave(salida), con_bots=True)
    next(iter(mensajes.values()))["con_bots"] = False              # uno solo sin bots basta
    _escribir_mensajes(salida, mensajes)
    with pytest.raises(SystemExit, match="--imagen-digest"):
        preparar.fase_mensajes(salida, imagen_tag="h7-sesion")
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
    assert _leer_clave(salida)["fase"] == "elegir"
```

y sustitúyelo por:

```python
def test_fase_mensajes_sin_bots_exige_el_tag_y_el_digest_de_la_imagen(sesion_elegida):
    preparar, salida = sesion_elegida
    _escribir_mensajes(salida, _mensajes_coherentes(_leer_clave(salida)))
    with pytest.raises(SystemExit, match="--imagen-digest"):
        preparar.fase_mensajes(salida, imagen_tag="h7-sesion")
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
    assert _leer_clave(salida)["fase"] == "elegir"


def test_fase_mensajes_rechaza_una_mezcla_de_origenes(sesion_elegida):
    """El acta cita UN origen: los 27 mensajes salen todos con bots o todos
    de la imagen local, aunque se pasen el tag y el digest."""
    preparar, salida = sesion_elegida
    clave = _leer_clave(salida)
    mensajes = _mensajes_coherentes(clave, con_bots=True)
    sin_bots = [c["patientId"] for c in clave["casos"][:2]]
    for pid in sin_bots:
        mensajes[pid].update(con_bots=False, coincide=None)
    _escribir_mensajes(salida, mensajes)
    with pytest.raises(SystemExit) as e:
        preparar.fase_mensajes(salida, **IMAGEN)
    assert "los mensajes mezclan orígenes: 25 con bots y 2 sin bots" in str(e.value)
    assert f"sin bots: {', '.join(sin_bots)}" in str(e.value)
    assert "un solo modo para los 27 casos" in str(e.value)
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
    assert _leer_clave(salida)["fase"] == "elegir"
```

Letra e. Una prueba nueva detrás de la de `casos_desde_fichero`.

En `tests/test_reproducir_casos.py`, busca:

```python
    with pytest.raises(SystemExit, match="no existe la placa"):
        casos_desde_fichero(fichero)
```

y sustitúyelo por:

```python
    with pytest.raises(SystemExit, match="no existe la placa"):
        casos_desde_fichero(fichero)


def test_casos_desde_fichero_rechaza_un_patientid_repetido(tmp_path):
    """mensajes.json va por patientId: un caso repetido pisaria el mensaje del
    otro y la sesion se quedaria con uno menos sin que nadie lo notara."""
    from pruebas.reproducir_casos import SIGNOS, SINTOMAS, casos_desde_fichero
    dcm = tmp_path / "a.dcm"
    dcm.write_bytes(b"x")
    caso = {"ruta_dcm": str(dcm), "signos": SIGNOS, "sintomas": SINTOMAS}
    fichero = tmp_path / "casos.json"
    fichero.write_text(json.dumps([{"patientId": "p-1", **caso}, {"patientId": "p-2", **caso},
                                   {"patientId": "p-1", **caso}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="repite el patientId p-1 en los casos 0 y 2"):
        casos_desde_fichero(fichero)
```

- [ ] **Paso 7: Correr las pruebas y ver que fallan**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_sesion.py tests/test_reproducir_casos.py
```

Esperado: FALLA. Dos pruebas en rojo y las demás en verde (un aviso, que
es de pydicom, `Invalid value for VR AS: '58'`, y ya estaba) y el resumen lista:

```text
FAILED tests/test_sesion.py::test_fase_mensajes_rechaza_una_mezcla_de_origenes
FAILED tests/test_reproducir_casos.py::test_casos_desde_fichero_rechaza_un_patientid_repetido
```

Las dos con `Failed: DID NOT RAISE SystemExit`.

- [ ] **Paso 8: Escribir el código (c, e)**

Letra c, en `scripts/preparar_sesion.py`. El docstring del módulo:

En `scripts/preparar_sesion.py`, busca:

```python
                   medico ve. Si algun mensaje no se genero con bots, exige
                   --imagen-tag y --imagen-digest, que el acta cita (spec §5.6).
```

y sustitúyelo por:

```python
                   medico ve. Los mensajes salen todos del mismo origen
                   (el acta cita UNO): una mezcla de mensajes con bots y sin
                   bots se rechaza. Si no se generaron con bots, exige
                   --imagen-tag y --imagen-digest, que el acta cita (spec §5.6).
```

Y la comprobación en `fase_mensajes`, antes de pedir el tag y el digest:

En `scripts/preparar_sesion.py`, busca:

```python
    con_bots = all(bool(c["con_bots"]) for c in clave["casos"] + clave["practica"])
    if not con_bots and not (imagen_tag and imagen_digest):
        raise SystemExit("hay mensajes que no se generaron con bots: el acta cita la imagen "
```

y sustitúyelo por:

```python
    todos = clave["casos"] + clave["practica"]
    sin_bots = [c["patientId"] for c in todos if not c["con_bots"]]
    if sin_bots and len(sin_bots) < len(todos):
        raise SystemExit(f"los mensajes mezclan orígenes: {len(todos) - len(sin_bots)} con bots y "
                         f"{len(sin_bots)} sin bots (sin bots: {', '.join(sin_bots)}). La sesión "
                         f"usa un solo modo para los {len(todos)} casos, porque el acta cita un "
                         f"solo origen: repite pruebas/reproducir_casos.py --casos con todos los "
                         f"casos en el mismo modo; no se escribe la lectura 2")
    con_bots = not sin_bots
    if not con_bots and not (imagen_tag and imagen_digest):
        raise SystemExit("los mensajes no se generaron con bots: el acta cita la imagen "
```

(El resto de esa orden `raise SystemExit(...)`, las dos líneas que siguen, no
cambia.)

Letra c, en `docs/sp5-sesion.md`: el runbook describe lo que detiene la fase.

En `docs/sp5-sesion.md`, busca:

```markdown
lista: no se corrige a mano. Si algún mensaje no se generó con bots y faltan
`--imagen-tag` o `--imagen-digest`, también se detiene: el acta los cita.
```

y sustitúyelo por:

```markdown
lista: no se corrige a mano. Si unos mensajes se generaron con bots y otros
sin bots, también se detiene: la sesión usa un solo modo para los 27 casos,
porque el acta cita un solo origen. Y si se generaron sin bots y faltan
`--imagen-tag` o `--imagen-digest`, también: el acta los cita.
```

Letra e, en `pruebas/reproducir_casos.py`, función `casos_desde_fichero`. El
docstring, el diccionario de los ya vistos y la comprobación:

En `pruebas/reproducir_casos.py`, busca:

```python
    {patientId, ruta_dcm, signos, sintomas}. Se comprueba cada uno ANTES de
    empezar: un caso a medias haria que el arnes dijera «SIN COMBINAR» de un
    caso que el medico va a leer como combinado."""
```

y sustitúyelo por:

```python
    {patientId, ruta_dcm, signos, sintomas}. Se comprueba cada uno ANTES de
    empezar: un caso a medias haria que el arnes dijera «SIN COMBINAR» de un
    caso que el medico va a leer como combinado, y un `patientId` repetido
    pisaria un mensaje con otro en `mensajes.json`, que va por `patientId`."""
```

En `pruebas/reproducir_casos.py`, busca:

```python
    meta = _metadatos()
    casos = []
    for i, d in enumerate(datos):
        faltan = [k for k in ("patientId", "ruta_dcm", "signos", "sintomas") if k not in d]
```

y sustitúyelo por:

```python
    meta = _metadatos()
    casos = []
    vistos = {}
    for i, d in enumerate(datos):
        faltan = [k for k in ("patientId", "ruta_dcm", "signos", "sintomas") if k not in d]
```

En `pruebas/reproducir_casos.py`, busca:

```python
            raise SystemExit(f"al caso {i} de {ruta} le faltan {faltan}")
```

y sustitúyelo por:

```python
            raise SystemExit(f"al caso {i} de {ruta} le faltan {faltan}")
        if d["patientId"] in vistos:
            raise SystemExit(f"{ruta} repite el patientId {d['patientId']} en los casos "
                             f"{vistos[d['patientId']]} y {i}: cada caso va una sola vez")
        vistos[d["patientId"]] = i
```

- [ ] **Paso 9: Correr las pruebas y ver el verde**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_sesion.py tests/test_reproducir_casos.py
```

Esperado: ningún fallo (un aviso de pydicom, que ya estaba).

- [ ] **Paso 10: Commit**

```bash
git add scripts/preparar_sesion.py pruebas/reproducir_casos.py docs/sp5-sesion.md tests/test_sesion.py tests/test_reproducir_casos.py
git commit -m "fix(sesion): un solo origen para los 27 mensajes y ningun patientId repetido (SP5-B1 T9)" -m "La fase mensajes rechaza una mezcla de mensajes con bots y sin bots: el acta cita un solo origen. El arnes rechaza un fichero de casos que repite un patientId, que pisaria un mensaje con otro." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Grupo 3 — El generador y los datos (letras f, g)

- [ ] **Paso 11: Escribir las pruebas (f, g)**

Letra f. Dos pruebas nuevas detrás de `test_sortear_caso_fuerza_el_asma_declarada`.

En `tests/test_generador.py`, busca:

```python
    libre = generador.sortear_caso(m, 0, np.random.default_rng(1))
    assert libre["asma"] == libre["asma_real"]
```

y sustitúyelo por:

```python
    libre = generador.sortear_caso(m, 0, np.random.default_rng(1))
    assert libre["asma"] == libre["asma_real"]


@pytest.mark.parametrize("asma", ["nose", "NO_SE", "", True, 1])
def test_sortear_caso_rechaza_un_asma_que_no_es_un_estado(prueba, asma):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    with pytest.raises(ValueError, match="asma"):
        generador.sortear_caso(m, 0, np.random.default_rng(1), asma=asma)


@pytest.mark.parametrize("asma", ["si", "no", "no_se"])
def test_sortear_caso_acepta_los_tres_estados_del_asma(prueba, asma):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    assert generador.sortear_caso(m, 0, np.random.default_rng(1), asma=asma)["asma"] == asma
```

Letra g. `sha256_de` ya existe y funciona: su prueba es de caracterización y
sale verde desde el principio (no hay fase roja que ver). Los bytes con CR y
LF se escriben con `bytes([...])` a propósito, sin barras invertidas.
`huella_de_texto` no se prueba aquí: es de la tarea 4.

En `tests/test_validacion_datos.py`, busca:

```python
import re

import numpy as np
```

y sustitúyelo por:

```python
import hashlib
import re

import numpy as np
```

En `tests/test_validacion_datos.py`, busca:

```python
def test_la_evidencia_de_imagen_usa_la_prevalencia_del_calibrador():
```

y sustitúyelo por:

```python
def test_sha256_de_es_el_sha256_de_los_bytes_del_fichero(tmp_path):
    ruta = tmp_path / "abc.txt"
    con_crlf = bytes([0x61, 0x0D, 0x0A, 0x62, 0x0A])          # «a», CR, LF, «b», LF
    solo_lf = bytes([0x61, 0x0A, 0x62, 0x0A])
    ruta.write_bytes(con_crlf)
    assert datos.sha256_de(ruta) == hashlib.sha256(con_crlf).hexdigest()
    assert datos.sha256_de(ruta) != hashlib.sha256(solo_lf).hexdigest()
    # más de un bloque de lectura (1 MiB): el fichero se lee entero
    grande = tmp_path / "grande.bin"
    contenido = bytes(range(256)) * 5000                      # 1 280 000 bytes
    grande.write_bytes(contenido)
    assert datos.sha256_de(grande) == hashlib.sha256(contenido).hexdigest()
    vacio = tmp_path / "vacio.bin"
    vacio.write_bytes(b"")
    assert datos.sha256_de(vacio) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_la_evidencia_de_imagen_usa_la_prevalencia_del_calibrador():
```

- [ ] **Paso 12: Correr las pruebas y ver que fallan las de la letra f**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_generador.py tests/test_validacion_datos.py
```

Esperado: FALLA. La última línea es `5 failed, 19 passed` y el resumen lista:

```text
FAILED tests/test_generador.py::test_sortear_caso_rechaza_un_asma_que_no_es_un_estado[nose]
FAILED tests/test_generador.py::test_sortear_caso_rechaza_un_asma_que_no_es_un_estado[NO_SE]
FAILED tests/test_generador.py::test_sortear_caso_rechaza_un_asma_que_no_es_un_estado[]
FAILED tests/test_generador.py::test_sortear_caso_rechaza_un_asma_que_no_es_un_estado[True]
FAILED tests/test_generador.py::test_sortear_caso_rechaza_un_asma_que_no_es_un_estado[1]
```

Las cinco con `Failed: DID NOT RAISE ValueError`. La prueba de `sha256_de` y
las tres de `test_sortear_caso_acepta_los_tres_estados_del_asma` pasan ya.

- [ ] **Paso 13: Escribir el código (f)**

En `src/copiloto_triaje/validacion/generador.py`. El import (absoluto, como en
`sesion.py` y `simulacion.py`):

En `src/copiloto_triaje/validacion/generador.py`, busca:

```python
from .oraculo import PROBABILIDAD_ASMA_PRESENTE, Modelo
```

y sustitúyelo por:

```python
from copiloto_triaje.servicio.heckerling import ESTADOS_ASMA

from .oraculo import PROBABILIDAD_ASMA_PRESENTE, Modelo
```

Y la validación al principio de `sortear_caso`:

En `src/copiloto_triaje/validacion/generador.py`, busca:

```python
    estado DECLARADO (`no_se` en el estrato del asma); el real sigue sorteado."""
    y = int(modelo.etiquetas[indice])
```

y sustitúyelo por:

```python
    estado DECLARADO (`no_se` en el estrato del asma); el real sigue sorteado.
    Tiene que ser uno de `heckerling.ESTADOS_ASMA`, o None para no forzarlo."""
    if asma is not None and not (isinstance(asma, str) and asma in ESTADOS_ASMA):
        raise ValueError(f"«asma» debe ser uno de {list(ESTADOS_ASMA)} o None, y es {asma!r}")
    y = int(modelo.etiquetas[indice])
```

- [ ] **Paso 14: Correr las pruebas y ver el verde**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_generador.py tests/test_validacion_datos.py tests/test_arquitectura.py
```

Esperado: `30 passed` (`tests/test_arquitectura.py` va en la orden porque el
generador gana un import de `servicio`).

- [ ] **Paso 15: Commit**

```bash
git add src/copiloto_triaje/validacion/generador.py tests/test_generador.py tests/test_validacion_datos.py
git commit -m "fix(validacion): sortear_caso valida el asma, y sha256_de tiene su prueba (SP5-B1 T9)" -m "Un asma forzada que no es si, no, no_se ni None es ValueError en vez de viajar a la viñeta. sha256_de se prueba con un vector conocido, con CRLF sin normalizar y con un fichero de mas de un bloque." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Grupo 4 — El spec (letra h)

- [ ] **Paso 16: Añadir al §5.3 del spec la vía de dos puntuaciones**

Es un cambio de documentación. El §5.3 da hoy la condición analítica de UNA
puntuación (`min(RV_clínica, RV_imagen) ≤ 17,5` y
`odds_previas × max(…) < 0,25`), que por sí sola daría ≈ 1,4 %, y afirma
≈ 3,3 % sin decir de dónde sale; el docstring de
`src/copiloto_triaje/validacion/categoria.py` sí lo dice. Se añade un párrafo
nuevo al final del §5.3, detrás de su último párrafo y delante de
`### 5.4. Diseño: dos lecturas del mismo conjunto`.

En `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`, busca:

```markdown
lo dice: la categoría del sistema en la sesión usa el previo del despliegue,
no el del §4.
```

y sustitúyelo por:

```markdown
lo dice: la categoría del sistema en la sesión usa el previo del despliegue,
no el del §4.

**De dónde sale el ≈ 3,3 %: la vía de dos puntuaciones.** Cruzar el 20 % y el
70 % a la vez exige que las odds de la mínima queden por debajo de 0,25 y las
de la máxima por encima de 7/3, es decir, un cociente de odds entre los dos
extremos mayor que ≈ 9,33. Con una sola puntuación ese cociente es
`min(RV_clínica, RV_imagen)`, la única RV clínica que pasa de 9,33 es la de 5
puntos (17,5), y la mínima vale entonces al menos `odds_previas × 17,5`: el
cruce doble exigiría una prevalencia por debajo de ≈ 1,4 %. El umbral más alto,
y por eso el que cuenta, es el del asma `no_se` con los otros cuatro hallazgos
presentes: el sistema entrega dos puntuaciones, [4, 5], y
`heckerling.combinacion` funde en una sola horquilla los extremos de las dos.
Con una imagen a favor y no más informativa que los 4 puntos (RV de imagen
entre 1 y 7,18), la mínima es la dependencia total de la puntuación 4,
`odds_previas × 7,18`, y la máxima es la independencia de la puntuación 5,
`odds_previas × 17,5 × RV_imagen`; el cociente, `17,5 × RV_imagen / 7,18`,
llega a 17,5. La mínima baja del 20 % si `odds_previas × 7,18 < 0,25`, o sea
con una prevalencia por debajo de ≈ 3,36 %; como la banda se decide sobre el
porcentaje entero (19 % o menos: una mínima menor que 0,195), el umbral
efectivo es ≈ 3,26 %. De ahí el «≈ 3,3 %», y por eso la prueba lo fija con
0,032 (hay cruces dobles, todos por esta vía) y 0,034 (ninguno). Las dos
prevalencias que se usan, 0,1466 y 0,2215, quedan muy por encima.
```

- [ ] **Paso 17: Comprobar las cifras del párrafo**

Las tres prevalencias del párrafo (3,36 %, 3,26 % y 1,4 %) salen de esta cuenta:

```bash
C:/venv-copiloto/Scripts/python.exe -c "f=lambda o: round(o/(1+o), 4); print(f(0.25/7.18), f((0.195/0.805)/7.18), f(0.25/17.5))"
```

Esperado: `0.0336 0.0326 0.0141`.

Y la prueba que fija el umbral con 0,032 y 0,034 sigue en verde:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_categoria.py
```

Esperado: `10 passed`.

- [ ] **Paso 18: Correr la suite afectada entera**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_concordancia.py tests/test_sesion.py tests/test_reproducir_casos.py tests/test_generador.py tests/test_validacion_datos.py
node tests/formulario.mjs
```

Esperado: ningún fallo de pytest (un aviso de pydicom, que ya estaba), y la
última línea de node es `16 OK`.

- [ ] **Paso 19: Commit**

```bash
git add docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md
git commit -m "docs(sp5): el umbral de 3,3 % del §5.3 sale de la via de dos puntuaciones (SP5-B1 T9)" -m "Con una sola puntuacion el cruce doble de 20 y 70 % exigiria una prevalencia bajo 1,4 %; el 3,3 % es el del asma no_se con puntuacion [4, 5]." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 10: La suite entera y el estado de SP5 en el README

**Ficheros:**
- Modificar: `README.md` (el punto de SP5 de la lista de sub-proyectos)

**Interfaces:**
- Consume: todo lo anterior.
- Produce: nada nuevo; deja la rama lista para la revisión final.

- [ ] **Paso 1: La suite entera**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest -q`

Esperado: ningún fallo ni error. Antes de este plan la suite daba
`499 passed, 18 skipped`; este plan añade pruebas y no salta ninguna más,
así que el resultado es `N passed, 18 skipped` con N mayor que 499 (los
avisos de `pydicom` ya estaban). Apunta N en el informe, con el recuento de
cada fichero de pruebas nuevo: `tests/test_metricas.py`,
`tests/test_simulacion.py`, `tests/test_validar_combinacion.py`,
`tests/test_informe.py`, `tests/test_resultados_publicados.py` y
`tests/test_medir_latencia.py`.

Si `tests/test_mantenimiento.py` da errores de fixture con `docker run`
(código 125), es que otro proceso está corriendo ese mismo fichero a la vez:
vuelve a correrlo a solas.

Y las pruebas de `node`, que no cambian con este plan salvo porque la tarea 9
no toca el formulario:

```bash
node tests/formulario.mjs
```

Esperado: `16 OK`.

- [ ] **Paso 2: Comprobar que nada de lo publicado quedó rancio**

Orden: `git status --short`

Esperado: vacío. Si `docs/validacion-semisintetica/` o
`docs/validacion-semisintetica-sp5.md` aparecen modificados, alguna tarea
posterior a la 7 cambió algo de lo que dependen los resultados: vuelve a
correr `scripts/validar_combinacion.py` (tarea 7, paso 3) y confirma el
resultado en un commit aparte, diciendo qué cambió.

- [ ] **Paso 3: El README dice dónde está la validación**

En `README.md`, sustituye el punto de SP5 de la lista de sub-proyectos (el que
empieza por `- **SP5 — validación semisintética y sesión con el médico (en curso).**`
y acaba en «el procedimiento de la sesión, en `docs/sp5-sesion.md`.») por:

```markdown
- **SP5 — validación semisintética y sesión con el médico (en curso).** El
  generador por puntuación de Heckerling, su oráculo, las métricas y la
  simulación por celda viven en `src/copiloto_triaje/validacion/`; los insumos
  y resultados, rotulados como simulación semisintética, en
  `docs/validacion-semisintetica/`, y su análisis en
  `docs/validacion-semisintetica-sp5.md`: lo genera
  `scripts/validar_combinacion.py` sin teclear ninguna cifra, y se reproduce
  sin los pesos. La simulación **no mide exactitud clínica**: mide si el
  sistema calcula lo que dice calcular y cuánto se desvía bajo cada supuesto
  de dependencia entre clínica e imagen. El procedimiento de la sesión con el
  médico, en `docs/sp5-sesion.md`.
```

- [ ] **Paso 4: Commit**

```bash
git add README.md
git commit -m "docs(sp5): el README dice dónde está la validación semisintética y qué no mide" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Autorrevisión del plan (hecha al escribirlo)

**Cobertura del spec.**

| Spec | Tarea |
| :--- | :--- |
| §4.3 sensibilidad al previo (Brier, ECE, intercepto ≈ +0,50, cambios de banda) | 3, 6, 7 |
| §4.4 calibración de la imagen sola como suelo | 3 (`imagen_sola`), 6 |
| §4.4 0C, cálculo | 3, 6 |
| §4.4 0B | recortado: el artículo no está en manos del equipo (spec §6.6, orden de recorte) |
| §4.5 escala legible por lado de la imagen, «poco informativa» en k = 2 y 3 | 3, 6 |
| §4.6 bootstrap B = 1 000, pareado, generador fijo, percentiles | 3, 4, 7 |
| §4.6 cuatro modelos puntuales y sus métricas; ECE con suelo; fiabilidad | 1, 2, 3, 5 |
| §4.6 horquilla: posición, colas con ε, contención; fila 0A en 0 / 0 / 100 % | 1, 2, 7 |
| §4.6 discordantes y `no_se` en filas aparte; recuentos por tipo | 2, 6 |
| §4.6 hipótesis del 90 %, celda a celda | 3, 6 |
| §4.6 la combinación, con el código del servidor | 2 (restricción 1) |
| §4.7 lo que puede afirmar y lo que no | 6 |
| §4.8 dónde vive cada cosa; huellas en los resultados; rótulo | 4, 5, 6, 7 |
| §6.3 latencia de extremo a extremo (herramienta; la corrida con bots la hace el equipo) | 8 |
| §8 pruebas de métricas y casos de borde de la horquilla | 1 |
| §11.2 y §11.3 | 7 |
| Residuos de la revisión final de SP5-A | 9 |

**Lo que este plan no cierra y queda dicho:** la corrida con bots contra el
VPS para `latencia.json` (la hace el equipo con sus secretos, siguiendo
`docs/sp5-sesion.md`, antes del 16-oct); la anonimización (plan SP5-B2); los
documentos del curso (plan SP5-C).

**Huecos.** Ningún paso dice «por determinar»; todo el código y todas las
pruebas están escritos y han corrido antes de escribirse aquí.

**Consistencia de nombres.** `metricas.EPSILON` es la única tolerancia;
`simulacion.evaluar_tarea` es el trabajador de los procesos; `resultados` es
siempre el diccionario leído del JSON; los intervalos son siempre el
diccionario plano `ruta → [li, ls]`.
