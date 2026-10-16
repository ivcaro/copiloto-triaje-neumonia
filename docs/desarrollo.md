# Desarrollo: entorno, servidor, pruebas y reproducción

Lo técnico del proyecto que no cabe en el [README](../README.md): cómo se montó el entorno,
qué variables de entorno hacen falta, dónde corre cada cosa, cómo se reproduce desde cero,
cómo se corren las pruebas (y cuáles se saltan), cómo funciona el servidor de inferencia y los
detalles de la aplicación de demostración. Hasta el 15 de octubre de 2026 todo esto vivía en
el README; con la estructura del curso (SP5-C2) el README pasó a ser la carta de presentación y
esto se trasladó aquí sin perder nada.

Para usar el sistema basta el [manual de usuario](manual_usuario.md); para entender cómo está
hecho, la [arquitectura](arquitectura.md).

## Contenido

1. [Los sub-proyectos](#1-los-sub-proyectos)
2. [El entorno de desarrollo](#2-el-entorno-de-desarrollo)
3. [Variables de entorno](#3-variables-de-entorno)
4. [Dónde corre cada cosa](#4-dónde-corre-cada-cosa)
5. [Reproducir desde cero](#5-reproducir-desde-cero)
6. [Pruebas](#6-pruebas)
7. [Las tablas derivadas del dataset](#7-las-tablas-derivadas-del-dataset)
8. [El servidor (SP2)](#8-el-servidor-sp2)
9. [La aplicación de demostración, en detalle](#9-la-aplicación-de-demostración-en-detalle)
10. [Documentos de diseño](#10-documentos-de-diseño)

## 1. Los sub-proyectos

El proyecto se construyó en sub-proyectos, cada uno con su diseño (`docs/superpowers/specs/`)
y su plan (`docs/superpowers/plans/`):

- **SP1 — núcleo de imagen.** Entrena una CNN de clasificación binaria sobre
  radiografías de tórax de adultos del dataset RSNA, con partición por paciente
  verificada sin fuga de datos.
- **SP2 — servidor.** Sirve esa CNN en Docker por dos puertas —una herramienta
  MCP y un `POST /inferir` de respaldo— para que n8n la consulte **sin que la
  imagen salga del VPS en ese paso**: el contenedor no publica puertos. Antes de
  llegar ahí el DICOM viaja **por Telegram**, que no es infraestructura nuestra;
  es un riesgo declarado, no una omisión (§5.5 del diseño de SP3). Ver
  [`sp2-despliegue.md`](sp2-despliegue.md) y la [sección 8](#8-el-servidor-sp2).
- **SP3 — los bots.** Los dos bots de Telegram (paciente y profesional) y el workflow de
  mantenimiento, orquestados con n8n (`n8n/`), con la base de datos PostgreSQL del sistema
  (`bd/`). Su operación, en [`sp3-operacion.md`](sp3-operacion.md).
- **SP4 — combinación bayesiana.** La regla clínica de Heckerling y su combinación con la
  evidencia de la imagen ([sección 8](#8-el-servidor-sp2), «Desde SP4»).
- **SP5 — validación semisintética y sesión con el médico.** El
  generador por puntuación de Heckerling, su oráculo, las métricas y la
  simulación por celda viven en `src/copiloto_triaje/validacion/`; los insumos
  y resultados, rotulados como simulación semisintética, en
  `docs/validacion-semisintetica/`, y su análisis en
  [`validacion-semisintetica-sp5.md`](validacion-semisintetica-sp5.md): lo genera
  `scripts/validar_combinacion.py` sin teclear ninguna cifra, y se reproduce
  sin los pesos. La simulación **no mide exactitud clínica**: mide si el
  sistema calcula lo que dice calcular y cuánto se desvía bajo cada supuesto
  de dependencia entre clínica e imagen. El procedimiento de la sesión con el
  médico, en [`sp5-sesion.md`](sp5-sesion.md), y su resultado, en el
  [acta](validacion-semisintetica/acta-h7.md).
- **SP5-C1 — interfaz de usuario.** Una página web (Streamlit) con la que
  cualquier persona prueba el mismo motor que usa el bot, sin cuenta de
  Telegram: `app/`, en Docker, con ejemplos precargados, el mapa de calor de la
  placa y una sección «Acerca de». Ver la [sección 9](#9-la-aplicación-de-demostración-en-detalle).
- **SP5-C2 — la estructura del curso.** La capa de rutas que pide el curso (`src/*.py`,
  `notebooks/01` a `05`, `data/`, `models/`, `results/`) como puntos de entrada finos sobre el
  código de siempre, y la documentación de `docs/` (diseño en
  `docs/superpowers/specs/2026-10-15-sp5c2-estructura-y-documentacion-design.md`).

La arquitectura se fijó **midiendo**, no a priori: las tres candidatas empatan
en AUC 0,874-0,889, un margen del orden de la varianza entre dos ejecuciones de
la misma configuración. Se despliega EfficientNet-B0 a 320 px (AUC de
validación 0,8827). El razonamiento está en [`comparativa-corridas.md`](comparativa-corridas.md)
y en [`optimizacion.md`](optimizacion.md).

## 2. El entorno de desarrollo

Para usar el proyecto basta `pip install -r requirements.txt` en un entorno virtual (README,
«Instalación y uso»). Lo que sigue es el entorno con el que se desarrolló en Windows.

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

**Smart App Control.** En algunas máquinas Windows, Smart App Control bloquea las bibliotecas
compiladas de torch y de scikit-learn: lo que las importa no carga. Esas pruebas se corren en
una imagen Linux de pruebas con las dependencias de `requirements.txt` (la del equipo se llama
`copiloto-pruebas:linux`), con el repositorio montado ([sección 6](#6-pruebas)), y la
aplicación, con Docker ([sección 9](#9-la-aplicación-de-demostración-en-detalle)).

## 3. Variables de entorno

Ningún valor que identifique una instalación está escrito en el repositorio:
se pasa por el entorno. Sin ellas, lo que las necesita se detiene con un
mensaje o, en la suite, se salta diciendo qué se queda sin verificar.

| Variable | Quién la necesita | Qué es |
| :--- | :--- | :--- |
| `RSNA_RAIZ` | `scripts/preparar_sesion.py`, `pruebas/seleccionar_casos.py`, `pruebas/reproducir_casos.py` (con bots y sin ellos), `pruebas/puntuaciones.py` y `pruebas/caracterizar_conjunto.py` (estos dos, solo si no hay caché), los guiones de entrenamiento y las pruebas que leen placas | la raíz del dataset preparado (`crudo/`, `png/`, `manifiestos/`; ver [`data/README.md`](../data/README.md)) |
| `N8N_URL` | `pruebas/reproducir_casos.py` con bots, `pruebas/verificar_webhooks.py` y las pruebas conducidas | la dirección base de n8n, p. ej. `https://n8n.ejemplo.test` |
| `RED_N8N` | `servidor/docker-compose.yml` (se declara en `servidor/.env`) | el nombre de la red externa de Docker que comparte n8n; obligatoria |
| `COPILOTO_URL`, `COPILOTO_BD_DSN`, `TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`, `CHAT_SUBIDA_PLACAS` | el arnés y las pruebas conducidas | las describe la cabecera de `pruebas/reproducir_casos.py`. Ojo: `COPILOTO_URL` no quiere el mismo valor en el arnés y en las pruebas de contrato ([`sp3-operacion.md`](sp3-operacion.md), §2) |
| `ANONIMATO_LISTA` | solo quien mantiene la lista de lo que no se publica, para regenerar las huellas | la ruta de esa lista, que vive fuera del repositorio ([`tests/anonimato/README.md`](../tests/anonimato/README.md)) |
| `UMBRAL`, `AUC_VALIDACION`, `PREVALENCIA_LOCAL`, `RUTA_PESOS`, `RUTA_CALIBRADOR` | el servidor y la aplicación | las cifras del despliegue y dónde están los pesos y el calibrador ([sección 8](#8-el-servidor-sp2) y [sección 9](#9-la-aplicación-de-demostración-en-detalle)) |

Los workflows de `n8n/` llevan **marcadores** en vez de la dirección y de los
identificadores de las credenciales: `scripts/marcadores_n8n.py` los
sustituye por los valores de `n8n/valores.local.json` (que no se versiona;
`n8n/valores.ejemplo.json` dice qué claves lleva) antes de importarlos, y los
vuelve a poner antes de versionar un export. El procedimiento, en
[`sp3-operacion.md`](sp3-operacion.md), §7.

## 4. Dónde corre cada cosa

El mismo paquete se ejecuta en dos sitios, y la división no es negociable:

| | Máquina local | Colab / Kaggle |
| :--- | :--- | :--- |
| **Tiene GPU** | No (`torch...+cpu`) | Sí |
| Desarrollo y pruebas | Sí | — |
| Entrenamiento de humo (2 épocas, datos sintéticos) | Sí | — |
| Preparación de datos (26 684 DICOM) | Sí (`--crudo`, ~25 min) | Sí, el conjunto completo |
| **Entrenamiento real** | Sí, pero caro (`scripts/entrenar_local.py`, o `python -m src.train`) | Sí, en horas |

El entrenamiento local **es posible y está soportado**, no es lo preferente.
Medido en una CPU de 20 hilos lógicos (10 de cómputo), para 4 + 20 épocas:
DenseNet121 a 320 px cuesta **24,9 h**, EfficientNet-B0 a 320 px **10,8 h** y
MobileNetV3 a 224 px **3,1 h** (las 24 épocas completas: la corrida 6, la desplegada, paró a
las 11 por la parada temprana y costó ≈ 5,3 h); la carga de imágenes no es el cuello de botella
(268 img/s con 8 procesos). Con GPU son horas. Por eso la ruta preferente sigue
siendo Colab o Kaggle, y `scripts/entrenar_local.py` existe para cuando la
cuota de GPU se agota: es reanudable justamente porque son corridas de una
noche. El notebook **instala el paquete**
(no lo pega a `sys.path`), de modo que los pines de `pyproject.toml` también se
aplican en Colab, y luego comprueba el entorno: si no hay GPU, o si
`copiloto_triaje` no viene del paquete instalado, se detiene.

## 5. Reproducir desde cero

1. **Local:** instalar y pasar las pruebas (`pytest -v`). Opcionalmente, verificar
   el script de preparación sobre una muestra:
   `C:\venv-copiloto\Scripts\python.exe scripts/preparar_datos.py --zip <zip> --raiz <dir> --limite 200`
   (o `python -m src.data_processing`, que lo llama; [`data/README.md`](../data/README.md)).
2. **Colab o Kaggle:** abrir `notebooks/entrenar_gpu.ipynb` y ejecutar las celdas
   en orden. El notebook descarga el dataset desde Kaggle por sí mismo, prepara
   los datos y entrena con GPU. En Drive quedan los checkpoints y los
   entregables: `reporte_metricas.md`, `reporte_metricas.json`, `curva_roc.svg`
   y `pesos_modelo_cpu.pt` (el `state_dict` limpio, en CPU, que consumirá SP2).
   En Kaggle, el cuaderno es `notebooks/03_modelado.ipynb` (el antiguo
   `entrenar_kaggle.ipynb`), que corre allí con GPU.
3. Requisito previo para el paso 2: cuenta de Kaggle con las reglas de la
   competencia aceptadas, y los secretos `KAGGLE_USERNAME` y `KAGGLE_KEY`
   configurados en Colab.
4. **Si Colab se cae a mitad del entrenamiento:** volver a ejecutar el notebook
   con `REANUDAR = True` (el valor por defecto). Como los checkpoints están en
   Drive, `entrenar` retoma desde `ultimo.pt` —pesos, optimizador, época, fase,
   historial y contadores— en vez de empezar de cero.
5. **Las métricas y las figuras de `results/`:** `python -m src.evaluate`, desde las
   puntuaciones congeladas de prueba ([`results/README.md`](../results/README.md)).

Los pesos del modelo desplegado no se reentrenan para usar el sistema: se descargan y se
comprueban con su SHA-256 ([`models/README.md`](../models/README.md)).

## 6. Pruebas

```
C:\venv-copiloto\Scripts\python.exe -m pytest -v
```

(o `python -m pytest` en cualquier entorno con `requirements.txt` instalado.)

Las dos pruebas más importantes son las que protegen la ausencia de fuga de
datos: `tests/test_particion.py` verifica la lógica de partición, y
`tests/test_manifiestos_emitidos.py` ejecuta el script de preparación de punta a
punta y comprueba la propiedad **sobre los tres CSV que quedan en disco**, que
son los que alimentan al Dataset. Si alguna falla, las métricas no significan
nada.

Las de la capa del curso son `tests/test_data_processing.py`, `tests/test_model.py` y
`tests/test_app.py` (con `tests/test_app_ejemplos.py` y `tests/test_app_metricas.py`), y
`tests/test_estructura_curso.py` comprueba que la estructura de carpetas que pide el curso
existe y que los enlaces del README y de `docs/` llevan a ficheros que existen.

### La imagen Linux de pruebas

Lo que importa torch o scikit-learn se prueba en una imagen Linux con las dependencias de
`requirements.txt` (sección 2), con el repositorio montado en `/repo` y, si se tienen, los
datos preparados en solo lectura (desde Git Bash, con `MSYS_NO_PATHCONV=1`):

```
docker run --rm -v "<ruta del repositorio>:/repo" -v "<RSNA_RAIZ>:/datos:ro" -e RSNA_RAIZ=/datos copiloto-pruebas:linux python -m pytest -q -p no:cacheprovider
```

La suite entera tarda unos minutos. La imagen no tiene Docker: las pruebas que lo necesitan
(`tests/test_servidor_docker.py`, `tests/test_app_docker.py`, `tests/test_esquema_bd.py`, que
levanta una PostgreSQL desechable) se corren en la máquina que lo tiene, por ejemplo:

```
C:\venv-copiloto\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_esquema_bd.py
```

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

El formulario de la sesión con el médico tiene la suya, `node
tests/formulario.mjs`: imprime cuántas comprobaciones pasaron (`16 OK`) y
sale 0, o se detiene en la primera que falla y sale 1.

### Las que se saltan, y qué se queda sin comprobar

Varias pruebas necesitan algo que no está siempre: el dataset (`RSNA_RAIZ`),
la dirección de n8n (`N8N_URL`), el contenedor del copiloto, una Postgres
desechable, el túnel a la base del VPS, los secretos de Telegram o la imagen
Docker de la interfaz (`copiloto-app`, que no construyen las pruebas: ver la
[sección 9](#9-la-aplicación-de-demostración-en-detalle)).
**Se saltan en vez de fallar**, con el motivo escrito y el comando para
levantarlo, porque un `ConnectionRefusedError` repetido enseña a no mirar los
fallos. El precio es que **un skip se ve verde**:

```
C:\venv-copiloto\Scripts\python.exe -m pytest -q -rs
```

`-rs` lista cada salto con lo que deja sin verificar. Conviene correrlo antes de decir
que la suite está en verde.

Entre ellas, `tests/test_sql_de_los_nodos.py` llama a los dos arneses de
`pruebas/verificar_sql_*.py`, que son los **únicos** que comprueban la semántica
SQL de los nodos: la lista blanca, el borrado de sesión, los tipos del `jsonb`,
la copia de síntomas a `consultas` y la idempotencia del doble toque. Antes
vivían fuera de `testpaths` y no los nombraba nadie: nueve de nueve mutaciones a
esas consultas dejaban la suite entera en verde.

### El anonimato

`tests/test_anonimato.py` y `scripts/verificar_anonimato.py` vigilan que el repositorio no
lleve nada que identifique al cliente, a la infraestructura o a personas, ni secretos; los
nombres del equipo y de la tutora solo pueden aparecer en `README.md`, `LICENSE` y
`docs/planificacion.md`. Cómo funcionan y qué no protegen, en
[`tests/anonimato/README.md`](../tests/anonimato/README.md).

## 7. Las tablas derivadas del dataset

Datos del dataset verificados el 16-sep-2026: 26 684 imágenes de entrenamiento, una por
paciente. 6 012 positivos (22,5%), 11 821 anormales sin opacidad (44,3%), 8 851 normales
(33,2%). El desbalance se maneja con partición estratificada, ponderación de clases y
selección del umbral sobre la curva ROC de validación.

En el repositorio de desarrollo viajan dos tablas derivadas de ese dataset, sin imágenes:
`docs/eda/metadatos_eda.csv` (identificador público, edad, sexo, proyección y
etiqueta de cada placa, con los que se hizo el análisis exploratorio) y
`docs/validacion-semisintetica/crudas_prueba.csv` (la puntuación del modelo
sobre las placas del conjunto de prueba). Las imágenes no viajan: se descargan
de la competición, con sus reglas aceptadas. Del conjunto, lo que se publica son agregados.

**Decisión del equipo (5-oct-2026): ninguna de las dos tablas va al repositorio público**, que se
publica más tarde y es el que describen el `README.md` y los documentos del curso. Se quedan en el
de desarrollo, que es privado. Sin ellas, lo que las necesita lo dice y se detiene en vez de
inventarlas (`src/evaluate.py`, la validación semisintética), y lo ya calculado queda en
agregados (`results/`, `app/assets/metricas.json`, las figuras y las salidas de los notebooks).
`metadatos_eda.csv` se regenera con `scripts/extraer_metadatos.py` desde los DICOM que cada uno
descarga; `crudas_prueba.csv`, con los pesos y las placas de prueba (`pruebas/puntuaciones.py`).
Qué no está en el repositorio y por qué, en [`data/README.md`](../data/README.md).

## 8. El servidor (SP2)

`servidor/` contiene el Dockerfile y el compose. El contenedor **no publica
puertos**: se une a la red interna donde ya vive n8n, y ahí lo llaman por su
nombre. Esa es la garantía de que la radiografía no sale del VPS **desde n8n en
adelante**.

> **Corregido el 26-sep, a raíz de una evaluación externa.** Esta frase decía
> que el compose es «la garantía de que la radiografía no sale de la red local»,
> y así no se sostiene: el DICOM entra por Telegram. La garantía es real, pero
> cubre un tramo —n8n → copiloto—, no el recorrido completo; presentar el
> recorrido completo como consecuencia de que falte un `ports` es vender una
> privacidad que el sistema no tiene. El tramo de entrada está declarado como
> riesgo aceptado en el §5.5 del diseño de SP3.

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

Y **no evalúa la placa que vería mal o que no cabe en memoria**, decidiéndolo por
la cabecera antes de descodificar un solo píxel (SP5-B4): solo acepta placas como
las de RSNA —8 bits sin signo, `MONOCHROME2`, una muestra por píxel, un cuadro y
5 000 píxeles de lado como mucho— y rechaza también un DICOM comprimido entero
(«Deflated»), uno comprimido con una sintaxis que no sabe descomprimir (JPEG-LS,
por ejemplo), uno sin metainformación legible y uno recortado, sin la imagen. Sale
con `dicom_invalido`, y el bot dice «No pude leer esa radiografía.» y espera otro
fichero. La lista, en el §9 de [`sp2-despliegue.md`](sp2-despliegue.md).

Latencia medida dentro del contenedor con la CPU acotada a 2 núcleos: 38 ms por
REST y 43 ms por MCP, contra un presupuesto de 4 s.

Los pesos (16 MB) **no viajan en el repo**: están en `.gitignore` y se copian al
servidor por separado (de dónde se descargan y cómo se comprueban, en
[`models/README.md`](../models/README.md)). [`sp2-despliegue.md`](sp2-despliegue.md) tiene el
procedimiento completo, con los pre-chequeos de solo lectura y la vuelta atrás.

**Desde SP4 (H6)**, si con la placa llegan los cinco datos de la regla de
Heckerling —temperatura, pulso, crepitantes, murmullo y asma—, la respuesta
trae además un bloque `combinacion`: la probabilidad posterior de opacidad
compatible, calculada como `odds(PREVALENCIA_LOCAL) × RV clínica × RV imagen`.
Se entrega como **horquilla** entre el supuesto de independencia y el de
dependencia total cuando las dos evidencias apuntan al mismo lado, y como un
número —o, si no se sabe si hay asma, como la horquilla de las dos
puntuaciones posibles— cuando se contradicen. Sin esos datos, la respuesta es
la de siempre.
`PREVALENCIA_LOCAL` es obligatoria, como `AUC_VALIDACION`, y arranca en
`0.1466` (la cohorte de Heckerling). Diseño y cifras:
`docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md`.

## 9. La aplicación de demostración, en detalle

El README cuenta qué es la aplicación y cómo se arranca; el
[manual de usuario](manual_usuario.md), cómo se usa. Aquí, lo que hay que saber para
desplegarla y mantenerla.

`app/` es la **interfaz de usuario** del proyecto: una página web hecha con
Streamlit en la que cualquier persona prueba el modelo sin cuenta de Telegram,
sin estar en la lista blanca y sin pasar por el cuestionario del paciente. No es
otro sistema: es **la puerta de evaluación del mismo motor** que usa el bot del
profesional. Carga el mismo `Motor` (`src/copiloto_triaje/servicio/inferencia.py`),
con los mismos pesos, la misma calibración y la misma combinación con la regla de
Heckerling, y calcula en su propio proceso: no llama al servidor, a n8n ni a
Telegram, y la placa no sale de ese proceso. El producto sigue siendo el bot; esta
página es la forma de probarlo sin montar nada. Es una demostración académica, no
un producto sanitario, y no sirve para decidir sobre un paciente: la propia página
lo dice.

Qué hace:

- **Entrada con validación.** Un DICOM subido (hasta 5 MB, como el servidor) o uno de
  los cuatro ejemplos: la opción «Usar un ejemplo» los ofrece, y el botón «Prueba con
  ejemplo» calcula el elegido (también vale «Calcular»). Los cinco hallazgos de la regla
  de Heckerling, opcionales en bloque y con límites de interfaz; y un interruptor
  «Umbral por vista (experimental)», apagado por defecto.
- **Indicador de carga y errores en lenguaje llano.** Lo que no se puede evaluar sale
  dicho a una persona y con lo que puede hacer, nunca como una traza: un fichero que
  no es un DICOM o no se puede leer, una edad desconocida o fuera de los 18-100
  años, unos hallazgos inválidos y, mirando solo la cabecera y antes de descodificar
  un solo píxel, las placas que el modelo vería mal (que no son de 8 bits, con la
  escala de grises invertida —MONOCHROME1— o en color, de más de 5 000 píxeles de
  lado, con varios cuadros) y un DICOM comprimido entero («Deflated»), que la página
  no abre.
- **El resultado**, en los bloques del informe del bot —cribado, evidencia de la
  imagen, clínica y combinado—, con la puntuación frente al umbral y la horquilla
  en gráficos, y el **mapa de calor** sobre la placa (Grad-CAM), con su
  advertencia: señala dónde mira el modelo, no por qué acierta ni dónde está una
  lesión.
- **El historial de la sesión**, que se descarga en CSV sin la imagen ni nada de la
  cabecera del DICOM.
- **«Acerca de»**: el modelo, los datos (con sus referencias), las métricas por
  subgrupo con sus intervalos, las limitaciones, el precio del umbral por vista y
  la licencia de los ejemplos.

### La orden de Docker, y lo que hay que saber

Desde la raíz del repositorio:

```
docker build -t copiloto-app -f app/Dockerfile .
docker run --rm -p 127.0.0.1:8501:8501 --memory=2g --memory-swap=2g copiloto-app
```

y se abre `http://127.0.0.1:8501`.

- **`127.0.0.1:` delante del puerto, siempre.** Sin él, Docker publica el 8501 en
  todas las interfaces de la máquina, y la página no pide ninguna contraseña.
- **Con un límite de memoria, siempre** (`--memory=2g --memory-swap=2g`): es la red
  de debajo. La página rechaza por la cabecera, antes de descodificar un solo píxel,
  lo que declara unas dimensiones desmesuradas —es la regla del motor, la misma que
  aplica el servidor desde SP5-B4: sin ella, un DICOM de cientos de bytes que declara
  60 000 × 60 000 hacía reservar 3,4 GiB—, y si algo se le escapara, con el límite lo
  que muere es el contenedor y no la máquina. `--memory-swap` igual a `--memory`,
  porque sin él Docker deja usar otro tanto de swap. La página usa menos de 500 MiB
  tras los cuatro ejemplos y el mapa de calor (`docker stats`): 2 GB, los del
  servidor, son margen de sobra.
- **La construcción tiene que correr desde la raíz**: es su contexto.
  `app/Dockerfile.dockerignore` es una lista blanca que deja fuera de él todo lo que
  la imagen no copia (`.git`, `pruebas/`, `docs/`, `tests/`, los `.env`…) y, de
  `app/`, todo lo que la página no lee. Ese fichero, el de un Dockerfile concreto, lo
  lee BuildKit (por defecto desde Docker 23): con el constructor antiguo se ignora y
  el repositorio entero viaja al demonio.
- **La imagen pesa**: torch en CPU y sus dependencias, 2,5 GB en disco. La primera
  construcción las descarga y tarda unos minutos. Para una demostración es
  aceptable. Una vez construida no necesita red: ni para cargar el modelo ni para
  arrancar.
- **La primera página que se abre carga el modelo** (unos segundos, con su
  indicador); a partir de ahí cada cálculo tarda décimas de segundo en CPU.
- **Corre sin privilegios, sin telemetría y sin llamar a nadie al arrancar.**
  Streamlit manda estadísticas de uso por defecto, y en modo `headless` pregunta a
  un servicio de fuera cuál es la IP pública de la máquina; la imagen apaga las dos
  cosas, y una prueba vigila que no vuelvan (`tests/test_app_docker.py`).
- **Las cifras del despliegue** —`UMBRAL`, `AUC_VALIDACION` y
  `PREVALENCIA_LOCAL`— se fijan en la imagen con los mismos valores que el
  `docker-compose.yml` del servidor (con la fuente de cada una en los comentarios
  de ese fichero), y la página los enseña en «Acerca de». Se pueden cambiar al
  arrancar con `-e`. `AUC_VALIDACION` y `PREVALENCIA_LOCAL` no tienen valor por
  defecto en el código, como en el servidor: sin ellas, la página no calcula y dice
  qué declarar.
- El despliegue público no forma parte de esto: se decide después.

### Sin Docker

Se instala desde la raíz y se lanza desde `app/`, con las dos
variables que no tienen valor por defecto, `AUC_VALIDACION` y `PREVALENCIA_LOCAL`
(en bash):

```
pip install -r app/requirements.txt
pip install --no-deps .
cd app
AUC_VALIDACION=0.8827 PREVALENCIA_LOCAL=0.1466 streamlit run app.py
```

En PowerShell, la última línea es:

```
$env:AUC_VALIDACION = "0.8827"; $env:PREVALENCIA_LOCAL = "0.1466"; streamlit run app.py
```

Esos dos valores son los de `servidor/docker-compose.yml`, los mismos que fija la
imagen. Las demás variables tienen valor por defecto: `UMBRAL` (el de
`app/assets/metricas.json`, 0,4258), `RUTA_PESOS` (`servidor/pesos_modelo_cpu.pt`) y
`RUTA_CALIBRADOR` (`servidor/calibrador.json`). **Desde `app/` y no desde la raíz**:
Streamlit lee `.streamlit/config.toml` del directorio desde el que se lanza, y desde
la raíz no hay ninguno, así que se pierden en silencio la telemetría apagada, el
límite de subida de 5 MB del servidor y las trazas ocultas en el navegador. Docker es
lo reproducible: la calibración usa scikit-learn, que en algunas máquinas Windows no
carga.

### De dónde salen los pesos

Los pesos (16 MB) **no viajan en el repo**: están en `.gitignore`, igual que para
el servidor, y se copian por separado. `docker build` los toma de
`servidor/pesos_modelo_cpu.pt`, los mismos que usa el servidor; salen del
entrenamiento (`notebooks/entrenar_gpu.ipynb` los deja como `pesos_modelo_cpu.pt`:
ver la [sección 5](#5-reproducir-desde-cero)) y se publican como descarga
([`models/README.md`](../models/README.md)). Sin ese fichero, la construcción se detiene en su
`COPY` y no deja ninguna imagen. Las métricas de «Acerca de» son las de **esos**
pesos: `app/assets/metricas.json` lleva el SHA-256 de los que se midieron, y la
página avisa si los cargados son otros o si el umbral no es aquel con el que se
midieron.

### Los ejemplos

«Usar un ejemplo» ofrece cuatro: una radiografía normal en PA, una con opacidad
en PA, una con opacidad en AP y el «rechazado», que es la normal con una edad de 15
años (inventada) para ver cómo el sistema se niega a evaluar lo que no puede.

**Son de otra fuente.** Las tres radiografías son de Wikimedia Commons, con
licencia CC0, de fuera de RSNA y del NIH, empaquetadas como DICOM; la fuente, la
licencia y la atribución de cada una están en
[`app/assets/LICENCIAS.md`](../app/assets/LICENCIAS.md). El modelo
se entrenó y se evaluó con RSNA y **no se ha medido con ellas**: lo que den no dice
nada de su rendimiento y puede discrepar de lo que dice su fuente (con los pesos de
esta entrega, la placa «normal» sale marcada por el cribado, y la propia página
avisa de que la imagen no apoya ese resultado). Sirven para ver cómo funciona la
página, no para evaluarla. La app no lleva ninguna imagen de RSNA ni del NIH, ni
ninguna fila por paciente: sus métricas son agregados (`app/assets/metricas.json`).

### Qué hay en `app/`

| Ruta | Qué es |
| :--- | :--- |
| `app/app.py` | La interfaz: una sola página de Streamlit con tres pestañas, «Probar el modelo», «Historial de la sesión» y «Acerca de» |
| `app/requirements.txt` | Sus dependencias, con la versión exacta: las del proyecto y las nuevas de la página |
| `app/Dockerfile` | La imagen: la base del servidor (la misma, por su digest), torch en CPU, y los pesos y el calibrador dentro |
| `app/Dockerfile.dockerignore` | Lo que entra al contexto de la construcción, en lista blanca y de `app/` por rutas: solo lo que la página lee. Se llama así y no `.dockerignore` porque el contexto es la raíz del repositorio, y Docker ignoraría en silencio un `app/.dockerignore` |
| `app/.streamlit/config.toml` | La configuración de Streamlit: límite de subida de 5 MB, sin telemetría, sin trazas en el navegador. Streamlit la lee del directorio desde el que se lanza, y la imagen lo lanza desde `app/` |
| `app/assets/ejemplos/` | Los cuatro DICOM de «Usar un ejemplo» |
| `app/assets/originales/` | Las tres radiografías reducidas (PNG) de las que salen. Sirven para rehacer los ejemplos; no entran a la imagen |
| `app/assets/metricas.json` | Las métricas de «Acerca de», en agregados, con la huella de los pesos y de las puntuaciones de las que salen |
| `app/assets/LICENCIAS.md` | Fuente, autor, licencia y atribución de cada ejemplo |
| `app/empaquetar_ejemplos.py` | Guion: empaqueta los PNG originales como los DICOM de ejemplo, con los mismos bytes cada vez |
| `app/generar_metricas.py` | Guion: calcula `metricas.json` desde las puntuaciones congeladas de prueba (las de cada placa no viajan al repositorio público) |

Las capturas del README y del manual están en `docs/interfaz/`. Se hicieron con la imagen
construida y los pesos de verdad, y cada una se miró antes de declararla
([`tests/anonimato/README.md`](../tests/anonimato/README.md)).

### Pruebas de la interfaz

La página se prueba con `streamlit.testing.v1.AppTest` (`tests/test_app.py`,
`tests/test_app_ejemplos.py` y `tests/test_app_metricas.py`), que corren en la imagen
Linux de pruebas. La imagen tiene la suya, `tests/test_app_docker.py`: comprueba lo
que dicen el Dockerfile y el README, qué contexto de construcción llega al demonio, y
arranca contenedores de verdad (publicados solo en `127.0.0.1`, o sin red, y con el
límite de memoria de la orden de arriba) para ver que la página responde, que no llama
a nadie al arrancar y que la app corre con los pesos de la imagen. **No construye la
imagen**: usa `copiloto-app` si está, y comprueba que es de este árbol (si no lo es,
falla y dice cómo reconstruirla); si no hay Docker o no está construida, se salta
diciendo por qué y con la orden de construirla.

```
C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_app_docker.py -rs
```

## 10. Documentos de diseño

| Sub-proyecto | Diseño | Plan |
| :--- | :--- | :--- |
| SP1 — núcleo de imagen | [diseño](superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md) | [plan](superpowers/plans/2026-09-16-sp1-nucleo-imagen.md) |
| SP2 — servidor MCP | [diseño](superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md) | [plan](superpowers/plans/2026-09-23-sp2-servidor-mcp.md) |
| SP3 — bots de n8n | [diseño](superpowers/specs/2026-09-24-sp3-bot-n8n-design.md) | [plan](superpowers/plans/2026-09-24-sp3-bot-n8n.md) |
| SP4 — combinación bayesiana | [diseño](superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md) | [plan](superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md) |
| SP5 — validación y cierre | [diseño](superpowers/specs/2026-09-27-sp5-validacion-y-cierre-design.md) | planes de [SP5-A](superpowers/plans/2026-09-28-sp5a-generador-y-sesion.md), [SP5-B1](superpowers/plans/2026-09-28-sp5b1-metricas-y-documento.md), [SP5-B2](superpowers/plans/2026-09-29-sp5b2-anonimizacion.md) y [SP5-B3](superpowers/plans/2026-10-05-sp5b3-residuos-del-acta.md) |
| SP5-C1 — interfaz y umbral por vista | [diseño](superpowers/specs/2026-10-05-sp5c1-interfaz-y-umbral-por-vista-design.md) | [plan](superpowers/plans/2026-10-05-sp5c1-interfaz-y-umbral-por-vista.md) |
| SP5-C2 — estructura y documentación del curso | [diseño](superpowers/specs/2026-10-15-sp5c2-estructura-y-documentacion-design.md) | — |

Y además:

- Despliegue: [`sp2-despliegue.md`](sp2-despliegue.md)
- Operación: [`sp3-operacion.md`](sp3-operacion.md)
- Procedimiento de la sesión con el médico: [`sp5-sesion.md`](sp5-sesion.md)
- Anonimato del repositorio: [`tests/anonimato/README.md`](../tests/anonimato/README.md)
- Comparativa de arquitecturas: [`comparativa-corridas.md`](comparativa-corridas.md)
- Frontera recall/especificidad: [`frontera-recall-especificidad.md`](frontera-recall-especificidad.md)
- Mejoras tras la primera corrida: [`mejoras-2026-09-21.md`](mejoras-2026-09-21.md)
