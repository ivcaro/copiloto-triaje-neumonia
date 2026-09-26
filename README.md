# Copiloto de triaje para neumonía en adultos

Proyecto Integrador (UEES, Maestría en IA). Dos sub-proyectos entregados:

- **SP1 — núcleo de imagen.** Entrena una CNN de clasificación binaria sobre
  radiografías de tórax de adultos del dataset RSNA, con partición por paciente
  verificada sin fuga de datos.
- **SP2 — servidor.** Sirve esa CNN en Docker por dos puertas —una herramienta
  MCP y un `POST /inferir` de respaldo— para que n8n la consulte sin que la
  imagen salga nunca de la red local. Ver `docs/sp2-despliegue.md`.

La arquitectura se fijó **midiendo**, no a priori: las tres candidatas empatan
en AUC 0,874-0,889, un margen del orden de la varianza entre dos ejecuciones de
la misma configuración. Se despliega EfficientNet-B0 a 320 px (AUC de
validación 0,8827). El razonamiento está en `docs/comparativa-corridas.md`.

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
| Preparación de datos (26 684 DICOM) | Sí (`--crudo`, ~25 min) | Sí, el conjunto completo |
| **Entrenamiento real** | Sí, pero caro (`scripts/entrenar_local.py`) | Sí, en horas |

El entrenamiento local **es posible y está soportado**, no es lo preferente.
Medido en una CPU de 20 hilos lógicos (10 de cómputo), para 4 + 20 épocas:
DenseNet121 a 320 px cuesta **24,9 h**, EfficientNet-B0 a 320 px **10,8 h** y
MobileNetV3 a 224 px **3,1 h**; la carga de imágenes no es el cuello de botella
(268 img/s con 8 procesos). Con GPU son horas. Por eso la ruta preferente sigue
siendo Colab o Kaggle, y `scripts/entrenar_local.py` existe para cuando la
cuota de GPU se agota: es reanudable justamente porque son corridas de una
noche. El notebook **instala el paquete**
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

### Lo que `pytest` NO ejecuta por sí solo

`pytest` corre el paquete de Python. Los dos bots de n8n tienen sus propias
suites, que ejecutan el `jsCode` **real** de los nodos y hay que lanzar aparte:

```
node tests/profesional.mjs
node tests/decidir.mjs
node tests/mantenimiento.mjs
```

Cada una imprime `TODO VERDE` y sale 0, o cuenta los fallos y sale 1. **No las
encadene con una tubería**: `node tests/profesional.mjs | tail` devuelve el
estado de `tail`, que es 0 siempre, y así se han fusionado pruebas rojas.

### Las que se saltan, y qué se queda sin comprobar

Varias pruebas necesitan algo que no está siempre: el contenedor del copiloto,
una Postgres desechable, el túnel a la base del VPS o los secretos de Telegram.
**Se saltan en vez de fallar**, con el motivo escrito y el comando para
levantarlo, porque un `ConnectionRefusedError` repetido ensena a no mirar los
fallos. El precio es que **un skip se ve verde**:

```
C:\venv-copiloto\Scripts\python.exe -m pytest -q -rs
```

`-rs` lista cada salto con lo que deja sin verificar. Conviénelo antes de decir
que la suite está en verde.

Entre ellas, `tests/test_sql_de_los_nodos.py` llama a los dos arneses de
`pruebas/verificar_sql_*.py`, que son los **únicos** que comprueban la semántica
SQL de los nodos: la lista blanca, el borrado de sesión, los tipos del `jsonb`,
la copia de síntomas a `consultas` y la idempotencia del doble toque. Antes
vivían fuera de `testpaths` y no los nombraba nadie: nueve de nueve mutaciones a
esas consultas dejaban la suite entera en verde.

## Datos del dataset (verificados el 16-sep-2026)

26 684 imágenes de entrenamiento, una por paciente. 6 012 positivos (22,5%),
11 821 anormales sin opacidad (44,3%), 8 851 normales (33,2%). El desbalance se
maneja con partición estratificada, ponderación de clases y selección del umbral
sobre la curva ROC de validación.

## El servidor (SP2)

`servidor/` contiene el Dockerfile y el compose. El contenedor **no publica
puertos**: se une a la red interna donde ya vive n8n, y ahí lo llaman por su
nombre. Esa es la garantía de que la radiografía no sale de la red local.

Lo que devuelve no es la salida cruda del modelo, que está desplazada por el
`pos_weight` del entrenamiento. Se calibra con una isotónica ajustada sobre las
3 810 imágenes de validación y se entrega como **razón de verosimilitud
acotada** a `[0,0163 ; 77,32]` —los extremos que los datos sostienen—, para que
la evidencia de imagen pueda mover la probabilidad previa de la regla clínica
pero no anularla ni volverla certeza. Sin esa cota, una sola radiografía en el
extremo saturado de la curva producía una razón de 3,5e-06, capaz de bajar un
previo de 0,90 a 0,003%.

El modelo **se niega** a opinar sobre pacientes fuera de 18-100 años, leyendo la
edad de la cabecera DICOM: se entrenó y se validó sobre adultos, y devolver un
número que nadie validó sería peor que no devolver nada.

Latencia medida dentro del contenedor con la CPU acotada a 2 núcleos: 38 ms por
REST y 43 ms por MCP, contra un presupuesto de 4 s.

Los pesos (16 MB) **no viajan en el repo**: están en `.gitignore` y se copian al
servidor por separado. `docs/sp2-despliegue.md` tiene el procedimiento completo,
con los pre-chequeos de solo lectura y la vuelta atrás.

## Documentos

- Diseño SP1: `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`
- Plan SP1: `docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md`
- Diseño SP2: `docs/superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md`
- Plan SP2: `docs/superpowers/plans/2026-09-23-sp2-servidor-mcp.md`
- Despliegue: `docs/sp2-despliegue.md`
- Comparativa de arquitecturas: `docs/comparativa-corridas.md`
- Frontera recall/especificidad: `docs/frontera-recall-especificidad.md`
