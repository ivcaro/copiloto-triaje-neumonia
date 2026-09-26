# SP2 — Servidor MCP: plan de implementación

> **Para agentes ejecutores:** SUB-SKILL OBLIGATORIA: usa
> `superpowers:subagent-driven-development` (recomendado) o
> `superpowers:executing-plans` para implementar este plan tarea a tarea. Los
> pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** servir la CNN entrenada en SP1 como herramienta MCP desde un
contenedor Docker, con endpoint REST de respaldo, consumible desde n8n **sin que
la radiografía salga del VPS en el paso de inferencia**: el contenedor no
publica puertos.

> **Corregido el 26-sep, a raíz de una evaluación externa.** Decía «sin que la
> radiografía salga de la red local», que no distingue los dos tramos. El
> anterior, Telegram → n8n, **sí** sale de la red del centro, porque el DICOM
> llega por Telegram. Riesgo declarado en el §5.5 del diseño de SP3. El
> comentario del compose del paso 3 habla del tramo de inferencia, que es el que
> ese fichero configura.
>
> **Ese comentario sí se corrigió después**, en `011134f`: decía «lo que
> garantiza que la radiografía no salga de la máquina», a secas, y ahora dice
> que no sale **en ese tramo**, remitiendo al §5.5. El bloque YAML transcrito en
> el paso 3 de este plan conserva la redacción vieja **a propósito**: un plan es
> el documento de lo que se planeó, y reescribirlo borraría que esto se
> planeó así. Lo que manda es el fichero.

**Arquitectura:** un solo proceso con tres capas. El núcleo de inferencia vive
en el paquete y no sabe de HTTP; encima, dos puertas delgadas —MCP y REST— que
llaman a la misma función. Un `docker-compose.yml` propio conectado como red
externa a la de n8n.

**Pila:** Python 3.12, PyTorch 2.14 CPU, pydicom 3.0.2, `mcp` 2.2.0
(`MCPServer`), FastAPI 0.141, uvicorn, scikit-learn (regresión isotónica).

**Spec:** `docs/superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md`

## Restricciones globales

Se aplican a TODAS las tareas:

- **Idioma:** nombres, docstrings, comentarios y mensajes en español, sin
  tildes en los identificadores. Los comentarios explican POR QUÉ, nunca QUÉ.
- **Intérprete:** `C:/venv-copiloto/Scripts/python.exe`. Nunca `python` a secas.
- **Pruebas:** `C:/venv-copiloto/Scripts/python.exe -m pytest -q`. Las 133
  existentes deben seguir pasando al terminar cada tarea.
- **TDD:** la prueba se escribe primero, se ejecuta para verla fallar, y solo
  entonces se implementa.
- **Sin emoji.**
- **Rango de edad válido:** 18 a 100 años, inclusive.
- **Prevalencia del dataset:** 0,2215 (5 627 positivos de 25 403).
- **Resolución de entrada:** 320×320. **Arquitectura:** `efficientnet_b0`.
- **MCP 2.x:** la clase es `MCPServer` (`from mcp.server.mcpserver import
  MCPServer`). En 1.x se llamaba `FastMCP`; ese nombre ya no existe.

## Hechos verificados durante el diseño

No los vuelvas a comprobar, y no los contradigas:

| Hecho | Valor |
| :--- | :--- |
| Tamaño de los DICOM de RSNA | mediana 131 KB, máximo 185 KB |
| Latencia de inferencia en CPU | 0,022 s por imagen |
| `streamable_http_app(host=...)` por defecto | `127.0.0.1`, y **rechaza con HTTP 421 "Invalid Host header"** cualquier petición cuya cabecera `Host` no sea esa. En Docker hay que pasar `0.0.0.0` |
| `max_request_body_size` por defecto | 4 MiB; el spec exige rechazar por encima de 5 MB, así que hay que pasarlo explícito |
| Montar MCP dentro de FastAPI | funciona **solo** si se cede el lifespan: `FastAPI(lifespan=mcp_app.router.lifespan_context)` |
| `httpx.ASGITransport` | NO dispara los eventos de lifespan; en las pruebas hay que entrar al contexto a mano |

---

### Tarea 1: Leer un DICOM desde bytes

`leer_dicom` recibe una ruta, pero el servidor recibe bytes por la red. Sin
esto habría que escribir un fichero temporal en cada petición.

**Ficheros:**
- Modificar: `src/copiloto_triaje/datos/dicom.py`
- Probar: `tests/test_dicom.py`

**Interfaces:**
- Consume: `_extraer_metadatos(ds) -> dict` (ya existe en ese módulo).
- Produce: `leer_dicom_desde_bytes(datos: bytes) -> tuple[np.ndarray, dict]`,
  misma forma de retorno que `leer_dicom`.

- [ ] **Paso 1: escribir la prueba que falla**

Añade al final de `tests/test_dicom.py`:

```python
def test_leer_dicom_desde_bytes_da_lo_mismo_que_desde_ruta(tmp_path):
    """El servidor recibe el DICOM por la red, no como fichero. Leer desde
    bytes tiene que dar exactamente lo mismo que leer desde disco: si
    divergieran, el modelo veria en produccion algo distinto de lo que se
    probo, y ninguna prueba de las existentes lo notaria."""
    ruta = tmp_path / "a.dcm"
    esperado = crear_dicom(ruta, edad="051Y", sexo="M", vista="AP")

    desde_ruta, meta_ruta = leer_dicom(ruta)
    desde_bytes, meta_bytes = leer_dicom_desde_bytes(ruta.read_bytes())

    assert np.array_equal(desde_ruta, desde_bytes)
    assert meta_ruta == meta_bytes
    assert meta_bytes["edad"] == "051Y"
    assert desde_bytes.shape == esperado.shape


def test_leer_dicom_desde_bytes_rechaza_lo_que_no_es_dicom():
    """Un PNG, un JSON o basura tienen que fallar con el error de pydicom, no
    con un AttributeError tres capas mas arriba."""
    with pytest.raises(pydicom.errors.InvalidDicomError):
        leer_dicom_desde_bytes(b"esto no es un DICOM")
```

Y amplía el import de ese fichero:

```python
from copiloto_triaje.datos.dicom import (
    convertir_a_png, convertir_lote, leer_dicom, leer_dicom_desde_bytes,
)
```

- [ ] **Paso 2: ejecutar y verla fallar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_dicom.py -q -k desde_bytes`
Esperado: FALLA con `ImportError: cannot import name 'leer_dicom_desde_bytes'`

- [ ] **Paso 3: implementar**

En `src/copiloto_triaje/datos/dicom.py`, después de `leer_dicom`:

```python
def leer_dicom_desde_bytes(datos: bytes) -> tuple[np.ndarray, dict]:
    """Igual que `leer_dicom` pero desde memoria.

    El servidor de SP2 recibe el DICOM por la red. Escribirlo a un fichero
    temporal solo para volver a leerlo seria un viaje al disco por peticion,
    y dejaria restos que limpiar si el proceso muere a mitad.
    """
    ds = pydicom.dcmread(io.BytesIO(datos))
    return ds.pixel_array, _extraer_metadatos(ds)
```

Añade `import io` al bloque de imports del módulo, antes de `import os`.

- [ ] **Paso 4: ejecutar y verla pasar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_dicom.py -q`
Esperado: PASA, y las pruebas anteriores del fichero siguen pasando.

- [ ] **Paso 5: commit**

```bash
git add src/copiloto_triaje/datos/dicom.py tests/test_dicom.py
git commit -m "Leer un DICOM desde bytes, no solo desde una ruta"
```

---

### Tarea 2: El calibrador

La salida del modelo no es una probabilidad: se entrenó con `pos_weight=3,44`.
Esta tarea produce el objeto que la convierte en algo que SP4 pueda meter en
una fórmula bayesiana.

**Ficheros:**
- Crear: `src/copiloto_triaje/servicio/__init__.py` (vacío)
- Crear: `src/copiloto_triaje/servicio/calibracion.py`
- Crear: `tests/test_calibracion.py`

**Interfaces:**
- Produce:
  - `Calibrador.desde_json(ruta) -> Calibrador`
  - `Calibrador.calibrar(probabilidad_cruda: float) -> float`
  - `Calibrador.razon_de_verosimilitud(probabilidad_cruda: float) -> float`
  - `Calibrador.a_json(ruta) -> None`
  - `ajustar_calibrador(y_true, y_score, prevalencia, procedencia) -> Calibrador`

- [ ] **Paso 1: escribir las pruebas que fallan**

Crea `tests/test_calibracion.py`:

```python
"""Pruebas del calibrador.

Lo que se protege aqui es que la evidencia de imagen que SP4 va a meter en la
formula bayesiana signifique lo que dice significar. La salida cruda del
modelo NO es una probabilidad -se entreno con pos_weight=3,44- y combinar ese
numero con la probabilidad previa de la regla clinica da un posterior
equivocado sin que nada falle de forma visible.
"""
import json

import numpy as np
import pytest

from copiloto_triaje.servicio.calibracion import Calibrador, ajustar_calibrador

PREVALENCIA = 0.2215


def _puntuaciones(n=2000, semilla=3):
    """Puntuaciones separables con la prevalencia real del dataset."""
    rng = np.random.default_rng(semilla)
    y = (rng.random(n) < PREVALENCIA).astype(int)
    crudo = rng.normal(1.7 * y, 1.0)
    return y, 1 / (1 + np.exp(-crudo))


def test_calibrar_acerca_la_media_a_la_prevalencia():
    """Una probabilidad calibrada promedia, sobre la poblacion, la prevalencia
    real. La cruda no: el pos_weight la empuja hacia arriba."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    calibradas = np.array([cal.calibrar(p) for p in crudo])

    assert abs(calibradas.mean() - PREVALENCIA) < 0.02, (
        f"media calibrada {calibradas.mean():.4f}, prevalencia {PREVALENCIA}")


def test_la_razon_de_verosimilitud_es_coherente_con_la_probabilidad():
    """RV = odds_posterior / odds_previo. Si esta relacion se rompe, SP4
    calcula mal el posterior y nadie lo nota."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    odds_previo = PREVALENCIA / (1 - PREVALENCIA)

    for p in (0.1, 0.35, 0.6, 0.9):
        calibrada = cal.calibrar(p)
        esperada = (calibrada / (1 - calibrada)) / odds_previo
        assert cal.razon_de_verosimilitud(p) == pytest.approx(esperada, rel=1e-6)


def test_la_razon_de_verosimilitud_crece_con_la_puntuacion():
    """Mas evidencia de imagen no puede dar menos razon de verosimilitud."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    valores = [cal.razon_de_verosimilitud(p) for p in (0.05, 0.25, 0.5, 0.75, 0.95)]
    assert valores == sorted(valores)


def test_el_calibrador_va_y_vuelve_por_json(tmp_path):
    """Viaja en el repositorio como JSON -unos kilobytes que si se versionan-
    y no como un objeto de scikit-learn serializado, que ataria el despliegue
    a la version exacta de la libreria."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "corrida_x")
    ruta = tmp_path / "calibrador.json"
    cal.a_json(ruta)

    recuperado = Calibrador.desde_json(ruta)
    for p in (0.1, 0.5, 0.9):
        assert recuperado.calibrar(p) == pytest.approx(cal.calibrar(p))
    assert json.loads(ruta.read_text(encoding="utf-8"))["procedencia"] == "corrida_x"


def test_el_calibrador_registra_de_donde_sale(tmp_path):
    """Un calibrador sin procedencia es un numero magico: nadie puede saber si
    corresponde a los pesos que esta sirviendo el contenedor."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "efficientnet_b0_320px")
    assert cal.procedencia == "efficientnet_b0_320px"
    assert cal.prevalencia == PREVALENCIA
```

- [ ] **Paso 2: ejecutar y verlas fallar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_calibracion.py -q`
Esperado: FALLA con `ModuleNotFoundError: No module named 'copiloto_triaje.servicio'`

- [ ] **Paso 3: implementar**

Crea `src/copiloto_triaje/servicio/__init__.py` vacío y
`src/copiloto_triaje/servicio/calibracion.py`:

```python
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
        """Probabilidad calibrada a la prevalencia del conjunto de ajuste."""
        return float(np.interp(float(probabilidad_cruda), self.x, self.y))

    def razon_de_verosimilitud(self, probabilidad_cruda: float) -> float:
        """Lo que SP4 debe multiplicar por las odds de la regla clinica.

        RV = odds_posterior / odds_previo. Los extremos se recortan porque una
        probabilidad de 0 o 1 daria una razon infinita, y ninguna radiografia
        justifica certeza absoluta.
        """
        p = min(max(self.calibrar(probabilidad_cruda), 1e-6), 1 - 1e-6)
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
```

- [ ] **Paso 4: ejecutar y verlas pasar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_calibracion.py -q`
Esperado: 5 pruebas PASAN.

- [ ] **Paso 5: commit**

```bash
git add src/copiloto_triaje/servicio/ tests/test_calibracion.py
git commit -m "Calibrador: de puntuacion cruda a razon de verosimilitud"
```

---

### Tarea 3: El script que ajusta el calibrador sobre validación

**Ficheros:**
- Crear: `scripts/ajustar_calibrador.py`
- Crear: `tests/test_ajustar_calibrador.py`

**Interfaces:**
- Consume: `Calibrador`, `ajustar_calibrador` (Tarea 2); `construir_modelo`,
  `DatasetRadiografias`, `construir_transformaciones` del paquete.
- Produce: `calibrador.json` en la carpeta de la corrida, y la función
  `main(argv=None) -> int`.

- [ ] **Paso 1: escribir la prueba que falla**

Crea `tests/test_ajustar_calibrador.py`:

```python
"""El script debe fallar al inicio si le falta algo, no a mitad de evaluar
3 810 imagenes."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ajustar_calibrador.py"


def _cargar():
    especificacion = importlib.util.spec_from_file_location("ajustar_calibrador", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


ajustar = _cargar()


def test_falla_si_no_estan_los_pesos(tmp_path, capsys):
    """Citando la ruta que busco, no un mensaje generico."""
    codigo = ajustar.main(["--corrida", str(tmp_path / "no_existe"),
                           "--raiz", str(tmp_path)])
    assert codigo == 2
    assert "no_existe" in capsys.readouterr().err


def test_falla_si_no_esta_el_manifiesto_de_validacion(tmp_path, capsys):
    """El calibrador se ajusta SOLO sobre validacion; sin ese manifiesto no
    hay nada que hacer, y usar otro conjunto seria un error silencioso."""
    corrida = tmp_path / "corrida"
    (corrida / "checkpoints").mkdir(parents=True)
    (corrida / "checkpoints" / "pesos_modelo_cpu.pt").write_bytes(b"x")
    codigo = ajustar.main(["--corrida", str(corrida), "--raiz", str(tmp_path)])
    assert codigo == 2
    assert "val.csv" in capsys.readouterr().err
```

- [ ] **Paso 2: ejecutar y verla fallar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_ajustar_calibrador.py -q`
Esperado: FALLA con `FileNotFoundError` al cargar el script (aún no existe).

- [ ] **Paso 3: implementar**

Crea `scripts/ajustar_calibrador.py`:

```python
# -*- coding: utf-8 -*-
"""Ajusta el calibrador sobre el conjunto de VALIDACION de una corrida.

Se ejecuta UNA vez por corrida, y su salida -calibrador.json- viaja con el
modelo al contenedor. Sin el, el servidor devolveria la salida cruda del
modelo como si fuera una probabilidad.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

RAIZ_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_REPO / "src"))

from copiloto_triaje.datos.dataset import DatasetRadiografias  # noqa: E402
from copiloto_triaje.modelo.arquitectura import construir_modelo  # noqa: E402
from copiloto_triaje.servicio.calibracion import ajustar_calibrador  # noqa: E402

PREVALENCIA = 0.2215
NOMBRE_PESOS = "pesos_modelo_cpu.pt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Ajusta el calibrador sobre validacion")
    parser.add_argument("--corrida", required=True, type=Path,
                        help="carpeta de la corrida, con checkpoints/ dentro")
    parser.add_argument("--raiz", required=True, type=Path,
                        help="raiz de datos, con png/ y manifiestos/")
    parser.add_argument("--arquitectura", default="efficientnet_b0")
    parser.add_argument("--tam-imagen", type=int, default=320)
    args = parser.parse_args(argv)

    pesos = args.corrida / "checkpoints" / NOMBRE_PESOS
    if not pesos.is_file():
        print(f"ERROR: no estan los pesos en {pesos}", file=sys.stderr)
        return 2
    manifiesto = args.raiz / "manifiestos" / "val.csv"
    if not manifiesto.is_file():
        print(f"ERROR: no esta el manifiesto de validacion {manifiesto}",
              file=sys.stderr)
        return 2

    modelo = construir_modelo(args.arquitectura, congelar_backbone=False,
                              preentrenado=False)
    modelo.load_state_dict(torch.load(pesos, map_location="cpu",
                                      weights_only=True))
    modelo.eval()

    df = pd.read_csv(manifiesto)
    conjunto = DatasetRadiografias(df, args.raiz / "png", args.tam_imagen,
                                   entrenamiento=False)
    cargador = DataLoader(conjunto, batch_size=32, num_workers=0)

    print(f"evaluando {len(df)} imagenes de validacion ...", flush=True)
    y, s = [], []
    with torch.no_grad():
        for x, etiquetas in cargador:
            s.extend(torch.sigmoid(modelo(x).view(-1)).tolist())
            y.extend(etiquetas.tolist())

    calibrador = ajustar_calibrador(y, s, PREVALENCIA, args.corrida.name)
    ruta = calibrador.a_json(args.corrida / "calibrador.json")
    print(f"calibrador ajustado sobre {len(y)} imagenes -> {ruta}")
    print(f"  procedencia: {calibrador.procedencia} | "
          f"prevalencia: {calibrador.prevalencia}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Paso 4: ejecutar y verla pasar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_ajustar_calibrador.py -q`
Esperado: 2 pruebas PASAN.

- [ ] **Paso 5: ajustarlo de verdad sobre la corrida real**

Ejecuta:

```bash
C:/venv-copiloto/Scripts/python.exe scripts/ajustar_calibrador.py \
  --corrida "C:/Users/[retirado]/datasets/rsna-pneumonia/trabajo/corridas/efficientnet_b0_320px_lote24_4+20ep" \
  --raiz "C:/Users/[retirado]/datasets/rsna-pneumonia/trabajo"
```

Esperado: tarda unos 5 minutos y termina con
`calibrador ajustado sobre 3810 imagenes`.
Copia el `calibrador.json` resultante a `servidor/calibrador.json`, que es el
que se versiona y viaja al contenedor.

- [ ] **Paso 6: commit**

```bash
git add scripts/ajustar_calibrador.py tests/test_ajustar_calibrador.py servidor/calibrador.json
git commit -m "Ajustar el calibrador sobre validacion, nunca sobre prueba"
```

---

### Tarea 4: El núcleo de inferencia

La única pieza con lógica clínica. No sabe de HTTP, MCP ni Docker.

**Ficheros:**
- Crear: `src/copiloto_triaje/servicio/inferencia.py`
- Crear: `tests/test_inferencia.py`

**Interfaces:**
- Consume: `leer_dicom_desde_bytes` (Tarea 1), `Calibrador` (Tarea 2),
  `edad_en_anios` de `datos.preparacion`, `construir_transformaciones` de
  `datos.dataset`, `construir_modelo` de `modelo.arquitectura`.
- Produce:
  - `ErrorDeInferencia(Exception)` con atributo `codigo: str`
  - `Motor.cargar(ruta_pesos, ruta_calibrador, umbral, arquitectura, tam_imagen) -> Motor`
  - `Motor.clasificar(datos_dicom: bytes) -> dict`

- [ ] **Paso 1: escribir las pruebas que fallan**

Crea `tests/test_inferencia.py`:

```python
"""Pruebas del nucleo de inferencia.

Se prueba aqui, en el paquete y no contra el servidor, para que corran sin
levantar Docker y en menos de un segundo.
"""
import numpy as np
import pytest
import torch

from copiloto_triaje.servicio.calibracion import ajustar_calibrador
from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

from test_dicom import crear_dicom  # reutiliza el generador de DICOM sinteticos


@pytest.fixture
def motor(tmp_path):
    """Un motor con un modelo lineal diminuto: aqui se prueba la logica del
    nucleo, no la calidad de la red, y cargar EfficientNet real haria que cada
    prueba descargara pesos de ImageNet."""
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.2215).astype(int)
    crudo = 1 / (1 + np.exp(-rng.normal(1.7 * y, 1.0)))
    calibrador = ajustar_calibrador(y, crudo, 0.2215, "prueba")

    class Trivial(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)

    return Motor(modelo=Trivial(), calibrador=calibrador, umbral=0.5,
                 tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.88)


def test_clasificar_devuelve_el_contrato_completo(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())

    esperadas = {"probabilidad_cruda", "probabilidad_calibrada",
                 "razon_de_verosimilitud", "umbral", "clasificacion",
                 "edad_paciente", "modelo", "auc_validacion", "milisegundos"}
    assert esperadas <= set(salida)
    assert 0.0 <= salida["probabilidad_cruda"] <= 1.0
    assert salida["edad_paciente"] == 54
    assert salida["razon_de_verosimilitud"] > 0


def test_una_placa_de_menor_se_rechaza(motor, tmp_path):
    """El modelo se entreno solo con adultos. Emitir una probabilidad sobre un
    nino seria dar por valido un numero que no lo es."""
    ruta = tmp_path / "nino.dcm"
    crear_dicom(ruta, edad="012Y")
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(ruta.read_bytes())
    assert fallo.value.codigo == "fuera_de_alcance"
    assert "12" in str(fallo.value)


def test_una_edad_ilegible_no_se_da_por_adulta(motor, tmp_path):
    """Suponer que quien no declara edad es adulto es exactamente el atajo que
    el filtro existe para evitar."""
    ruta = tmp_path / "sin_edad.dcm"
    crear_dicom(ruta, edad="")
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(ruta.read_bytes())
    assert fallo.value.codigo == "edad_desconocida"


def test_lo_que_no_es_un_dicom_se_rechaza_con_su_codigo(motor):
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(b"esto no es un DICOM")
    assert fallo.value.codigo == "dicom_invalido"


def test_la_clasificacion_respeta_el_umbral(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())
    esperada = ("opacidad_probable"
                if salida["probabilidad_cruda"] >= salida["umbral"]
                else "sin_opacidad_probable")
    assert salida["clasificacion"] == esperada


def test_el_preprocesamiento_es_el_mismo_que_el_de_entrenamiento(motor, tmp_path):
    """Si el servidor preprocesa distinto que el entrenamiento, el modelo se
    degrada en produccion y ninguna metrica lo avisa. El motor tiene que usar
    construir_transformaciones del paquete, no una copia propia."""
    from PIL import Image
    from copiloto_triaje.datos.dataset import construir_transformaciones

    from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes

    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()

    arreglo, _ = leer_dicom_desde_bytes(datos)
    esperado = construir_transformaciones(32, entrenamiento=False)(
        Image.fromarray(arreglo).convert("RGB")).unsqueeze(0)

    assert torch.allclose(motor._preparar_tensor(datos), esperado)
```

- [ ] **Paso 2: ejecutar y verlas fallar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_inferencia.py -q`
Esperado: FALLA con `ModuleNotFoundError: No module named 'copiloto_triaje.servicio.inferencia'`

- [ ] **Paso 3: implementar**

Crea `src/copiloto_triaje/servicio/inferencia.py`:

```python
"""El nucleo: bytes de un DICOM a evidencia de imagen.

No sabe de HTTP, de MCP ni de Docker. Las dos puertas del servidor son
envoltorios sobre `Motor.clasificar`, y esa simetria es lo unico que impide
que el respaldo REST y el camino MCP digan cosas distintas sobre la misma
radiografia.
"""
from __future__ import annotations

import time
from pathlib import Path

import pydicom.errors
import torch
from PIL import Image

from copiloto_triaje.datos.dataset import construir_transformaciones
from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes
from copiloto_triaje.datos.preparacion import edad_en_anios
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.servicio.calibracion import Calibrador

EDAD_MINIMA = 18
EDAD_MAXIMA = 100


class ErrorDeInferencia(Exception):
    """Un fallo que el profesional puede entender y accionar.

    Lleva `codigo` para que las dos puertas lo traduzcan al formato que
    corresponda sin tener que interpretar el texto del mensaje.
    """

    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo = codigo


class Motor:
    """Modelo cargado y listo para clasificar. Se construye una vez al arrancar."""

    def __init__(self, modelo, calibrador: Calibrador, umbral: float,
                 tam_imagen: int, nombre_modelo: str, auc_validacion: float):
        self.modelo = modelo
        self.modelo.eval()
        self.calibrador = calibrador
        self.umbral = float(umbral)
        self.tam_imagen = int(tam_imagen)
        self.nombre_modelo = nombre_modelo
        self.auc_validacion = float(auc_validacion)
        # Una sola instancia: construir_transformaciones en cada peticion
        # recrearia los mismos objetos por nada.
        self._transformar = construir_transformaciones(tam_imagen,
                                                       entrenamiento=False)

    @classmethod
    def cargar(cls, ruta_pesos, ruta_calibrador, umbral: float,
               arquitectura: str = "efficientnet_b0", tam_imagen: int = 320,
               auc_validacion: float = 0.883) -> "Motor":
        """Carga como lo hara el contenedor: en CPU y con weights_only."""
        ruta_pesos, ruta_calibrador = Path(ruta_pesos), Path(ruta_calibrador)
        if not ruta_pesos.is_file():
            raise FileNotFoundError(f"No estan los pesos en {ruta_pesos}")
        if not ruta_calibrador.is_file():
            raise FileNotFoundError(f"No esta el calibrador en {ruta_calibrador}")
        modelo = construir_modelo(arquitectura, congelar_backbone=False,
                                  preentrenado=False)
        modelo.load_state_dict(torch.load(ruta_pesos, map_location="cpu",
                                          weights_only=True))
        return cls(modelo, Calibrador.desde_json(ruta_calibrador), umbral,
                   tam_imagen, f"{arquitectura}_{tam_imagen}px", auc_validacion)

    def _tensor_desde_arreglo(self, arreglo) -> torch.Tensor:
        """La conversion, en UN solo sitio.

        `clasificar` y `_preparar_tensor` la comparten a proposito: si cada uno
        tuviera su copia, la prueba que verifica la igualdad con el
        preprocesamiento de entrenamiento comprobaria un camino mientras
        produccion usa el otro, que es justo el fallo que esa prueba existe
        para impedir.
        """
        return self._transformar(
            Image.fromarray(arreglo).convert("RGB")).unsqueeze(0)

    def _preparar_tensor(self, datos_dicom: bytes) -> torch.Tensor:
        """Mismo camino que el entrenamiento: se usa
        `construir_transformaciones` del paquete en vez de reimplementarla,
        porque una copia se desincroniza en silencio y degrada el modelo en
        produccion sin que ninguna metrica lo avise."""
        arreglo, _ = leer_dicom_desde_bytes(datos_dicom)
        return self._tensor_desde_arreglo(arreglo)

    def clasificar(self, datos_dicom: bytes) -> dict:
        comienzo = time.perf_counter()
        try:
            arreglo, meta = leer_dicom_desde_bytes(datos_dicom)
        except (pydicom.errors.InvalidDicomError, AttributeError,
                ValueError, TypeError) as exc:
            raise ErrorDeInferencia(
                "dicom_invalido",
                f"El fichero no es un DICOM legible: {exc}") from exc

        edad = edad_en_anios(meta.get("edad"))
        if edad is None:
            raise ErrorDeInferencia(
                "edad_desconocida",
                "La cabecera DICOM no declara una edad interpretable. No se "
                "asume que el paciente sea adulto: pide la edad al profesional.")
        if not EDAD_MINIMA <= edad <= EDAD_MAXIMA:
            raise ErrorDeInferencia(
                "fuera_de_alcance",
                f"El paciente tiene {edad} anios y el modelo solo es valido "
                f"entre {EDAD_MINIMA} y {EDAD_MAXIMA}.")

        # El arreglo ya esta leido: se reusa en vez de volver a decodificar el
        # DICOM, y la conversion es la MISMA que usa _preparar_tensor.
        tensor = self._tensor_desde_arreglo(arreglo)
        with torch.no_grad():
            cruda = float(torch.sigmoid(self.modelo(tensor).view(-1))[0])

        return {
            "probabilidad_cruda": round(cruda, 4),
            "probabilidad_calibrada": round(self.calibrador.calibrar(cruda), 4),
            "razon_de_verosimilitud": round(
                self.calibrador.razon_de_verosimilitud(cruda), 4),
            "umbral": round(self.umbral, 4),
            "clasificacion": ("opacidad_probable" if cruda >= self.umbral
                              else "sin_opacidad_probable"),
            "edad_paciente": edad,
            "modelo": self.nombre_modelo,
            "auc_validacion": self.auc_validacion,
            "milisegundos": round((time.perf_counter() - comienzo) * 1000, 1),
        }
```

- [ ] **Paso 4: ejecutar y verlas pasar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_inferencia.py -q`
Esperado: 6 pruebas PASAN.

Si `from test_dicom import crear_dicom` falla, añade a `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["tests"]
```

- [ ] **Paso 5: la suite completa**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest -q`
Esperado: las 133 anteriores más las nuevas, todas en verde.

- [ ] **Paso 6: commit**

```bash
git add src/copiloto_triaje/servicio/inferencia.py tests/test_inferencia.py pyproject.toml
git commit -m "Nucleo de inferencia: de bytes de DICOM a evidencia de imagen"
```

---

### Tarea 5: Las dos puertas y la aplicación

**Ficheros:**
- Crear: `src/copiloto_triaje/servicio/aplicacion.py`
- Crear: `tests/test_aplicacion.py`

**Interfaces:**
- Consume: `Motor`, `ErrorDeInferencia` (Tarea 4).
- Produce: `construir_aplicacion(motor, host_permitido="0.0.0.0") -> FastAPI`,
  con `POST /inferir` (multipart, campo `archivo`), `GET /salud` y el
  transporte MCP en `/mcp` con la herramienta `clasificar_radiografia`.

- [ ] **Paso 1: escribir las pruebas que fallan**

Crea `tests/test_aplicacion.py`:

```python
"""Pruebas de las dos puertas.

La tercera es la que de verdad protege: si MCP y REST divergen, el respaldo
comprometido en el cronograma deja de ser un respaldo y nadie se entera hasta
que hace falta.
"""
import base64
import json

import httpx
import numpy as np
import pytest
import pytest_asyncio
import torch

from copiloto_triaje.servicio.aplicacion import construir_aplicacion
from copiloto_triaje.servicio.calibracion import ajustar_calibrador
from copiloto_triaje.servicio.inferencia import Motor

from test_dicom import crear_dicom


@pytest.fixture
def motor():
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.2215).astype(int)
    crudo = 1 / (1 + np.exp(-rng.normal(1.7 * y, 1.0)))

    class Trivial(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)

    return Motor(modelo=Trivial(),
                 calibrador=ajustar_calibrador(y, crudo, 0.2215, "prueba"),
                 umbral=0.5, tam_imagen=32, nombre_modelo="prueba",
                 auc_validacion=0.88)


@pytest_asyncio.fixture
async def cliente(motor):
    """httpx.ASGITransport NO dispara los eventos de lifespan, y el gestor de
    sesiones de MCP vive ahi. Se entra al contexto a mano; en produccion lo
    hace uvicorn."""
    app = construir_aplicacion(motor)
    transporte = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), \
            httpx.AsyncClient(transport=transporte,
                              base_url="http://prueba") as c:
        yield c


@pytest.mark.asyncio
async def test_salud_responde_listo(cliente):
    r = await cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "listo"


@pytest.mark.asyncio
async def test_rest_clasifica_un_dicom(cliente, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    r = await cliente.post("/inferir",
                           files={"archivo": ("a.dcm", ruta.read_bytes())})
    assert r.status_code == 200
    assert r.json()["edad_paciente"] == 54


@pytest.mark.asyncio
async def test_rest_devuelve_el_codigo_de_error_en_el_cuerpo(cliente, tmp_path):
    ruta = tmp_path / "nino.dcm"
    crear_dicom(ruta, edad="012Y")
    r = await cliente.post("/inferir",
                           files={"archivo": ("n.dcm", ruta.read_bytes())})
    assert r.status_code == 422
    assert r.json()["codigo"] == "fuera_de_alcance"


@pytest.mark.asyncio
async def test_las_dos_puertas_dan_lo_mismo(cliente, tmp_path):
    """El criterio de aceptacion anadido en el spec. Sin esta prueba el
    respaldo puede divergir del camino principal."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()

    por_rest = (await cliente.post(
        "/inferir", files={"archivo": ("a.dcm", datos)})).json()

    cuerpo = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "clasificar_radiografia",
                         "arguments": {"dicom_base64":
                                       base64.b64encode(datos).decode()}}}
    r = await cliente.post("/mcp", json=cuerpo, headers={
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"})
    assert r.status_code == 200
    por_mcp = _extraer_resultado(r.text)

    # Los milisegundos difieren por construccion: se comparan los demas.
    sin_tiempo = lambda d: {k: v for k, v in d.items() if k != "milisegundos"}
    assert sin_tiempo(por_mcp) == sin_tiempo(por_rest)


def _extraer_resultado(texto: str) -> dict:
    """La respuesta puede venir como SSE; se queda con el JSON del evento."""
    for linea in texto.splitlines():
        if linea.startswith("data: "):
            texto = linea[6:]
            break
    respuesta = json.loads(texto)
    contenido = respuesta["result"]
    if "structuredContent" in contenido:
        return contenido["structuredContent"]
    return json.loads(contenido["content"][0]["text"])


@pytest.mark.asyncio
async def test_mcp_acepta_una_cabecera_host_de_otro_contenedor(cliente, tmp_path):
    """Con el host por defecto (127.0.0.1) el transporte responde 421 Invalid
    Host header a cualquier peticion que no venga de localhost, y en Docker
    n8n llama por nombre de servicio. Verificado durante el diseño."""
    r = await cliente.post("/mcp",
                           json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                           headers={"Host": "copiloto-mcp:8000",
                                    "Accept": "application/json, text/event-stream",
                                    "Content-Type": "application/json"})
    assert r.status_code == 200
    assert "clasificar_radiografia" in r.text
```

- [ ] **Paso 2: instalar las dependencias y ver fallar la prueba**

```bash
C:/venv-copiloto/Scripts/python.exe -m pip install "mcp==2.2.0" "fastapi==0.141.1" "uvicorn[standard]>=0.34" httpx pytest-asyncio python-multipart
```

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_aplicacion.py -q`
Esperado: FALLA con `ModuleNotFoundError: ... servicio.aplicacion`

- [ ] **Paso 3: implementar**

Crea `src/copiloto_triaje/servicio/aplicacion.py`:

```python
"""Las dos puertas del servicio, sobre el mismo nucleo.

MCP es lo comprometido en el hito H4; REST es la contingencia que el propio
cronograma previo por si n8n y MCP no se entendian. Las dos llaman a
`Motor.clasificar`, asi que no pueden divergir.
"""
from __future__ import annotations

import base64

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from mcp.server.mcpserver import MCPServer

from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

MAXIMO_BYTES = 5 * 1024 * 1024


def construir_aplicacion(motor: Motor, host_permitido: str = "0.0.0.0") -> FastAPI:
    """Monta MCP y REST en un solo proceso.

    `host_permitido` va a "0.0.0.0" y NO al 127.0.0.1 por defecto del SDK:
    el transporte valida la cabecera Host y con el valor por defecto responde
    421 "Invalid Host header" a todo lo que no venga de localhost. En Docker,
    n8n llama por nombre de servicio, asi que con el valor por defecto el
    despliegue falla entero. Comprobado durante el diseño.
    """
    servidor = MCPServer(name="copiloto-triaje", version="0.1.0",
                         instructions="Clasifica opacidad pulmonar en "
                                      "radiografia de torax de adultos.")

    @servidor.tool(
        name="clasificar_radiografia",
        description="Recibe una radiografia de torax en DICOM (base64) y "
                    "devuelve la evidencia de imagen: probabilidad calibrada "
                    "y razon de verosimilitud para combinar con la regla "
                    "clinica. Solo valida para pacientes de 18 a 100 anios.")
    def clasificar_radiografia(dicom_base64: str) -> dict:
        try:
            datos = base64.b64decode(dicom_base64, validate=True)
        except Exception as exc:
            raise ValueError(f"base64 invalido: {exc}") from exc
        if len(datos) > MAXIMO_BYTES:
            raise ValueError(
                f"payload_excesivo: {len(datos)} bytes, maximo {MAXIMO_BYTES}")
        try:
            return motor.clasificar(datos)
        except ErrorDeInferencia as exc:
            # El codigo viaja en el texto: MCP transporta el error como
            # mensaje, y quien llama necesita distinguir "fuera de alcance"
            # de "no es un DICOM" sin interpretar prosa.
            raise ValueError(f"{exc.codigo}: {exc}") from exc

    mcp_app = servidor.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        max_request_body_size=MAXIMO_BYTES,
        host=host_permitido,
    )

    # El lifespan del app de MCP se cede al de FastAPI: montarlo sin esto deja
    # el gestor de sesiones sin arrancar y la herramienta falla con un
    # RuntimeError de grupo de tareas. Comprobado durante el diseño.
    api = FastAPI(title="copiloto-triaje", version="0.1.0",
                  lifespan=mcp_app.router.lifespan_context)

    @api.get("/salud")
    def salud() -> dict:
        return {"estado": "listo", "modelo": motor.nombre_modelo,
                "umbral": motor.umbral,
                "calibrador": motor.calibrador.procedencia}

    @api.post("/inferir")
    async def inferir(archivo: UploadFile = File(...)):
        datos = await archivo.read()
        if len(datos) > MAXIMO_BYTES:
            return JSONResponse(status_code=413, content={
                "codigo": "payload_excesivo",
                "detalle": f"{len(datos)} bytes, maximo {MAXIMO_BYTES}"})
        try:
            return motor.clasificar(datos)
        except ErrorDeInferencia as exc:
            # 422 y no 400: la peticion esta bien formada, lo que no sirve es
            # su contenido para este modelo.
            return JSONResponse(status_code=422, content={
                "codigo": exc.codigo, "detalle": str(exc)})

    api.mount("/", mcp_app)
    return api
```

- [ ] **Paso 4: ejecutar y verlas pasar**

Ejecuta: `C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_aplicacion.py -q`
Esperado: 5 pruebas PASAN.

Si pytest-asyncio se queja del modo, añade a `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Paso 5: comprobar que la prueba de equivalencia sirve de algo**

Rompe a propósito la puerta REST para que redondee distinto —por ejemplo,
cambia `return motor.clasificar(datos)` del endpoint por
`r = motor.clasificar(datos); r["umbral"] = 0.99; return r`— y ejecuta:

`C:/venv-copiloto/Scripts/python.exe -m pytest tests/test_aplicacion.py -q -k dan_lo_mismo`

Esperado: **FALLA**. Si pasa, la prueba es decorativa y hay que arreglarla.
Deshaz el cambio después.

- [ ] **Paso 6: commit**

```bash
git add src/copiloto_triaje/servicio/aplicacion.py tests/test_aplicacion.py pyproject.toml
git commit -m "Las dos puertas del servicio sobre el mismo nucleo"
```

---

### Tarea 6: El contenedor y su compose

**Ficheros:**
- Crear: `servidor/Dockerfile`
- Crear: `servidor/docker-compose.yml`
- Crear: `servidor/arrancar.py`
- Crear: `servidor/.dockerignore`
- Crear: `docs/sp2-despliegue.md`

**Interfaces:**
- Consume: `construir_aplicacion`, `Motor.cargar` (Tareas 4 y 5).
- Produce: la imagen `copiloto-mcp` y el servicio del mismo nombre en la red
  externa de n8n.

- [ ] **Paso 1: el punto de entrada**

Crea `servidor/arrancar.py`:

```python
# -*- coding: utf-8 -*-
"""Punto de entrada del contenedor: carga el modelo UNA vez y sirve.

Cargar el modelo al importar y no en cada peticion es lo que convierte los
22 ms medidos en la latencia real del servicio.
"""
import os

import uvicorn

from copiloto_triaje.servicio.aplicacion import construir_aplicacion
from copiloto_triaje.servicio.inferencia import Motor

RUTA_PESOS = os.environ.get("RUTA_PESOS", "/modelo/pesos_modelo_cpu.pt")
RUTA_CALIBRADOR = os.environ.get("RUTA_CALIBRADOR", "/modelo/calibrador.json")
UMBRAL = float(os.environ.get("UMBRAL", "0.4258"))

motor = Motor.cargar(RUTA_PESOS, RUTA_CALIBRADOR, UMBRAL)
app = construir_aplicacion(motor)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
```

- [ ] **Paso 2: el Dockerfile**

Crea `servidor/Dockerfile`:

```dockerfile
FROM python:3.12-slim

# torch por el indice de ruedas CPU: `pip install torch` a secas descarga la
# compilacion con CUDA, 2,5 GB para un servidor que no tiene GPU.
ENV PIP_INDEX_URL=https://download.pytorch.org/whl/cpu \
    PIP_EXTRA_INDEX_URL=https://pypi.org/simple \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir . \
 && pip install --no-cache-dir "mcp==2.2.0" "fastapi==0.141.1" \
      "uvicorn[standard]>=0.34" python-multipart

# Los pesos y el calibrador van DENTRO de la imagen: son 16 MB y asi el
# contenedor es autocontenido, que es lo que hace reproducible la prueba
# cruzada de despliegue que exige el hito H4.
COPY servidor/pesos_modelo_cpu.pt /modelo/pesos_modelo_cpu.pt
COPY servidor/calibrador.json /modelo/calibrador.json
COPY servidor/arrancar.py ./arrancar.py

EXPOSE 8000
CMD ["python", "arrancar.py"]
```

Crea `servidor/.dockerignore`:

```
**/__pycache__
**/*.pyc
.pytest_cache
.git
docs
tests
notebooks
scripts
```

- [ ] **Paso 3: el compose**

Crea `servidor/docker-compose.yml`:

```yaml
services:
  copiloto-mcp:
    build:
      context: ..
      dockerfile: servidor/Dockerfile
    image: copiloto-mcp:0.1.0
    container_name: copiloto-mcp
    restart: unless-stopped
    # Sin `ports`: el servicio NO se expone a internet. n8n lo alcanza por
    # nombre de servicio dentro de la red interna, que es lo que garantiza
    # que la radiografia no salga de la maquina.
    environment:
      UMBRAL: "0.4258"
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/salud').status==200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          memory: 2G
    networks:
      - n8n

networks:
  n8n:
    external: true
    # El nombre real de la red de n8n. Averigualo con `docker network ls` y
    # ajustalo: si no coincide, el compose falla al arrancar en vez de dejar
    # los contenedores sin verse, que seria peor.
    name: n8n_default
```

- [ ] **Paso 4: copiar los artefactos del modelo y construir**

```bash
cp "C:/Users/[retirado]/datasets/rsna-pneumonia/trabajo/corridas/efficientnet_b0_320px_lote24_4+20ep/checkpoints/pesos_modelo_cpu.pt" servidor/pesos_modelo_cpu.pt
cd servidor && docker compose build
```

Esperado: construye sin error. Anota el tamaño con `docker images copiloto-mcp`.
Debe rondar los 800 MB; si pasa de 1,5 GB, la rueda CPU de torch no se aplicó.

Añade a `.gitignore`:

```
servidor/pesos_modelo_cpu.pt
```

Los pesos no se versionan (16 MB binarios); el `calibrador.json` sí.

- [ ] **Paso 5: levantar y probar de extremo a extremo**

```bash
docker compose up -d
docker compose ps        # el estado debe ser "healthy"
docker compose exec copiloto-mcp python -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/salud')))"
```

Esperado: `{'estado': 'listo', 'modelo': 'efficientnet_b0_320px', ...}`

- [ ] **Paso 6: medir la latencia DENTRO del contenedor**

Es un criterio de aceptación de H4, así que se mide donde va a correr, no en
la máquina de desarrollo:

Copia primero un DICOM real del conjunto de prueba al contenedor:

```bash
docker compose cp "C:/Users/[retirado]/datasets/rsna-pneumonia/trabajo/crudo/stage_2_train_images/<id>.dcm" copiloto-mcp:/modelo/ejemplo.dcm
```

Y mide, dentro del contenedor, por las dos puertas:

```bash
docker compose exec copiloto-mcp python - <<'PYEOF'
import base64, json, statistics, time, urllib.request

datos = open("/modelo/ejemplo.dcm", "rb").read()
print(f"DICOM de prueba: {len(datos)} bytes")


def cronometrar(envio, repes=20):
    envio()  # una de calentamiento: la primera paga el arranque perezoso
    tiempos = []
    for _ in range(repes):
        t0 = time.perf_counter()
        envio()
        tiempos.append(time.perf_counter() - t0)
    return statistics.median(tiempos), max(tiempos)


def por_rest():
    frontera = "----x"
    cabecera = (f"--{frontera}\r\n"
                'Content-Disposition: form-data; name="archivo"; '
                'filename="a.dcm"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n").encode()
    cuerpo = cabecera + datos + f"\r\n--{frontera}--\r\n".encode()
    pet = urllib.request.Request(
        "http://127.0.0.1:8000/inferir", data=cuerpo,
        headers={"Content-Type": f"multipart/form-data; boundary={frontera}"})
    return json.load(urllib.request.urlopen(pet))


def por_mcp():
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": {"dicom_base64":
                                 base64.b64encode(datos).decode()}}}).encode()
    pet = urllib.request.Request(
        "http://127.0.0.1:8000/mcp", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    return urllib.request.urlopen(pet).read()


print("resultado de una inferencia:", json.dumps(por_rest(), indent=2))
for nombre, envio in (("REST", por_rest), ("MCP ", por_mcp)):
    mediana, peor = cronometrar(envio)
    print(f"{nombre}: mediana {mediana*1000:.0f} ms | peor {peor*1000:.0f} ms "
          f"| presupuesto 4000 ms -> {4/mediana:.0f}x de margen")
PYEOF
```

Registra las dos medianas en `docs/sp2-despliegue.md`. Si alguna supera los
4 000 ms, **para**: el criterio de aceptación de H4 no se cumple y hay que
averiguar por qué antes de seguir.

- [ ] **Paso 7: escribir la guía de despliegue**

Crea `docs/sp2-despliegue.md` con: los requisitos previos, cómo averiguar el
nombre de la red de n8n, los comandos de construcción y arranque, cómo
comprobar la salud, la latencia medida en el paso 6, y cómo configurar el nodo
MCP de n8n apuntando a `http://copiloto-mcp:8000/mcp`.

El destinatario es tu compañero haciendo la prueba cruzada **sin conocer el
código**: si un paso exige saber algo que no está escrito ahí, falta.

- [ ] **Paso 8: commit**

```bash
git add servidor/ docs/sp2-despliegue.md .gitignore
git commit -m "Contenedor del servidor MCP y su compose"
```

---

## Verificación final de SP2

Antes de dar SP2 por terminado, comprueba los cinco criterios de aceptación
del spec:

1. [ ] Caso de extremo a extremo desde n8n con una imagen de prueba.
2. [ ] Latencia medida **dentro del contenedor** y registrada en
   `docs/sp2-despliegue.md`. Debe estar muy por debajo de 4 s.
3. [ ] `docker compose up` desde cero en una máquina limpia, siguiendo solo
   `docs/sp2-despliegue.md`.
4. [ ] La prueba de equivalencia entre las dos puertas pasa, y se comprobó que
   falla cuando se rompe una de ellas (Tarea 5, paso 5).
5. [ ] Una placa de menor de 18 años se rechaza con `fuera_de_alcance`, y una
   sin edad legible con `edad_desconocida`.

Y la suite completa: `C:/venv-copiloto/Scripts/python.exe -m pytest -q`
