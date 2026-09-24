# SP2 — Servidor MCP: diseño

**Fecha:** 23 de septiembre de 2026
**Hito:** H4 — Servidor MCP operativo en el VPS (30 de septiembre, Sprint 2)
**Depende de:** SP1 (núcleo de imagen), cerrado el 23-sep-2026
**Bloquea a:** SP3 (bot de Telegram + n8n), SP4 (combinación bayesiana)

---

## 1. Contexto

SP1 dejó un modelo entrenado y verificado: **EfficientNet-B0 a 320 px con
ajuste fino completo**, con recall 0,882, especificidad 0,702 y AUC 0,885 sobre
el conjunto de prueba, y pesos de 16 MB que cargan en CPU con
`weights_only=True`. La inferencia mide **0,022 s por imagen**, 181 veces por
debajo del presupuesto de 4 s.

Ese modelo hoy solo se puede invocar desde un script. SP2 lo convierte en un
servicio que n8n pueda llamar, sin que la radiografía salga de la red local.

## 2. Objetivo y criterios de aceptación

Servir la CNN como herramienta MCP desde un contenedor Docker, con endpoint
REST de respaldo, desplegable en el VPS y consumible desde n8n.

Los criterios son los que el documento maestro comprometió para H4, más dos que
añade este diseño:

1. Caso de prueba de extremo a extremo desde n8n con una imagen de test.
2. Latencia de inferencia en CPU **medida y registrada** (objetivo parcial:
   < 4 s del total de 8 s del sistema).
3. Despliegue reproducible con `docker-compose up` desde cero, verificable por
   el otro integrante sin conocimiento previo del código.
4. **(Añadido)** La puerta MCP y la puerta REST devuelven resultados idénticos
   para la misma entrada, comprobado por una prueba.
5. **(Añadido)** El servidor rechaza por sí mismo las radiografías fuera del
   rango de edad para el que el modelo es válido.

## 3. Alcance

**Dentro:** carga del modelo, lectura de DICOM, preprocesamiento idéntico al de
entrenamiento, inferencia, calibración, filtro de edad, las dos puertas
(MCP y REST), el contenedor y su compose, y las pruebas.

**Fuera, y por qué:**

- **Grad-CAM** → SP5. Los documentos lo prometen como mitigación del riesgo de
  caja negra, pero el mapa de calor solo tiene valor cuando un médico lo mira y
  dice si le sirve, y eso ocurre en la validación clínica. Adelantarlo ahora
  complica la interfaz (hay que devolver una imagen) a cambio de nada
  verificable. **Queda anotado como deuda explícita.**
- **Autenticación entre contenedores** → la red interna de Docker ya aísla el
  servicio, que no publica ningún puerto. Añadir tokens sin un atacante en el
  modelo de amenaza es ceremonia.
- **Lotes, colas y reintentos** → con 31 ms por imagen no hay nada que
  orquestar.

## 4. Hechos verificados que condicionan el diseño

Medidos, no supuestos:

| Hecho | Valor | Consecuencia |
| :--- | :--- | :--- |
| Tamaño de los DICOM de RSNA | mediana 131 KB, máx. 185 KB | Caben en base64 (246 KB) dentro del mensaje: **no hace falta volumen compartido** |
| Latencia de inferencia en CPU | 0,022 s/imagen | Sobra margen; nada de colas ni lotes |
| Tamaño de los pesos | 16 MB | Caben dentro de la imagen Docker |
| Entrenamiento con `pos_weight` | 3,44 | La salida del modelo **no es una probabilidad calibrada** |
| Rango de edad del entrenamiento | 18-100 años | Fuera de ahí el modelo no es válido |
| Transformaciones de entrada | `Resize((320,320))` + normalización ImageNet, sin recorte | El preprocesamiento del servidor debe ser byte a byte el mismo |

## 5. Arquitectura

Un solo servicio en su propio `docker-compose.yml`, conectado como red
**externa** a la de n8n. No publica puertos: n8n lo alcanza por nombre de
servicio dentro de la red interna.

```
n8n  ──(red interna de Docker)──>  copiloto-mcp
                                    ├── puerta MCP  (HTTP)
                                    ├── puerta REST (multipart)
                                    └── núcleo de inferencia
```

Tres capas con una responsabilidad cada una:

| Capa | Dónde vive | Responsabilidad |
| :--- | :--- | :--- |
| **Núcleo** | `src/copiloto_triaje/servicio/inferencia.py` | bytes de DICOM → resultado. No sabe de HTTP, MCP ni Docker |
| **Puerta MCP** | `src/copiloto_triaje/servicio/mcp.py` | expone `clasificar_radiografia` sobre HTTP; DICOM en base64 |
| **Puerta REST** | `src/copiloto_triaje/servicio/rest.py` | `POST /inferir` multipart y `GET /salud` |

Las tres capas viven **dentro del paquete**, y en `servidor/` solo quedan los
artefactos de despliegue (Dockerfile y compose). La razón es la prueba de
equivalencia de §9: comparar lo que devuelven las dos puertas exige importarlas,
y desde una carpeta suelta fuera del paquete no se puede sin trucos de
`sys.path`. Las dos son envoltorios delgados sobre la misma función del núcleo,
que es lo único que impide que el respaldo REST y el camino MCP digan cosas
distintas sobre la misma radiografía.

## 6. El contrato

Herramienta MCP `clasificar_radiografia`. Entrada: el DICOM en base64.
Salida en caso correcto:

```json
{
  "probabilidad_cruda": 0.7412,
  "probabilidad_calibrada": 0.5187,
  "razon_de_verosimilitud": 3.84,
  "umbral": 0.4258,
  "clasificacion": "opacidad_probable",
  "edad_paciente": 54,
  "modelo": "efficientnet_b0_320px",
  "auc_validacion": 0.883,
  "milisegundos": 31
}
```

### 6.1 Por qué tres números y no uno

El modelo se entrenó con `BCEWithLogitsLoss(pos_weight=3.44)` para compensar el
22,15% de positivos. Eso desplaza su salida hacia arriba: **0,74 no significa
74% de probabilidad de neumonía.**

SP4 va a combinar la evidencia de imagen con la probabilidad previa de la regla
clínica mediante una fórmula bayesiana. Meter ahí la salida cruda produce un
posterior equivocado sin que nada falle de forma visible, que es la peor clase
de error.

- `probabilidad_cruda` — la salida del modelo, para trazabilidad y depuración.
- `probabilidad_calibrada` — ajustada sobre el conjunto de **validación** a la
  prevalencia del dataset (22,15%).
- `razon_de_verosimilitud` — **lo que SP4 debe consumir**. Se multiplica por las
  probabilidades a favor (*odds*) de la regla clínica y da el posterior
  correcto:
  `odds_posterior = odds_previo × razón_de_verosimilitud`.

El calibrador (regresión isotónica sobre validación) se ajusta **una sola vez**
con un script del repositorio y se guarda como `calibrador.json` —unos pocos
kilobytes de puntos de la curva, no un objeto serializado de scikit-learn— para
que sí se pueda versionar en Git, a diferencia de los pesos, que están
gitignorados por tamaño. El fichero registra con qué corrida se ajustó. La razón
de verosimilitud se deriva de la probabilidad calibrada y de la prevalencia:

`RV = [p/(1-p)] / [0.2215/(1-0.2215)]`

### 6.2 El umbral y la frontera

`umbral` y `clasificacion` se incluyen para que n8n pueda redactar en lenguaje
natural, pero **no son la salida principal**. SP1 midió que los dos objetivos
del proyecto no son alcanzables a la vez: no existe ningún punto con recall
≥0,85 y especificidad ≥0,75 (ver `docs/frontera-recall-especificidad.md`). El
umbral por defecto prioriza el recall, y el servidor lo declara en la respuesta
para que la elección quede registrada en cada inferencia, no escondida en el
código.

## 7. Manejo de errores

El servidor falla ruidosamente y con un motivo accionable. **Nunca devuelve un
número dudoso.**

Por MCP, los errores se lanzan como  del SDK y **no** como
: en MCP 2.x una excepción que no sea  se trata como un
fallo inesperado y **el SDK descarta su mensaje**, de modo que un paciente
fuera de rango, un base64 ilegible y un fichero corrupto llegarían al cliente
como el mismo texto. Verificado levantando el servidor y llamándolo con el
cliente oficial. El SDK antepone  al mensaje,
así que el código queda como **segundo** campo: quien lo consuma debe buscar el
código dentro del texto, no partir por el primer .

| Caso | Código | Detalle |
| :--- | :--- | :--- |
| El fichero no es un DICOM válido | `dicom_invalido` | incluye el motivo de pydicom |
| `PatientAge` fuera de 18-100 | `fuera_de_alcance` | incluye la edad leída |
| `PatientAge` ausente o ilegible | `edad_desconocida` | **no se asume adulto** |
| Payload > 5 MB | `payload_excesivo` | el transporte de MCP corta muy por encima como red de seguridad, pero el umbral del producto se comprueba sobre los bytes YA DECODIFICADOS, para que las dos puertas rechacen el mismo tamanio |
| base64 ilegible (solo MCP) | `base64_invalido` | antes de intentar leer el DICOM |
| El modelo no cargó | `/salud` responde no-listo | el healthcheck del contenedor falla |

`edad_desconocida` merece justificarse: dar por adulto a quien no declara edad
es exactamente el atajo que el filtro existe para evitar. Es preferible que n8n
pida la edad al profesional.

## 8. Despliegue

**Dockerfile** sobre `python:3.12-slim`. Trampa conocida: `pip install torch` a
secas descarga la compilación con CUDA, **2,5 GB para un servidor sin GPU**. Hay
que forzar el índice de ruedas CPU
(`--index-url https://download.pytorch.org/whl/cpu`), con lo que la imagen baja
a unos 800 MB.

**Los pesos van dentro de la imagen**, no montados: son 16 MB y así el
contenedor es autocontenido y se despliega en cualquier sitio sin arrastrar
ficheros aparte. Es lo que hace reproducible la prueba cruzada que H4 exige.

**`docker-compose.yml`** con la red de n8n declarada `external`, `healthcheck`
contra `/salud`, sin puertos publicados y con `deploy.resources.limits` para que
el modelo no agote el VPS.

## 9. Estrategia de pruebas

Cuatro niveles. El tercero es el que protege de verdad:

1. **Núcleo** — DICOM sintéticos, como ya hace `tests/test_dicom.py`. Rápido y
   sin Docker.
2. **Casos límite** — cada fila de la tabla de errores tiene su prueba.
3. **Equivalencia de las dos puertas** — el mismo DICOM por MCP y por REST debe
   dar **exactamente** el mismo resultado. Sin esta prueba el respaldo puede
   divergir del camino principal y nadie lo nota hasta que hace falta.
4. **Extremo a extremo con un DICOM real** del conjunto de prueba, midiendo y
   registrando la latencia, que es literalmente un criterio de aceptación.

Además, una prueba que fija que el preprocesamiento del servidor produce el
**mismo tensor** que el de entrenamiento: si divergen, el modelo se degrada en
producción sin que ninguna prueba falle.

## 10. Riesgos

| Riesgo | Mitigación |
| :--- | :--- |
| El preprocesamiento del servidor diverge del de entrenamiento | Prueba de igualdad de tensores (§9); el núcleo importa `construir_transformaciones` del paquete en vez de reimplementarla |
| La calibración se ajusta sobre datos equivocados | Se ajusta solo sobre validación, nunca sobre prueba, y el fichero del calibrador registra con qué corrida se hizo |
| n8n no habla MCP como esperamos | El endpoint REST es la contingencia ya comprometida en el cronograma; existe desde el día uno, no como parche |
| La imagen de Docker crece hasta hacerse inmanejable | Ruedas CPU de torch y `python:3.12-slim`; se mide el tamaño final y se registra |
| El VPS no tiene memoria suficiente | Límites declarados en el compose; el modelo son 16 MB y torch en CPU pide unos 500 MB de RSS |

## 11. Entregables de SP2

1. `src/copiloto_triaje/servicio/inferencia.py` — el núcleo, con pruebas.
2. `src/copiloto_triaje/servicio/mcp.py` y `.../rest.py` — las dos puertas.
3. `servidor/Dockerfile` y `servidor/docker-compose.yml`.
4. `scripts/ajustar_calibrador.py` y el `calibrador.json` que produce,
   versionado en el repositorio.
5. `docs/sp2-despliegue.md` — cómo levantarlo desde cero, para la prueba
   cruzada del otro integrante.
6. Registro de la latencia medida dentro del contenedor.

## 12. Deuda declarada

- **Grad-CAM** (SP5): los documentos lo comprometen como mitigación del riesgo
  de interpretabilidad. No se implementa aquí.
- **Calibración validada clínicamente**: la regresión isotónica sobre
  validación es correcta estadísticamente, pero la calidad del posterior
  bayesiano solo se puede juzgar con casos reales, en SP5.
- **Reportar el rendimiento por separado en placas AP y PA**: el EDA halló que
  las AP tienen 38,3% de opacidad frente al 9,3% de las PA, y los documentos
  comprometen medir ambas por separado. No se ha hecho todavía.
