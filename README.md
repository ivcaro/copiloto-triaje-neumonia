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
desechable, el túnel a la base del VPS o los secretos de Telegram.
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

## Documentos

- Diseño SP1: `docs/superpowers/specs/2026-09-16-sp1-nucleo-imagen-design.md`
- Plan SP1: `docs/superpowers/plans/2026-09-16-sp1-nucleo-imagen.md`
- Diseño SP2: `docs/superpowers/specs/2026-09-23-sp2-servidor-mcp-design.md`
- Plan SP2: `docs/superpowers/plans/2026-09-23-sp2-servidor-mcp.md`
- Diseño SP4: `docs/superpowers/specs/2026-09-26-sp4-combinacion-bayesiana-design.md`
- Plan SP4: `docs/superpowers/plans/2026-09-26-sp4-combinacion-bayesiana.md`
- Despliegue: `docs/sp2-despliegue.md`
- Operación: `docs/sp3-operacion.md`
- Anonimato del repositorio: `tests/anonimato/README.md`
- Comparativa de arquitecturas: `docs/comparativa-corridas.md`
- Frontera recall/especificidad: `docs/frontera-recall-especificidad.md`
