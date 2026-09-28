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
  cada cifra `float` que mide `medir`: los cuatro modelos, las diferencias
  pareadas, la horquilla, los discordantes y los `no_se`. **Van sin
  intervalo:** los recuentos; el suelo de la ECE y la fiabilidad (D11); la
  escala legible, que es una forma cerrada y no tiene sorteo que remuestrear
  (D7); y la sensibilidad al previo y 0C, que son tablas de contraste sobre la
  estimación puntual. Si una cifra falta en alguna réplica (su grupo de casos
  quedó vacío al remuestrear), el bootstrap se detiene: un intervalo no se
  calcula sobre menos réplicas de las que el resultado dice que hubo.
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


def test_la_contencion_se_cuenta_y_un_90_por_ciento_exacto_lo_es():
    """Restando, 1 − 0,06 − 0,04 da 0,8999999999999999 y no alcanza el 0,90."""
    assert 1.0 - 0.06 - 0.04 < 0.9
    n = 2000
    oraculo = np.array([-1.0] * 120 + [2.0] * 80 + [0.5] * (n - 200))
    h = metricas.horquilla(oraculo, np.zeros(n), np.ones(n))
    assert (h["bajo"], h["sobre"], h["contencion"]) == (0.06, 0.04, 0.9)
    assert h["contencion"] >= 0.90
    r = metricas.contencion_en_rango(oraculo, np.zeros(n), np.ones(n))
    assert (r["bajo"], r["sobre"], r["contencion"]) == (0.06, 0.04, 0.9)
    # en todos los repartos de colas que suman un 10 %
    for bajos in range(0, 201, 8):
        oraculo = np.array([-1.0] * bajos + [2.0] * (200 - bajos) + [0.5] * (n - 200))
        assert metricas.horquilla(oraculo, np.zeros(n), np.ones(n))["contencion"] == 0.9


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

Esperado: `9 failed, 18 passed`; los fallos son
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
    # La contencion se CUENTA, no se resta: 1 − 0,06 − 0,04 da
    # 0,8999999999999999, y un 90 % exacto no alcanzaria su umbral.
    return {"n": n, "sin_horquilla": int((~con).sum()),
            "lambda": _cuartiles((o[con] - d[con]) / delta[con]),
            "bajo": float(bajo.mean()), "sobre": float(sobre.mean()),
            "contencion": float((~(bajo | sobre)).mean())}


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
            "contencion": float((~(bajo | sobre)).mean())}


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

Esperado: `27 passed`.

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

Esperado: `37 passed` (las 27 de las métricas y las 10 de 0A).

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


def test_cada_replica_remuestrea_placas_y_vuelve_a_sortear_la_clinica(conjunto, monkeypatch):
    """Las dos mitades del bootstrap, fijadas: si una réplica dejara de
    remuestrear las placas, o midiera siempre la clínica de la estimación
    puntual, los intervalos se estrecharían sin que nada más lo notara."""
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)
    semillas, filas = [], []
    generar, medir = generador.generar, simulacion.medir

    def generar_espia(m, semilla):
        semillas.append(semilla)
        return generar(m, semilla)

    def medir_espia(c, salidas, l_oraculo, f=None):
        filas.append(f)
        return medir(c, salidas, l_oraculo, f)

    monkeypatch.setattr(generador, "generar", generar_espia)
    monkeypatch.setattr(simulacion, "medir", medir_espia)
    corridas = [simulacion.replica(conjunto, modelo, b) for b in (0, 1, 2)]
    assert semillas == [simulacion.SEMILLA_CLINICA + b for b in (0, 1, 2)]
    assert simulacion.SEMILLA_PUNTUAL not in semillas
    n = conjunto.y.size
    for b, f in enumerate(filas):
        assert f is not None and f.shape == (n,)
        assert 0 <= f.min() and f.max() < n
        assert np.unique(f).size < n                    # con reemplazo: hay repetidas
        assert np.array_equal(f, np.random.default_rng(
            simulacion.SEMILLA_INDICES + b).integers(0, n, n))
    assert not np.array_equal(filas[0], filas[1])
    # pareado: la diferencia entre modelos es la de ESA réplica
    for c in corridas:
        for combinado in simulacion.COMBINADOS:
            for cifra in ("auc", "brier", "pendiente"):
                assert c[f"pareadas.{combinado}.{cifra}"] == pytest.approx(
                    c[f"modelos.{combinado}.{cifra}"] - c[f"modelos.imagen.{cifra}"], abs=1e-15)


def test_un_intervalo_no_se_calcula_sobre_menos_replicas_de_las_que_dice(conjunto, monkeypatch):
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)
    monkeypatch.setattr(simulacion, "replica", lambda c, m, b: (
        {"a.auc": 0.9, "a.ece": 0.01} if b != 2 else {"a.auc": 0.9}))
    assert simulacion.bootstrap(conjunto, modelo, replicas=2) == {
        "a.auc": [0.9, 0.9], "a.ece": [0.01, 0.01]}
    with pytest.raises(ArithmeticError, match="a.ece"):
        simulacion.bootstrap(conjunto, modelo, replicas=3)


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

Esperado: `4 failed, 15 passed`, con
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
    incompletas = [r for r in rutas if any(r not in c for c in corridas)]
    if incompletas:
        # Una cifra falta en una replica cuando su grupo de casos quedo vacio
        # al remuestrear. No se calcula un intervalo sobre menos replicas de
        # las que el resultado dice que hubo.
        raise ArithmeticError(f"{len(incompletas)} cifras faltan en alguna réplica (la "
                              f"primera, {incompletas[0]}): algún grupo de casos quedó "
                              "vacío al remuestrear")
    return {r: metricas.percentiles([c[r] for c in corridas]) for r in rutas}
```

- [ ] **Paso 4: Correrlas y ver el verde**

Orden: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_simulacion.py -q`

Esperado: `19 passed`.

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
    assert [f["rv_derivacion"] for f in c["por_puntuacion"]] == [
        0.12, 0.20, 0.70, 1.64, 7.18, 17.5]
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

Esperado: `19 passed` y las 10 nuevas en
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
    # A 4 decimales, como lo entregaria el sistema con esas RV: los dos lados
    # de la comparacion son lo mismo salvo la tabla.
    con_validacion = np.array([
        round(combinar(conjunto.prevalencia, RV_VALIDACION[int(kk)], float(r)), 4)
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
`29` pruebas.

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
    `tareas_de_la_rejilla(replicas, rejilla=oraculo.RHO_REJILLA, destacadas=oraculo.CELDAS_DESTACADAS) -> list[tuple]`
    (`ValueError` si una destacada no está en la rejilla o es el origen);
    `huella_de_los_pesos() -> str` (`SystemExit` si el `.sha256` no lleva una huella);
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
    # rutas relativas a la raiz del repo: ni la carpeta ni el usuario de nadie
    assert i["crudas"] == "docs/validacion-semisintetica/crudas_prueba.csv"
    assert i["calibrador"] == "servidor/calibrador.json"
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

    # y no solo los mismos datos: el mismo FICHERO, con las claves en su orden
    def como_fichero(d):
        return json.dumps(d, ensure_ascii=False, indent=1, allow_nan=False)
    assert como_fichero(r) == como_fichero(resultados_minimos)


def test_una_destacada_que_no_esta_en_la_rejilla_se_rechaza(validar):
    # como listas, que es como las guarda el propio JSON, valen
    tareas = validar.tareas_de_la_rejilla(5, rejilla=[0, 0.3], destacadas=[[0.3, 0.3]])
    assert tareas == [(0.0, 0.0, 5, True), (0.0, 0.3, 0, False),
                      (0.3, 0.0, 0, False), (0.3, 0.3, 5, True)]
    with pytest.raises(ValueError, match="rejilla"):
        validar.tareas_de_la_rejilla(5, rejilla=(0.0, 0.3), destacadas=((0.3, 0.45),))
    with pytest.raises(ValueError, match="0A"):
        validar.tareas_de_la_rejilla(5, rejilla=(0.0, 0.3), destacadas=((0.0, 0.0),))


def test_la_huella_de_los_pesos_tiene_que_ser_un_sha256(validar, tmp_path, monkeypatch):
    assert validar.huella_de_los_pesos() == datos.HASH_CONGELADO.read_text(
        encoding="utf-8").strip()
    for contenido in ("", "no-es-una-huella", "ab" * 32 + " " + "cd" * 32, "AB" * 32):
        malo = tmp_path / "pesos.sha256"
        malo.write_text(contenido, encoding="utf-8")
        monkeypatch.setattr(datos, "HASH_CONGELADO", malo)
        with pytest.raises(SystemExit, match="no lleva un sha256"):
            validar.huella_de_los_pesos()


def test_un_nan_no_llega_al_json(validar, tmp_path):
    with pytest.raises(ValueError):
        validar.escribir_resultados({"cifra": float("nan")}, tmp_path / "r.json")


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

Esperado: `1 passed, 9 errors`: pasa la de la huella y las otras nueve dan
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
import re
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
    rejilla. Solo 0A y las destacadas llevan bootstrap y sensibilidad. Una
    destacada que no esta en la rejilla se rechaza: si no, el resultado la
    anunciaria en sus parametros sin haberla calculado."""
    rejilla = [float(r) for r in rejilla]
    destacadas = {(float(a), float(b)) for a, b in destacadas}
    fuera = sorted(d for d in destacadas
                   if d[0] not in rejilla or d[1] not in rejilla or d == (0.0, 0.0))
    if fuera:
        raise ValueError(f"las celdas destacadas {fuera} no valen: tienen que estar en la "
                         f"rejilla {rejilla}, y el origen es 0A, que se cuenta aparte")
    tareas = []
    for rho1 in rejilla:
        for rho0 in rejilla:
            completa = (rho1 == 0.0 and rho0 == 0.0) or (rho1, rho0) in destacadas
            tareas.append((rho1, rho0, replicas if completa else 0, completa))
    return tareas


def _relativa(ruta: Path) -> str:
    try:
        return Path(ruta).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(ruta).name


def huella_de_los_pesos() -> str:
    """El sha256 de los pesos con que se generaron las crudas congeladas. Aqui
    no se puede recalcular (los pesos no viajan con el repositorio): se
    comprueba que el fichero lleva UNA huella, y se escribe en los resultados."""
    partes = datos.HASH_CONGELADO.read_text(encoding="utf-8").split()
    if len(partes) != 1 or not re.fullmatch(r"[0-9a-f]{64}", partes[0]):
        raise SystemExit(f"{_relativa(datos.HASH_CONGELADO)} no lleva un sha256: no se sabe "
                         "con qué pesos se generaron las crudas congeladas")
    return partes[0]


def calcular(replicas: int = simulacion.B_REPLICAS, procesos: int = 1,
             rejilla=oraculo.RHO_REJILLA, destacadas=oraculo.CELDAS_DESTACADAS) -> dict:
    pesos = huella_de_los_pesos()
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
            "pesos_sha256": pesos,
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
        # allow_nan=False: «NaN» no es JSON, y un tercero no podria leerlo.
        f.write(json.dumps(resultados, ensure_ascii=False, indent=1, allow_nan=False) + "\n")
    return ruta


def leer_resultados(ruta) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--replicas", type=int, default=simulacion.B_REPLICAS,
                   help="réplicas del bootstrap en 0A y las seis celdas destacadas "
                        "(0: sin bootstrap ni intervalos, para ensayos)")
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

Esperado: `10 passed` (unos 10 s: la fixture calcula cuatro celdas y la prueba
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
- Modificar: `scripts/validar_combinacion.py` (bloque nuevo «LAS FIGURAS» antes de `main()`, y tres cambios dentro de `main()`)
- Modificar: `pyproject.toml` (el extra `figuras`)
- Prueba: `tests/test_validar_combinacion.py` (el `import copy`, un cambio en una prueba de la tarea 4 y doce pruebas nuevas al final)

**Interfaces:**
- Consume: del propio script, `ROTULO`, `NOMBRE_RESULTADOS`, `leer_resultados(ruta) -> dict`,
  `escribir_resultados`, `calcular`; `simulacion.MODELOS`; el diccionario `resultados`
  (de cada celda: `nombre`, `rho1`, `rho0`, `destacada`, `modelos[m].fiabilidad[] {p_media, observada}`,
  `modelos[m].ece`, `modelos[m].suelo.{media,p95}`, `modelos.independencia.pendiente`,
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
  - privadas `_pyplot()` (sin matplotlib sale con `SystemExit` y dice qué instalar; si lo que
    falta es otra cosa, deja pasar el error),
    `_luminancia(color) -> float`, `_tinta_sobre(color) -> str` (blanco o `TINTA`: la que más
    contrasta con el color pintado), `_ejes(ax, titulo, x, y)`, `_coma(valor, decimales)`,
    `_rho(valor)`, `_guardar(plt, fig, destino, titulo) -> Path`;
  - `main()`: con `--solo-documento` comprueba primero que el JSON existe; después, salvo con
    `--sin-figuras`, comprueba ANTES de calcular que se puede dibujar (`_pyplot()`); tras
    escribir el JSON lo lee con `leer_resultados(ruta)` y llama a
    `figuras(resultados, salida)`, que imprime `figura: <ruta>` por cada una. `figuras()`
    comprueba lo mismo antes de borrar las figuras que hubiera.
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

En `tests/test_validar_combinacion.py` hay que hacer tres cosas.

(0) El `import copy`, al principio del fichero. Busca exactamente:

```python
"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
import json
```

y sustitúyelo por:

```python
"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
import copy
import json
```

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


def _contraste(una: float, otra: float) -> float:
    """La razon de contraste de WCAG 2 entre dos luminancias."""
    clara, oscura = max(una, otra), min(una, otra)
    return (clara + 0.05) / (oscura + 0.05)


def test_la_tinta_es_la_que_mas_contrasta_con_el_color_pintado(validar):
    pytest.importorskip("matplotlib")
    # la luminancia relativa de WCAG 2: sus tres coeficientes y su gamma
    assert validar._luminancia("#ff0000") == pytest.approx(0.2126)
    assert validar._luminancia("#00ff00") == pytest.approx(0.7152)
    assert validar._luminancia("#0000ff") == pytest.approx(0.0722)
    assert validar._luminancia("white") == pytest.approx(1.0)
    assert validar._luminancia("black") == 0.0
    assert validar._luminancia("#808080") == pytest.approx(0.2159, abs=1e-4)
    for claro in ("#e34948", "#f0a09f", "#c9c8c3", "#f0efec", "#cde2fb", "white"):
        assert validar._tinta_sobre(claro) == validar.TINTA, claro
    for oscuro in ("#1c5cab", "#0d366b", validar.TINTA, "black"):
        assert validar._tinta_sobre(oscuro) == "white", oscuro
    # tal como lo da un mapa de color: una tupla RGBA
    assert validar._tinta_sobre((0.05, 0.21, 0.42, 1.0)) == "white"
    assert validar._tinta_sobre((0.91, 0.55, 0.54, 1.0)) == validar.TINTA
    # y en cualquier color, tambien donde las dos casi empatan, la elegida
    # contrasta al menos tanto como la otra
    tinta = validar._luminancia(validar.TINTA)
    for color in validar.RAMPA_AZUL + validar.RAMPA_DIVERGENTE + tuple(
            c for _, _, c in validar.TRAMOS):
        fondo = validar._luminancia(color)
        elegida, otra = ((1.0, tinta) if validar._tinta_sobre(color) == "white"
                         else (tinta, 1.0))
        assert _contraste(fondo, elegida) >= _contraste(fondo, otra), color


def test_las_casillas_y_las_barras_se_escriben_con_la_tinta_que_contrasta(
        validar, resultados_minimos, tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.axes import Axes
    escritos = []
    escribir = Axes.text

    def escribir_espia(self, x, y, texto, **kwargs):
        escritos.append((texto, kwargs.get("color")))
        return escribir(self, x, y, texto, **kwargs)

    monkeypatch.setattr(Axes, "text", escribir_espia)
    # cifras puestas a mano, lejos del punto en que la tinta cambia (la
    # contencion cambia hacia el 59 %): la prueba es del dibujo, no de la
    # simulacion. Con la regla vieja (por posicion en la escala) el 55 % y las
    # pendientes 0,65 y 1,30 irian en blanco.
    trucados = copy.deepcopy(resultados_minimos)
    for celda, contencion, pendiente in zip(
            trucados["celdas"], (1.0, 0.20, 0.55, 0.70), (1.0, 0.65, 0.79, 1.30)):
        celda["horquilla"]["todos"]["contencion"] = contencion
        celda["modelos"]["independencia"]["pendiente"] = pendiente
    validar.figura_rejilla(trucados, tmp_path / "pendiente.png", "pendiente")
    assert escritos == [("1,00", validar.TINTA), ("0,65", validar.TINTA),
                        ("0,79", validar.TINTA), ("1,30", validar.TINTA)]

    escritos.clear()
    validar.figura_rejilla(trucados, tmp_path / "contencion.png", "contencion")
    assert escritos == [("100,0 %", "white"), ("20,0 %", validar.TINTA),
                        ("55,0 %", validar.TINTA), ("70,0 %", "white")]

    escritos.clear()
    for lado in ("a_favor", "en_contra"):
        trucados["celdas"][3]["horquilla"][lado].update(bajo=0.25, contencion=0.5, sobre=0.25)
    validar.figura_horquilla(trucados, tmp_path / "horquilla.png")
    assert ("25 %", validar.TINTA) in escritos and ("50 %", validar.TINTA) in escritos
    assert all(color == validar.TINTA for _, color in escritos)


def test_la_leyenda_de_fiabilidad_da_la_ece_con_la_media_y_el_p95_de_su_suelo(
        validar, resultados_minimos, tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from matplotlib.axes import Axes
    rotulos = []
    trazar = Axes.plot

    def trazar_espia(self, *args, **kwargs):
        rotulos.append(kwargs.get("label", ""))
        return trazar(self, *args, **kwargs)

    monkeypatch.setattr(Axes, "plot", trazar_espia)
    celda = resultados_minimos["celdas"][3]
    validar.figura_fiabilidad(celda, tmp_path / "fiabilidad.png")

    def coma(x):
        return f"{x:.3f}".replace(".", ",")

    assert rotulos[0] == "calibración perfecta"
    assert rotulos[1:] == [
        f"{validar.NOMBRE_MODELO[m]} — ECE {coma(celda['modelos'][m]['ece'])} (suelo "
        f"{coma(celda['modelos'][m]['suelo']['media'])}; "
        f"p95 {coma(celda['modelos'][m]['suelo']['p95'])})"
        for m in simulacion.MODELOS]


def test_el_rojo_es_exagerar_en_la_horquilla_y_en_la_pendiente(validar):
    colores = {clave: color for clave, _, color in validar.TRAMOS}
    # λ < 0: el oraculo queda mas cerca del previo que las dos combinaciones
    assert colores["bajo"] == validar.RAMPA_DIVERGENTE[0]          # pendiente < 1
    assert colores["sobre"] == validar.RAMPA_DIVERGENTE[-1]        # pendiente > 1
    assert [clave for clave, _, _ in validar.TRAMOS] == ["bajo", "contencion", "sobre"]


def test_sin_matplotlib_se_calcula_y_dibujar_lo_dice(
        validar, resultados_minimos, tmp_path, monkeypatch):
    import sys
    calculos = []

    def calcular_falso(replicas, procesos):
        calculos.append(replicas)
        return resultados_minimos

    monkeypatch.setitem(sys.modules, "matplotlib", None)      # como si no estuviera instalado
    monkeypatch.setattr(validar, "calcular", calcular_falso)
    orden = ["--replicas", "2", "--procesos", "1", "--salida", str(tmp_path)]
    assert validar.main(orden + ["--sin-figuras"]) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["resultados_simulacion.json"]
    assert calculos == [2]
    # con figuras de una corrida anterior: pedir dibujar sale ANTES de calcular
    # y ANTES de borrarlas
    previa = tmp_path / "fiabilidad_0a.png"
    previa.write_bytes(b"de la corrida anterior")
    with pytest.raises(SystemExit, match="--sin-figuras"):
        validar.main(orden)
    assert calculos == [2]
    assert previa.read_bytes() == b"de la corrida anterior"
    with pytest.raises(SystemExit, match="extra `figuras`"):
        validar.figuras(resultados_minimos, tmp_path)
    assert previa.read_bytes() == b"de la corrida anterior"
    with pytest.raises(SystemExit, match="--sin-figuras"):
        validar.main(orden + ["--solo-documento"])
    assert [p.name for p in tmp_path.glob("*.png")] == ["fiabilidad_0a.png"]
    # y si lo que falta es el JSON, se dice eso: es lo primero que hay que arreglar
    with pytest.raises(SystemExit, match="no existe .*corre primero sin --solo-documento"):
        validar.main(["--salida", str(tmp_path / "vacia"), "--solo-documento"])
    with pytest.raises(ValueError, match="contencion"):      # se rechaza antes de importar nada
        validar.figura_rejilla(resultados_minimos, tmp_path / "x.png", "auc")


def test_si_falta_otra_cosa_no_se_dice_que_falta_matplotlib(validar, monkeypatch):
    import builtins
    importar = builtins.__import__

    def sin_numpy(nombre, *args, **kwargs):
        if nombre == "matplotlib":
            raise ModuleNotFoundError("No module named 'numpy'", name="numpy")
        return importar(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_numpy)
    with pytest.raises(ModuleNotFoundError, match="numpy"):
        validar._pyplot()


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
        leido = leer(ruta)
        # lo leido NO es lo calculado: si main dibujara con lo que tiene en
        # memoria, la figura de (0,3; 0,3) seguiria saliendo
        leido["celdas"][3]["destacada"] = False
        return leido

    monkeypatch.setattr(validar, "calcular", lambda replicas, procesos: resultados_minimos)
    monkeypatch.setattr(validar, "leer_resultados", leer_espia)
    assert resultados_minimos["celdas"][3]["destacada"] is True
    assert validar.main(["--replicas", "2", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert leidos == [tmp_path / "resultados_simulacion.json"]
    dibujadas = [n for n in NOMBRES_MINIMOS if n != "fiabilidad_r1-030_r0-030.png"]
    assert sorted(p.name for p in tmp_path.glob("*.png")) == sorted(dibujadas)
    salida = capsys.readouterr().out
    assert [linea[len("figura: "):] for linea in salida.splitlines()
            if linea.startswith("figura: ")] == [str(tmp_path / n) for n in dibujadas]


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

Esperado: `11 failed, 11 passed`. Fallan las once que dibujan o usan lo nuevo:

```
E       AttributeError: module 'validar_combinacion' has no attribute 'slug_de_celda'
E       AttributeError: module 'validar_combinacion' has no attribute 'figuras'
E       AttributeError: module 'validar_combinacion' has no attribute 'figura_fiabilidad'
E       AttributeError: module 'validar_combinacion' has no attribute 'figuras_presentes'
E       AssertionError: assert [] == [WindowsPath(...lacion.json')]
FAILED tests/test_validar_combinacion.py::test_el_slug_de_celda - AttributeEr...
FAILED tests/test_validar_combinacion.py::test_las_figuras_salen_con_su_nombre_a_300_dpi_y_con_el_rotulo
FAILED tests/test_validar_combinacion.py::test_cada_figura_se_puede_dibujar_por_separado
FAILED tests/test_validar_combinacion.py::test_la_tinta_es_la_que_mas_contrasta_con_el_color_pintado
FAILED tests/test_validar_combinacion.py::test_las_casillas_y_las_barras_se_escriben_con_la_tinta_que_contrasta
FAILED tests/test_validar_combinacion.py::test_la_leyenda_de_fiabilidad_da_la_ece_con_la_media_y_el_p95_de_su_suelo
FAILED tests/test_validar_combinacion.py::test_el_rojo_es_exagerar_en_la_horquilla_y_en_la_pendiente
FAILED tests/test_validar_combinacion.py::test_sin_matplotlib_se_calcula_y_dibujar_lo_dice
FAILED tests/test_validar_combinacion.py::test_si_falta_otra_cosa_no_se_dice_que_falta_matplotlib
FAILED tests/test_validar_combinacion.py::test_las_figuras_borran_las_propias_rancias_y_respetan_las_ajenas
FAILED tests/test_validar_combinacion.py::test_main_dibuja_las_figuras_leyendo_el_json
11 failed, 11 passed
```

`test_main_sin_figuras_no_dibuja_nada` y la prueba modificada en (a) PASAN ya en este paso: el
`main()` de la tarea 4 acepta `--sin-figuras` y todavía no dibuja. Es lo esperado: esas dos
pruebas guardan el comportamiento, no lo estrenan. La última de las once falla porque `main()`
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
# 0 (mas alla del extremo conservador), dentro, y por encima de 1. Los colores
# dicen lo mismo que en el mapa de la pendiente: rojo donde el sistema exagera
# (λ < 0: el oraculo queda mas cerca del previo que las dos combinaciones) y
# azul donde se queda corto (λ > 1).
TRAMOS = (("bajo", "por el lado conservador (λ < 0)", "#e34948"),
          ("contencion", "dentro de la horquilla", "#c9c8c3"),
          ("sobre", "más allá de la independencia (λ > 1)", "#2a78d6"))
LADOS = (("a_favor", "imagen a favor (RV ≥ 1)"),
         ("en_contra", "imagen en contra (RV < 1)"))
RAMPA_AZUL = ("#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
RAMPA_DIVERGENTE = ("#e34948", "#f0efec", "#2a78d6")
FIGURAS_GLOBALES = ("horquilla_por_celda", "contencion_rejilla", "pendiente_rejilla")
PREFIJO_FIABILIDAD = "fiabilidad_"
REJILLAS = ("contencion", "pendiente")


def _pyplot():
    try:
        import matplotlib
    except ModuleNotFoundError as error:
        if error.name != "matplotlib":          # falta otra cosa: que se vea cual
            raise
        raise SystemExit('para dibujar hace falta matplotlib, que es el extra `figuras` '
                         '(pip install -e ".[figuras]"); sin él, corre con --sin-figuras'
                         ) from None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _luminancia(color) -> float:
    """La luminancia relativa de un color (WCAG 2), de 0 (negro) a 1 (blanco)."""
    from matplotlib.colors import to_rgb
    lineal = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in to_rgb(color)]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def _tinta_sobre(color) -> str:
    """Blanco o tinta: la que mas contrasta (razon de contraste de WCAG) con el
    color que de verdad se pinta debajo, no con su posicion en la escala."""
    fondo = _luminancia(color) + 0.05
    con_blanco = 1.05 / fondo
    con_tinta = fondo / (_luminancia(TINTA) + 0.05)
    return "white" if con_blanco > con_tinta else TINTA


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

    La ECE va en la leyenda AL LADO de su suelo (media y percentil 95): sola
    no dice nada, y contra la media sola parece fuera del ruido la que no lo
    esta."""
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
                label=f"{NOMBRE_MODELO[modelo]} — ECE {_coma(m['ece'], 3)} (suelo "
                      f"{_coma(m['suelo']['media'], 3)}; p95 {_coma(m['suelo']['p95'], 3)})")
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
                            va="center", fontsize=8, color=_tinta_sobre(color))
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
        decimales, unidad = 1, " %"
        titulo = f"Contención del oráculo en la horquilla, por celda — {ROTULO}"
        barra = "contención (% de los casos concordantes)"
    else:
        presentes = [v for fila in numeros for v in fila if v == v]
        desvio = max([abs(v - 1.0) for v in presentes] + [0.05])
        mapa = LinearSegmentedColormap.from_list("divergente", RAMPA_DIVERGENTE)
        norma = TwoSlopeNorm(vcenter=1.0, vmin=1.0 - desvio, vmax=1.0 + desvio)
        decimales, unidad = 2, ""
        titulo = f"Pendiente de la independencia, por celda — {ROTULO}"
        barra = "pendiente de calibración (< 1 exagera; > 1 se queda corta)"
    mapa = mapa.with_extremes(bad="#f0efec")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    imagen = ax.imshow(numeros, cmap=mapa, norm=norma, origin="lower", aspect="auto")
    for i, fila in enumerate(numeros):
        for j, v in enumerate(fila):
            ax.text(j, i, _coma(v, decimales) + (unidad if v == v else ""),
                    ha="center", va="center", fontsize=10 if len(rejilla) <= 5 else 8,
                    color=_tinta_sobre(mapa(norma(v))) if v == v else TINTA)
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
    que ya no son las del JSON. Sin matplotlib sale ANTES de borrar nada."""
    _pyplot()
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

Y, para que sin matplotlib no se calcule en vano (pero diciendo antes, si es el
caso, que lo que falta es el JSON), busca exactamente:

```python
    salida = Path(args.salida)
    ruta = salida / NOMBRE_RESULTADOS
    if not args.solo_documento:
        escribir_resultados(calcular(args.replicas, args.procesos), ruta)
        print(f"resultados: {ruta}")
    elif not ruta.is_file():
        raise SystemExit(f"no existe {ruta}: corre primero sin --solo-documento")
```

y sustitúyelo por:

```python
    salida = Path(args.salida)
    ruta = salida / NOMBRE_RESULTADOS
    if args.solo_documento and not ruta.is_file():
        raise SystemExit(f"no existe {ruta}: corre primero sin --solo-documento")
    if not args.sin_figuras:
        _pyplot()                 # sin matplotlib se sale ANTES de calcular nada
    if not args.solo_documento:
        escribir_resultados(calcular(args.replicas, args.procesos), ruta)
        print(f"resultados: {ruta}")
```

- [ ] **Paso 6: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_validar_combinacion.py`

Esperado: `22 passed`, sin avisos (tarda cerca de medio minuto). Si aparece un `PendingDeprecationWarning` de
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
- fiabilidad: la leyenda (arriba a la izquierda, con la ECE al lado de la media y del p95 de su suelo: «ECE 0,052 (suelo 0,010; p95 0,015)») no tapa ningún punto; las marcas de los ejes llevan coma («0,2»);
- horquilla: siete barras por panel, con 0A arriba y al 100 % en gris; en rojo el lado conservador (λ < 0, el sistema exagera) y en azul más allá de la independencia (λ > 1); los porcentajes escritos dentro de los tramos de 12 % o más; la leyenda de los tres tramos debajo, sin pisar el rótulo del eje;
- rejillas: 25 casillas con su cifra («70,7 %», «0,79»), con ρ1 = 0 abajo y ρ0 = 0 a la izquierda; la barra de color de la pendiente tiene el gris en 1,00; cada cifra se lee sin esfuerzo (en blanco solo sobre los azules oscuros de la contención).

No copies nada de `<CARPETA_TEMPORAL>` al repo.

- [ ] **Paso 9: Commit**

```bash
git add pyproject.toml scripts/validar_combinacion.py tests/test_validar_combinacion.py
git commit -m "feat(validacion): las figuras de la simulacion, a 300 DPI y desde el JSON (SP5-B1 T5)" -m "Fiabilidad por deciles de 0A y las destacadas (la ECE, con la media y el p95 de su suelo), la horquilla por celda y lado, y los mapas de contencion y de pendiente. Se dibujan leyendo resultados_simulacion.json; matplotlib es el extra figuras y solo se importa dentro de las funciones. Todo titulo lleva el rotulo de simulacion semisintetica." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 6: El documento de análisis

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/informe.py`
- Modificar: `scripts/validar_combinacion.py` (el `import` del paquete, un bloque nuevo «EL DOCUMENTO» antes de `main()`, y dos líneas al final de `main()`)
- Prueba: `tests/test_informe.py` (nuevo, 38 pruebas)
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


SIN_INTERVALO = " (estimación puntual, sin intervalo)"
NO_SE_PUEDE = ("no se puede decir: la estimación y su intervalo no quedan enteros a un lado "
               "del umbral")


def _veredictos(documento: str) -> dict:
    """{celda: veredicto}, leido de la tabla del veredicto."""
    horquilla = _seccion(documento, "La horquilla frente al oráculo")
    tabla = horquilla.split("| celda | contención | umbral | veredicto |\n")[1]
    filas = tabla.split("\n\n")[0].splitlines()
    assert filas[0] == "| :--- | ---: | ---: | :--- |"
    return {f.split(" | ")[0][2:]: f.split(" | ")[-1][:-2] for f in filas[1:]}


def _con_hipotesis(resultados, indice, contencion, intervalo):
    """Una copia con la contencion de una celda puesta a mano. El JSON lleva
    ademas `se_sostiene`, calculado sobre la estimacion sin redondear."""
    otro = copy.deepcopy(resultados)
    celda = otro["celdas"][indice]
    celda["hipotesis"]["se_sostiene"] = contencion is not None and contencion >= 0.9
    celda["hipotesis"]["contencion"] = contencion
    celda["horquilla"]["todos"]["contencion"] = contencion
    if intervalo is None:
        celda.get("intervalos", {}).pop("horquilla.todos.contencion", None)
    else:
        celda["intervalos"]["horquilla.todos.contencion"] = list(intervalo)
    return otro


def test_el_veredicto_lee_el_intervalo_y_dice_cuando_solo_hay_estimacion(
        texto, resultados_minimos):
    celda = resultados_minimos["celdas"][3]
    assert celda["hipotesis"]["se_sostiene"] is False
    assert celda["intervalos"]["horquilla.todos.contencion"][1] < 0.9
    assert "intervalos" not in resultados_minimos["celdas"][1]
    assert _veredictos(texto) == {
        "0A": "se sostiene",
        "(0; 0,3)": "no se sostiene" + SIN_INTERVALO,
        "(0,3; 0)": "no se sostiene" + SIN_INTERVALO,
        "(0,3; 0,3)": "no se sostiene"}
    casos = [
        (3, 0.95, (0.91, 0.97), "se sostiene"),
        (3, 0.95, (0.90, 0.97), "se sostiene"),                  # el umbral vale
        (3, 0.95, (0.8996, 0.97), "se sostiene"),                # se imprime «90,0»
        (3, 0.90, (0.90, 0.90), "se sostiene"),
        # restando en coma flotante, un 90 % exacto es 0,8999999999999999
        (3, 1.0 - 0.06 - 0.04, (0.91, 0.95), "se sostiene"),
        (3, 0.8996, (0.91, 0.95), "se sostiene"),                # se imprime «90,0 %»
        (3, 0.8996, None, "se sostiene" + SIN_INTERVALO),
        (3, 0.85, (0.80, 0.8996), NO_SE_PUEDE),                  # se imprime «90,0»
        (3, 0.91, (0.88, 0.97), NO_SE_PUEDE),                    # el intervalo lo cruza
        (3, 0.89, (0.85, 0.93), NO_SE_PUEDE),
        (3, 0.91, (0.80, 0.89), NO_SE_PUEDE),            # la estimacion, del otro lado
        (3, 0.89, (0.91, 0.95), NO_SE_PUEDE),            # y al reves
        (3, 0.85, (0.80, 0.89), "no se sostiene"),
        (3, 0.8994, (0.80, 0.8994), "no se sostiene"),           # se imprime «89,9»
        (3, 0.95, None, "se sostiene" + SIN_INTERVALO),
        (1, 0.913, None, "se sostiene" + SIN_INTERVALO),
        (1, 0.437, None, "no se sostiene" + SIN_INTERVALO),
        (3, None, (0.80, 0.89),
         "no se puede decir: no hay casos concordantes con horquilla"),
        (3, 0.85, (float("nan"), 0.89), "no se sostiene" + SIN_INTERVALO),
    ]
    for indice, contencion, intervalo, esperado in casos:
        otro = _con_hipotesis(resultados_minimos, indice, contencion, intervalo)
        nombre = otro["celdas"][indice]["nombre"]
        documento = informe.redactar(otro)
        assert _veredictos(documento)[nombre] == esperado, (contencion, intervalo)
        if contencion is not None and 0.8995 < contencion < 0.9:
            # lo que el lector ve al lado del veredicto
            assert f"| {nombre} | 90,0 % " in documento
    # junto a la tabla se dice con que se decide, y que el JSON va sin redondear
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    assert ("Se decide con la contención tal como se imprime (un «90,0 %» alcanza un umbral "
            "del 90 %); el campo `se_sostiene` del fichero de resultados se calcula sin "
            "redondear:") in horquilla


def test_el_umbral_se_imprime_con_los_decimales_con_que_se_compara(resultados_minimos):
    assert [informe._umbral(x) for x in (0.9, 0.905, 0.8, 0.9004, 1.0)] == [
        "90", "90,5", "80", "90", "100"]
    otro = copy.deepcopy(resultados_minimos)
    otro["parametros"]["hipotesis_contencion"] = 0.905
    for celda in otro["celdas"]:
        celda["hipotesis"]["umbral"] = 0.905
    otro["celdas"][3]["horquilla"]["todos"]["contencion"] = 0.902
    otro["celdas"][3]["intervalos"]["horquilla.todos.contencion"] = [0.88, 0.904]
    documento = informe.redactar(otro)
    # un 90,2 % no alcanza un 90,5 %, y la fila lo deja ver
    assert "| (0,3; 0,3) | 90,2 % (IC 95 %: 88,0 a 90,4) | ≥ 90,5 % | no se sostiene |" in documento
    assert "en ≥ 90,5 % de los concordantes»" in documento
    assert "(contención ≥ 90,5 % de los concordantes)" in documento
    assert "≥ 90 %" not in documento and "≥ 91 %" not in documento


def test_la_lectura_se_genera_desde_las_cifras(texto, resultados_minimos):
    lectura = _seccion(texto, "Lectura de los resultados")
    celda = resultados_minimos["celdas"][3]
    assert celda["modelos"]["independencia"]["pendiente"] < 1
    assert "menor que 1: 1 de 1: (0,3; 0,3), " in lectura
    assert informe.porcentaje(celda["horquilla"]["a_favor"]["bajo"]) in lectura
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["modelos"]["independencia"]["pendiente"] = 1.25
    otro["celdas"][3]["intervalos"]["modelos.independencia.pendiente"] = [1.1, 1.4]
    nueva = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "menor que 1: 0 de 1. Una pendiente menor que 1 es" in nueva


def _hipotesis(documento: str) -> str:
    """La frase de la hipotesis, de la lectura."""
    lectura = _seccion(documento, "Lectura de los resultados")
    frases = [l for l in lectura.splitlines() if l.startswith("- **La hipótesis de la horquilla**")]
    assert len(frases) == 1
    return frases[0]


def test_la_lectura_de_la_hipotesis_cuenta_0a_aparte_y_lee_los_intervalos(
        texto, resultados_minimos):
    # la precondicion: en la rejilla minima ninguna celda con dependencia
    # llega al umbral, ni de lejos
    assert [c["horquilla"]["todos"]["contencion"] < 0.8
            for c in resultados_minimos["celdas"][1:]] == [True] * 3
    assert _hipotesis(texto) == (
        "- **La hipótesis de la horquilla** (contención ≥ 90 % de los concordantes). "
        "0A es la comprobación de la métrica y se cuenta aparte. "
        "Celdas con dependencia: 3; con intervalo, 1. "
        "Donde hay intervalo decide el intervalo entero. "
        "Con intervalo, celdas en las que se sostiene: ninguna. "
        "Con intervalo, celdas en las que no se sostiene: 1, que es (0,3; 0,3). "
        "Con intervalo, celdas en las que no se puede decir, porque la estimación y su "
        "intervalo no quedan enteros a un lado del umbral: ninguna. "
        "Sin intervalo, 2: solo hay estimación puntual. "
        "Sin intervalo, celdas en las que la estimación alcanza el umbral: ninguna.")
    # cada cuenta dice de que celdas es: la tabla del veredicto tiene mas
    # filas «no se sostiene» que celdas con intervalo
    assert not re.search(r"(?<!intervalo, )celdas en las que", _hipotesis(texto))
    # ninguna frase pone «ninguna» detras de un verbo: «no se sostiene en
    # ninguna» diria lo contrario de lo que cuenta
    for documento in (texto, informe.redactar(resultados_minimos, {})):
        assert not re.search(r"\b(en|de) ninguna\b", documento)
    # 0A no cuenta aunque se sostenga; la que solo tiene estimacion se dice
    otro = _con_hipotesis(resultados_minimos, 1, 0.913, None)
    assert ("Sin intervalo, 2: solo hay estimación puntual. Sin intervalo, celdas en las "
            "que la estimación alcanza el umbral: 1, que es (0; 0,3).") in _hipotesis(
        informe.redactar(otro))
    assert "Con intervalo, celdas en las que se sostiene: ninguna." in _hipotesis(
        informe.redactar(otro))
    otro = _con_hipotesis(resultados_minimos, 3, 0.95, (0.91, 0.97))
    assert ("Con intervalo, celdas en las que se sostiene: 1, que es (0,3; 0,3). Con "
            "intervalo, celdas en las que no se sostiene: ninguna.") in _hipotesis(
        informe.redactar(otro))
    otro = _con_hipotesis(resultados_minimos, 3, 0.91, (0.88, 0.97))
    frase = _hipotesis(informe.redactar(otro))
    assert ("Con intervalo, celdas en las que se sostiene: ninguna. Con intervalo, celdas "
            "en las que no se sostiene: ninguna.") in frase
    assert "a un lado del umbral: 1, que es (0,3; 0,3)." in frase
    # sin bootstrap no hay intervalos que leer, y no se finge
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        celda.pop("intervalos", None)
    documento = informe.redactar(otro)
    frase = _hipotesis(documento)
    assert "Celdas con dependencia: 3; con intervalo, 0. Sin intervalo, 3:" in frase
    assert "Donde hay intervalo" not in frase
    assert "- **Los intervalos.**" not in documento
    assert "- **Los intervalos.**" in texto
    # todas con intervalo: no se habla de estimaciones sueltas
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"][1:3]:
        celda["intervalos"] = {"horquilla.todos.contencion": [0.4, 0.5]}
    frase = _hipotesis(informe.redactar(otro))
    assert "Celdas con dependencia: 3; con intervalo, 3." in frase
    assert "Sin intervalo" not in frase and "estimación alcanza" not in frase
    # una celda sin casos concordantes con horquilla se cuenta aparte
    otro = _con_hipotesis(resultados_minimos, 2, None, None)
    frase = _hipotesis(informe.redactar(otro))
    assert frase.endswith("Celdas sin casos concordantes con horquilla: 1, que es (0,3; 0).")
    assert "Sin intervalo, 1:" in frase
    assert "sin casos concordantes" not in _hipotesis(texto)
    # sin 0A no se habla de 0A
    otro = copy.deepcopy(resultados_minimos)
    del otro["celdas"][0]
    assert "0A" not in _hipotesis(informe.redactar(otro))


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
    # el alcance no afirma un resultado: lo que dice esta corrida va aparte
    assert "**Puede decir:**" in limites and "**Puede afirmar:**" not in limites
    assert "- si el sistema reproduce caso a caso" in limites
    assert "- si, **cuando** la puntuación tiene la exactitud publicada" in limites
    # cada punto remite a donde se responde
    assert ("(0A: lo comprueban las pruebas de `tests/test_validacion_0a.py`; la fila 0A de "
            "la horquilla lo acompaña, como control más débil y solo para los concordantes)"
            ) in limites
    assert limites.count("caso a caso") == 1
    assert ("Lo demás se lee en «Lectura de los resultados» y, lo del previo, en "
            "«Sensibilidad al previo».") in limites
    assert "Cada placa con su clínica sorteada es una viñeta." in _seccion(
        texto, "Insumos y parámetros")


def test_los_limites_dicen_lo_que_dice_esta_corrida(texto, resultados_minimos):
    limites = _seccion(texto, "Lo que esta simulación puede afirmar y lo que no")
    cero = resultados_minimos["celdas"][0]
    m = cero["modelos"]["independencia"]
    assert m["ece"] <= m["suelo"]["p95"]
    assert ("En esta corrida, la fila 0A de la horquilla se cumple; la pendiente de la "
            "combinación por independencia en 0A es "
            + informe.numero(m["pendiente"], 2)) in limites
    assert (f"y su ECE ({informe.numero(m['ece'], 3)}) no supera el percentil 95 de su "
            f"suelo") in limites
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["horquilla"]["todos"].update(bajo=0.01, contencion=0.99)
    otro["celdas"][0]["modelos"]["independencia"]["ece"] = 0.5
    otro["celdas"][0]["intervalos"]["modelos.independencia.pendiente"] = [1.05, 1.2]
    limites = _seccion(informe.redactar(otro),
                       "Lo que esta simulación puede afirmar y lo que no")
    assert "la fila 0A de la horquilla **no se cumple**" in limites
    assert "su intervalo no contiene el 1" in limites
    assert "y su ECE (0,500) supera el percentil 95 de su suelo" in limites
    del otro["celdas"][0]
    limites = _seccion(informe.redactar(otro),
                       "Lo que esta simulación puede afirmar y lo que no")
    assert ("Esta corrida no incluye la celda 0A: de los dos primeros puntos no dice nada."
            ) in limites
    assert "En esta corrida, la fila 0A" not in limites
    # sin casos con horquilla la comprobacion no se puede hacer: no es un fallo
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["horquilla"]["todos"].update(
        n=0, bajo=None, sobre=None, contencion=None)
    limites = _seccion(informe.redactar(otro),
                       "Lo que esta simulación puede afirmar y lo que no")
    assert "la fila 0A de la horquilla **no se puede comprobar**; la pendiente" in limites


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


# --------------------------------------------------------------------------
# Una prueba por rama: cada frase cuya verdad depende de los datos, con
# resultados trucados para que caiga en cada una de sus ramas.
# --------------------------------------------------------------------------
def test_la_ece_se_lee_frente_al_p95_de_su_suelo(texto, resultados_minimos):
    suelo = {"media": 0.010, "p95": 0.020}
    assert informe._frente_al_suelo(0.020, suelo).startswith("no supera el percentil 95")
    # las dos se imprimen «0,020»: el documento no puede decir que una supera a la otra
    assert informe._frente_al_suelo(0.0201, suelo).startswith("no supera el percentil 95")
    assert informe._frente_al_suelo(0.0204, {"media": 0.01, "p95": 0.0196}).startswith(
        "no supera")
    assert informe._frente_al_suelo(0.0206, suelo).startswith("supera el percentil 95")
    assert informe._frente_al_suelo(0.015, suelo).startswith("no supera")   # no es la media
    for ece, p95 in ((None, 0.02), (0.02, None), (float("nan"), 0.02)):
        assert informe._frente_al_suelo(ece, {"media": 0.01, "p95": p95}) == (
            "no se puede comparar con su suelo")
    otro = copy.deepcopy(resultados_minimos)
    otro["imagen_sola"]["ece"] = otro["imagen_sola"]["suelo"]["p95"] + 0.001
    imagen = _seccion(informe.redactar(otro), "La imagen sola")
    assert ") supera el percentil 95 de su suelo: hay descalibración" in imagen
    otro["imagen_sola"]["ece"] = otro["imagen_sola"]["suelo"]["p95"] - 0.001
    imagen = _seccion(informe.redactar(otro), "La imagen sola")
    assert ") no supera el percentil 95 de su suelo: no se distingue" in imagen
    otro["celdas"][0]["modelos"]["independencia"]["ece"] = 0.5
    assert ") supera el percentil 95 de su suelo" in _seccion(
        informe.redactar(otro), "Escenario 0A: la aritmética")
    assert ") no supera el percentil 95 de su suelo" in _seccion(
        texto, "Escenario 0A: la aritmética")


def test_la_fila_0a_dice_si_la_metrica_se_cumple(texto, resultados_minimos):
    cero = _seccion(texto, "Escenario 0A: la aritmética")
    assert "Se cumple: la métrica de la horquilla pasa su comprobación en el caso nulo." in cero
    assert "NO se cumple" not in cero
    n = resultados_minimos["celdas"][0]["horquilla"]["todos"]["n"]
    for cambio, fuera in ((dict(bajo=10 / n, contencion=1 - 10 / n), "quedan fuera de la horquilla 10"),
                          (dict(sobre=3 / n, contencion=1 - 3 / n), "quedan fuera de la horquilla 3"),
                          # un solo caso fuera se imprime «0,0 %» y «100,0 %»
                          (dict(bajo=1 / n, contencion=1 - 1 / n), "queda fuera de la horquilla 1")):
        otro = copy.deepcopy(resultados_minimos)
        otro["celdas"][0]["horquilla"]["todos"].update(cambio)
        cero = _seccion(informe.redactar(otro), "Escenario 0A: la aritmética")
        assert (f"**NO se cumple: {fuera} de los {informe.entero(n)} concordantes. La "
                f"métrica de la horquilla o el generador tienen un defecto") in cero, cambio
        assert "Se cumple: la métrica" not in cero
    # sin casos no se puede comprobar, que no es lo mismo que no cumplirse
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["horquilla"]["todos"].update(
        n=0, bajo=None, sobre=None, contencion=None)
    documento = informe.redactar(otro)
    cero = _seccion(documento, "Escenario 0A: la aritmética")
    assert "**No se puede comprobar: no hay casos concordantes con horquilla" in cero
    assert "NO se cumple" not in cero and "Se cumple: la métrica" not in cero
    assert "tienen un defecto" not in cero
    assert "Horquilla: no hay casos con horquilla." in _seccion(
        documento, "Lectura de los resultados")
    otro = copy.deepcopy(resultados_minimos)
    del otro["celdas"][0]
    documento = informe.redactar(otro)
    assert "Esta corrida no incluye la celda 0A." in _seccion(
        documento, "Escenario 0A: la aritmética")
    assert "Esta corrida no calculó 0C." in _seccion(
        documento, "0C: optimismo de la derivación (cálculo, no experimento)")
    assert "- **0A.**" not in documento


def test_la_pendiente_de_0a_dice_si_su_intervalo_contiene_el_1(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    cero = otro["celdas"][0]
    cero["modelos"]["independencia"]["pendiente"] = 1.03
    for intervalo, esperado in (([0.91, 1.09], "1,03 (IC 95 %: 0,91 a 1,09); su intervalo contiene el 1."),
                                ([1.0, 1.09], "1,03 (IC 95 %: 1,00 a 1,09); su intervalo contiene el 1."),
                                ([1.004, 1.09], "1,03 (IC 95 %: 1,00 a 1,09); su intervalo contiene el 1."),
                                ([1.01, 1.09], "1,03 (IC 95 %: 1,01 a 1,09); su intervalo no contiene el 1."),
                                ([0.8, 0.99], "1,03 (IC 95 %: 0,80 a 0,99); su intervalo no contiene el 1."),
                                ([0.9, 0.996], "1,03 (IC 95 %: 0,90 a 1,00); su intervalo contiene el 1."),
                                ([0.9, 0.994], "1,03 (IC 95 %: 0,90 a 0,99); su intervalo no contiene el 1.")):
        cero["intervalos"]["modelos.independencia.pendiente"] = intervalo
        lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
        assert ("- **0A.** La pendiente de la combinación por independencia es "
                + esperado + " Horquilla: queda dentro el 100,0 %; ninguna cola tiene casos."
                ) in lectura
    del cero["intervalos"]["modelos.independencia.pendiente"]
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "independencia es 1,03. Horquilla: " in lectura


def _con_pendiente(resultados, clave, pendiente, intervalo):
    otro = copy.deepcopy(resultados)
    celda = otro["celdas"][3]
    celda["modelos"][clave]["pendiente"] = pendiente
    if intervalo is None:
        del celda["intervalos"][f"modelos.{clave}.pendiente"]
    else:
        celda["intervalos"][f"modelos.{clave}.pendiente"] = list(intervalo)
    return _seccion(informe.redactar(otro), "Lectura de los resultados")


def test_la_pendiente_de_la_independencia_se_lee_con_su_intervalo(resultados_minimos):
    lectura = _con_pendiente(resultados_minimos, "independencia", 0.8, (0.7, 0.9))
    assert ("- **La independencia.** Celdas destacadas en las que la estimación de la "
            "pendiente de la combinación por independencia es menor que 1: 1 de 1: "
            "(0,3; 0,3), 0,80 (IC 95 %: 0,70 a 0,90). Una pendiente menor que 1 es la forma "
            "cuantitativa de «exagera».") in lectura
    assert ("- De esas, con el intervalo entero por debajo de 1 (exagera): 1 de 1: "
            "(0,3; 0,3).") in lectura
    assert "En sentido contrario, la estimación de la pendiente de la combinación" not in lectura
    lectura = _con_pendiente(resultados_minimos, "independencia", 0.95, (0.85, 1.0))
    assert "- De esas, con el intervalo entero por debajo de 1 (exagera): 0 de 1." in lectura
    lectura = _con_pendiente(resultados_minimos, "independencia", 0.8, None)
    assert "menor que 1: 1 de 1: (0,3; 0,3), 0,80. Una pendiente" in lectura
    assert "con el intervalo entero por debajo de 1" not in lectura.split(
        "**El extremo conservador.**")[0]
    lectura = _con_pendiente(resultados_minimos, "independencia", 1.25, (1.1, 1.4))
    assert ("- En sentido contrario, la estimación de la pendiente de la combinación por "
            "independencia es mayor que 1: 1 de 1: (0,3; 0,3), 1,25 (IC 95 %: 1,10 a 1,40)."
            ) in lectura
    assert ("- De esas, con el intervalo entero por encima de 1 (se queda corta): 1 de 1: "
            "(0,3; 0,3).") in lectura
    for pendiente in (1.0, 0.996, 1.004):                    # las tres se imprimen «1,00»
        lectura = _con_pendiente(resultados_minimos, "independencia", pendiente, (0.9, 1.1))
        assert "menor que 1: 0 de 1. Una pendiente" in lectura   # ni de un lado ni del otro
        assert "En sentido contrario, la estimación de la pendiente de la comb" not in lectura
    assert ("Las comparaciones con un umbral o con un valor de referencia se hacen con las "
            "cifras tal como se imprimen: «por encima» y «por debajo» son estrictos, y un "
            "umbral «≥» se alcanza también con la igualdad.") in lectura
    # «exagera» y «se queda corta» se dicen del intervalo, nunca de la estimacion sola
    assert not re.search(r"que 1 \((exagera|se queda)", lectura)


def test_la_pendiente_del_extremo_conservador_se_lee_con_su_intervalo(resultados_minimos):
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.12, (1.02, 1.21))
    assert ("- **El extremo conservador.** Celdas destacadas en las que la estimación de su "
            "pendiente es mayor que 1: 1 de 1: (0,3; 0,3), 1,12 (IC 95 %: 1,02 a 1,21)."
            ) in lectura
    assert ("- De esas, con el intervalo entero por encima de 1 (se queda corto): 1 de 1: "
            "(0,3; 0,3).") in lectura
    # la estimacion por encima de 1 no basta si el intervalo contiene el 1
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.03, (0.95, 1.12))
    assert "pendiente es mayor que 1: 1 de 1: (0,3; 0,3), 1,03" in lectura
    assert "- De esas, con el intervalo entero por encima de 1 (se queda corto): 0 de 1." in lectura
    # un extremo 1,004 se imprime «1,00»: no queda por encima de 1
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.13, (1.004, 1.17))
    assert "(0,3; 0,3), 1,13 (IC 95 %: 1,00 a 1,17)." in lectura
    assert "- De esas, con el intervalo entero por encima de 1 (se queda corto): 0 de 1." in lectura
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.13, (1.006, 1.17))
    assert ("- De esas, con el intervalo entero por encima de 1 (se queda corto): 1 de 1: "
            "(0,3; 0,3).") in lectura
    # y si queda entero por debajo, ni el extremo conservador basta: se dice
    lectura = _con_pendiente(resultados_minimos, "conservador", 0.9, (0.84, 0.98))
    assert "pendiente es mayor que 1: 0 de 1." in lectura
    assert ("- En sentido contrario, la estimación de la pendiente del extremo conservador "
            "es menor que 1: 1 de 1: (0,3; 0,3), 0,90 (IC 95 %: 0,84 a 0,98).") in lectura
    assert ("- De esas, con el intervalo entero por debajo de 1 (también el extremo "
            "conservador exagera): 1 de 1: (0,3; 0,3).") in (
        lectura.split("**El extremo conservador.**")[1])
    assert not re.search(r"que 1 \((también|se queda)", lectura)


def test_las_diferencias_pareadas_se_leen_por_su_intervalo(resultados_minimos):
    def lectura(clave, metrica, intervalo):
        otro = copy.deepcopy(resultados_minimos)
        otro["celdas"][3]["intervalos"][f"pareadas.{clave}.{metrica}"] = list(intervalo)
        return _seccion(informe.redactar(otro), "Lectura de los resultados")

    def frase(texto, titulo):
        return next(l for l in texto.splitlines()
                    if l.startswith(f"- **Frente a la imagen sola: {titulo}.**"))

    cabecera = "Celdas destacadas con intervalo: 1. "
    la = frase(lectura("independencia", "auc", (0.01, 0.03)), "ΔAUC, combinación, independencia")
    assert la.endswith(cabecera + "Con el intervalo entero del lado de la mejora (por "
                       "encima de 0): 1, que es (0,3; 0,3). Con el intervalo entero del lado "
                       "contrario: ninguna. Con el 0 dentro del intervalo: ninguna.")
    la = frase(lectura("independencia", "auc", (-0.03, -0.01)), "ΔAUC, combinación, independencia")
    assert la.endswith("(por encima de 0): ninguna. Con el intervalo entero del lado "
                       "contrario: 1, que es (0,3; 0,3). Con el 0 dentro del intervalo: "
                       "ninguna.")
    for intervalo in ((-0.01, 0.0), (-0.01, 0.02), (0.0004, 0.03), (-0.03, -0.0004)):
        la = frase(lectura("independencia", "auc", intervalo),
                   "ΔAUC, combinación, independencia")
        assert la.endswith("(por encima de 0): ninguna. Con el intervalo entero del lado "
                           "contrario: ninguna. Con el 0 dentro del intervalo: 1, que es "
                           "(0,3; 0,3)."), intervalo
    # en el Brier la mejora es bajar
    la = frase(lectura("conservador", "brier", (-0.02, -0.01)),
               "ΔBrier, combinación, extremo conservador")
    assert la.endswith(cabecera + "Con el intervalo entero del lado de la mejora (por "
                       "debajo de 0): 1, que es (0,3; 0,3). Con el intervalo entero del lado "
                       "contrario: ninguna. Con el 0 dentro del intervalo: ninguna.")
    la = frase(lectura("conservador", "brier", (0.001, 0.01)),
               "ΔBrier, combinación, extremo conservador")
    assert la.endswith("Con el intervalo entero del lado contrario: 1, que es (0,3; 0,3). "
                       "Con el 0 dentro del intervalo: ninguna.")
    # sin intervalos no hay frase
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        celda.pop("intervalos", None)
    assert "Frente a la imagen sola" not in informe.redactar(otro)
    assert len([l for l in informe.redactar(resultados_minimos).splitlines()
                if l.startswith("- **Frente a la imagen sola: ")]) == 4


def test_las_colas_en_todas_sus_ramas():
    def colas(bajo, sobre):
        dentro = None if bajo is None or sobre is None else 1.0 - bajo - sobre
        return informe._colas({"bajo": bajo, "sobre": sobre, "contencion": dentro})

    assert colas(None, 0.1) == colas(0.1, None) == "no hay casos con horquilla"
    assert colas(0.0, 0.0) == "queda dentro el 100,0 %; ninguna cola tiene casos"
    assert colas(0.2, 0.2) == ("queda dentro el 60,0 %; las dos colas pesan lo mismo "
                               "(20,0 % cada una)")
    # las dos se imprimen «20,0 %»: ninguna es «la mayor»
    assert colas(0.2001, 0.2004) == ("queda dentro el 60,0 %; las dos colas pesan lo mismo "
                                     "(20,0 % cada una)")
    # con un solo caso en una cola no se dice que ninguna tiene casos
    assert colas(0.0004, 0.0) == ("queda dentro el 100,0 %; las dos colas pesan lo mismo "
                                  "(0,0 % cada una)")
    assert colas(0.3, 0.1) == ("queda dentro el 60,0 %; la cola mayor es la del lado "
                               "conservador (30,0 %, frente a 10,0 % más allá de la "
                               "independencia)")
    assert colas(0.1, 0.3) == ("queda dentro el 60,0 %; la cola mayor es la de más allá de "
                               "la independencia (30,0 %, frente a 10,0 % por el lado "
                               "conservador)")


def test_el_reparto_de_0c(texto, resultados_minimos):
    titulo = "0C: optimismo de la derivación (cálculo, no experimento)"
    por_puntuacion = resultados_minimos["celdas"][0]["optimismo_de_la_derivacion"][
        "por_puntuacion"]
    assert [(f["k"], f["rv_derivacion"], f["rv_validacion"]) for f in por_puntuacion] == [
        (0, 0.12, 0.19), (1, 0.20, 0.19), (2, 0.70, 1.04),
        (3, 1.64, 1.04), (4, 7.18, 8.33), (5, 17.5, 8.33)]
    assert ("La RV de la derivación es más extrema que la de validación en k = 0, 2, 3 y 5 "
            "y menos extrema en k = 1 y 4 (más extrema: más lejos de 1). El «optimismo» de "
            "la derivación no es uniforme.") in _seccion(texto, titulo)

    def con(validacion):
        otro = copy.deepcopy(resultados_minimos)
        filas = otro["celdas"][0]["optimismo_de_la_derivacion"]["por_puntuacion"]
        for fila, rv in zip(filas, validacion):
            fila["rv_validacion"] = rv
        return _seccion(informe.redactar(otro), titulo)

    todas = con([0.5, 0.5, 0.9, 1.1, 2.0, 2.0])
    assert ("La RV de la derivación es más extrema que la de validación en k = 0, 1, 2, 3, "
            "4 y 5 (más extrema: más lejos de 1).") in todas
    assert "no es uniforme" not in todas
    ninguna = con([0.01, 0.01, 0.1, 9.0, 99.0, 99.0])
    assert "La RV de la derivación es menos extrema en k = 0, 1, 2, 3, 4 y 5 (" in ninguna
    assert "no es uniforme" not in ninguna
    empate = con([0.12, 0.19, 1.04, 1.04, 8.33, 8.33])
    assert ("más extrema que la de validación en k = 2, 3 y 5, menos extrema en k = 1 y 4 "
            "y igual de extrema en k = 0 (") in empate
    assert "no es uniforme" in empate
    # «más» e «igual», sin «menos»: tampoco es uniforme
    sin_menos = con([0.12, 0.5, 0.9, 1.1, 2.0, 2.0])
    assert ("La RV de la derivación es más extrema que la de validación en k = 1, 2, 3, 4 "
            "y 5 y igual de extrema en k = 0 (") in sin_menos
    assert "no es uniforme" in sin_menos
    solo_iguales = con([0.12, 0.20, 0.70, 1.64, 7.18, 17.5])
    assert "La RV de la derivación es igual de extrema en k = 0, 1, 2, 3, 4 y 5 (" in solo_iguales
    assert "no es uniforme" not in solo_iguales
    # «menos» e «igual», sin «más»: nunca es mas extrema, y no hay optimismo
    # que repartir
    sin_mas = con([0.12, 0.01, 0.1, 9.0, 99.0, 99.0])
    assert ("La RV de la derivación es menos extrema en k = 1, 2, 3, 4 y 5 y igual de "
            "extrema en k = 0 (") in sin_mas
    assert "no es uniforme" not in sin_mas


def test_la_nota_del_rho_extremo_sale_de_la_rejilla(texto, resultados_minimos):
    nota = "sobre la puntuación es un caso extremo, no plausible"
    assert max(resultados_minimos["parametros"]["rejilla"]) < informe.RHO_EXTREMO
    assert nota not in texto
    otro = copy.deepcopy(resultados_minimos)
    otro["parametros"]["rejilla"] = [0.0, 0.3, 0.6]
    assert f"Un ρ de 0,6 {nota}" in _seccion(
        informe.redactar(otro), "Dependencia entre clínica e imagen")


def test_sin_destacadas_y_sin_sensibilidad_se_dice(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        celda["destacada"] = False
        celda.pop("sensibilidad_al_previo", None)
    documento = informe.redactar(otro)
    assert "esta corrida no tiene celdas destacadas." in _seccion(
        documento, "Insumos y parámetros")
    assert "Esta corrida no tiene celdas destacadas." in _seccion(
        documento, "Cuánto de su evidencia conserva la puntuación")
    assert "- Esta corrida no tiene celdas destacadas." in _seccion(
        documento, "Lectura de los resultados")
    assert "Esta corrida no calculó la sensibilidad al previo." in _seccion(
        documento, "Sensibilidad al previo")
    assert "Hacia qué lado cae el oráculo" not in documento


def test_la_fraccion_de_0a_solo_se_da_por_entera_si_lo_es(texto, resultados_minimos):
    titulo = "Cuánto de su evidencia conserva la puntuación"
    assert ("es 1,00 con la imagen a favor y 1,00 con la imagen en contra: sin dependencia "
            "la puntuación conserva toda su evidencia.") in _seccion(texto, titulo)
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["escala_legible"]["en_contra"]["fraccion_mediana_extremas"] = 0.8
    escala = _seccion(informe.redactar(otro), titulo)
    assert ("es 1,00 con la imagen a favor y 0,80 con la imagen en contra: **sin "
            "dependencia tendría que ser 1,00 en los dos lados, y no lo es.**") in escala
    assert "conserva toda su evidencia." not in escala.split("### Celda")[0].split("\n\n")[-2]


def test_la_expectativa_no_se_presenta_como_declarada_a_ciegas(texto):
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    assert "**Hipótesis declarada de antemano, a refutar celda a celda:**" in horquilla
    assert "medida sobre el conjunto durante el diseño y no declarada a ciegas" in horquilla
    assert "antes de correr nada" not in texto


def test_las_semillas_van_sin_separador_y_la_prevalencia_es_la_del_conjunto(
        texto, resultados_minimos):
    insumos = _seccion(texto, "Insumos y parámetros")
    assert "(semilla 20261009)" in insumos
    assert "clínica de la réplica b, 10000 + b; placas de la réplica b, 20000 + b." in insumos
    assert "20 261 009" not in texto and "10 000" not in texto
    assert "con la semilla 1 sobre todas las placas" in _seccion(
        texto, "Lectura de los resultados")
    assert "que cubre el redondeo de las RV publicadas" in insumos
    assert "redondeo máximo" not in texto
    otro = copy.deepcopy(resultados_minimos)
    otro["insumos"]["positivas"] = 1000
    otro["insumos"]["placas"] = 4000
    insumos = _seccion(informe.redactar(otro), "Insumos y parámetros")
    assert "(una por paciente; 1 000 positivas, prevalencia 0,2500)" in insumos
    # el previo es el del calibrador, y si no es la prevalencia del conjunto se dice
    assert ("Previo del análisis principal: 0,2215, el del calibrador, que **no es la "
            "prevalencia del conjunto** (0,2500). El previo desplegado, 0,1466,") in insumos
    assert ("Previo del análisis principal: 0,2215, el del calibrador, que es la "
            "prevalencia del conjunto. El previo desplegado, 0,1466,") in _seccion(
        texto, "Insumos y parámetros")
    assert "la prevalencia de la población simulada" not in texto
    sensibilidad = _seccion(texto, "Sensibilidad al previo")
    assert "usa como previo 0,2215 (el de «Insumos y parámetros»)" in sensibilidad
    assert "donde el análisis principal usa 0,2215 tiene un efecto analítico" in sensibilidad
    assert "previo correcto" not in texto
    assert "cifras que lo llevan (comparadas sin redondear)." in _seccion(
        texto, "Lectura de los resultados")
    assert "(estimaciones puntuales):" in _seccion(texto, "Lectura de los resultados")


def test_las_columnas_de_texto_van_a_la_izquierda(texto):
    assert informe._tabla(["celda", "n", "veredicto"], [["a", "1", "x"]],
                          texto=("veredicto",)) == [
        "| celda | n | veredicto |", "| :--- | ---: | :--- |", "| a | 1 | x |", ""]
    assert informe._tabla(["a", "b"], [])[1] == "| :--- | ---: |"
    guias = {l: texto.splitlines()[i + 1] for i, l in enumerate(texto.splitlines())
             if l.startswith("| ") and texto.splitlines()[i + 1].startswith("| :---")}
    assert guias["| celda | contención | umbral | veredicto |"].endswith("| :--- |")
    assert all(g.endswith("| :--- |") for c, g in guias.items() if c.endswith("| rótulo |"))
    assert all(g.endswith("| :--- |") for c, g in guias.items()
               if c.endswith("| en qué sentido |"))


def test_las_listas_de_celdas_no_llevan_doble_parentesis(texto, resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"][1:]:
        celda["destacada"] = True
    for documento in (texto, informe.redactar(otro)):
        assert "((" not in documento and "))" not in documento
    assert "las figuras que ya hubiera" not in texto
    assert "que pueden ser de una corrida anterior" in informe.redactar(
        resultados_minimos, {"contencion_rejilla": "f/contencion_rejilla.png"})
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


def _par(celda: dict, ruta: str):
    """El intervalo de esa ruta, o None si la celda no lo lleva o no son dos
    cifras."""
    par = (celda.get("intervalos") or {}).get(ruta)
    if not par or _falta(par[0]) or _falta(par[1]):
        return None
    return par


def _a_la_vista(x, decimales: int) -> float:
    """La cifra con los decimales con que se imprime. Las comparaciones de la
    prosa se hacen asi: el documento no afirma de una cifra lo que su forma
    impresa no deja ver (un extremo 1,004 se imprime «1,00» y no queda por
    encima de 1)."""
    return float(f"{float(x):.{decimales}f}")


def _umbral(x) -> str:
    """Un umbral, en porcentaje y con los decimales que tenga: «90», «90,5».
    Se imprime con la misma precision con que `_alcanza` lo compara."""
    return f"{_a_la_vista(100.0 * x, 1):g}".replace(".", ",")


def _alcanza(x, umbral) -> bool:
    """Si una fraccion alcanza un umbral que se cumple con la igualdad («≥»),
    con las dos cifras tal como se imprimen: en porcentaje y con un decimal."""
    return _a_la_vista(100.0 * x, 1) >= _a_la_vista(100.0 * umbral, 1)


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


def _tabla(cabeceras, filas, izquierdas: int = 1, texto=()) -> list:
    """Una tabla de Markdown: las primeras columnas y las de `texto` (por su
    cabecera) a la izquierda, las cifras a la derecha."""
    guia = [":---" if i < izquierdas or cabecera in texto else "---:"
            for i, cabecera in enumerate(cabeceras)]
    lineas = ["| " + " | ".join(cabeceras) + " |", "| " + " | ".join(guia) + " |"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return lineas + [""]


def _lista(nombres) -> str:
    """«a, b y c»."""
    nombres = list(nombres)
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _nombradas(celdas) -> str:
    """Cuantas celdas y cuales: «ninguna», «1, que es a», «3, que son a, b y c»."""
    nombres = [c["nombre"] for c in celdas]
    if not nombres:
        return "ninguna"
    return f"{len(nombres)}, que {'es' if len(nombres) == 1 else 'son'} {_lista(nombres)}"


def _con_su_cifra(celdas, ruta: str, decimales: int) -> str:
    """«: a, 0,87 (IC 95 %: 0,81 a 0,92); b, ...», o nada si no hay celdas."""
    if not celdas:
        return ""
    return ": " + "; ".join(f"{c['nombre']}, {_cifra(c, ruta, decimales)}" for c in celdas)


def _semilla(x) -> str:
    """Una semilla se copia y se pega: sin separador de millares."""
    return SIN_CIFRA if _falta(x) else str(int(x))


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
    if _a_la_vista(ece, 3) <= _a_la_vista(suelo["p95"], 3):
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


def _la_fila_0a_se_cumple(cero: dict) -> bool:
    """Colas exactamente 0 y contencion 100 %: la comprobacion de la metrica.
    Es exacta, no «tal como se imprime»: un solo caso fuera la incumple."""
    h = cero["horquilla"]["todos"]
    return h["bajo"] == 0 and h["sobre"] == 0 and h["contencion"] == 1


def _estado_de_0a(cero: dict) -> str:
    """`cumple`, `no_cumple` o `sin_casos`: sin casos con horquilla la
    comprobacion no se puede hacer, que no es lo mismo que fallarla."""
    h = cero["horquilla"]["todos"]
    if _falta(h["bajo"]) or _falta(h["sobre"]) or not h["n"]:
        return "sin_casos"
    return "cumple" if _la_fila_0a_se_cumple(cero) else "no_cumple"


def _la_fila_0a(cero: dict) -> str:
    """Lo que se dice debajo de la fila 0A. Si no se cumple se da la cuenta:
    la tabla puede imprimir «0,0 %» con un caso fuera."""
    estado = _estado_de_0a(cero)
    if estado == "sin_casos":
        return ("**No se puede comprobar: no hay casos concordantes con horquilla, y las "
                "tablas de la horquilla de este documento no se pueden leer.**")
    if estado == "cumple":
        return "Se cumple: la métrica de la horquilla pasa su comprobación en el caso nulo."
    h = cero["horquilla"]["todos"]
    fuera = round((h["bajo"] + h["sobre"]) * h["n"])
    return (f"**NO se cumple: {'queda' if fuera == 1 else 'quedan'} fuera de la horquilla "
            f"{entero(fuera)} de los {entero(h['n'])} concordantes. La métrica de la "
            f"horquilla o el generador tienen un defecto, y las tablas de la horquilla de "
            f"este documento no se pueden leer hasta corregirlo.**")


def _que_previo(insumos: dict) -> str:
    """El previo del analisis principal es el del calibrador: se dice si es,
    como tiene que ser, la prevalencia del conjunto."""
    del_conjunto = (insumos["positivas"] / insumos["placas"] if insumos["placas"] else None)
    if numero(del_conjunto, 4) == numero(insumos["prevalencia"], 4):
        return "el del calibrador, que es la prevalencia del conjunto"
    return (f"el del calibrador, que **no es la prevalencia del conjunto** "
            f"({numero(del_conjunto, 4)})")


def _pendiente_de_0a(cero: dict) -> str:
    """La pendiente de la independencia en 0A, con lo que dice su intervalo."""
    par = _par(cero, "modelos.independencia.pendiente")
    return (_cifra(cero, "modelos.independencia.pendiente", 2)
            + ("" if par is None else
               "; su intervalo contiene el 1"
               if _a_la_vista(par[0], 2) <= 1 <= _a_la_vista(par[1], 2)
               else "; su intervalo no contiene el 1"))


VEREDICTOS = {
    "se_sostiene": "se sostiene",
    "no_se_sostiene": "no se sostiene",
    "no_se_puede_decir": "no se puede decir: la estimación y su intervalo no quedan "
                         "enteros a un lado del umbral",
    "punto_si": "se sostiene (estimación puntual, sin intervalo)",
    "punto_no": "no se sostiene (estimación puntual, sin intervalo)",
    "sin_casos": "no se puede decir: no hay casos concordantes con horquilla",
}


def _veredicto(celda: dict) -> tuple:
    """(clave, texto) del veredicto de la hipotesis en una celda. Con
    intervalo decide el intervalo ENTERO, y tiene que quedar del mismo lado
    del umbral que la estimacion; sin el, solo esta la estimacion puntual, y
    el texto lo dice. Todo, con las cifras tal como se imprimen: una
    contencion que se imprime «90,0 %» alcanza un umbral del 90 %."""
    umbral = celda["hipotesis"]["umbral"]
    punto = celda["horquilla"]["todos"]["contencion"]
    if _falta(punto):
        clave = "sin_casos"
    else:
        par = _par(celda, "horquilla.todos.contencion")
        alcanza = _alcanza(punto, umbral)
        if par is None:
            clave = "punto_si" if alcanza else "punto_no"
        elif alcanza and _alcanza(par[0], umbral):
            clave = "se_sostiene"
        elif not alcanza and not _alcanza(par[1], umbral):
            clave = "no_se_sostiene"
        else:
            clave = "no_se_puede_decir"
    return clave, VEREDICTOS[clave]


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
        f"{numero(i['positivas'] / i['placas'] if i['placas'] else None, 4)}), nunca "
        f"usadas para entrenar ni calibrar, con su "
        f"etiqueta real de opacidad. Es un desenlace análogo al de Heckerling (infiltrado "
        f"radiográfico) en una población distinta: RSNA no es una cohorte con sospecha de "
        f"neumonía.",
        "- **Clínica:** a cada placa se le sortea la puntuación de Heckerling dada su "
        "etiqueta, con las frecuencias publicadas de la cohorte de derivación. No se "
        "inventa la exactitud de la regla: se usa la publicada, tal como la usa el sistema. "
        "Cada placa con su clínica sorteada es una viñeta.",
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
        f"- Previo del análisis principal: {numero(i['prevalencia'], 4)}, {_que_previo(i)}. "
        f"El previo desplegado, "
        f"{numero(p['previo_desplegado'], 4)}, solo entra en la sensibilidad al previo.",
        f"- Rejilla: ρ1 y ρ0 toman los valores {' / '.join(rho(x) for x in p['rejilla'])}: "
        f"{entero(len(r['celdas']))} celdas. El origen es 0A y se cuenta aparte; "
        + (f"celdas destacadas: {_lista(destacadas)}." if destacadas
           else "esta corrida no tiene celdas destacadas."),
        f"- Bootstrap: {replicas}.",
        f"- Semillas: clínica de la estimación puntual, {_semilla(p['semilla_puntual'])}; "
        f"clínica de la réplica b, {_semilla(p['semilla_clinica'])} + b; placas de la "
        f"réplica b, {_semilla(p['semilla_indices'])} + b.",
        f"- Tolerancia de las colas de la horquilla: ε = {numero(p['epsilon'], 3)} log-odds, "
        f"que cubre el redondeo de las RV publicadas (la misma tolerancia de la "
        f"comprobación 0A).",
        f"- ECE: {entero(p['bins'])} tramos de igual masa, con los empates rotos por el orden "
        f"del identificador de la placa. Su suelo de ruido: "
        f"{entero(p['repeticiones_suelo'])} juegos de etiquetas simuladas con las "
        f"probabilidades del propio modelo (semilla {_semilla(p['semilla_suelo'])}); se "
        f"publican la media y el percentil 95.",
        f"- Hipótesis de la horquilla: contención ≥ "
        f"{_umbral(p['hipotesis_contencion'])} % de los concordantes.",
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
        "Lo que 0A puede demostrar es que el sistema calcula lo que dice calcular; no que "
        "la posterior sea exacta en pacientes.",
        "",
    ]
    cero = _cero(r)
    if cero is None:
        return lineas + ["Esta corrida no incluye la celda 0A.", ""]
    n = cero["recuentos"]
    h = cero["horquilla"]["todos"]
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
        _la_fila_0a(cero),
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
    umbral = _umbral(p["hipotesis_contencion"])
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
        f"medida sobre el conjunto durante el diseño y no declarada a ciegas, era que solo "
        f"se sostuviera en 0A y en las celdas más suaves. Una contención baja es un "
        f"resultado igual de publicable, y obliga a repensar la cota, no a ocultarla.",
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
               "El veredicto, celda a celda, sobre todos los concordantes. Donde hay "
               "intervalo decide el intervalo entero: si la estimación y su intervalo no "
               "quedan enteros a un lado del umbral, no se puede decir. Donde no lo hay "
               "solo está la estimación puntual, y el veredicto lo dice. Se decide con la "
               f"contención tal como se imprime (un «{porcentaje(p['hipotesis_contencion'])}» "
               f"alcanza un umbral del {umbral} %); el campo `se_sostiene` del fichero de "
               "resultados se calcula sin redondear:", ""]
    lineas += _tabla(
        ["celda", "contención", "umbral", "veredicto"],
        [[c["nombre"], _fraccion(c, "horquilla.todos.contencion"),
          f"≥ {_umbral(c['hipotesis']['umbral'])} %", _veredicto(c)[1]]
         for c in r["celdas"]], texto=("veredicto",))
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
        fracciones = [cero["escala_legible"][lado]["fraccion_mediana_extremas"]
                      for lado, _ in LADOS_DE_LA_IMAGEN]
        entera = all(numero(f, 2) == numero(1.0, 2) for f in fracciones)
        lineas += ["En 0A la fracción mediana de las puntuaciones extremas (k ≤ 1 y k ≥ 4) es "
                   + _lista([f"{numero(f, 2)} {nombre}"
                             for f, (_, nombre) in zip(fracciones, LADOS_DE_LA_IMAGEN)])
                   + (": sin dependencia la puntuación conserva toda su evidencia." if entera
                      else f": **sin dependencia tendría que ser {numero(1.0, 2)} en los dos "
                           f"lados, y no lo es.**"), ""]
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
                 for f in e["por_puntuacion"]], texto=("rótulo",))
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
        f"El análisis principal usa como previo {principal} (el de «Insumos y parámetros»); "
        f"el sistema desplegado arranca con {previo}. Declarar {previo} donde el análisis "
        f"principal usa {principal} tiene un efecto analítico: todas las odds posteriores se multiplican "
        f"por {numero(math.exp(d), 3)}, es decir, se desplazan {numero(d, 2, signo=True)} en "
        f"log-odds por igual. El intercepto de calibración debe moverse, por tanto, en "
        f"torno a {numero(-d, 2, signo=True)} respecto del principal.",
        "",
        "**El AUC no cambia** (un desplazamiento común no altera el orden de los casos) y "
        "no se reporta en esta tabla. **Esto no recomienda configurar el despliegue con "
        f"{principal}:** es el previo de un conjunto de datos de un reto, no la prevalencia "
        "de ningún servicio.",
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
                      "en qué sentido"], filas, izquierdas=2, texto=("en qué sentido",))
    lineas += ["La categoría que el sistema imprime (todos los casos, también los del asma "
               "desconocida):", ""]
    lineas += _tabla(
        ["celda", "cambian de categoría", "en qué sentido"],
        [[c["nombre"],
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['cambian'])} de "
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['casos'])}",
          _transiciones(c["sensibilidad_al_previo"]["categoria_del_sistema"])]
         for c in celdas], texto=("en qué sentido",))
    return lineas


def _optimismo(r: dict) -> list:
    lineas = ["## 0C: optimismo de la derivación (cálculo, no experimento)", ""]
    cero = _cero(r)
    if cero is None or "optimismo_de_la_derivacion" not in cero:
        return lineas + ["Esta corrida no calculó 0C.", ""]
    o = cero["optimismo_de_la_derivacion"]
    mas, menos, iguales = [], [], []
    for f in o["por_puntuacion"]:
        derivacion = abs(math.log(f["rv_derivacion"]))
        validacion = abs(math.log(f["rv_validacion"]))
        (mas if derivacion > validacion else menos if derivacion < validacion
         else iguales).append(str(f["k"]))
    reparto = []
    if mas:
        reparto.append(f"más extrema que la de validación en k = {_lista(mas)}")
    if menos:
        reparto.append(f"menos extrema en k = {_lista(menos)}")
    if iguales:
        reparto.append(f"igual de extrema en k = {_lista(iguales)}")
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
        + (" El «optimismo» de la derivación no es uniforme."
           if mas and (menos or iguales) else ""),
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
        return "no hay casos con horquilla"
    if bajo == 0 and sobre == 0:
        return f"{dentro}; ninguna cola tiene casos"
    # cual es la mayor, con las dos tal como se imprimen
    if _a_la_vista(100.0 * bajo, 1) == _a_la_vista(100.0 * sobre, 1):
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
    """(cuantas cifras con intervalo quedan fuera de el, cuantas hay). Se
    compara SIN redondear: casi ninguno de esos intervalos se imprime, y la
    frase lo dice."""
    fuera = total = 0
    for celda in celdas:
        for ruta, par in (celda.get("intervalos") or {}).items():
            valor = _valor(celda, ruta)
            if _falta(valor) or _falta(par[0]) or _falta(par[1]):
                continue
            total += 1
            fuera += valor < par[0] - 1e-9 or valor > par[1] + 1e-9
    return fuera, total


def _del_lado(celdas, clave: str, debajo: bool) -> tuple:
    """Las celdas cuya pendiente de `clave` queda por debajo (o por encima) de
    1, las que de ellas llevan intervalo, y las que lo tienen ENTERO de ese
    lado."""
    ruta = f"modelos.{clave}.pendiente"

    def de_ese_lado(v) -> bool:
        return _a_la_vista(v, 2) < 1 if debajo else _a_la_vista(v, 2) > 1

    puntuales = [c for c in celdas if not _falta(c["modelos"][clave]["pendiente"])
                 and de_ese_lado(c["modelos"][clave]["pendiente"])]
    con_intervalo = [c for c in puntuales if _par(c, ruta) is not None]
    enteras = [c for c in con_intervalo if de_ese_lado(_par(c, ruta)[1 if debajo else 0])]
    return puntuales, con_intervalo, enteras


def _lectura_de_la_pendiente(celdas, clave: str, debajo: bool, esperada: str,
                             contraria: str, quiere_decir: dict) -> list:
    """Las frases de la pendiente de un modelo: primero el lado esperado y
    despues, si alguna celda cae en el, el contrario. La estimacion sola no
    decide: lo que la pendiente `quiere_decir` (por debajo de 1, True; por
    encima, False) se dice solo de las celdas con el intervalo ENTERO de ese
    lado."""
    ruta = f"modelos.{clave}.pendiente"
    lineas = []
    for lado, frase in ((debajo, esperada), (not debajo, contraria)):
        puntuales, con_intervalo, enteras = _del_lado(celdas, clave, lado)
        if lado != debajo and not puntuales:
            continue
        lineas.append(f"- {frase}: {len(puntuales)} de {len(celdas)}"
                      + _con_su_cifra(puntuales, ruta, 2) + ".")
        if con_intervalo:
            lineas.append(
                f"- De esas, con el intervalo entero por {'debajo' if lado else 'encima'} "
                f"de 1 ({quiere_decir[lado]}): {len(enteras)} de {len(con_intervalo)}"
                + (": " + _lista(c["nombre"] for c in enteras) if enteras else "") + ".")
    return lineas


def _lectura_de_las_pareadas(celdas) -> list:
    """Por combinacion y por metrica: en cuantas celdas el intervalo de la
    diferencia frente a la imagen sola queda entero del lado de la mejora,
    entero del contrario, o cruza el 0."""
    lineas = []
    for clave, nombre in COMBINADOS:
        for metrica, titulo, sube in (("auc", "ΔAUC", True), ("brier", "ΔBrier", False)):
            ruta = f"pareadas.{clave}.{metrica}"
            con_intervalo = [c for c in celdas if _par(c, ruta) is not None]
            if not con_intervalo:
                continue
            encima = [c for c in con_intervalo if _a_la_vista(_par(c, ruta)[0], 3) > 0]
            debajo = [c for c in con_intervalo if _a_la_vista(_par(c, ruta)[1], 3) < 0]
            cruzan = [c for c in con_intervalo if c not in encima and c not in debajo]
            mejoran, empeoran = (encima, debajo) if sube else (debajo, encima)
            lineas.append(
                f"- **Frente a la imagen sola: {titulo}, {nombre}.** Celdas destacadas con "
                f"intervalo: {len(con_intervalo)}. Con el intervalo entero del lado de la "
                f"mejora (por {'encima' if sube else 'debajo'} de 0): "
                f"{_nombradas(mejoran)}. Con el intervalo entero del lado contrario: "
                f"{_nombradas(empeoran)}. Con el 0 dentro del intervalo: "
                f"{_nombradas(cruzan)}.")
    return lineas


def _lectura_de_la_hipotesis(r: dict) -> str:
    """0A aparte. En las demas, las que llevan intervalo se leen por el; en
    las que no, se dice que solo hay estimacion puntual."""
    umbral = _umbral(r["parametros"]["hipotesis_contencion"])
    resto = [c for c in r["celdas"] if c["nombre"] != "0A"]
    clases = {clave: [] for clave in VEREDICTOS}
    for c in resto:
        clases[_veredicto(c)[0]].append(c)
    con_intervalo = clases["se_sostiene"] + clases["no_se_sostiene"] + clases["no_se_puede_decir"]
    sin_intervalo = clases["punto_si"] + clases["punto_no"]
    frases = [f"- **La hipótesis de la horquilla** (contención ≥ {umbral} % de los "
              f"concordantes)."]
    if _cero(r) is not None:
        frases.append("0A es la comprobación de la métrica y se cuenta aparte.")
    frases.append(f"Celdas con dependencia: {entero(len(resto))}; con intervalo, "
                  f"{entero(len(con_intervalo))}.")
    if con_intervalo:
        frases += [
            "Donde hay intervalo decide el intervalo entero.",
            f"Con intervalo, celdas en las que se sostiene: "
            f"{_nombradas(clases['se_sostiene'])}.",
            f"Con intervalo, celdas en las que no se sostiene: "
            f"{_nombradas(clases['no_se_sostiene'])}.",
            f"Con intervalo, celdas en las que no se puede decir, porque la estimación y su "
            f"intervalo no quedan enteros a un lado del umbral: "
            f"{_nombradas(clases['no_se_puede_decir'])}."]
    if sin_intervalo:
        frases.append(
            f"Sin intervalo, {entero(len(sin_intervalo))}: solo hay estimación puntual. "
            f"Sin intervalo, celdas en las que la estimación alcanza el umbral: "
            f"{_nombradas(clases['punto_si'])}.")
    if clases["sin_casos"]:
        frases.append(f"Celdas sin casos concordantes con horquilla: "
                      f"{_nombradas(clases['sin_casos'])}.")
    return " ".join(frases)


def _lectura(r: dict) -> list:
    lineas = [
        "## Lectura de los resultados",
        "",
        "Estas frases se componen contando sobre las cifras de las tablas: dicen lo que las "
        "cifras dicen, y nada más. Todo se refiere a la simulación. Las comparaciones con "
        "un umbral o con un valor de referencia se hacen con las cifras tal como se "
        "imprimen: «por encima» y «por debajo» son estrictos, y un umbral «≥» se alcanza "
        "también con la igualdad.",
        "",
    ]
    destacadas = _destacadas(r)
    cero = _cero(r)
    if cero is not None:
        lineas.append(
            f"- **0A.** La pendiente de la combinación por independencia es "
            f"{_pendiente_de_0a(cero)}. Horquilla: "
            f"{_colas(cero['horquilla']['todos'])}.")
    if not destacadas:
        lineas.append("- Esta corrida no tiene celdas destacadas.")
    else:
        independencia = _lectura_de_la_pendiente(
            destacadas, "independencia", True,
            "**La independencia.** Celdas destacadas en las que la estimación de la "
            "pendiente de la combinación por independencia es menor que 1",
            "En sentido contrario, la estimación de la pendiente de la combinación por "
            "independencia es mayor que 1",
            {True: "exagera", False: "se queda corta"})
        independencia[0] += " Una pendiente menor que 1 es la forma cuantitativa de «exagera»."
        lineas += independencia
        lineas += _lectura_de_la_pendiente(
            destacadas, "conservador", False,
            "**El extremo conservador.** Celdas destacadas en las que la estimación de su "
            "pendiente es mayor que 1",
            "En sentido contrario, la estimación de la pendiente del extremo conservador es "
            "menor que 1",
            {True: "también el extremo conservador exagera", False: "se queda corto"})
        lineas += _lectura_de_las_pareadas(destacadas)
    lineas.append(_lectura_de_la_hipotesis(r))
    fuera, cifras = _fuera_de_su_intervalo(r["celdas"])
    if cifras:
        lineas.append(
            f"- **Los intervalos.** La estimación puntual usa la clínica sorteada con la "
            f"semilla {_semilla(r['parametros']['semilla_puntual'])} sobre todas las placas; "
            f"cada réplica remuestrea las placas y sortea otra clínica. El intervalo son los "
            f"percentiles de las réplicas y no está centrado en la estimación puntual: en "
            f"esta corrida, de {entero(r['parametros']['replicas'])} réplicas, quedan fuera "
            f"de su intervalo {entero(fuera)} de las {entero(cifras)} cifras que lo "
            f"llevan (comparadas sin redondear).")
    if destacadas:
        lineas += ["", "Hacia qué lado cae el oráculo, por eje y por lado de la imagen "
                       "(estimaciones puntuales):", ""]
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
    cero = _cero(r)
    if cero is None:
        corrida = ("Esta corrida no incluye la celda 0A: de los dos primeros puntos no dice "
                   "nada.")
    else:
        m = cero["modelos"]["independencia"]
        estado = {"cumple": "se cumple", "no_cumple": "**no se cumple**",
                  "sin_casos": "**no se puede comprobar**"}[_estado_de_0a(cero)]
        corrida = (
            f"En esta corrida, la fila 0A de la horquilla {estado}; la "
            f"pendiente de la combinación por independencia en 0A es "
            f"{_pendiente_de_0a(cero)}; y su ECE ({numero(m['ece'], 3)}) "
            f"{_frente_al_suelo(m['ece'], m['suelo'])}.")
    return [
        "## Lo que esta simulación puede afirmar y lo que no",
        "",
        "**Puede decir:**",
        "",
        f"- si el sistema reproduce caso a caso la posterior del generador (0A: lo "
        f"comprueban las pruebas de `{PRUEBA_0A}`; la fila 0A de la horquilla lo acompaña, "
        f"como control más débil y solo para los concordantes);",
        "- si, **cuando** la puntuación tiene la exactitud publicada y es condicionalmente "
        "independiente de la imagen, la aritmética y la calibración de la imagen dan una "
        "posterior calibrada en el conjunto de prueba de RSNA;",
        "- cuánto se desvía la independencia de la posterior del generador **bajo cada "
        "supuesto de dependencia**, en qué dirección, y dónde cae el oráculo respecto a la "
        "horquilla;",
        "- cuánto desplaza la calibración un previo equivocado.",
        "",
        corrida + " Lo demás se lee en «Lectura de los resultados» y, lo del previo, en "
                  "«Sensibilidad al previo».",
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
               "hubiera en la carpeta, que pueden ser de una corrida anterior.", ""]
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

Esperado: `38 passed` (casi todo el tiempo es la fixture `resultados_minimos`, que calcula la rejilla mínima).

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

Esperado: `3 failed, 23 passed`:

```
E       AttributeError: module 'validar_combinacion' has no attribute 'escribir_analisis'
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\test_main_escribe_el_analisis_0\\docs\\analisis.md'
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\test_solo_documento_escribe_el0\\analisis.md'
FAILED tests/test_validar_combinacion.py::test_escribir_analisis_enlaza_las_figuras_con_rutas_relativas
FAILED tests/test_validar_combinacion.py::test_main_escribe_el_analisis_leyendo_el_json
FAILED tests/test_validar_combinacion.py::test_solo_documento_escribe_el_documento_sin_recalcular
3 failed, 23 passed
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

Esperado: `26 passed`. Después comprueba que ninguna prueba ha escrito en el repo:

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
`análisis: …validacion-semisintetica-sp5.md`. El documento tiene cerca de 570 líneas y este índice:

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
  métrica de la horquilla pasa su comprobación en el caso nulo»;
- «Dependencia»: la tabla de correlaciones da 0,000 en 0A (no «−0,000») y ≈ 0,275 / 0,286 con ρ = 0,3;
- «La horquilla»: la tabla del veredicto tiene 25 filas y solo llevan intervalo 0A y las seis
  destacadas; las 18 que no lo llevan acaban en «(estimación puntual, sin intervalo)», y entre
  ellas se sostiene (0,15; 0,15);
- «Lectura de los resultados»: cada frase se puede comprobar contra su tabla (p. ej. «menor que 1:
  6 de 6» contra la columna de la pendiente, y cada «De esas, con el intervalo entero…» contra los
  intervalos impresos en la frase anterior); la hipótesis cuenta 24 celdas con dependencia y 6 con
  intervalo, con 0A aparte, cada cuenta dice si es de las celdas con intervalo o sin él, y
  ninguna frase dice «en ninguna»; «exagera» y «se queda corto» se
  dicen solo de los intervalos enteros; los ejes salen en el orden simétrica, solo con neumonía,
  solo sin neumonía;
- «Lo que esta simulación puede afirmar y lo que no»: dice el alcance («Puede decir: si…») y,
  aparte, lo que dice esta corrida de 0A;
- «Figuras»: diez enlaces, todos `validacion-semisintetica/<nombre>.png`, sin ninguna barra invertida
  ni ruta absoluta;
- en todo el documento: ningún `nan`, `None`, llave, doble paréntesis ni punto decimal.

Con 20 réplicas algunos intervalos no contienen su estimación puntual (la «Lectura» dice cuántos: 13
de 357); no es un fallo del documento, que imprime lo que hay en el JSON.

No copies nada de `<CARPETA_TEMPORAL>` al repo.

- [ ] **Paso 11: Commit**

```bash
git add src/copiloto_triaje/validacion/informe.py scripts/validar_combinacion.py tests/test_informe.py tests/test_validar_combinacion.py
git commit -m "feat(validacion): el documento de analisis, generado desde el JSON (SP5-B1 T6)" -m "informe.redactar compone el Markdown leyendo resultados_simulacion.json: ninguna cifra se teclea, las frases de la lectura se cuentan sobre las tablas y deciden sobre el intervalo, con las cifras tal como se imprimen y la cuenta como predicado. El script lo escribe con las figuras que haya, tambien con --solo-documento. Las pruebas de main() desvian el analisis a una carpeta temporal." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
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

La última línea sale del campo `se_sostiene` del JSON, que se calcula sobre la
estimación puntual y sin redondear. El documento no lee ese campo: decide con
el intervalo donde lo hay, con las cifras tal como se imprimen, y lo dice.

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
simulación puede afirmar y lo que no» tiene que estar. En la «Lectura de los
resultados», la frase de la hipótesis tiene que decir: 24 celdas con
dependencia, 6 con intervalo; con intervalo, no se sostiene en las 6; sin
intervalo, la estimación alcanza el umbral en 1, que es (0,15; 0,15).

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
git commit -m "feat(validacion): la simulación semisintética, publicada: resultados, figuras y análisis" -m "La rejilla de 25 celdas con 1 000 réplicas de bootstrap en 0A y en las seis destacadas. La fila 0A sale con colas 0 y contención 100 %. La hipótesis del 90 % no se sostiene en ninguna de las seis celdas destacadas, que son las que llevan intervalo; de las 18 sin intervalo, la estimación solo alcanza el umbral en (0,15; 0,15). El análisis se genera desde el JSON, sin teclear ninguna cifra, y una prueba vigila que lo versionado corresponde a los insumos y al código." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Tarea 8: La latencia de extremo a extremo

Spec de SP5 §6.3. La latencia NO es simulación: es una medición del sistema
desplegado con casos de prueba. Lo que se mide (`ms_extremo`) es una cota
inferior de la latencia de extremo a extremo, y el JSON lo dice. Esta tarea no habla con ningún sistema: deja
el instrumento (el arnés escribe `latencias.json`; un script lo resume en
`latencia.json`) y lo prueba con filas fabricadas. La corrida real con bots
la hace después una persona, con el túnel y los secretos.

**Ficheros:**
- Crear: `scripts/medir_latencia.py`
- Crear: `tests/test_medir_latencia.py`
- Modificar: `pruebas/reproducir_casos.py` (dos funciones nuevas entre `escribir_corpus` y el resumen; una llamada en `main()`; y dos rótulos que llamaban «de extremo a extremo» a `ms_extremo`)
- Modificar: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md` (las dos filas de la latencia, §6.2 y §6.3)
- Modificar: `docs/sp5-sesion.md` (sección nueva «6. Medir la latencia» y el párrafo de lo que se versiona)
- Modificar: `docs/validacion-semisintetica/README.md` (sección nueva `latencia.json`, al final)
- Prueba: `tests/test_reproducir_casos.py` (cuatro pruebas nuevas, al final), `tests/test_medir_latencia.py` (17)

**Interfaces:**
- Consume: de `pruebas/reproducir_casos.py`, las filas `(caso, obs, redaccion)` que `main()` ya construye y pasa a `escribir_corpus(destino, filas)` y a `resumen(...)`:
  `caso["patientId"]`, `caso["perfil"].carpeta`; de LA CONSULTA de los bots, `obs["con_bots"]`, `obs.get("fallo")`, `obs.get("error")`, `obs.get("coincide")`, `obs.get("ms_extremo")` y `obs.get("resultado")` (los de la tabla `consultas`; solo con bots); `obs.get("ms_arnes")`;
  de la llamada propia del arnés, `redaccion["error"]` y, sin bots, `redaccion["resultado"]["milisegundos"]`. `numpy` y `statistics` en el script. Nada de `src/`.
- Produce, en `pruebas/reproducir_casos.py`:
  - `LATENCIAS = "latencias.json"`, `RECHAZOS_PREVISTOS` (las carpetas de los perfiles 05 a 09)
  - `filas_de_latencia(filas) -> list[dict]`: una fila por caso, con las claves, en este orden, `patientId`, `perfil`, `rechazo_previsto`, `con_bots`, `fallo`, `error_consulta`, `coincide`, `ms_extremo`, `ms_modelo`, `error_arnes`, `ms_arnes`. El error que decide si la medida cuenta es el de la consulta medida (`error_consulta`), no el de la llamada del arnés.
  - `escribir_latencias(destino, filas) -> pathlib.Path`: escribe `<destino>/latencias.json` (una lista JSON con esas filas) y devuelve la ruta.
  - `main()` llama a `escribir_latencias(destino, filas)` SIEMPRE, justo después de `escribir_corpus(destino, filas)`.
- Produce, en `scripts/medir_latencia.py`:
  - constantes `TITULO`, `TRAMO`, `MINIMO = 30`, `UMBRALES_S = {"minimo": 8, "objetivo": 3}`, `NO_MEDIDO = "no medido"`, `A_MANO_N = 5`, `MOTIVOS = ("sin_bots", "rechazo_previsto", "fallo", "error", "no_coincide", "sin_ms_extremo")`, `CLAVES` (las de una fila), `LECTURA`, `PERCENTIL`, `A_MANO`, `CARPETA`, `NOMBRE = "latencia.json"`.
  - `_es_una_medida(v) -> bool` (milisegundos: número finito y no negativo; ni cadena ni booleano).
  - `resumir(filas, minimo=MINIMO, manual=None) -> dict` con las claves, en este orden, `titulo`, `tramo`, `lectura`, `n`, `percentil`, `p50_ms`, `p95_ms`, `minimo_ms`, `maximo_ms`, `ms_extremo_ordenados`, `modelo_p50_ms`, `umbrales_s`, `frente_a_umbrales` (`{"p50": {"cumple_minimo": bool, "cumple_objetivo": bool}, "p95": {...}}`), `tramo_manual` (`{"valores_s": [...], "n": int, "mediana_s": float}` o `"no medido"`), `descartadas` (`{"total", "sin_bots", "fallo", "error", "sin_ms_extremo"}`). Con menos de `minimo` consultas válidas, `SystemExit`.
  - `leer_manual(texto) -> list[float] | None`: los CINCO tiempos de `--manual`; `SystemExit` si no son cinco números positivos separados por comas (con decimales con coma saldrían diez).
  - `leer_corrida(ruta) -> list`: las filas de un `latencias.json`, comprobadas; `SystemExit` si no existe, no es un JSON, no es una lista o una fila no lleva las claves `CLAVES`.
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
CLAVES_DE_LATENCIA = ["patientId", "perfil", "rechazo_previsto", "con_bots", "fallo",
                      "error_consulta", "coincide", "ms_extremo", "ms_modelo",
                      "error_arnes", "ms_arnes"]


def test_filas_de_latencia_da_una_fila_por_caso_con_lo_que_se_midio():
    from pruebas.reproducir_casos import RECHAZOS_PREVISTOS, filas_de_latencia
    bien = {"texto": "x", "texto_paciente": "", "error": None,
            "resultado": UN_RESULTADO}
    rechazo = {"texto": "NO PROCEDE", "texto_paciente": "",
               "error": "fuera_de_alcance: eso", "resultado": None}
    filas = [
        (_caso(pid="p-1"),
         {"con_bots": True, "ms_extremo": 1840, "ms_arnes": 61.5, "coincide": "sí",
          "error": None, "resultado": dict(UN_RESULTADO, milisegundos=150.0)},
         bien),
        (_caso(perfil=PERFILES[4], pid="p-2"),
         {"con_bots": True, "ms_extremo": 410, "ms_arnes": 12.0, "coincide": "sí",
          "error": "fuera_de_alcance: lo que guardo el bot", "resultado": None},
         rechazo),
        (_caso(pid="p-3"),
         {"con_bots": True, "fallo": "no se pudo subir la placa",
          "ms_arnes": 60.0}, bien),
        (_caso(pid="p-4"), {"con_bots": False, "ms_arnes": 58.25}, bien),
        # El flujo agoto su tiempo limite; la llamada propia del arnes,
        # segundos despues, salio limpia.
        (_caso(pid="p-5"),
         {"con_bots": True, "ms_extremo": 30450, "ms_arnes": 61.0,
          "coincide": "NO: uno dio resultado y el otro no",
          "error": "copiloto_no_responde: tiempo agotado", "resultado": None},
         bien),
    ]
    salida = filas_de_latencia(filas)
    assert [list(f) for f in salida] == [CLAVES_DE_LATENCIA] * 5
    assert salida[0] == {
        "patientId": "p-1", "perfil": "03-banda_contradictoria",
        "rechazo_previsto": False, "con_bots": True, "fallo": None,
        "error_consulta": None, "coincide": "sí", "ms_extremo": 1840,
        # lo que tardo el modelo EN LA CONSULTA MEDIDA, no en la llamada del
        # arnes (que dijo 37,4)
        "ms_modelo": 150.0, "error_arnes": None, "ms_arnes": 61.5}
    # El error que decide es el de la consulta que se midio: el que guardo el
    # bot. El de la redaccion del arnes va aparte.
    assert salida[1]["perfil"] == "05-menor_edad"
    assert salida[1]["rechazo_previsto"] is True
    assert salida[1]["error_consulta"] == "fuera_de_alcance: lo que guardo el bot"
    assert salida[1]["error_arnes"] == "fuera_de_alcance: eso"
    assert salida[1]["ms_modelo"] is None and salida[1]["ms_extremo"] == 410
    assert salida[2]["fallo"] == "no se pudo subir la placa"
    assert salida[2]["ms_extremo"] is None and salida[2]["coincide"] is None
    assert salida[2]["error_consulta"] is None and salida[2]["ms_modelo"] is None
    # Sin bots no hay consulta: ni su error ni su medida; el modelo, el del arnes.
    assert salida[3]["con_bots"] is False and salida[3]["ms_extremo"] is None
    assert salida[3]["error_consulta"] is None and salida[3]["ms_modelo"] == 37.4
    assert salida[3]["ms_arnes"] == 58.25
    assert salida[4]["error_consulta"] == "copiloto_no_responde: tiempo agotado"
    assert salida[4]["error_arnes"] is None and salida[4]["ms_modelo"] is None
    assert salida[4]["ms_extremo"] == 30450
    assert salida[4]["coincide"] == "NO: uno dio resultado y el otro no"
    assert RECHAZOS_PREVISTOS == tuple(p.carpeta for p in PERFILES[4:])
    assert RECHAZOS_PREVISTOS[0] == "05-menor_edad" and len(RECHAZOS_PREVISTOS) == 5
    # un `resultado` que no es un diccionario (una fila rara de `consultas`) no
    # tiene milisegundos que dar, y no revienta
    rara = filas_de_latencia([(_caso(pid="p-6"),
                               {"con_bots": True, "resultado": "no es un diccionario"},
                               bien)])[0]
    assert rara["ms_modelo"] is None and rara["ms_extremo"] is None
    # los casos de la sesion (`--casos`) no son de ningun perfil de rechazo
    from pruebas.reproducir_casos import PERFIL_SESION
    sesion = filas_de_latencia([(_caso(perfil=PERFIL_SESION, pid="p-7"),
                                 {"con_bots": False}, bien)])[0]
    assert sesion["perfil"] == "00-sesion" and sesion["rechazo_previsto"] is False
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
    assert all(f["error_consulta"] is None and f["coincide"] is None for f in filas)
    assert all(isinstance(f["ms_arnes"], float) for f in filas)
    assert filas[0]["ms_modelo"] == 37.4
    assert filas[1]["error_arnes"].startswith("fuera_de_alcance")
    assert [f["rechazo_previsto"] for f in filas] == [False, True]
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
# Los perfiles cuyo desenlace ESPERADO es un rechazo (05 a 09): al medir la
# latencia se cuentan aparte de los errores que nadie esperaba.
RECHAZOS_PREVISTOS = tuple(p.carpeta for p in PERFILES if p.orden >= 5)


def filas_de_latencia(filas):
    """Una fila por caso con lo que esta corrida midio, lista para JSON.

    `ms_extremo` es el de `consultas` y solo existe con bots: lo escribe el
    flujo, desde que `Normalizar update` recibe el update con la placa hasta
    que `Desenlace` compone la respuesta. Todo lo que dice si esa medida
    cuenta es de LA MISMA consulta: `error_consulta` es el error que el flujo
    guardo en esa fila de `consultas` (un `copiloto_no_responde` o una
    `descarga_fallida` solo nacen alli), `coincide` dice si esa consulta y la
    lectura de este arnes cuentan lo mismo, y `ms_modelo` es lo que el
    servidor dijo que tardo el modelo EN ESA consulta.

    `error_arnes` y `ms_arnes` son de la otra llamada, la que este arnes hace
    por su cuenta al copiloto para redactar: no pasa por Telegram ni por n8n
    y no dice nada de la latencia de extremo a extremo. Sin bots no hay
    consulta, y `ms_modelo` es entonces el de la llamada del arnes.

    Aqui no se filtra ni se resume nada: que filas cuentan lo decide quien
    mide.
    """
    salida = []
    for caso, obs, redaccion in filas:
        con_bots = bool(obs.get("con_bots"))
        resultado = obs.get("resultado") if con_bots else redaccion.get("resultado")
        if not isinstance(resultado, dict):
            resultado = {}
        salida.append({
            "patientId": caso["patientId"],
            "perfil": caso["perfil"].carpeta,
            "rechazo_previsto": caso["perfil"].carpeta in RECHAZOS_PREVISTOS,
            "con_bots": con_bots,
            "fallo": obs.get("fallo"),
            "error_consulta": obs.get("error") if con_bots else None,
            "coincide": obs.get("coincide"),
            "ms_extremo": obs.get("ms_extremo"),
            "ms_modelo": resultado.get("milisegundos"),
            "error_arnes": redaccion.get("error"),
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

Tercero, los dos rótulos que llamaban «de extremo a extremo» a `ms_extremo`: es
el tramo que ve el flujo, y en el resumen entran además todas las filas,
rechazos incluidos. Busca:

```python
            _punto("de extremo a extremo",
                   f"{obs['ms_extremo']} ms" if obs.get("ms_extremo") is not None
```

y sustitúyelo por:

```python
            _punto("ms_extremo (de n8n a la respuesta)",
                   f"{obs['ms_extremo']} ms" if obs.get("ms_extremo") is not None
```

Y busca:

```python
        lineas.append(_punto("  de extremo a extremo (mediana)",
                             f"{extremo:.0f} ms" if extremo is not None
                             else "(no se registró)"))
```

y sustitúyelo por:

```python
        # Todas las filas, rechazos incluidos, y solo el tramo que ve el
        # flujo: NO es la latencia de extremo a extremo. La medida, con sus
        # descartes, la da scripts/medir_latencia.py.
        lineas.append(_punto("  ms_extremo, todas las filas (mediana)",
                             f"{extremo:.0f} ms" if extremo is not None
                             else "(no se registró)"))
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

Primero, la prueba que va de punta a punta (las filas del arnés, tal como las
lee el script). En `tests/test_reproducir_casos.py`, busca:

```python
    assert json.loads(json.dumps(salida)) == salida
    assert filas_de_latencia([]) == []


def test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida(tmp_path):
```

y sustitúyelo por:

```python
    assert json.loads(json.dumps(salida)) == salida
    assert filas_de_latencia([]) == []


def test_un_error_del_flujo_no_entra_en_la_medida_aunque_el_arnes_salga_limpio():
    """De punta a punta: las filas del arnes, tal como las lee el script que
    mide. Un `copiloto_no_responde` de 30 s no puede arrastrar el p95."""
    import importlib.util
    import pathlib

    from pruebas.reproducir_casos import _coincide, filas_de_latencia
    ruta = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "medir_latencia.py"
    spec = importlib.util.spec_from_file_location("medir_latencia", ruta)
    medir = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(medir)
    bien = {"texto": "x", "texto_paciente": "", "error": None, "resultado": UN_RESULTADO}
    rechazo = {"texto": "NO PROCEDE", "texto_paciente": "",
               "error": "fuera_de_alcance: eso", "resultado": None}
    sin_arnes = {"texto": "x", "texto_paciente": "",
                 "error": "copiloto_no_responde: el arnes no pudo", "resultado": None}
    filas = [(_caso(pid=f"p-{i}"),
              {"con_bots": True, "ms_extremo": 1000 + 100 * i, "ms_arnes": 60.0,
               "error": None, "resultado": UN_RESULTADO}, bien)
             for i in range(30)]
    filas.append((_caso(pid="p-lenta"),
                  {"con_bots": True, "ms_extremo": 30450, "ms_arnes": 61.0,
                   "error": "copiloto_no_responde: tiempo agotado", "resultado": None},
                  bien))
    filas.append((_caso(perfil=PERFILES[4], pid="p-menor"),
                  {"con_bots": True, "ms_extremo": 410, "ms_arnes": 12.0,
                   "error": "fuera_de_alcance: eso", "resultado": None}, rechazo))
    # la consulta salio bien y lo que fallo fue la llamada del arnes: no hay
    # con que confirmarla, y se descarta diciendo por que
    filas.append((_caso(pid="p-sin-confirmar"),
                  {"con_bots": True, "ms_extremo": 2000, "ms_arnes": 30000.0,
                   "error": None, "resultado": UN_RESULTADO}, sin_arnes))
    # `coincide` lo pone el arnes, como en `main()`: no se escribe a mano
    for caso, obs, redaccion in filas:
        obs["coincide"] = _coincide(obs, caso, redaccion)
    assert [obs["coincide"] for _, obs, _ in filas[:30]] == ["sí"] * 30
    assert [obs["coincide"] for _, obs, _ in filas[30:]] == [
        "NO: uno dio resultado y el otro no", "sí", "NO: uno dio resultado y el otro no"]
    medido = medir.resumir(json.loads(json.dumps(filas_de_latencia(filas))))
    assert medido["n"] == 30 and medido["maximo_ms"] == 3900.0
    assert medido["descartadas"]["error"] == 1
    assert medido["descartadas"]["rechazo_previsto"] == 1
    assert medido["descartadas"]["no_coincide"] == 1
    assert medido["descartadas"]["total"] == 3


def test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida(tmp_path):
```

Después, `tests/test_medir_latencia.py` (fichero nuevo):

```python
# -*- coding: utf-8 -*-
"""La latencia del sistema desplegado (spec de SP5 §6.3), con filas fabricadas.

No hay sistema desplegado al que hablar desde una prueba: las filas son las
que `pruebas/reproducir_casos.py` deja en `latencias.json`, escritas a mano.
Lo que se ata es que filas cuentan (y que lo decide LA CONSULTA MEDIDA, no la
llamada propia del arnes), que cifras salen de ellas, que el JSON dice por si
solo que mide y que no, y que con menos de 30 no se escribe nada.
"""
import importlib.util
import json
import pathlib

import numpy as np
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
DESCARTES = {"total": 0, "sin_bots": 0, "rechazo_previsto": 0, "fallo": 0,
             "error": 0, "no_coincide": 0, "sin_ms_extremo": 0}
CINCO = [5.2, 4.8, 6.1, 5.0, 5.5]


@pytest.fixture(scope="module")
def medir():
    """`scripts/medir_latencia.py` cargado como modulo."""
    spec = importlib.util.spec_from_file_location(
        "medir_latencia", REPO / "scripts" / "medir_latencia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fila(ms_extremo=1000, ms_modelo=150.0, **cambios):
    fila = {"patientId": "p", "perfil": "01-positiva_clara",
            "rechazo_previsto": False, "con_bots": True, "fallo": None,
            "error_consulta": None, "coincide": "sí", "ms_extremo": ms_extremo,
            "ms_modelo": ms_modelo, "error_arnes": None, "ms_arnes": 60.0}
    fila.update(cambios)
    return fila


def _validas(n=40):
    """n consultas validas de 1000, 1100, 1200... ms."""
    return [_fila(ms_extremo=1000 + 100 * i, ms_modelo=140.0 + i) for i in range(n)]


def _descartes(**cuentas):
    return dict(DESCARTES, total=sum(cuentas.values()), **cuentas)


def test_las_claves_de_una_fila_son_las_que_escribe_el_arnes(medir):
    from pruebas.reproducir_casos import filas_de_latencia
    caso = {"patientId": "p", "perfil": type("P", (), {"carpeta": "01-positiva_clara"})()}
    fila = filas_de_latencia([(caso, {"con_bots": False}, {"error": None, "resultado": None})])[0]
    assert tuple(fila) == medir.CLAVES
    assert tuple(_fila()) == medir.CLAVES


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
    assert r["descartadas"] == DESCARTES
    assert r["total_a_mano"] == "no medido"


def test_cualquiera_puede_recalcular_los_percentiles(medir):
    """Se publican las medidas, ordenadas y sin identificadores, y el metodo."""
    desordenadas = list(reversed(_validas(37)))
    r = medir.resumir(desordenadas)
    assert r["ms_extremo_ordenados"] == [1000.0 + 100 * i for i in range(37)]
    assert len(r["ms_extremo_ordenados"]) == r["n"] == 37
    p50, p95 = np.percentile(r["ms_extremo_ordenados"], [50, 95], method="linear")
    assert (r["p50_ms"], r["p95_ms"]) == (round(float(p50), 1), round(float(p95), 1))
    assert "tipo 7 de Hyndman y Fan" in r["percentil"]
    assert "`ms_extremo_ordenados`" in r["percentil"]
    # con 37 consultas el p95 cae entre la 35.ª y la 36.ª: el maximo no entra
    assert r["ms_extremo_ordenados"][34] < r["p95_ms"] < r["ms_extremo_ordenados"][35]
    assert all(set(f) == set(medir.CLAVES) for f in desordenadas), "no se tocan las filas"


def test_el_json_dice_por_si_solo_que_mide_y_que_no(medir):
    r = medir.resumir(_validas(30), manual=CINCO)
    assert r["titulo"] == ("Latencia del sistema desplegado, medida con el arnés "
                           "(no es una simulación): el tramo `ms_extremo`, cota "
                           "inferior de la latencia de extremo a extremo")
    assert "semisintética" not in json.dumps(r, ensure_ascii=False)
    for trozo in ("`Normalizar update`", "`Desenlace`", "la subida a Telegram",
                  "la entrega del webhook", "el envío de `Responder`"):
        assert trozo in r["tramo"], trozo
    for trozo in ("cota inferior", "tampoco lo cumple de extremo a extremo",
                  "necesario pero no suficiente", "se acota, si se cronometró, en "
                  "`total_a_mano`"):
        assert trozo in r["lectura"], trozo
    for trozo in ("tiempo TOTAL, no el tramo que falta", "no un percentil",
                  "no se suma a `p50_ms`"):
        assert trozo in r["total_a_mano"]["que_es"], trozo
    assert list(r) == ["titulo", "tramo", "lectura", "n", "percentil", "p50_ms",
                       "p95_ms", "minimo_ms", "maximo_ms", "ms_extremo_ordenados",
                       "modelo_p50_ms", "umbrales_s", "frente_a_umbrales",
                       "total_a_mano", "descartadas"]
    assert list(r["descartadas"]) == ["total"] + list(medir.MOTIVOS)


def test_cuenta_la_consulta_medida_y_no_la_llamada_del_arnes(medir):
    """`ms_extremo` es de la consulta de los bots: su error es el que decide.

    Un `copiloto_no_responde` solo nace en el flujo (el tiempo limite del
    nodo HTTP): la llamada propia del arnes, segundos despues, sale limpia.
    Esa consulta NO es valida, y sus 30 s no entran en el p95."""
    filas = _validas(30) + [
        _fila(error_consulta="copiloto_no_responde: tiempo agotado",
              error_arnes=None, ms_extremo=30450, ms_modelo=None,
              coincide="NO: uno dio resultado y el otro no"),
        _fila(error_consulta="descarga_fallida: x", error_arnes=None,
              ms_extremo=9000, coincide="NO: uno dio resultado y el otro no"),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 30 and r["maximo_ms"] == 3900.0
    assert r["descartadas"] == _descartes(error=2)
    # y al reves: si lo que fallo fue la llamada del arnes, la medida es buena
    # solo si las dos lecturas coinciden; si no, se descarta diciendo por que
    filas = _validas(30) + [
        _fila(error_arnes="copiloto_no_responde: x", coincide="sí", ms_extremo=5000),
        _fila(error_arnes="copiloto_no_responde: x", ms_extremo=6000,
              coincide="NO: uno dio resultado y el otro no"),
        _fila(coincide=None, ms_extremo=7000),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 31 and r["maximo_ms"] == 5000.0
    assert r["descartadas"] == _descartes(no_coincide=2)


def test_cada_fila_se_descarta_por_un_solo_motivo_y_en_orden(medir):
    filas = _validas(30) + [
        _fila(con_bots=False, ms_extremo=None),
        _fila(con_bots=False, ms_extremo=None),
        _fila(fallo="no se pudo subir la placa", ms_extremo=None, coincide=None),
        # los rechazos que el corpus busca a proposito (perfiles 05 a 09)
        _fila(perfil="05-menor_edad", rechazo_previsto=True,
              error_consulta="fuera_de_alcance: eso", error_arnes="fuera_de_alcance: eso",
              ms_extremo=410, ms_modelo=None),
        _fila(perfil="08-fichero_corrupto_FABRICADO", rechazo_previsto=True,
              error_consulta="dicom_invalido: x", ms_extremo=90000, ms_modelo=None),
        # un rechazo previsto que NO rechazo tampoco es una consulta de la medida
        _fila(perfil="05-menor_edad", rechazo_previsto=True, ms_extremo=1500),
        # un error que nadie esperaba, en un perfil que tenia que dar resultado
        _fila(error_consulta="copiloto_no_responde: x", ms_extremo=30001),
        _fila(ms_extremo=None),
        # el primero que le toca
        _fila(con_bots=False, fallo="x", rechazo_previsto=True,
              error_consulta="y", coincide="NO", ms_extremo=None),
        # un rechazo previsto que no llego al final es un rechazo previsto:
        # `fallo` cuenta solo las consultas que tenian que dar resultado
        _fila(fallo="x", rechazo_previsto=True, error_consulta="y", ms_extremo=None),
        _fila(perfil="09-fichero_enorme_FABRICADO", rechazo_previsto=True,
              fallo="no se pudo subir la placa", ms_extremo=None, coincide=None),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 30
    assert r["maximo_ms"] == 3900.0, "ni el rechazo de 90 s ni el error de 30 s cuentan"
    assert r["descartadas"] == _descartes(sin_bots=3, rechazo_previsto=5, fallo=1,
                                          error=1, sin_ms_extremo=1)
    assert list(r["descartadas"]) == ["total", "sin_bots", "rechazo_previsto", "fallo",
                                      "error", "no_coincide", "sin_ms_extremo"]
    assert r["n"] + r["descartadas"]["total"] == len(filas)


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
    assert r["descartadas"] == _descartes(sin_ms_extremo=5)
    # y un ms_modelo que no es una medida no entra en la mediana del modelo
    r = medir.resumir([_fila(ms_modelo="x")] * 15 + [_fila(ms_modelo=150.0)] * 15)
    assert r["modelo_p50_ms"] == 150.0
    assert medir.resumir([_fila(ms_modelo=None)] * 30)["modelo_p50_ms"] is None


def test_con_menos_del_minimo_no_se_mide_y_dice_cuantas_hay_y_que_hacer(medir):
    filas = _validas(29) + [_fila(error_consulta="copiloto_no_responde: x")]
    with pytest.raises(SystemExit) as salida:
        medir.resumir(filas)
    mensaje = str(salida.value)
    assert "29 consultas" in mensaje and "30" in mensaje
    assert "no medida" in mensaje
    assert "'error': 1" in mensaje
    assert "--por-perfil mayor" in mensaje and "lleva esta causa al informe" in mensaje
    assert "que no son un rechazo previsto" in mensaje
    with pytest.raises(SystemExit, match="0 consultas"):
        medir.resumir([])
    assert medir.resumir(filas, minimo=29)["n"] == 29
    # con 31 validas hacen falta DOS fallos para quedarse sin medicion
    assert medir.resumir(_validas(30) + [_fila(fallo="x")])["n"] == 30
    with pytest.raises(SystemExit, match="29 consultas"):
        medir.resumir(_validas(29) + [_fila(fallo="x"), _fila(fallo="y")])


def test_lo_medido_a_mano_lleva_los_valores_su_mediana_y_lo_que_es(medir):
    r = medir.resumir(_validas(30), manual=CINCO)
    assert r["total_a_mano"] == {
        "que_es": medir.A_MANO, "valores_s": CINCO, "n": 5,
        "mediana_s": 5.2, "minimo_s": 4.8, "maximo_s": 6.1}
    assert medir.resumir(_validas(30), manual=[])["total_a_mano"] == "no medido"
    assert medir.resumir(_validas(30), manual=None)["total_a_mano"] == "no medido"


def test_leer_manual_acepta_segundos_con_punto_y_rechaza_lo_demas(medir):
    assert medir.leer_manual("5.2,4.8, 6.1,5.0,5.5") == CINCO
    assert medir.leer_manual("5,4,6,5,5") == [5.0, 4.0, 6.0, 5.0, 5.0]
    assert medir.leer_manual(None) is None
    assert medir.A_MANO_N == 5
    # el marcador del runbook, copiado tal cual, NO escribe medidas inventadas
    for malo in ("S1,S2,S3,S4,S5", "<s1>,<s2>", "5.2;4.8", "cinco", "5.2,,4.8,6.1,5.0",
                 "5.2,4.8,6.1,5.0,-1", "5.2,4.8,6.1,5.0,0", "5.2,4.8,6.1,5.0,nan",
                 "5.2,4.8,6.1,5.0,inf", "",
                 # cuatro, seis, y los diez que salen de escribir los decimales con coma
                 "5.2,4.8,6.1,5.0", "5.2,4.8,6.1,5.0,5.5,5.1", "5,2,4,8,6,1,5,0,5,5"):
        with pytest.raises(SystemExit, match="--manual espera los 5 tiempos"):
            medir.leer_manual(malo)


def test_ni_el_script_ni_el_runbook_traen_medidas_de_ejemplo(medir):
    """Una orden lista para copiar con cinco tiempos inventados acabaria en un
    JSON versionado: el ejemplo es un marcador que `leer_manual` rechaza."""
    import re
    for ruta in (REPO / "scripts" / "medir_latencia.py", REPO / "docs" / "sp5-sesion.md",
                 REPO / "docs" / "validacion-semisintetica" / "README.md"):
        texto = ruta.read_text(encoding="utf-8")
        assert not re.search(r"--manual\s+\"?\d", texto), ruta.name
    runbook = (REPO / "docs" / "sp5-sesion.md").read_text(encoding="utf-8")
    marcador = re.search(r'--manual "([^"]+)"', runbook).group(1)
    with pytest.raises(SystemExit, match="--manual"):
        medir.leer_manual(marcador)


def test_la_cli_escribe_el_json_y_no_lo_escribe_si_no_hay_minimo(medir, tmp_path, capsys):
    corrida = tmp_path / "corpus" / "latencias.json"
    corrida.parent.mkdir()
    corrida.write_text(json.dumps(_validas(36)), encoding="utf-8")
    salida = tmp_path / "docs" / "latencia.json"
    assert medir.main(["--corrida", str(corrida), "--salida", str(salida),
                       "--manual", "5.2,4.8,6.1,5.0,5.5"]) == 0
    escrito = json.loads(salida.read_text(encoding="utf-8"))
    assert escrito == medir.resumir(_validas(36), manual=CINCO)
    crudo = salida.read_bytes()
    assert "simulación)".encode("utf-8") in crudo, "sin escapes \\u"
    assert b"\r" not in crudo and crudo.endswith(b"}\n")
    dicho = capsys.readouterr().out
    assert "36 consultas" in dicho and "p50 2,75 s" in dicho and "p95 4,33 s" in dicho
    assert "AVISO" not in dicho

    corta = tmp_path / "corta.json"
    corta.write_text(json.dumps(_validas(12)), encoding="utf-8")
    with pytest.raises(SystemExit, match="12 consultas"):
        medir.main(["--corrida", str(corta), "--salida", str(salida)])
    assert json.loads(salida.read_text(encoding="utf-8")) == escrito, "no pisa el bueno"
    otra = tmp_path / "no-se-escribe.json"
    with pytest.raises(SystemExit, match="12 consultas"):
        medir.main(["--corrida", str(corta), "--salida", str(otra)])
    assert not otra.exists()
    with pytest.raises(SystemExit, match="--manual"):
        medir.main(["--corrida", str(corrida), "--salida", str(otra),
                    "--manual", "S1,S2,S3,S4,S5"])
    assert not otra.exists()


def test_repetir_sin_manual_avisa_de_que_se_pierde_lo_medido_a_mano(medir, tmp_path, capsys):
    corrida = tmp_path / "latencias.json"
    corrida.write_text(json.dumps(_validas(30)), encoding="utf-8")
    salida = tmp_path / "latencia.json"
    orden = ["--corrida", str(corrida), "--salida", str(salida)]
    assert medir.main(orden) == 0
    assert "AVISO" not in capsys.readouterr().out          # no habia nada que perder
    assert medir.main(orden) == 0
    assert "AVISO" not in capsys.readouterr().out          # el anterior decia «no medido»
    assert medir.main(orden + ["--manual", "5.2,4.8,6.1,5.0,5.5"]) == 0
    assert "AVISO" not in capsys.readouterr().out
    assert medir.main(orden) == 0
    dicho = capsys.readouterr().out
    # el aviso da los valores que se pierden, listos para repetir la orden
    assert "AVISO" in dicho and '--manual "5.2,4.8,6.1,5.0,5.5"' in dicho
    assert json.loads(salida.read_text(encoding="utf-8"))["total_a_mano"] == "no medido"
    for roto in ("esto no es un JSON", "[1, 2]", '{"total_a_mano": {"n": 5}}',
                 '{"total_a_mano": {"valores_s": []}}'):
        salida.write_text(roto, encoding="utf-8")
        assert medir.main(orden) == 0                      # un fichero raro no estorba
        assert "AVISO" not in capsys.readouterr().out


def test_si_no_se_puede_escribir_el_json_el_anterior_sigue_entero(
        medir, tmp_path, monkeypatch):
    corrida = tmp_path / "latencias.json"
    corrida.write_text(json.dumps(_validas(30)), encoding="utf-8")
    salida = tmp_path / "latencia.json"
    orden = ["--corrida", str(corrida), "--salida", str(salida)]
    assert medir.main(orden) == 0
    bueno = salida.read_bytes()
    monkeypatch.setattr(medir, "resumir",
                        lambda filas, manual=None: {"p50_ms": float("nan")})
    with pytest.raises(ValueError):
        medir.main(orden)
    assert salida.read_bytes() == bueno


def test_la_cli_rechaza_una_corrida_que_no_es_de_este_arnes(medir, tmp_path):
    destino = str(tmp_path / "s.json")
    with pytest.raises(SystemExit, match="no existe"):
        medir.main(["--corrida", str(tmp_path / "nada.json"), "--salida", destino])
    casos = {
        "rara.json": (json.dumps({"filas": []}), "no es una lista"),
        "vacia.json": ("", "no es un JSON"),
        "rota.json": ('[{"patientId": ', "no es un JSON"),
        "numeros.json": (json.dumps([1, 2, 3]), "la fila 1 de"),
        # la fila de una version anterior del arnes: llevaba `error`, no
        # `error_consulta`, y con ella se mediria la llamada equivocada
        "vieja.json": (json.dumps(
            [_fila()] + [{"patientId": "p", "perfil": "01-positiva_clara",
                          "con_bots": True, "fallo": None, "error": None,
                          "ms_extremo": 1000, "ms_modelo": 150.0, "ms_arnes": 60.0}]),
            "la fila 2 de"),
    }
    for nombre, (contenido, mensaje) in casos.items():
        ruta = tmp_path / nombre
        ruta.write_text(contenido, encoding="utf-8")
        with pytest.raises(SystemExit, match=mensaje):
            medir.main(["--corrida", str(ruta), "--salida", destino])
    assert not (tmp_path / "s.json").exists()
```

- [ ] **Paso 7: Correrlas y ver el fallo**

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_medir_latencia.py
```

Salida esperada: las diecisiete pruebas del script dan ERROR en la fixture `medir`, con
`FileNotFoundError: [Errno 2] No such file or directory: '...scripts\\medir_latencia.py'`
(el script no existe todavía), y la prueba de punta a punta del arnés falla por lo mismo:

```
17 errors
```

- [ ] **Paso 8: Escribir el script**

`scripts/medir_latencia.py` (fichero nuevo):

```python
# -*- coding: utf-8 -*-
"""Mide la latencia del sistema desplegado: de latencias.json del arnes a latencia.json.

USO
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "S1,S2,S3,S4,S5"

Lee el `latencias.json` que deja una corrida CON BOTS de
`pruebas/reproducir_casos.py` contra el sistema desplegado y escribe
docs/validacion-semisintetica/latencia.json (spec de SP5 §6.3). Es una
MEDICION, no una simulacion: lo dice el titulo del JSON.

Cuenta solo las consultas que pasaron por los bots, llegaron al final, no
son un rechazo previsto, no dieron error EN LA CONSULTA MEDIDA, coinciden
con la lectura del arnes (que tambien tiene que haber salido bien) y llevan
`ms_extremo`. Con menos de 30 no escribe
nada: la latencia queda «no medida», y el informe lo dice con la causa.

`ms_extremo` es una COTA INFERIOR de lo que espera el profesional: no ve la
subida a Telegram, la entrega del webhook ni el envio de la respuesta. Por
eso el JSON dice que cumplir un umbral aqui es necesario y no suficiente.

`--manual` son los segundos, cronometrados a mano en el cliente de Telegram,
desde que se envia la placa hasta que aparece la respuesta: el tiempo TOTAL,
en 5 consultas. Acota lo que `ms_extremo` no ve; no es un percentil ni se
suma al p50. S1..S5 son los cinco tiempos, con punto decimal (con coma
saldrian diez valores, y se rechazan): sin medicion a mano, `--manual` se
omite.
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

TITULO = ("Latencia del sistema desplegado, medida con el arnés (no es una "
          "simulación): el tramo `ms_extremo`, cota inferior de la latencia "
          "de extremo a extremo")
TRAMO = ("`ms_extremo` de la tabla `consultas`: desde que `Normalizar update` "
         "recibe el update con la placa hasta que `Desenlace` compone la "
         "respuesta. Excluye la subida a Telegram, la entrega del webhook y "
         "el envío de `Responder`: no es el tiempo desde que el profesional "
         "sube la radiografía hasta que recibe el pre-informe.")
LECTURA = ("`ms_extremo` es una cota inferior de lo que espera el "
           "profesional. Si un percentil NO cumple un umbral aquí, tampoco "
           "lo cumple de extremo a extremo; si lo cumple aquí, es necesario "
           "pero no suficiente. Lo que `ms_extremo` no ve se acota, si se "
           "cronometró, en `total_a_mano`.")
PERCENTIL = ("interpolación lineal entre estadísticos de orden (el método "
             "«linear» de numpy, tipo 7 de Hyndman y Fan) sobre "
             "`ms_extremo_ordenados`")
A_MANO = ("segundos desde que se envía la placa hasta que aparece la "
          "respuesta, cronometrados a mano en el cliente de Telegram. Es el "
          "tiempo TOTAL, no el tramo que falta: una acotación en pocas "
          "consultas, no un percentil, y no se suma a `p50_ms`")
MINIMO = 30
A_MANO_N = 5                 # spec §6.3: se acota a mano en 5 consultas
UMBRALES_S = {"minimo": 8, "objetivo": 3}
NO_MEDIDO = "no medido"
# Los motivos de descarte, en el orden en que se miran: cada fila cuenta en
# uno solo, el primero que le toca. Los rechazos previstos van antes que los
# fallos: asi `fallo` cuenta solo las consultas que tenian que dar resultado.
MOTIVOS = ("sin_bots", "rechazo_previsto", "fallo", "error", "no_coincide",
           "sin_ms_extremo")
# Las claves de una fila de latencias.json (las escribe
# `pruebas/reproducir_casos.py::filas_de_latencia`).
CLAVES = ("patientId", "perfil", "rechazo_previsto", "con_bots", "fallo",
          "error_consulta", "coincide", "ms_extremo", "ms_modelo",
          "error_arnes", "ms_arnes")


def _es_una_medida(v) -> bool:
    """Unos milisegundos: un numero finito y no negativo. Ni `None`, ni una
    cadena, ni un booleano (`True` contaria como 1 ms)."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v >= 0)


def _motivo(fila):
    """Por que una fila no cuenta, o None si cuenta.

    El error que cuenta es el de LA CONSULTA MEDIDA, la que paso por los
    bots y escribio `ms_extremo`: un `copiloto_no_responde` del flujo no
    alcanza a la llamada propia del arnes, que es otra y no pasa por Telegram
    ni por n8n. `error_arnes` no se mira, pero la llamada del arnes si pesa
    por `coincide`: una consulta solo cuenta si la lectura del arnes la
    confirma, y si esa llamada fallo no hay con que confirmarla. Eso tambien
    es `no_coincide`."""
    if not fila.get("con_bots"):
        return "sin_bots"
    if fila.get("rechazo_previsto"):
        return "rechazo_previsto"
    if fila.get("fallo"):
        return "fallo"
    if fila.get("error_consulta"):
        return "error"
    if fila.get("coincide") != "sí":
        return "no_coincide"
    if not _es_una_medida(fila.get("ms_extremo")):
        return "sin_ms_extremo"
    return None


def _frente_a(ms):
    return {"cumple_minimo": bool(ms <= UMBRALES_S["minimo"] * 1000),
            "cumple_objetivo": bool(ms <= UMBRALES_S["objetivo"] * 1000)}


def resumir(filas, minimo=MINIMO, manual=None) -> dict:
    """El contenido de latencia.json, desde las filas de latencias.json.

    `manual` son los segundos de envio a respuesta cronometrados a mano (el
    tiempo total, no el tramo que falta); sin ellos, `total_a_mano` dice «no
    medido». Con menos de `minimo` consultas validas sale con `SystemExit`:
    no hay cifra que dar.
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
            f"hay {len(validas)} consultas con bots, que no son un rechazo "
            f"previsto, sin fallo ni error, que coinciden con el arnés y llevan "
            f"ms_extremo, y hacen falta "
            f"{minimo}: la latencia de extremo a extremo queda «no medida» y "
            f"no se escribe nada (descartadas: {descartadas}). Vuelve a correr "
            f"el arnés con un --por-perfil mayor o, si no se puede, lleva "
            f"esta causa al informe")

    ms = np.sort(np.array([float(f["ms_extremo"]) for f in validas]))
    # Los umbrales se comparan con el percentil SIN redondear: 8 000,04 ms se
    # escribe «8000,0» y no cumple los 8 s. Se redondea solo lo que se escribe.
    p50, p95 = (float(v) for v in np.percentile(ms, [50, 95]))
    modelo = [float(f["ms_modelo"]) for f in validas if _es_una_medida(f.get("ms_modelo"))]
    manual = [float(v) for v in (manual or [])]
    return {
        "titulo": TITULO,
        "tramo": TRAMO,
        "lectura": LECTURA,
        "n": len(validas),
        "percentil": PERCENTIL,
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "minimo_ms": round(float(ms.min()), 1),
        "maximo_ms": round(float(ms.max()), 1),
        "ms_extremo_ordenados": [round(float(v), 1) for v in ms],
        # lo que el servidor dijo que tardo el modelo EN las consultas medidas
        "modelo_p50_ms": round(statistics.median(modelo), 1) if modelo else None,
        "umbrales_s": dict(UMBRALES_S),
        "frente_a_umbrales": {"p50": _frente_a(p50), "p95": _frente_a(p95)},
        "total_a_mano": ({"que_es": A_MANO, "valores_s": manual, "n": len(manual),
                          "mediana_s": round(statistics.median(manual), 2),
                          "minimo_s": min(manual), "maximo_s": max(manual)}
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
    if len(valores) != A_MANO_N or any(not 0 < v < float("inf") for v in valores):
        raise SystemExit(
            f"--manual espera los {A_MANO_N} tiempos cronometrados, en segundos "
            f"positivos, con punto decimal (no coma) y separados por comas; "
            f"llegó «{texto}». Sin medición a mano, omite --manual")
    return valores


def leer_corrida(ruta) -> list:
    """Las filas de un latencias.json, comprobadas: lo que no es de este
    arnes no se mide."""
    ruta = pathlib.Path(ruta)
    if not ruta.is_file():
        raise SystemExit(f"no existe {ruta}: lo escribe una corrida de "
                         f"pruebas/reproducir_casos.py en su carpeta de salida")
    try:
        filas = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SystemExit(f"{ruta} no es un JSON ({error}): vuelve a correr "
                         f"pruebas/reproducir_casos.py") from None
    if not isinstance(filas, list):
        raise SystemExit(f"{ruta} no es una lista de filas de latencia")
    for n, fila in enumerate(filas, 1):
        if not isinstance(fila, dict) or set(fila) != set(CLAVES):
            raise SystemExit(
                f"la fila {n} de {ruta} no lleva las claves de una fila de "
                f"latencia ({', '.join(CLAVES)}): si es de una versión "
                f"anterior del arnés, vuelve a correr pruebas/reproducir_casos.py")
    return filas


def _a_mano_anterior(salida):
    """Los tiempos a mano del latencia.json que se va a pisar, o None si no
    los llevaba (o no se puede leer)."""
    try:
        anterior = json.loads(pathlib.Path(salida).read_text(encoding="utf-8"))
        return list(anterior["total_a_mano"]["valores_s"]) or None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _segundos(ms):
    return f"{ms / 1000:.2f}".replace(".", ",") + " s"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corrida", required=True,
                   help="el latencias.json de una corrida con bots del arnés")
    p.add_argument("--salida", default=str(CARPETA / NOMBRE))
    p.add_argument("--manual", metavar="SEGUNDOS",
                   help="los segundos de envío a respuesta cronometrados a mano "
                        "en el cliente de Telegram, con punto decimal y "
                        "separados por comas; sin medición a mano se omite")
    args = p.parse_args(argv)

    manual = leer_manual(args.manual)
    resultado = resumir(leer_corrida(args.corrida), manual=manual)

    # Se serializa ANTES de abrir: si fallara, el fichero anterior sigue entero.
    texto = json.dumps(resultado, ensure_ascii=False, indent=1, allow_nan=False) + "\n"
    salida = pathlib.Path(args.salida)
    anteriores = _a_mano_anterior(salida)
    if manual is None and anteriores:
        print(f"AVISO: el {salida.name} anterior llevaba una medición a mano y "
              f"este no. Para conservarla, repite la orden con "
              f"--manual \"{','.join(str(v) for v in anteriores)}\"")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
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
17 passed
```

Y la prueba de punta a punta, que ya tiene su script:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_reproducir_casos.py -k latencia
```

Salida esperada: `3 passed` y, con `-k flujo`, `1 passed`.

Y el script, a mano, sin corrida (sale con código 1 y este mensaje):

```bash
C:/venv-copiloto/Scripts/python.exe scripts/medir_latencia.py --corrida nada.json
```

```
no existe nada.json: lo escribe una corrida de pruebas/reproducir_casos.py en su carpeta de salida
```

- [ ] **Paso 10: Commit**

```bash
git add scripts/medir_latencia.py tests/test_medir_latencia.py tests/test_reproducir_casos.py
git commit -m "feat(validacion): medir_latencia.py, p50 y p95 de ms_extremo frente a 8 s y 3 s (SP5-B1 T8)" -m "Lee el latencias.json de una corrida con bots y escribe docs/validacion-semisintetica/latencia.json: es una medicion, no una simulacion, y el titulo lo dice. Cuenta solo las consultas con bots, sin fallo, que no son un rechazo previsto, sin error en la consulta medida, que coinciden con el arnes y llevan ms_extremo; con menos de 30 no escribe nada y la latencia queda «no medida». ms_extremo es una cota inferior, y lo que no ve se acota cronometrando a mano el tiempo total con --manual." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
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
cinco perfiles son rechazos previstos (20 casos más) y se cuentan aparte. Con
el `--por-perfil 10` por defecto serían 31: bastarían dos conversaciones
fallidas para dejar la medición sin hacer. Son 57 casos y, como poco, 20
minutos. El arnés imprime «N casos» al arrancar: si salen menos de 57, a algún
perfil le faltan placas en la caché; lo que importa es que las consultas de
los perfiles 01 a 04 pasen holgadamente de 30, y `scripts/medir_latencia.py`
dice cuántas contó y cuántas descartó, con el motivo.

La corrida deja `pruebas/corpus/latencia/latencias.json` (una fila por caso;
la carpeta está ignorada). Después:

    C:/venv-copiloto/Scripts/python.exe scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "S1,S2,S3,S4,S5"

`S1`…`S5` son los cinco tiempos cronometrados a mano (más abajo), en segundos
y con punto decimal: la orden, copiada tal cual, se niega a correr. Sin
medición a mano se omite `--manual`, y el JSON dice «no medido».

Escribe `docs/validacion-semisintetica/latencia.json` con el p50 y el p95 de
`ms_extremo` frente a los umbrales de 8 s y 3 s, las medidas ordenadas (sin
identificadores, para que cualquiera pueda recalcular) y cuántas filas se
descartaron y por qué. Una consulta cuenta si pasó por los bots, llegó al
final, no es un rechazo previsto, no dio error **en la propia consulta** y
coincide con la lectura del arnés. Con menos de 30 consultas válidas se
detiene, lo dice y no escribe nada.

`ms_extremo` va desde que `Normalizar update` recibe el update con la placa
hasta que `Desenlace` compone la respuesta: no ve la subida a Telegram, la
entrega del webhook ni el envío de `Responder`. Es, por tanto, una **cota
inferior** de lo que espera el profesional: si no cumple un umbral, la
latencia de extremo a extremo tampoco lo cumple; si lo cumple, es necesario
pero no suficiente.

Lo que `ms_extremo` no ve se acota **a mano, en 5 consultas** completas,
hechas por una persona con los dos bots y un cronómetro, porque el cliente de
Telegram solo enseña horas y minutos. Cada consulta necesita su propio
código: primero el cuestionario en el bot del paciente y después, en el del
profesional, el código y la placa. Hacen falta un chat dado de alta como
profesional y cinco placas del conjunto de prueba. El bot del paciente admite
5 cuestionarios por chat y día: las cinco consultas caben justas, y repetir
una obliga a esperar al día siguiente o a usar otro chat. El cronómetro se
pone en marcha al enviar la placa y se para cuando aparece el pre-informe: es
el tiempo **total**, subida incluida, no el tramo que falta, y no se suma al
p50. Son los cinco valores de `--manual`. Esas consultas quedan registradas
con el chat de quien mide: son consultas de prueba del equipo, y el informe
lo dice.

Una consulta cuyo flujo acabó bien pero que el arnés no pudo confirmar con su
propia llamada se descarta como `no_coincide`: no entra en la medida, y se ve
en el recuento.

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
las dos huellas) y `latencia.json` (cifras agregadas y las medidas
ordenadas, sin identificadores). No se versionan
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
al menos 30 consultas sin error, frente a los umbrales de 8 s y 3 s, con las
medidas ordenadas y el método del percentil. El tramo medido va desde que
`Normalizar update` recibe el update con la placa hasta que `Desenlace`
compone la respuesta; la subida a Telegram, la entrega del webhook y el envío
de `Responder` quedan fuera. Es, por tanto, una **cota inferior** de la
latencia de extremo a extremo: cumplir un umbral aquí es necesario, no
suficiente. Lo que queda fuera se acota cronometrando a mano 5 consultas
completas (`total_a_mano`: el tiempo total, que no se suma al p50). Los casos
son placas de RSNA con clínica inventada: no hay usuarios ni pacientes. Si el
fichero no está, la latencia de extremo a extremo no se midió. Cómo se mide:
`docs/sp5-sesion.md`, «Medir la latencia».
````

Por qué `--por-perfil 12` y no 4: el arnés no da `por_perfil × 9` casos. El
perfil 04 reusa UNA placa del 03, los tres fabricados llevan un caso cada uno
y solo existen 5 edades imposibles; y los perfiles 05 a 09 son rechazos
previstos, que se cuentan aparte. Las consultas válidas son `3 × por_perfil + 1`:
13 con `--por-perfil 4`, 31 con 10 (el valor por defecto), 37 con 12.

Y el spec tiene que decir lo mismo que el instrumento. En
`docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`, dos
sustituciones. Busca (es una fila de tabla, en una sola línea):

```markdown
§5.4. El tramo que falta se acota a mano en 5 casos (hora del envío en el cliente de Telegram frente a hora de la respuesta) y se dice. Sin corrida con bots antes del 16-oct, **no medido** con la causa |
```

y sustitúyelo por:

```markdown
§5.4. `ms_extremo` es, por tanto, una cota inferior: no cumplir un umbral con él es no cumplirlo de extremo a extremo; cumplirlo es necesario, no suficiente. Lo que no ve se acota a mano en 5 consultas, cronometrando el tiempo total desde que se envía la placa hasta que aparece la respuesta (el cliente de Telegram solo muestra horas y minutos), y se dice. Sin corrida con bots antes del 16-oct, **no medido** con la causa |
```

Busca (es una fila de tabla, en una sola línea):

```markdown
| Latencia de extremo a extremo (8 s / 3 s) | cumplido con cambio (provisional) | se mide `ms_extremo`, el tramo n8n → respuesta, no la subida a Telegram ni la entrega (§6.3); si no hay corrida con bots antes del 16-oct, «no medido» con la causa |
```

y sustitúyelo por:

```markdown
| Latencia de extremo a extremo (8 s / 3 s) | cumplido con cambio (provisional) | se mide `ms_extremo`, el tramo n8n → respuesta, no la subida a Telegram ni la entrega (§6.3): es una cota inferior, así que si no cumple el umbral la etiqueta es «no cumplido», y si lo cumple, «cumplido con cambio», diciendo el tramo que no ve y lo cronometrado a mano; si no hay corrida con bots antes del 16-oct, «no medido» con la causa |
```

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
git add docs/sp5-sesion.md docs/validacion-semisintetica/README.md docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md
git commit -m "docs(sp5): como se mide la latencia de extremo a extremo y que es latencia.json (SP5-B1 T8)" -m "Runbook: corrida con bots del arnes con --por-perfil 12 (37 consultas validas), scripts/medir_latencia.py y cinco consultas cronometradas a mano, con lo que hace falta para hacerlas. El spec dice que ms_extremo es una cota inferior. El README de la carpeta dice que latencia.json es una medicion del sistema desplegado con casos de prueba, no una simulacion." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Lo que pidió la última revisión de la tarea

- el runbook decía que cada consulta cronometrada necesita su propio código, y es
  falso: el código no es de un solo uso y vale 7 días (spec de SP3 §5.2);
- el procedimiento a mano dice los pasos del bot del profesional y cómo se da de
  alta el chat;
- el spec decide la etiqueta con el p95 frente al mínimo de 8 s, y lo cronometrado
  a mano pesa en contra;
- la ayuda de `--manual` dice que son cinco tiempos, y el script los repite en
  pantalla;
- una prueba fija los rótulos del arnés.

- [ ] **Paso 14: Las pruebas, que fallan**

Aplica las sustituciones de los dos ficheros de pruebas (abajo) y corre:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_medir_latencia.py tests/test_reproducir_casos.py
```

Esperado: `1 failed, 46 passed` (con las pruebas de la tarea 9 ya en el fichero del
arnés). La prueba nueva del arnés pasa ya: fija los rótulos del paso 3.

- [ ] **Paso 15: El script, el runbook y el spec**

Aplica las demás sustituciones y corre la misma orden. Esperado: `47 passed`.

- [ ] **Paso 16: Commit**

```bash
git add tests/test_medir_latencia.py tests/test_reproducir_casos.py scripts/medir_latencia.py docs/sp5-sesion.md docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md
git commit -m "fix(validacion): el runbook de la latencia dice bien lo del codigo, y el spec con que se decide la etiqueta" -m "El codigo del cuestionario no es de un solo uso: basta uno para las cinco consultas cronometradas. El procedimiento a mano dice los pasos del bot del profesional. El spec decide la etiqueta con el p95 frente al minimo de 8 s, y lo cronometrado a mano pesa en contra. El script repite en pantalla los cinco tiempos." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

**Las sustituciones.** Cada sustitución da el texto exacto a buscar (aparece UNA vez) y el que lo
sustituye. Primero las de las pruebas (y verlas fallar), después las demás.

**Las pruebas del script: `tests/test_medir_latencia.py`**

**1. Busca**

````python
    dicho = capsys.readouterr().out
    assert "36 consultas" in dicho and "p50 2,75 s" in dicho and "p95 4,33 s" in dicho
    assert "AVISO" not in dicho
````

y sustitúyelo por

````python
    dicho = capsys.readouterr().out
    assert "36 consultas" in dicho and "p50 2,75 s" in dicho and "p95 4,33 s" in dicho
    assert "AVISO" not in dicho
    # lo cronometrado se repite en pantalla: un decimal con coma se ve aqui
    assert "cronometrado a mano: 5,20 s; 4,80 s; 6,10 s; 5,00 s; 5,50 s" in dicho
    assert "cinco tiempos" in medir.leer_manual.__doc__.lower()
````

**2. Busca**

````python
    assert medir.main(orden) == 0
    assert "AVISO" not in capsys.readouterr().out          # no habia nada que perder
````

y sustitúyelo por

````python
    assert medir.main(orden) == 0
    dicho = capsys.readouterr().out
    assert "AVISO" not in dicho                            # no habia nada que perder
    assert "cronometrado a mano" not in dicho              # ni nada cronometrado
````

**Las pruebas del arnés: `tests/test_reproducir_casos.py`**

**1. Busca**

````python
def test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida(tmp_path):
````

y sustitúyelo por

````python
def test_el_arnes_no_llama_de_extremo_a_extremo_a_ms_extremo(tmp_path):
    """`ms_extremo` es el tramo que ve el flujo, y en el resumen entran todas
    las filas: ninguno de los dos es la latencia de extremo a extremo."""
    from pruebas.reproducir_casos import resumen
    bien = {"texto": "CRIBADO — opacidad probable", "texto_paciente": "", "error": None,
            "resultado": UN_RESULTADO}
    obs = {"con_bots": True, "entrega": "intentada", "codigo": "K7QM",
           "ms_extremo": 1840, "ms_arnes": 61.5, "coincide": "sí",
           "error": None, "resultado": UN_RESULTADO}
    caso = texto_del_caso(_caso(), obs, bien)
    assert "ms_extremo (de n8n a la respuesta)" in caso and "1840 ms" in caso
    assert "de extremo a extremo" not in caso
    dicho = resumen([(_caso(), obs, bien)], True, tmp_path)
    assert "ms_extremo, todas las filas (mediana)" in dicho and "1840 ms" in dicho
    assert "de extremo a extremo (mediana)" not in dicho


def test_escribir_latencias_deja_el_json_en_la_carpeta_de_salida(tmp_path):
````

**El script: `scripts/medir_latencia.py`**

**1. Busca**

````python
def leer_manual(texto):
    """Los segundos de `--manual`: separados por comas y con punto decimal."""
````

y sustitúyelo por

````python
def leer_manual(texto):
    """Los CINCO tiempos de `--manual` (`A_MANO_N`), en segundos: separados
    por comas y con punto decimal. Con coma decimal saldrian diez valores y se
    rechazan; una mezcla de comas y puntos que de justo cinco no se puede
    distinguir de cinco tiempos, y por eso la orden imprime lo que escribio."""
````

**2. Busca**

````python
                   help="los segundos de envío a respuesta cronometrados a mano "
                        "en el cliente de Telegram, con punto decimal y "
                        "separados por comas; sin medición a mano se omite")
````

y sustitúyelo por

````python
                   help="los cinco tiempos, en segundos, de envío a respuesta "
                        "cronometrados a mano en el cliente de Telegram, con "
                        "punto decimal y separados por comas; sin medición a "
                        "mano se omite")
````

**3. Busca**

````python
    print(f"{resultado['n']} consultas: p50 {_segundos(resultado['p50_ms'])}, "
          f"p95 {_segundos(resultado['p95_ms'])} "
          f"({resultado['descartadas']['total']} descartadas); {salida}")
    return 0
````

y sustitúyelo por

````python
    print(f"{resultado['n']} consultas: p50 {_segundos(resultado['p50_ms'])}, "
          f"p95 {_segundos(resultado['p95_ms'])} "
          f"({resultado['descartadas']['total']} descartadas); {salida}")
    if manual is not None:
        # para que un decimal escrito con coma se vea antes de versionar nada
        print("cronometrado a mano: " + "; ".join(_segundos(1000 * v) for v in manual))
    return 0
````

**El runbook: `docs/sp5-sesion.md`**

**1. Busca**

````markdown
Lo que `ms_extremo` no ve se acota **a mano, en 5 consultas** completas,
hechas por una persona con los dos bots y un cronómetro, porque el cliente de
Telegram solo enseña horas y minutos. Cada consulta necesita su propio
código: primero el cuestionario en el bot del paciente y después, en el del
profesional, el código y la placa. Hacen falta un chat dado de alta como
profesional y cinco placas del conjunto de prueba. El bot del paciente admite
5 cuestionarios por chat y día: las cinco consultas caben justas, y repetir
una obliga a esperar al día siguiente o a usar otro chat. El cronómetro se
pone en marcha al enviar la placa y se para cuando aparece el pre-informe: es
el tiempo **total**, subida incluida, no el tramo que falta, y no se suma al
p50. Son los cinco valores de `--manual`. Esas consultas quedan registradas
con el chat de quien mide: son consultas de prueba del equipo, y el informe
lo dice.
````

y sustitúyelo por

````markdown
Lo que `ms_extremo` no ve se acota **a mano, en 5 consultas** completas,
hechas por una persona con los dos bots y un cronómetro, porque el cliente de
Telegram solo enseña horas y minutos. Hace falta:

- un chat dado de alta como profesional (`pruebas/profesionales.py --alta`);
- un código de cuestionario, del bot del paciente. Basta uno para las cinco
  consultas: el código no es de un solo uso y vale 7 días (spec de SP3 §5.2),
  y cada uso queda en `consultas`. Un cuestionario nuevo cuenta contra el
  límite de 5 por chat y día (spec de SP3 §4.2);
- cinco placas del conjunto de prueba, en DICOM.

En el bot del profesional cada consulta es: el código, los cuatro signos
(temperatura, frecuencia cardiaca, crepitantes y murmullo) y la placa, enviada
como **documento** (como foto, Telegram la recomprime a JPEG y deja de ser un
DICOM). El cronómetro se pone en marcha al enviar la placa y se para cuando
aparece el pre-informe: es el tiempo **total**, subida incluida, no el tramo
que falta, y no se suma al p50. Son los cinco valores de `--manual`. Esas
consultas quedan registradas con el chat de quien mide: son consultas de
prueba del equipo, y el informe lo dice.
````

**El spec: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`**

**1. Busca**

````markdown
(§6.3): es una cota inferior, así que si no cumple el umbral la etiqueta es «no cumplido», y si lo cumple, «cumplido con cambio», diciendo el tramo que no ve y lo cronometrado a mano; si no hay corrida con bots antes del 16-oct, «no medido» con la causa |
````

y sustitúyelo por

````markdown
(§6.3): es una cota inferior. La etiqueta se decide con el p95 frente al mínimo de 8 s (el p50 y el objetivo de 3 s se reportan al lado): si no lo cumple, «no cumplido»; si lo cumple, «cumplido con cambio», diciendo el tramo que no ve y lo cronometrado a mano. Lo cronometrado a mano pesa en contra: si su mediana supera los 8 s, «no cumplido». Si no hay corrida con bots antes del 16-oct, «no medido» con la causa |
````

---

### Tarea 9: Residuos de SP5-A

Nueve arreglos pequeños: ocho sobre código de SP5-A que ya está fusionado y
probado y uno del spec que sacó a la luz la revisión de la tarea 6. Cada letra
cambia solo lo que dice; van en cuatro commits: el acta (a, b, d), la
preparación (c, e), el generador y los datos (f, g) y el spec (h, i).

**Ficheros:**
- Modificar: `src/copiloto_triaje/validacion/concordancia.py` (a, b, d)
- Modificar: `docs/validacion-semisintetica/acta-h7-plantilla.md` (d)
- Modificar: `scripts/preparar_sesion.py` (c)
- Modificar: `pruebas/reproducir_casos.py` (e)
- Modificar: `docs/sp5-sesion.md` (c: el párrafo del runbook que describe `--fase mensajes`)
- Modificar: `src/copiloto_triaje/validacion/generador.py` (f)
- Modificar: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md` (h, i)
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

#### Grupo 4 — El spec (letras h, i)

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

- [ ] **Paso 16 bis: Corregir en el §4.4 dónde la derivación es menos extrema (letra i)**

El §4.4 dice que la RV de la derivación es menos extrema que la de validación
solo en k = 4. En k = 1 también lo es: 0,20 queda más cerca de 1 que 0,19 (la
diferencia de logaritmos es +0,05, y las dos RV son menores que 1). El
documento de análisis lo calcula y dice «k = 1 y 4»; el spec tiene que decir
lo mismo. En el mismo fichero, busca:

```markdown
derivación es más extrema que la validación en k = 0, 2, 3 y 5 y menos en
k = 4: el «optimismo» no es uniforme. Se reporta la tabla completa y
```

y sustitúyelo por:

```markdown
derivación es más extrema que la validación en k = 0, 2, 3 y 5 y menos en
k = 1 y 4: el «optimismo» no es uniforme. Se reporta la tabla completa y
```

Se comprueba con esta cuenta (más extrema: más lejos de 1, o sea, mayor
valor absoluto del logaritmo):

```bash
C:/venv-copiloto/Scripts/python.exe -c "import math; d=[0.12,0.20,0.70,1.64,7.18,17.5]; v=[0.19,0.19,1.04,1.04,8.33,8.33]; print([k for k in range(6) if abs(math.log(d[k])) < abs(math.log(v[k]))])"
```

Esperado: `[1, 4]`.

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
git commit -m "docs(sp5): el umbral de 3,3 % del §5.3 sale de la via de dos puntuaciones (SP5-B1 T9)" -m "Con una sola puntuacion el cruce doble de 20 y 70 % exigiria una prevalencia bajo 1,4 %; el 3,3 % es el del asma no_se con puntuacion [4, 5]. Y en el 4.4 la derivacion es menos extrema que la validacion en k = 1 y 4, no solo en k = 4." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

#### Grupo 5 — Lo que pidió la revisión de la tarea

La revisión de la tarea encontró que dos de las reglas de arriba dejaban abierto
el caso que su letra quería cerrar, y el acta se envía al médico:

- **letra (a):** cada extremo de la horquilla se corregía hacia un solo lado. Con
  los DOS extremos bajo 0,01 el bot imprime un solo «< 1 %» y el acta admitía el 1
  del médico. Los dos extremos pasan ahora por una sola regla, la de Desenlace
  (`_entero_como_el_bot`), y `_pct_como_el_bot` la usa también;
- **letra (b):** con 24 casos un kappa puede valer EXACTAMENTE 0,4 o 0,6, y la coma
  flotante lo deja un ulp por debajo: el acta escribía «(0,400000) no alcanza el
  mínimo de 0,4». Se compara a seis decimales (`_a_seis`), que es lo más que se
  imprime: lo que a seis decimales es el umbral, es el umbral.

Y cinco menores: una prueba de la fecha que cambia la zona (la de arriba no
detecta nada en una máquina que ya está en UTC−5); una sola explicación del 3,3 %
en el spec; «todos por esta vía», afirmado por una prueba; el docstring de
`sha256_de`; y las ramas que seguían sin prueba.

- [ ] **Paso 20: Las pruebas, que fallan**

Aplica las sustituciones de los cuatro ficheros de pruebas (abajo) y corre:

```bash
C:/venv-copiloto/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_concordancia.py tests/test_sesion.py tests/test_generador.py tests/test_categoria.py
```

Esperado: `9 failed, 102 passed`, las nueve en `tests/test_concordancia.py`. Las
pruebas nuevas de la fecha, del rechazo sin bots, del generador y de la categoría
pasan ya: fijan lo que el código ya hacía.

- [ ] **Paso 21: El código, `datos.py` y el spec**

Aplica las demás sustituciones y corre la misma orden. Esperado: `111 passed`.
Después, la suite afectada entera (la orden del paso 18, más
`tests/test_categoria.py`): `145 passed`, y `node tests/formulario.mjs` en `16 OK`.

- [ ] **Paso 22: Commit**

```bash
git add tests/test_concordancia.py tests/test_sesion.py tests/test_generador.py tests/test_categoria.py src/copiloto_triaje/validacion/concordancia.py src/copiloto_triaje/validacion/datos.py docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md
git commit -m "fix(validacion): el acta lee la horquilla como la imprime el bot, y un kappa que es el umbral lo alcanza" -m "Los dos extremos de la horquilla pasan por la misma regla que Desenlace: con los dos bajo el 1 % el bot imprime un solo valor y el acta ya no admite el 1. El kappa se compara con 0,4 y 0,6 a seis decimales: con 24 casos puede valer exactamente el umbral y la coma flotante lo dejaba un ulp por debajo. El spec da una sola explicacion del 3,3 %." -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

**Las sustituciones.** Cada sustitución da el texto exacto a buscar (aparece UNA vez) y el que lo
sustituye. Primero las de las pruebas (y verlas fallar), después las demás.

**Las pruebas del acta: `tests/test_concordancia.py`**

**1. Busca**

````python
    (0.0060, 0.3000, 0, True),      # 0,0060 se imprime «< 1 %»: el límite inferior es 0
    (0.0100, 0.3000, 0, False),     # 0,01 exacto se imprime «1 %»
])
def test_dentro_de_la_horquilla_compara_enteros_como_los_imprime_el_bot(minima, maxima, pct, dentro):
    r = cc.acuerdo_continuo([pct, 50], [0.5, 0.5], minima=[minima, 0.4], maxima=[maxima, 0.6])
    assert r["fraccion_dentro_de_la_horquilla"] == pytest.approx(0.5 + 0.5 * dentro)
    assert r["horquillas_de_anchura_cero"] == int(cc.porcentaje_entero(minima) == cc.porcentaje_entero(maxima))
````

y sustitúyelo por

````python
    (0.0060, 0.3000, 0, True),      # 0,0060 se imprime «< 1 %»: el límite inferior es 0
    (0.0100, 0.3000, 0, False),     # 0,01 exacto se imprime «1 %»
    # los DOS extremos bajo 0,01: el bot imprime un solo «< 1 %», que no admite el 1
    (0.0030, 0.0080, 0, True),
    (0.0030, 0.0080, 1, False),
    (0.0070, 0.0070, 0, True),      # un discordante: «< 1 %», y es de un solo valor
    (0.0070, 0.0070, 1, False),
    # y los dos sobre 0,99: un solo «> 99 %», que no admite el 99
    (0.9920, 0.9980, 100, True),
    (0.9920, 0.9980, 99, False),
])
def test_dentro_de_la_horquilla_compara_enteros_como_los_imprime_el_bot(minima, maxima, pct, dentro):
    r = cc.acuerdo_continuo([pct, 50], [0.5, 0.5], minima=[minima, 0.4], maxima=[maxima, 0.6])
    assert r["fraccion_dentro_de_la_horquilla"] == pytest.approx(0.5 + 0.5 * dentro)
    # «de un solo valor» es lo que el bot imprime como un solo valor
    un_solo_valor = cc._pct_como_el_bot(minima) == cc._pct_como_el_bot(maxima)
    assert r["horquillas_de_anchura_cero"] == int(un_solo_valor)
    assert cc._horquilla_como_el_bot(minima, maxima).count("%") == (1 if un_solo_valor else 2)


def test_un_extremo_de_la_horquilla_es_un_entero_con_la_regla_del_bot():
    casos = [(0.0, 0, "< 1 %"), (0.0099, 0, "< 1 %"), (0.01, 1, "1 %"), (0.0149, 1, "1 %"),
             (0.4406, 44, "44 %"), (0.984, 98, "98 %"), (0.985, 99, "99 %"), (0.99, 99, "99 %"),
             (0.9901, 100, "> 99 %"), (0.995, 100, "> 99 %"), (1.0, 100, "> 99 %")]
    for x, entero, impreso in casos:
        assert cc._entero_como_el_bot(x) == entero, x
        assert cc._pct_como_el_bot(x) == impreso, x
    # de 0,01 a 0,99 el entero nunca es 0 ni 100: las cotas no se confunden
    for x in np.linspace(0.01, 0.99, 981):
        assert 1 <= cc._entero_como_el_bot(float(x)) <= 99


def test_un_kappa_que_es_exactamente_un_umbral_lo_alcanza(tmp_path):
    """Con 24 casos el kappa es un racional. Esta tabla da 0,4 exacto
    (1 − 24·7/280), y la coma flotante lo deja un ulp por debajo."""
    tabla = {("baja", "baja"): 13, ("baja", "intermedia"): 3, ("intermedia", "baja"): 2,
             ("intermedia", "intermedia"): 5, ("alta", "baja"): 1}
    a = [fila for (fila, _), n in tabla.items() for _ in range(n)]
    b = [columna for (_, columna), n in tabla.items() for _ in range(n)]
    assert len(a) == 24
    k = cc.kappa_con_intervalos(a, b, tipo="lineal")
    assert k["kappa"] == pytest.approx(0.4, abs=1e-12)
    assert k["kappa"] != 0.4, "si algun dia sale 0,4 exacto, esta prueba no prueba nada"
    k["frente_a_umbrales"] = cc.frente_a_umbrales(k)
    assert k["frente_a_umbrales"]["puntual_ge_0_4"] is True
    assert k["frente_a_umbrales"]["puntual_ge_0_6"] is False
    frase = cc._criterio("El kappa ponderado", k)
    assert frase.startswith("El kappa ponderado (0,40) alcanza el mínimo de 0,4 de la Semana 1 "
                            "y no el objetivo de 0,6;")
    assert "0,400000" not in frase and "0,399" not in frase

    def con(kappa, li_a=0.1, li_b=0.1):
        r = {"kappa": kappa, "ic95": [li_a, 1.0], "ic95_bca": [li_b, 1.0]}
        r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
        return r
    un_ulp = 0.3999999999999999
    assert con(un_ulp)["frente_a_umbrales"]["puntual_ge_0_4"] is True
    assert con(0.5999999999999999)["frente_a_umbrales"]["puntual_ge_0_6"] is True
    assert cc._criterio("K", con(0.5999999999999999)).startswith(
        "K (0,60) alcanza el mínimo de 0,4 de la Semana 1 y el objetivo de 0,6;")
    # lo mismo en los limites inferiores: un limite que es el umbral no queda por debajo
    u = con(0.7, li_a=un_ulp, li_b=0.39)["frente_a_umbrales"]
    assert (u["li_analitico_lt_0_4"], u["li_bca_lt_0_4"]) == (False, True)
    assert "con el BCa (0,39) y no con el método analítico (0,40)" in cc._criterio(
        "K", con(0.7, li_a=un_ulp, li_b=0.39))
    # y lo que a seis decimales NO es el umbral sigue sin alcanzarlo, y se ve
    assert con(0.399999)["frente_a_umbrales"]["puntual_ge_0_4"] is False
    assert cc._criterio("K", con(0.399999)).startswith("K (0,399999) no alcanza el mínimo")
````

**2. Busca**

````python
    assert cc._f_frente_a_umbral(-0.12) == "-0,12"
    assert cc._f_frente_a_umbral(float("nan")) == "—"
````

y sustitúyelo por

````python
    assert cc._f_frente_a_umbral(-0.12) == "-0,12"
    assert cc._f_frente_a_umbral(float("nan")) == "—"
    assert cc._f_frente_a_umbral(None) == "—"
    # hasta seis decimales, los que hagan falta para que no se lea el umbral
    assert cc._f_frente_a_umbral(0.39996) == "0,39996"
    assert cc._f_frente_a_umbral(0.399996) == "0,399996"
    assert cc._f_frente_a_umbral(0.600004) == "0,600004"
    # y lo que a seis decimales es el umbral, se imprime como el umbral
    assert cc._f_frente_a_umbral(0.3999999999999999) == "0,40"
    assert cc._f_frente_a_umbral(0.4000000004) == "0,40"
    assert cc._f_frente_a_umbral(0.6000000000000001) == "0,60"
````

**3. Busca**

````python
    assert cc._fecha(ms(2026, 10, 7, 4, 59, 59)) == "2026-10-06"     # las 23:59:59 del 6 en UTC−5
    assert cc._fecha(ms(2026, 10, 7, 5, 0, 0)) == "2026-10-07"       # las 00:00:00 del 7
    assert cc._fecha(None) == "—" and cc._fecha(0) == "—"
````

y sustitúyelo por

````python
    assert cc._fecha(ms(2026, 10, 7, 4, 59, 59)) == "2026-10-06"     # las 23:59:59 del 6 en UTC−5
    assert cc._fecha(ms(2026, 10, 7, 5, 0, 0)) == "2026-10-07"       # las 00:00:00 del 7
    assert cc._fecha(None) == "—" and cc._fecha(0) == "—"


def test_la_fecha_sale_de_la_zona_de_la_sesion_y_de_ninguna_otra(monkeypatch):
    """En una maquina que ya esta en UTC−5 la prueba de arriba pasaria tambien
    con la hora local: aqui se cambia la zona y el dia tiene que cambiar."""
    import datetime
    instante = int(datetime.datetime(2026, 10, 7, 4, 59, 59,
                                     tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert cc._fecha(instante) == "2026-10-06"
    monkeypatch.setattr(cc, "ZONA_DE_LA_SESION",
                        datetime.timezone(datetime.timedelta(hours=9)))
    assert cc._fecha(instante) == "2026-10-07"
    monkeypatch.setattr(cc, "ZONA_DE_LA_SESION",
                        datetime.timezone(datetime.timedelta(hours=-12)))
    assert cc._fecha(instante) == "2026-10-06"
    assert cc._fecha(instante + 8 * 3600 * 1000) == "2026-10-07"
````

**Las pruebas de la preparación: `tests/test_sesion.py`**

**1. Busca**

````python
    with pytest.raises(SystemExit, match="--imagen-digest"):
        preparar.fase_mensajes(salida, imagen_tag="h7-sesion")
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
````

y sustitúyelo por

````python
    with pytest.raises(SystemExit, match="--imagen-digest") as rechazo:
        preparar.fase_mensajes(salida, imagen_tag="h7-sesion")
    assert "los mensajes no se generaron con bots" in str(rechazo.value)
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
````

**Las pruebas del generador: `tests/test_generador.py`**

**1. Busca**

````python
    with pytest.raises(ValueError, match="asma"):
        generador.sortear_caso(m, 0, np.random.default_rng(1), asma=asma)
````

y sustitúyelo por

````python
    rng = np.random.default_rng(1)
    antes = rng.bit_generator.state
    with pytest.raises(ValueError, match="asma"):
        generador.sortear_caso(m, 0, rng, asma=asma)
    # se rechaza ANTES de sortear nada: si consumiera el generador, los casos
    # siguientes de la sesion serian otros
    assert rng.bit_generator.state == antes
````

**Las pruebas de la categoría: `tests/test_categoria.py`**

**1. Busca**

````python
def _cruces_dobles(prevalencia):
    cruces = 0
    for rv in np.geomspace(0.016, 77.3, 400):
        for h in _hallazgos():
            b = combinacion(prevalencia, h, float(rv))
            if (categoria.porcentaje_entero(b["minima"]) < 20
                    and categoria.porcentaje_entero(b["maxima"]) > 70):
                cruces += 1
    return cruces
````

y sustitúyelo por

````python
def _los_cruces_dobles(prevalencia):
    """(hallazgos, bloque) de cada horquilla que cruza el 20 y el 70 % a la vez."""
    cruces = []
    for rv in np.geomspace(0.016, 77.3, 400):
        for h in _hallazgos():
            b = combinacion(prevalencia, h, float(rv))
            if (categoria.porcentaje_entero(b["minima"]) < 20
                    and categoria.porcentaje_entero(b["maxima"]) > 70):
                cruces.append((h, b))
    return cruces


def _cruces_dobles(prevalencia):
    return len(_los_cruces_dobles(prevalencia))
````

**2. Busca**

````python
    """Con 0,032 cruza por la vía del asma `no_se` con puntuación [4, 5]."""
    assert _cruces_dobles(prevalencia) > 0
````

y sustitúyelo por

````python
    """Con 0,032 cruza por la vía del asma `no_se` con puntuación [4, 5]."""
    assert _cruces_dobles(prevalencia) > 0


def test_con_0_032_todos_los_cruces_dobles_son_de_la_via_de_dos_puntuaciones():
    """Spec §5.3: entre ≈ 1,4 % y ≈ 3,3 % solo cruza el asma `no_se` con los
    otros cuatro hallazgos presentes, que da las dos puntuaciones [4, 5]."""
    cruces = _los_cruces_dobles(0.032)
    assert cruces
    for hallazgos, bloque in cruces:
        assert hallazgos["asma"] == "no_se"
        assert list(bloque["puntuacion"]) == [4, 5]
    # y por debajo del 1,4 % tambien cruza una sola puntuacion, la de 5 puntos
    una = [b for _, b in _los_cruces_dobles(0.012) if len(b["puntuacion"]) == 1]
    assert una and all(list(b["puntuacion"]) == [5] for b in una)
    assert not [b for _, b in _los_cruces_dobles(0.016) if len(b["puntuacion"]) == 1]
````

**El acta: `src/copiloto_triaje/validacion/concordancia.py`**

**1. Busca**

````python
def acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict:
    """Spearman entre el porcentaje del medico y el punto medio del sistema;
    Bland-Altman en log-odds con 0 y 100 acotados a 0,5 y 99,5; y la fraccion
    de porcentajes que caen dentro de la horquilla.

    «Dentro» compara el porcentaje entero del medico, SIN acotar, con la
    horquilla tal como la imprime el bot: `porcentaje_entero` de la minima y
    de la maxima (Math.round en Desenlace), salvo en las cotas: una minima
    por debajo de 0,01 se imprime «< 1 %» y su limite es 0, y una maxima por
    encima de 0,99 se imprime «> 99 %» y su limite es 100. Una horquilla de
    un solo valor (los discordantes con el asma conocida) solo admite ese
    entero, y se cuentan aparte para que el acta lo diga."""
````

y sustitúyelo por

````python
def _entero_como_el_bot(x: float) -> int:
    """Un extremo de la horquilla como el ENTERO que el medico puede contestar,
    con la convencion de Desenlace: por debajo de 0,01 el bot imprime «< 1 %»
    y el entero es 0; por encima de 0,99 imprime «> 99 %» y es 100; si no,
    `porcentaje_entero` (Math.round), que da de 1 a 99."""
    if x < 0.01:
        return 0
    if x > 0.99:
        return 100
    return porcentaje_entero(x)


def acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict:
    """Spearman entre el porcentaje del medico y el punto medio del sistema;
    Bland-Altman en log-odds con 0 y 100 acotados a 0,5 y 99,5; y la fraccion
    de porcentajes que caen dentro de la horquilla.

    «Dentro» compara el porcentaje entero del medico, SIN acotar, con la
    horquilla tal como la imprime el bot: los DOS extremos pasan por
    `_entero_como_el_bot`. Un extremo por debajo de 0,01 se imprime «< 1 %» y
    vale 0; uno por encima de 0,99 se imprime «> 99 %» y vale 100. Si los dos
    extremos dan el mismo entero el bot imprime un solo valor (los
    discordantes con el asma conocida, y cualquier horquilla entera bajo el
    1 % o sobre el 99 %): solo admite ese entero, y se cuentan aparte para
    que el acta lo diga."""
````

**2. Busca**

````python
        lo = np.array([0 if x < 0.01 else porcentaje_entero(x) for x in minima], dtype=int)
        hi = np.array([100 if x > 0.99 else porcentaje_entero(x) for x in maxima], dtype=int)
````

y sustitúyelo por

````python
        lo = np.array([_entero_como_el_bot(x) for x in minima], dtype=int)
        hi = np.array([_entero_como_el_bot(x) for x in maxima], dtype=int)
````

**3. Busca**

````python
    """Un extremo de la horquilla como lo imprime Desenlace: entero con
    Math.round (`porcentaje_entero`), y nunca 0 % ni 100 %."""
    if x < 0.01:
        return "< 1 %"
    if x > 0.99:
        return "> 99 %"
    return f"{porcentaje_entero(x)} %"
````

y sustitúyelo por

````python
    """Un extremo de la horquilla como lo imprime Desenlace: entero con
    Math.round (`porcentaje_entero`), y nunca 0 % ni 100 %. Las cotas son las
    de `_entero_como_el_bot`: estan escritas una sola vez."""
    entero = _entero_como_el_bot(x)
    return {0: "< 1 %", 100: "> 99 %"}.get(entero, f"{entero} %")
````

**4. Busca**

````python
    """El kappa frente al 0,4 de la Semana 1 y el 0,6 (spec §5.5, §11.4):
    la estimacion puntual y el limite inferior de cada intervalo. None si el
    kappa no es calculable."""
    if k["kappa"] is None or math.isnan(k["kappa"]):
        return None
    return {"puntual_ge_0_4": bool(k["kappa"] >= 0.4), "puntual_ge_0_6": bool(k["kappa"] >= 0.6),
            "li_analitico_lt_0_4": bool(k["ic95"][0] < 0.4),
            "li_bca_lt_0_4": bool(k["ic95_bca"][0] < 0.4)}
````

y sustitúyelo por

````python
    """El kappa frente al 0,4 de la Semana 1 y el 0,6 (spec §5.5, §11.4):
    la estimacion puntual y el limite inferior de cada intervalo. None si el
    kappa no es calculable.

    Se compara a seis decimales (`_a_seis`): con 24 casos un kappa es un
    racional que puede valer EXACTAMENTE 0,4 o 0,6, y la coma flotante lo
    deja en 0,3999999999999999. Eso alcanza el umbral."""
    if k["kappa"] is None or math.isnan(k["kappa"]):
        return None
    return {"puntual_ge_0_4": bool(_a_seis(k["kappa"]) >= 0.4),
            "puntual_ge_0_6": bool(_a_seis(k["kappa"]) >= 0.6),
            "li_analitico_lt_0_4": bool(_a_seis(k["ic95"][0]) < 0.4),
            "li_bca_lt_0_4": bool(_a_seis(k["ic95_bca"][0]) < 0.4)}
````

**5. Busca**

````python
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
````

y sustitúyelo por

````python
UMBRALES_KAPPA = (0.4, 0.6)
_DECIMALES_MAXIMOS = 6


def _a_seis(x: float) -> float:
    """Un kappa a seis decimales, que es con lo que se compara con los
    umbrales y lo mas que se imprime: lo que a seis decimales es el umbral, es
    el umbral."""
    return round(x, _DECIMALES_MAXIMOS)


def _f_frente_a_umbral(x) -> str:
    """Un kappa, o un limite de su intervalo, para la frase que lo compara
    con 0,4 y 0,6. Si los dos decimales de siempre dieran justo un umbral sin
    que el valor lo sea (0,3996 → «0,40»), la frase se contradiria; entonces
    se imprime con tres decimales, y con los que hagan falta (hasta seis) si
    tres aun dan el umbral. Un valor que a seis decimales ES el umbral se
    imprime como el umbral, y `frente_a_umbrales` lo trata igual."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return _f(x)
    for umbral in UMBRALES_KAPPA:
        if _a_seis(x) != umbral and round(x, 2) == umbral:
````

**Los datos: `src/copiloto_triaje/validacion/datos.py`**

**1. Busca**

````python
def sha256_de(ruta) -> str:
    h = hashlib.sha256()
````

y sustitúyelo por

````python
def sha256_de(ruta) -> str:
    """El sha256 de los BYTES de un fichero, tal como estan: sin normalizar
    finales de linea. Es el de los ficheros que NO se versionan y que el acta
    cita (`mensajes.json`, `clave.json`): quien los guarda comprueba esos
    bytes. Para un insumo versionado, `huella_de_texto`."""
    h = hashlib.sha256()
````

**El spec: `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`**

**1. Busca**

````markdown
dos previos, 27-sep); tiene explicación analítica —el cociente de odds de los
dos extremos vale `min(RV_clínica, RV_imagen) ≤ 17,5`, y cruzar 20 y 70 % a
la vez exige además `odds_previas × max(RV_clínica, RV_imagen) < 0,25`, lo que
solo ocurre con prevalencia declarada por debajo de ≈ 3,3 %— y una prueba lo
afirma con los dos previos y con el umbral analítico (§8). Como
````

y sustitúyelo por

````markdown
dos previos, 27-sep); tiene explicación analítica —solo ocurre con una
prevalencia declarada por debajo de ≈ 3,3 %; la cuenta está al final de este
apartado— y una prueba lo afirma con los dos previos y con el umbral
analítico (§8). Como
````

**2. Busca**

````markdown
extremos mayor que ≈ 9,33. Con una sola puntuación ese cociente es
`min(RV_clínica, RV_imagen)`, la única RV clínica que pasa de 9,33 es la de 5
````

y sustitúyelo por

````markdown
extremos mayor que ≈ 9,33. Con una sola puntuación y las dos RV a favor ese
cociente es `min(RV_clínica, RV_imagen)` (con las dos en contra no pasa de
8,33, y en los casos discordantes la horquilla es un punto); la única RV
clínica que pasa de 9,33 es la de 5
````

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
