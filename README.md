# Copiloto de triaje para neumonía en adultos

Proyecto Integrador (UEES, Maestría en IA). Sub-proyectos:

- **SP1 — núcleo de imagen.** Entrena una CNN de clasificación binaria sobre
  radiografías de tórax de adultos del dataset RSNA, con partición por paciente
  verificada sin fuga de datos.
- **SP2 — servidor.** Sirve esa CNN en Docker por dos puertas —una herramienta
  MCP y un `POST /inferir` de respaldo— para que n8n la consulte **sin que la
  imagen salga del VPS en ese paso**: el contenedor no publica puertos. Antes de
  llegar ahí el DICOM viaja **por Telegram**, que no es infraestructura nuestra;
  es un riesgo declarado, no una omisión (§5.5 del diseño de SP3). Ver
  `docs/sp2-despliegue.md`.
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
- **SP5-C1 — interfaz de usuario.** Una página web (Streamlit) con la que
  cualquier persona prueba el mismo motor que usa el bot, sin cuenta de
  Telegram: `app/`, en Docker, con ejemplos precargados, el mapa de calor de la
  placa y una sección «Acerca de». Ver «Interfaz de usuario».

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

## Variables de entorno

Ningún valor que identifique una instalación está escrito en el repositorio:
se pasa por el entorno. Sin ellas, lo que las necesita se detiene con un
mensaje o, en la suite, se salta diciendo qué se queda sin verificar.

| Variable | Quién la necesita | Qué es |
| :--- | :--- | :--- |
| `RSNA_RAIZ` | `scripts/preparar_sesion.py`, `pruebas/seleccionar_casos.py`, `pruebas/reproducir_casos.py` (con bots y sin ellos), `pruebas/puntuaciones.py` y `pruebas/caracterizar_conjunto.py` (estos dos, solo si no hay caché) y las pruebas que leen placas | la raíz del dataset preparado (`crudo/`, `png/`, `manifiestos/`) |
| `N8N_URL` | `pruebas/reproducir_casos.py` con bots, `pruebas/verificar_webhooks.py` y las pruebas conducidas | la dirección base de n8n, p. ej. `https://n8n.ejemplo.test` |
| `RED_N8N` | `servidor/docker-compose.yml` (se declara en `servidor/.env`) | el nombre de la red externa de Docker que comparte n8n; obligatoria |
| `COPILOTO_URL`, `COPILOTO_BD_DSN`, `TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`, `CHAT_SUBIDA_PLACAS` | el arnés y las pruebas conducidas | las describe la cabecera de `pruebas/reproducir_casos.py`. Ojo: `COPILOTO_URL` no quiere el mismo valor en el arnés y en las pruebas de contrato (`docs/sp3-operacion.md`, §2) |
| `ANONIMATO_LISTA` | solo quien mantiene la lista de lo que no se publica, para regenerar las huellas | la ruta de esa lista, que vive fuera del repositorio (`tests/anonimato/README.md`) |

Los workflows de `n8n/` llevan **marcadores** en vez de la dirección y de los
identificadores de las credenciales: `scripts/marcadores_n8n.py` los
sustituye por los valores de `n8n/valores.local.json` (que no se versiona;
`n8n/valores.ejemplo.json` dice qué claves lleva) antes de importarlos, y los
vuelve a poner antes de versionar un export. El procedimiento, en
`docs/sp3-operacion.md`, §7.

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

El formulario de la sesión con el médico tiene la suya, `node
tests/formulario.mjs`: imprime cuántas comprobaciones pasaron (`16 OK`) y
sale 0, o se detiene en la primera que falla y sale 1.

### Las que se saltan, y qué se queda sin comprobar

Varias pruebas necesitan algo que no está siempre: el dataset (`RSNA_RAIZ`),
la dirección de n8n (`N8N_URL`), el contenedor del copiloto, una Postgres
desechable, el túnel a la base del VPS, los secretos de Telegram o la imagen
Docker de la interfaz (`copiloto-app`, que no construyen las pruebas: ver
«Interfaz de usuario»).
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

En el repositorio viajan dos tablas derivadas de ese dataset, sin imágenes:
`docs/eda/metadatos_eda.csv` (identificador público, edad, sexo, proyección y
etiqueta de cada placa, con los que se hizo el análisis exploratorio) y
`docs/validacion-semisintetica/crudas_prueba.csv` (la puntuación del modelo
sobre las placas del conjunto de prueba). Las imágenes no viajan: se descargan
de la competición, con sus reglas aceptadas.

## El servidor (SP2)

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

Latencia medida dentro del contenedor con la CPU acotada a 2 núcleos: 38 ms por
REST y 43 ms por MCP, contra un presupuesto de 4 s.

Los pesos (16 MB) **no viajan en el repo**: están en `.gitignore` y se copian al
servidor por separado. `docs/sp2-despliegue.md` tiene el procedimiento completo,
con los pre-chequeos de solo lectura y la vuelta atrás.

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

## Interfaz de usuario

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

- **Entrada con validación.** Un DICOM subido (hasta 5 MB, como el servidor) o uno
  de los cuatro ejemplos: la opción «Usar un ejemplo» los ofrece, y el botón
  «Prueba con ejemplo» calcula el elegido (también vale «Calcular»). Los cinco
  hallazgos de la regla de Heckerling, opcionales en bloque y con límites de
  interfaz; y un interruptor «Umbral por vista (experimental)», apagado por
  defecto.
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

![La pestaña «Probar el modelo» con «Usar un ejemplo», el ejemplo «Neumonía, PA» y los cinco hallazgos: el resultado en bloques y el mapa de calor sobre la placa](docs/interfaz/probar-con-ejemplo.png)

![El ejemplo «Rechazado: menor de edad»: el motor se niega a evaluar una placa con una edad fuera de 18-100 años y la página lo dice en lenguaje llano](docs/interfaz/rechazado.png)

![La pestaña «Acerca de»: qué hace y qué no, y el modelo con su regla de Heckerling](docs/interfaz/acerca-de-modelo.png)

![«Acerca de»: las métricas por subgrupo con sus intervalos, y las limitaciones](docs/interfaz/acerca-de-metricas.png)

### Cómo se ejecuta

Desde la raíz del repositorio, con Docker:

```
docker build -t copiloto-app -f app/Dockerfile .
docker run --rm -p 127.0.0.1:8501:8501 --memory=2g --memory-swap=2g copiloto-app
```

y se abre `http://127.0.0.1:8501`. Lo que hay que saber:

- **`127.0.0.1:` delante del puerto, siempre.** Sin él, Docker publica el 8501 en
  todas las interfaces de la máquina, y la página no pide ninguna contraseña.
- **Con un límite de memoria, siempre** (`--memory=2g --memory-swap=2g`): es la red
  de debajo. La página rechaza por la cabecera, antes de descodificar un solo píxel,
  lo que declara unas dimensiones desmesuradas, pero el motor y el servidor siguen sin
  esa guarda: con el lector del motor, un DICOM de cientos de bytes que declara
  60 000 × 60 000 hace reservar 3,4 GiB, y con el límite lo que muere es el contenedor
  y no la máquina. `--memory-swap` igual a `--memory`, porque sin él Docker deja usar
  otro tanto de swap. La página usa menos de 500 MiB tras los cuatro ejemplos y el mapa
  de calor (`docker stats`): 2 GB, los del servidor, son margen de sobra.
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

**Sin Docker**, se instala desde la raíz y se lanza desde `app/`:

```
pip install -r app/requirements.txt
pip install --no-deps .
cd app
streamlit run app.py
```

con las variables de entorno que dice la cabecera de `app/app.py`. **Desde `app/` y
no desde la raíz**: Streamlit lee `.streamlit/config.toml` del directorio desde el
que se lanza, y desde la raíz no hay ninguno, así que se pierden en silencio la
telemetría apagada, el límite de subida de 5 MB del servidor y las trazas ocultas en
el navegador. Docker es lo reproducible: la calibración usa scikit-learn, que en
algunas máquinas Windows no carga.

### De dónde salen los pesos

Los pesos (16 MB) **no viajan en el repo**: están en `.gitignore`, igual que para
el servidor, y se copian por separado. `docker build` los toma de
`servidor/pesos_modelo_cpu.pt`, los mismos que usa el servidor; salen del
entrenamiento (`notebooks/entrenar_gpu.ipynb` los deja como `pesos_modelo_cpu.pt`:
ver «Reproducir desde cero»). Sin ese fichero, la construcción se detiene en su
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
licencia y la atribución de cada una están en `app/assets/LICENCIAS.md`. El modelo
se entrenó y se evaluó con RSNA y **no se ha medido con ellas**: lo que den no dice
nada de su rendimiento y puede discrepar de lo que dice su fuente (con los pesos de
esta entrega, la placa «normal» sale marcada por el cribado, y la propia página
avisa de que la imagen no apoya ese resultado). Sirven para ver cómo funciona la
página, no para evaluarla. El repositorio no lleva ninguna imagen de RSNA ni del
NIH, ni ninguna fila por paciente: las métricas son agregados.

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

Las capturas de arriba están en `docs/interfaz/`. Se hicieron con la imagen
construida y los pesos de verdad, y cada una se miró antes de declararla
(`tests/anonimato/README.md`).

### Pruebas de la interfaz

La página se prueba con `streamlit.testing.v1.AppTest` (`tests/test_app.py`,
`tests/test_app_ejemplos.py` y `tests/test_app_metricas.py`), que corren en la imagen
Linux de pruebas. La imagen tiene la suya, `tests/test_app_docker.py`: comprueba lo
que dicen el Dockerfile y este README, qué contexto de construcción llega al demonio, y
arranca contenedores de verdad (publicados solo en `127.0.0.1`, o sin red, y con el
límite de memoria de la orden de arriba) para ver que la página responde, que no llama
a nadie al arrancar y que la app corre con los pesos de la imagen. **No construye la
imagen**: usa `copiloto-app` si está, y comprueba que es de este árbol (si no lo es,
falla y dice cómo reconstruirla); si no hay Docker o no está construida, se salta
diciendo por qué y con la orden de construirla.

```
C:\venv-copiloto\Scripts\python.exe -m pytest tests/test_app_docker.py -rs
```

## Documentos

- Diseño SP1: `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`
- Plan SP1: `docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md`
- Diseño SP2: `docs/superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md`
- Plan SP2: `docs/superpowers/plans/2026-09-23-sp2-servidor-mcp.md`
- Diseño SP4: `docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md`
- Plan SP4: `docs/superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md`
- Diseño SP5-C1: `docs/superpowers/specs/2026-10-05-sp5c1-interfaz-y-umbral-por-vista-design.md`
- Plan SP5-C1: `docs/superpowers/plans/2026-10-05-sp5c1-interfaz-y-umbral-por-vista.md`
- Despliegue: `docs/sp2-despliegue.md`
- Operación: `docs/sp3-operacion.md`
- Anonimato del repositorio: `tests/anonimato/README.md`
- Comparativa de arquitecturas: `docs/comparativa-corridas.md`
- Frontera recall/especificidad: `docs/frontera-recall-especificidad.md`
