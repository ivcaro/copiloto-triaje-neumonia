# SP1 — Núcleo de imagen: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** convertir el dataset RSNA descargado en una CNN de clasificación binaria entrenada, con partición por paciente verificada sin fuga y métricas medidas de forma honesta.

**Arquitectura:** paquete de Python con pruebas (`copiloto_triaje`), no un notebook. Se desarrolla y verifica en CPU con datos sintéticos y un entrenamiento de humo; el entrenamiento completo ejecuta el mismo paquete en GPU externa desde un notebook delgado.

**Stack:** Python 3.13, PyTorch 2.14.0+cpu, torchvision 0.29.0+cpu, pydicom 3.0.2, scikit-learn 1.9.1, Pillow, pandas, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`

## Restricciones globales

- **Intérprete obligatorio: `C:\venv-copiloto\Scripts\python.exe`.** No usar el Python del sistema. Motivo verificado: el Python de Microsoft Store tiene una ruta base tan larga que instalar torchvision falla con `WinError 206` (nombre de archivo demasiado largo). El entorno virtual en ruta corta ya está creado y con todas las dependencias instaladas.
- **Datos crudos: `C:\Users\[retirado]\datasets\rsna-pneumonia\`** — fuera del repositorio y fuera de OneDrive. El zip `rsna-pneumonia-detection-challenge.zip` (3,66 GB) ya está ahí. Nunca versionar datos.
- **Nombres de funciones, variables y archivos en español**, coherente con el resto del proyecto.
- **Semilla por defecto: 42.** Toda función con aleatoriedad la recibe explícitamente; ninguna usa el generador global.
- **Hechos verificados del dataset** (medidos el 16-sep-2026, no suponer otros): 26 684 imágenes de entrenamiento, **una por paciente**; `patientId` coincide con el nombre del archivo DICOM; 6 012 positivos (22,5%); DICOM de 1024×1024 **uint8** `MONOCHROME2`, por lo que la conversión a PNG es directa y no necesita ventaneo; los metadatos `PatientAge`, `PatientSex` y `ViewPosition` (PA/AP) están presentes.
- **Todas las pruebas con pytest**, ejecutadas con `C:\venv-copiloto\Scripts\python.exe -m pytest`.
- **Un commit por tarea**, al final de la tarea, solo con las pruebas en verde.

---

## Estructura de archivos

| Archivo | Responsabilidad |
| :--- | :--- |
| `pyproject.toml` | Metadatos del paquete y dependencias fijadas |
| `src/copiloto_triaje/config.py` | Configuración y semilla, en un único lugar |
| `src/copiloto_triaje/datos/particion.py` | Partición por paciente y verificación anti-fuga |
| `src/copiloto_triaje/datos/dicom.py` | Lectura de DICOM, conversión a PNG, metadatos |
| `src/copiloto_triaje/datos/dataset.py` | Dataset de PyTorch y transformaciones |
| `src/copiloto_triaje/modelo/arquitectura.py` | Construcción del modelo y congelado de capas |
| `src/copiloto_triaje/modelo/evaluacion.py` | Métricas binarias y selección de umbral |
| `src/copiloto_triaje/modelo/entrenamiento.py` | Bucle de entrenamiento, early stopping, checkpoints |
| `scripts/preparar_datos.py` | Línea de órdenes: zip → PNG → manifiestos |
| `notebooks/entrenar_gpu.ipynb` | Notebook delgado para Colab o Kaggle |

---

### Tarea 1: Andamiaje del paquete y configuración

**Archivos:**
- Crear: `pyproject.toml`
- Crear: `src/copiloto_triaje/__init__.py`, `src/copiloto_triaje/datos/__init__.py`, `src/copiloto_triaje/modelo/__init__.py`
- Crear: `src/copiloto_triaje/config.py`
- Prueba: `tests/test_config.py`

**Interfaces:**
- Produce: `Config` (dataclass congelada) con los campos y valores por defecto definidos abajo. Todas las tareas posteriores la reciben como parámetro `cfg`.

- [ ] **Paso 1: Escribir la prueba que falla**

```python
# tests/test_config.py
import pytest
from pathlib import Path
from copiloto_triaje.config import Config


def test_config_usa_valores_por_defecto_del_spec():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/rsna.zip"))
    assert cfg.semilla == 42
    assert cfg.tam_imagen == 224
    assert cfg.proporciones == (0.70, 0.15, 0.15)
    assert cfg.especificidad_objetivo == 0.75
    assert cfg.especificidad_minima == 0.70
    assert cfg.recall_objetivo == 0.85


def test_config_rechaza_proporciones_que_no_suman_uno():
    with pytest.raises(ValueError, match="deben sumar 1"):
        Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/r.zip"),
               proporciones=(0.7, 0.2, 0.2))


def test_config_es_inmutable():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/r.zip"))
    with pytest.raises(Exception):
        cfg.semilla = 7


def test_rutas_derivadas_cuelgan_de_la_raiz():
    cfg = Config(raiz_datos=Path("/tmp/d"), zip_rsna=Path("/tmp/d/r.zip"))
    assert cfg.dir_png == Path("/tmp/d/png")
    assert cfg.dir_manifiestos == Path("/tmp/d/manifiestos")
    assert cfg.dir_checkpoints == Path("/tmp/d/checkpoints")
```

- [ ] **Paso 2: Ejecutar la prueba y comprobar que falla**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_config.py -v`
Esperado: FALLA con `ModuleNotFoundError: No module named 'copiloto_triaje'`

- [ ] **Paso 3: Crear `pyproject.toml`**

```toml
[project]
name = "copiloto-triaje"
version = "0.1.0"
description = "Copiloto de triaje para neumonia en adultos - nucleo de imagen (SP1)"
requires-python = ">=3.11"
dependencies = [
    "torch==2.14.0",
    "torchvision==0.29.0",
    "pydicom==3.0.2",
    "pillow>=11",
    "numpy>=2",
    "pandas>=2.2",
    "scikit-learn>=1.6",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Paso 4: Crear los `__init__.py` y `config.py`**

Los tres `__init__.py` quedan vacíos.

```python
# src/copiloto_triaje/config.py
"""Configuracion unica del pipeline. Toda aleatoriedad pasa por `semilla`."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Parametros del pipeline. Los valores por defecto son los del spec."""

    raiz_datos: Path
    zip_rsna: Path
    semilla: int = 42
    tam_imagen: int = 224
    proporciones: tuple[float, float, float] = (0.70, 0.15, 0.15)
    lote: int = 32
    epocas_cabeza: int = 3
    epocas_ajuste: int = 7
    lr_cabeza: float = 1e-3
    lr_ajuste: float = 1e-4
    paciencia: int = 3
    especificidad_objetivo: float = 0.75
    especificidad_minima: float = 0.70
    recall_objetivo: float = 0.85

    def __post_init__(self) -> None:
        total = sum(self.proporciones)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Las proporciones deben sumar 1, suman {total}")
        if self.semilla is None:
            raise ValueError("La semilla es obligatoria para poder reproducir")

    @property
    def dir_png(self) -> Path:
        return self.raiz_datos / "png"

    @property
    def dir_manifiestos(self) -> Path:
        return self.raiz_datos / "manifiestos"

    @property
    def dir_checkpoints(self) -> Path:
        return self.raiz_datos / "checkpoints"
```

- [ ] **Paso 5: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_config.py -v`
Esperado: 4 passed

- [ ] **Paso 6: Commit**

```bash
git add pyproject.toml src tests
git commit -m "feat: andamiaje del paquete y configuracion con semilla"
```

---

### Tarea 2: Partición por paciente y verificación anti-fuga

Es la tarea más importante del sub-proyecto: es el error que invalidó el dataset pediátrico que descartamos, y debe ser imposible cometerlo sin que una prueba falle.

**Archivos:**
- Crear: `src/copiloto_triaje/datos/particion.py`
- Prueba: `tests/test_particion.py`

**Interfaces:**
- Consume: nada (lógica pura sobre listas de diccionarios).
- Produce: `particionar_por_paciente(registros, proporciones, semilla) -> dict[str, list[dict]]` con claves `"train"`, `"val"`, `"test"`; `verificar_sin_fuga(particiones) -> None`; excepción `FugaDeDatos`. Cada registro es un dict con al menos `patientId: str` y `etiqueta: int` (0 o 1).

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_particion.py
import pytest
from copiloto_triaje.datos.particion import (
    FugaDeDatos, particionar_por_paciente, verificar_sin_fuga,
)


def registros_sinteticos(n_pacientes=200, imagenes_por_paciente=2, tasa_positivos=0.225):
    """Pacientes con VARIAS imagenes cada uno, para que la fuga sea posible."""
    registros = []
    for i in range(n_pacientes):
        etiqueta = 1 if i < int(n_pacientes * tasa_positivos) else 0
        for j in range(imagenes_por_paciente):
            registros.append({"patientId": f"P{i:04d}", "archivo": f"P{i:04d}_{j}.png",
                              "etiqueta": etiqueta})
    return registros


def test_ningun_paciente_aparece_en_dos_particiones():
    p = particionar_por_paciente(registros_sinteticos(), (0.7, 0.15, 0.15), semilla=42)
    verificar_sin_fuga(p)  # no debe lanzar
    ids = {k: {r["patientId"] for r in v} for k, v in p.items()}
    assert ids["train"].isdisjoint(ids["val"])
    assert ids["train"].isdisjoint(ids["test"])
    assert ids["val"].isdisjoint(ids["test"])


def test_todas_las_imagenes_de_un_paciente_caen_juntas():
    p = particionar_por_paciente(registros_sinteticos(), (0.7, 0.15, 0.15), semilla=42)
    ubicacion = {}
    for nombre, regs in p.items():
        for r in regs:
            ubicacion.setdefault(r["patientId"], set()).add(nombre)
    assert all(len(v) == 1 for v in ubicacion.values())


def test_no_se_pierde_ni_se_duplica_ningun_registro():
    registros = registros_sinteticos()
    p = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    total = sum(len(v) for v in p.values())
    assert total == len(registros)
    archivos = [r["archivo"] for v in p.values() for r in v]
    assert len(archivos) == len(set(archivos))


def test_proporciones_aproximadas():
    registros = registros_sinteticos(n_pacientes=1000)
    p = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    n = len(registros)
    assert 0.66 <= len(p["train"]) / n <= 0.74
    assert 0.12 <= len(p["val"]) / n <= 0.18
    assert 0.12 <= len(p["test"]) / n <= 0.18


def test_estratificacion_conserva_la_tasa_de_positivos():
    registros = registros_sinteticos(n_pacientes=1000, tasa_positivos=0.225)
    p = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    for nombre, regs in p.items():
        tasa = sum(r["etiqueta"] for r in regs) / len(regs)
        assert 0.17 <= tasa <= 0.28, f"{nombre} tiene tasa {tasa}"


def test_la_misma_semilla_reproduce_la_misma_particion():
    registros = registros_sinteticos()
    a = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    b = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    assert [r["archivo"] for r in a["test"]] == [r["archivo"] for r in b["test"]]


def test_semillas_distintas_dan_particiones_distintas():
    registros = registros_sinteticos()
    a = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    b = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=7)
    assert [r["archivo"] for r in a["test"]] != [r["archivo"] for r in b["test"]]


def test_verificar_sin_fuga_detecta_una_fuga_inyectada():
    p = particionar_por_paciente(registros_sinteticos(), (0.7, 0.15, 0.15), semilla=42)
    intruso = dict(p["train"][0])
    p["test"].append(intruso)
    with pytest.raises(FugaDeDatos, match="train"):
        verificar_sin_fuga(p)


def test_proporciones_invalidas_fallan_de_inmediato():
    with pytest.raises(ValueError, match="deben sumar 1"):
        particionar_por_paciente(registros_sinteticos(), (0.7, 0.2, 0.2), semilla=42)
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_particion.py -v`
Esperado: FALLA con `ModuleNotFoundError: No module named 'copiloto_triaje.datos.particion'`

- [ ] **Paso 3: Implementar `particion.py`**

```python
# src/copiloto_triaje/datos/particion.py
"""Particion de registros POR PACIENTE, con verificacion de fuga de datos.

Un mismo paciente nunca puede aparecer en dos particiones: si ocurre, el
modelo se evalua sobre datos que ya vio y las metricas dejan de significar
nada. Es el error documentado que invalida al dataset pediatrico de Kermany.
"""
from __future__ import annotations

import random
from collections import defaultdict


class FugaDeDatos(Exception):
    """Un mismo paciente aparece en mas de una particion."""


def particionar_por_paciente(
    registros: list[dict],
    proporciones: tuple[float, float, float],
    semilla: int,
) -> dict[str, list[dict]]:
    """Reparte los registros en train/val/test agrupando por paciente.

    Todas las imagenes de un paciente caen en la misma particion. La
    estratificacion se hace sobre la etiqueta del paciente: es positivo si
    alguno de sus registros lo es.
    """
    total = sum(proporciones)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Las proporciones deben sumar 1, suman {total}")

    por_paciente: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_paciente[r["patientId"]].append(r)

    positivos, negativos = [], []
    for pid, regs in por_paciente.items():
        destino = positivos if any(x["etiqueta"] == 1 for x in regs) else negativos
        destino.append(pid)

    rng = random.Random(semilla)
    resultado: dict[str, list[dict]] = {"train": [], "val": [], "test": []}

    for grupo in (sorted(positivos), sorted(negativos)):
        grupo = list(grupo)
        rng.shuffle(grupo)
        n = len(grupo)
        corte_train = round(n * proporciones[0])
        corte_val = corte_train + round(n * proporciones[1])
        reparto = (
            ("train", grupo[:corte_train]),
            ("val", grupo[corte_train:corte_val]),
            ("test", grupo[corte_val:]),
        )
        for nombre, pids in reparto:
            for pid in pids:
                resultado[nombre].extend(por_paciente[pid])

    return resultado


def verificar_sin_fuga(particiones: dict[str, list[dict]]) -> None:
    """Lanza FugaDeDatos si un patientId aparece en dos particiones."""
    conjuntos = {k: {r["patientId"] for r in v} for k, v in particiones.items()}
    nombres = sorted(conjuntos)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            comun = conjuntos[a] & conjuntos[b]
            if comun:
                muestra = sorted(comun)[:3]
                raise FugaDeDatos(
                    f"{len(comun)} paciente(s) en '{a}' y '{b}' a la vez: {muestra}"
                )
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_particion.py -v`
Esperado: 9 passed

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/datos/particion.py tests/test_particion.py
git commit -m "feat: particion por paciente con verificacion anti-fuga"
```

---

### Tarea 3: Métricas binarias y selección de umbral

**Archivos:**
- Crear: `src/copiloto_triaje/modelo/evaluacion.py`
- Prueba: `tests/test_evaluacion.py`

**Interfaces:**
- Consume: nada (lógica pura sobre arreglos de numpy).
- Produce: `metricas_binarias(y_true, y_pred) -> dict` con claves `recall`, `especificidad`, `precision`, `f1`, `tp`, `tn`, `fp`, `fn`; `elegir_umbral(y_true, y_score, especificidad_objetivo, especificidad_minima, recall_objetivo) -> tuple[float, dict, str]` donde el tercer elemento nombra el paso de la regla que se aplicó.

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_evaluacion.py
import numpy as np
from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_binarias


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


def test_umbral_relaja_al_paso_2_si_el_recall_no_llega():
    """Clases muy solapadas: con especificidad 0,75 no se alcanza 0,85 de
    recall, asi que la regla debe relajar hasta la especificidad minima."""
    rng = np.random.default_rng(1)
    y = np.array([1] * 200 + [0] * 800)
    score = np.where(y == 1, rng.normal(0.55, 0.20, 1000), rng.normal(0.45, 0.20, 1000))
    umbral, m, paso = elegir_umbral(y, score)
    assert paso in ("paso_2_especificidad_minima", "paso_3_se_conserva_paso_1")
    assert m["especificidad"] >= 0.70


def test_el_umbral_devuelto_reproduce_las_metricas_reportadas():
    rng = np.random.default_rng(2)
    y = np.array([1] * 100 + [0] * 300)
    score = np.where(y == 1, rng.normal(0.8, 0.1, 400), rng.normal(0.2, 0.1, 400))
    umbral, m, _ = elegir_umbral(y, score)
    recalculadas = metricas_binarias(y, (score >= umbral).astype(int))
    assert recalculadas["recall"] == m["recall"]
    assert recalculadas["especificidad"] == m["especificidad"]
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_evaluacion.py -v`
Esperado: FALLA con `ModuleNotFoundError`

- [ ] **Paso 3: Implementar `evaluacion.py`**

```python
# src/copiloto_triaje/modelo/evaluacion.py
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
        if i2 is not None and tpr[i2] >= recall_objetivo:
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
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_evaluacion.py -v`
Esperado: 6 passed

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/modelo/evaluacion.py tests/test_evaluacion.py
git commit -m "feat: metricas binarias y seleccion de umbral por ROC"
```

---

### Tarea 4: Conversión de DICOM a PNG

**Archivos:**
- Crear: `src/copiloto_triaje/datos/dicom.py`
- Prueba: `tests/test_dicom.py`

**Interfaces:**
- Consume: nada.
- Produce: `leer_dicom(ruta) -> tuple[np.ndarray, dict]`; `convertir_a_png(ruta_dcm, ruta_png) -> dict` (metadatos con claves `patientId`, `edad`, `sexo`, `vista`, `filas`, `columnas`, `archivo_png`); `convertir_lote(rutas_dcm, dir_png) -> tuple[list[dict], list[dict]]` que devuelve `(convertidos, omitidos)`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_dicom.py
import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian

from copiloto_triaje.datos.dicom import convertir_a_png, convertir_lote, leer_dicom


def crear_dicom(ruta, patient_id="P0001", edad="51", sexo="F", vista="PA", lado=64):
    """Crea un DICOM minimo equivalente a los de RSNA: uint8 MONOCHROME2."""
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientAge = edad
    ds.PatientSex = sexo
    ds.ViewPosition = vista
    ds.Modality = "CR"
    ds.Rows, ds.Columns = lado, lado
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    arr = (np.arange(lado * lado, dtype=np.uint8) % 256).reshape(lado, lado)
    ds.PixelData = arr.tobytes()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.save_as(str(ruta), enforce_file_format=True)
    return arr


def test_leer_dicom_devuelve_pixeles_y_metadatos(tmp_path):
    ruta = tmp_path / "a.dcm"
    esperado = crear_dicom(ruta)
    arr, meta = leer_dicom(ruta)
    assert arr.shape == esperado.shape
    assert meta["patientId"] == "P0001"
    assert meta["edad"] == "51"
    assert meta["sexo"] == "F"
    assert meta["vista"] == "PA"


def test_convertir_a_png_escribe_el_archivo_y_conserva_tamano(tmp_path):
    from PIL import Image
    dcm = tmp_path / "a.dcm"
    crear_dicom(dcm, lado=128)
    png = tmp_path / "salida" / "a.png"
    meta = convertir_a_png(dcm, png)
    assert png.exists()
    assert Image.open(png).size == (128, 128)
    assert meta["archivo_png"] == "a.png"


def test_convertir_lote_omite_los_corruptos_sin_abortar(tmp_path):
    buenos = []
    for i in range(3):
        r = tmp_path / f"b{i}.dcm"
        crear_dicom(r, patient_id=f"P{i:04d}")
        buenos.append(r)
    corrupto = tmp_path / "malo.dcm"
    corrupto.write_bytes(b"esto no es un DICOM")
    convertidos, omitidos = convertir_lote(buenos + [corrupto], tmp_path / "png")
    assert len(convertidos) == 3
    assert len(omitidos) == 1
    assert omitidos[0]["archivo"] == "malo.dcm"
    assert omitidos[0]["motivo"]


def test_convertir_lote_es_idempotente(tmp_path):
    r = tmp_path / "a.dcm"
    crear_dicom(r)
    dir_png = tmp_path / "png"
    convertir_lote([r], dir_png)
    mtime = (dir_png / "a.png").stat().st_mtime_ns
    convertidos, _ = convertir_lote([r], dir_png)
    assert len(convertidos) == 1
    assert (dir_png / "a.png").stat().st_mtime_ns == mtime
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_dicom.py -v`
Esperado: FALLA con `ModuleNotFoundError`

- [ ] **Paso 3: Implementar `dicom.py`**

```python
# src/copiloto_triaje/datos/dicom.py
"""Lectura de DICOM de RSNA y conversion a PNG.

Verificado el 16-sep-2026: los DICOM de RSNA vienen en uint8 con
PhotometricInterpretation MONOCHROME2, de modo que la conversion es
directa. El reescalado solo actua como red de seguridad si algun archivo
llegara con otra profundidad de bits.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

CAMPOS = {
    "patientId": "PatientID",
    "edad": "PatientAge",
    "sexo": "PatientSex",
    "vista": "ViewPosition",
}


def leer_dicom(ruta: Path) -> tuple[np.ndarray, dict]:
    """Devuelve (pixeles, metadatos) de un DICOM."""
    ds = pydicom.dcmread(str(ruta))
    meta = {clave: str(getattr(ds, campo, "")) for clave, campo in CAMPOS.items()}
    meta["filas"] = int(getattr(ds, "Rows", 0))
    meta["columnas"] = int(getattr(ds, "Columns", 0))
    return ds.pixel_array, meta


def convertir_a_png(ruta_dcm: Path, ruta_png: Path) -> dict:
    """Convierte un DICOM a PNG de 8 bits y devuelve sus metadatos."""
    arr, meta = leer_dicom(ruta_dcm)
    if arr.dtype != np.uint8:
        minimo, maximo = int(arr.min()), int(arr.max())
        rango = max(maximo - minimo, 1)
        arr = ((arr.astype(np.float32) - minimo) / rango * 255).astype(np.uint8)
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(ruta_png)
    meta["archivo_png"] = ruta_png.name
    return meta


def convertir_lote(rutas_dcm, dir_png: Path) -> tuple[list[dict], list[dict]]:
    """Convierte una lista de DICOM. Un archivo ilegible se omite y se
    registra, pero nunca aborta el proceso: una perdida silenciosa de datos
    seria peor que un fallo ruidoso.

    Es idempotente: si el PNG ya existe, no lo reescribe.
    """
    dir_png = Path(dir_png)
    dir_png.mkdir(parents=True, exist_ok=True)
    convertidos: list[dict] = []
    omitidos: list[dict] = []
    for ruta in rutas_dcm:
        ruta = Path(ruta)
        destino = dir_png / (ruta.stem + ".png")
        try:
            if destino.exists():
                _, meta = leer_dicom(ruta)
                meta["archivo_png"] = destino.name
            else:
                meta = convertir_a_png(ruta, destino)
            convertidos.append(meta)
        except Exception as exc:  # noqa: BLE001 - se registra y se continua
            omitidos.append({"archivo": ruta.name, "motivo": f"{type(exc).__name__}: {exc}"})
    return convertidos, omitidos
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_dicom.py -v`
Esperado: 4 passed

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/datos/dicom.py tests/test_dicom.py
git commit -m "feat: conversion DICOM a PNG con omision registrada de corruptos"
```

---

### Tarea 5: Dataset de PyTorch y transformaciones

**Archivos:**
- Crear: `src/copiloto_triaje/datos/dataset.py`
- Prueba: `tests/test_dataset.py`

**Interfaces:**
- Consume: `Config` (Tarea 1) para `tam_imagen`.
- Produce: `construir_transformaciones(tam_imagen, entrenamiento) -> Compose`; `DatasetRadiografias(manifiesto: pd.DataFrame, dir_png: Path, tam_imagen: int, entrenamiento: bool)` cuyo `__getitem__` devuelve `(tensor[3,H,W], etiqueta_float)`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_dataset.py
import numpy as np
import pandas as pd
import torch
from PIL import Image

from copiloto_triaje.datos.dataset import DatasetRadiografias, construir_transformaciones


def manifiesto_y_pngs(tmp_path, n=6):
    dir_png = tmp_path / "png"
    dir_png.mkdir()
    filas = []
    for i in range(n):
        nombre = f"P{i:04d}.png"
        arr = (np.random.default_rng(i).integers(0, 255, (100, 100))).astype(np.uint8)
        Image.fromarray(arr).save(dir_png / nombre)
        filas.append({"archivo_png": nombre, "patientId": f"P{i:04d}", "etiqueta": i % 2})
    return pd.DataFrame(filas), dir_png


def test_devuelve_tensor_de_tres_canales_del_tamano_pedido(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, tam_imagen=224, entrenamiento=False)
    x, y = ds[0]
    assert x.shape == (3, 224, 224)
    assert x.dtype == torch.float32
    assert isinstance(y, torch.Tensor) and y.dtype == torch.float32


def test_la_longitud_coincide_con_el_manifiesto(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path, n=6)
    assert len(DatasetRadiografias(man, dir_png, 224, False)) == 6


def test_la_etiqueta_corresponde_a_su_fila(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, 224, False)
    for i in range(len(ds)):
        assert float(ds[i][1]) == float(man.iloc[i]["etiqueta"])


def test_sin_aumento_el_resultado_es_determinista(tmp_path):
    man, dir_png = manifiesto_y_pngs(tmp_path)
    ds = DatasetRadiografias(man, dir_png, 224, entrenamiento=False)
    assert torch.equal(ds[0][0], ds[0][0])


def test_el_aumento_solo_se_aplica_en_entrenamiento():
    t_train = construir_transformaciones(224, entrenamiento=True)
    t_eval = construir_transformaciones(224, entrenamiento=False)
    nombres_train = [type(t).__name__ for t in t_train.transforms]
    nombres_eval = [type(t).__name__ for t in t_eval.transforms]
    assert "RandomAffine" in nombres_train
    assert "RandomAffine" not in nombres_eval


def test_no_se_usa_volteo_horizontal():
    """La lateralidad cardiaca es informacion clinica: voltear produciria
    imagenes anatomicamente imposibles."""
    nombres = [type(t).__name__ for t in construir_transformaciones(224, True).transforms]
    assert not any("Flip" in n for n in nombres)
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_dataset.py -v`
Esperado: FALLA con `ModuleNotFoundError`

- [ ] **Paso 3: Implementar `dataset.py`**

```python
# src/copiloto_triaje/datos/dataset.py
"""Dataset de PyTorch que lee SIEMPRE desde un manifiesto, nunca del
directorio: asi la particion es un artefacto explicito y auditable."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

MEDIA_IMAGENET = [0.485, 0.456, 0.406]
DESV_IMAGENET = [0.229, 0.224, 0.225]


def construir_transformaciones(tam_imagen: int, entrenamiento: bool):
    """Transformaciones de imagen. El aumento solo se aplica en entrenamiento.

    No se usa volteo horizontal: la lateralidad cardiaca es informacion
    clinica real y voltearla produciria anatomia imposible.
    """
    pasos = [transforms.Resize((tam_imagen, tam_imagen))]
    if entrenamiento:
        pasos.append(transforms.RandomAffine(degrees=7, translate=(0.05, 0.05)))
        pasos.append(transforms.ColorJitter(brightness=0.15, contrast=0.15))
    pasos.append(transforms.ToTensor())
    pasos.append(transforms.Normalize(MEDIA_IMAGENET, DESV_IMAGENET))
    return transforms.Compose(pasos)


class DatasetRadiografias(Dataset):
    """Lee las imagenes listadas en un manifiesto y devuelve (tensor, etiqueta)."""

    def __init__(self, manifiesto: pd.DataFrame, dir_png, tam_imagen: int = 224,
                 entrenamiento: bool = False):
        self.manifiesto = manifiesto.reset_index(drop=True)
        self.dir_png = Path(dir_png)
        self.transformaciones = construir_transformaciones(tam_imagen, entrenamiento)

    def __len__(self) -> int:
        return len(self.manifiesto)

    def __getitem__(self, indice: int):
        fila = self.manifiesto.iloc[indice]
        ruta = self.dir_png / fila["archivo_png"]
        imagen = Image.open(ruta).convert("RGB")  # 3 canales: la red es de ImageNet
        x = self.transformaciones(imagen)
        y = torch.tensor(float(fila["etiqueta"]), dtype=torch.float32)
        return x, y
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_dataset.py -v`
Esperado: 6 passed

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/datos/dataset.py tests/test_dataset.py
git commit -m "feat: dataset de PyTorch leido desde manifiesto"
```

---

### Tarea 6: Arquitectura del modelo

**Archivos:**
- Crear: `src/copiloto_triaje/modelo/arquitectura.py`
- Prueba: `tests/test_arquitectura.py`

**Interfaces:**
- Consume: nada.
- Produce: `construir_modelo(congelar_backbone=True, preentrenado=True) -> nn.Module` con una única salida (logit); `descongelar_para_ajuste(modelo, n_bloques=3) -> None`; `contar_parametros_entrenables(modelo) -> int`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_arquitectura.py
import torch

from copiloto_triaje.modelo.arquitectura import (
    construir_modelo, contar_parametros_entrenables, descongelar_para_ajuste,
)


def test_el_modelo_tiene_una_sola_salida():
    """Una salida (logit) + BCEWithLogitsLoss, no dos clases con softmax."""
    modelo = construir_modelo(preentrenado=False)
    salida = modelo(torch.randn(2, 3, 224, 224))
    assert salida.shape == (2, 1)


def test_congelar_backbone_deja_entrenable_solo_la_cabeza():
    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    assert all(not p.requires_grad for p in modelo.features.parameters())
    assert any(p.requires_grad for p in modelo.classifier.parameters())


def test_descongelar_aumenta_los_parametros_entrenables():
    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    antes = contar_parametros_entrenables(modelo)
    descongelar_para_ajuste(modelo, n_bloques=3)
    assert contar_parametros_entrenables(modelo) > antes


def test_sin_congelar_todo_es_entrenable():
    modelo = construir_modelo(congelar_backbone=False, preentrenado=False)
    assert all(p.requires_grad for p in modelo.parameters())


def test_latencia_de_inferencia_en_cpu_bajo_el_limite():
    """Criterio de aceptacion del spec: menos de 4 s por imagen en CPU, que es
    lo que SP2 debe poder servir desde el VPS. Se mide la mediana de 5 pasadas
    para no depender de la primera, que incluye calentamiento."""
    import time
    modelo = construir_modelo(preentrenado=False).eval()
    entrada = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        modelo(entrada)  # calentamiento
        tiempos = []
        for _ in range(5):
            inicio = time.perf_counter()
            modelo(entrada)
            tiempos.append(time.perf_counter() - inicio)
    mediana = sorted(tiempos)[2]
    assert mediana < 4.0, f"latencia {mediana:.3f}s supera el limite de 4 s"
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_arquitectura.py -v`
Esperado: FALLA con `ModuleNotFoundError`

- [ ] **Paso 3: Implementar `arquitectura.py`**

```python
# src/copiloto_triaje/modelo/arquitectura.py
"""Construccion del modelo de clasificacion.

Se elige MobileNetV3-Large sobre ResNet50 por una razon de sistema, no de
exactitud: SP2 exige servir la inferencia en la CPU del VPS en menos de 4
segundos. Entrenar primero el modelo que se va a poder servir evita
rehacer el trabajo.
"""
from __future__ import annotations

import torch.nn as nn
from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large


def construir_modelo(congelar_backbone: bool = True, preentrenado: bool = True) -> nn.Module:
    """MobileNetV3-Large con una unica salida (logit) para clasificacion binaria."""
    pesos = MobileNet_V3_Large_Weights.IMAGENET1K_V1 if preentrenado else None
    modelo = mobilenet_v3_large(weights=pesos)
    entradas = modelo.classifier[-1].in_features
    modelo.classifier[-1] = nn.Linear(entradas, 1)
    if congelar_backbone:
        for parametro in modelo.features.parameters():
            parametro.requires_grad = False
    return modelo


def descongelar_para_ajuste(modelo: nn.Module, n_bloques: int = 3) -> None:
    """Descongela los ultimos n bloques del extractor para el ajuste fino."""
    bloques = list(modelo.features)
    for bloque in bloques[-n_bloques:]:
        for parametro in bloque.parameters():
            parametro.requires_grad = True


def contar_parametros_entrenables(modelo: nn.Module) -> int:
    return sum(p.numel() for p in modelo.parameters() if p.requires_grad)
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_arquitectura.py -v`
Esperado: 5 passed

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/modelo/arquitectura.py tests/test_arquitectura.py
git commit -m "feat: MobileNetV3-Large con salida binaria y congelado por fases"
```

---

### Tarea 7: Bucle de entrenamiento con early stopping y checkpoints

**Archivos:**
- Crear: `src/copiloto_triaje/modelo/entrenamiento.py`
- Prueba: `tests/test_entrenamiento.py`

**Interfaces:**
- Consume: `construir_modelo`, `descongelar_para_ajuste` (Tarea 6); `metricas_binarias` (Tarea 3).
- Produce: `evaluar_epoca(modelo, cargador, dispositivo) -> tuple[np.ndarray, np.ndarray]` que devuelve `(y_true, y_score)`; `entrenar(modelo, cargador_train, cargador_val, cfg, dispositivo, dir_checkpoints) -> dict` con claves `mejor_recall`, `mejor_epoca`, `historial`, `ruta_mejor_checkpoint`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_entrenamiento.py
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from copiloto_triaje.config import Config
from copiloto_triaje.modelo.entrenamiento import entrenar, evaluar_epoca


class ModeloTrivial(torch.nn.Module):
    """Un lineal sobre la media de la imagen: entrena rapido en CPU."""

    def __init__(self):
        super().__init__()
        self.capa = torch.nn.Linear(1, 1)

    def forward(self, x):
        return self.capa(x.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(1))


def cargadores_sinteticos(n=32):
    g = torch.Generator().manual_seed(0)
    y = torch.cat([torch.ones(n // 2), torch.zeros(n // 2)])
    x = torch.randn(n, 3, 8, 8, generator=g) + y.view(-1, 1, 1, 1) * 2.0
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=8), DataLoader(ds, batch_size=8)


def test_evaluar_epoca_devuelve_etiquetas_y_puntajes_alineados():
    _, val = cargadores_sinteticos()
    y_true, y_score = evaluar_epoca(ModeloTrivial(), val, torch.device("cpu"))
    assert len(y_true) == len(y_score) == 32
    assert set(np.unique(y_true)).issubset({0.0, 1.0})


def test_entrenar_devuelve_historial_y_guarda_checkpoint(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=2, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    assert len(res["historial"]) == 2
    assert "recall" in res["historial"][0]
    assert res["ruta_mejor_checkpoint"].exists()


def test_el_checkpoint_guardado_se_puede_recargar(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=1, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    estado = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)
    assert "modelo" in estado and "epoca" in estado
    ModeloTrivial().load_state_dict(estado["modelo"])


def test_early_stopping_corta_antes_del_maximo_de_epocas(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=20, epocas_ajuste=0, paciencia=1)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    assert len(res["historial"]) < 20
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_entrenamiento.py -v`
Esperado: FALLA con `ModuleNotFoundError`

- [ ] **Paso 3: Implementar `entrenamiento.py`**

```python
# src/copiloto_triaje/modelo/entrenamiento.py
"""Bucle de entrenamiento en dos fases con early stopping por RECALL.

El criterio de parada observa el Recall en validacion, no la exactitud ni
la perdida: con 22,5% de positivos, la exactitud premia al modelo que
nunca detecta a nadie.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from copiloto_triaje.modelo.arquitectura import descongelar_para_ajuste
from copiloto_triaje.modelo.evaluacion import metricas_binarias


def evaluar_epoca(modelo, cargador, dispositivo) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (y_true, y_score) con y_score = probabilidad de la clase positiva."""
    modelo.eval()
    etiquetas, puntajes = [], []
    with torch.no_grad():
        for x, y in cargador:
            logits = modelo(x.to(dispositivo)).squeeze(1)
            puntajes.append(torch.sigmoid(logits).cpu().numpy())
            etiquetas.append(y.numpy())
    return np.concatenate(etiquetas), np.concatenate(puntajes)


def _etiquetas_de(cargador) -> np.ndarray:
    """Etiquetas del conjunto sin cargar las imagenes, si el dataset expone su
    manifiesto. Solo itera el cargador como ultimo recurso."""
    dataset = cargador.dataset
    manifiesto = getattr(dataset, "manifiesto", None)
    if manifiesto is not None and "etiqueta" in manifiesto:
        return manifiesto["etiqueta"].to_numpy(dtype=float)
    return np.concatenate([y.numpy() for _, y in cargador])


def _pasada_de_entrenamiento(modelo, cargador, criterio, optimizador, dispositivo) -> float:
    modelo.train()
    perdida_total = 0.0
    for x, y in cargador:
        x, y = x.to(dispositivo), y.to(dispositivo)
        optimizador.zero_grad()
        perdida = criterio(modelo(x).squeeze(1), y)
        perdida.backward()
        optimizador.step()
        perdida_total += float(perdida) * x.size(0)
    return perdida_total / len(cargador.dataset)


def entrenar(modelo, cargador_train, cargador_val, cfg, dispositivo,
             dir_checkpoints) -> dict:
    """Entrena en dos fases y devuelve el historial y el mejor checkpoint.

    Fase 1: solo la cabeza (backbone congelado), `cfg.epocas_cabeza` epocas.
    Fase 2: ajuste fino de los ultimos bloques, `cfg.epocas_ajuste` epocas.
    En ambas, early stopping por Recall en validacion con `cfg.paciencia`.
    """
    dir_checkpoints = Path(dir_checkpoints)
    dir_checkpoints.mkdir(parents=True, exist_ok=True)
    modelo = modelo.to(dispositivo)

    # peso de la clase positiva: compensa el desbalance 22,5 / 77,5.
    # Se leen las etiquetas del manifiesto cuando existe: iterar el cargador
    # cargaria y transformaria las 18 000 imagenes solo para contar etiquetas.
    etiquetas_train = _etiquetas_de(cargador_train)
    positivos = max(float(etiquetas_train.sum()), 1.0)
    negativos = max(float(len(etiquetas_train) - positivos), 1.0)
    peso_positivo = torch.tensor([negativos / positivos], device=dispositivo)
    criterio = nn.BCEWithLogitsLoss(pos_weight=peso_positivo)

    historial: list[dict] = []
    mejor_recall, mejor_epoca, sin_mejora = -1.0, -1, 0
    ruta_mejor = dir_checkpoints / "mejor.pt"

    fases = [("cabeza", cfg.epocas_cabeza, cfg.lr_cabeza),
             ("ajuste", cfg.epocas_ajuste, cfg.lr_ajuste)]

    for nombre_fase, n_epocas, lr in fases:
        if n_epocas <= 0:
            continue
        if nombre_fase == "ajuste":
            descongelar_para_ajuste(modelo)
        parametros = [p for p in modelo.parameters() if p.requires_grad]
        optimizador = torch.optim.Adam(parametros, lr=lr)

        for epoca in range(n_epocas):
            perdida = _pasada_de_entrenamiento(
                modelo, cargador_train, criterio, optimizador, dispositivo)
            y_true, y_score = evaluar_epoca(modelo, cargador_val, dispositivo)
            m = metricas_binarias(y_true, (y_score >= 0.5).astype(int))
            registro = {"fase": nombre_fase, "epoca": len(historial),
                        "perdida": perdida, "recall": m["recall"],
                        "especificidad": m["especificidad"]}
            historial.append(registro)

            torch.save({"modelo": modelo.state_dict(), "epoca": registro["epoca"],
                        "metricas": m}, dir_checkpoints / "ultimo.pt")

            if m["recall"] > mejor_recall:
                mejor_recall, mejor_epoca, sin_mejora = m["recall"], registro["epoca"], 0
                torch.save({"modelo": modelo.state_dict(), "epoca": registro["epoca"],
                            "metricas": m}, ruta_mejor)
            else:
                sin_mejora += 1
                if sin_mejora >= cfg.paciencia:
                    return {"mejor_recall": mejor_recall, "mejor_epoca": mejor_epoca,
                            "historial": historial, "ruta_mejor_checkpoint": ruta_mejor}

    return {"mejor_recall": mejor_recall, "mejor_epoca": mejor_epoca,
            "historial": historial, "ruta_mejor_checkpoint": ruta_mejor}
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_entrenamiento.py -v`
Esperado: 4 passed

- [ ] **Paso 5: Commit**

```bash
git add src/copiloto_triaje/modelo/entrenamiento.py tests/test_entrenamiento.py
git commit -m "feat: entrenamiento en dos fases con early stopping por recall"
```

---

### Tarea 8: Línea de órdenes de preparación de datos

Convierte el zip real en PNG y manifiestos. Es la única tarea que toca los 26 684 archivos.

**Archivos:**
- Crear: `src/copiloto_triaje/datos/preparacion.py`
- Crear: `scripts/preparar_datos.py`
- Prueba: `tests/test_preparacion.py`

**Interfaces:**
- Consume: `convertir_lote` (Tarea 4), `particionar_por_paciente` y `verificar_sin_fuga` (Tarea 2), `Config` (Tarea 1).
- Produce: `cargar_etiquetas(ruta_csv) -> dict[str, int]`; `construir_registros(metadatos, etiquetas) -> list[dict]`; `escribir_manifiestos(particiones, dir_manifiestos, semilla) -> dict[str, Path]`.

- [ ] **Paso 1: Escribir las pruebas que fallan**

```python
# tests/test_preparacion.py
import pandas as pd
import pytest

from copiloto_triaje.datos.preparacion import (
    cargar_etiquetas, construir_registros, escribir_manifiestos,
)
from copiloto_triaje.datos.particion import particionar_por_paciente


def test_cargar_etiquetas_colapsa_las_filas_por_paciente(tmp_path):
    """Un paciente positivo tiene varias filas (una por caja); debe quedar
    una sola etiqueta y ser positiva."""
    csv = tmp_path / "labels.csv"
    csv.write_text(
        "patientId,x,y,width,height,Target\n"
        "P0001,10,10,50,50,1\n"
        "P0001,80,80,40,40,1\n"
        "P0002,,,,,0\n", encoding="utf-8")
    etiquetas = cargar_etiquetas(csv)
    assert etiquetas == {"P0001": 1, "P0002": 0}


def test_construir_registros_cruza_metadatos_con_etiquetas():
    metadatos = [{"patientId": "P0001", "archivo_png": "P0001.png", "edad": "51"},
                 {"patientId": "P0002", "archivo_png": "P0002.png", "edad": "19"}]
    registros = construir_registros(metadatos, {"P0001": 1, "P0002": 0})
    assert len(registros) == 2
    assert registros[0]["etiqueta"] == 1
    assert registros[1]["etiqueta"] == 0


def test_construir_registros_descarta_los_que_no_tienen_etiqueta():
    metadatos = [{"patientId": "P0001", "archivo_png": "P0001.png"},
                 {"patientId": "FANTASMA", "archivo_png": "X.png"}]
    registros = construir_registros(metadatos, {"P0001": 1})
    assert [r["patientId"] for r in registros] == ["P0001"]


def test_escribir_manifiestos_crea_tres_csv_con_la_semilla(tmp_path):
    registros = [{"patientId": f"P{i:04d}", "archivo_png": f"P{i:04d}.png",
                  "etiqueta": i % 4 == 0} for i in range(100)]
    for r in registros:
        r["etiqueta"] = int(r["etiqueta"])
    particiones = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    rutas = escribir_manifiestos(particiones, tmp_path, semilla=42)
    assert set(rutas) == {"train", "val", "test"}
    for nombre, ruta in rutas.items():
        df = pd.read_csv(ruta)
        assert {"patientId", "archivo_png", "etiqueta", "semilla"} <= set(df.columns)
        assert (df["semilla"] == 42).all()
```

- [ ] **Paso 2: Ejecutar las pruebas y comprobar que fallan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_preparacion.py -v`
Esperado: FALLA con `ModuleNotFoundError`

- [ ] **Paso 3: Implementar `preparacion.py`**

```python
# src/copiloto_triaje/datos/preparacion.py
"""Cruce de metadatos con etiquetas y escritura de manifiestos."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def cargar_etiquetas(ruta_csv: Path) -> dict[str, int]:
    """Lee stage_2_train_labels.csv y colapsa las filas por paciente.

    Hay mas filas que pacientes porque un positivo puede tener varias cajas;
    el paciente es positivo si alguna de sus filas lo es.
    """
    df = pd.read_csv(ruta_csv)
    agrupado = df.groupby("patientId")["Target"].max()
    return {str(k): int(v) for k, v in agrupado.items()}


def construir_registros(metadatos: list[dict], etiquetas: dict[str, int]) -> list[dict]:
    """Une metadatos de imagen con su etiqueta. Descarta los sin etiqueta."""
    registros = []
    for meta in metadatos:
        pid = meta.get("patientId")
        if pid in etiquetas:
            registro = dict(meta)
            registro["etiqueta"] = int(etiquetas[pid])
            registros.append(registro)
    return registros


def escribir_manifiestos(particiones: dict[str, list[dict]], dir_manifiestos,
                         semilla: int) -> dict[str, Path]:
    """Escribe train.csv, val.csv y test.csv con la semilla registrada."""
    dir_manifiestos = Path(dir_manifiestos)
    dir_manifiestos.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, registros in particiones.items():
        df = pd.DataFrame(registros)
        df["semilla"] = semilla
        ruta = dir_manifiestos / f"{nombre}.csv"
        df.to_csv(ruta, index=False)
        rutas[nombre] = ruta
    return rutas
```

- [ ] **Paso 4: Ejecutar las pruebas y comprobar que pasan**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_preparacion.py -v`
Esperado: 4 passed

- [ ] **Paso 5: Escribir el script de línea de órdenes**

```python
# scripts/preparar_datos.py
"""Prepara los datos de RSNA: zip -> PNG -> manifiestos.

Uso:
    C:\\venv-copiloto\\Scripts\\python.exe scripts/preparar_datos.py ^
        --zip "C:\\Users\\[retirado]\\datasets\\rsna-pneumonia\\rsna-pneumonia-detection-challenge.zip" ^
        --raiz "C:\\Users\\[retirado]\\datasets\\rsna-pneumonia\\trabajo" ^
        [--limite 200]

Es idempotente: descomprimir y convertir se saltan si ya estan hechos.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copiloto_triaje.config import Config  # noqa: E402
from copiloto_triaje.datos.dicom import convertir_lote  # noqa: E402
from copiloto_triaje.datos.particion import (  # noqa: E402
    particionar_por_paciente, verificar_sin_fuga,
)
from copiloto_triaje.datos.preparacion import (  # noqa: E402
    cargar_etiquetas, construir_registros, escribir_manifiestos,
)


def descomprimir(zip_rsna: Path, destino: Path) -> Path:
    """Descomprime el zip si aun no se hizo. Devuelve el directorio."""
    marca = destino / ".descomprimido"
    if marca.exists():
        print(f"[1/4] Ya descomprimido en {destino}")
        return destino
    destino.mkdir(parents=True, exist_ok=True)
    print(f"[1/4] Descomprimiendo {zip_rsna.name} ...")
    with zipfile.ZipFile(zip_rsna) as z:
        z.extractall(destino)
    marca.write_text("ok", encoding="utf-8")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara los datos de RSNA")
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--raiz", required=True, type=Path)
    parser.add_argument("--limite", type=int, default=0,
                        help="procesar solo N imagenes (para pruebas rapidas)")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    cfg = Config(raiz_datos=args.raiz, zip_rsna=args.zip, semilla=args.semilla)
    crudo = descomprimir(args.zip, args.raiz / "crudo")

    dicoms = sorted((crudo / "stage_2_train_images").glob("*.dcm"))
    if args.limite:
        dicoms = dicoms[: args.limite]
    print(f"[2/4] Convirtiendo {len(dicoms)} DICOM a PNG ...")
    convertidos, omitidos = convertir_lote(dicoms, cfg.dir_png)
    print(f"      convertidos: {len(convertidos)} | omitidos: {len(omitidos)}")
    if omitidos:
        (cfg.dir_png.parent / "omitidos.json").write_text(
            json.dumps(omitidos, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[3/4] Cruzando con las etiquetas ...")
    etiquetas = cargar_etiquetas(crudo / "stage_2_train_labels.csv")
    registros = construir_registros(convertidos, etiquetas)
    positivos = sum(r["etiqueta"] for r in registros)
    print(f"      registros: {len(registros)} | positivos: {positivos} "
          f"({positivos / max(len(registros), 1) * 100:.1f}%)")

    print("[4/4] Particionando por paciente y verificando fuga ...")
    particiones = particionar_por_paciente(registros, cfg.proporciones, cfg.semilla)
    verificar_sin_fuga(particiones)
    rutas = escribir_manifiestos(particiones, cfg.dir_manifiestos, cfg.semilla)
    for nombre, ruta in rutas.items():
        print(f"      {nombre}: {len(particiones[nombre])} imagenes -> {ruta}")
    print("LISTO. Sin fuga de datos entre particiones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Paso 6: Ejecutar el script sobre una muestra real de 200 imágenes**

Ejecutar:
```bash
C:\venv-copiloto\Scripts\python.exe scripts/preparar_datos.py --zip "C:\Users\[retirado]\datasets\rsna-pneumonia\rsna-pneumonia-detection-challenge.zip" --raiz "C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo" --limite 200
```
Esperado: termina con `LISTO. Sin fuga de datos entre particiones.` y los tres manifiestos escritos. La descompresión completa tarda varios minutos la primera vez.

- [ ] **Paso 7: Commit**

```bash
git add src/copiloto_triaje/datos/preparacion.py scripts/preparar_datos.py tests/test_preparacion.py
git commit -m "feat: preparacion de datos de zip a manifiestos con verificacion"
```

---

### Tarea 9: Prueba de humo de punta a punta

Demuestra que todo el pipeline corre sin GPU en menos de un minuto. Es la prueba que protege contra roturas de integración entre módulos.

**Archivos:**
- Prueba: `tests/test_humo.py`

**Interfaces:**
- Consume: todo lo anterior.
- Produce: nada (solo verificación).

- [ ] **Paso 1: Escribir la prueba de humo**

```python
# tests/test_humo.py
"""Entrenamiento completo de punta a punta con imagenes sinteticas.

No mide calidad del modelo: demuestra que las piezas encajan y que el
pipeline corre en CPU. Debe tardar menos de un minuto.
"""
import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader

from copiloto_triaje.config import Config
from copiloto_triaje.datos.dataset import DatasetRadiografias
from copiloto_triaje.datos.particion import particionar_por_paciente, verificar_sin_fuga
from copiloto_triaje.datos.preparacion import escribir_manifiestos
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.modelo.entrenamiento import entrenar, evaluar_epoca
from copiloto_triaje.modelo.evaluacion import elegir_umbral


def test_pipeline_completo_en_cpu(tmp_path):
    rng = np.random.default_rng(0)
    dir_png = tmp_path / "png"
    dir_png.mkdir()

    # 50 pacientes: los positivos llevan una mancha clara, para que el modelo
    # tenga algo que aprender en dos epocas.
    registros = []
    for i in range(50):
        etiqueta = int(i < 15)
        arr = rng.integers(0, 120, (64, 64), dtype=np.uint8)
        if etiqueta:
            arr[20:40, 20:40] = 240
        nombre = f"P{i:04d}.png"
        Image.fromarray(arr).save(dir_png / nombre)
        registros.append({"patientId": f"P{i:04d}", "archivo_png": nombre,
                          "etiqueta": etiqueta})

    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 tam_imagen=64, lote=8, epocas_cabeza=2, epocas_ajuste=0)

    particiones = particionar_por_paciente(registros, cfg.proporciones, cfg.semilla)
    verificar_sin_fuga(particiones)
    escribir_manifiestos(particiones, cfg.dir_manifiestos, cfg.semilla)

    def cargador(nombre, entrenamiento):
        df = pd.read_csv(cfg.dir_manifiestos / f"{nombre}.csv")
        ds = DatasetRadiografias(df, dir_png, cfg.tam_imagen, entrenamiento)
        return DataLoader(ds, batch_size=cfg.lote, shuffle=entrenamiento)

    modelo = construir_modelo(congelar_backbone=True, preentrenado=False)
    resultado = entrenar(modelo, cargador("train", True), cargador("val", False),
                         cfg, torch.device("cpu"), cfg.dir_checkpoints)

    assert len(resultado["historial"]) >= 1
    assert resultado["ruta_mejor_checkpoint"].exists()

    y_true, y_score = evaluar_epoca(modelo, cargador("test", False), torch.device("cpu"))
    assert len(y_true) == len(y_score) > 0
    umbral, metricas, paso = elegir_umbral(y_true, y_score)
    assert 0.0 <= metricas["recall"] <= 1.0
    assert "umbral" in metricas and paso
```

- [ ] **Paso 2: Ejecutar la prueba de humo**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_humo.py -v --durations=3`
Esperado: 1 passed, en menos de 60 segundos

- [ ] **Paso 3: Ejecutar la batería completa de pruebas**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest -v`
Esperado: 43 passed (4+9+6+4+6+5+4+4+1)

- [ ] **Paso 4: Commit**

```bash
git add tests/test_humo.py
git commit -m "test: prueba de humo de punta a punta en CPU"
```

---

### Tarea 10: Notebook de entrenamiento en GPU y README

**Archivos:**
- Crear: `notebooks/entrenar_gpu.ipynb`
- Crear: `README.md`

**Interfaces:**
- Consume: todo el paquete.
- Produce: nada (documentación y punto de entrada para GPU).

- [ ] **Paso 1: Crear el notebook con exactamente estas seis celdas**

El notebook no contiene lógica: trae el código, trae los datos y llama al paquete. Tres reglas que gobiernan su diseño:

1. **El dataset se descarga dentro de Colab desde Kaggle, nunca se sube desde la máquina local.** Subir 3,66 GB a Drive consumiría casi toda la cuota gratuita de 15 GB y tardaría horas; Colab lo baja de Kaggle en uno o dos minutos por su conexión de centro de datos.
2. **Los checkpoints y el reporte van a Drive, no a `/content`.** Colab borra `/content` al caerse la sesión, que es exactamente el escenario del que los checkpoints deben protegernos.
3. **Las credenciales de Kaggle se leen de los Secretos de Colab**, no de un archivo subido: se configuran una vez en el icono de la llave del panel lateral y no quedan en el notebook.

Crear `notebooks/entrenar_gpu.ipynb` con estas celdas, en este orden:

```python
# Celda 1 - comprobar GPU e instalar lo que Colab no trae
!nvidia-smi
!pip install -q pydicom
import torch
assert torch.cuda.is_available(), "Sin GPU: en Colab, Entorno de ejecucion > Cambiar tipo > GPU"
print('GPU:', torch.cuda.get_device_name(0))
```

```python
# Celda 2 - traer el codigo del paquete
# Opcion A (mientras el repo sea privado): comprimir la carpeta copiloto-triaje
# en el equipo y subirla aqui. Pesa unos 100 KB.
import sys, pathlib, zipfile
from google.colab import files

subidos = files.upload()            # seleccionar copiloto-triaje.zip
nombre = next(iter(subidos))
with zipfile.ZipFile(nombre) as z:
    z.extractall('/content')
RAIZ = pathlib.Path('/content/copiloto-triaje')

# Opcion B (cuando el repo sea publico, hito H8): comentar lo de arriba y usar
# !git clone https://github.com/<usuario>/copiloto-triaje.git /content/copiloto-triaje

sys.path.insert(0, str(RAIZ / 'src'))
import copiloto_triaje
print('paquete cargado desde', RAIZ)
```

```python
# Celda 3 - Drive para lo que debe sobrevivir, y descarga del dataset desde Kaggle
import os, pathlib
from google.colab import drive, userdata

drive.mount('/content/drive')
PERSISTENTE = pathlib.Path('/content/drive/MyDrive/copiloto-triaje')
PERSISTENTE.mkdir(parents=True, exist_ok=True)

# Secretos de Colab (icono de la llave): KAGGLE_USERNAME y KAGGLE_KEY
os.environ['KAGGLE_USERNAME'] = userdata.get('KAGGLE_USERNAME')
os.environ['KAGGLE_KEY'] = userdata.get('KAGGLE_KEY')

!pip install -q kaggle
!kaggle competitions download -c rsna-pneumonia-detection-challenge -p /content/datos
ZIP = '/content/datos/rsna-pneumonia-detection-challenge.zip'
print('descargado:', pathlib.Path(ZIP).stat().st_size / 1e9, 'GB')
```

```python
# Celda 4 - preparar los datos: zip -> PNG -> manifiestos (dentro de Colab)
!python {RAIZ}/scripts/preparar_datos.py --zip {ZIP} --raiz /content/trabajo
```

```python
# Celda 5 - entrenamiento completo con GPU, checkpoints en Drive
import torch, pandas as pd, pathlib
from torch.utils.data import DataLoader
from copiloto_triaje.config import Config
from copiloto_triaje.datos.dataset import DatasetRadiografias
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.modelo.entrenamiento import entrenar

cfg = Config(raiz_datos=pathlib.Path('/content/trabajo'),
             zip_rsna=pathlib.Path(ZIP), lote=64)
dispositivo = torch.device('cuda')
DIR_CHECKPOINTS = PERSISTENTE / 'checkpoints'   # en Drive: sobrevive a la caida

def cargador(nombre, entrenamiento):
    df = pd.read_csv(cfg.dir_manifiestos / f'{nombre}.csv')
    ds = DatasetRadiografias(df, cfg.dir_png, cfg.tam_imagen, entrenamiento)
    return DataLoader(ds, batch_size=cfg.lote, shuffle=entrenamiento, num_workers=2)

modelo = construir_modelo(congelar_backbone=True, preentrenado=True)
resultado = entrenar(modelo, cargador('train', True), cargador('val', False),
                     cfg, dispositivo, DIR_CHECKPOINTS)
print('mejor recall en validacion:', resultado['mejor_recall'],
      '| epoca:', resultado['mejor_epoca'])
```

```python
# Celda 6 - umbral en VALIDACION, evaluacion UNICA en prueba, reporte a Drive
import json
from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_binarias
from copiloto_triaje.modelo.entrenamiento import evaluar_epoca

y_val, s_val = evaluar_epoca(modelo, cargador('val', False), dispositivo)
umbral, m_val, paso = elegir_umbral(y_val, s_val, cfg.especificidad_objetivo,
                                    cfg.especificidad_minima, cfg.recall_objetivo)
print('umbral elegido en validacion:', umbral, '| regla aplicada:', paso)

# El conjunto de prueba se toca UNA sola vez, con el umbral ya congelado.
y_test, s_test = evaluar_epoca(modelo, cargador('test', False), dispositivo)
m_test = metricas_binarias(y_test, (s_test >= umbral).astype(int))
print(json.dumps(m_test, indent=2, ensure_ascii=False))

(PERSISTENTE / 'reporte_metricas.json').write_text(
    json.dumps({'umbral': umbral, 'regla': paso, 'validacion': m_val,
                'prueba': m_test, 'historial': resultado['historial']},
               indent=2, ensure_ascii=False), encoding='utf-8')
print('reporte y checkpoints guardados en', PERSISTENTE)
```

**Alternativa: notebooks de Kaggle.** Tu cuenta ya los tiene habilitados y ahí el dataset de la competencia **se adjunta sin descargar nada** (Add Input → Competitions → RSNA). Si Colab da problemas de cuota de GPU, se cambian las celdas 1 a 4 por adjuntar el dataset y apuntar `--raiz /kaggle/working`; las celdas 5 y 6 quedan idénticas porque el paquete es el mismo.

- [ ] **Paso 2: Escribir el `README.md`**

```markdown
# Copiloto de triaje para neumonía en adultos — núcleo de imagen (SP1)

Primer sub-proyecto del Proyecto Integrador (UEES, Maestría en IA). Entrena una
CNN de clasificación binaria sobre radiografías de tórax de adultos del dataset
RSNA, con partición por paciente verificada sin fuga de datos.

## Requisitos

Entorno virtual en **ruta corta** (obligatorio en Windows: el Python de Microsoft
Store provoca `WinError 206` al instalar torchvision):

```
python -m venv C:\venv-copiloto
C:\venv-copiloto\Scripts\python.exe -m pip install -e ".[dev]"
```

## Dónde corre cada cosa

El mismo paquete se ejecuta en dos sitios, y la división no es negociable:

| | Máquina local | Colab / Kaggle |
| :--- | :--- | :--- |
| **Tiene GPU** | No (`torch...+cpu`) | Sí |
| Desarrollo y pruebas | Sí | — |
| Entrenamiento de humo (2 épocas, datos sintéticos) | Sí | — |
| Preparación de datos (26 684 DICOM) | solo una muestra, para verificar el script | Sí, el conjunto completo |
| **Entrenamiento real** | **No** | **Sí** |

El entrenamiento completo **nunca** corre en la máquina local: sin GPU tardaría
días y no alcanzaría el Recall comprometido. El notebook exige GPU en su primera
celda y se detiene si no la encuentra.

## Reproducir desde cero

1. **Local:** instalar y pasar las pruebas (`pytest -v`). Opcionalmente, verificar
   el script de preparación sobre una muestra:
   `C:\venv-copiloto\Scripts\python.exe scripts/preparar_datos.py --zip <zip> --raiz <dir> --limite 200`
2. **Colab o Kaggle:** abrir `notebooks/entrenar_gpu.ipynb` y ejecutar las celdas
   en orden. El notebook descarga el dataset desde Kaggle por sí mismo, prepara
   los datos, entrena con GPU y deja checkpoints y reporte en Drive.
3. Requisito previo para el paso 2: cuenta de Kaggle con las reglas de la
   competencia aceptadas, y los secretos `KAGGLE_USERNAME` y `KAGGLE_KEY`
   configurados en Colab.

## Pruebas

```
C:\venv-copiloto\Scripts\python.exe -m pytest -v
```

La prueba `tests/test_particion.py` es la más importante: verifica que ningún
paciente aparece en dos particiones. Si falla, las métricas no significan nada.

## Datos del dataset (verificados el 16-sep-2026)

26 684 imágenes de entrenamiento, una por paciente. 6 012 positivos (22,5%),
11 821 anormales sin opacidad (44,3%), 8 851 normales (33,2%). El desbalance se
maneja con partición estratificada, ponderación de clases y selección del umbral
sobre la curva ROC de validación.

## Documentos

- Diseño: `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`
- Plan: `docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md`
```

- [ ] **Paso 3: Verificar que la batería completa sigue en verde**

Ejecutar: `C:\venv-copiloto\Scripts\python.exe -m pytest -v`
Esperado: 43 passed

- [ ] **Paso 4: Commit**

```bash
git add notebooks/entrenar_gpu.ipynb README.md
git commit -m "docs: notebook de entrenamiento en GPU y README reproducible"
```

---

## Cobertura del spec

| Requisito del spec | Tarea |
| :--- | :--- |
| Configuración y semilla en un solo lugar (§5) | 1 |
| Partición por paciente estratificada (§6) | 2 |
| Verificación anti-fuga como prueba (§2, §9) | 2 |
| Reproducibilidad con la misma semilla (§2) | 2 |
| Regla de selección de umbral en tres pasos (§6) | 3 |
| Métricas: Recall, especificidad, F1, AUC, confusión (§2) | 3 |
| Conversión DICOM a PNG (§7) | 4 |
| Omisión registrada de DICOM corruptos (§8) | 4 |
| Aumento solo en entrenamiento, sin volteo (§6) | 5 |
| Lectura desde manifiesto, no del directorio (§7) | 5 |
| MobileNetV3-Large con salida binaria (§6) | 6 |
| Entrenamiento en dos fases (§6) | 6, 7 |
| Latencia de inferencia en CPU < 4 s (§2) | 6 |
| Early stopping por Recall (§6) | 7 |
| Ponderación de clases por desbalance (§6) | 7 |
| Checkpoints reanudables (§8) | 7 |
| Idempotencia de las etapas (§8) | 4, 8 |
| Manifiestos con semilla registrada (§7) | 8 |
| Pipeline de punta a punta desde una orden (§2) | 8 |
| Entrenamiento de humo en CPU (§9) | 9 |
| Notebook delgado para GPU (§10) | 10 |
| README reproducible (§12) | 10 |
