# Copiloto de triaje para neumonía en adultos — núcleo de imagen (SP1)

Primer sub-proyecto del Proyecto Integrador (UEES, Maestría en IA). Entrena una
CNN de clasificación binaria sobre radiografías de tórax de adultos del dataset
RSNA, con partición por paciente verificada sin fuga de datos.

## Requisitos

Entorno virtual en **ruta corta** (obligatorio en Windows: el Python de Microsoft
Store provoca `WinError 206` al instalar torchvision):

```
python -m venv C:\venv-copiloto
C:\venv-copiloto\Scripts\python.exe -m pip install -e . --no-deps
```

> **Por qué `--no-deps`:** `C:\venv-copiloto` ya está aprovisionado y verificado
> con `torch==2.14.0+cpu` y `torchvision==0.29.0+cpu`, y con el resto de
> dependencias de `pyproject.toml` (incluido `pytest`). Sin `--no-deps`, pip
> intentaría resolver e instalar de nuevo esas dependencias desde PyPI y podría
> volver a chocar con el `WinError 206` (ruta demasiado larga) que obligó a
> crear este entorno en ruta corta. Este comando solo registra `copiloto-triaje`
> en modo editable en un entorno que ya tiene todo lo demás instalado: no lo
> quites para "arreglarlo". Si algún día se aprovisiona un entorno nuevo desde
> cero, ahí sí hace falta `pip install -e ".[dev]"` sin `--no-deps`.

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
días y no alcanzaría el Recall comprometido. El notebook **instala el paquete**
(no lo pega a `sys.path`), de modo que los pines de `pyproject.toml` también se
aplican en Colab, y luego comprueba el entorno: si no hay GPU, o si
`copiloto_triaje` no viene del paquete instalado, se detiene.

## Reproducir desde cero

1. **Local:** instalar y pasar las pruebas (`pytest -v`). Opcionalmente, verificar
   el script de preparación sobre una muestra:
   `C:\venv-copiloto\Scripts\python.exe scripts/preparar_datos.py --zip <zip> --raiz <dir> --limite 200`
2. **Colab o Kaggle:** abrir `notebooks/entrenar_gpu.ipynb` y ejecutar las celdas
   en orden. El notebook descarga el dataset desde Kaggle por sí mismo, prepara
   los datos y entrena con GPU. En Drive quedan los checkpoints y los
   entregables: `reporte_metricas.md`, `reporte_metricas.json`, `curva_roc.svg`
   y `pesos_modelo_cpu.pt` (el `state_dict` limpio, en CPU, que consumirá SP2).
3. Requisito previo para el paso 2: cuenta de Kaggle con las reglas de la
   competencia aceptadas, y los secretos `KAGGLE_USERNAME` y `KAGGLE_KEY`
   configurados en Colab.
4. **Si Colab se cae a mitad del entrenamiento:** volver a ejecutar el notebook
   con `REANUDAR = True` (el valor por defecto). Como los checkpoints están en
   Drive, `entrenar` retoma desde `ultimo.pt` —pesos, optimizador, época, fase,
   historial y contadores— en vez de empezar de cero.

## Pruebas

```
C:\venv-copiloto\Scripts\python.exe -m pytest -v
```

Las dos pruebas más importantes son las que protegen la ausencia de fuga de
datos: `tests/test_particion.py` verifica la lógica de partición, y
`tests/test_manifiestos_emitidos.py` ejecuta el script de preparación de punta a
punta y comprueba la propiedad **sobre los tres CSV que quedan en disco**, que
son los que alimentan al Dataset. Si alguna falla, las métricas no significan
nada.

## Datos del dataset (verificados el 16-sep-2026)

26 684 imágenes de entrenamiento, una por paciente. 6 012 positivos (22,5%),
11 821 anormales sin opacidad (44,3%), 8 851 normales (33,2%). El desbalance se
maneja con partición estratificada, ponderación de clases y selección del umbral
sobre la curva ROC de validación.

## Documentos

- Diseño: `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`
- Plan: `docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md`
