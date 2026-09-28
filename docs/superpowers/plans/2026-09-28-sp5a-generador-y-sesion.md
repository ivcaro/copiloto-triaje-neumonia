# SP5-A — Generador, oráculo, 0A y la sesión con el médico: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos
> usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** dejar listo, antes del 5-oct, todo lo que la sesión con el
médico necesita y la comprobación 0A que la Semana 1 prometió: el generador
de clínica semisintética por puntuación de Heckerling, su oráculo en forma
cerrada, la prueba determinista caso a caso, la categoría del sistema, la
entrada `--casos` del arnés, el script que prepara la sesión, el formulario
que la mide y el script que la analiza.

**Arquitectura:** un paquete nuevo `copiloto_triaje.validacion` con módulos
pequeños y puros (`datos`, `oraculo`, `generador`, `categoria`, `sesion`,
`concordancia`), que llaman a `heckerling.combinacion` / `combinar` y a
`calibracion.Calibrador` —nunca a una reimplementación—; dos scripts
(`preparar_sesion.py`, `analizar_sesion.py`) que solo leen y escriben
ficheros; un formulario HTML local cuya lógica vive en un `.js` sin DOM que
`node` prueba; y una entrada `--casos` en `pruebas/reproducir_casos.py` para
que los mensajes de la sesión los redacten los nodos reales. Todo lo que es
resultado de simulación vive en `docs/validacion-semisintetica/`; todo lo de
la sesión (placas, mensajes, CSV del médico) vive en `pruebas/sesion/`,
ignorado por git.

**Pila:** Python 3.12 (intérprete `C:/venv-copiloto/Scripts/python.exe`),
numpy, pandas, **scipy** (`ndtr`, `ndtri`, `rankdata`; ya está instalado como
dependencia de scikit-learn y este plan lo declara en `pyproject.toml`),
pytest; `node` para `pruebas/redactar.mjs` y para las pruebas `.mjs`. Las
pruebas se corren con `C:/venv-copiloto/Scripts/python.exe -m pytest` desde la
raíz del repo.

**Spec:** `docs/superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md`
(commit `b0ff8ee` o posterior) — léelo entero antes de la primera tarea. El
plan argumenta desde él; en cualquier contradicción manda el spec, salvo en lo
que la sección «Decisiones del plan» fija porque el spec lo dejaba abierto.
Este plan cubre §4.1-§4.5 (generador y oráculo), 0A de §4.4, §5.1-§5.8 y las
pruebas correspondientes de §8. **No cubre** la rejilla con bootstrap y las
métricas de §4.6, 0B/0C, la anonimización de §6.1 ni los documentos de §6.7:
son los planes SP5-B y SP5-C.

## Restricciones globales

Copiadas del spec de SP5 y de lo que SP4 dejó en vigor. **Los requisitos de
cada tarea las incluyen.**

1. **La verdad del generador son los recuentos** de la derivación de
   Heckerling, por puntuación: con neumonía `1/11/28/42/37/15` sobre 134; sin
   neumonía `48/316/232/149/30/5` sobre 780 (SP4 §4). Se escriben una sola
   vez, en `oraculo.py`. El sistema sigue usando `RV_POR_PUNTUACION` de
   `heckerling.py` (0,12; 0,20; 0,70; 1,64; 7,18; 17,5): **nadie lo toca**.
2. **La combinación se calcula llamando a `heckerling.combinacion` y
   `heckerling.combinar`** —el código que sirve el contenedor—, nunca a una
   copia. Los cortes son estrictos y se aplican allí: 37,8 °C y 100 lpm exactos
   **no** puntúan.
3. **Reparto de puntos (spec §4.2):** el punto de «sin asma» con probabilidad
   0,9 cuando `1 ≤ k ≤ 4`; con `k = 0` el asma está presente y con `k = 5`,
   ausente; los puntos restantes en un subconjunto uniforme de los cuatro
   signos. Temperatura con una décima de resolución y pulso entero; con
   probabilidad 0,2 **exactamente** 37,9 °C / 101 lpm si el hallazgo está
   presente, y **exactamente** 37,8 °C / 100 lpm si está ausente. `no_se` en
   el 10 % de los casos, al azar e independiente de todo (MCAR).
4. **`z_1(q)` y `z_0(q)` se evalúan en el mismo `q` de cada placa** (spec
   §4.5): el oráculo es función de `(q, k)` y nunca de la etiqueta. Usar el
   rango de la placa dentro de su propia clase para las dos densidades es el
   error que invierte la conclusión, y una prueba lo caza.
5. **La prevalencia de la simulación es la del calibrador desplegado**
   (`servidor/calibrador.json` → `prevalencia`, 0,2215), leída, no tecleada.
   **La de la sesión es la desplegada**, `heckerling.PREVALENCIA_COHORTE`
   (0,1466), y el acta lo dice.
6. **Ni un nombre de persona, del cliente, de la empresa ni una ruta con el
   usuario de Windows** en nada de lo que se versiona. La raíz del dataset es
   la variable de entorno **`RSNA_RAIZ`, sin valor por defecto**. Nada de la
   sesión (placas, mensajes, CSV del médico, clave) se versiona:
   `pruebas/sesion/` va en `.gitignore`. Ningún secreto en el repositorio.
7. **Rótulo «simulación semisintética»** en el título o cabecera de todo
   artefacto de resultados, que vive bajo `docs/validacion-semisintetica/`. El
   código no lleva rótulo. `crudas_prueba.csv` no es simulación y su README lo
   dice.
8. **El kappa sale solo de la lectura 1** (24 casos sin copiloto). La lectura
   2 son los mismos 24 una sola vez: 20 con el mensaje y 4 controles sin
   mensaje, dos de «positivas claras» y dos de «negativas claras», uno
   concordante y uno discordante en cada uno.
9. **Los mensajes de la sesión los redactan los nodos reales** por
   `pruebas/redactar.mjs`; nada se escribe a mano. El arnés con bots lo corre
   una persona; este plan no toca ningún workflow ni el VPS.
10. **Los mensajes que lee un clínico van bien escritos**, con tildes y de
    usted (SP3/SP4). Las viñetas y el formulario también.
11. **Ninguna cifra del acta se teclea:** todas salen de `sesion.json`.

## Decisiones del plan

Lo que el spec dejaba abierto, decidido aquí para que las tareas no tengan
que decidirlo:

- **D1. Φ y Φ⁻¹** son `scipy.special.ndtr` y `scipy.special.ndtri`;
  `scipy>=1.13` entra en `pyproject.toml` (ya está en `C:\venv-copiloto`, 1.18).
- **D2. Dónde vive la sesión:** `pruebas/sesion/` (ignorado). Dentro:
  `casos.json` (entrada del arnés), `clave.json` (todo lo que el médico no
  ve), `formulario/` (HTML + JS + `datos_lectura1.js`, `datos_lectura2.js`,
  `datos_planb.js` + `placas/*.png`), `dosier_lectura1.md`,
  `dosier_lectura2.md`, `mensajes.json` (lo deja el arnés), `lectura1.csv`,
  `lectura2.csv` o `planb.csv` (los exporta el formulario). Al acta van solo
  los `patientId`, los estratos y las cifras.
- **D3. Dos fases en `preparar_sesion.py`:** `--fase elegir` (casos,
  viñetas, placas, lectura 1, clave provisional) y, tras correr el arnés con
  `--casos`, `--fase mensajes` (lee `mensajes.json`, comprueba que el bloque
  EXPLORADO de cada mensaje repite la viñeta y que la concordancia coincide
  con la prevista, y escribe la lectura 2, el plan B y la clave definitiva).
  La categoría del sistema que se usa en el kappa es la del bloque **del
  mensaje**, que es lo que el médico ve.
- **D4. El formulario** es un `index.html` que lee `?lectura=1|2|planb` y
  carga `datos_lectura<N>.js`; la lógica está en `formulario.js` (sin DOM) y
  la prueba `tests/formulario.mjs` la carga en `node`. El CSV se descarga con
  un botón al final; el estado se guarda en `localStorage` tras cada envío.
- **D5. El dosier** se genera en Markdown (uno por lectura); pasarlo a PDF con
  Word es un paso manual y opcional: no es instrumento de medida (spec §5.8).
- **D6. La mutación `>` → `>=`** no se puede parchear sin editar código: se
  simula moviendo el corte a 37,79 °C y a 99 lpm, que sobre la rejilla de
  décimas y de enteros equivale exactamente a `>=`.
- **D7. Uniforme fuera del corte:** cuando el sorteo no cae en el valor exacto
  del corte (probabilidad 0,2), el valor uniforme se toma de la rejilla **sin**
  ese valor, para que la fracción total en el corte sea exactamente 0,2, que
  es lo que dice el spec §8.
- **D8. Los 3 casos de práctica** salen de «positivas claras», «negativas
  claras» y «banda contradictoria» (uno de cada), fuera de los 24, y sus
  filas van al CSV marcadas `practica=true`; el análisis las descarta.
- **D9. `analizar_sesion.py`** hace el bootstrap BCa con 2 000 réplicas y
  semilla `20261013`, y el intervalo analítico con la fórmula de Fleiss,
  Cohen y Everitt (1969).
- **D10. Umbral de cribado:** `sesion.UMBRAL_CRIBADO = 0.4258` (el del
  despliegue, `/salud`); una prueba lo compara con
  `pruebas.seleccionar_casos.UMBRAL` para que no diverjan.

## Estructura de ficheros

| Fichero | Responsabilidad |
| :--- | :--- |
| `src/copiloto_triaje/validacion/__init__.py` | el paquete, con su docstring |
| `src/copiloto_triaje/validacion/datos.py` | crudas congeladas, calibrador desplegado, `(p_cal, q, rv)` |
| `src/copiloto_triaje/validacion/oraculo.py` | recuentos, `z_y` sobre todo `q`, umbrales, `P(k \| q, y)`, oráculo, correlación teórica |
| `src/copiloto_triaje/validacion/generador.py` | sorteo de `k`, reparto en hallazgos, números, `no_se`, `generar`, `sortear_caso` |
| `src/copiloto_triaje/validacion/categoria.py` | la categoría del sistema (§5.3) y sus variantes |
| `src/copiloto_triaje/validacion/sesion.py` | estratos, cuotas, viñetas, órdenes y controles (§5.1, §5.4) |
| `src/copiloto_triaje/validacion/concordancia.py` | kappas con sus dos intervalos, acuerdo continuo, tiempos pareados, análisis de la sesión |
| `scripts/preparar_sesion.py` | las dos fases de D3 |
| `scripts/analizar_sesion.py` | CSV → `sesion.json` → acta |
| `pruebas/formulario/index.html`, `pruebas/formulario/formulario.js` | el formulario y su lógica |
| `pruebas/reproducir_casos.py` | entrada `--casos`, botones y signos por caso, `mensajes.json` |
| `docs/validacion-semisintetica/README.md`, `crudas_prueba.csv`, `crudas_prueba.sha256` | insumos congelados |
| `docs/validacion-semisintetica/acta-h7-plantilla.md` | la plantilla del acta |
| `docs/sp5-sesion.md` | cómo se corre todo, de principio a fin |
| `tests/test_validacion_datos.py`, `test_oraculo.py`, `test_generador.py`, `test_validacion_0a.py`, `test_categoria.py`, `test_sesion.py`, `test_concordancia.py`, `test_reproducir_casos.py`, `tests/formulario.mjs` | las pruebas |

---

### Tarea 1: El paquete `validacion`, scipy, las crudas congeladas y los datos

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/__init__.py`
- Crear: `src/copiloto_triaje/validacion/datos.py`
- Crear: `docs/validacion-semisintetica/README.md`
- Crear: `docs/validacion-semisintetica/crudas_prueba.csv` (copia) y `crudas_prueba.sha256` (copia)
- Modificar: `pyproject.toml` (dependencias), `.gitignore`
- Prueba: `tests/test_validacion_datos.py`

**Interfaces:**
- Consume: `copiloto_triaje.servicio.calibracion.Calibrador` (`desde_json`, `calibrar`, `razon_de_verosimilitud`, `prevalencia`).
- Produce: `datos.cargar_crudas(ruta=CRUDAS_CONGELADAS) -> pandas.DataFrame`
  (columnas `patientId, edad, sexo, vista, etiqueta, cruda`, 3 811 filas);
  `datos.calibrador_desplegado(ruta=CALIBRADOR) -> Calibrador`;
  `datos.evidencia_imagen(crudas, calibrador) -> (p_cal, q, rv)` (tres
  `np.ndarray` de la misma longitud, `q = logit p_cal`); constantes `REPO`,
  `CARPETA`, `CRUDAS_CONGELADAS`, `HASH_CONGELADO`, `CALIBRADOR`;
  `datos.sha256_de(ruta) -> str`.

- [ ] **Paso 1: Declarar scipy y la carpeta de la sesión**

En `pyproject.toml`, dentro de `dependencies`, después de la línea
`"scikit-learn>=1.6",` añade:

```toml
    "scipy>=1.13",
```

Al final de `.gitignore` añade:

```gitignore

# La sesion con el medico (SP5 §5, D2 del plan SP5-A): placas de RSNA,
# mensajes reales, la clave del evaluador y los CSV del medico. Nada de esto
# se versiona; al acta van solo los patientId, los estratos y las cifras.
pruebas/sesion/
```

Comprueba que scipy ya está: `C:/venv-copiloto/Scripts/python.exe -c "import scipy; print(scipy.__version__)"`
Esperado: `1.18.1` (o superior).

- [ ] **Paso 2: Congelar las crudas**

Desde la raíz del repo (PowerShell o Git Bash):

```bash
mkdir -p docs/validacion-semisintetica
cp pruebas/crudas_prueba.csv docs/validacion-semisintetica/crudas_prueba.csv
cp pruebas/crudas_prueba.sha256 docs/validacion-semisintetica/crudas_prueba.sha256
```

Crea `docs/validacion-semisintetica/README.md`:

```markdown
# Validación semisintética de la combinación (SP5)

**Todo lo que hay en esta carpeta, salvo `crudas_prueba.csv`, es resultado
de una simulación semisintética** (spec de SP5, §4): las placas y sus
etiquetas son reales (conjunto de prueba de RSNA), la clínica se sortea con
la distribución publicada de la puntuación de Heckerling, y la dependencia
entre clínica e imagen es un supuesto declarado. Nada de aquí mide exactitud
clínica en pacientes. Cada tabla, figura y JSON lleva ese rótulo en su
título.

## `crudas_prueba.csv` y `crudas_prueba.sha256`

No son simulación: son las **puntuaciones crudas del modelo desplegado**
sobre las 3 811 placas del conjunto de prueba (una por paciente), con la
edad, el sexo, la proyección y la etiqueta real de opacidad de RSNA. Es una
copia congelada de la caché de `pruebas/puntuaciones.py`; el `.sha256` es el
hash de los pesos con los que se generó. Con esta copia, un tercero
reproduce todos los números de la simulación **sin los pesos**. Si el modelo
se reentrena, se regenera la caché y se vuelve a congelar aquí.

Los identificadores son los públicos de RSNA (`patientId`); no hay ningún
dato de persona.
```

- [ ] **Paso 3: Escribir la prueba que falla**

`tests/test_validacion_datos.py`:

```python
"""Los insumos congelados de la simulación semisintética (spec SP5 §4.1, §4.8).

Ninguno es simulación: son las puntuaciones reales del modelo desplegado
sobre las placas reales de prueba, y el calibrador que sirve el contenedor.
"""
import re

import numpy as np
import pytest

from copiloto_triaje.validacion import datos


def test_las_crudas_congeladas_son_las_3811_placas_de_prueba():
    df = datos.cargar_crudas()
    assert len(df) == 3811
    assert df["patientId"].is_unique
    assert int(df["etiqueta"].sum()) == 844
    assert set(df["vista"].unique()) == {"AP", "PA"}
    assert set(df["sexo"].unique()) == {"F", "M"}
    assert df["cruda"].between(0.0, 1.0).all()


def test_el_hash_congelado_es_un_sha256_y_coincide_con_la_cache_si_existe():
    texto = datos.HASH_CONGELADO.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"[0-9a-f]{64}", texto)
    cache = datos.REPO / "pruebas" / "crudas_prueba.sha256"
    if cache.is_file():
        assert cache.read_text(encoding="utf-8").strip() == texto


def test_la_evidencia_de_imagen_usa_la_prevalencia_del_calibrador():
    """p_cal ⇔ prevalencia × RV: es la misma cadena que `heckerling.combinar`
    recorre, y por eso el previo de la simulación es el del calibrador."""
    cal = datos.calibrador_desplegado()
    df = datos.cargar_crudas()
    p, q, rv = datos.evidencia_imagen(df["cruda"].values[:200], cal)
    odds_previas = cal.prevalencia / (1 - cal.prevalencia)
    assert np.allclose(np.exp(q), odds_previas * rv)
    assert np.allclose(p, 1 / (1 + np.exp(-q)))
    assert cal.prevalencia == pytest.approx(844 / 3811, abs=5e-5)


def test_cargar_rechaza_pacientes_repetidos_y_columnas_que_faltan(tmp_path):
    df = datos.cargar_crudas().head(3)
    repetidos = tmp_path / "repetidos.csv"
    df.iloc[[0, 0, 1]].to_csv(repetidos, index=False)
    with pytest.raises(ValueError, match="repite pacientes"):
        datos.cargar_crudas(repetidos)
    sin_vista = tmp_path / "sin_vista.csv"
    df.drop(columns=["vista"]).to_csv(sin_vista, index=False)
    with pytest.raises(ValueError, match="faltan las columnas"):
        datos.cargar_crudas(sin_vista)
```

- [ ] **Paso 4: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validacion_datos.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'copiloto_triaje.validacion'`.

- [ ] **Paso 5: Escribir el paquete y `datos.py`**

`src/copiloto_triaje/validacion/__init__.py`:

```python
"""Validación semisintética de la combinación bayesiana y sesión con el médico (SP5).

Nada de este paquete toca el servidor ni los bots: lee las puntuaciones
congeladas del modelo, sortea clínica con la distribución publicada de la
puntuación de Heckerling, y compara lo que `heckerling.combinacion` calcula
con lo que el generador sabe. Los módulos son puros; los scripts de
`scripts/` son los únicos que leen y escriben ficheros de la sesión.
"""
```

`src/copiloto_triaje/validacion/datos.py`:

```python
# -*- coding: utf-8 -*-
"""Los datos de la simulación semisintética (spec de SP5 §4.1, §4.8).

Dos insumos, y ninguno es una simulación:

- `crudas_prueba.csv` CONGELADA en `docs/validacion-semisintetica/`: las
  puntuaciones crudas del modelo desplegado sobre las 3 811 placas del
  conjunto de prueba de RSNA, una por paciente, con su etiqueta real. Es una
  copia de la caché de `pruebas/puntuaciones.py`, con el sha256 de los pesos
  al lado, para que un tercero reproduzca todos los números SIN los pesos.
- `servidor/calibrador.json`: el MISMO calibrador que sirve el contenedor. Su
  `prevalencia` (0,2215) es el previo de la simulación (§4.3): se lee de ahí y
  no se teclea.
"""
from __future__ import annotations

import hashlib
import pathlib

import numpy as np
import pandas as pd

from copiloto_triaje.servicio.calibracion import Calibrador

REPO = pathlib.Path(__file__).resolve().parents[3]
CARPETA = REPO / "docs" / "validacion-semisintetica"
CRUDAS_CONGELADAS = CARPETA / "crudas_prueba.csv"
HASH_CONGELADO = CARPETA / "crudas_prueba.sha256"
CALIBRADOR = REPO / "servidor" / "calibrador.json"
COLUMNAS = ("patientId", "edad", "sexo", "vista", "etiqueta", "cruda")


def sha256_de(ruta) -> str:
    h = hashlib.sha256()
    with pathlib.Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_crudas(ruta=CRUDAS_CONGELADAS) -> pd.DataFrame:
    """Las crudas congeladas, comprobadas: las seis columnas, una placa por
    paciente y etiquetas 0/1. Un fichero a medias se rechaza, no se lee."""
    df = pd.read_csv(ruta)
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"a {ruta} le faltan las columnas {faltan}")
    if df["patientId"].duplicated().any():
        raise ValueError(f"{ruta} repite pacientes: no es una placa por paciente")
    if not set(df["etiqueta"].unique()) <= {0, 1}:
        raise ValueError(f"{ruta} tiene etiquetas que no son 0/1")
    return df


def calibrador_desplegado(ruta=CALIBRADOR) -> Calibrador:
    return Calibrador.desde_json(ruta)


def evidencia_imagen(crudas, calibrador: Calibrador):
    """(p_cal, q, rv) por placa, con el mismo calibrador que sirve el contenedor.

    `q = logit p_cal` es lo que el oráculo toma como verdad de la imagen
    (§4.4); `rv` es lo que `heckerling.combinar` multiplica. Con la prevalencia
    del calibrador, `prevalencia × rv` son exactamente las odds de `p_cal`.
    """
    crudas = np.asarray(crudas, dtype=float)
    p = np.array([calibrador.calibrar(c) for c in crudas])
    rv = np.array([calibrador.razon_de_verosimilitud(c) for c in crudas])
    return p, np.log(p / (1.0 - p)), rv
```

- [ ] **Paso 6: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validacion_datos.py -v`
Esperado: 4 PASS.

- [ ] **Paso 7: Commit**

```bash
git add pyproject.toml .gitignore src/copiloto_triaje/validacion/__init__.py src/copiloto_triaje/validacion/datos.py docs/validacion-semisintetica/ tests/test_validacion_datos.py
git commit -m "feat(validacion): paquete, crudas congeladas y evidencia de imagen (SP5-A T1)"
```

---

### Tarea 2: El oráculo en forma cerrada

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/oraculo.py`
- Prueba: `tests/test_oraculo.py`

**Interfaces:**
- Consume: `datos.cargar_crudas`, `datos.calibrador_desplegado`, `datos.evidencia_imagen` (solo en las pruebas).
- Produce: `RECUENTOS`, `TOTALES`, `PUNTUACIONES`, `PROBABILIDAD_ASMA_PRESENTE`,
  `RHO_REJILLA`, `CELDAS_DESTACADAS`; `probabilidad_puntuacion(y) -> np.ndarray(6)`;
  `rv_recuentos(k) -> float`; `fda_rango_medio(q_clase, q) -> np.ndarray`;
  `puntuaciones_normales(q, etiquetas) -> (z1, z0)`;
  `umbrales(z_clase, rho, y) -> np.ndarray(5)`;
  `probabilidad_k_dado_q(z, rho, taus) -> np.ndarray(n, 6)`; `matriz_k4() -> np.ndarray(6, 5)`;
  `Modelo` (campos `rho1, rho0, etiquetas, z1, z0, tau1, tau0`; métodos
  `z_propia()`, `probabilidades() -> (p1, p0)`); `ajustar(q, etiquetas, rho1=0.0, rho0=0.0) -> Modelo`;
  `log_rv_condicional(modelo) -> np.ndarray(n, 6)`; `logit_oraculo(modelo, q, k) -> np.ndarray`;
  `logit_oraculo_no_se(modelo, q, k4) -> np.ndarray`; `correlacion_teorica(modelo, y) -> float`.

- [ ] **Paso 1: Escribir la prueba que falla**

`tests/test_oraculo.py`:

```python
"""El modelo de umbral latente y su oráculo (spec de SP5 §4.4-§4.5, §8).

Todo en forma cerrada: nada de aquí sortea. Los valores esperados de la
correlación son los que el spec §4.5 declara, medidos el 27-sep sobre las
crudas congeladas; si cambian las crudas, cambian ellos y hay que decirlo.
"""
import numpy as np
import pytest
from scipy.special import ndtri

from copiloto_triaje.validacion import datos, oraculo


@pytest.fixture(scope="module")
def prueba():
    df = datos.cargar_crudas()
    _, q, _ = datos.evidencia_imagen(df["cruda"].values, datos.calibrador_desplegado())
    return q, df["etiqueta"].values.astype(int)


def test_los_recuentos_son_los_de_sp4():
    assert sum(oraculo.RECUENTOS[1]) == oraculo.TOTALES[1] == 134
    assert sum(oraculo.RECUENTOS[0]) == oraculo.TOTALES[0] == 780
    assert round(oraculo.rv_recuentos(0), 2) == 0.12
    assert round(oraculo.rv_recuentos(3), 2) == 1.64
    assert round(oraculo.rv_recuentos(5), 1) == 17.5
    assert np.allclose(oraculo.probabilidad_puntuacion(1).sum(), 1.0)


def test_la_fda_de_rango_medio_esta_definida_sobre_todo_q():
    clase = np.array([1.0, 2.0, 2.0, 3.0])
    fda = oraculo.fda_rango_medio
    assert fda(clase, [1.0]) == pytest.approx(0.5 / 4)          # rango medio propio
    assert fda(clase, [2.0]) == pytest.approx((1 + 0.5 * 2) / 4)  # empate: 1 menor + ½·2 iguales
    assert fda(clase, [2.5]) == pytest.approx(3 / 4)            # fuera de la clase: cuenta menores
    assert fda(clase, [-5.0]) == pytest.approx(0.5 / 4)         # la cota inferior
    assert fda(clase, [99.0]) == pytest.approx(1 - 0.5 / 4)     # la cota superior


def test_z_de_una_placa_negativa_es_el_rango_que_tendria_entre_las_positivas(prueba):
    """Spec §8: z_1(q) de una negativa = Φ⁻¹ de su rango medio al insertarla entre las positivas."""
    q, y = prueba
    z1, z0 = oraculo.puntuaciones_normales(q, y)
    i = int(np.flatnonzero(y == 0)[10])
    positivas = np.sort(q[y == 1])
    menores = np.sum(positivas < q[i])
    iguales = np.sum(positivas == q[i])
    n = positivas.size
    esperado = ndtri(np.clip((menores + 0.5 * iguales) / n, 0.5 / n, 1 - 0.5 / n))
    assert z1[i] == pytest.approx(esperado)
    assert z1.shape == z0.shape == q.shape


def test_con_rho_cero_los_umbrales_son_los_cuantiles_de_los_recuentos(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.0, 0.0)
    for clase, tau in ((1, m.tau1), (0, m.tau0)):
        acumulada = np.cumsum(oraculo.probabilidad_puntuacion(clase))[:-1]
        assert np.allclose(tau, ndtri(acumulada), atol=1e-9)
        assert np.all(np.diff(tau) > 0)


def test_con_rho_cero_la_rv_condicional_es_la_de_los_recuentos_en_todo_q(prueba):
    q, y = prueba
    lrv = oraculo.log_rv_condicional(oraculo.ajustar(q, y))
    esperado = np.log([oraculo.rv_recuentos(k) for k in range(6)])
    assert np.allclose(lrv, esperado[None, :], atol=1e-9)
    k = np.full(q.size, 3)
    assert np.allclose(oraculo.logit_oraculo(oraculo.ajustar(q, y), q, k),
                       q + np.log(oraculo.rv_recuentos(3)))


@pytest.mark.parametrize("rho", [0.3, 0.6])
def test_la_forma_cerrada_conserva_p_k_dado_y_con_dependencia(prueba, rho):
    """Spec §4.5 y §8: la media sobre la clase de P(k | q_i, y) son los recuentos (±1e-9)."""
    q, y = prueba
    m = oraculo.ajustar(q, y, rho, rho)
    p1, p0 = m.probabilidades()
    assert np.allclose(p1[y == 1].mean(axis=0), oraculo.probabilidad_puntuacion(1), atol=1e-9)
    assert np.allclose(p0[y == 0].mean(axis=0), oraculo.probabilidad_puntuacion(0), atol=1e-9)
    assert np.allclose(p1.sum(axis=1), 1.0) and np.allclose(p0.sum(axis=1), 1.0)
    assert np.all(p1 > 0) and np.all(p0 > 0)


@pytest.mark.parametrize("rho, esperadas", [(0.3, (0.275, 0.286)), (0.6, (0.558, 0.574))])
def test_la_correlacion_teorica_reproduce_los_valores_del_spec(prueba, rho, esperadas):
    q, y = prueba
    m = oraculo.ajustar(q, y, rho, rho)
    assert oraculo.correlacion_teorica(m, 0) == pytest.approx(esperadas[0], abs=0.005)
    assert oraculo.correlacion_teorica(m, 1) == pytest.approx(esperadas[1], abs=0.005)
    assert oraculo.correlacion_teorica(oraculo.ajustar(q, y), 1) == pytest.approx(0.0, abs=1e-9)


def test_el_oraculo_de_no_se_marginaliza_el_asma_con_la_regla_de_reparto(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.0)
    p1, p0 = m.probabilidades()
    pa = oraculo.PROBABILIDAD_ASMA_PRESENTE
    # k4 = 3 viene de k = 3 con asma presente o de k = 4 con asma ausente
    s1 = p1[:, 3] * pa[3] + p1[:, 4] * (1 - pa[4])
    s0 = p0[:, 3] * pa[3] + p0[:, 4] * (1 - pa[4])
    k4 = np.full(q.size, 3)
    assert np.allclose(oraculo.logit_oraculo_no_se(m, q, k4), q + np.log(s1) - np.log(s0))
    matriz = oraculo.matriz_k4()
    assert matriz.shape == (6, 5) and np.allclose(matriz.sum(axis=1), 1.0)
    assert matriz[0, 0] == 1.0 and matriz[5, 4] == 1.0 and matriz[4, 3] == pytest.approx(0.9)


def test_la_trampa_del_rango_propio_invierte_la_conclusion(prueba):
    """Restricción 4: z_1 y z_0 en el MISMO q. Con el rango de la propia clase
    para las dos densidades, la fracción de log-RV conservada sale > 1 (la
    clínica «gana» información al ver la imagen), que es lo contrario de lo
    que el modelo simétrico produce. La prueba caza ese error."""
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    correcto = oraculo.log_rv_condicional(m)
    zp = m.z_propia()
    trampa = (np.log(oraculo.probabilidad_k_dado_q(zp, 0.3, m.tau1))
              - np.log(oraculo.probabilidad_k_dado_q(zp, 0.3, m.tau0)))
    ln_rv = np.log([oraculo.rv_recuentos(k) for k in range(6)])
    extremas = [0, 1, 4, 5]
    assert np.median(correcto[:, extremas] / ln_rv[extremas]) < 1.0
    assert np.median(trampa[:, extremas] / ln_rv[extremas]) > 1.0


def test_ajustar_rechaza_rho_fuera_de_rango(prueba):
    q, y = prueba
    with pytest.raises(ValueError):
        oraculo.ajustar(q, y, 1.0, 0.0)
    with pytest.raises(ValueError):
        oraculo.ajustar(q, y, 0.0, -0.1)
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_oraculo.py -v`
Esperado: FAIL con `ImportError: cannot import name 'oraculo'`.

- [ ] **Paso 3: Escribir `oraculo.py`**

```python
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
```

- [ ] **Paso 4: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_oraculo.py -v`
Esperado: 11 PASS (los parametrizados cuentan aparte). Tarda unos segundos:
la bisección hace 200 pasos por umbral.

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/validacion/oraculo.py tests/test_oraculo.py
git commit -m "feat(validacion): modelo de umbral latente y oraculo en forma cerrada (SP5-A T2)"
```

---

### Tarea 3: El generador

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/generador.py`
- Prueba: `tests/test_generador.py`

**Interfaces:**
- Consume: `oraculo.Modelo` (`etiquetas`, `rho1`, `rho0`, `tau1`, `tau0`, `z_propia()`), `oraculo.PROBABILIDAD_ASMA_PRESENTE`; `heckerling.puntuar` (solo en las pruebas).
- Produce: constantes `FRACCION_NO_SE = 0.10`, `FRACCION_EN_EL_CORTE = 0.20`,
  `SIGNOS = ("temperatura_c", "frecuencia_cardiaca", "crepitantes", "murmullo_disminuido")`,
  `COLUMNAS`; `sortear_puntuacion(modelo, rng) -> np.ndarray`;
  `repartir(k, rng) -> dict` (claves `k, k4, asma_real, temperatura_c, frecuencia_cardiaca, crepitantes, murmullo_disminuido`);
  `ocultar_asma(asma_real, rng) -> str`; `sortear_caso(modelo, indice, rng, asma=None) -> dict`
  (lo de `repartir` más `asma`, el estado declarado); `generar(modelo, semilla) -> pandas.DataFrame`
  (columnas `COLUMNAS`, una fila por placa en el orden del modelo);
  `hallazgos(fila) -> dict` (los cinco hallazgos con tipos de Python, listos para `heckerling.combinacion`).

- [ ] **Paso 1: Escribir la prueba que falla**

`tests/test_generador.py`:

```python
"""El generador de la simulación semisintética (spec de SP5 §4.2, §8).

Las comprobaciones empíricas agregan R = 50 sorteos por placa, como pide el
§8: con un solo sorteo las tolerancias caerían dentro del ruido de muestreo
y un generador correcto fallaría la mitad de las veces.
"""
import numpy as np
import pandas as pd
import pytest

from copiloto_triaje.servicio.heckerling import (
    PULSO_CORTE_LPM, TEMPERATURA_CORTE_C, puntuar,
)
from copiloto_triaje.validacion import datos, generador, oraculo

R = 50


@pytest.fixture(scope="module")
def prueba():
    df = datos.cargar_crudas()
    _, q, _ = datos.evidencia_imagen(df["cruda"].values, datos.calibrador_desplegado())
    return q, df["etiqueta"].values.astype(int)


def _sorteos(modelo):
    ks = np.concatenate([generador.sortear_puntuacion(modelo, np.random.default_rng(s))
                         for s in range(1, R + 1)])
    return ks, np.tile(modelo.etiquetas, R), np.tile(modelo.z_propia(), R)


@pytest.mark.parametrize("rho", [0.0, 0.6])
def test_p_k_dado_y_empirica_coincide_con_los_recuentos(prueba, rho):
    q, y = prueba
    ks, ys, _ = _sorteos(oraculo.ajustar(q, y, rho, rho))
    for clase in (0, 1):
        empirica = np.bincount(ks[ys == clase], minlength=6) / np.sum(ys == clase)
        assert np.allclose(empirica, oraculo.probabilidad_puntuacion(clase), atol=0.01)


@pytest.mark.parametrize("rho", [0.0, 0.3, 0.6])
def test_la_correlacion_empirica_dentro_de_cada_clase_es_la_teorica(prueba, rho):
    """Spec §8: Pearson entre k y z_y(q) dentro de la clase, contra la forma cerrada (±0,03)."""
    q, y = prueba
    m = oraculo.ajustar(q, y, rho, rho)
    ks, ys, z = _sorteos(m)
    for clase in (0, 1):
        r = np.corrcoef(ks[ys == clase], z[ys == clase])[0, 1]
        esperada = 0.0 if rho == 0.0 else oraculo.correlacion_teorica(m, clase)
        assert r == pytest.approx(esperada, abs=0.03)


def test_repartir_da_exactamente_k_puntos_y_respeta_el_asma():
    """La puntuación que `heckerling.puntuar` calcula sobre lo repartido es k,
    siempre; y el punto de «sin asma» sigue la regla del §4.2."""
    rng = np.random.default_rng(7)
    sin_asma = {k: [] for k in range(6)}
    for _ in range(6000):
        k = int(rng.integers(0, 6))
        h = generador.repartir(k, rng)
        assert puntuar({s: h[s] for s in generador.SIGNOS}, h["asma_real"]) == (k,)
        assert h["k4"] == k - (h["asma_real"] == "no")
        sin_asma[k].append(h["asma_real"] == "no")
    assert not any(sin_asma[0]) and all(sin_asma[5])
    for k in (1, 2, 3, 4):
        assert np.mean(sin_asma[k]) == pytest.approx(0.9, abs=0.03)
    with pytest.raises(ValueError):
        generador.repartir(6, rng)


def test_los_numeros_caen_en_su_rejilla_y_el_20_por_ciento_en_el_corte():
    """Spec §4.2 paso 3 y §8: décimas y enteros; 37,9 / 101 exactos si el
    hallazgo está presente y 37,8 / 100 exactos si está ausente, en el 20 %."""
    rng = np.random.default_rng(11)
    filas = [generador.repartir(int(rng.integers(0, 6)), rng) for _ in range(20000)]
    t = np.array([f["temperatura_c"] for f in filas])
    fc = np.array([f["frecuencia_cardiaca"] for f in filas])
    assert np.all(np.round(t, 1) == t)
    assert all(isinstance(f["frecuencia_cardiaca"], int) for f in filas)
    presentes_t = t > TEMPERATURA_CORTE_C
    assert t[~presentes_t].min() >= 36.0 and t[presentes_t].max() <= 39.5
    assert np.mean(t[presentes_t] == 37.9) == pytest.approx(0.2, abs=0.02)
    assert np.mean(t[~presentes_t] == TEMPERATURA_CORTE_C) == pytest.approx(0.2, abs=0.02)
    presentes_p = fc > PULSO_CORTE_LPM
    assert fc[~presentes_p].min() >= 60 and fc[presentes_p].max() <= 130
    assert np.mean(fc[presentes_p] == 101) == pytest.approx(0.2, abs=0.02)
    assert np.mean(fc[~presentes_p] == PULSO_CORTE_LPM) == pytest.approx(0.2, abs=0.02)


def test_no_se_es_el_10_por_ciento_e_independiente_de_la_etiqueta(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y)
    diferencias, fracciones = [], []
    for semilla in range(1, R + 1):
        df = generador.generar(m, semilla)
        no_se = (df["asma"] == "no_se").values
        fracciones.append(no_se.mean())
        diferencias.append(no_se[y == 1].mean() - no_se[y == 0].mean())
    assert np.mean(fracciones) == pytest.approx(generador.FRACCION_NO_SE, abs=0.01)
    assert abs(np.mean(diferencias)) < 0.01
    assert list(df.columns) == list(generador.COLUMNAS) and len(df) == y.size
    assert set(df["asma"]) <= {"si", "no", "no_se"} and set(df["asma_real"]) <= {"si", "no"}


def test_generar_es_reproducible_por_semilla(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.0)
    a, b = generador.generar(m, 5), generador.generar(m, 5)
    pd.testing.assert_frame_equal(a, b)
    assert not generador.generar(m, 6).equals(a)


def test_sortear_caso_fuerza_el_asma_declarada(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    caso = generador.sortear_caso(m, 0, np.random.default_rng(1), asma="no_se")
    assert caso["asma"] == "no_se" and caso["asma_real"] in ("si", "no")
    signos = {s: caso[s] for s in generador.SIGNOS}
    assert puntuar(signos, "no_se") == (caso["k4"], caso["k4"] + 1)
    libre = generador.sortear_caso(m, 0, np.random.default_rng(1))
    assert libre["asma"] == libre["asma_real"]


def test_hallazgos_lleva_tipos_de_python(prueba):
    """`heckerling.validar_hallazgos` rechaza `numpy.bool_`: los tipos son de Python."""
    q, y = prueba
    df = generador.generar(oraculo.ajustar(q, y), semilla=1)
    h = generador.hallazgos(df.iloc[0])
    assert set(h) == set(generador.SIGNOS) | {"asma"}
    assert type(h["crepitantes"]) is bool and type(h["murmullo_disminuido"]) is bool
    assert type(h["frecuencia_cardiaca"]) is int and type(h["temperatura_c"]) is float
    assert type(h["asma"]) is str
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_generador.py -v`
Esperado: FAIL con `ImportError: cannot import name 'generador'`.

- [ ] **Paso 3: Escribir `generador.py`**

```python
# -*- coding: utf-8 -*-
"""El generador de la simulación semisintética (spec de SP5 §4.2).

Por placa: (1) la puntuacion `k` sale del modelo de umbral latente de
`oraculo.py`, con la distribucion exacta de los recuentos de Heckerling;
(2) los `k` puntos se reparten en los cinco predictores con una regla
declarada que solo afecta a la redaccion de la viñeta y al oraculo de
`no_se`; (3) temperatura y pulso salen como numeros, con una decima y
enteros, y con probabilidad 0,2 EXACTAMENTE en el corte (ausente) o en el
valor inmediato superior (presente): asi un `>` cambiado por `>=`, o un
corte movido, cambia la puntuacion de una fraccion conocida de casos;
(4) el asma se oculta (`no_se`) en el 10 % de los casos, al azar.

Nada de esto inventa la exactitud de la regla: la RV de cada puntuacion es
la publicada. Lo unico que el generador decide es a que placa le toca que
puntuacion, y con que numeros se escribe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .oraculo import PROBABILIDAD_ASMA_PRESENTE, Modelo

FRACCION_NO_SE = 0.10          # asma oculta al azar (MCAR), §4.2 paso 4
FRACCION_EN_EL_CORTE = 0.20    # exactamente el corte / el inmediato superior
# Rejillas [a, b): temperatura en decimas de grado, pulso en lpm.
TEMPERATURA_PRESENTE = (379, 396)   # 37,9 … 39,5 °C
TEMPERATURA_AUSENTE = (360, 379)    # 36,0 … 37,8 °C
PULSO_PRESENTE = (101, 131)         # 101 … 130 lpm
PULSO_AUSENTE = (60, 101)           # 60 … 100 lpm
SIGNOS = ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
          "murmullo_disminuido")
COLUMNAS = ("k", "k4", "asma_real", "asma") + SIGNOS


def sortear_puntuacion(modelo: Modelo, rng: np.random.Generator) -> np.ndarray:
    """k_i = #{j : u_i > τ_{y,j}},  u_i = ρ_y z_y(q_i) + √(1 − ρ_y²) ε_i."""
    y = modelo.etiquetas
    rho = np.where(y == 1, modelo.rho1, modelo.rho0)
    u = rho * modelo.z_propia() + np.sqrt(1.0 - rho ** 2) * rng.standard_normal(y.size)
    tau = np.where((y == 1)[:, None], modelo.tau1[None, :], modelo.tau0[None, :])
    return (u[:, None] > tau).sum(axis=1)


def _valor(presente: bool, rejilla_presente, rejilla_ausente,
           rng: np.random.Generator) -> int:
    """Un valor de la rejilla: con probabilidad FRACCION_EN_EL_CORTE el borde
    (el inmediato superior al corte si esta presente; el corte exacto si esta
    ausente) y, si no, uniforme sobre el RESTO de la rejilla, para que la
    fraccion total en el borde sea exactamente la declarada (D7)."""
    a, b = rejilla_presente if presente else rejilla_ausente
    if rng.random() < FRACCION_EN_EL_CORTE:
        return a if presente else b - 1
    return int(rng.integers(a + 1, b)) if presente else int(rng.integers(a, b - 1))


def repartir(k: int, rng: np.random.Generator) -> dict:
    """Los k puntos en los cinco predictores, con temperatura y pulso como numeros."""
    if not 0 <= k <= 5:
        raise ValueError(f"la puntuación va de 0 a 5, y es {k!r}")
    # Con k = 0 nunca (P = 1,0 de asma presente), con k = 5 siempre, y entre
    # medias con probabilidad 0,9: la MISMA tabla que usa el oraculo de no_se.
    sin_asma = bool(rng.random() >= PROBABILIDAD_ASMA_PRESENTE[k])
    puntos = k - int(sin_asma)
    presentes = np.zeros(4, dtype=bool)
    presentes[rng.choice(4, size=puntos, replace=False)] = True
    return {
        "k": int(k),
        "k4": int(puntos),
        "asma_real": "no" if sin_asma else "si",
        "temperatura_c": _valor(bool(presentes[0]), TEMPERATURA_PRESENTE,
                                TEMPERATURA_AUSENTE, rng) / 10.0,
        "frecuencia_cardiaca": _valor(bool(presentes[1]), PULSO_PRESENTE,
                                      PULSO_AUSENTE, rng),
        "crepitantes": bool(presentes[2]),
        "murmullo_disminuido": bool(presentes[3]),
    }


def ocultar_asma(asma_real: str, rng: np.random.Generator) -> str:
    return "no_se" if rng.random() < FRACCION_NO_SE else asma_real


def sortear_caso(modelo: Modelo, indice: int, rng: np.random.Generator,
                 asma: str | None = None) -> dict:
    """La clinica de UNA placa, para la sesion (spec §5.1). `asma` fuerza el
    estado DECLARADO (`no_se` en el estrato del asma); el real sigue sorteado."""
    y = int(modelo.etiquetas[indice])
    rho, tau = (modelo.rho1, modelo.tau1) if y == 1 else (modelo.rho0, modelo.tau0)
    u = rho * float(modelo.z_propia()[indice]) + np.sqrt(1.0 - rho ** 2) * rng.standard_normal()
    fila = repartir(int((u > tau).sum()), rng)
    fila["asma"] = asma if asma is not None else fila["asma_real"]
    return fila


def generar(modelo: Modelo, semilla: int) -> pd.DataFrame:
    """Una fila por placa, en el orden del modelo, reproducible por semilla."""
    rng = np.random.default_rng(semilla)
    filas = [repartir(int(k), rng) for k in sortear_puntuacion(modelo, rng)]
    for fila in filas:
        fila["asma"] = ocultar_asma(fila["asma_real"], rng)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def hallazgos(fila) -> dict:
    """Los cinco hallazgos tal como los recibe `heckerling.combinacion`, con
    tipos de Python: `validar_hallazgos` rechaza un `numpy.bool_`."""
    return {"temperatura_c": float(fila["temperatura_c"]),
            "frecuencia_cardiaca": int(fila["frecuencia_cardiaca"]),
            "crepitantes": bool(fila["crepitantes"]),
            "murmullo_disminuido": bool(fila["murmullo_disminuido"]),
            "asma": str(fila["asma"])}
```

- [ ] **Paso 4: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_generador.py -v`
Esperado: 10 PASS (≈ 10 s: el de `no_se` genera 50 veces las 3 811 filas).

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/validacion/generador.py tests/test_generador.py
git commit -m "feat(validacion): generador por puntuacion, reparto y numeros en el corte (SP5-A T3)"
```

---

### Tarea 4: Escenario 0A, determinista y con mutaciones

**Ficheros:**
- Prueba: `tests/test_validacion_0a.py`

**Interfaces:**
- Consume: `datos.cargar_crudas`, `datos.calibrador_desplegado`, `datos.evidencia_imagen`;
  `oraculo.ajustar`, `oraculo.logit_oraculo`, `oraculo.rv_recuentos`; `generador.generar`,
  `generador.hallazgos`; `heckerling.combinacion`, `combinar`, `mas_informativa`,
  `RV_POR_PUNTUACION`, y los cortes como atributos del módulo `heckerling`.
- Produce: nada que otras tareas importen. Es la prueba del criterio 1 del §11.

- [ ] **Paso 1: Escribir la prueba (falla hasta que las tres comprobaciones y las mutaciones estén bien)**

`tests/test_validacion_0a.py`:

```python
"""Escenario 0A: la aritmética del sistema, caso a caso contra el generador
(spec de SP5 §4.4, §8, §11.1).

Tres comprobaciones deterministas sobre las 3 811 placas de prueba con
dependencia nula, y las mutaciones que tienen que romperlas. No hay
estadística: un caso basta para que falle. Es lo que la Semana 1 §5.2
prometió: «la probabilidad posterior calculada debe coincidir con la del
generador de casos».
"""
import math

import numpy as np
import pytest

from copiloto_triaje.servicio import heckerling
from copiloto_triaje.servicio.heckerling import (
    RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from copiloto_triaje.validacion import datos, generador, oraculo

TOLERANCIA = 0.015   # el redondeo máximo de las RV publicadas (0,013 en k = 1)
SEMILLA = 1


def _logit(p):
    return math.log(p / (1.0 - p))


@pytest.fixture(scope="module")
def escenario():
    df = datos.cargar_crudas()
    cal = datos.calibrador_desplegado()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int))   # ρ1 = ρ0 = 0
    clinica = generador.generar(modelo, SEMILLA).to_dict("records")
    return cal.prevalencia, q, rv, modelo, clinica


def bloques(prevalencia, rv, clinica):
    return [combinacion(prevalencia, generador.hallazgos(fila), float(r))
            for fila, r in zip(clinica, rv)]


def fallos_0a1(prevalencia, rv, clinica):
    """Casos con asma conocida cuya puntuación del sistema no es la k del generador."""
    return [i for i, (fila, b) in enumerate(zip(clinica, bloques(prevalencia, rv, clinica)))
            if fila["asma"] != "no_se" and b["puntuacion"][0] != fila["k"]]


def fallos_0a3(prevalencia, q, rv, modelo, clinica):
    """Casos en que la aritmética sin redondear se aleja del oráculo más de la
    tolerancia. La k verdadera va en los dos lados, también con el asma oculta."""
    k = np.array([fila["k"] for fila in clinica])
    esperado = oraculo.logit_oraculo(modelo, q, k)
    sistema = np.array([_logit(combinar(prevalencia, RV_POR_PUNTUACION[int(kk)], float(r)))
                        for kk, r in zip(k, rv)])
    return list(np.flatnonzero(np.abs(sistema - esperado) > TOLERANCIA))


def test_0a1_la_puntuacion_del_sistema_es_la_del_generador(escenario):
    prevalencia, q, rv, modelo, clinica = escenario
    conocidas = sum(fila["asma"] != "no_se" for fila in clinica)
    assert conocidas > 3000
    assert fallos_0a1(prevalencia, rv, clinica) == []


def test_0a2_el_bloque_no_altera_la_aritmetica(escenario):
    """`independencia`, `dependencia`, `minima` y `maxima` son exactamente
    `round(combinar(...), 4)` de lo que heckerling.py dice que son."""
    prevalencia, q, rv, modelo, clinica = escenario
    for b, r in zip(bloques(prevalencia, rv, clinica), rv):
        r = float(r)
        for i, rvc in enumerate(b["rv_clinica"]):
            assert b["independencia"][i] == round(combinar(prevalencia, rvc, r), 4)
            if b["concordantes"]:
                assert b["dependencia"][i] == round(
                    combinar(prevalencia, mas_informativa(rvc, r), 1.0), 4)
        todas = b["independencia"] + (b["dependencia"] or [])
        assert b["minima"] == min(todas) and b["maxima"] == max(todas)


def test_0a3_la_aritmetica_coincide_con_el_oraculo_en_los_3811_casos(escenario):
    prevalencia, q, rv, modelo, clinica = escenario
    assert len(clinica) == 3811
    assert fallos_0a3(prevalencia, q, rv, modelo, clinica) == []


def test_0a3_la_diferencia_es_exactamente_el_redondeo_de_las_rv_publicadas(escenario):
    prevalencia, q, rv, modelo, clinica = escenario
    k = np.array([fila["k"] for fila in clinica])
    sistema = np.array([_logit(combinar(prevalencia, RV_POR_PUNTUACION[int(kk)], float(r)))
                        for kk, r in zip(k, rv)])
    diferencia = sistema - oraculo.logit_oraculo(modelo, q, k)
    esperada = np.array([math.log(RV_POR_PUNTUACION[int(kk)] / oraculo.rv_recuentos(int(kk)))
                         for kk in k])
    assert np.allclose(diferencia, esperada, atol=1e-9)
    assert 0.010 < np.abs(esperada).max() < TOLERANCIA


@pytest.mark.parametrize("k, mutada", [(5, 1.75), (4, 7.81), (3, 1.46)])
def test_una_rv_mutada_rompe_0a3_en_todos_los_casos_con_esa_puntuacion(
        escenario, monkeypatch, k, mutada):
    prevalencia, q, rv, modelo, clinica = escenario
    monkeypatch.setitem(RV_POR_PUNTUACION, k, mutada)
    con_esa_k = {i for i, fila in enumerate(clinica) if fila["k"] == k}
    assert con_esa_k
    assert set(fallos_0a3(prevalencia, q, rv, modelo, clinica)) == con_esa_k


@pytest.mark.parametrize("atributo, corte, afectado", [
    # el corte movido a 38,0: 37,9 y 38,0 dejan de puntuar
    ("TEMPERATURA_CORTE_C", 38.0, lambda t, fc: 37.8 < t <= 38.0),
    # 37,79 equivale a `>=` sobre la rejilla de décimas: 37,8 pasa a puntuar (D6)
    ("TEMPERATURA_CORTE_C", 37.79, lambda t, fc: t == 37.8),
    # 99 equivale a `>=` en el pulso: 100 pasa a puntuar
    ("PULSO_CORTE_LPM", 99, lambda t, fc: fc == 100),
])
def test_un_corte_mutado_rompe_0a1_caso_a_caso(escenario, monkeypatch, atributo, corte, afectado):
    prevalencia, q, rv, modelo, clinica = escenario
    monkeypatch.setattr(heckerling, atributo, corte)
    afectados = {i for i, fila in enumerate(clinica)
                 if fila["asma"] != "no_se"
                 and afectado(fila["temperatura_c"], fila["frecuencia_cardiaca"])}
    assert len(afectados) > 100
    assert set(fallos_0a1(prevalencia, rv, clinica)) == afectados
```

- [ ] **Paso 2: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_validacion_0a.py -v`
Esperado: 10 PASS. Si `test_0a1` o `test_0a3` fallan, el defecto está en las
tareas 2 o 3 (o en `heckerling.py`, que este plan no toca): no se ajusta la
tolerancia. Si una mutación NO rompe nada, el generador no está poniendo
valores en el corte (Tarea 3, `_valor`).

- [ ] **Paso 3: Commit**

```bash
git add tests/test_validacion_0a.py
git commit -m "test(validacion): escenario 0A determinista, con mutaciones de RV y de corte (SP5-A T4)"
```

---

### Tarea 5: La categoría del sistema

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/categoria.py`
- Prueba: `tests/test_categoria.py`

**Interfaces:**
- Consume: un bloque `combinacion` (dict con `minima`, `maxima`, `independencia`, `dependencia`, `concordantes`); `heckerling.combinacion` y `PREVALENCIA_COHORTE` (en las pruebas).
- Produce: `BANDAS = ("baja", "intermedia", "alta")`; `porcentaje_entero(p) -> int`;
  `banda(pct) -> str`; `punto_medio_log_odds(a, b) -> float`;
  `categoria_del_sistema(bloque) -> dict` con claves `primaria`, `punto_medio`,
  `independencia`, `conservador`, `cruza`, `cruza_limite`.

- [ ] **Paso 1: Escribir la prueba que falla**

`tests/test_categoria.py`:

```python
"""La categoría del sistema, fijada antes de la sesión (spec de SP5 §5.3, §8)."""
import itertools
import json
import pathlib

import numpy as np
import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE, combinacion
from copiloto_triaje.validacion import categoria

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_el_porcentaje_se_redondea_hacia_arriba_en_medio_como_el_bot():
    assert categoria.porcentaje_entero(0.195) == 20
    assert categoria.porcentaje_entero(0.705) == 71
    assert categoria.porcentaje_entero(0.1949) == 19
    assert categoria.porcentaje_entero(0.0) == 0 and categoria.porcentaje_entero(1.0) == 100
    # el nodo Desenlace redondea igual: Math.round sube en ,5
    flujo = json.loads((REPO / "n8n" / "copiloto-profesional.json").read_text(encoding="utf-8"))
    desenlace = next(n for n in flujo["nodes"] if n["name"] == "Desenlace")
    assert "Math.round(v * 100)" in desenlace["parameters"]["jsCode"]


def test_las_bandas_tienen_los_bordes_20_y_70_dentro_de_intermedia():
    assert categoria.banda(19) == "baja"
    assert categoria.banda(20) == "intermedia"
    assert categoria.banda(70) == "intermedia"
    assert categoria.banda(71) == "alta"
    assert categoria.banda(0) == "baja" and categoria.banda(100) == "alta"


def test_el_punto_medio_es_en_log_odds():
    # logit 0,2 = −1,386; logit 0,8 = +1,386 → punto medio 0,5
    assert categoria.punto_medio_log_odds(0.2, 0.8) == pytest.approx(0.5)
    # y no es la media aritmética: (0,1 ; 0,9) también da 0,5, pero (0,1 ; 0,5) no da 0,3
    assert categoria.punto_medio_log_odds(0.1, 0.5) == pytest.approx(0.25, abs=0.01)


def _bloque(minima, maxima, independencia, dependencia, concordantes):
    return {"minima": minima, "maxima": maxima, "independencia": independencia,
            "dependencia": dependencia, "concordantes": concordantes}


def test_la_categoria_primaria_y_sus_variantes():
    # horquilla 0,65-0,95 (concordante, la imagen absorbe): punto medio en log-odds ≈ 0,87 → alta;
    # independencia 0,95 → alta; conservador 0,65 → intermedia; cruza el 70 % → intermedia
    c = categoria.categoria_del_sistema(_bloque(0.65, 0.95, [0.95], [0.65], True))
    assert c["primaria"] == "alta" and c["independencia"] == "alta"
    assert c["conservador"] == "intermedia" and c["cruza"] == "intermedia" and c["cruza_limite"]
    # discordante: un número, todas las variantes coinciden
    c = categoria.categoria_del_sistema(_bloque(0.12, 0.12, [0.12], None, False))
    assert {c["primaria"], c["independencia"], c["conservador"], c["cruza"]} == {"baja"}
    assert not c["cruza_limite"]
    # asma no_se: dos posteriores de independencia; el punto medio de las dos
    c = categoria.categoria_del_sistema(_bloque(0.30, 0.60, [0.30, 0.60], None, False))
    assert c["independencia"] == "intermedia" and c["primaria"] == "intermedia"


def _hallazgos():
    for t, fc, cr, mu, asma in itertools.product((37.8, 37.9), (100, 101), (False, True),
                                                 (False, True), ("si", "no", "no_se")):
        yield {"temperatura_c": t, "frecuencia_cardiaca": fc, "crepitantes": cr,
               "murmullo_disminuido": mu, "asma": asma}


def _cruces_dobles(prevalencia):
    cruces = 0
    for rv in np.geomspace(0.016, 77.3, 400):
        for h in _hallazgos():
            b = combinacion(prevalencia, h, float(rv))
            if (categoria.porcentaje_entero(b["minima"]) < 20
                    and categoria.porcentaje_entero(b["maxima"]) > 70):
                cruces += 1
    return cruces


@pytest.mark.parametrize("prevalencia", [PREVALENCIA_COHORTE, 0.2215, 0.05])
def test_ninguna_horquilla_cruza_los_dos_limites_con_las_tablas_actuales(prevalencia):
    """Spec §5.3 y §8: barrido de la RV de imagen desplegada (0,016-77,3) por las
    48 combinaciones de hallazgos. El umbral analítico está por debajo de ≈ 2,6 %."""
    assert _cruces_dobles(prevalencia) == 0


def test_con_una_prevalencia_bajo_el_umbral_analitico_si_hay_cruces_dobles():
    assert _cruces_dobles(0.02) > 0
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_categoria.py -v`
Esperado: FAIL con `ImportError: cannot import name 'categoria'`.

- [ ] **Paso 3: Escribir `categoria.py`**

```python
# -*- coding: utf-8 -*-
"""La categoria del sistema para el kappa, fijada ANTES de la sesion (spec §5.3).

Regla primaria: la banda del punto medio en log-odds de [minima, maxima],
convertido a porcentaje entero con redondeo hacia arriba en ,5 (el mismo
`Math.round` del nodo Desenlace). Bandas: [0, 20) baja, [20, 70] intermedia,
(70, 100] alta. Los cortes 20 y 70 son una convencion del equipo fijada el
27-sep, no un estandar publicado.

Variantes, fijadas de antemano como analisis de sensibilidad: la banda del
extremo de independencia, la del extremo conservador, y la regla «si la
horquilla cruza un limite, intermedia». Con las tablas actuales ninguna
horquilla cruza a la vez el 20 % y el 70 % (prueba): el cociente de odds de
los dos extremos vale min(RV_clinica, RV_imagen) ≤ 17,5, y cruzar los dos
exige ademas odds_previas × max(RV) < 0,25, que solo ocurre con prevalencia
declarada por debajo de ≈ 2,6 %.
"""
from __future__ import annotations

import math

BANDAS = ("baja", "intermedia", "alta")
_MARGEN = 1e-6   # un bloque redondeado a 4 decimales no llega a 0 ni a 1, pero por si acaso


def porcentaje_entero(p: float) -> int:
    """floor(100 p + 0,5): hacia arriba en ,5, como `Math.round` en el bot."""
    return int(math.floor(p * 100.0 + 0.5))


def banda(pct: int) -> str:
    if pct < 20:
        return "baja"
    if pct > 70:
        return "alta"
    return "intermedia"


def _logit(p: float) -> float:
    p = min(max(float(p), _MARGEN), 1.0 - _MARGEN)
    return math.log(p / (1.0 - p))


def punto_medio_log_odds(a: float, b: float) -> float:
    medio = 0.5 * (_logit(a) + _logit(b))
    return 1.0 / (1.0 + math.exp(-medio))


def categoria_del_sistema(bloque: dict) -> dict:
    """La primaria y las tres variantes, a partir del bloque `combinacion`."""
    medio = punto_medio_log_odds(bloque["minima"], bloque["maxima"])
    indep = bloque["independencia"]
    independencia = punto_medio_log_odds(indep[0], indep[-1])
    dep = bloque["dependencia"]
    conservador = (punto_medio_log_odds(dep[0], dep[-1]) if bloque["concordantes"] and dep
                   else independencia)
    baja_, alta_ = banda(porcentaje_entero(bloque["minima"])), banda(porcentaje_entero(bloque["maxima"]))
    return {
        "primaria": banda(porcentaje_entero(medio)),
        "punto_medio": medio,
        "independencia": banda(porcentaje_entero(independencia)),
        "conservador": banda(porcentaje_entero(conservador)),
        "cruza": baja_ if baja_ == alta_ else "intermedia",
        "cruza_limite": baja_ != alta_,
    }
```

- [ ] **Paso 4: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_categoria.py -v`
Esperado: 8 PASS (el barrido son 76 800 llamadas a `combinacion`: unos segundos).

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/validacion/categoria.py tests/test_categoria.py
git commit -m "feat(validacion): categoria del sistema y prueba de que ninguna horquilla cruza los dos limites (SP5-A T5)"
```

---

### Tarea 6: El arnés acepta `--casos` y teclea la clínica de cada caso

**Ficheros:**
- Modificar: `pruebas/reproducir_casos.py` (constantes tras `BOTONES_PACIENTE`; `Perfil`/`POR_CLAVE`; `Bots.conversacion_del_paciente`; `Bots.conversacion_del_profesional`; `main`)
- Modificar: `tests/test_reproducir_casos.py` (el auxiliar `_redactar` y pruebas nuevas)

**Interfaces:**
- Consume: `hallazgos_del_caso`, `SIGNOS`, `SINTOMAS`, `BOTONES_PACIENTE`, `SIGNOS_TECLEADOS`, `SIGNOS_BOTONES`, `Perfil`, `_metadatos`, `redactar` (todo existente en el arnés).
- Produce: `CLAVES_PACIENTE`; `botones_del_paciente(sintomas) -> tuple[str, ...]`;
  `signos_tecleados(signos) -> tuple[str, str]`; `signos_botones(signos) -> tuple[str, str]`;
  `PERFIL_SESION: Perfil`; `casos_desde_fichero(ruta) -> list[dict]` (cada caso con
  `perfil, patientId, ruta_dcm, cruda_cache, edad_rsna, clase_rsna, sexo_rsna, sintomas, signos`);
  la opción `--casos JSON`; y el fichero `<salida>/mensajes.json`:
  `{patientId: {texto, texto_paciente, error, resultado, codigo, ms_extremo, con_bots, fallo}}`.
  El formato de `casos.json`: lista de `{"patientId", "ruta_dcm", "signos": {los cuatro}, "sintomas": {los siete del cuestionario, con texto_libre}}`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

En `tests/test_reproducir_casos.py`, localiza el auxiliar `_redactar` (el que
construye `decidir` con `"signos": {"temperatura_c": 38.2, ...}` y llama a
`node pruebas/redactar.mjs`). Dale un parámetro más, `signos=None`, y usa
`signos if signos is not None else SIGNOS` como `decidir["signos"]`, sin
cambiar nada más de su comportamiento. Después añade al final del fichero:

```python
# --------------------------------------------------------------------------
# --casos: la sesion con el medico (SP5 §5.6). El arnes teclea la clinica de
# CADA caso, y los mensajes los redactan los nodos reales.
# --------------------------------------------------------------------------
def test_los_botones_y_los_signos_de_cada_caso_reproducen_las_constantes():
    from pruebas.reproducir_casos import (
        BOTONES_PACIENTE, SIGNOS_BOTONES, SIGNOS_TECLEADOS, botones_del_paciente,
        signos_botones, signos_tecleados,
    )
    assert botones_del_paciente(SINTOMAS) == BOTONES_PACIENTE
    assert signos_tecleados(SIGNOS) == SIGNOS_TECLEADOS
    assert signos_botones(SIGNOS) == SIGNOS_BOTONES
    otros = {"temperatura_c": 37.8, "frecuencia_cardiaca": 101,
             "crepitantes": False, "murmullo_disminuido": True}
    assert signos_tecleados(otros) == ("37,8", "101")
    assert signos_botones(otros) == ("s4:no", "s5:si")
    assert botones_del_paciente({**SINTOMAS, "fiebre": "no", "asma": "si"})[0] == "p1:no"
    assert botones_del_paciente({**SINTOMAS, "fiebre": "no", "asma": "si"})[5] == "p6:si"


def test_casos_desde_fichero_construye_los_casos_de_la_sesion(tmp_path):
    from pruebas.reproducir_casos import (
        PERFIL_SESION, SIGNOS, SINTOMAS, casos_desde_fichero, hallazgos_del_caso,
    )
    dcm = tmp_path / "a.dcm"
    dcm.write_bytes(b"x")
    signos = {"temperatura_c": 37.9, "frecuencia_cardiaca": 100,
              "crepitantes": True, "murmullo_disminuido": False}
    sintomas = {**SINTOMAS, "fiebre": "si", "asma": "no"}
    fichero = tmp_path / "casos.json"
    fichero.write_text(json.dumps([
        {"patientId": "p-1", "ruta_dcm": str(dcm), "signos": signos, "sintomas": sintomas},
        {"patientId": "p-2", "ruta_dcm": str(dcm), "signos": SIGNOS, "sintomas": SINTOMAS},
        {"patientId": "p-3", "ruta_dcm": str(dcm), "signos": signos,
         "sintomas": {**sintomas, "asma": "no_se"}},
    ]), encoding="utf-8")
    casos = casos_desde_fichero(fichero)
    assert [c["patientId"] for c in casos] == ["p-1", "p-2", "p-3"]
    assert all(c["perfil"] is PERFIL_SESION for c in casos)
    assert hallazgos_del_caso(casos[0]["sintomas"], casos[0]["signos"]) == {**signos, "asma": "no"}
    assert hallazgos_del_caso(casos[2]["sintomas"], casos[2]["signos"])["asma"] == "no_se"
    # un caso a medias no se acepta: el arnes diria «SIN COMBINAR» y nadie lo notaria
    fichero.write_text(json.dumps([{"patientId": "p-4", "ruta_dcm": str(dcm),
                                    "signos": {"temperatura_c": 38.0}, "sintomas": SINTOMAS}]),
                       encoding="utf-8")
    with pytest.raises(SystemExit, match="cinco hallazgos"):
        casos_desde_fichero(fichero)
    fichero.write_text(json.dumps([{"patientId": "p-5", "ruta_dcm": str(tmp_path / "no.dcm"),
                                    "signos": signos, "sintomas": sintomas}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="no existe la placa"):
        casos_desde_fichero(fichero)


def test_el_explorado_del_mensaje_repite_los_signos_del_caso():
    """Los nodos reales redactan EXPLORADO con lo que el arnes tecleo: 37,8 y
    100 exactos (no puntuan) tienen que salir tal cual, no como 38 y 100."""
    signos = {"temperatura_c": 37.8, "frecuencia_cardiaca": 101,
              "crepitantes": False, "murmullo_disminuido": True}
    d = _redactar({"statusCode": 200, "cuerpo": _sse(UN_RESULTADO)}, signos=signos)
    assert "EXPLORADO — 37,8 °C, 101 lpm, crepitantes no, murmullo disminuido" in d["texto"]
```

- [ ] **Paso 2: Correr las pruebas y ver que fallan**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_reproducir_casos.py -v -k "casos or botones or explorado"`
Esperado: 2 FAIL por `ImportError` (`botones_del_paciente`, `PERFIL_SESION`) y
1 FAIL o error en `_redactar` por el parámetro `signos` (hasta que lo añadas).

- [ ] **Paso 3: Añadir las funciones por caso y el perfil de la sesión**

En `pruebas/reproducir_casos.py`, justo después de la definición de
`BOTONES_PACIENTE` (y antes del comentario «Los cinco datos que `A base64`
manda…»):

```python
# El orden de las seis preguntas del cuestionario. Con esto los botones y los
# signos se componen para CUALQUIER caso, y no solo para los fijos de arriba:
# la sesion con el medico (SP5 §5.6) manda por `--casos` la clinica de cada
# caso, y el arnes tiene que teclear exactamente esa.
CLAVES_PACIENTE = ("fiebre", "tos", "dias_evolucion", "disnea", "dolor_toracico",
                   "asma")


def botones_del_paciente(sintomas):
    """Los seis botones del cuestionario para estos sintomas: `p{i}:{valor}`."""
    return tuple(f"p{i}:{sintomas[k]}" for i, k in enumerate(CLAVES_PACIENTE, 1))


def signos_tecleados(signos):
    """Lo que el profesional teclea: la temperatura con coma decimal y una
    decima, el pulso entero. 37,8 exactos se teclean como «37,8»: es el corte,
    y que no puntue es justo lo que la sesion quiere ver redactado."""
    return (f"{float(signos['temperatura_c']):.1f}".replace(".", ","),
            str(int(round(signos["frecuencia_cardiaca"]))))


def signos_botones(signos):
    """Los dos botones de la exploracion: s4 crepitantes, s5 murmullo."""
    return ("s4:si" if signos["crepitantes"] else "s4:no",
            "s5:si" if signos["murmullo_disminuido"] else "s5:no")
```

Justo después de la definición de `POR_CLAVE` (el diccionario de perfiles por
clave):

```python
# El perfil de los casos que llegan por `--casos`: la sesion con el medico
# (SP5 §5.6). No esta en PERFILES a proposito: no es parte del corpus, y por
# eso tampoco se puede pedir con `--solo`.
PERFIL_SESION = Perfil(
    0, "sesion", "Casos de la sesión con el médico (viñetas semisintéticas)",
    "de un fichero `--casos`: placa real del conjunto de prueba y clínica del "
    "generador de SP5",
    "que EXPLORADO y REFERIDO POR EL PACIENTE repitan la viñeta de cada caso")


def casos_desde_fichero(ruta):
    """Los casos de `--casos`: una lista JSON de
    {patientId, ruta_dcm, signos, sintomas}. Se comprueba cada uno ANTES de
    empezar: un caso a medias haria que el arnes dijera «SIN COMBINAR» de un
    caso que el medico va a leer como combinado."""
    ruta = pathlib.Path(ruta)
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, list) or not datos:
        raise SystemExit(f"{ruta} no es una lista de casos")
    meta = _metadatos()
    casos = []
    for i, d in enumerate(datos):
        faltan = [k for k in ("patientId", "ruta_dcm", "signos", "sintomas") if k not in d]
        if faltan:
            raise SystemExit(f"al caso {i} de {ruta} le faltan {faltan}")
        if hallazgos_del_caso(d["sintomas"], d["signos"]) is None:
            raise SystemExit(f"el caso {d['patientId']} no lleva los cinco hallazgos "
                             f"con su tipo: no se puede combinar")
        if not pathlib.Path(d["ruta_dcm"]).is_file():
            raise SystemExit(f"no existe la placa {d['ruta_dcm']} del caso {d['patientId']}")
        edad, clase, sexo = meta.get(d["patientId"], (None, "?", "?"))
        casos.append({
            "perfil": PERFIL_SESION,
            "patientId": d["patientId"],
            "ruta_dcm": d["ruta_dcm"],
            "cruda_cache": d.get("cruda"),
            "edad_rsna": edad,
            "clase_rsna": clase,
            "sexo_rsna": sexo,
            "sintomas": dict(d["sintomas"]),
            "signos": dict(d["signos"]),
        })
    return casos
```

- [ ] **Paso 4: Que los bots tecleen la clínica de cada caso**

En `Bots.conversacion_del_paciente`, sustituye
`for dato in BOTONES_PACIENTE:` por `for dato in botones_del_paciente(sintomas):`.

En `Bots.conversacion_del_profesional`, cambia la firma a
`def conversacion_del_profesional(self, codigo, ruta_dcm, signos=SIGNOS):` y
sustituye `zip(SIGNOS_TECLEADOS, (3, 4))` por `zip(signos_tecleados(signos), (3, 4))`
y `zip(SIGNOS_BOTONES, (5, 6))` por `zip(signos_botones(signos), (5, 6))`.

En `main`:

1. Tras `p.add_argument("--salida", ...)` añade:

```python
    p.add_argument("--casos", metavar="JSON",
                   help="los casos de la sesión con el médico (SP5 §5.6): "
                        "placa, signos y síntomas de cada uno; ignora "
                        "--por-perfil y --solo, y deja <salida>/mensajes.json")
```

2. Sustituye `casos = construir_casos(args.por_perfil, args.solo, destino)` por:

```python
    casos = (casos_desde_fichero(args.casos) if args.casos
             else construir_casos(args.por_perfil, args.solo, destino))
```

3. En la llamada `bots.conversacion_del_profesional(codigo, caso["ruta_dcm"])`
   añade el tercer argumento: `bots.conversacion_del_profesional(codigo, caso["ruta_dcm"], caso.get("signos") or SIGNOS)`.

4. Sustituye `signos = obs["signos"] if obs.get("signos") else SIGNOS` por
   `signos = obs["signos"] if obs.get("signos") else (caso.get("signos") or SIGNOS)`.

5. Justo después del bucle `for fila, redaccion in zip(filas, redacciones):`
   (dentro del `try`, antes del `finally`) añade:

```python
        if args.casos:
            # Lo que `scripts/preparar_sesion.py --fase mensajes` lee: el texto
            # que redactaron los nodos reales y el bloque `combinacion` que
            # devolvio el copiloto, por caso. Ademas del corpus legible.
            destino.mkdir(parents=True, exist_ok=True)
            mensajes = {}
            for caso, obs, redaccion in filas:
                mensajes[caso["patientId"]] = {
                    "texto": redaccion["texto"],
                    "texto_paciente": redaccion.get("texto_paciente"),
                    "error": redaccion["error"],
                    "resultado": redaccion["resultado"],
                    "codigo": obs.get("codigo"),
                    "ms_extremo": obs.get("ms_extremo"),
                    "con_bots": obs["con_bots"],
                    "fallo": obs.get("fallo"),
                }
            (destino / "mensajes.json").write_text(
                json.dumps(mensajes, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"mensajes de la sesión: {destino / 'mensajes.json'}")
```

- [ ] **Paso 5: Correr las pruebas y ver que pasan**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_reproducir_casos.py -v`
Esperado: todas PASS, incluidas las tres nuevas y las que ya existían (el
auxiliar `_redactar` sigue dando lo mismo sin `signos`).

- [ ] **Paso 6: Comprobación de extremo a extremo sin bots (manual, contra la imagen local)**

Si Docker está disponible, arranca la imagen local del mismo commit
desplegado (el `docker run` de `tests/test_contrato_mcp.py::ARRANCAR`, con el
tag `copiloto-mcp:sp4` y `-p 127.0.0.1:18001:8000`), y con un `casos.json` de
2 casos reales (dos `patientId` de `docs/validacion-semisintetica/crudas_prueba.csv`
cuyos DICOM estén en `<RSNA_RAIZ>/crudo/stage_2_train_images/`):

```bash
COPILOTO_URL=http://127.0.0.1:18001/mcp C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --sin-bots --casos /ruta/casos.json --salida /tmp/sesion-prueba
```

Esperado: `MODO SIN BOTS (--sin-bots)`, dos casos redactados, la carpeta
`00-sesion/` con dos `.txt` legibles cuyo bloque EXPLORADO repite los signos
del fichero, y `/tmp/sesion-prueba/mensajes.json` con las dos claves y
`resultado.combinacion` en cada una. Si Docker no está disponible, dilo en el
informe de la tarea: la prueba de extremo a extremo la hará quien prepare la
sesión (Tarea 10, runbook).

- [ ] **Paso 7: Commit**

```bash
git add pruebas/reproducir_casos.py tests/test_reproducir_casos.py
git commit -m "feat(arnes): --casos para la sesion con el medico, clinica por caso y mensajes.json (SP5-A T6)"
```

---

### Tarea 7: Elegir los casos, escribir las viñetas y preparar la sesión

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/sesion.py`
- Crear: `scripts/preparar_sesion.py`
- Prueba: `tests/test_sesion.py`

**Interfaces:**
- Consume: `datos.*`; `oraculo.ajustar`; `generador.SIGNOS`, `generador.hallazgos`, `generador.sortear_caso`;
  `categoria.categoria_del_sistema`; `heckerling.combinacion`, `TEMPERATURA_CORTE_C`, `PREVALENCIA_COHORTE`;
  `pruebas/formulario/index.html` y `formulario.js` (Tarea 8: hasta que existan, `fase_elegir` los copia si están y avisa si no).
- Produce: en `sesion.py`: `UMBRAL_CRIBADO`, `RV_POSITIVA_CLARA`, `RV_NEGATIVA_CLARA`, `ESTRATOS`, `CUOTA`,
  `PRACTICA`, `RHO_SESION`, `SINTOMAS_FIJOS`, `SEXO`; `estratos(df, rv) -> dict[str, np.ndarray]`;
  `sintomas_de(hallazgos) -> dict`; `elegir(df, rv, modelo, prevalencia, semilla) -> (casos, practica)`
  (cada caso: `patientId, estrato, etiqueta, edad, sexo, vista, cruda, rv_imagen, signos, sintomas, k, asma_real, concordante, bloque_previsto, categoria_prevista`);
  `vineta(caso) -> str`; `linea_explorado(signos) -> str`; `ordenes(casos, rng) -> {"lectura1", "lectura2", "controles"}`.
  En `preparar_sesion.py`: `raiz_rsna()`, `entrada_formulario(caso, mensaje, control=False)`,
  `datos_js(nombre, lectura, modo, casos, practica, salida)`, `dosier(titulo, entradas, salida, nombre)`,
  `fase_elegir(salida, semilla)`, `fase_mensajes(salida)`; la forma de `datos_lectura<N>.js`:
  `window.DATOS = {"lectura": N, "modo": "simple"|"secuencial", "casos": [{id, placa, vineta, mensaje, control}], "practica": [...]};`
  y la de `clave.json` (`rotulo, semilla, prevalencia_sesion, rho_sesion, ordenes, casos, practica, fase`; tras la fase `mensajes` cada caso lleva además `bloque, categoria, mensaje, con_bots`).

- [ ] **Paso 1: Escribir la prueba que falla**

`tests/test_sesion.py`:

```python
"""La selección de casos y las viñetas de la sesión (spec de SP5 §5.1, §5.3, §5.4, §5.8)."""
import importlib.util
import json
import pathlib
import re

import numpy as np
import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE, validar_hallazgos
from copiloto_triaje.validacion import datos, oraculo, sesion
from test_reproducir_casos import UN_RESULTADO, _redactar, _sse

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def conjunto():
    df = datos.cargar_crudas()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, datos.calibrador_desplegado())
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int), *sesion.RHO_SESION)
    return df, rv, modelo


@pytest.fixture(scope="module")
def eleccion(conjunto):
    df, rv, modelo = conjunto
    return sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, semilla=20261006)


def test_el_umbral_de_cribado_es_el_del_selector_de_casos():
    from pruebas.seleccionar_casos import UMBRAL
    assert sesion.UMBRAL_CRIBADO == UMBRAL


def test_la_prevalencia_de_la_sesion_es_la_desplegada():
    compose = (REPO / "servidor" / "docker-compose.yml").read_text(encoding="utf-8")
    declarada = float(re.search(r'PREVALENCIA_LOCAL:\s*"([0-9.]+)"', compose).group(1))
    assert round(PREVALENCIA_COHORTE, 4) == declarada


def test_hay_candidatos_de_sobra_en_cada_estrato(conjunto):
    df, rv, _ = conjunto
    e = sesion.estratos(df, rv)
    assert len(e["positiva_clara"]) > 300 and len(e["negativa_clara"]) > 1000
    assert len(e["banda_contradictoria"]) > 300 and len(e["asma_no_se"]) == len(df)
    assert (df["etiqueta"].values[e["positiva_clara"]] == 1).all()
    assert (rv[e["banda_contradictoria"]] < 1.0).all()


def test_elegir_llena_las_cuotas_por_estrato_y_por_concordancia(eleccion):
    casos, practica = eleccion
    assert len(casos) == 24 and len(practica) == 3
    for estrato, cuota in sesion.CUOTA.items():
        del_estrato = [c for c in casos if c["estrato"] == estrato]
        assert len(del_estrato) == 2 * cuota
        assert sum(c["concordante"] for c in del_estrato) == cuota
    ids = [c["patientId"] for c in casos + practica]
    assert len(set(ids)) == 27
    assert [p["estrato"] for p in practica] == list(sesion.PRACTICA)
    for c in casos:
        assert c["concordante"] == c["bloque_previsto"]["concordantes"]
        assert c["categoria_prevista"]["primaria"] in ("baja", "intermedia", "alta")
        validar_hallazgos({**c["signos"], "asma": c["sintomas"]["asma"]})
    assert all(c["sintomas"]["asma"] == "no_se" for c in casos if c["estrato"] == "asma_no_se")
    assert all(c["sintomas"]["asma"] != "no_se" for c in casos if c["estrato"] != "asma_no_se")


def test_la_fiebre_referida_sigue_a_la_temperatura(eleccion):
    casos, _ = eleccion
    for c in casos:
        assert c["sintomas"]["fiebre"] == ("si" if c["signos"]["temperatura_c"] > 37.8 else "no")
        assert {k: v for k, v in c["sintomas"].items() if k not in ("fiebre", "asma")} == sesion.SINTOMAS_FIJOS


def test_elegir_es_reproducible_por_semilla(conjunto):
    df, rv, modelo = conjunto
    a = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, 1)
    b = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, 1)
    assert a == b
    assert sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, 2) != a


def test_la_vineta_se_lee_como_un_caso_y_con_coma_decimal(eleccion):
    casos, _ = eleccion
    c = dict(casos[0])
    c.update({"edad": 57, "sexo": "M", "vista": "AP",
              "signos": {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
                         "crepitantes": True, "murmullo_disminuido": False},
              "sintomas": {**sesion.SINTOMAS_FIJOS, "fiebre": "si", "asma": "no_se"}})
    v = sesion.vineta(c)
    assert v.startswith("Paciente de 57 años, sexo masculino; radiografía de tórax en proyección AP.")
    assert "refiere fiebre; tos con flema; entre 3 y 7 días de evolución; sin disnea; con dolor torácico; no sabe si tiene asma." in v
    assert "temperatura 38,2 °C; frecuencia cardíaca 104 lpm; crepitantes: sí; murmullo vesicular: normal." in v


def test_linea_explorado_es_la_que_redacta_el_nodo_desenlace():
    signos = {"temperatura_c": 37.8, "frecuencia_cardiaca": 101,
              "crepitantes": False, "murmullo_disminuido": True}
    d = _redactar({"statusCode": 200, "cuerpo": _sse(UN_RESULTADO)}, signos=signos)
    assert sesion.linea_explorado(signos) in d["texto"]


def test_los_ordenes_son_permutaciones_y_los_controles_salen_de_los_estratos_claros(eleccion):
    casos, _ = eleccion
    o = sesion.ordenes(casos, np.random.default_rng(3))
    ids = {c["patientId"] for c in casos}
    assert set(o["lectura1"]) == ids and set(o["lectura2"]) == ids
    assert len(o["lectura1"]) == len(o["lectura2"]) == 24
    assert len(set(o["controles"])) == 4
    por_id = {c["patientId"]: c for c in casos}
    pares = {(por_id[i]["estrato"], por_id[i]["concordante"]) for i in o["controles"]}
    assert pares == {("positiva_clara", True), ("positiva_clara", False),
                     ("negativa_clara", True), ("negativa_clara", False)}


def _preparar():
    spec = importlib.util.spec_from_file_location(
        "preparar_sesion", REPO / "scripts" / "preparar_sesion.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _leer_datos_js(ruta):
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith("window.DATOS = ") and texto.rstrip().endswith(";")
    return json.loads(texto[len("window.DATOS = "):].rstrip().rstrip(";"))


def test_fase_elegir_deja_lo_que_el_arnes_y_el_formulario_necesitan(tmp_path, monkeypatch):
    preparar = _preparar()
    raiz = tmp_path / "rsna"
    (raiz / "png").mkdir(parents=True)
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    salida = tmp_path / "sesion"
    preparar.fase_elegir(salida, semilla=20261006)
    casos = json.loads((salida / "casos.json").read_text(encoding="utf-8"))
    assert len(casos) == 27
    assert all(set(c) == {"patientId", "ruta_dcm", "signos", "sintomas", "cruda"} for c in casos)
    assert casos[0]["ruta_dcm"].endswith(f"{casos[0]['patientId']}.dcm")
    d1 = _leer_datos_js(salida / "formulario" / "datos_lectura1.js")
    assert d1["lectura"] == 1 and d1["modo"] == "simple"
    assert len(d1["casos"]) == 24 and len(d1["practica"]) == 3
    assert all(e["mensaje"] is None and not e["control"] for e in d1["casos"])
    assert (salida / "formulario" / "placas" / f"{d1['casos'][0]['id']}.png").is_file()
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    assert clave["fase"] == "elegir" and clave["prevalencia_sesion"] == PREVALENCIA_COHORTE
    assert "simulación semisintética" in clave["rotulo"]
    assert "simulación semisintética" in (salida / "dosier_lectura1.md").read_text(encoding="utf-8")


def _mensajes_coherentes(clave):
    return {c["patientId"]: {"texto": "CRIBADO — ...\n" + sesion.linea_explorado(c["signos"]) + "\nCOMBINADO — ...",
                             "texto_paciente": None, "error": None,
                             "resultado": {"combinacion": c["bloque_previsto"]},
                             "codigo": "ABC123", "ms_extremo": 1500, "con_bots": False, "fallo": None}
            for c in clave["casos"] + clave["practica"]}


def test_fase_mensajes_construye_la_lectura_2_con_20_mensajes_y_4_controles(tmp_path, monkeypatch):
    preparar = _preparar()
    raiz = tmp_path / "rsna"
    (raiz / "png").mkdir(parents=True)
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    salida = tmp_path / "sesion"
    preparar.fase_elegir(salida, semilla=20261006)
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    (salida / "corpus").mkdir()
    (salida / "corpus" / "mensajes.json").write_text(
        json.dumps(_mensajes_coherentes(clave)), encoding="utf-8")
    preparar.fase_mensajes(salida)
    d2 = _leer_datos_js(salida / "formulario" / "datos_lectura2.js")
    assert d2["lectura"] == 2 and d2["modo"] == "simple" and len(d2["casos"]) == 24
    assert sum(e["mensaje"] is not None for e in d2["casos"]) == 20
    assert sum(e["control"] for e in d2["casos"]) == 4
    assert all((e["mensaje"] is None) == e["control"] for e in d2["casos"])
    assert [e["id"] for e in d2["casos"]] == clave["ordenes"]["lectura2"]
    planb = _leer_datos_js(salida / "formulario" / "datos_planb.js")
    assert planb["modo"] == "secuencial" and all(e["mensaje"] for e in planb["casos"])
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    assert clave["fase"] == "mensajes"
    assert all("categoria" in c and c["bloque"] == c["bloque_previsto"] for c in clave["casos"])


def test_fase_mensajes_aborta_si_un_mensaje_no_repite_la_vineta(tmp_path, monkeypatch):
    preparar = _preparar()
    raiz = tmp_path / "rsna"
    (raiz / "png").mkdir(parents=True)
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    salida = tmp_path / "sesion"
    preparar.fase_elegir(salida, semilla=20261006)
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    mensajes = _mensajes_coherentes(clave)
    primero = clave["casos"][0]["patientId"]
    mensajes[primero]["texto"] = "EXPLORADO — 40,0 °C, 150 lpm, crepitantes sí, murmullo disminuido"
    (salida / "corpus").mkdir()
    (salida / "corpus" / "mensajes.json").write_text(json.dumps(mensajes), encoding="utf-8")
    with pytest.raises(SystemExit, match="EXPLORADO no repite"):
        preparar.fase_mensajes(salida)
    assert not (salida / "formulario" / "datos_lectura2.js").exists()


def test_sin_rsna_raiz_el_script_lo_dice(monkeypatch):
    preparar = _preparar()
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        preparar.raiz_rsna()
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_sesion.py -v`
Esperado: FAIL con `ImportError: cannot import name 'sesion'`.

- [ ] **Paso 3: Escribir `sesion.py`**

```python
# -*- coding: utf-8 -*-
"""La seleccion de casos, las viñetas y los ordenes de la sesion con el medico
(spec de SP5 §5.1, §5.3, §5.4). Puro: no lee ni escribe ficheros.

Estratos deliberados y, dentro de cada uno, mitad con clinica concordante y
mitad discordante segun el propio bloque `combinacion` del sistema, para que
el kappa no lo inflen los casos faciles. La clinica sale del generador con
(ρ1, ρ0) = RHO_SESION: ni independiente de la placa (viñetas incoherentes) ni
copia de ella. Los sintomas referidos son un fondo constante salvo la fiebre,
que sigue a la temperatura medida, y el asma, que sale del generador.
"""
from __future__ import annotations

import numpy as np

from copiloto_triaje.servicio.heckerling import TEMPERATURA_CORTE_C, combinacion

from .categoria import categoria_del_sistema
from .generador import SIGNOS, hallazgos, sortear_caso
from .oraculo import Modelo

UMBRAL_CRIBADO = 0.4258        # el desplegado (`/salud` -> umbral); prueba contra seleccionar_casos.UMBRAL
RV_POSITIVA_CLARA = 5.0
RV_NEGATIVA_CLARA = 0.2
ESTRATOS = ("positiva_clara", "negativa_clara", "banda_contradictoria", "asma_no_se")
# Casos por estrato Y por concordancia: 4+4, 4+4, 2+2, 2+2 = 24.
CUOTA = {"positiva_clara": 4, "negativa_clara": 4,
         "banda_contradictoria": 2, "asma_no_se": 2}
PRACTICA = ("positiva_clara", "negativa_clara", "banda_contradictoria")
RHO_SESION = (0.3, 0.3)
# Los de `pruebas/reproducir_casos.SINTOMAS`, salvo la fiebre y el asma.
SINTOMAS_FIJOS = {"tos": "con_flema", "dias_evolucion": "3_a_7", "disnea": "no",
                  "dolor_toracico": "si", "texto_libre": None}
SEXO = {"F": "femenino", "M": "masculino"}


def estratos(df, rv) -> dict:
    """Indices candidatos por estrato, sobre las crudas congeladas."""
    etiqueta = df["etiqueta"].values
    cruda = df["cruda"].values
    rv = np.asarray(rv, dtype=float)
    return {
        "positiva_clara": np.flatnonzero((etiqueta == 1) & (rv >= RV_POSITIVA_CLARA)),
        "negativa_clara": np.flatnonzero((etiqueta == 0) & (rv <= RV_NEGATIVA_CLARA)),
        "banda_contradictoria": np.flatnonzero((cruda >= UMBRAL_CRIBADO) & (rv < 1.0)),
        "asma_no_se": np.arange(len(df)),
    }


def sintomas_de(h: dict) -> dict:
    """Los siete campos del cuestionario para esta clinica."""
    return {"fiebre": "si" if h["temperatura_c"] > TEMPERATURA_CORTE_C else "no",
            **SINTOMAS_FIJOS, "asma": h["asma"]}


def _caso(df, i, rv_i, h, bloque, estrato) -> dict:
    fila = df.iloc[int(i)]
    return {
        "patientId": str(fila["patientId"]), "estrato": estrato,
        "etiqueta": int(fila["etiqueta"]), "edad": int(fila["edad"]),
        "sexo": str(fila["sexo"]), "vista": str(fila["vista"]),
        "cruda": float(fila["cruda"]), "rv_imagen": float(rv_i),
        "signos": {s: h[s] for s in SIGNOS}, "sintomas": sintomas_de(h),
        "k": int(h["k"]), "asma_real": h["asma_real"],
        "concordante": bool(bloque["concordantes"]),
        "bloque_previsto": bloque,
        "categoria_prevista": categoria_del_sistema(bloque),
    }


def _llenar(df, rv, modelo, prevalencia, rng, indices, usados, estrato, cuota):
    """Recorre `indices` (ya barajados) sorteando clinica hasta llenar `cuota`
    concordantes y `cuota` discordantes. Un candidato cuya concordancia ya
    esta llena se descarta con su clinica: el sorteo es de una sola vez."""
    pendientes = {True: cuota, False: cuota}
    casos = []
    for i in indices:
        if pendientes[True] == 0 and pendientes[False] == 0:
            break
        if int(i) in usados:
            continue
        h = sortear_caso(modelo, int(i), rng,
                         asma="no_se" if estrato == "asma_no_se" else None)
        bloque = combinacion(prevalencia, hallazgos(h), float(rv[i]))
        if pendientes[bloque["concordantes"]] == 0:
            continue
        pendientes[bloque["concordantes"]] -= 1
        usados.add(int(i))
        casos.append(_caso(df, i, rv[i], h, bloque, estrato))
    if pendientes[True] or pendientes[False]:
        raise RuntimeError(f"no hay candidatos suficientes en {estrato}: faltan {pendientes}")
    return casos


def elegir(df, rv, modelo: Modelo, prevalencia: float, semilla: int):
    """Los 24 casos con sus cuotas y los 3 de practica, reproducibles por semilla."""
    rng = np.random.default_rng(semilla)
    candidatos = estratos(df, rv)
    usados: set = set()
    casos = []
    for estrato in ESTRATOS:
        casos += _llenar(df, rv, modelo, prevalencia, rng,
                         rng.permutation(candidatos[estrato]), usados, estrato,
                         CUOTA[estrato])
    practica = []
    for estrato in PRACTICA:
        for i in rng.permutation(candidatos[estrato]):
            if int(i) in usados:
                continue
            h = sortear_caso(modelo, int(i), rng)
            bloque = combinacion(prevalencia, hallazgos(h), float(rv[i]))
            usados.add(int(i))
            practica.append(_caso(df, i, rv[i], h, bloque, estrato))
            break
    return casos, practica


def _coma(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def vineta(caso: dict) -> str:
    """La viñeta clinica en prosa breve, de usted y con tildes (§5.1)."""
    s, r = caso["signos"], caso["sintomas"]
    fiebre = "refiere fiebre" if r["fiebre"] == "si" else "no refiere fiebre"
    asma = {"si": "tiene asma", "no": "no tiene asma",
            "no_se": "no sabe si tiene asma"}[r["asma"]]
    return (
        f"Paciente de {caso['edad']} años, sexo {SEXO[caso['sexo']]}; "
        f"radiografía de tórax en proyección {caso['vista']}.\n"
        f"Refiere: {fiebre}; tos con flema; entre 3 y 7 días de evolución; "
        f"sin disnea; con dolor torácico; {asma}.\n"
        f"Exploración: temperatura {_coma(float(s['temperatura_c']))} °C; "
        f"frecuencia cardíaca {int(s['frecuencia_cardiaca'])} lpm; "
        f"crepitantes: {'sí' if s['crepitantes'] else 'no'}; "
        f"murmullo vesicular: {'disminuido' if s['murmullo_disminuido'] else 'normal'}."
    )


def linea_explorado(signos: dict) -> str:
    """El bloque EXPLORADO que redacta el nodo Desenlace (`redactarSignos`)
    para estos signos. Se usa para comprobar que el mensaje repite la viñeta."""
    return ("EXPLORADO — " + _coma(float(signos["temperatura_c"])) + " °C, "
            + str(int(signos["frecuencia_cardiaca"])) + " lpm, "
            + "crepitantes " + ("sí" if signos["crepitantes"] else "no") + ", "
            + ("murmullo disminuido" if signos["murmullo_disminuido"]
               else "murmullo normal"))


def ordenes(casos, rng: np.random.Generator) -> dict:
    """Los dos ordenes aleatorios y los 4 controles de la lectura 2 (§5.4):
    dos de positivas claras y dos de negativas claras, uno concordante y uno
    discordante en cada uno."""
    ids = [c["patientId"] for c in casos]
    controles = []
    for estrato in ("positiva_clara", "negativa_clara"):
        for concordante in (True, False):
            elegibles = [c["patientId"] for c in casos
                         if c["estrato"] == estrato and c["concordante"] == concordante]
            controles.append(elegibles[int(rng.integers(len(elegibles)))])
    return {"lectura1": [ids[i] for i in rng.permutation(len(ids))],
            "lectura2": [ids[i] for i in rng.permutation(len(ids))],
            "controles": controles}
```

- [ ] **Paso 4: Escribir `scripts/preparar_sesion.py`**

```python
# -*- coding: utf-8 -*-
"""Prepara la sesion con el medico (spec de SP5 §5.1-§5.8; plan SP5-A, D2-D3).

Dos fases:
  --fase elegir    elige los 24 + 3 casos con semilla, genera las viñetas,
                   copia las placas, y escribe casos.json (para el arnes),
                   clave.json (provisional), formulario/datos_lectura1.js y
                   dosier_lectura1.md.
  --fase mensajes  lee corpus/mensajes.json (lo deja `pruebas/reproducir_casos.py
                   --casos`), comprueba que cada mensaje repite la viñeta y que
                   la concordancia coincide con la prevista, y escribe
                   datos_lectura2.js, datos_planb.js, dosier_lectura2.md y la
                   clave definitiva: la categoria del sistema sale del bloque
                   DEL MENSAJE, que es lo que el medico ve.

Nada de lo que escribe se versiona (`pruebas/sesion/` esta en .gitignore).

ENTORNO
    RSNA_RAIZ   raiz del dataset preparado, SIN valor por defecto: las placas
                en <RSNA_RAIZ>/crudo/stage_2_train_images/<id>.dcm y los PNG
                en <RSNA_RAIZ>/png/<id>.png

USO
    python scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion --semilla 20261006
    python pruebas/reproducir_casos.py --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus
    python scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion
"""
import argparse
import json
import os
import pathlib
import shutil
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402
from copiloto_triaje.validacion import datos, oraculo, sesion  # noqa: E402
from copiloto_triaje.validacion.categoria import categoria_del_sistema  # noqa: E402

FORMULARIO = REPO / "pruebas" / "formulario"
ROTULO = "simulación semisintética — sesión H7"


def raiz_rsna() -> pathlib.Path:
    raiz = os.environ.get("RSNA_RAIZ")
    if not raiz:
        raise SystemExit("falta RSNA_RAIZ: la raíz del dataset preparado, sin valor "
                         "por defecto (spec de SP5 §6.1)")
    return pathlib.Path(raiz)


def entrada_formulario(caso: dict, mensaje, control: bool = False) -> dict:
    return {"id": caso["patientId"], "placa": f"placas/{caso['patientId']}.png",
            "vineta": sesion.vineta(caso), "mensaje": mensaje, "control": bool(control)}


def datos_js(nombre, lectura, modo, casos, practica, salida: pathlib.Path):
    contenido = {"lectura": lectura, "modo": modo, "casos": casos, "practica": practica}
    (salida / "formulario").mkdir(parents=True, exist_ok=True)
    (salida / "formulario" / nombre).write_text(
        "window.DATOS = " + json.dumps(contenido, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")


def dosier(titulo, entradas, salida: pathlib.Path, nombre):
    partes = [f"# {titulo}\n\n",
              "Simulación semisintética: la placa es real (RSNA, conjunto de prueba); "
              "la clínica es generada. Respaldo impreso del formulario, no instrumento "
              "de medida (spec de SP5 §5.8).\n"]
    for n, e in enumerate(entradas, 1):
        partes.append(f"\n## Caso {n}\n\n![placa](formulario/{e['placa']})\n\n```\n{e['vineta']}\n```\n")
        if e["mensaje"]:
            partes.append("\nMensaje del copiloto:\n\n```\n" + e["mensaje"] + "\n```\n")
    (salida / nombre).write_text("".join(partes), encoding="utf-8")


def _escribir_clave(salida, clave):
    (salida / "clave.json").write_text(json.dumps(clave, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


def fase_elegir(salida: pathlib.Path, semilla: int):
    raiz = raiz_rsna()
    df = datos.cargar_crudas()
    cal = datos.calibrador_desplegado()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int), *sesion.RHO_SESION)
    casos, practica = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, semilla)
    ordenes = sesion.ordenes(casos, np.random.default_rng(semilla + 1))

    (salida / "formulario" / "placas").mkdir(parents=True, exist_ok=True)
    for nombre in ("index.html", "formulario.js"):
        if (FORMULARIO / nombre).is_file():
            shutil.copy(FORMULARIO / nombre, salida / "formulario" / nombre)
        else:
            print(f"AVISO: falta {FORMULARIO / nombre}; el formulario se copia cuando exista")
    for c in casos + practica:
        png = raiz / "png" / f"{c['patientId']}.png"
        if not png.is_file():
            raise SystemExit(f"no existe {png}")
        shutil.copy(png, salida / "formulario" / "placas" / png.name)

    (salida / "casos.json").write_text(json.dumps([
        {"patientId": c["patientId"],
         "ruta_dcm": str(raiz / "crudo" / "stage_2_train_images" / f"{c['patientId']}.dcm"),
         "signos": c["signos"], "sintomas": c["sintomas"], "cruda": c["cruda"]}
        for c in casos + practica], ensure_ascii=False, indent=1), encoding="utf-8")

    por_id = {c["patientId"]: c for c in casos}
    lectura1 = [entrada_formulario(por_id[i], None) for i in ordenes["lectura1"]]
    practica_f = [entrada_formulario(c, None) for c in practica]
    datos_js("datos_lectura1.js", 1, "simple", lectura1, practica_f, salida)
    dosier("Dosier de la lectura 1 (sin copiloto) — simulación semisintética",
           practica_f + lectura1, salida, "dosier_lectura1.md")
    _escribir_clave(salida, {
        "rotulo": ROTULO, "semilla": semilla, "prevalencia_sesion": PREVALENCIA_COHORTE,
        "rho_sesion": list(sesion.RHO_SESION), "ordenes": ordenes,
        "casos": casos, "practica": practica, "fase": "elegir"})
    print(f"{len(casos)} casos y {len(practica)} de práctica en {salida}.")
    print(f"Ahora: python pruebas/reproducir_casos.py --casos {salida / 'casos.json'} "
          f"--salida {salida / 'corpus'}")


def fase_mensajes(salida: pathlib.Path):
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    mensajes = json.loads((salida / "corpus" / "mensajes.json").read_text(encoding="utf-8"))
    problemas = []
    for c in clave["casos"] + clave["practica"]:
        m = mensajes.get(c["patientId"])
        if m is None:
            problemas.append(f"{c['patientId']}: sin mensaje")
            continue
        if m.get("error") or m.get("fallo"):
            problemas.append(f"{c['patientId']}: {m.get('error') or m.get('fallo')}")
            continue
        if sesion.linea_explorado(c["signos"]) not in m["texto"]:
            problemas.append(f"{c['patientId']}: EXPLORADO no repite la viñeta")
            continue
        bloque = (m.get("resultado") or {}).get("combinacion")
        if not bloque:
            problemas.append(f"{c['patientId']}: el mensaje no lleva combinación")
            continue
        if bool(bloque["concordantes"]) != c["concordante"]:
            problemas.append(f"{c['patientId']}: concordancia {bloque['concordantes']} "
                             f"≠ prevista {c['concordante']}")
            continue
        c["bloque"] = bloque
        c["categoria"] = categoria_del_sistema(bloque)
        c["mensaje"] = m["texto"]
        c["con_bots"] = m.get("con_bots")
    if problemas:
        raise SystemExit("mensajes que no sirven; no se escribe la lectura 2:\n  "
                         + "\n  ".join(problemas))
    por_id = {c["patientId"]: c for c in clave["casos"]}
    controles = set(clave["ordenes"]["controles"])
    lectura2 = [entrada_formulario(por_id[i], None if i in controles else por_id[i]["mensaje"],
                                   control=i in controles)
                for i in clave["ordenes"]["lectura2"]]
    planb = [entrada_formulario(por_id[i], por_id[i]["mensaje"])
             for i in clave["ordenes"]["lectura1"]]
    practica_f = [entrada_formulario(c, c["mensaje"]) for c in clave["practica"]]
    datos_js("datos_lectura2.js", 2, "simple", lectura2, practica_f, salida)
    datos_js("datos_planb.js", 1, "secuencial", planb, practica_f, salida)
    dosier("Dosier de la lectura 2 (con copiloto) — simulación semisintética",
           practica_f + lectura2, salida, "dosier_lectura2.md")
    clave["fase"] = "mensajes"
    _escribir_clave(salida, clave)
    print("lectura 2 y plan B listos; la clave lleva el bloque y la categoría "
          "del mensaje de cada caso")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fase", choices=("elegir", "mensajes"), required=True)
    p.add_argument("--salida", default=str(REPO / "pruebas" / "sesion"))
    p.add_argument("--semilla", type=int, default=20261006)
    args = p.parse_args()
    salida = pathlib.Path(args.salida)
    if args.fase == "elegir":
        fase_elegir(salida, args.semilla)
    else:
        fase_mensajes(salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Paso 5: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_sesion.py -v`
Esperado: 13 PASS. (`test_el_umbral_de_cribado_es_el_del_selector_de_casos`
importa `pruebas.seleccionar_casos`, que carga torch: unos segundos.) Las
pruebas de `fase_elegir` avisan de que falta el formulario si la Tarea 8 no
está hecha todavía; eso es un `print`, no un fallo.

- [ ] **Paso 6: Commit**

```bash
git add src/copiloto_triaje/validacion/sesion.py scripts/preparar_sesion.py tests/test_sesion.py
git commit -m "feat(sesion): eleccion de casos por estratos y concordancia, viñetas y preparar_sesion (SP5-A T7)"
```

---

### Tarea 8: El formulario

**Ficheros:**
- Crear: `pruebas/formulario/formulario.js`, `pruebas/formulario/index.html`
- Prueba: `tests/formulario.mjs` (node) y `tests/test_formulario_js.py` (la envuelve en la suite)

**Interfaces:**
- Consume: `datos_lectura<N>.js` de la Tarea 7 (`window.DATOS = {lectura, modo, casos: [{id, placa, vineta, mensaje, control}], practica: [...]}`).
- Produce: en `formulario.js`, el objeto `Formulario` con `BANDAS`, `NOTAS`, `COLUMNAS`,
  `nuevoEstado(datos)`, `casoActual(estado)`, `terminado(estado)`, `abrir(estado, ahora)`,
  `enviar(estado, respuesta, ahora) -> {estado, revelar}`, `enviarConAyuda(estado, respuesta, ahora)`,
  `aCSV(estado) -> string`; y el CSV con las columnas
  `lectura,orden,id,practica,control,banda,porcentaje,abierto_en,enviado_en,segundos,banda_con,porcentaje_con,segundos_con,correccion,utilidad,lenguaje,comentario`
  (`practica` y `control` como `true`/`false`; los tiempos en segundos con decimales; las notas vacías cuando no aplican). La Tarea 9 lee ese CSV.

- [ ] **Paso 1: Escribir la prueba que falla**

`tests/formulario.mjs`:

```js
// node tests/formulario.mjs — la lógica del formulario de la sesión, sin navegador.
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { Formulario } = require("../pruebas/formulario/formulario.js");

let ok = 0;
function prueba(nombre, fn) { fn(); ok += 1; console.log("OK  " + nombre); }

const datos = (modo) => ({
  lectura: 2, modo,
  practica: [{ id: "pr-1", placa: "placas/pr-1.png", vineta: "práctica", mensaje: "M0", control: false }],
  casos: [
    { id: "c-1", placa: "placas/c-1.png", vineta: "v1", mensaje: "M1", control: false },
    { id: "c-2", placa: "placas/c-2.png", vineta: "v2", mensaje: null, control: true },
  ],
});
const conNotas = { banda: "alta", porcentaje: 80, correccion: 5, utilidad: 4, lenguaje: 5 };

prueba("la práctica va primero y el CSV la marca", () => {
  const e = Formulario.nuevoEstado(datos("simple"));
  assert.equal(Formulario.casoActual(e).id, "pr-1");
  Formulario.abrir(e, 1000);
  Formulario.enviar(e, conNotas, 4000);
  assert.equal(e.fase, "casos");
  assert.equal(Formulario.casoActual(e).id, "c-1");
  assert.equal(e.respuestas[0].practica, true);
  assert.equal(e.respuestas[0].segundos, 3);
});

prueba("el tiempo va de abrir a enviar, y sin abrir no se envía", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  assert.throws(() => Formulario.enviar(e, { banda: "baja", porcentaje: 5 }, 10), /no se abrió/);
  Formulario.abrir(e, 100);
  Formulario.abrir(e, 500);                       // abrir dos veces no reinicia el reloj
  Formulario.enviar(e, conNotas, 2600);
  assert.equal(e.respuestas[0].segundos, 2.5);
  assert.equal(e.respuestas[0].abierto_en, 100);
  assert.equal(e.respuestas[0].enviado_en, 2600);
});

prueba("con mensaje en modo simple las notas son obligatorias; en un control, no", () => {
  const e = Formulario.nuevoEstado({ lectura: 2, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 80 }, 1000), /notas/);
  Formulario.enviar(e, conNotas, 1000);
  assert.equal(e.respuestas[0].correccion, 5);
  Formulario.abrir(e, 2000);
  Formulario.enviar(e, { banda: "baja", porcentaje: 10 }, 3000);   // c-2 es control: sin notas
  assert.equal(e.respuestas[1].control, true);
  assert.equal(e.respuestas[1].correccion, "");
  assert.equal(Formulario.terminado(e), true);
  assert.equal(Formulario.casoActual(e), null);
});

prueba("no hay vuelta atrás: el índice solo crece", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  assert.equal(typeof Formulario.retroceder, "undefined");
  Formulario.abrir(e, 0); Formulario.enviar(e, conNotas, 1);
  assert.equal(e.indice, 1);
  Formulario.abrir(e, 2); Formulario.enviar(e, { banda: "baja", porcentaje: 0 }, 3);
  assert.equal(e.fase, "fin");
  assert.throws(() => Formulario.enviar(e, conNotas, 4), /no hay caso/);
});

prueba("modo secuencial: primero sin ayuda, luego se revela y se pide la segunda respuesta", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "secuencial", practica: [], casos: datos("secuencial").casos });
  Formulario.abrir(e, 0);
  const r = Formulario.enviar(e, { banda: "intermedia", porcentaje: 40 }, 30000);
  assert.equal(r.revelar, true);
  assert.equal(e.indice, 0);                          // el caso no ha avanzado
  assert.throws(() => Formulario.enviar(e, conNotas, 31000), /falta la respuesta/);
  Formulario.enviarConAyuda(e, { banda: "alta", porcentaje: 85, correccion: 4, utilidad: 5, lenguaje: 4 }, 45000);
  const f = e.respuestas[0];
  assert.equal(f.banda, "intermedia"); assert.equal(f.porcentaje, 40); assert.equal(f.segundos, 30);
  assert.equal(f.banda_con, "alta"); assert.equal(f.porcentaje_con, 85); assert.equal(f.segundos_con, 15);
  assert.equal(f.utilidad, 5);
  assert.equal(e.indice, 1);
  Formulario.abrir(e, 50000);
  const r2 = Formulario.enviar(e, { banda: "baja", porcentaje: 5 }, 51000);   // c-2 no tiene mensaje
  assert.equal(r2.revelar, false);
  assert.equal(e.fase, "fin");
});

prueba("el CSV lleva las columnas en orden y escapa comas, comillas y saltos", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  Formulario.enviar(e, Object.assign({}, conNotas, { comentario: 'dudo, "quizá"\nver base' }), 1500);
  const lineas = Formulario.aCSV(e).split("\n");
  assert.equal(lineas[0], Formulario.COLUMNAS.join(","));
  assert.equal(lineas[0].split(",").length, 17);
  assert.ok(lineas[1].startsWith("1,1,c-1,false,false,alta,80,0,1500,1.5,,,,5,4,5,"));
  assert.ok(lineas[1].endsWith('"dudo, ""quizá""'));
  assert.equal(lineas[2], "ver base\"");
});

prueba("banda o porcentaje inválidos se rechazan sin avanzar", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  assert.throws(() => Formulario.enviar(e, { banda: "media", porcentaje: 50, correccion: 3, utilidad: 3, lenguaje: 3 }, 1), /banda/);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 101, correccion: 3, utilidad: 3, lenguaje: 3 }, 1), /porcentaje/);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 7.5, correccion: 3, utilidad: 3, lenguaje: 3 }, 1), /porcentaje/);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 70, correccion: 0, utilidad: 3, lenguaje: 3 }, 1), /notas/);
  assert.equal(e.indice, 0);
  assert.equal(e.respuestas.length, 0);
});

console.log(ok + " OK");
```

`tests/test_formulario_js.py`:

```python
"""La lógica del formulario de la sesión vive en JavaScript y la prueba `node`;
esto la mete en la suite de pytest, como el redactor."""
import pathlib
import shutil
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_la_logica_del_formulario_pasa_sus_pruebas_en_node():
    node = shutil.which("node")
    assert node, "hace falta node: el redactor y las pruebas de los nodos ya lo exigen"
    salida = subprocess.run([node, str(REPO / "tests" / "formulario.mjs")],
                            capture_output=True, text=True, encoding="utf-8")
    assert salida.returncode == 0, salida.stderr
    assert salida.stdout.strip().endswith("7 OK"), salida.stdout


def test_el_html_carga_la_logica_y_los_datos_por_lectura():
    html = (REPO / "pruebas" / "formulario" / "index.html").read_text(encoding="utf-8")
    assert '<script src="formulario.js"></script>' in html
    assert "datos_lectura" in html and "datos_planb.js" in html
    assert "opacidad o infiltrado compatible con neumonía" in html
    assert "no se puede volver atrás" in html
    assert "simulación semisintética" in html
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

Run: `node tests/formulario.mjs`
Esperado: error `Cannot find module '../pruebas/formulario/formulario.js'`.

- [ ] **Paso 3: Escribir `pruebas/formulario/formulario.js`**

```js
// Lógica del formulario de la sesión con el médico (spec de SP5 §5.2, §5.4, §5.8).
// Sin DOM a propósito: `tests/formulario.mjs` la carga en node y `index.html`
// solo pinta el estado y llama a estas funciones.
//
// Lo que este fichero hace cumplir:
//   - un caso por pantalla y sin volver atrás: no existe ninguna función que
//     retroceda; `indice` solo crece;
//   - el tiempo de triaje va de abrir el caso a enviar la banda, con el reloj
//     que se le pasa (Date.now() en el navegador; un contador en las pruebas);
//   - en modo "simple" (lecturas 1 y 2) el mensaje, si lo hay, se muestra con
//     el caso y las tres notas se piden en el mismo envío; en modo
//     "secuencial" (plan B) el mensaje se revela DESPUÉS de enviar la banda
//     sin ayuda y se pide una segunda respuesta con las notas;
//   - los casos de práctica van primero y salen en el CSV marcados.
(function (raiz) {
  "use strict";

  const BANDAS = ["baja", "intermedia", "alta"];
  const NOTAS = ["correccion", "utilidad", "lenguaje"];
  const COLUMNAS = ["lectura", "orden", "id", "practica", "control", "banda", "porcentaje",
    "abierto_en", "enviado_en", "segundos", "banda_con", "porcentaje_con", "segundos_con",
    "correccion", "utilidad", "lenguaje", "comentario"];

  function nuevoEstado(datos) {
    if (!datos || !Array.isArray(datos.casos) || !Array.isArray(datos.practica)) {
      throw new Error("datos sin casos o sin práctica");
    }
    return {
      lectura: datos.lectura,
      modo: datos.modo === "secuencial" ? "secuencial" : "simple",
      practica: datos.practica.map((c) => Object.assign({}, c, { practica: true })),
      casos: datos.casos.map((c) => Object.assign({}, c, { practica: false })),
      fase: datos.practica.length ? "practica" : "casos",
      indice: 0, abierto_en: null, revelado_en: null, pendiente: null, respuestas: [],
    };
  }

  function lista(e) { return e.fase === "practica" ? e.practica : e.casos; }
  function casoActual(e) { return e.fase === "fin" ? null : (lista(e)[e.indice] || null); }
  function terminado(e) { return e.fase === "fin"; }

  function abrir(e, ahora) {
    if (e.fase !== "fin" && e.abierto_en === null) { e.abierto_en = ahora; }
    return e;
  }

  function validarBanda(r) {
    if (!BANDAS.includes(r.banda)) { throw new Error("elija una banda: baja, intermedia o alta"); }
    const p = Number(r.porcentaje);
    if (!Number.isInteger(p) || p < 0 || p > 100) { throw new Error("el porcentaje es un entero de 0 a 100"); }
  }

  function validarNotas(r) {
    for (const k of NOTAS) {
      const v = Number(r[k]);
      if (!Number.isInteger(v) || v < 1 || v > 5) { throw new Error("las tres notas van de 1 a 5"); }
    }
  }

  function filaBase(e, c, r, ahora) {
    return {
      lectura: e.lectura, orden: e.indice + 1, id: c.id, practica: c.practica, control: !!c.control,
      banda: r.banda, porcentaje: Number(r.porcentaje),
      abierto_en: e.abierto_en, enviado_en: ahora, segundos: (ahora - e.abierto_en) / 1000,
      banda_con: "", porcentaje_con: "", segundos_con: "",
      correccion: "", utilidad: "", lenguaje: "", comentario: r.comentario || "",
    };
  }

  function enviar(e, r, ahora) {
    const c = casoActual(e);
    if (!c) { throw new Error("no hay caso abierto: la lectura terminó"); }
    if (e.pendiente) { throw new Error("falta la respuesta con el mensaje"); }
    if (e.abierto_en === null) { throw new Error("el caso no se abrió"); }
    validarBanda(r);
    const fila = filaBase(e, c, r, ahora);
    if (c.mensaje && e.modo === "simple") {
      validarNotas(r);
      for (const k of NOTAS) { fila[k] = Number(r[k]); }
    }
    if (c.mensaje && e.modo === "secuencial") {
      e.pendiente = fila;
      e.revelado_en = ahora;
      return { estado: e, revelar: true };
    }
    return avanzar(e, fila);
  }

  function enviarConAyuda(e, r, ahora) {
    if (!e.pendiente) { throw new Error("no hay mensaje revelado"); }
    validarBanda(r);
    validarNotas(r);
    const fila = e.pendiente;
    fila.banda_con = r.banda;
    fila.porcentaje_con = Number(r.porcentaje);
    fila.segundos_con = (ahora - e.revelado_en) / 1000;
    for (const k of NOTAS) { fila[k] = Number(r[k]); }
    if (r.comentario) { fila.comentario = r.comentario; }
    e.pendiente = null;
    e.revelado_en = null;
    return avanzar(e, fila);
  }

  function avanzar(e, fila) {
    e.respuestas.push(fila);
    e.abierto_en = null;
    e.indice += 1;
    if (e.indice >= lista(e).length) {
      if (e.fase === "practica" && e.casos.length) { e.fase = "casos"; e.indice = 0; }
      else { e.fase = "fin"; }
    }
    return { estado: e, revelar: false };
  }

  function celda(v) {
    const s = (v === null || v === undefined) ? "" : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function aCSV(e) {
    const lineas = [COLUMNAS.join(",")];
    for (const f of e.respuestas) { lineas.push(COLUMNAS.map((k) => celda(f[k])).join(",")); }
    return lineas.join("\n") + "\n";
  }

  raiz.Formulario = { BANDAS, NOTAS, COLUMNAS, nuevoEstado, casoActual, terminado, abrir, enviar, enviarConAyuda, aCSV };
})(typeof module !== "undefined" && module.exports ? module.exports : window);
```

- [ ] **Paso 4: Escribir `pruebas/formulario/index.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sesión H7 — formulario (simulación semisintética)</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 16px; max-width: 1200px; }
  .fila { display: flex; gap: 24px; flex-wrap: wrap; }
  img { max-width: 640px; width: 100%; border: 1px solid #999; background: #000; }
  pre { white-space: pre-wrap; background: #f4f4f4; padding: 12px; border-radius: 6px; }
  fieldset { margin: 12px 0; }
  label { margin-right: 12px; }
  .aviso { color: #a00; min-height: 1.2em; }
  button { font-size: 1rem; padding: 8px 16px; }
</style>
</head>
<body>
<h1>Sesión H7 — simulación semisintética</h1>
<p id="cabecera"></p>
<div id="caso" hidden>
  <div class="fila">
    <div><img id="placa" alt="radiografía de tórax"></div>
    <div style="flex: 1; min-width: 320px">
      <h2 id="rotulo"></h2>
      <pre id="vineta"></pre>
      <div id="bloque-mensaje" hidden>
        <h3>Mensaje del copiloto</h3>
        <pre id="mensaje"></pre>
      </div>
      <form id="formulario">
        <fieldset>
          <legend>Probabilidad de que la placa muestre una opacidad o infiltrado compatible con neumonía</legend>
          <label><input type="radio" name="banda" value="baja"> baja (&lt; 20 %)</label>
          <label><input type="radio" name="banda" value="intermedia"> intermedia (20-70 %)</label>
          <label><input type="radio" name="banda" value="alta"> alta (&gt; 70 %)</label>
          <br>
          <label>Porcentaje (entero de 0 a 100): <input type="number" name="porcentaje" min="0" max="100" step="1" required></label>
        </fieldset>
        <fieldset id="notas" hidden>
          <legend>El pre-informe, de 1 (peor) a 5 (mejor)</legend>
          <label>Corrección <select name="correccion"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label>
          <label>Utilidad <select name="utilidad"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label>
          <label>Lenguaje <select name="lenguaje"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label>
        </fieldset>
        <label>Comentario (opcional)<br><textarea name="comentario" rows="3" cols="60"></textarea></label>
        <p id="error" class="aviso"></p>
        <button type="submit">Enviar</button>
      </form>
    </div>
  </div>
</div>
<div id="fin" hidden>
  <h2>Lectura terminada</h2>
  <p>Gracias. Descargue el CSV y envíelo al equipo.</p>
  <button id="descargar">Descargar CSV</button>
</div>
<script src="formulario.js"></script>
<script>
(function () {
  // ?lectura=1 | 2 | planb -> datos_lectura1.js | datos_lectura2.js | datos_planb.js
  var params = new URLSearchParams(location.search);
  var lectura = params.get("lectura") || "1";
  var fichero = lectura === "planb" ? "datos_planb.js" : "datos_lectura" + lectura + ".js";
  var clave = "sesion-h7-" + lectura;
  var estado = null;

  function guardar() { try { localStorage.setItem(clave, JSON.stringify(estado)); } catch (e) {} }
  function recuperar() { try { var t = localStorage.getItem(clave); return t ? JSON.parse(t) : null; } catch (e) { return null; } }

  function arrancar() {
    var previo = recuperar();
    if (previo && previo.lectura === window.DATOS.lectura && previo.fase !== "fin") {
      // Se retoma donde se cerró; el caso a medias vuelve a empezar y su reloj también.
      estado = previo; estado.abierto_en = null; estado.pendiente = null; estado.revelado_en = null;
    } else {
      estado = Formulario.nuevoEstado(window.DATOS);
    }
    pintar();
  }

  function pintar() {
    var c = Formulario.casoActual(estado);
    document.getElementById("cabecera").textContent =
      "Lectura " + estado.lectura + (estado.modo === "secuencial" ? " (plan B)" : "") +
      ". Un caso por pantalla; no se puede volver atrás. La clínica de cada caso es simulada.";
    if (!c) {
      document.getElementById("caso").hidden = true;
      document.getElementById("fin").hidden = false;
      return;
    }
    var total = c.practica ? estado.practica.length : estado.casos.length;
    document.getElementById("caso").hidden = false;
    document.getElementById("rotulo").textContent = (c.practica ? "Práctica " : "Caso ") + (estado.indice + 1) + " de " + total;
    document.getElementById("placa").src = c.placa;
    document.getElementById("vineta").textContent = c.vineta;
    var conMensaje = !!c.mensaje && (estado.modo === "simple" || !!estado.pendiente);
    document.getElementById("bloque-mensaje").hidden = !conMensaje;
    document.getElementById("mensaje").textContent = c.mensaje || "";
    document.getElementById("notas").hidden = !conMensaje;
    document.getElementById("formulario").reset();
    document.getElementById("error").textContent = "";
    Formulario.abrir(estado, Date.now());
  }

  document.getElementById("formulario").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var f = new FormData(ev.target);
    var r = { banda: f.get("banda"), porcentaje: f.get("porcentaje"), comentario: f.get("comentario") || "",
              correccion: f.get("correccion"), utilidad: f.get("utilidad"), lenguaje: f.get("lenguaje") };
    try {
      var res = estado.pendiente
        ? Formulario.enviarConAyuda(estado, r, Date.now())
        : Formulario.enviar(estado, r, Date.now());
      guardar();
      pintar();
      if (res.revelar) { window.scrollTo(0, 0); }
    } catch (e) {
      document.getElementById("error").textContent = e.message;
    }
  });

  document.getElementById("descargar").addEventListener("click", function () {
    var blob = new Blob([Formulario.aCSV(estado)], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (lectura === "planb" ? "planb" : "lectura" + lectura) + ".csv";
    a.click();
  });

  var s = document.createElement("script");
  s.src = fichero;
  s.onload = arrancar;
  s.onerror = function () { document.getElementById("cabecera").textContent = "No se encuentra " + fichero + " junto a este fichero."; };
  document.head.appendChild(s);
})();
</script>
</body>
</html>
```

- [ ] **Paso 5: Correr las pruebas y ver que pasan**

Run: `node tests/formulario.mjs` → Esperado: siete líneas `OK ...` y `7 OK`.
Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_formulario_js.py -v` → Esperado: 2 PASS.

Abre `pruebas/formulario/index.html?lectura=1` en un navegador **con un
`datos_lectura1.js` de prueba al lado** (por ejemplo el que deja
`tests/test_sesion.py` en su `tmp_path`, o uno escrito a mano con dos casos y
PNG cualesquiera) y comprueba a ojo: la placa, la viñeta, las tres bandas, el
porcentaje, que sin banda no envía, que tras el último caso aparece el botón y
descarga `lectura1.csv`. En `?lectura=planb` con un `datos_planb.js`, que el
mensaje aparece solo tras la primera respuesta.

- [ ] **Paso 6: Commit**

```bash
git add pruebas/formulario/ tests/formulario.mjs tests/test_formulario_js.py
git commit -m "feat(sesion): formulario HTML local con logica probada en node (SP5-A T8)"
```

---

### Tarea 9: Kappas, tiempos, análisis de la sesión y acta

**Ficheros:**
- Crear: `src/copiloto_triaje/validacion/concordancia.py`
- Crear: `scripts/analizar_sesion.py`
- Crear: `docs/validacion-semisintetica/acta-h7-plantilla.md`
- Prueba: `tests/test_concordancia.py`

**Interfaces:**
- Consume: `clave.json` de la Tarea 7 (`casos[*].categoria` con `primaria, punto_medio, independencia, conservador, cruza`;
  `casos[*].bloque` con `minima, maxima`; `casos[*].estrato`; `ordenes.controles`) y los CSV de la Tarea 8.
- Produce: en `concordancia.py`: `CATEGORIAS`, `TEXTO_FIJADO`, `B_BOOTSTRAP = 2000`, `SEMILLA_BOOTSTRAP = 20261013`;
  `kappa(a, b, c=3, tipo="lineal") -> dict(kappa, ee, ic95, po, pe, n)`;
  `kappa_binario(a, b, positiva="alta") -> dict`; `bca(datos, estadistico, B, semilla, alfa) -> [lo, hi]`;
  `kappa_con_intervalos(a, b, tipo) -> dict` (añade `ic95_bca`; `tipo` ∈ `lineal | ninguno | binario_alta`);
  `acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict`;
  `razon_de_tiempos(t_sin, t_con) -> dict`; `leer_csv(ruta) -> list[dict]` (tipos convertidos);
  `analizar(clave, lectura1, lectura2=None, planb=None) -> dict` (la estructura de `sesion.json`);
  `valores_para_acta(sesion, clave) -> dict[str, str]`; `rellenar_acta(plantilla, valores) -> str`.
  En `scripts/analizar_sesion.py`: la línea de comandos.

- [ ] **Paso 1: Escribir la prueba que falla**

`tests/test_concordancia.py`:

```python
"""Kappas, intervalos, acuerdo continuo, tiempos y el análisis de la sesión
(spec de SP5 §5.4-§5.5, §8, §11.4; plan SP5-A D9).

Los kappas se comprueban contra un ejemplo calculado a mano de 8 casos:
  a = baja baja alta alta inter inter baja alta
  b = baja inter alta alta inter baja baja alta
  acuerdo bruto 6/8; marginales 3/2/3 en los dos; Cohen = 0,6190;
  ponderado lineal: (b,inter) e (inter,b) pesan 0,5 → po 0,875, pe 0,53125 → 0,7333.
"""
import csv
import json
import pathlib

import numpy as np
import pytest

from copiloto_triaje.validacion import concordancia as cc

A = ["baja", "baja", "alta", "alta", "intermedia", "intermedia", "baja", "alta"]
B = ["baja", "intermedia", "alta", "alta", "intermedia", "baja", "baja", "alta"]


def test_kappa_de_cohen_y_ponderado_lineal_del_ejemplo_a_mano():
    ia, ib = cc.indices(A), cc.indices(B)
    cohen = cc.kappa(ia, ib, 3, "ninguno")
    lineal = cc.kappa(ia, ib, 3, "lineal")
    assert cohen["kappa"] == pytest.approx(0.6190, abs=1e-4)
    assert cohen["po"] == pytest.approx(0.75) and cohen["pe"] == pytest.approx(0.34375)
    assert lineal["kappa"] == pytest.approx(0.7333, abs=1e-4)
    assert lineal["po"] == pytest.approx(0.875) and lineal["pe"] == pytest.approx(0.53125)
    assert cohen["ee"] > 0 and lineal["ee"] > 0
    assert cohen["ic95"][0] < cohen["kappa"] < cohen["ic95"][1]
    assert cc.kappa(ib, ia, 3, "lineal")["kappa"] == pytest.approx(lineal["kappa"])


def test_el_acuerdo_perfecto_da_kappa_1_con_error_tipico_0():
    ia = cc.indices(A)
    r = cc.kappa(ia, ia, 3, "lineal")
    assert r["kappa"] == pytest.approx(1.0) and r["ee"] == pytest.approx(0.0)


def test_kappa_binario_en_alta():
    r = cc.kappa_binario(A, B)
    assert r["kappa"] == pytest.approx(1.0)          # coinciden en todas las «alta»
    assert cc.kappa_binario(A, ["baja"] * 8)["kappa"] == pytest.approx(0.0)


def test_los_intervalos_bca_contienen_la_estimacion_y_son_reproducibles():
    r = cc.kappa_con_intervalos(A * 3, B * 3, "lineal")
    assert r["ic95_bca"][0] <= r["kappa"] <= r["ic95_bca"][1]
    assert r["ic95_bca"] == cc.kappa_con_intervalos(A * 3, B * 3, "lineal")["ic95_bca"]
    assert r["n"] == 24
    binario = cc.kappa_con_intervalos(A * 3, B * 3, "binario_alta")
    assert binario["kappa"] == pytest.approx(1.0)


def test_bca_sobre_una_media_conocida():
    datos = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    lo, hi = cc.bca(datos, lambda d: float(np.mean(d)), B=500, semilla=1)
    assert lo < 4.5 < hi and 2.0 < lo and hi < 7.0
    assert cc.bca(np.ones(10), lambda d: float(np.mean(d))) == [1.0, 1.0]


def test_acuerdo_continuo_acota_0_y_100_y_mide_spearman():
    pct = [0, 10, 40, 70, 100]
    p = [0.02, 0.15, 0.45, 0.7, 0.95]
    r = cc.acuerdo_continuo(pct, p, minima=[0.0, 0.1, 0.3, 0.6, 0.9], maxima=[0.05, 0.2, 0.5, 0.8, 1.0])
    assert r["spearman"] == pytest.approx(1.0)
    assert r["acotados_0_o_100"] == 2
    assert np.isfinite(r["diferencia_media_log_odds"]) and r["n"] == 5
    assert r["fraccion_dentro_de_la_horquilla"] == pytest.approx(1.0)


def test_razon_de_tiempos_pareada():
    r = cc.razon_de_tiempos([60, 80, 100, 120], [30, 40, 50, 60])
    assert r["razon_medias_geometricas"] == pytest.approx(0.5)
    assert r["reduccion_pct"] == pytest.approx(50.0)
    assert r["n"] == 4 and r["ic95_bca"][0] <= 0.5 <= r["ic95_bca"][1]
    with pytest.raises(ValueError):
        cc.razon_de_tiempos([1, 2], [1])


# --------------------------------------------------------------------------
# El análisis entero sobre una sesión fabricada con valores conocidos.
# --------------------------------------------------------------------------
BANDAS_SISTEMA = (["baja"] * 8 + ["alta"] * 8 + ["intermedia"] * 4 + ["intermedia"] * 4)
ESTRATOS = (["positiva_clara"] * 8 + ["negativa_clara"] * 8
            + ["banda_contradictoria"] * 4 + ["asma_no_se"] * 4)
PUNTO_MEDIO = {"baja": 0.08, "intermedia": 0.45, "alta": 0.9}


def _clave():
    casos = []
    for i in range(24):
        banda = BANDAS_SISTEMA[i]
        pm = PUNTO_MEDIO[banda]
        casos.append({"patientId": f"c-{i:02d}", "estrato": ESTRATOS[i], "concordante": i % 2 == 0,
                      "bloque": {"minima": pm - 0.05, "maxima": pm + 0.05},
                      "categoria": {"primaria": banda, "punto_medio": pm, "independencia": banda,
                                    "conservador": banda, "cruza": banda, "cruza_limite": False}})
    return {"rotulo": "simulación semisintética — sesión H7", "casos": casos,
            "ordenes": {"lectura1": [c["patientId"] for c in casos],
                        "lectura2": [c["patientId"] for c in casos][::-1],
                        "controles": ["c-00", "c-01", "c-08", "c-09"]}}


def _csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cc.COLUMNAS_CSV)
        w.writeheader()
        w.writerows(filas)


def _fila(lectura, orden, caso, banda, pct, segundos, control=False, notas=None, banda_con="", pct_con="", seg_con=""):
    n = notas or {}
    return {"lectura": lectura, "orden": orden, "id": caso["patientId"], "practica": "false",
            "control": "true" if control else "false", "banda": banda, "porcentaje": pct,
            "abierto_en": 1760000000000 + orden * 100000, "enviado_en": 1760000000000 + orden * 100000 + int(segundos * 1000),
            "segundos": segundos, "banda_con": banda_con, "porcentaje_con": pct_con, "segundos_con": seg_con,
            "correccion": n.get("correccion", ""), "utilidad": n.get("utilidad", ""), "lenguaje": n.get("lenguaje", ""),
            "comentario": "dudoso" if banda != caso["categoria"]["primaria"] else ""}


def test_analizar_una_sesion_fabricada(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    # Lectura 1: el médico coincide en 20 y discrepa en 4 (dos de ellas a la banda vecina).
    discrepa = {"c-02": "intermedia", "c-10": "intermedia", "c-17": "baja", "c-21": "alta"}
    l1 = [_fila(1, i + 1, casos[pid], discrepa.get(pid, casos[pid]["categoria"]["primaria"]),
                int(casos[pid]["categoria"]["punto_medio"] * 100), 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    # Lectura 2: con mensaje en 20 (mitad de tiempo, notas 5/4/3) y 4 controles (mismo tiempo).
    controles = set(clave["ordenes"]["controles"])
    l2 = []
    for i, pid in enumerate(clave["ordenes"]["lectura2"]):
        c = casos[pid]
        if pid in controles:
            l2.append(_fila(2, i + 1, c, c["categoria"]["primaria"], 50, 60.0, control=True))
        else:
            l2.append(_fila(2, i + 1, c, c["categoria"]["primaria"], 50, 30.0,
                            notas={"correccion": 5, "utilidad": 4, "lenguaje": 3}))
    _csv(tmp_path / "lectura1.csv", l1)
    _csv(tmp_path / "lectura2.csv", l2)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "lectura1.csv"), cc.leer_csv(tmp_path / "lectura2.csv"))

    assert s["n"] == 24 and s["categoria_de"] == "mensaje"
    assert s["kappa"]["ponderado_lineal"]["n"] == 24
    assert 0.6 < s["kappa"]["ponderado_lineal"]["kappa"] < 1.0
    assert s["kappa"]["cohen"]["kappa"] < s["kappa"]["ponderado_lineal"]["kappa"]
    for nombre in ("ponderado_lineal", "cohen", "binario_alta"):
        k = s["kappa"][nombre]
        assert k["ic95"][0] <= k["kappa"] <= k["ic95"][1]
        assert k["ic95_bca"][0] <= k["kappa"] <= k["ic95_bca"][1]
    assert set(s["sensibilidad_categoria"]) == {"independencia", "conservador", "cruza"}
    assert len(s["desacuerdos"]) == 4
    assert {d["id"] for d in s["desacuerdos"]} == set(discrepa)
    assert all(d["comentario"] == "dudoso" for d in s["desacuerdos"])
    assert s["acuerdo_continuo"]["n"] == 24 and s["acuerdo_continuo"]["spearman"] > 0.9
    l2s = s["lectura2"]
    assert l2s["n_con_mensaje"] == 20 and l2s["n_controles"] == 4
    assert l2s["kappa_con_mensaje"]["kappa"] == pytest.approx(1.0)
    assert l2s["cambios_de_banda"] == 4          # los 4 discrepantes de la lectura 1 vuelven a la del sistema
    assert l2s["utilidad"]["correccion"]["media"] == pytest.approx(5.0)
    assert l2s["utilidad"]["lenguaje"]["media"] == pytest.approx(3.0)
    assert l2s["tiempo"]["medido"] is True
    assert l2s["tiempo"]["razon_medias_geometricas"] == pytest.approx(0.5)
    assert l2s["tiempo"]["controles"]["media_geometrica"] == pytest.approx(1.0)
    assert l2s["tiempo"]["razon_corregida_por_releer"] == pytest.approx(0.5)
    assert s["plan_b"] is None
    assert s["texto_fijado"] == cc.TEXTO_FIJADO


def test_analizar_el_plan_b(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    filas = [_fila(1, i + 1, casos[pid], casos[pid]["categoria"]["primaria"],
                   int(casos[pid]["categoria"]["punto_medio"] * 100), 40.0,
                   notas={"correccion": 4, "utilidad": 4, "lenguaje": 4},
                   banda_con="alta" if i < 3 else casos[pid]["categoria"]["primaria"], pct_con=80, seg_con=20.0)
             for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "planb.csv", filas)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "planb.csv"), planb=cc.leer_csv(tmp_path / "planb.csv"))
    assert s["kappa"]["ponderado_lineal"]["kappa"] == pytest.approx(1.0)
    assert s["lectura2"] is None
    pb = s["plan_b"]
    assert pb["tiempo_medido"] is False
    assert pb["segundos_adicionales_leer_mensaje"]["mediana"] == pytest.approx(20.0)
    assert pb["cambios_de_banda"] == 3          # las tres primeras filas llevan «alta» y su sistema es «baja»
    assert pb["kappa_con_mensaje"]["n"] == 24


def test_leer_csv_convierte_los_tipos_del_formulario(tmp_path):
    clave = _clave()
    _csv(tmp_path / "l.csv", [_fila(1, 1, clave["casos"][0], "baja", 7, 12.5, notas={"correccion": 5, "utilidad": 4, "lenguaje": 3})])
    fila = cc.leer_csv(tmp_path / "l.csv")[0]
    assert fila["practica"] is False and fila["control"] is False
    assert fila["porcentaje"] == 7 and fila["segundos"] == 12.5 and fila["orden"] == 1
    assert fila["correccion"] == 5 and fila["porcentaje_con"] is None and fila["segundos_con"] is None


def test_el_acta_se_rellena_desde_sesion_json_y_no_deja_huecos(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    l1 = [_fila(1, i + 1, casos[pid], casos[pid]["categoria"]["primaria"], 50, 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "l1.csv", l1)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "l1.csv"))
    plantilla = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "validacion-semisintetica"
                 / "acta-h7-plantilla.md").read_text(encoding="utf-8")
    acta = cc.rellenar_acta(plantilla, cc.valores_para_acta(s, clave))
    assert "{{" not in acta
    assert "simulación semisintética" in acta
    assert cc.TEXTO_FIJADO in acta
    assert "c-00" in acta and "positiva_clara" in acta
    assert "no medido" in acta       # sin lectura 2 ni plan B, el tiempo no se midió
    with pytest.raises(KeyError):
        cc.rellenar_acta("{{no_existe}}", {})
```

- [ ] **Paso 2: Correr la prueba y ver que falla**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_concordancia.py -v`
Esperado: FAIL con `ImportError: cannot import name 'concordancia'`.

- [ ] **Paso 3: Escribir `concordancia.py`**

```python
# -*- coding: utf-8 -*-
"""Concordancia, acuerdo continuo, tiempos y el analisis de la sesion con el
medico (spec de SP5 §5.4-§5.5, §11.4; plan SP5-A D9).

Primario: kappa ponderado lineal sobre las 24 lecturas SIN copiloto. Tambien
el de Cohen sin ponderar (el prometido literalmente) y el binario en «alta».
Dos intervalos: el analitico de Fleiss, Cohen y Everitt (1969) y el BCa por
remuestreo de casos. Con 24 casos el intervalo mide 0,5-0,6 y el texto que lo
dice esta fijado aqui, antes de la sesion.
"""
from __future__ import annotations

import csv
import math
import pathlib
import statistics

import numpy as np
from scipy.special import ndtr, ndtri
from scipy.stats import rankdata

CATEGORIAS = ("baja", "intermedia", "alta")
NOTAS = ("correccion", "utilidad", "lenguaje")
COLUMNAS_CSV = ("lectura", "orden", "id", "practica", "control", "banda", "porcentaje",
                "abierto_en", "enviado_en", "segundos", "banda_con", "porcentaje_con",
                "segundos_con", "correccion", "utilidad", "lenguaje", "comentario")
B_BOOTSTRAP = 2000
SEMILLA_BOOTSTRAP = 20261013
TEXTO_FIJADO = (
    "Con 24 casos y un solo evaluador, el intervalo del 95 % del kappa tiene una "
    "anchura de 0,5 a 0,6. El diseño no distingue una concordancia moderada (0,4) "
    "de una sustancial (0,6), ni generaliza a otros médicos ni a otro reparto de "
    "casos, que aquí es deliberado. El criterio ≥ 0,4 de la Semana 1 se evalúa "
    "sobre la estimación puntual y se publica siempre con su intervalo; si el "
    "límite inferior queda por debajo de 0,4, se dice.")


# --------------------------------------------------------------------------
# Kappas
# --------------------------------------------------------------------------
def indices(categorias_obs, categorias=CATEGORIAS) -> np.ndarray:
    try:
        return np.array([categorias.index(c) for c in categorias_obs], dtype=int)
    except ValueError as exc:
        raise ValueError(f"categoría desconocida: {exc}") from None


def pesos(c: int, tipo: str) -> np.ndarray:
    i = np.arange(c)
    if tipo == "lineal":
        return 1.0 - np.abs(i[:, None] - i[None, :]) / (c - 1)
    if tipo == "ninguno":
        return np.eye(c)
    raise ValueError(f"tipo de pesos desconocido: {tipo!r}")


def kappa(a, b, c: int = 3, tipo: str = "lineal") -> dict:
    """Kappa (ponderado lineal o de Cohen) con el error tipico de Fleiss,
    Cohen y Everitt (1969):
        Var = [Σ p_ij (w_ij − (w̄_i. + w̄_.j)(1 − κ))² − (κ − p_e(1 − κ))²] / [n (1 − p_e)²]
    con w̄_i. = Σ_j p_.j w_ij y w̄_.j = Σ_i p_i. w_ij."""
    a = np.asarray(a, dtype=int)
    b = np.asarray(b, dtype=int)
    n = a.size
    if n == 0 or b.size != n:
        raise ValueError("las dos listas deben tener la misma longitud, y no estar vacías")
    m = np.zeros((c, c))
    np.add.at(m, (a, b), 1.0)
    m /= n
    w = pesos(c, tipo)
    pi, pj = m.sum(axis=1), m.sum(axis=0)
    po = float((m * w).sum())
    pe = float((np.outer(pi, pj) * w).sum())
    if pe >= 1.0:
        nan = float("nan")
        return {"kappa": nan, "ee": nan, "ic95": [nan, nan], "po": po, "pe": pe, "n": int(n)}
    k = (po - pe) / (1.0 - pe)
    wi = w @ pj
    wj = pi @ w
    termino = (w - (wi[:, None] + wj[None, :]) * (1.0 - k)) ** 2
    var = ((m * termino).sum() - (k - pe * (1.0 - k)) ** 2) / (n * (1.0 - pe) ** 2)
    ee = math.sqrt(max(float(var), 0.0))
    return {"kappa": float(k), "ee": ee,
            "ic95": [float(k - 1.96 * ee), float(k + 1.96 * ee)],
            "po": po, "pe": pe, "n": int(n)}


def kappa_binario(a, b, positiva: str = "alta") -> dict:
    ia = (np.asarray(a) == positiva).astype(int)
    ib = (np.asarray(b) == positiva).astype(int)
    return kappa(ia, ib, c=2, tipo="ninguno")


def bca(datos, estadistico, B: int = B_BOOTSTRAP, semilla: int = SEMILLA_BOOTSTRAP,
        alfa: float = 0.05) -> list:
    """Intervalo BCa por remuestreo de casos (las filas de `datos`)."""
    datos = np.asarray(datos)
    n = datos.shape[0]
    rng = np.random.default_rng(semilla)
    theta = float(estadistico(datos))
    boots = np.array([estadistico(datos[rng.integers(0, n, n)]) for _ in range(B)], dtype=float)
    boots = boots[np.isfinite(boots)]
    if boots.size == 0 or np.all(boots == boots[0]):
        return [theta, theta]
    fraccion = (np.sum(boots < theta) + 0.5 * np.sum(boots == theta)) / boots.size
    z0 = ndtri(min(max(float(fraccion), 1e-6), 1 - 1e-6))
    jack = np.array([estadistico(np.delete(datos, i, axis=0)) for i in range(n)], dtype=float)
    jack = jack[np.isfinite(jack)]
    d = jack.mean() - jack
    den = 6.0 * (np.sum(d ** 2) ** 1.5)
    a = float(np.sum(d ** 3) / den) if den > 0 else 0.0

    def ajustada(z):
        return float(ndtr(z0 + (z0 + z) / (1.0 - a * (z0 + z))))

    lo, hi = ajustada(ndtri(alfa / 2)), ajustada(ndtri(1 - alfa / 2))
    return [float(np.percentile(boots, 100 * lo)), float(np.percentile(boots, 100 * hi))]


def kappa_con_intervalos(a, b, tipo: str = "lineal") -> dict:
    """`tipo`: lineal | ninguno | binario_alta. Devuelve el kappa con los dos intervalos."""
    if tipo == "binario_alta":
        ia = (np.asarray(a) == "alta").astype(int)
        ib = (np.asarray(b) == "alta").astype(int)
        c, pesos_ = 2, "ninguno"
    else:
        ia, ib, c, pesos_ = indices(a), indices(b), 3, tipo
    r = kappa(ia, ib, c, pesos_)
    pares = np.stack([ia, ib], axis=1)
    r["ic95_bca"] = bca(pares, lambda d: kappa(d[:, 0], d[:, 1], c, pesos_)["kappa"])
    r["tipo"] = tipo
    return r


# --------------------------------------------------------------------------
# Acuerdo continuo y tiempos
# --------------------------------------------------------------------------
def acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict:
    """Spearman entre el porcentaje del medico y el punto medio del sistema;
    Bland-Altman en log-odds con 0 y 100 acotados a 0,5 y 99,5; y la fraccion
    de porcentajes que caen dentro de la horquilla."""
    pct = np.asarray(pct_medico, dtype=float)
    p = np.asarray(p_sistema, dtype=float)
    acotados = int(np.sum((pct <= 0) | (pct >= 100)))
    pm = np.clip(pct, 0.5, 99.5) / 100.0
    d = np.log(pm / (1 - pm)) - np.log(p / (1 - p))
    de = float(d.std(ddof=1)) if d.size > 1 else 0.0
    salida = {"n": int(pct.size),
              "spearman": float(np.corrcoef(rankdata(pct), rankdata(p))[0, 1]) if pct.size > 1 else float("nan"),
              "diferencia_media_log_odds": float(d.mean()), "de": de,
              "limites_95": [float(d.mean() - 1.96 * de), float(d.mean() + 1.96 * de)],
              "acotados_0_o_100": acotados}
    if minima is not None and maxima is not None:
        dentro = (pm >= np.asarray(minima, dtype=float)) & (pm <= np.asarray(maxima, dtype=float))
        salida["fraccion_dentro_de_la_horquilla"] = float(dentro.mean())
    return salida


def razon_de_tiempos(t_sin, t_con) -> dict:
    """Razon de medias geometricas con/sin, pareada por caso, con BCa."""
    t_sin = np.asarray(t_sin, dtype=float)
    t_con = np.asarray(t_con, dtype=float)
    if t_sin.size == 0 or t_sin.size != t_con.size or np.any(t_sin <= 0) or np.any(t_con <= 0):
        raise ValueError("hacen falta tiempos pareados y positivos")
    ln = np.log(t_con / t_sin)

    def razon(d):
        return float(np.exp(np.mean(d)))

    r = razon(ln)
    return {"n": int(ln.size), "razon_medias_geometricas": r,
            "ic95_bca": bca(ln, razon) if ln.size >= 3 else [r, r],
            "reduccion_pct": float((1.0 - r) * 100.0),
            "razones": [float(x) for x in np.exp(ln)]}


# --------------------------------------------------------------------------
# El CSV del formulario y el analisis
# --------------------------------------------------------------------------
def _entero(v):
    return None if v in ("", None) else int(float(v))


def _decimal(v):
    return None if v in ("", None) else float(v)


def leer_csv(ruta) -> list:
    """Las filas del CSV del formulario con sus tipos."""
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    salida = []
    for fila in filas:
        salida.append({
            "lectura": fila["lectura"], "orden": _entero(fila["orden"]), "id": fila["id"],
            "practica": fila["practica"].strip().lower() == "true",
            "control": fila["control"].strip().lower() == "true",
            "banda": fila["banda"], "porcentaje": _entero(fila["porcentaje"]),
            "abierto_en": _entero(fila["abierto_en"]), "enviado_en": _entero(fila["enviado_en"]),
            "segundos": _decimal(fila["segundos"]),
            "banda_con": fila["banda_con"] or None, "porcentaje_con": _entero(fila["porcentaje_con"]),
            "segundos_con": _decimal(fila["segundos_con"]),
            **{k: _entero(fila[k]) for k in NOTAS},
            "comentario": fila.get("comentario", "") or "",
        })
    return salida


def _sin_practica(filas):
    return [f for f in filas if not f["practica"]]


def _notas(filas) -> dict:
    salida = {}
    for k in NOTAS:
        valores = [f[k] for f in filas if f[k] is not None]
        salida[k] = {"media": float(np.mean(valores)) if valores else None,
                     "distribucion": {str(v): valores.count(v) for v in range(1, 6)},
                     "n": len(valores)}
    return salida


def analizar(clave: dict, lectura1: list, lectura2: list | None = None,
             planb: list | None = None) -> dict:
    """De los CSV y la clave a la estructura de `sesion.json`."""
    casos = {c["patientId"]: c for c in clave["casos"]}
    categoria_de = "mensaje" if all("categoria" in c for c in casos.values()) else "prevista"
    clave_cat = "categoria" if categoria_de == "mensaje" else "categoria_prevista"
    clave_bloque = "bloque" if categoria_de == "mensaje" else "bloque_previsto"

    l1 = _sin_practica(lectura1)
    ids = [f["id"] for f in l1]
    if set(ids) != set(casos) or len(ids) != len(casos):
        raise ValueError(f"la lectura 1 tiene {len(ids)} filas para {len(casos)} casos, o ids que no cuadran")
    sistema = [casos[i][clave_cat]["primaria"] for i in ids]
    medico = [f["banda"] for f in l1]
    pct = [f["porcentaje"] for f in l1]

    kappas = {"ponderado_lineal": kappa_con_intervalos(sistema, medico, "lineal"),
              "cohen": kappa_con_intervalos(sistema, medico, "ninguno"),
              "binario_alta": kappa_con_intervalos(sistema, medico, "binario_alta")}
    sensibilidad = {v: kappa(indices([casos[i][clave_cat][v] for i in ids]), indices(medico), 3, "lineal")["kappa"]
                    for v in ("independencia", "conservador", "cruza")}
    acuerdo = acuerdo_continuo(pct, [casos[i][clave_cat]["punto_medio"] for i in ids],
                               minima=[casos[i][clave_bloque]["minima"] for i in ids],
                               maxima=[casos[i][clave_bloque]["maxima"] for i in ids])
    desacuerdos = [{"id": f["id"], "estrato": casos[f["id"]]["estrato"], "sistema": s,
                    "medico": f["banda"], "porcentaje": f["porcentaje"],
                    "horquilla": [casos[f["id"]][clave_bloque]["minima"], casos[f["id"]][clave_bloque]["maxima"]],
                    "comentario": f["comentario"]}
                   for f, s in zip(l1, sistema) if f["banda"] != s]
    medico1 = {f["id"]: f["banda"] for f in l1}
    t1 = {f["id"]: f["segundos"] for f in l1}

    salida = {"rotulo": clave.get("rotulo", "simulación semisintética — sesión H7"),
              "n": len(ids), "categoria_de": categoria_de, "kappa": kappas,
              "sensibilidad_categoria": sensibilidad, "acuerdo_continuo": acuerdo,
              "desacuerdos": desacuerdos, "lectura2": None, "plan_b": None,
              "texto_fijado": TEXTO_FIJADO}

    if lectura2 is not None:
        l2 = _sin_practica(lectura2)
        con = [f for f in l2 if not f["control"]]
        controles = [f for f in l2 if f["control"]]
        tiempo = razon_de_tiempos([t1[f["id"]] for f in con], [f["segundos"] for f in con])
        razones_c = [f["segundos"] / t1[f["id"]] for f in controles]
        media_c = float(np.exp(np.mean(np.log(razones_c)))) if razones_c else None
        tiempo["controles"] = {"n": len(controles), "razones": razones_c, "media_geometrica": media_c}
        tiempo["razon_corregida_por_releer"] = (tiempo["razon_medias_geometricas"] / media_c
                                                if media_c else None)
        tiempo["medido"] = True
        salida["lectura2"] = {
            "n_con_mensaje": len(con), "n_controles": len(controles),
            "kappa_con_mensaje": kappa_con_intervalos(
                [casos[f["id"]][clave_cat]["primaria"] for f in con], [f["banda"] for f in con], "lineal"),
            "cambios_de_banda": sum(f["banda"] != medico1[f["id"]] for f in con),
            "utilidad": _notas(con), "tiempo": tiempo}

    if planb is not None:
        pb = _sin_practica(planb)
        salida["plan_b"] = {
            "tiempo_medido": False,
            "segundos_adicionales_leer_mensaje": {
                "mediana": float(statistics.median([f["segundos_con"] for f in pb if f["segundos_con"] is not None])),
                "n": sum(f["segundos_con"] is not None for f in pb)},
            "kappa_con_mensaje": kappa_con_intervalos(
                [casos[f["id"]][clave_cat]["primaria"] for f in pb], [f["banda_con"] for f in pb], "lineal"),
            "cambios_de_banda": sum(f["banda_con"] != f["banda"] for f in pb),
            "utilidad": _notas(pb)}
    return salida


# --------------------------------------------------------------------------
# El acta
# --------------------------------------------------------------------------
def _f(x, decimales=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.{decimales}f}".replace(".", ",")


def _kappa_texto(k: dict) -> str:
    return (f"{_f(k['kappa'])} (IC 95 % analítico {_f(k['ic95'][0])} a {_f(k['ic95'][1])}; "
            f"BCa {_f(k['ic95_bca'][0])} a {_f(k['ic95_bca'][1])}; n = {k['n']})")


def _fecha(ms):
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else "—"


def valores_para_acta(sesion: dict, clave: dict, lectura1: list | None = None,
                      lectura2: list | None = None) -> dict:
    """Los valores que rellenan la plantilla. Ninguno se teclea: salen de
    `sesion.json` y de la clave."""
    k = sesion["kappa"]
    casos = "\n".join(f"| {c['patientId']} | {c['estrato']} | {'concordante' if c['concordante'] else 'discordante'} |"
                      for c in clave["casos"])
    desacuerdos = "\n".join(
        f"| {d['id']} | {d['estrato']} | {d['sistema']} | {d['medico']} ({d['porcentaje']} %) | "
        f"{_f(d['horquilla'][0] * 100, 0)}-{_f(d['horquilla'][1] * 100, 0)} % | {d['comentario']} |"
        for d in sesion["desacuerdos"]) or "| (ninguno) | | | | | |"
    l2 = sesion.get("lectura2")
    pb = sesion.get("plan_b")
    if l2:
        t = l2["tiempo"]
        tiempo = (f"razón de medias geométricas con/sin {_f(t['razon_medias_geometricas'])} "
                  f"(IC 95 % BCa {_f(t['ic95_bca'][0])} a {_f(t['ic95_bca'][1])}; n = {t['n']}), "
                  f"reducción {_f(t['reduccion_pct'], 0)} %; controles releídos sin copiloto: "
                  f"media geométrica {_f(t['controles']['media_geometrica'])} (n = {t['controles']['n']}); "
                  f"razón corregida por releer {_f(t['razon_corregida_por_releer'])}. La reducción mezcla "
                  f"el efecto del copiloto con el de releer; los controles lo estiman de forma descriptiva.")
        influencia = (f"kappa con el mensaje delante {_kappa_texto(l2['kappa_con_mensaje'])}; "
                      f"cambió de banda en {l2['cambios_de_banda']} de {l2['n_con_mensaje']} casos")
        u = l2["utilidad"]
    elif pb:
        tiempo = (f"no medido (plan B, una sola sesión); leer el mensaje añadió una mediana de "
                  f"{_f(pb['segundos_adicionales_leer_mensaje']['mediana'], 0)} s por caso")
        influencia = (f"kappa tras revelar el mensaje {_kappa_texto(pb['kappa_con_mensaje'])}; "
                      f"cambió de banda en {pb['cambios_de_banda']} de {pb['kappa_con_mensaje']['n']} casos")
        u = pb["utilidad"]
    else:
        tiempo = "no medido"
        influencia = "no medida"
        u = None
    utilidad = ("; ".join(f"{n} {_f(u[n]['media'], 1)} (n = {u[n]['n']})" for n in NOTAS) if u else "no medida")
    a = sesion["acuerdo_continuo"]
    return {
        "rotulo": sesion["rotulo"], "n": str(sesion["n"]),
        "fecha_lectura1": _fecha(lectura1[0]["abierto_en"]) if lectura1 else "—",
        "fecha_lectura2": _fecha(lectura2[0]["abierto_en"]) if lectura2 else "—",
        "prevalencia_sesion": _f(clave.get("prevalencia_sesion"), 4),
        "categoria_de": sesion["categoria_de"],
        "kappa_ponderado": _kappa_texto(k["ponderado_lineal"]),
        "kappa_cohen": _kappa_texto(k["cohen"]),
        "kappa_binario": _kappa_texto(k["binario_alta"]),
        "sensibilidad": "; ".join(f"{v} {_f(x)}" for v, x in sesion["sensibilidad_categoria"].items()),
        "spearman": _f(a["spearman"]), "bland_altman": f"{_f(a['diferencia_media_log_odds'])} (DE {_f(a['de'])})",
        "dentro_horquilla": _f(a.get("fraccion_dentro_de_la_horquilla", float("nan")) * 100, 0),
        "acotados": str(a["acotados_0_o_100"]),
        "influencia": influencia, "utilidad": utilidad, "tiempo": tiempo,
        "tabla_casos": casos, "tabla_desacuerdos": desacuerdos,
        "texto_fijado": sesion["texto_fijado"],
    }


def rellenar_acta(plantilla: str, valores: dict) -> str:
    """Sustituye {{clave}}; una clave sin valor es KeyError, no un hueco."""
    import re
    def sustituir(m):
        return str(valores[m.group(1)])
    return re.sub(r"\{\{(\w+)\}\}", sustituir, plantilla)
```

- [ ] **Paso 4: Escribir la plantilla del acta**

`docs/validacion-semisintetica/acta-h7-plantilla.md`:

```markdown
# Acta de H7 — sesión de concordancia con un médico sobre viñetas semisintéticas

**Rótulo:** {{rotulo}}. La placa de cada caso es real (conjunto de prueba de
RSNA); la clínica es generada. El kappa mide acuerdo con un evaluador, no
exactitud clínica.

**Participante:** médico general colaborador, de forma voluntaria; sin datos
personales en ningún fichero del proyecto.

**Fechas:** lectura 1 el {{fecha_lectura1}}; lectura 2 el {{fecha_lectura2}}.

**Casos:** {{n}}, elegidos con semilla por estratos (tabla al final). Los
mensajes del sistema se generaron con la prevalencia desplegada
({{prevalencia_sesion}}); la categoría del sistema sale del bloque
`combinacion` del {{categoria_de}}.

## Método

Dos lecturas del mismo conjunto: la primera sin copiloto (placa y viñeta;
banda y porcentaje); la segunda, al menos siete días después, con el mensaje
real del sistema en 20 casos y 4 controles sin mensaje. El kappa sale solo de
la primera. Pregunta al médico: probabilidad de que la placa muestre una
opacidad o infiltrado compatible con neumonía, en tres bandas (< 20 %,
20-70 %, > 70 %; convención del equipo) y como porcentaje entero. Instrumento:
el formulario local, un caso por pantalla, sin volver atrás; el tiempo va de
abrir el caso a enviar la banda.

## Resultados

- **Kappa ponderado lineal (primario):** {{kappa_ponderado}}.
- **Kappa de Cohen sin ponderar:** {{kappa_cohen}}.
- **Kappa binario en «alta»:** {{kappa_binario}}.
- **Sensibilidad a la regla de categoría del sistema (kappa ponderado):** {{sensibilidad}}.
- **Acuerdo continuo:** Spearman {{spearman}}; diferencia media en log-odds
  (médico − sistema) {{bland_altman}}; el porcentaje del médico cae dentro de
  la horquilla en el {{dentro_horquilla}} % de los casos; porcentajes de 0 o
  100 acotados: {{acotados}}.
- **Influencia del sistema (no es concordancia independiente):** {{influencia}}.
- **Utilidad del pre-informe (1-5):** {{utilidad}}.
- **Tiempo de triaje:** {{tiempo}}.

{{texto_fijado}}

## Desacuerdos, caso por caso

| Caso | Estrato | Sistema | Médico | Horquilla del sistema | Comentario |
| :--- | :--- | :--- | :--- | :--- | :--- |
{{tabla_desacuerdos}}

## Observaciones del médico

(Se anexan sin editar. Si no las envió, se hace constar.)

## Conformidad

El acta se cierra con la conformidad del médico, o con la constancia de que
no la envió.

## Anexo: los casos

| Caso | Estrato | Clínica frente a imagen |
| :--- | :--- | :--- |
{{tabla_casos}}
```

- [ ] **Paso 5: Escribir `scripts/analizar_sesion.py`**

```python
# -*- coding: utf-8 -*-
"""Analiza la sesion con el medico: de los CSV del formulario a sesion.json y al acta.

USO
    python scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 lectura1.csv --lectura2 lectura2.csv
    python scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 planb.csv --planb planb.csv

Escribe docs/validacion-semisintetica/sesion.json y acta-h7.md (rellena la
plantilla). Ninguna cifra del acta se teclea: todas salen de sesion.json.
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.validacion import concordancia as cc  # noqa: E402

CARPETA = REPO / "docs" / "validacion-semisintetica"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sesion", default=str(REPO / "pruebas" / "sesion"))
    p.add_argument("--lectura1", required=True, help="CSV de la lectura sin copiloto (o el del plan B)")
    p.add_argument("--lectura2", help="CSV de la lectura con copiloto")
    p.add_argument("--planb", help="CSV del plan B (lectura secuencial)")
    p.add_argument("--salida", default=str(CARPETA / "sesion.json"))
    p.add_argument("--acta", default=str(CARPETA / "acta-h7.md"))
    args = p.parse_args()
    if args.lectura2 and args.planb:
        raise SystemExit("o lectura 2 o plan B, no los dos")

    sesion_dir = pathlib.Path(args.sesion)
    clave = json.loads((sesion_dir / "clave.json").read_text(encoding="utf-8"))
    l1 = cc.leer_csv(sesion_dir / args.lectura1)
    l2 = cc.leer_csv(sesion_dir / args.lectura2) if args.lectura2 else None
    pb = cc.leer_csv(sesion_dir / args.planb) if args.planb else None
    resultado = cc.analizar(clave, l1, l2, pb)

    salida = pathlib.Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    plantilla = (CARPETA / "acta-h7-plantilla.md").read_text(encoding="utf-8")
    acta = cc.rellenar_acta(plantilla, cc.valores_para_acta(resultado, clave, l1, l2))
    pathlib.Path(args.acta).write_text(acta, encoding="utf-8")
    k = resultado["kappa"]["ponderado_lineal"]
    print(f"kappa ponderado {k['kappa']:.3f} (BCa {k['ic95_bca'][0]:.2f} a {k['ic95_bca'][1]:.2f}); "
          f"{len(resultado['desacuerdos'])} desacuerdos; sesion.json y acta escritos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Paso 6: Correr la prueba y ver que pasa**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_concordancia.py -v`
Esperado: 11 PASS (el BCa con 2 000 réplicas por kappa tarda unos segundos).

- [ ] **Paso 7: Commit**

```bash
git add src/copiloto_triaje/validacion/concordancia.py scripts/analizar_sesion.py docs/validacion-semisintetica/acta-h7-plantilla.md tests/test_concordancia.py
git commit -m "feat(sesion): kappas con dos intervalos, tiempos pareados, analizar_sesion y plantilla del acta (SP5-A T9)"
```

---

### Tarea 10: El runbook de la sesión y la suite entera

**Ficheros:**
- Crear: `docs/sp5-sesion.md`
- Modificar: `README.md` (un párrafo y un enlace)

**Interfaces:**
- Consume: todo lo anterior.
- Produce: el procedimiento completo, de principio a fin, que sigue quien prepara y conduce la sesión.

- [ ] **Paso 1: Escribir `docs/sp5-sesion.md`**

```markdown
# SP5 — La sesión con el médico, de principio a fin

Todo lo de aquí es **simulación semisintética** (spec de SP5 §4-§5): la placa
es real, la clínica es generada, y el kappa mide acuerdo con un evaluador, no
exactitud. Nada de la sesión se versiona: `pruebas/sesion/` está en
`.gitignore`.

## 0. Antes (una vez)

- `RSNA_RAIZ` apunta a la raíz del dataset preparado (`crudo/stage_2_train_images/*.dcm`
  y `png/*.png`). Sin ella, los scripts se detienen y lo dicen.
- La suite en verde: `C:/venv-copiloto/Scripts/python.exe -m pytest` y
  `node tests/formulario.mjs`.
- Fechas con el médico: lectura 1 el 6, 7 u 8 de octubre; lectura 2 exactamente
  siete días o más después (6 → 13, 7 → 14, 8 → 15). En presencia o por
  videollamada: en remoto asíncrono los tiempos no valen.

## 1. Elegir los casos (5-oct, y se congela con el tag `h7-sesion`)

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion --semilla 20261006

Deja `casos.json` (27 casos: 24 + 3 de práctica), `clave.json`,
`formulario/` con las placas y `datos_lectura1.js`, y `dosier_lectura1.md`.

## 2. Los mensajes reales

Con el túnel al VPS y los secretos en el entorno (los de `pruebas/reproducir_casos.py`):

    C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus

Sin túnel, el respaldo escrito en el spec §5.6: la imagen local construida del
tag `h7-sesion`, y `--sin-bots`; el acta cita el tag y el digest de la imagen:

    docker build -t copiloto-mcp:h7-sesion -f servidor/Dockerfile .
    docker image inspect copiloto-mcp:h7-sesion --format "{{.Id}}"
    (arrancar el contenedor como en tests/test_contrato_mcp.py::ARRANCAR, con ese tag y -p 127.0.0.1:18001:8000)
    COPILOTO_URL=http://127.0.0.1:18001/mcp C:/venv-copiloto/Scripts/python.exe pruebas/reproducir_casos.py --sin-bots --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus

En los dos casos queda `pruebas/sesion/corpus/mensajes.json` y un corpus legible en `00-sesion/`.

    C:/venv-copiloto/Scripts/python.exe scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion

Comprueba que cada mensaje repite la viñeta y que la concordancia coincide con
la prevista, y escribe `datos_lectura2.js`, `datos_planb.js`,
`dosier_lectura2.md` y la clave definitiva. Si algo no cuadra, se detiene y
lo lista: no se corrige a mano.

    git tag h7-sesion

## 3. Ensayo (antes del 5-oct)

Un integrante del equipo hace las dos lecturas con el formulario
(`pruebas/sesion/formulario/index.html?lectura=1` y `?lectura=2`), descarga
los CSV y corre el análisis del paso 5. Sirve para probar el formulario, los
tiempos y el acta; sus CSV se borran.

## 4. Las lecturas

- Abrir `pruebas/sesion/formulario/index.html?lectura=1` en el navegador del
  equipo (en presencia) o compartirlo por videollamada. Tres casos de
  práctica primero, luego los 24. Al terminar, «Descargar CSV» →
  `pruebas/sesion/lectura1.csv`.
- Siete días después, `?lectura=2` → `pruebas/sesion/lectura2.csv`.
- **Plan B** (una sola sesión): `?lectura=planb` → `pruebas/sesion/planb.csv`.
  El kappa sale de la primera respuesta; el tiempo no se mide.
- El estado se guarda en el navegador tras cada envío: si se cierra, se
  retoma en el caso a medias, que vuelve a empezar con su reloj.

## 5. El análisis y el acta

    C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 lectura1.csv --lectura2 lectura2.csv
    (plan B)  C:/venv-copiloto/Scripts/python.exe scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 planb.csv --planb planb.csv

Escribe `docs/validacion-semisintetica/sesion.json` y `acta-h7.md` con todas
las cifras leídas del JSON. El acta se envía al médico el 16-oct; sus
observaciones se anexan sin editar. Los resultados se presentan a la tutora
en la tutoría del 17-oct.

## Qué se versiona y qué no

Se versionan `sesion.json` y `acta-h7.md` (cifras, `patientId`, estratos).
No se versionan las placas, los mensajes, los CSV del médico ni `clave.json`.
```

- [ ] **Paso 2: Enlazar desde el README**

En `README.md`, tras el bloque de sub-proyectos entregados, añade:

```markdown
- **SP5 — validación semisintética y sesión con el médico.** El generador por
  puntuación de Heckerling, su oráculo y la comprobación caso a caso viven en
  `src/copiloto_triaje/validacion/`; los insumos y resultados, rotulados como
  simulación semisintética, en `docs/validacion-semisintetica/`; el
  procedimiento de la sesión, en `docs/sp5-sesion.md`.
```

- [ ] **Paso 3: Correr la suite entera**

Run: `C:/venv-copiloto/Scripts/python.exe -m pytest -q` y `node tests/formulario.mjs`
Esperado: todo en verde (las pruebas conducidas de SP3 se saltan sin sus secretos, como siempre).

- [ ] **Paso 4: Commit**

```bash
git add docs/sp5-sesion.md README.md
git commit -m "docs(sp5): runbook de la sesion con el medico (SP5-A T10)"
```

---

## Autorrevisión del plan (hecha al escribirlo)

- **Cobertura del spec:** §4.2 (Tarea 3), §4.4 0A (Tarea 4), §4.5 modelo y
  oráculo (Tarea 2), §5.1 casos y viñetas (Tarea 7), §5.2-§5.3 pregunta y
  categoría (Tareas 5, 8), §5.4-§5.5 diseño y análisis (Tareas 8, 9), §5.6
  mensajes reales (Tarea 6), §5.8 instrumentos (Tareas 7-9), §8 pruebas del
  generador, umbral latente, oráculo, 0A, categoría, sesión, arnés (Tareas
  2-7). Fuera de este plan, a propósito: §4.6 (rejilla, bootstrap, métricas),
  0B/0C, §6 entero.
- **Tipos:** `generador.hallazgos(fila)` devuelve el dict que `heckerling.combinacion`
  acepta; `sesion._caso` guarda `signos` (cuatro claves) y `sintomas` (siete) por
  separado, que es lo que `casos.json` y `hallazgos_del_caso` esperan; el CSV
  del formulario y `concordancia.leer_csv` comparten `COLUMNAS`/`COLUMNAS_CSV`
  en el mismo orden.
