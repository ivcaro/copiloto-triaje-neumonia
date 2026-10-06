# SP5-C1 — La interfaz de demostración y el umbral por vista: plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar este plan tarea a tarea. Los pasos
> usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** una app Streamlit en Docker que cualquiera pueda usar para probar
el copiloto con el mismo motor que el servidor, más el umbral por vista
(apagado por defecto) y el mapa de calor que comprometió el workshop S4.

**Arquitectura:** dos piezas nuevas en el núcleo (`Motor`): el parámetro
`umbrales_por_vista` y el método `mapa_de_calor`. Encima, `app/`: la app, sus
ejemplos con licencia, las métricas en agregados y su imagen Docker. El
servidor solo gana dos variables de entorno opcionales.

**Pila:** Python 3.13, PyTorch en CPU, pydicom, Streamlit (versión fijada en
`app/requirements.txt`), pytest. Las pruebas se corren en la imagen Linux
`copiloto-pruebas:linux` (en Windows, Smart App Control bloquea
scikit-learn), y las de Docker, en Windows con Docker Desktop.

**Spec:** `docs/superpowers/specs/2026-10-05-sp5c1-interfaz-y-umbral-por-vista-design.md`.

**Parte de:** `main` en `35a01c8`. Rama: `sp5c1-interfaz`.

## Restricciones globales

1. **La respuesta del motor sin `umbrales_por_vista` no cambia en nada**: es
   la de hoy clave por clave, con y sin `hallazgos` (criterio de SP3 y SP4).
2. **Un solo camino de imagen a tensor**: `Motor._tensor_desde_arreglo`. El mapa
   de calor lo usa; no se escribe otro.
3. **Ningún dato del conjunto de entrenamiento en el repositorio**: ni placas de
   RSNA o del NIH ni filas por paciente. Los ejemplos vienen de fuera de RSNA
   con licencia que permita redistribuirlos; las métricas, en agregados.
4. **Nada que identifique al cliente** (dirección, dominio, nombres), ni rutas
   de una máquina, ni secretos, en ningún fichero versionado. El verificador
   (`scripts/verificar_anonimato.py --raiz .`) sale con 0 después de cada
   commit, y cada binario nuevo se declara (prueba de los binarios y
   `tests/anonimato/README.md`) después de mirarlo.
5. **Versiones fijadas** de toda dependencia nueva.
6. Mensajes de commit en español, al estilo del repositorio, con la línea final
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
7. Las pruebas, en la imagen Linux, desde Git Bash:

       export MSYS_NO_PATHCONV=1
       docker run --rm -v "<clon>:/repo" -v "<RSNA_RAIZ>:/datos:ro" -e RSNA_RAIZ=/datos copiloto-pruebas:linux python -m pytest -q -p no:cacheprovider <pruebas>

## Ficheros

| Fichero | Tarea | Qué |
| :--- | :--- | :--- |
| `src/copiloto_triaje/servicio/inferencia.py` | 1, 2 | `umbrales_por_vista`; `mapa_de_calor` |
| `servidor/arrancar.py`, `docs/sp2-despliegue.md` | 1 | `UMBRAL_PA`/`UMBRAL_AP`, las dos o ninguna |
| `tests/test_inferencia.py`, `tests/test_arrancar.py` | 1, 2 | pruebas |
| `app/generar_metricas.py`, `app/assets/metricas.json`, `tests/test_app_metricas.py` | 3 | métricas en agregados |
| `app/empaquetar_ejemplos.py`, `app/assets/ejemplos/`, `app/assets/LICENCIAS.md`, `tests/test_app_ejemplos.py` | 4 | ejemplos |
| `app/app.py`, `app/requirements.txt`, `app/.streamlit/config.toml`, `tests/test_app.py` | 5 | la app |
| `app/Dockerfile`, `app/.dockerignore`, `README.md` | 6 | imagen y documentación |

---

### Tarea 1: El umbral por vista en el motor y en el servidor

**Interfaces:**
- Produce: `Motor(..., umbrales_por_vista: Mapping[str, float] | None = None)` y
  `Motor.cargar(..., umbrales_por_vista=None)`. Con el parámetro, la respuesta
  de `clasificar` lleva `umbral` = el aplicado y `umbral_por_vista: {"vista":
  "PA" | "AP" | None, "aplicado": bool}`.

- [ ] **Paso 1: las pruebas** (en `tests/test_inferencia.py`, con la fixture
  `motor` y los DICOM sintéticos que ya usa el fichero; el helper que escribe
  un DICOM gana un parámetro `vista` si no lo tiene):
  - `test_sin_umbrales_por_vista_la_respuesta_no_cambia`: con y sin
    `hallazgos`, el conjunto de claves y los valores son los de hoy (la prueba
    de SP3 «clave por clave» sigue pasando y no se toca).
  - `test_con_umbrales_por_vista_cada_vista_usa_el_suyo`: un modelo de
    puntuación fija entre los dos umbrales (p. ej. 0,30 con PA 0,18 y AP 0,58):
    PA → `opacidad_probable`, `umbral` 0,18, `umbral_por_vista` `{"vista":
    "PA", "aplicado": True}`; AP → `sin_opacidad_probable`, `umbral` 0,58.
  - `test_una_vista_desconocida_usa_el_umbral_global`: sin `ViewPosition`, o
    con `LL`, el global y `{"vista": None, "aplicado": False}`.
  - `test_la_vista_se_lee_sin_espacios_ni_minusculas`: `" pa "` cuenta como PA.
  - `test_el_umbral_por_vista_no_toca_la_evidencia_ni_la_combinacion`: la razón
    de verosimilitud, la probabilidad calibrada y el bloque `combinacion` son
    iguales con y sin el parámetro.
  - `test_unos_umbrales_por_vista_mal_formados_se_rechazan_al_construir`:
    falta una clave, sobra una, un valor 0, 1, negativo, `nan` o no numérico →
    `ValueError` que dice qué está mal.
  - En `tests/test_arrancar.py`: con solo `UMBRAL_PA` (o solo `UMBRAL_AP`) el
    arranque se detiene diciendo que hacen falta las dos; con un valor fuera
    de (0, 1), diciendo cuál; con las dos válidas, pasa de esa comprobación
    (mismo patrón que las pruebas de `PREVALENCIA_LOCAL`).

- [ ] **Paso 2: verlas fallar** (en la imagen Linux): `tests/test_inferencia.py
  tests/test_arrancar.py`.

- [ ] **Paso 3: el código.** En `Motor.__init__`, guardar y validar el
  parámetro (exactamente `{"PA", "AP"}`, valores finitos en (0, 1)). En
  `clasificar`, tras leer `meta`:

  ```python
  umbral = self.umbral
  por_vista = None
  if self.umbrales_por_vista is not None:
      vista = (meta.get("vista") or "").strip().upper()
      if vista in self.umbrales_por_vista:
          umbral = self.umbrales_por_vista[vista]
          por_vista = {"vista": vista, "aplicado": True}
      else:
          por_vista = {"vista": None, "aplicado": False}
  ```

  y usar `umbral` en `umbral` y `clasificacion`; añadir `umbral_por_vista`
  solo si `por_vista` no es `None`, justo después de `umbral` en el orden de
  claves. `Motor.cargar` lo pasa tal cual. En `servidor/arrancar.py`, leer
  `UMBRAL_PA` y `UMBRAL_AP`: ninguna → `None`; una sola → `SystemExit` con un
  mensaje que diga que van juntas; fuera de (0, 1) → `SystemExit` diciendo cuál.
  En `docs/sp2-despliegue.md`, la tabla de variables gana las dos, con «apagado
  si no se definen» y los valores del workshop S4 como ejemplo.

- [ ] **Paso 4: verlas pasar**, y la suite de `tests/test_contrato_mcp.py` y
  `tests/test_contrato_sp4.py` sin cambios (el compose no define las
  variables).

- [ ] **Paso 5: commit** — `feat(servicio): el umbral por vista, apagado por defecto`.

---

### Tarea 2: El mapa de calor

**Interfaces:**
- Consume: `Motor._tensor_desde_arreglo`, `leer_dicom_desde_bytes`, las
  comprobaciones de edad de `clasificar`.
- Produce: `Motor.mapa_de_calor(datos_dicom: bytes) -> numpy.ndarray` de forma
  `(tam_imagen, tam_imagen)`, `float32` en [0, 1].

- [ ] **Paso 1: las pruebas** (`tests/test_inferencia.py`; el modelo de la
  fixture `motor` es trivial, así que para estas se construye un
  `construir_modelo("efficientnet_b0", preentrenado=False)` con pesos
  aleatorios y semilla fija):
  - forma y tipo; valores en [0, 1]; máximo 1 salvo matriz de ceros;
  - determinismo: dos llamadas, el mismo resultado;
  - una imagen uniforme no da `nan`;
  - una placa de menor, una sin edad y un fichero que no es DICOM se rechazan
    con `fuera_de_alcance`, `edad_desconocida` y `dicom_invalido`;
  - después de `mapa_de_calor`, `clasificar` de la misma placa da lo mismo, el
    modelo sigue en modo evaluación y no le queda ningún gancho registrado
    (`_forward_hooks` y `_backward_hooks` del módulo objetivo vacíos).

- [ ] **Paso 2: verlas fallar.**

- [ ] **Paso 3: el código.** Factorizar la lectura y las comprobaciones de
  edad de `clasificar` en un método privado que usen los dos (sin cambiar los
  mensajes ni los códigos). Grad-CAM sobre `modelo.features[-1]` (el último
  bloque de EfficientNet-B0 de torchvision), respecto del logit: activaciones
  y gradientes capturados con ganchos que se quitan en un `finally`; pesos =
  media espacial del gradiente; mapa = ReLU de la suma ponderada,
  interpolado a `tam_imagen` y normalizado por su máximo (si el máximo es 0,
  ceros). Con `torch.enable_grad()` dentro y el modelo en `eval()` al salir.

- [ ] **Paso 4: verlas pasar**, y todo `tests/test_inferencia.py`.

- [ ] **Paso 5: commit** — `feat(servicio): el mapa de calor de la imagen, por el mismo camino que la clasificación`.

---

### Tarea 3: Las métricas en agregados

**Interfaces:**
- Produce: `app/assets/metricas.json` con `{"generado": ..., "pesos_sha256":
  ..., "puntuaciones_sha256": ..., "umbral": 0.4258, "umbrales_por_vista":
  {"PA": ..., "AP": ...}, "global": {...}, "subgrupos": [{"nombre", "n",
  "positivos", "auc", "recall", "recall_ic", "especificidad",
  "especificidad_ic"}, ...], "umbral_por_vista_en_prueba": {...}}`.

- [ ] **Paso 1: las pruebas** (`tests/test_app_metricas.py`):
  - el JSON versionado tiene esas claves y ningún campo por paciente (ni
    `patientId` ni listas de la longitud del conjunto);
  - si están las puntuaciones congeladas (`docs/validacion-semisintetica/crudas_prueba.csv`
    en el repositorio de desarrollo), recalcular da el mismo JSON salvo la
    fecha; si no están (el repositorio público), la prueba se salta diciéndolo;
  - los subgrupos son los de la tabla 2 del workshop S4 (todas, sexo, tres
    tramos de edad, vista, y los cruces de vista con sexo y con 60 o más).

- [ ] **Paso 2: verlas fallar.**

- [ ] **Paso 3: el código.** `app/generar_metricas.py` con AUC por
  Mann-Whitney con rangos medios, Wilson z = 1,96, y los umbrales por vista
  leídos de un parámetro (los del workshop S4 por defecto: 0,1798 y 0,5815),
  más su efecto en prueba (recall y especificidad por vista y global con un
  umbral y con dos). Escribe el JSON con `ensure_ascii=False, indent=2`.

- [ ] **Paso 4: generar el JSON, verlas pasar.**

- [ ] **Paso 5: commit** — `feat(app): las métricas de «Acerca de», en agregados`.

---

### Tarea 4: Los ejemplos

**Requisito previo:** el equipo aprueba la descarga de cada imagen (fichero,
fuente, tamaño y licencia). Sin esa aprobación, esta tarea no empieza.

- [ ] **Paso 1: las pruebas** (`tests/test_app_ejemplos.py`): cada DICOM de
  `app/assets/ejemplos/` se lee con `leer_dicom_desde_bytes`, declara la edad,
  el sexo y la vista que dice `app/assets/LICENCIAS.md` y no lleva ningún otro
  campo de paciente con contenido (nombre, identificador, fechas); hay uno por
  tipo (normal PA, opacidad PA, AP) y el «rechazado» con 15 años; cada uno
  tiene fuente, autor, licencia y atribución en `LICENCIAS.md`.
- [ ] **Paso 2: verlas fallar.**
- [ ] **Paso 3: el código.** `app/empaquetar_ejemplos.py`: de cada imagen
  original (guardada en `app/assets/originales/`) a un DICOM de 8 bits
  MONOCHROME2 con `PatientAge` (`"045Y"`), `PatientSex`, `ViewPosition` y
  UIDs generados, sin nombre ni fecha de paciente.
- [ ] **Paso 4: mirar cada binario, declararlo** en la prueba de los binarios y
  en `tests/anonimato/README.md`, y verlas pasar con el verificador en 0.
- [ ] **Paso 5: commit** — `feat(app): los ejemplos, de fuera de RSNA y con su licencia`.

---

### Tarea 5: La app

**Interfaces:**
- Consume: `Motor.cargar(...)`, `Motor.clasificar`, `Motor.mapa_de_calor`,
  `ErrorDeInferencia`, `app/assets/metricas.json`, `app/assets/ejemplos/`.
- Produce: `app/app.py`, ejecutable con `streamlit run app/app.py`. Lee
  `UMBRAL`, `AUC_VALIDACION` y `PREVALENCIA_LOCAL` del entorno, con la misma
  disciplina que el servidor (las dos últimas, obligatorias), y las rutas de
  los pesos y del calibrador de `RUTA_PESOS` y `RUTA_CALIBRADOR` con las del
  repositorio por defecto.

- [ ] **Paso 1: las pruebas** (`tests/test_app.py`, con
  `streamlit.testing.v1.AppTest`; el motor se sustituye por uno con el modelo
  trivial de `tests/test_inferencia.py` mediante una variable de entorno de
  prueba que la app documenta, para no cargar pesos):
  - la app arranca sin excepciones y enseña «Acerca de»;
  - con cada ejemplo y «Calcular», enseña los bloques (cribado, evidencia,
    clínica si hay hallazgos, combinado, «Esto no es un diagnóstico.»);
  - con el «rechazado», el mensaje de `fuera_de_alcance` en lenguaje llano y
    ningún bloque de resultado;
  - un fichero que no es DICOM, el mensaje de `dicom_invalido`;
  - hallazgos fuera de los límites de interfaz no se pueden enviar;
  - el interruptor cambia el umbral aplicado y enseña la vista;
  - el historial crece con cada cálculo y el CSV tiene las columnas
    declaradas y ninguna imagen.
- [ ] **Paso 2: verlas fallar.**
- [ ] **Paso 3: el código.** Lo que dice el §3 del spec. El motor se carga una
  vez (`st.cache_resource`); el mapa de calor se pinta con la placa original
  y una transparencia; la horquilla, en un gráfico (Streamlit o Plotly, con la
  versión fijada); los textos de los avisos, iguales a los del bot donde el
  bot los tiene. `app/.streamlit/config.toml` con `maxUploadSize = 5`.
  `app/requirements.txt` con las versiones fijadas.
- [ ] **Paso 4: verlas pasar.**
- [ ] **Paso 5: commit** — `feat(app): la interfaz de demostración`.

---

### Tarea 6: La imagen Docker y la documentación

- [ ] **Paso 1: la imagen.** `app/Dockerfile` (base `python:3.13-slim`, torch
  en CPU, `app/requirements.txt`, `src/`, `app/`, los pesos y el calibrador
  de `servidor/`, las variables con los valores del `docker-compose.yml`,
  `EXPOSE 8501`, `streamlit run app/app.py --server.address=0.0.0.0`), y
  `app/.dockerignore` (sin `.git`, sin `pruebas/`, sin `docs/`).
- [ ] **Paso 2: la prueba de humo**, en Windows con Docker: construir, arrancar
  con `-p 127.0.0.1:8501:8501`, esperar a `/_stcore/health` y pedir `/`; una
  prueba en `tests/test_app_docker.py` que se salta, diciéndolo, si no hay
  Docker.
- [ ] **Paso 3: el README**: la sección «Interfaz de usuario» (qué es, cómo se
  ejecuta, de dónde salen los pesos, capturas, que los ejemplos son de otra
  fuente) y el mapa de la carpeta `app/`.
- [ ] **Paso 4: la suite entera** (Linux y Windows), el verificador en 0.
- [ ] **Paso 5: commit** — `feat(app): la imagen Docker de la interfaz, y su documentación`.

---

## Autorrevisión del plan

- **Cobertura del spec:** D1-D9 y §3-§9 tienen tarea: el umbral (T1), el mapa
  (T2), las métricas (T3), los ejemplos (T4), la pantalla y «Acerca de» (T5),
  la ejecución y el README (T6). El §10 queda fuera, como dice.
- **Orden:** T5 consume T1-T4; T6, T5. T4 espera la aprobación de las
  descargas; mientras tanto se puede adelantar T5 con un ejemplo de prueba
  sintético que no se versiona.
- **Riesgo de regresión:** la restricción 1 la vigila la prueba de SP3 «clave
  por clave», que no se toca, y las de contrato.
