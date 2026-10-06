# SP5-C1 — La interfaz de demostración y el umbral por vista

**Estado:** aprobado por el equipo en conversación el 5-oct-2026 (la app en
Docker en local; el despliegue público, después). Parte de: `main` con
SP5-B3 y el consentimiento nuevo fusionados.

## 1. Qué y por qué

La entrega final del curso evalúa con un 20 % una **interfaz de usuario** que
permita a cualquier persona probar el modelo de forma interactiva, y fija sus
mínimos: entrada con validación; indicador de carga y manejo de errores;
probabilidades con visualizaciones; una sección «Acerca de» con el modelo, sus
métricas y sus limitaciones; y ejemplos precargados con un botón «Prueba con
ejemplo». La estructura de carpetas que pide incluye `app/app.py`.

El bot de Telegram sigue siendo el producto: es lo que usa un profesional. Pero
no cumple esos mínimos —para probarlo hace falta una cuenta de Telegram, estar
en la lista blanca y pasar por el cuestionario del paciente; no tiene ejemplos
ni «Acerca de»—, y se retira del servidor después de la calificación. La app es
**la puerta de evaluación del mismo sistema**: el mismo motor, los mismos
pesos, la misma calibración y la misma combinación bayesiana.

Además, el workshop de la semana 4 compromete dos mitigaciones antes de
congelar el código: el **umbral por vista** como parámetro de despliegue
apagado por defecto (M1, paso 3) y un **mapa de calor** junto a la
probabilidad (M5).

## 2. Decisiones

| # | Decisión | Por qué |
| :--- | :--- | :--- |
| D1 | **Streamlit**, en `app/app.py` | Es la opción que la entrega recomienda y la estructura que pide |
| D2 | La app calcula **en su propio proceso con `Motor`** (`servicio/inferencia.py`): no llama al servidor, a n8n ni a Telegram | El mismo núcleo que el servidor: los resultados coinciden por construcción, y el mapa de calor necesita el modelo en el proceso |
| D3 | Se ejecuta en **Docker**, con una imagen propia (`app/Dockerfile`), publicada solo en `127.0.0.1:8501` | La calibración usa scikit-learn y en la máquina de desarrollo Windows no carga; Docker es además lo reproducible para cualquier evaluador. El despliegue público se decide después |
| D4 | **Umbral por vista** en `Motor`, opcional y apagado por defecto (§4) | M1 del workshop S4; sin él, la respuesta no cambia en nada |
| D5 | **Mapa de calor Grad-CAM** como método de `Motor` (§5), usado solo por la app | M5 del workshop S4; un único camino de imagen a tensor |
| D6 | **Ejemplos precargados de fuera de RSNA**, con licencia que permita redistribuirlos (§6) | El repositorio público solo referencia el conjunto de datos; nunca lo comparte (decisión del equipo, 5-oct) |
| D7 | Las métricas de «Acerca de» salen de un **JSON de agregados** (`app/assets/metricas.json`) | Las puntuaciones por placa no van al repositorio público (decisión del 5-oct); los agregados no son el conjunto de datos |
| D8 | Nada del cliente en la app: ninguna dirección de servidor, dominio ni nombre. Los nombres del equipo, como en el README | Regla de anonimato de SP5-B2, con la excepción decidida para el README |
| D9 | La interfaz, en español | El público del proyecto; el inglés, solo si sobra tiempo |

## 3. La pantalla

**Entrada.**

- Subir un DICOM (como el servidor: hasta 5 MB) **o** «Prueba con ejemplo»,
  con un selector de los ejemplos de §6.
- Los cinco hallazgos de Heckerling, opcionales en bloque: temperatura (°C) y
  frecuencia cardíaca (lpm) como números, con límites de interfaz razonables
  (30–45 °C, 20–250 lpm); crepitantes y murmullo disminuido (sí/no); asma
  (sí/no/no sé). Sin hallazgos, la app da solo la evidencia de la imagen, como
  el servidor sin `hallazgos`.
- Un interruptor «Umbral por vista (experimental)», apagado por defecto.

**Proceso.** Un botón «Calcular», con indicador de carga. Los rechazos del
motor (`dicom_invalido`, `edad_desconocida`, `fuera_de_alcance`,
`hallazgos_invalidos`) se muestran en lenguaje llano, con lo que el usuario
puede hacer; nunca una traza.

**Resultado.** En bloques rotulados, como el mensaje del bot:

- **Cribado**: la etiqueta, la puntuación frente al umbral aplicado y, con el
  interruptor encendido, la vista que se leyó.
- **Evidencia de la imagen**: la razón de verosimilitud y la probabilidad
  calibrada.
- **Clínica**: la puntuación de Heckerling y su razón de verosimilitud.
- **Combinado**: la probabilidad de partida y la horquilla (o el número, si las
  evidencias se contradicen) en un gráfico de 0 a 100 %, con el aviso de
  dependencia que da el motor.
- El aviso asimétrico de los negativos y «Esto no es un diagnóstico.».
- El **mapa de calor** superpuesto a la placa, con su advertencia: señala dónde
  mira el modelo, no por qué acierta.

**Sesión.** Un historial de las predicciones de la sesión y su descarga en
CSV, sin imagen.

**Acerca de.** Qué hace el sistema y qué no; el modelo (EfficientNet-B0,
calibración, cotas de la razón de verosimilitud, regla de Heckerling,
combinación); los datos (RSNA, **solo con referencias y enlaces**); las
métricas globales y por subgrupo (sexo, edad, vista) con sus intervalos; las
limitaciones (opacidad no es neumonía; datos de Estados Unidos; el sesgo por
vista y edad; validación semisintética); el umbral por vista y su precio; la
atribución de los ejemplos; y el aviso de que no es un producto sanitario.

## 4. El umbral por vista

- `Motor.__init__` y `Motor.cargar` aceptan `umbrales_por_vista: Mapping[str,
  float] | None = None`. Si no es `None`, tiene exactamente las claves `"PA"` y
  `"AP"`, cada una un número estrictamente entre 0 y 1; si no, `ValueError` al
  construir.
- En `clasificar`, con el parámetro: si la cabecera dice `PA` o `AP` (la
  `ViewPosition`, ya leída por `leer_dicom_desde_bytes`, en mayúsculas y sin
  espacios), la clasificación usa el umbral de esa vista; si no, el global.
- **La respuesta sin el parámetro es la de hoy, clave por clave** (criterio de
  aceptación de SP3 y SP4). Con el parámetro, `umbral` es el umbral
  **aplicado**, y aparece una clave nueva, `umbral_por_vista`, con `vista`
  (`"PA"`, `"AP"` o `null`) y `aplicado` (booleano).
- La razón de verosimilitud y la combinación **no cambian**: el umbral solo
  decide la etiqueta del cribado. Calibrar la razón de verosimilitud por vista
  queda fuera.
- **Servidor:** variables `UMBRAL_PA` y `UMBRAL_AP`, las dos o ninguna; con una
  sola, o fuera de (0, 1), `servidor/arrancar.py` se detiene diciendo cuál y por
  qué. El `docker-compose.yml` no las define: en producción, apagado. Encenderlo
  lo decide la institución.
- Los valores del workshop S4 (elegidos en validación, tabla 3): PA 0,1798 y
  AP 0,5815. La app los usa al encender el interruptor y los cita en «Acerca de».

## 5. El mapa de calor

- `Motor.mapa_de_calor(datos_dicom: bytes) -> numpy.ndarray`: lee el DICOM con
  el mismo lector, convierte con `_tensor_desde_arreglo` (el único camino de
  imagen a tensor) y calcula Grad-CAM sobre el último bloque convolucional de
  EfficientNet-B0, respecto del logit de opacidad.
- Devuelve una matriz del tamaño de entrada del modelo (320 × 320), con valores
  en [0, 1]; sin `nan` aunque la imagen sea uniforme (con gradiente nulo, una
  matriz de ceros). La app la reescala a la imagen original para superponerla.
- Rechaza lo mismo que `clasificar` (DICOM ilegible, edad desconocida o fuera de
  alcance), con los mismos códigos.
- No altera `clasificar`: después de calcular un mapa, la misma placa da la
  misma respuesta, y el modelo queda en modo evaluación y sin ganchos.

## 6. Los ejemplos

- Tres radiografías de tórax de adultos **de fuera de RSNA y del NIH** —una
  normal en PA, una con opacidad en PA y una en AP—, con una licencia que
  permita redistribuirlas (dominio público o CC0; CC BY con atribución), cada
  una con su licencia verificada en su página de origen.
- Se guardan en `app/assets/ejemplos/` ya empaquetadas como DICOM, con una
  edad, un sexo y una vista de ejemplo, junto al guion que las empaqueta
  (`app/empaquetar_ejemplos.py`) y un `app/assets/LICENCIAS.md` con la fuente,
  el autor, la licencia y la atribución de cada una.
- Un cuarto ejemplo, **«rechazado»**: la primera imagen con una edad de 15
  años, para enseñar cómo el sistema rechaza lo que no puede evaluar.
- La app avisa de que los ejemplos son de otra fuente y de que el modelo se
  entrenó con RSNA: su rendimiento con ellos no está medido.
- Cada binario nuevo se revisa a mano y se declara en la prueba de los binarios
  y en la declaración de anonimato (`tests/anonimato/README.md`), como pide
  SP5-B2. La descarga de las imágenes la aprueba el equipo, fichero a fichero.

## 7. Las métricas de «Acerca de»

`app/generar_metricas.py` lee las puntuaciones congeladas de prueba (y las de
validación, si están) y escribe `app/assets/metricas.json` con agregados: AUC,
recall y especificidad con sus intervalos de Wilson, global y por subgrupo, y
los umbrales por vista. Ninguna fila por paciente. El JSON lleva la huella
(sha256) de los pesos y de las puntuaciones de las que sale, para que se pueda
comprobar. En el repositorio público van el guion y el JSON; las puntuaciones
por placa, no.

## 8. Ejecución

    docker build -t copiloto-app -f app/Dockerfile .
    docker run --rm -p 127.0.0.1:8501:8501 --memory=2g --memory-swap=2g copiloto-app

y abrir `http://127.0.0.1:8501`. Los pesos no están en git (como en el
servidor): el `docker build` los toma de `servidor/pesos_modelo_cpu.pt`, y el
README dice de dónde descargarlos. Las variables `UMBRAL`, `AUC_VALIDACION` y
`PREVALENCIA_LOCAL` se fijan en la imagen con los mismos valores que el
`docker-compose.yml` del servidor, y la app los muestra.

Sin Docker, se lanza desde `app/` (`cd app` y `streamlit run app.py`): Streamlit lee
`.streamlit/config.toml` del directorio desde el que se lanza, y desde la raíz no hay
ninguno.

## 9. Pruebas

- **Motor, umbral por vista:** sin el parámetro, la salida es la de hoy clave
  por clave; con él, PA y AP aplican su umbral y la etiqueta cambia donde debe;
  sin vista o con una vista que no es PA ni AP, el global y `aplicado: false`;
  parámetros mal formados dan `ValueError`; la razón de verosimilitud y la
  combinación no cambian; `arrancar.py` con una sola variable se detiene.
- **Mapa de calor:** forma, rango, determinismo, la imagen uniforme sin `nan`,
  los rechazos con sus códigos, y que `clasificar` no cambia después.
- **App** (`streamlit.testing.v1.AppTest`): arranca sin excepciones; cada
  ejemplo da su resultado y el «rechazado», su mensaje; hallazgos fuera de los
  límites se rechazan; el interruptor cambia el umbral aplicado; el historial y
  el CSV llevan lo que deben y ninguna imagen.
- **Ejemplos:** cada DICOM se lee con el lector del proyecto y declara la edad,
  el sexo y la vista que dice `LICENCIAS.md`, y cada uno tiene su licencia.
- **Métricas:** el JSON coincide con lo que se recalcula de las puntuaciones
  (cuando están) y no lleva ninguna fila por paciente.
- **Imagen Docker:** se construye y la página responde (prueba de humo).
- **Anonimato:** el verificador sale con 0, y los binarios nuevos están
  declarados.

## 10. Fuera de alcance

La calibración por vista de la razón de verosimilitud; el despliegue público
(Hugging Face u otro, se revisa después); la interfaz en inglés; el dashboard
de métricas de n8n (SP3 §15), que es otro trabajo.

## 11. Riesgos

| Riesgo | Mitigación |
| :--- | :--- |
| Los ejemplos son de otra fuente y el modelo puede rendir distinto con ellos | Se dice en la app; son ilustrativos |
| El mapa de calor se lee como explicación causal | La advertencia, junto al mapa |
| Encender el umbral por vista en producción sin mirar su precio | Apagado por defecto; «Acerca de» y el workshop S4 enseñan la tabla 3 |
| La imagen Docker pesa (torch en CPU) | Aceptable para una demostración; se documenta |
| Una dependencia nueva rompe la suite | Versiones fijadas; la suite se corre en la imagen Linux |
