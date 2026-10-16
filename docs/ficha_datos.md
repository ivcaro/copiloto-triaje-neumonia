# Ficha de datos: RSNA Pneumonia Detection Challenge

**Copiloto de triaje para neumonía en adultos** · Ficha de datos (*datasheet*) siguiendo el
esquema de Gebru et al., «Datasheets for datasets» (2021).

Esta ficha cumple el compromiso M5 del workshop de impacto social de la Semana 4 (ficha del
conjunto de datos). Complementa la ficha del modelo (`docs/ficha_modelo.md`) y el análisis
exploratorio (`docs/analisis_datos.md`). Estado a **15 de octubre de 2026**.

**Qué documenta.** El conjunto de datos **tal como lo usa este proyecto**: la parte de adultos
del conjunto de entrenamiento del RSNA Pneumonia Detection Challenge (2018), sus particiones y
sus preparaciones. No la escribió quien creó el dataset. Las respuestas sobre cómo se recogió
originalmente salen de los artículos publicados y de las condiciones de uso; **donde las
fuentes del proyecto no lo dicen, la ficha pone «no consta»** en vez de suponerlo.

## Ficha resumida

| | |
| :--- | :--- |
| Nombre | RSNA Pneumonia Detection Challenge (2018), conjunto de entrenamiento de la fase 2 |
| Origen | Subconjunto del NIH ChestX-ray14 (NIH Clinical Center, EE. UU.), con anotaciones de radiólogos organizadas por la RSNA |
| Tamaño | 26 684 radiografías frontales de tórax en DICOM, una por paciente; 25 403 de adultos (18 a 100 años) usadas por el proyecto |
| Tarea | Opacidad pulmonar compatible con neumonía: clasificación binaria (el proyecto) y detección con cajas (la competición) |
| Positivos | 6 012 de 26 684 (22,5 %); 5 627 de 25 403 de adultos (22,15 %) |
| Condiciones | Términos de la competición de Kaggle («Subject to Competition Rules») y condiciones de uso y atribución de la RSNA |
| **Redistribución** | **No se redistribuye.** El repositorio solo lo referencia, con cifras agregadas |
| Fecha de la copia del proyecto | Inspeccionada el 16 de septiembre de 2026 |

## Contenido

1. [Motivación](#1-motivación)
2. [Composición](#2-composición)
3. [Proceso de recolección](#3-proceso-de-recolección)
4. [Preprocesamiento, limpieza y etiquetado](#4-preprocesamiento-limpieza-y-etiquetado)
5. [Usos](#5-usos)
6. [Distribución](#6-distribución)
7. [Mantenimiento](#7-mantenimiento)
8. [Sesgos y limitaciones conocidos](#8-sesgos-y-limitaciones-conocidos)
9. [Referencias](#9-referencias)

## 1. Motivación

**¿Para qué se creó el dataset?** Para el RSNA Pneumonia Detection Challenge de 2018, una
competición en Kaggle patrocinada por la Radiological Society of North America (RSNA) para
detectar en radiografías de tórax opacidades pulmonares que pueden representar neumonía. El
artículo del dataset es Shih et al. (2019) (Presentación del proyecto, Semana 1, §4.1;
investigación de la Semana 4, §7).

**¿Quién lo creó?** Las imágenes son del NIH Clinical Center (conjunto ChestX-ray14, Wang
et al., 2017) y la RSNA las re-anotó con radiólogos. Quién financió cada parte y cómo se
compensó a los anotadores no consta en las fuentes del proyecto.

**¿Por qué lo eligió este proyecto?** La Semana 1 comparó tres datasets (Presentación del
proyecto, §4):

| Dataset | Papel | Razón |
| :--- | :--- | :--- |
| **RSNA Pneumonia Detection Challenge** | Principal | La mejor anotación específica de neumonía entre los datasets abiertos, hecha por radiólogos; adultos; tamaño manejable; acceso inmediato tras aceptar las reglas |
| PadChest (BIMCV) | Validación externa, si el trámite llegaba a tiempo | Origen distinto e informes en español. El acuerdo de uso no se gestionó y se descartó |
| NIH ChestX-ray14 | Plan B | Etiquetas automáticas con errores conocidos y mucho más pesado; no hizo falta |

Se descartaron explícitamente el conjunto pediátrico de Kermany (población de 1 a 5 años,
identificadores repetidos entre particiones —fuga de datos— y un conjunto de validación de 16
imágenes) y el COVID-19 Radiography Database (sus clases proceden de RSNA y de Kermany: ni es
independiente ni es de adultos).

## 2. Composición

### 2.1 Qué es cada instancia

Una radiografía de tórax de un paciente, en formato DICOM, con sus metadatos de cabecera, una
etiqueta de tres clases y cero o más cajas de opacidad. Hay **una imagen por paciente**: los
26 684 identificadores son distintos. Los identificadores son códigos opacos; los metadatos que
extrae el proyecto no incluyen nombres ni historias clínicas.

### 2.2 Cuántas y de qué tipo

| Elemento | Cantidad |
| :--- | ---: |
| DICOM de entrenamiento con etiquetas (`stage_2_train_images`) | 26 684 |
| DICOM de prueba de la competición, sin etiquetas públicas (**no se usan**) | 3 000 |
| Filas del CSV de etiquetas (una por caja, más una por paciente sin cajas) | 30 227 |
| Cajas de opacidad (en 6 012 pacientes positivos) | 9 555 |
| Radiografías de adultos de 18 a 100 años que usa el proyecto | 25 403 |

Es un **subconjunto** del NIH ChestX-ray14, que en su versión completa tiene 112 120
radiografías de 30 805 pacientes. El criterio con que se escogieron las 26 684 no consta en las
fuentes del proyecto, y por eso no se puede afirmar que sean una muestra representativa de
ChestX-ray14 ni de ninguna población clínica.

### 2.3 Qué datos lleva cada instancia

| Dato | Detalle |
| :--- | :--- |
| Píxeles | 1 024 × 1 024, 8 bits, `MONOCHROME2`, un solo cuadro; en todas las imágenes |
| Modalidad y parte | CR, tórax: en todas |
| Metadatos que extrae el proyecto de la cabecera | Edad, sexo, proyección (PA o AP), dimensiones, profundidad de bits, peso del archivo |
| Etiqueta de tres clases | `Lung Opacity`, `No Lung Opacity / Not Normal`, `Normal` |
| Cajas | Cero a cuatro por paciente: 2 614 pacientes con una, 3 266 con dos, 119 con tres y 13 con cuatro |

### 2.4 Etiquetas

La etiqueta binaria del proyecto es **positivo si la placa tiene al menos una caja de
opacidad**; el resto, normales y anormales sin opacidad, es negativo. La clase positiva es una
**opacidad pulmonar compatible con neumonía**, no neumonía confirmada.

| Clase | Pacientes | Proporción | Etiqueta binaria |
| :--- | ---: | ---: | :-: |
| `Lung Opacity` | 6 012 | 22,5 % | Positivo |
| `No Lung Opacity / Not Normal` | 11 821 | 44,3 % | Negativo |
| `Normal` | 8 851 | 33,2 % | Negativo |

### 2.5 Datos faltantes, errores y ruido

- **Faltantes:** ninguno en los metadatos extraídos (`docs/analisis_datos.md`, sección 3).
- **Edades fuera del alcance:** 1 276 pacientes (4,78 %) son menores de 18 años, desde 1 año, y
  cinco tienen edades imposibles (148, 150, 151, 153 y 155 años). El proyecto los excluye
  (sección 4).
- **Ruido de etiqueta:** las etiquetas originales de ChestX-ray14 se extrajeron de informes
  radiológicos por procesamiento de lenguaje natural y tienen errores conocidos (Wang et al.);
  la RSNA re-anotó las opacidades con radiólogos. El proyecto **no midió** el ruido de la
  etiqueta ni la variabilidad entre lectores.
- **Duplicados:** el proyecto verifica que ningún identificador de paciente aparezca en dos
  conjuntos. No comprobó duplicados de imagen bajo identificadores distintos.

### 2.6 Subpoblaciones

Se distinguen por los metadatos extraídos. Cálculo sobre los adultos (25 403) y sobre las
26 684 placas, en `docs/analisis_datos.md`.

| Variable | Distribución |
| :--- | :--- |
| Sexo (26 684) | Hombres 56,8 %; mujeres 43,2 % |
| Edad (adultos) | 18 a 39 años: 28,5 %; 40 a 59: 45,7 %; 60 o más: 25,8 % |
| Proyección (adultos) | PA 54,9 %; AP 45,1 % |
| Raza, etnia, nivel socioeconómico | **No consta**: no están en los metadatos extraídos |

### 2.7 Datos sensibles e identificables

Son datos de salud, de la categoría que la normativa de protección de datos trata como
sensible. Las placas de RSNA están desidentificadas y las condiciones de la RSNA prohíben
intentar identificar o contactar a los sujetos. El proyecto no lo intenta y no guarda ninguna
imagen en su repositorio. Los aspectos legales y éticos están en
`docs/consideraciones_eticas.md`.

## 3. Proceso de recolección

| Pregunta | Respuesta |
| :--- | :--- |
| ¿Cómo se adquirieron los datos? | Radiografías clínicas del NIH Clinical Center (ChestX-ray14), con etiquetas extraídas de los informes por procesamiento de lenguaje natural. La RSNA seleccionó un subconjunto y radiólogos anotaron cajas sobre opacidades que pueden representar neumonía (Wang et al., 2017; Shih et al., 2019) |
| ¿Quién anotó y con qué criterio? | Radiólogos organizados por la RSNA; la etiqueta positiva es la presencia de opacidad, sin confirmación de laboratorio. El detalle del procedimiento de anotación está en Shih et al. y no se reproduce aquí |
| ¿Cuándo? | La competición es de 2018. El periodo de adquisición de las imágenes no consta en las fuentes del proyecto |
| ¿Dónde? | Un único centro: el NIH Clinical Center, en EE. UU. |
| ¿Hubo revisión ética o consentimiento de los pacientes? | No consta en las fuentes del proyecto. Se trata de datos retrospectivos desidentificados que la RSNA distribuye con condiciones de uso |
| ¿Cuándo y cómo obtuvo el proyecto su copia? | Descarga del paquete de la competición con la API de Kaggle tras aceptar las reglas (`kaggle competitions download -c rsna-pneumonia-detection-challenge`); archivo inspeccionado el 16 de septiembre de 2026 (spec de SP1, §4) |

## 4. Preprocesamiento, limpieza y etiquetado

Lo que el proyecto hace con los datos originales, en orden. Las razones están en
`docs/analisis_datos.md` (sección 8).

| Paso | Qué hace | Dónde |
| :--- | :--- | :--- |
| 1. Extracción de metadatos | Lee solo las cabeceras de los 26 684 DICOM (26 segundos) y escribe una tabla de 17 columnas | `scripts/extraer_metadatos.py` |
| 2. Etiqueta binaria | Positivo si hay al menos una caja de opacidad | `src/copiloto_triaje/datos/preparacion.py` |
| 3. Filtro de edad | Se conservan los pacientes de 18 a 100 años: se descartan 1 276 menores y cinco edades imposibles; quedan 25 403. El descarte queda escrito, con su motivo, en un fichero | `filtrar_por_edad` |
| 4. Conversión | DICOM a PNG de 8 bits, sin ventaneo (RSNA ya es de 8 bits); un DICOM corrupto se omite y se registra | `src/copiloto_triaje/datos/dicom.py` |
| 5. Partición | 70/15/15 por paciente, estratificada por etiqueta, con semilla 42: 17 782, 3 810 y 3 811 placas. Verificación automática de que ningún paciente está en dos conjuntos | `src/copiloto_triaje/datos/particion.py` |
| 6. Entrada al modelo | Redimensionado a 320 × 320, tres canales, normalización con las estadísticas de ImageNet. Aumento de datos solo en entrenamiento: rotación de ±7°, desplazamiento del 5 %, brillo y contraste de ±0,15; sin volteo horizontal | `src/copiloto_triaje/datos/dataset.py` |

**¿Se conservan los datos originales sin preprocesar?** Sí, en la copia local de quien
prepara los datos; el repositorio no guarda ninguno (sección 6). **Software:** Python, pydicom,
Pillow, torchvision y pandas, con las versiones de `requirements.txt`. El procedimiento
paso a paso está en `data/README.md` y en `notebooks/02_preprocesamiento.ipynb`.

## 5. Usos

**Uso en este proyecto.** Entrenar, validar, calibrar y probar un clasificador de opacidad
compatible con neumonía (EfficientNet-B0) y medir su rendimiento por subgrupos (sexo, edad,
proyección). Las 3 811 placas de prueba son una partición propia: el conjunto de prueba oficial
de la competición no tiene etiquetas públicas.

**Usos para los que es adecuado.** Investigación y educación en detección de opacidades
pulmonares en radiografía frontal de adultos, siempre con atribución y sin intentar identificar
a los sujetos (condiciones de la RSNA).

**Otros usos posibles.** Detección y localización con cajas (la tarea original de la
competición); el proyecto solo hace clasificación.

**Usos que no se recomiendan, y por qué:**

| Uso | Razón |
| :--- | :--- |
| Decidir sobre un paciente real | La etiqueta es opacidad y no neumonía confirmada; no hay validación con datos de un centro real ni con la clínica emparejada |
| Aplicarlo a niños | El dataset trae menores, pero la neumonía infantil y la anatomía son distintas y el proyecto no los validó |
| Estimar prevalencia en una población | RSNA es un conjunto de radiografías ya indicadas, no la población que llega con tos; su 22,5 % no es una prevalencia clínica (el proyecto declara aparte una de 0,1466) |
| Evaluar la generalización a otros hospitales, equipos o países | Origen único; sin validación externa |
| Usar la proyección, el peso del archivo o el número de cajas como variable | Son atajos o la etiqueta misma (sección 8) |

**Efecto de la composición sobre los usos.** Un modelo entrenado aquí puede aprender
atajos: la proyección predice la etiqueta, y los modelos de radiografía de tórax se han mostrado
capaces de explotar atajos de ese tipo y de rendir distinto en hospitales distintos (Zech et
al., 2018; DeGrave et al., 2021). Quien reutilice el dataset debería medir el rendimiento por
proyección y por subgrupo, como hace este proyecto.

## 6. Distribución

**¿Se distribuye el dataset desde este repositorio?** **No.** El repositorio público no
incluirá imágenes, ni etiquetas, ni tablas con una fila por paciente; solo referencias, cifras
agregadas (`app/assets/metricas.json`) y los guiones que regeneran todo desde el conjunto que
cada persona descarga. Las dos tablas de trabajo del repositorio de desarrollo
(`docs/eda/metadatos_eda.csv` y `docs/validacion-semisintetica/crudas_prueba.csv`) no viajan a
él, por decisión del equipo del 5 de octubre (`data/README.md`). Los ejemplos de la interfaz son de otra fuente (tres radiografías de
Wikimedia Commons con licencia CC0).

**Por qué.** Las reglas de la competición de Kaggle conservan una cláusula general (7.B) que
prohíbe duplicar, publicar o redistribuir los datos a quien no participe en la competición. Las
condiciones propias de la RSNA, en cambio, permiten usar los datos con fines académicos y de
educación «y otros fines comerciales o no comerciales», y redistribuirlos con atribución. Hay
tensión entre las dos (investigación de la Semana 4, §7.3), y el equipo eligió la lectura más
prudente: no redistribuir. Es una lectura del equipo, no asesoría legal.

**Cómo obtenerlo.**

- En Kaggle, aceptando las reglas de la competición: `kaggle competitions download -c
  rsna-pneumonia-detection-challenge` (requiere credenciales de la API de Kaggle).
- En el sitio de la RSNA, que ofrece cuatro descargas (imágenes del NIH, anotaciones iniciales,
  imágenes y anotaciones de la competición, y la tabla de correspondencia RSNA-NIH):
  <https://www.rsna.org/education/ai-resources-and-training/ai-image-challenge/RSNA-Pneumonia-Detection-Challenge-2018>.

**Condiciones de uso** (documento «Pneumonia Detection Challenge Terms of Use and
Attribution» de la RSNA):

1. No intentar identificar ni contactar a ningún sujeto de los datos.
2. Si se comparten o redistribuyen los datos en cualquier forma, atribuirlos: enlazar el sitio de
   descarga del NIH, citar el artículo de Wang et al. (CVPR, 2017) y reconocer al NIH Clinical
   Center como proveedor; y enlazar el sitio de descarga de la RSNA y citar el artículo de Shih
   et al. (2019).

La página de datos de Kaggle declara la licencia como «Subject to Competition Rules». Ni la
licencia MIT del código del repositorio ni la CC BY-NC 4.0 de los pesos **cubren los datos**.

**Los pesos entrenados con estos datos.** El modelo se publica como una descarga del release
del repositorio, con licencia CC BY-NC 4.0 (el código es MIT; `models/README.md`). El equipo
leyó las condiciones de la RSNA y las reglas de la competición: la cláusula 7.B de Kaggle
prohíbe redistribuir los **datos**, no un modelo entrenado con ellos, y las condiciones de la
RSNA piden atribuir el conjunto (citar a Wang et al. y a Shih et al., en las referencias) y no
intentar identificar a ningún sujeto. Se publican, pues, los pesos con esa atribución y **sin
ninguna imagen ni etiqueta**. Es la lectura del equipo, no asesoría legal.

## 7. Mantenimiento

| Pregunta | Respuesta |
| :--- | :--- |
| ¿Quién mantiene el dataset original? | La RSNA (la competición y sus descargas), Kaggle (su alojamiento) y el NIH (el conjunto de origen) |
| ¿Quién mantiene lo que el proyecto hace con él? | El equipo: los guiones, el filtro de edad, las particiones y las cifras agregadas, versionados en el repositorio |
| ¿Se actualiza? | No. La competición está cerrada y los datos son estáticos; el proyecto usa la copia del 16 de septiembre de 2026 |
| ¿Cómo se comunican las correcciones? | Por escrito y con fecha. Dos del proyecto: el documento de la Semana 1 daba 15 000 positivos y 15 000 negativos (la proporción real de positivos es 22,5 %) y lo describía como «de adultos» (4,78 % son menores de 18 años). Ambas se corrigieron en el Registro de cambios |
| ¿Cómo se contacta? | Para dudas sobre cómo usa el proyecto el dataset: las Issues del repositorio. Para el dataset original: la RSNA y Kaggle |
| ¿Cómo se amplía o se sustituye? | El pipeline lee manifiestos de partición (CSV), no el directorio. Otro conjunto con el mismo formato de manifiesto, y que se convierta a PNG de 8 bits, podría entrar, pero el filtro y las validaciones están pensados para RSNA |
| ¿Cuánto tiempo se conservan los datos? | El repositorio no conserva radiografías. En el bot y en la interfaz tampoco se guarda la imagen: la procesan y la descartan |

## 8. Sesgos y limitaciones conocidos

Es lo que obliga a leer con reserva cualquier métrica obtenida con este dataset. La evidencia y
el efecto sobre el modelo están en `docs/analisis_datos.md`, `docs/optimizacion.md` y
`docs/consideraciones_eticas.md`.

| Sesgo o limitación | Evidencia | Efecto | Qué se hizo |
| :--- | :--- | :--- | :--- |
| **La proyección AP/PA predice la etiqueta** | 38,3 % de opacidad en AP frente a 9,3 % en PA (26 684 placas); correlación de 0,346 con la etiqueta | Riesgo de aprendizaje por atajo. Con un umbral único el modelo deja pasar el 31 % de las opacidades en PA (recall 0,693) y marca como sospechosas el 61 % de las AP sin opacidad | Se mide por proyección; umbral por vista opcional y apagado por defecto, con su precio en especificidad |
| **Origen único** | Todas las placas son del NIH Clinical Center | El rendimiento en otros equipos, poblaciones y prevalencias no está garantizado; no hay validación externa | Se declara; la validación local es condición de cualquier uso clínico |
| **Etiqueta proxy** | Opacidad compatible con neumonía, no confirmada; etiquetas originales por lenguaje natural | El modelo aprende lo que anotaron los radiólogos, con su variabilidad | Todos los textos dicen «opacidad»; cada resultado negativo avisa de que no descarta la neumonía |
| **Composición demográfica desigual** | Hombres 56,8 %; 60 años o más, 25,8 % de los adultos; la opacidad baja del 24,2 % (18 a 39 años) al 20,6 % (60 o más) | Menos datos en los mayores, donde el AUC es menor (0,854 en prueba) | Métricas por sexo, edad y proyección con sus intervalos |
| **Sin raza, etnia ni nivel socioeconómico** | No están en los metadatos extraídos | El sesgo por esas variables no se puede auditar | Se declara como límite |
| **Peso del archivo** | Correlación de −0,20 con la etiqueta; las placas con opacidad y las AP pesan menos | Segundo atajo potencial, probablemente ligado a la proyección | No se usa como variable; el modelo ve solo la imagen |
| **Prevalencia de RSNA ≠ prevalencia clínica** | 22,5 % de positivos en un conjunto de placas ya indicadas | Una probabilidad calibrada en RSNA no vale tal cual en otra población | La salida se entrega como razón de verosimilitud y el previo se declara aparte (0,1466 por defecto) |
| **Menores y edades imposibles** | 1 276 menores (30,2 % con opacidad) y cinco edades de 148 a 155 años | Contradicen el alcance «adultos» | Filtro de 18 a 100 años en datos y en inferencia |
| **Formato único** | Todas las imágenes son CR, 8 bits, `MONOCHROME2` y 1 024 × 1 024 | Una placa de otro formato queda fuera de lo que el modelo vio | El servidor y la interfaz rechazan por la cabecera lo que no es de ese formato |
| **Las particiones son del mismo dataset** | Entrenamiento, validación y prueba salen de la misma fuente | Las métricas miden validez interna, no generalización | Se declara; la prueba se mira una sola vez con la configuración elegida |

## 9. Referencias

- T. Gebru *et al.*, «Datasheets for datasets», *Commun. ACM*, vol. 64, n.º 12, pp. 86–92, dic.
  2021, doi: 10.1145/3458723.
- G. Shih *et al.*, «Augmenting the National Institutes of Health chest radiograph dataset with
  expert annotations of possible pneumonia», *Radiol. Artif. Intell.*, vol. 1, n.º 1, art.
  e180041, ene. 2019, doi: 10.1148/ryai.2019180041.
- X. Wang, Y. Peng, L. Lu, Z. Lu, M. Bagheri y R. M. Summers, «ChestX-ray8: hospital-scale
  chest X-ray database and benchmarks on weakly-supervised classification and localization of
  common thorax diseases», en *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, 2017,
  pp. 3462–3471, doi: 10.1109/CVPR.2017.369.
- J. R. Zech, M. A. Badgeley, M. Liu, A. B. Costa, J. J. Titano y E. K. Oermann, «Variable
  generalization performance of a deep learning model to detect pneumonia in chest
  radiographs: a cross-sectional study», *PLOS Med.*, vol. 15, n.º 11, art. e1002683, nov.
  2018, doi: 10.1371/journal.pmed.1002683.
- A. J. DeGrave, J. D. Janizek y S.-I. Lee, «AI for radiographic COVID-19 detection selects
  shortcuts over signal», *Nat. Mach. Intell.*, vol. 3, n.º 7, pp. 610–619, 2021, doi:
  10.1038/s42256-021-00338-7.
- Radiological Society of North America, «Pneumonia Detection Challenge Terms of Use and
  Attribution». Consultado: 5 oct. 2026. [En línea]. Disponible:
  https://www.rsna.org/-/media/files/rsna/education/ai-resources-and-training/ai-image-challenge/pneumonia-detection-challenge-terms-of-use-and-attribution.pdf
- Radiological Society of North America y Kaggle, «RSNA Pneumonia Detection Challenge: Rules»,
  2018. Consultado: 5 oct. 2026. [En línea]. Disponible: https://www.kaggle.com/competitions/rsna-pneumonia-detection-challenge/rules
